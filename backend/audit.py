"""
GoldVault Ledger - Audit Logging
Records all data-modifying actions with full before/after snapshots.
"""

import json
import logging
from typing import Optional, Any, Dict

from backend.database import get_db

logger = logging.getLogger(__name__)


def log_action(
    action: str,
    original_data: Optional[Any],
    new_data: Optional[Any],
    changed_by: int,
    approved_by: Optional[int] = None,
    remarks: str = ""
) -> int:
    """
    Insert a record into audit_log.

    Args:
        action: Short description, e.g. 'add_entry', 'edit_entry', 'delete_entry',
                'approve_request', 'reject_request', 'clear_data', 'create_user',
                'edit_user', 'delete_user', 'backup', 'restore'.
        original_data: Dict or None – serialised to JSON.
        new_data: Dict or None – serialised to JSON.
        changed_by: User ID who performed the action.
        approved_by: Admin user ID if different from changed_by (e.g., for approvals).
        remarks: Optional free-text note.

    Returns:
        ID of the new audit_log row.
    """
    conn = get_db()

    orig_json = json.dumps(original_data, default=str) if original_data is not None else None
    new_json = json.dumps(new_data, default=str) if new_data is not None else None

    cursor = conn.execute(
        """INSERT INTO audit_log (action, original_data, new_data, changed_by, approved_by, remarks)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (action, orig_json, new_json, changed_by, approved_by, remarks)
    )
    conn.commit()
    logger.debug("Audit log: action=%s by user=%d", action, changed_by)
    return cursor.lastrowid


def get_audit_log(
    action_filter: Optional[str] = None,
    user_filter: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 500,
    offset: int = 0
) -> list:
    """
    Retrieve audit log entries with optional filters.

    Returns list of dicts with joined user names.
    """
    conn = get_db()

    conditions = []
    params = []

    if action_filter:
        conditions.append("al.action LIKE ?")
        params.append(f"%{action_filter}%")
    if user_filter:
        conditions.append("al.changed_by = ?")
        params.append(user_filter)
    if date_from:
        conditions.append("al.timestamp >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("al.timestamp <= ?")
        params.append(date_to + " 23:59:59")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    query = f"""
        SELECT al.id, al.action, al.original_data, al.new_data,
               al.timestamp, al.remarks,
               u1.username AS changed_by_name,
               u2.username AS approved_by_name
        FROM audit_log al
        LEFT JOIN users u1 ON al.changed_by = u1.id
        LEFT JOIN users u2 ON al.approved_by = u2.id
        {where_clause}
        ORDER BY al.timestamp DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]
