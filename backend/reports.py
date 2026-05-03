"""
GoldVault Ledger - Report Generation
Generates printable HTML reports for all 8 report types.
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from backend.database import get_db
from backend.calculations import format_decimal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared HTML helpers
# ---------------------------------------------------------------------------

PRINT_STYLE = """
<style>
  body { font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; color: #222; }
  h1 { color: #B8860B; border-bottom: 2px solid #D4AF37; padding-bottom: 8px; }
  h2 { color: #8B6914; margin-top: 20px; }
  .meta { color: #666; font-size: 0.9em; margin-bottom: 16px; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 20px; font-size: 0.9em; }
  th { background: #D4AF37; color: white; padding: 8px 10px; text-align: left; }
  td { padding: 7px 10px; border-bottom: 1px solid #eee; }
  tr:nth-child(even) { background: #fafafa; }
  .total-row { background: #FFF8DC !important; font-weight: bold; border-top: 2px solid #D4AF37; }
  .print-btn { background: #D4AF37; color: white; border: none; padding: 10px 24px;
               font-size: 1em; border-radius: 4px; cursor: pointer; margin-bottom: 16px; }
  .print-btn:hover { background: #B8860B; }
  .badge-sm { background: #D4AF37; color: white; border-radius: 3px; padding: 2px 6px; font-size: 0.8em; }
  .badge-mts { background: #2e7d32; }
  .badge-stm { background: #c62828; }
  @media print { .print-btn { display: none; } }
</style>
"""


def _html_wrap(title: str, body: str, filters_desc: str = "") -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title} – GoldVault Ledger</title>
  {PRINT_STYLE}
</head>
<body>
  <button class="print-btn" onclick="window.print()">🖨 Print Report</button>
  <h1>GoldVault Ledger – {title}</h1>
  <div class="meta">Generated: {now}{(' | Filters: ' + filters_desc) if filters_desc else ''}</div>
  {body}
</body>
</html>"""


def _direction_badge(direction: str) -> str:
    cls = "badge-mts" if direction == "Moozhayil to Smith" else "badge-stm"
    return f'<span class="badge-sm {cls}">{direction}</span>'


def _no_data() -> str:
    return '<p style="color:#888;font-style:italic;">No entries found for the selected filters.</p>'


# ---------------------------------------------------------------------------
# Report 1: Daily Report
# ---------------------------------------------------------------------------
def daily_report(filters: Dict[str, Any]) -> str:
    conn = get_db()
    date_from = filters.get('date_from', '')
    date_to = filters.get('date_to', '')
    smith_id = filters.get('smith_id')

    conditions = []
    params = []
    if date_from:
        conditions.append("e.entry_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("e.entry_date <= ?")
        params.append(date_to)
    if smith_id:
        conditions.append("e.smith_id = ?")
        params.append(smith_id)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = conn.execute(f"""
        SELECT e.entry_date, e.direction,
               SUM(e.raw_weight) AS total_raw,
               SUM(e.converted_weight) AS total_converted,
               COUNT(*) AS entry_count
        FROM entries e
        {where}
        GROUP BY e.entry_date, e.direction
        ORDER BY e.entry_date ASC, e.direction ASC
    """, params).fetchall()

    if not rows:
        return _html_wrap("Daily Report", _no_data())

    # Group by date
    days: Dict[str, list] = {}
    for r in rows:
        days.setdefault(r['entry_date'], []).append(dict(r))

    body = ""
    grand_raw = 0.0
    grand_conv = 0.0

    for day, day_rows in sorted(days.items()):
        body += f"<h2>{day}</h2><table><thead><tr>"
        body += "<th>Direction</th><th>Entries</th><th>Total Raw Weight (g)</th><th>Total 995 Weight (g)</th>"
        body += "</tr></thead><tbody>"
        day_raw = 0.0
        day_conv = 0.0
        for dr in day_rows:
            body += f"<tr><td>{_direction_badge(dr['direction'])}</td>"
            body += f"<td>{dr['entry_count']}</td>"
            body += f"<td>{format_decimal(dr['total_raw'])}</td>"
            body += f"<td>{format_decimal(dr['total_converted'])}</td></tr>"
            day_raw += dr['total_raw']
            day_conv += dr['total_converted']
        body += f'<tr class="total-row"><td colspan="2">Day Total</td>'
        body += f'<td>{format_decimal(day_raw)}</td><td>{format_decimal(day_conv)}</td></tr>'
        body += "</tbody></table>"
        grand_raw += day_raw
        grand_conv += day_conv

    body += f'<table><tr class="total-row"><td><strong>Grand Total</strong></td>'
    body += f'<td></td><td>{format_decimal(grand_raw)}</td><td>{format_decimal(grand_conv)}</td></tr></table>'

    filters_desc = f"{date_from or 'all'} to {date_to or 'all'}"
    return _html_wrap("Daily Report", body, filters_desc)


# ---------------------------------------------------------------------------
# Report 2: Smith-wise Ledger
# ---------------------------------------------------------------------------
def smith_ledger_report(filters: Dict[str, Any]) -> str:
    conn = get_db()
    date_from = filters.get('date_from', '')
    date_to = filters.get('date_to', '')
    smith_id = filters.get('smith_id')

    conditions = ["1=1"]
    params = []
    if date_from:
        conditions.append("e.entry_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("e.entry_date <= ?")
        params.append(date_to)
    if smith_id:
        conditions.append("e.smith_id = ?")
        params.append(smith_id)

    where = "WHERE " + " AND ".join(conditions)

    rows = conn.execute(f"""
        SELECT e.entry_number, e.entry_date, e.entry_time, e.direction,
               e.raw_weight, e.purity, e.converted_weight, e.balance_after,
               e.remarks, u.username AS entered_by, s.name AS smith_name, s.id AS smith_id
        FROM entries e
        JOIN smiths s ON e.smith_id = s.id
        JOIN users u ON e.user_id = u.id
        {where}
        ORDER BY s.name ASC, e.entry_date ASC, e.entry_time ASC, e.id ASC
    """, params).fetchall()

    if not rows:
        return _html_wrap("Smith-wise Ledger", _no_data())

    # Group by smith
    smiths: Dict[str, list] = {}
    for r in rows:
        smiths.setdefault(r['smith_name'], []).append(dict(r))

    body = ""
    for smith_name, s_rows in smiths.items():
        body += f"<h2>Smith: {smith_name}</h2>"
        body += """<table><thead><tr>
            <th>#</th><th>Date</th><th>Time</th><th>Direction</th>
            <th>Raw Weight (g)</th><th>Purity</th><th>995 Weight (g)</th>
            <th>Balance (g)</th><th>Entered By</th><th>Remarks</th>
        </tr></thead><tbody>"""
        for r in s_rows:
            body += f"""<tr>
                <td>{r['entry_number']}</td>
                <td>{r['entry_date']}</td>
                <td>{r['entry_time']}</td>
                <td>{_direction_badge(r['direction'])}</td>
                <td>{format_decimal(r['raw_weight'])}</td>
                <td>{format_decimal(r['purity'])}</td>
                <td>{format_decimal(r['converted_weight'])}</td>
                <td>{format_decimal(r['balance_after'])}</td>
                <td>{r['entered_by']}</td>
                <td>{r['remarks'] or ''}</td>
            </tr>"""
        final_balance = s_rows[-1]['balance_after']
        body += f'<tr class="total-row"><td colspan="6">Final Balance</td>'
        body += f'<td colspan="4">{format_decimal(final_balance)} g (995 basis)</td></tr>'
        body += "</tbody></table>"

    filters_desc = f"{date_from or 'all'} to {date_to or 'all'}"
    return _html_wrap("Smith-wise Ledger", body, filters_desc)


# ---------------------------------------------------------------------------
# Report 3: Balance Report
# ---------------------------------------------------------------------------
def balance_report(filters: Dict[str, Any]) -> str:
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, balance FROM smiths ORDER BY name ASC"
    ).fetchall()

    if not rows:
        return _html_wrap("Balance Report", _no_data())

    body = """<table><thead><tr>
        <th>#</th><th>Smith Name</th><th>Current Balance (995 basis, g)</th>
    </tr></thead><tbody>"""

    total = 0.0
    for i, r in enumerate(rows, 1):
        body += f"<tr><td>{i}</td><td>{r['name']}</td><td>{format_decimal(r['balance'])}</td></tr>"
        total += r['balance']

    body += f'<tr class="total-row"><td colspan="2">Total</td><td>{format_decimal(total)}</td></tr>'
    body += "</tbody></table>"

    return _html_wrap("Balance Report", body)


# ---------------------------------------------------------------------------
# Report 4: Gold Given Report (Moozhayil to Smith)
# ---------------------------------------------------------------------------
def gold_given_report(filters: Dict[str, Any]) -> str:
    conn = get_db()
    date_from = filters.get('date_from', '')
    date_to = filters.get('date_to', '')
    smith_id = filters.get('smith_id')

    conditions = ["e.direction = 'Moozhayil to Smith'"]
    params = []
    if date_from:
        conditions.append("e.entry_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("e.entry_date <= ?")
        params.append(date_to)
    if smith_id:
        conditions.append("e.smith_id = ?")
        params.append(smith_id)

    where = "WHERE " + " AND ".join(conditions)

    rows = conn.execute(f"""
        SELECT e.entry_number, e.entry_date, e.entry_time,
               e.raw_weight, e.purity, e.converted_weight, e.remarks,
               s.name AS smith_name, u.username AS entered_by
        FROM entries e
        JOIN smiths s ON e.smith_id = s.id
        JOIN users u ON e.user_id = u.id
        {where}
        ORDER BY e.entry_date ASC, e.entry_time ASC, e.id ASC
    """, params).fetchall()

    if not rows:
        return _html_wrap("Gold Given Report", _no_data())

    body = """<table><thead><tr>
        <th>#</th><th>Date</th><th>Time</th><th>Smith</th>
        <th>Raw Weight (g)</th><th>Purity</th><th>995 Weight (g)</th>
        <th>Entered By</th><th>Remarks</th>
    </tr></thead><tbody>"""

    total_raw = 0.0
    total_conv = 0.0
    for r in rows:
        body += f"""<tr>
            <td>{r['entry_number']}</td><td>{r['entry_date']}</td><td>{r['entry_time']}</td>
            <td>{r['smith_name']}</td><td>{format_decimal(r['raw_weight'])}</td>
            <td>{format_decimal(r['purity'])}</td><td>{format_decimal(r['converted_weight'])}</td>
            <td>{r['entered_by']}</td><td>{r['remarks'] or ''}</td>
        </tr>"""
        total_raw += r['raw_weight']
        total_conv += r['converted_weight']

    body += f'<tr class="total-row"><td colspan="4">Total ({len(rows)} entries)</td>'
    body += f'<td>{format_decimal(total_raw)}</td><td></td><td>{format_decimal(total_conv)}</td>'
    body += '<td colspan="2"></td></tr></tbody></table>'

    filters_desc = f"{date_from or 'all'} to {date_to or 'all'}"
    return _html_wrap("Gold Given Report (Moozhayil → Smith)", body, filters_desc)


# ---------------------------------------------------------------------------
# Report 5: Gold Received Report (Smith to Moozhayil)
# ---------------------------------------------------------------------------
def gold_received_report(filters: Dict[str, Any]) -> str:
    conn = get_db()
    date_from = filters.get('date_from', '')
    date_to = filters.get('date_to', '')
    smith_id = filters.get('smith_id')

    conditions = ["e.direction = 'Smith to Moozhayil'"]
    params = []
    if date_from:
        conditions.append("e.entry_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("e.entry_date <= ?")
        params.append(date_to)
    if smith_id:
        conditions.append("e.smith_id = ?")
        params.append(smith_id)

    where = "WHERE " + " AND ".join(conditions)

    rows = conn.execute(f"""
        SELECT e.entry_number, e.entry_date, e.entry_time,
               e.raw_weight, e.purity, e.converted_weight, e.remarks,
               s.name AS smith_name, u.username AS entered_by
        FROM entries e
        JOIN smiths s ON e.smith_id = s.id
        JOIN users u ON e.user_id = u.id
        {where}
        ORDER BY e.entry_date ASC, e.entry_time ASC, e.id ASC
    """, params).fetchall()

    if not rows:
        return _html_wrap("Gold Received Report", _no_data())

    body = """<table><thead><tr>
        <th>#</th><th>Date</th><th>Time</th><th>Smith</th>
        <th>Raw Weight (g)</th><th>Purity</th><th>995 Weight (g)</th>
        <th>Entered By</th><th>Remarks</th>
    </tr></thead><tbody>"""

    total_raw = 0.0
    total_conv = 0.0
    for r in rows:
        body += f"""<tr>
            <td>{r['entry_number']}</td><td>{r['entry_date']}</td><td>{r['entry_time']}</td>
            <td>{r['smith_name']}</td><td>{format_decimal(r['raw_weight'])}</td>
            <td>{format_decimal(r['purity'])}</td><td>{format_decimal(r['converted_weight'])}</td>
            <td>{r['entered_by']}</td><td>{r['remarks'] or ''}</td>
        </tr>"""
        total_raw += r['raw_weight']
        total_conv += r['converted_weight']

    body += f'<tr class="total-row"><td colspan="4">Total ({len(rows)} entries)</td>'
    body += f'<td>{format_decimal(total_raw)}</td><td></td><td>{format_decimal(total_conv)}</td>'
    body += '<td colspan="2"></td></tr></tbody></table>'

    filters_desc = f"{date_from or 'all'} to {date_to or 'all'}"
    return _html_wrap("Gold Received Report (Smith → Moozhayil)", body, filters_desc)


# ---------------------------------------------------------------------------
# Report 6: User-wise Entry Report
# ---------------------------------------------------------------------------
def user_entry_report(filters: Dict[str, Any]) -> str:
    conn = get_db()
    date_from = filters.get('date_from', '')
    date_to = filters.get('date_to', '')
    user_filter = filters.get('user_id')

    conditions = []
    params = []
    if date_from:
        conditions.append("e.entry_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("e.entry_date <= ?")
        params.append(date_to)
    if user_filter:
        conditions.append("e.user_id = ?")
        params.append(user_filter)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = conn.execute(f"""
        SELECT e.entry_number, e.entry_date, e.entry_time, e.direction,
               e.raw_weight, e.purity, e.converted_weight, e.remarks,
               s.name AS smith_name, u.username AS entered_by, u.id AS user_id
        FROM entries e
        JOIN smiths s ON e.smith_id = s.id
        JOIN users u ON e.user_id = u.id
        {where}
        ORDER BY u.username ASC, e.entry_date ASC, e.entry_time ASC
    """, params).fetchall()

    if not rows:
        return _html_wrap("User-wise Entry Report", _no_data())

    # Group by user
    users: Dict[str, list] = {}
    for r in rows:
        users.setdefault(r['entered_by'], []).append(dict(r))

    body = ""
    for username, u_rows in users.items():
        body += f"<h2>User: {username}</h2>"
        body += """<table><thead><tr>
            <th>#</th><th>Date</th><th>Time</th><th>Smith</th><th>Direction</th>
            <th>Raw Weight (g)</th><th>Purity</th><th>995 Weight (g)</th><th>Remarks</th>
        </tr></thead><tbody>"""
        total_conv = 0.0
        for r in u_rows:
            body += f"""<tr>
                <td>{r['entry_number']}</td><td>{r['entry_date']}</td><td>{r['entry_time']}</td>
                <td>{r['smith_name']}</td><td>{_direction_badge(r['direction'])}</td>
                <td>{format_decimal(r['raw_weight'])}</td><td>{format_decimal(r['purity'])}</td>
                <td>{format_decimal(r['converted_weight'])}</td><td>{r['remarks'] or ''}</td>
            </tr>"""
            total_conv += r['converted_weight']
        body += f'<tr class="total-row"><td colspan="7">Total ({len(u_rows)} entries)</td>'
        body += f'<td>{format_decimal(total_conv)}</td><td></td></tr>'
        body += "</tbody></table>"

    filters_desc = f"{date_from or 'all'} to {date_to or 'all'}"
    return _html_wrap("User-wise Entry Report", body, filters_desc)


# ---------------------------------------------------------------------------
# Report 7: Edit/Delete Audit Report
# ---------------------------------------------------------------------------
def audit_report(filters: Dict[str, Any]) -> str:
    conn = get_db()
    date_from = filters.get('date_from', '')
    date_to = filters.get('date_to', '')
    action_filter = filters.get('action', '')
    user_filter = filters.get('user_id')

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

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = conn.execute(f"""
        SELECT al.id, al.action, al.timestamp, al.remarks,
               al.original_data, al.new_data,
               u1.username AS changed_by_name,
               u2.username AS approved_by_name
        FROM audit_log al
        LEFT JOIN users u1 ON al.changed_by = u1.id
        LEFT JOIN users u2 ON al.approved_by = u2.id
        {where}
        ORDER BY al.timestamp ASC
    """, params).fetchall()

    if not rows:
        return _html_wrap("Audit Report", _no_data())

    body = """<table><thead><tr>
        <th>ID</th><th>Action</th><th>Timestamp</th><th>Changed By</th>
        <th>Approved By</th><th>Remarks</th><th>Original Data</th><th>New Data</th>
    </tr></thead><tbody>"""

    for r in rows:
        orig = r['original_data'] or ''
        new = r['new_data'] or ''
        # Truncate long JSON for display
        if len(orig) > 200:
            orig = orig[:200] + '...'
        if len(new) > 200:
            new = new[:200] + '...'
        body += f"""<tr>
            <td>{r['id']}</td>
            <td><strong>{r['action']}</strong></td>
            <td>{r['timestamp']}</td>
            <td>{r['changed_by_name'] or '?'}</td>
            <td>{r['approved_by_name'] or '-'}</td>
            <td>{r['remarks'] or ''}</td>
            <td style="font-size:0.75em;word-break:break-all">{orig}</td>
            <td style="font-size:0.75em;word-break:break-all">{new}</td>
        </tr>"""

    body += f'<tr class="total-row"><td colspan="8">Total: {len(rows)} audit records</td></tr>'
    body += "</tbody></table>"

    filters_desc = f"{date_from or 'all'} to {date_to or 'all'}"
    return _html_wrap("Edit/Delete Audit Report", body, filters_desc)


# ---------------------------------------------------------------------------
# Report 8: Change Request Report
# ---------------------------------------------------------------------------
def change_request_report(filters: Dict[str, Any]) -> str:
    conn = get_db()
    date_from = filters.get('date_from', '')
    date_to = filters.get('date_to', '')
    status_filter = filters.get('status', '')

    conditions = []
    params = []
    if status_filter:
        conditions.append("cr.status = ?")
        params.append(status_filter)
    if date_from:
        conditions.append("cr.requested_at >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("cr.requested_at <= ?")
        params.append(date_to + " 23:59:59")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = conn.execute(f"""
        SELECT cr.id, cr.entry_id, cr.reason, cr.requested_at, cr.status,
               cr.approved_at, cr.admin_remarks, cr.requested_changes,
               u1.username AS requested_by_name,
               u2.username AS approved_by_name,
               e.entry_number, s.name AS smith_name
        FROM change_requests cr
        JOIN entries e ON cr.entry_id = e.id
        JOIN smiths s ON e.smith_id = s.id
        JOIN users u1 ON cr.requested_by = u1.id
        LEFT JOIN users u2 ON cr.approved_by = u2.id
        {where}
        ORDER BY cr.requested_at ASC
    """, params).fetchall()

    if not rows:
        return _html_wrap("Change Request Report", _no_data())

    body = """<table><thead><tr>
        <th>ID</th><th>Entry #</th><th>Smith</th><th>Requested By</th>
        <th>Requested At</th><th>Status</th><th>Approved By</th>
        <th>Approved At</th><th>Reason</th><th>Admin Remarks</th>
    </tr></thead><tbody>"""

    status_colors = {'pending': '#f57c00', 'approved': '#2e7d32', 'rejected': '#c62828'}
    for r in rows:
        color = status_colors.get(r['status'], '#333')
        body += f"""<tr>
            <td>{r['id']}</td>
            <td>{r['entry_number']}</td>
            <td>{r['smith_name']}</td>
            <td>{r['requested_by_name']}</td>
            <td>{r['requested_at']}</td>
            <td><strong style="color:{color}">{r['status'].upper()}</strong></td>
            <td>{r['approved_by_name'] or '-'}</td>
            <td>{r['approved_at'] or '-'}</td>
            <td>{r['reason']}</td>
            <td>{r['admin_remarks'] or '-'}</td>
        </tr>"""

    body += f'<tr class="total-row"><td colspan="10">Total: {len(rows)} requests</td></tr>'
    body += "</tbody></table>"

    filters_desc = f"{date_from or 'all'} to {date_to or 'all'}"
    return _html_wrap("Change Request Report", body, filters_desc)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
REPORT_FUNCTIONS = {
    'daily': daily_report,
    'smith_ledger': smith_ledger_report,
    'balance': balance_report,
    'gold_given': gold_given_report,
    'gold_received': gold_received_report,
    'user_entry': user_entry_report,
    'audit': audit_report,
    'change_request': change_request_report,
}


def generate_report(report_type: str, filters: Dict[str, Any]) -> str:
    """
    Generate a report and return HTML string.

    Args:
        report_type: One of the keys in REPORT_FUNCTIONS.
        filters: Dict of filter parameters.

    Returns:
        HTML string.

    Raises:
        ValueError: If report_type is unknown.
    """
    fn = REPORT_FUNCTIONS.get(report_type)
    if not fn:
        raise ValueError(f"Unknown report type: {report_type}")
    return fn(filters)
