"""
GoldVault Ledger - Entry Management
Handles adding, editing, deleting ledger entries and balance recalculation.
"""

import logging
from typing import Dict, Any, List, Optional

from backend.database import get_db
from backend.calculations import to_995_basis, format_decimal
from backend.audit import log_action

logger = logging.getLogger(__name__)


def _get_next_entry_number(conn) -> int:
    """Read and increment the global entry number from settings."""
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'next_entry_number'"
    ).fetchone()
    num = int(row['value']) if row else 1
    conn.execute(
        "UPDATE settings SET value = ? WHERE key = 'next_entry_number'",
        (str(num + 1),)
    )
    return num


def recalculate_smith_balance(smith_id: int) -> float:
    """
    Recompute balance for a Smith from scratch by processing all their entries
    in chronological order (entry_date, entry_time, id).

    Updates:
        - entries.converted_weight for each entry
        - entries.balance_after for each entry
        - smiths.balance (final balance)

    Returns:
        Final balance after all entries.
    """
    conn = get_db()
    entries = conn.execute(
        """SELECT id, raw_weight, purity, direction
           FROM entries
           WHERE smith_id = ?
           ORDER BY entry_date ASC, entry_time ASC, id ASC""",
        (smith_id,)
    ).fetchall()

    balance = 0.0
    for entry in entries:
        converted = to_995_basis(
            float(entry['raw_weight']),
            float(entry['purity']),
            entry['direction']
        )
        if entry['direction'] == 'Moozhayil to Smith':
            balance += converted
        else:
            balance -= converted
        balance = round(balance, 3)

        conn.execute(
            "UPDATE entries SET converted_weight=?, balance_after=? WHERE id=?",
            (converted, balance, entry['id'])
        )

    # Update Smith's current balance
    conn.execute(
        "UPDATE smiths SET balance=? WHERE id=?",
        (balance, smith_id)
    )
    conn.commit()
    logger.debug("Recalculated balance for smith_id=%d: %.3f", smith_id, balance)
    return balance


