"""
GoldVault Ledger - Change Request System
Employees submit change requests; Admins approve or reject them.
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from backend.database import get_db
from backend.calculations import to_995_basis
from backend.audit import log_action

logger = logging.getLogger(__name__)


def create_request(
    entry_id: int,
    changes_dict: Dict[str, Any],
    reason: str,
    user_id: int
) -> int:
    """
    Create a pending change request for an existing entry.

    Args:
        entry_id: ID of the entry to change.
        changes_dict: Dict of field -> new_value pairs.
        reason: Required reason text.
        user_id: ID of the requesting user.

    Returns:
        New change_request ID.

    Raises:
        ValueError: If entry not found or reason is empty.
    """
    if not reason or not reason.strip():
        raise ValueError("A reason is required for change requests.")

    conn = get_db()
    entry = conn.execute("SELECT id FROM entries WHERE id = ?", (entry_id,)).fetchone()
    if not entry:
        raise ValueError(f"Entry ID {entry_id} not found.")

    # Check for existing pending request on same entry
    existing = conn.execute(
        "SELECT id FROM change_requests WHERE entry_id = ? AND status = 'pending'",
        (entry_id,)
    ).fetchone()
    if existing:
        raise ValueError("A pending change request already exists for this entry.")

    cursor = conn.execute(
        """INSERT INTO change_requests (entry_id, requested_changes, reason, requested_by)
           VALUES (?, ?, ?, ?)""",
        (entry_id, json.dumps(changes_dict, default=str), reason.strip(), user_id)
    )
    conn.commit()
    logger.info("Change request created: entry_id=%d by user_id=%d", entry_id, user_id)
    return cursor.lastrowid


def get_requests(
    status: Optional[str] = None,
    user_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve change requests with joined entry and user data.

    Args:
        status: Filter by 'pending', 'approved', 'rejected', or None for all.
        user_id: Filter by requesting user ID.

    Returns:
        List of request dicts.
    """
    conn = get_db()
    conditions = []
    params = []

    if status:
        conditions.append("cr.status = ?")
        params.append(status)
    if user_id:
        conditions.append("cr.requested_by = ?")
        params.append(user_id)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    query = f"""
        SELECT cr.id, cr.entry_id, cr.requested_changes, cr.reason,
               cr.requested_at, cr.status, cr.approved_at, cr.admin_remarks,
               u1.username AS requested_by_name,
               u2.username AS approved_by_name,
               e.entry_number, e.entry_date, e.entry_time,
               e.direction, e.raw_weight, e.purity, e.converted_weight,
               e.balance_after, e.remarks AS entry_remarks,
               s.name AS smith_name
        FROM change_requests cr
        JOIN entries e ON cr.entry_id = e.id
        JOIN smiths s ON e.smith_id = s.id
        JOIN users u1 ON cr.requested_by = u1.id
        LEFT JOIN users u2 ON cr.approved_by = u2.id
        {where}
        ORDER BY cr.requested_at DESC
    """
    rows = conn.execute(query, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        # Parse JSON changes for display
        try:
            d['requested_changes_parsed'] = json.loads(d['requested_changes'])
        except Exception:
            d['requested_changes_parsed'] = {}
        result.append(d)
    return result


def approve_request(
    req_id: int,
    admin_id: int,
    admin_remarks: str = ""
) -> None:
    """
    Approve a change request:
    1. Apply requested changes to the entry.
    2. Recalculate the Smith's balance from scratch.
    3. Log to audit.
    4. Mark request as approved.

    Raises:
        ValueError: If request not found or not pending.
    """
    conn = get_db()
    req = conn.execute(
        "SELECT * FROM change_requests WHERE id = ? AND status = 'pending'",
        (req_id,)
    ).fetchone()
    if not req:
        raise ValueError(f"Pending change request ID {req_id} not found.")

    entry_id = req['entry_id']
    original_entry = dict(conn.execute(
        "SELECT * FROM entries WHERE id = ?", (entry_id,)
    ).fetchone())

    changes = json.loads(req['requested_changes'])

    # Build updated entry values
    new_entry = dict(original_entry)
    for field, value in changes.items():
        if field in ('entry_date', 'entry_time', 'direction', 'raw_weight', 'purity', 'remarks'):
            new_entry[field] = value

    # Validate new values
    if new_entry['raw_weight'] <= 0:
        raise ValueError("Weight must be > 0.")
    if new_entry['purity'] <= 0 or new_entry['purity'] > 1000:
        raise ValueError("Purity must be between 0 and 1000.")

    # Recompute converted weight for this entry
    new_converted = to_995_basis(
        float(new_entry['raw_weight']),
        float(new_entry['purity']),
        new_entry['direction']
    )
    new_entry['converted_weight'] = new_converted

    # Update the entry (balance_after will be fixed by recalculation)
    conn.execute(
        """UPDATE entries SET entry_date=?, entry_time=?, direction=?,
           raw_weight=?, purity=?, converted_weight=?, remarks=?
           WHERE id=?""",
        (
            new_entry['entry_date'], new_entry['entry_time'],
            new_entry['direction'], new_entry['raw_weight'],
            new_entry['purity'], new_entry['converted_weight'],
            new_entry['remarks'], entry_id
        )
    )
    conn.commit()

    # Recalculate Smith's balance from scratch
    from backend.entries import recalculate_smith_balance
    recalculate_smith_balance(original_entry['smith_id'])

    # Fetch updated entry for audit
    updated_entry = dict(conn.execute(
        "SELECT * FROM entries WHERE id = ?", (entry_id,)
    ).fetchone())

    # Log audit
    log_action(
        action='approve_request',
        original_data=original_entry,
        new_data=updated_entry,
        changed_by=req['requested_by'],
        approved_by=admin_id,
        remarks=f"Request #{req_id} approved. {admin_remarks}"
    )

    # Mark request approved
    conn.execute(
        """UPDATE change_requests SET status='approved', approved_by=?, approved_at=datetime('now'), admin_remarks=?
           WHERE id=?""",
        (admin_id, admin_remarks, req_id)
    )
    conn.commit()
    logger.info("Change request %d approved by admin %d", req_id, admin_id)


def reject_request(
    req_id: int,
    admin_id: int,
    admin_remarks: str
) -> None:
    """
    Reject a change request. No data changes; just mark as rejected.

    Raises:
        ValueError: If request not found, not pending, or no reason given.
    """
    if not admin_remarks or not admin_remarks.strip():
        raise ValueError("A reason is required to reject a change request.")

    conn = get_db()
    req = conn.execute(
        "SELECT id, entry_id, requested_by FROM change_requests WHERE id = ? AND status = 'pending'",
        (req_id,)
    ).fetchone()
    if not req:
        raise ValueError(f"Pending change request ID {req_id} not found.")

    conn.execute(
        """UPDATE change_requests SET status='rejected', approved_by=?, approved_at=datetime('now'), admin_remarks=?
           WHERE id=?""",
        (admin_id, admin_remarks.strip(), req_id)
    )
    conn.commit()

    log_action(
        action='reject_request',
        original_data={'request_id': req_id, 'entry_id': req['entry_id']},
        new_data=None,
        changed_by=req['requested_by'],
        approved_by=admin_id,
        remarks=f"Rejected: {admin_remarks}"
    )
    logger.info("Change request %d rejected by admin %d", req_id, admin_id)