def add_entry(
    entry_date: str,
    entry_time: str,
    smith_id: int,
    direction: str,
    raw_weight: float,
    purity: float,
    remarks: str,
    user_id: int
) -> Dict[str, Any]:
    """
    Add a new ledger entry.

    Returns:
        Dict with entry_id, entry_number, converted_weight, balance_after.

    Raises:
        ValueError: On invalid inputs.
    """
    # Validate
    if raw_weight <= 0:
        raise ValueError("Weight must be greater than 0.")
    if purity <= 0 or purity > 1000:
        raise ValueError("Purity must be between 0 and 1000.")
    if direction not in ('Smith to Moozhayil', 'Moozhayil to Smith'):
        raise ValueError("Invalid direction.")

    conn = get_db()

    # Verify smith exists
    smith = conn.execute("SELECT id, balance FROM smiths WHERE id = ?", (smith_id,)).fetchone()
    if not smith:
        raise ValueError(f"Smith ID {smith_id} not found.")

    # Compute converted weight
    converted = to_995_basis(raw_weight, purity, direction)

    # Compute new balance
    current_balance = float(smith['balance'])
    if direction == 'Moozhayil to Smith':
        new_balance = round(current_balance + converted, 3)
    else:
        new_balance = round(current_balance - converted, 3)

    # Get entry number
    entry_number = _get_next_entry_number(conn)

    cursor = conn.execute(
        """INSERT INTO entries
           (entry_number, entry_date, entry_time, smith_id, direction,
            raw_weight, purity, converted_weight, balance_after, user_id, remarks)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (entry_number, entry_date, entry_time, smith_id, direction,
         raw_weight, purity, converted, new_balance, user_id, remarks)
    )
    entry_id = cursor.lastrowid

    # Update Smith balance
    conn.execute("UPDATE smiths SET balance=? WHERE id=?", (new_balance, smith_id))
    conn.commit()

    log_action(
        action='add_entry',
        original_data=None,
        new_data={
            'entry_id': entry_id,
            'entry_number': entry_number,
            'smith_id': smith_id,
            'direction': direction,
            'raw_weight': raw_weight,
            'purity': purity,
            'converted_weight': converted,
            'balance_after': new_balance
        },
        changed_by=user_id
    )

    logger.info("Entry #%d added (id=%d) by user %d", entry_number, entry_id, user_id)
    return {
        'entry_id': entry_id,
        'entry_number': entry_number,
        'converted_weight': converted,
        'balance_after': new_balance
    }


def edit_entry(
    entry_id: int,
    new_data: Dict[str, Any],
    reason: str,
    admin_id: int
) -> None:
    """
    Admin directly edits an entry. Recalculates Smith balance from scratch.

    Args:
        entry_id: Entry to edit.
        new_data: Dict with any of: entry_date, entry_time, direction,
                  raw_weight, purity, remarks.
        reason: Reason for edit (stored in audit).
        admin_id: Admin user ID.

    Raises:
        ValueError: On invalid inputs.
    """
    conn = get_db()
    original = conn.execute(
        "SELECT * FROM entries WHERE id = ?", (entry_id,)
    ).fetchone()
    if not original:
        raise ValueError(f"Entry ID {entry_id} not found.")

    original_dict = dict(original)

    # Merge changes
    updated = dict(original_dict)
    for field in ('entry_date', 'entry_time', 'direction', 'raw_weight', 'purity', 'remarks'):
        if field in new_data and new_data[field] is not None:
            updated[field] = new_data[field]

    # Validate
    if float(updated['raw_weight']) <= 0:
        raise ValueError("Weight must be > 0.")
    if float(updated['purity']) <= 0 or float(updated['purity']) > 1000:
        raise ValueError("Purity must be between 0 and 1000.")
    if updated['direction'] not in ('Smith to Moozhayil', 'Moozhayil to Smith'):
        raise ValueError("Invalid direction.")

    # Recompute converted weight
    new_converted = to_995_basis(
        float(updated['raw_weight']),
        float(updated['purity']),
        updated['direction']
    )

    conn.execute(
        """UPDATE entries SET entry_date=?, entry_time=?, direction=?,
           raw_weight=?, purity=?, converted_weight=?, remarks=?
           WHERE id=?""",
        (
            updated['entry_date'], updated['entry_time'], updated['direction'],
            updated['raw_weight'], updated['purity'], new_converted,
            updated['remarks'], entry_id
        )
    )
    conn.commit()

    # Recalculate entire Smith balance
    recalculate_smith_balance(original_dict['smith_id'])

    # Fetch updated entry for audit
    updated_entry = dict(conn.execute(
        "SELECT * FROM entries WHERE id = ?", (entry_id,)
    ).fetchone())

    log_action(
        action='edit_entry',
        original_data=original_dict,
        new_data=updated_entry,
        changed_by=admin_id,
        remarks=reason
    )
    logger.info("Entry %d edited by admin %d", entry_id, admin_id)


def delete_entry(entry_id: int, reason: str, admin_id: int) -> None:
    """
    Admin deletes an entry. Recalculates Smith balance from scratch.

    Raises:
        ValueError: If entry not found.
    """
    conn = get_db()
    original = conn.execute(
        "SELECT * FROM entries WHERE id = ?", (entry_id,)
    ).fetchone()
    if not original:
        raise ValueError(f"Entry ID {entry_id} not found.")

    original_dict = dict(original)
    smith_id = original_dict['smith_id']

    # Delete any pending change requests for this entry
    conn.execute(
        "DELETE FROM change_requests WHERE entry_id = ? AND status = 'pending'",
        (entry_id,)
    )

    conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    conn.commit()

    # Recalculate Smith balance
    recalculate_smith_balance(smith_id)

    log_action(
        action='delete_entry',
        original_data=original_dict,
        new_data=None,
        changed_by=admin_id,
        remarks=reason
    )
    logger.info("Entry %d deleted by admin %d", entry_id, admin_id)


def get_entries(
    smith_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Retrieve ledger entries with joined Smith and User names.

    Returns list of dicts suitable for frontend display.
    """
    conn = get_db()
    conditions = []
    params = []

    if smith_id:
        conditions.append("e.smith_id = ?")
        params.append(smith_id)
    if date_from:
        conditions.append("e.entry_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("e.entry_date <= ?")
        params.append(date_to)
    if user_id:
        conditions.append("e.user_id = ?")
        params.append(user_id)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    query = f"""
        SELECT e.id, e.entry_number, e.entry_date, e.entry_time,
               e.direction, e.raw_weight, e.purity, e.converted_weight,
               e.balance_after, e.remarks, e.created_at,
               s.name AS smith_name, s.id AS smith_id,
               u.username AS entered_by
        FROM entries e
        JOIN smiths s ON e.smith_id = s.id
        JOIN users u ON e.user_id = u.id
        {where}
        ORDER BY e.entry_date ASC, e.entry_time ASC, e.id ASC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d['converted_weight_fmt'] = format_decimal(d['converted_weight'])
        d['balance_after_fmt'] = format_decimal(d['balance_after'])
        d['raw_weight_fmt'] = format_decimal(d['raw_weight'])
        result.append(d)
    return result


def get_entry_count(
    smith_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> int:
    """Return total count of entries matching filters."""
    conn = get_db()
    conditions = []
    params = []

    if smith_id:
        conditions.append("smith_id = ?")
        params.append(smith_id)
    if date_from:
        conditions.append("entry_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("entry_date <= ?")
        params.append(date_to)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    row = conn.execute(f"SELECT COUNT(*) FROM entries {where}", params).fetchone()
    return row[0]


def get_smiths() -> List[Dict[str, Any]]:
    """Return all Smiths with formatted balance."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, balance, created_at FROM smiths ORDER BY name ASC"
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['balance_fmt'] = format_decimal(d['balance'])
        result.append(d)
    return result


def add_smith(name: str) -> int:
    """
    Add a new Smith.

    Returns:
        New Smith ID.

    Raises:
        ValueError: If name is empty or duplicate.
    """
    name = name.strip()
    if not name:
        raise ValueError("Smith name cannot be empty.")

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM smiths WHERE name = ?", (name,)
    ).fetchone()
    if existing:
        raise ValueError(f"Smith '{name}' already exists.")

    cursor = conn.execute(
        "INSERT INTO smiths (name, balance) VALUES (?, 0.0)",
        (name,)
    )
    conn.commit()
    logger.info("Smith added: %s (id=%d)", name, cursor.lastrowid)
    return cursor.lastrowid


def clear_entries(
    clear_type: str,
    target: Any,
    admin_id: int,
    reason: str
) -> int:
    """
    Clear entries based on type.

    Args:
        clear_type: 'all' | 'smith' | 'before_date' | 'older_than_2weeks' | 'older_than_1month'
        target: Smith ID (for 'smith') or date string (for 'before_date'), else None.
        admin_id: Admin performing the action.
        reason: Reason for clearing.

    Returns:
        Number of entries deleted.
    """
    from datetime import date, timedelta

    conn = get_db()

    if clear_type == 'all':
        count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        conn.execute("DELETE FROM entries")
        conn.execute("DELETE FROM change_requests")
        conn.execute("UPDATE smiths SET balance = 0.0")
        conn.commit()

    elif clear_type == 'smith':
        smith_id = int(target)
        count = conn.execute(
            "SELECT COUNT(*) FROM entries WHERE smith_id = ?", (smith_id,)
        ).fetchone()[0]
        conn.execute(
            "DELETE FROM change_requests WHERE entry_id IN (SELECT id FROM entries WHERE smith_id = ?)",
            (smith_id,)
        )
        conn.execute("DELETE FROM entries WHERE smith_id = ?", (smith_id,))
        conn.execute("UPDATE smiths SET balance = 0.0 WHERE id = ?", (smith_id,))
        conn.commit()

    elif clear_type == 'before_date':
        cutoff = str(target)
        count = conn.execute(
            "SELECT COUNT(*) FROM entries WHERE entry_date < ?", (cutoff,)
        ).fetchone()[0]
        affected_smiths = [r[0] for r in conn.execute(
            "SELECT DISTINCT smith_id FROM entries WHERE entry_date < ?", (cutoff,)
        ).fetchall()]
        conn.execute(
            "DELETE FROM change_requests WHERE entry_id IN (SELECT id FROM entries WHERE entry_date < ?)",
            (cutoff,)
        )
        conn.execute("DELETE FROM entries WHERE entry_date < ?", (cutoff,))
        conn.commit()
        for sid in affected_smiths:
            recalculate_smith_balance(sid)

    elif clear_type in ('older_than_2weeks', 'older_than_1month'):
        delta = timedelta(weeks=2) if clear_type == 'older_than_2weeks' else timedelta(days=30)
        cutoff = (date.today() - delta).isoformat()
        count = conn.execute(
            "SELECT COUNT(*) FROM entries WHERE entry_date < ?", (cutoff,)
        ).fetchone()[0]
        affected_smiths = [r[0] for r in conn.execute(
            "SELECT DISTINCT smith_id FROM entries WHERE entry_date < ?", (cutoff,)
        ).fetchall()]
        conn.execute(
            "DELETE FROM change_requests WHERE entry_id IN (SELECT id FROM entries WHERE entry_date < ?)",
            (cutoff,)
        )
        conn.execute("DELETE FROM entries WHERE entry_date < ?", (cutoff,))
        conn.commit()
        for sid in affected_smiths:
            recalculate_smith_balance(sid)

    else:
        raise ValueError(f"Unknown clear_type: {clear_type}")

    log_action(
        action='clear_data',
        original_data={'clear_type': clear_type, 'target': str(target), 'count': count},
        new_data=None,
        changed_by=admin_id,
        remarks=reason
    )
    logger.info("Cleared %d entries (type=%s) by admin %d", count, clear_type, admin_id)
    return count
