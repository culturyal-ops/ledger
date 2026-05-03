"""
GoldVault Ledger - Main Application Entry Point
Python + Eel desktop application for offline gold ledger management.
"""

import os
import sys
import time
import logging
import threading
import traceback
from datetime import datetime
from typing import Optional, Any, Dict

import eel

# ---------------------------------------------------------------------------
# Determine application base directory (works for both .py and .exe)
# ---------------------------------------------------------------------------
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_FOLDER = os.path.join(APP_DIR, 'GoldVaultData')
BACKUP_FOLDER = os.path.join(DATA_FOLDER, 'backups')
LOG_FILE = os.path.join(DATA_FOLDER, 'goldvault.log')

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
os.makedirs(DATA_FOLDER, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('goldvault.main')

# ---------------------------------------------------------------------------
# Import backend modules (after path setup)
# ---------------------------------------------------------------------------
from backend.database import EncryptedVault, vault as _vault_module
import backend.database as db_module
from backend.auth import (
    authenticate_user, create_user, get_users, get_user_by_id,
    edit_user, delete_user, toggle_user_active, change_password, verify_password
)
from backend.entries import (
    add_entry as _add_entry, edit_entry as _edit_entry,
    delete_entry as _delete_entry, get_entries, get_entry_count,
    get_smiths as _get_smiths, add_smith as _add_smith,
    recalculate_smith_balance, clear_entries
)
from backend.change_requests import (
    create_request, get_requests,
    approve_request as _approve_request,
    reject_request as _reject_request
)
from backend.audit import log_action, get_audit_log
from backend.reports import generate_report as _generate_report

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
vault: Optional[EncryptedVault] = None
current_user: Optional[Dict[str, Any]] = None
session_last_activity: float = 0.0
SESSION_TIMEOUT = 600  # 10 minutes
_failed_unlock_attempts = 0
MAX_UNLOCK_ATTEMPTS = 3
_usb_poll_running = False
_session_check_running = False


def _set_vault(v: EncryptedVault):
    global vault
    vault = v
    db_module.vault = v


def _require_auth():
    """Raise if no user is logged in or session timed out."""
    global current_user, session_last_activity
    if current_user is None:
        raise PermissionError("Not authenticated. Please log in.")
    if time.time() - session_last_activity > SESSION_TIMEOUT:
        _do_logout()
        raise PermissionError("Session timed out. Please log in again.")


def _require_admin():
    """Raise if current user is not admin."""
    _require_auth()
    if current_user['role'] != 'admin':
        raise PermissionError("Admin access required.")


def _touch_session():
    """Reset session activity timer."""
    global session_last_activity
    session_last_activity = time.time()


def _do_logout():
    """Clear session without closing vault."""
    global current_user, session_last_activity
    current_user = None
    session_last_activity = 0.0


def _safe_call(fn, *args, **kwargs):
    """Wrap a backend call with error handling, returning {'ok': bool, ...}."""
    try:
        result = fn(*args, **kwargs)
        return {'ok': True, 'data': result}
    except PermissionError as e:
        logger.warning("Permission error: %s", e)
        return {'ok': False, 'error': str(e), 'type': 'permission'}
    except ValueError as e:
        logger.warning("Validation error: %s", e)
        return {'ok': False, 'error': str(e), 'type': 'validation'}
    except Exception as e:
        logger.error("Unexpected error: %s\n%s", e, traceback.format_exc())
        return {'ok': False, 'error': f"Unexpected error: {str(e)}", 'type': 'error'}


# ---------------------------------------------------------------------------
# USB Polling Thread
# ---------------------------------------------------------------------------
def _usb_poll_thread():
    """Poll every 2 seconds for USB drive availability."""
    global _usb_poll_running
    _usb_poll_running = True
    logger.info("USB polling thread started. Watching: %s", DATA_FOLDER)
    while _usb_poll_running:
        try:
            if vault and vault.is_open():
                if not os.path.exists(DATA_FOLDER):
                    logger.warning("Data folder not found – locking vault.")
                    try:
                        eel.lock_vault_from_python()()
                    except Exception:
                        pass
        except Exception as e:
            logger.debug("USB poll error (non-fatal): %s", e)
        time.sleep(2)


# ---------------------------------------------------------------------------
# Session Timeout Thread
# ---------------------------------------------------------------------------
def _session_timeout_thread():
    """Check session timeout every 30 seconds."""
    global _session_check_running
    _session_check_running = True
    while _session_check_running:
        try:
            if current_user and time.time() - session_last_activity > SESSION_TIMEOUT:
                logger.info("Session timed out for user: %s", current_user.get('username'))
                _do_logout()
                try:
                    eel.session_timeout_from_python()()
                except Exception:
                    pass
        except Exception as e:
            logger.debug("Session check error: %s", e)
        time.sleep(30)


# ---------------------------------------------------------------------------
# Eel exposed functions
# ---------------------------------------------------------------------------

@eel.expose
def keep_alive():
    """Called by frontend on any user interaction to reset session timer."""
    _touch_session()


@eel.expose
def check_vault_exists() -> bool:
    """Return True if the encrypted vault file exists."""
    v = EncryptedVault(DATA_FOLDER)
    return v.exists()


@eel.expose
def create_vault(master_pw: str, admin_username: str, admin_pw: str) -> dict:
    """First-run: create encrypted vault with admin user."""
    global vault, _failed_unlock_attempts

    def _create():
        if not master_pw or len(master_pw) < 4:
            raise ValueError("Master password must be at least 4 characters.")
        if not admin_username or len(admin_username.strip()) < 3:
            raise ValueError("Admin username must be at least 3 characters.")
        if not admin_pw or len(admin_pw) < 4:
            raise ValueError("Admin password must be at least 4 characters.")

        v = EncryptedVault(DATA_FOLDER)
        v.setup_first_run(master_pw, admin_username.strip(), admin_pw)
        _set_vault(v)
        _failed_unlock_attempts = 0
        logger.info("Vault created successfully.")

    return _safe_call(_create)


@eel.expose
def unlock_vault(master_pw: str) -> dict:
    """Decrypt and load the vault. Returns ok/error."""
    global vault, _failed_unlock_attempts

    def _unlock():
        global _failed_unlock_attempts
        if _failed_unlock_attempts >= MAX_UNLOCK_ATTEMPTS:
            raise PermissionError("Too many failed attempts. Application locked.")

        v = EncryptedVault(DATA_FOLDER)
        try:
            v.load(master_pw)
        except ValueError:
            _failed_unlock_attempts += 1
            remaining = MAX_UNLOCK_ATTEMPTS - _failed_unlock_attempts
            if remaining <= 0:
                raise PermissionError("Too many failed attempts. Application locked.")
            raise ValueError(f"Incorrect master password. {remaining} attempt(s) remaining.")

        _set_vault(v)
        _failed_unlock_attempts = 0
        logger.info("Vault unlocked.")

    return _safe_call(_unlock)


@eel.expose
def login_user(username: str, password: str) -> dict:
    """Authenticate user against the in-memory database."""
    global current_user, session_last_activity

    def _login():
        if vault is None or not vault.is_open():
            raise RuntimeError("Vault is not open.")
        user = authenticate_user(username, password)
        if user is None:
            raise ValueError("Invalid username or password.")
        current_user = user
        session_last_activity = time.time()
        logger.info("User logged in: %s", username)
        return {
            'id': user['id'],
            'username': user['username'],
            'role': user['role']
        }

    return _safe_call(_login)


@eel.expose
def logout() -> dict:
    """Log out current user (keep vault open)."""
    _do_logout()
    return {'ok': True}


@eel.expose
def lock_vault() -> dict:
    """Lock vault completely (close in-memory DB)."""
    global vault
    _do_logout()
    if vault:
        vault.close()
        vault = None
        db_module.vault = None
    return {'ok': True}


@eel.expose
def get_current_user() -> dict:
    """Return current logged-in user info."""
    if current_user:
        _touch_session()
        return {'ok': True, 'data': current_user}
    return {'ok': False, 'error': 'Not logged in'}


# ---------------------------------------------------------------------------
# Smith management
# ---------------------------------------------------------------------------

@eel.expose
def get_smiths() -> dict:
    _touch_session()
    return _safe_call(lambda: _get_smiths())


@eel.expose
def add_smith(name: str) -> dict:
    _touch_session()
    def _do():
        _require_auth()
        smith_id = _add_smith(name)
        vault.save()
        return {'id': smith_id, 'name': name.strip()}
    return _safe_call(_do)


@eel.expose
def delete_smith(smith_id: int) -> dict:
    _touch_session()
    def _do():
        _require_admin()
        conn = db_module.get_db()
        entry_count = conn.execute(
            "SELECT COUNT(*) FROM entries WHERE smith_id = ?", (smith_id,)
        ).fetchone()[0]
        if entry_count > 0:
            raise ValueError("Cannot delete Smith with existing entries.")
        conn.execute("DELETE FROM smiths WHERE id = ?", (smith_id,))
        conn.commit()
        vault.save()
        log_action('delete_smith', {'smith_id': smith_id}, None, current_user['id'])
    return _safe_call(_do)


@eel.expose
def edit_smith(smith_id: int, new_name: str) -> dict:
    _touch_session()
    def _do():
        _require_admin()
        new_name_stripped = new_name.strip()
        if not new_name_stripped:
            raise ValueError("Smith name cannot be empty.")
        conn = db_module.get_db()
        conflict = conn.execute(
            "SELECT id FROM smiths WHERE name = ? AND id != ?", (new_name_stripped, smith_id)
        ).fetchone()
        if conflict:
            raise ValueError(f"Smith '{new_name_stripped}' already exists.")
        conn.execute("UPDATE smiths SET name = ? WHERE id = ?", (new_name_stripped, smith_id))
        conn.commit()
        vault.save()
    return _safe_call(_do)


# ---------------------------------------------------------------------------
# Entry management
# ---------------------------------------------------------------------------

@eel.expose
def add_entry(entry_data: dict) -> dict:
    _touch_session()
    def _do():
        _require_auth()
        result = _add_entry(
            entry_date=entry_data['entry_date'],
            entry_time=entry_data['entry_time'],
            smith_id=int(entry_data['smith_id']),
            direction=entry_data['direction'],
            raw_weight=float(entry_data['raw_weight']),
            purity=float(entry_data['purity']),
            remarks=entry_data.get('remarks', ''),
            user_id=current_user['id']
        )
        vault.save()
        return result
    return _safe_call(_do)


@eel.expose
def get_ledger_entries(filters: dict, offset: int = 0, limit: int = 50) -> dict:
    _touch_session()
    def _do():
        _require_auth()
        entries = get_entries(
            smith_id=filters.get('smith_id'),
            date_from=filters.get('date_from'),
            date_to=filters.get('date_to'),
            user_id=filters.get('user_id'),
            limit=limit,
            offset=offset
        )
        total = get_entry_count(
            smith_id=filters.get('smith_id'),
            date_from=filters.get('date_from'),
            date_to=filters.get('date_to')
        )
        return {'entries': entries, 'total': total}
    return _safe_call(_do)


@eel.expose
def edit_entry(entry_id: int, new_data: dict, reason: str) -> dict:
    _touch_session()
    def _do():
        _require_admin()
        _edit_entry(entry_id, new_data, reason, current_user['id'])
        vault.save()
    return _safe_call(_do)


@eel.expose
def delete_entry(entry_id: int, reason: str) -> dict:
    _touch_session()
    def _do():
        _require_admin()
        if not reason or not reason.strip():
            raise ValueError("A reason is required to delete an entry.")
        _delete_entry(entry_id, reason, current_user['id'])
        vault.save()
    return _safe_call(_do)


# ---------------------------------------------------------------------------
# Change requests
# ---------------------------------------------------------------------------

@eel.expose
def create_change_request(entry_id: int, changes: dict, reason: str) -> dict:
    _touch_session()
    def _do():
        _require_auth()
        req_id = create_request(entry_id, changes, reason, current_user['id'])
        vault.save()
        return {'request_id': req_id}
    return _safe_call(_do)


@eel.expose
def get_change_requests(status: str = None) -> dict:
    _touch_session()
    def _do():
        _require_auth()
        user_filter = None if current_user['role'] == 'admin' else current_user['id']
        return get_requests(status=status, user_id=user_filter)
    return _safe_call(_do)


@eel.expose
def get_pending_requests_count() -> dict:
    _touch_session()
    def _do():
        _require_auth()
        reqs = get_requests(status='pending')
        return len(reqs)
    return _safe_call(_do)


@eel.expose
def approve_request(req_id: int, admin_remarks: str = "") -> dict:
    _touch_session()
    def _do():
        _require_admin()
        _approve_request(req_id, current_user['id'], admin_remarks)
        vault.save()
    return _safe_call(_do)


@eel.expose
def reject_request(req_id: int, admin_remarks: str) -> dict:
    _touch_session()
    def _do():
        _require_admin()
        _reject_request(req_id, current_user['id'], admin_remarks)
        vault.save()
    return _safe_call(_do)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@eel.expose
def generate_report(report_type: str, filters: dict) -> dict:
    _touch_session()
    def _do():
        _require_auth()
        html = _generate_report(report_type, filters)
        return html
    return _safe_call(_do)


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

@eel.expose
def get_users_list() -> dict:
    _touch_session()
    def _do():
        _require_admin()
        return get_users()
    return _safe_call(_do)


@eel.expose
def add_user(username: str, password: str, role: str) -> dict:
    _touch_session()
    def _do():
        _require_admin()
        uid = create_user(username, password, role, current_user['id'])
        log_action('create_user', None, {'username': username, 'role': role},
                   current_user['id'])
        vault.save()
        return {'user_id': uid}
    return _safe_call(_do)


@eel.expose
def edit_user_data(user_id: int, username: str, password: str, role: str, active: int) -> dict:
    _touch_session()
    def _do():
        _require_admin()
        original = get_user_by_id(user_id)
        edit_user(
            user_id,
            username=username or None,
            password=password or None,
            role=role or None,
            active=active if active is not None else None
        )
        log_action('edit_user', original, get_user_by_id(user_id), current_user['id'])
        vault.save()
    return _safe_call(_do)


@eel.expose
def delete_user_account(user_id: int) -> dict:
    _touch_session()
    def _do():
        _require_admin()
        original = get_user_by_id(user_id)
        delete_user(user_id)
        log_action('delete_user', original, None, current_user['id'])
        vault.save()
    return _safe_call(_do)


@eel.expose
def toggle_user(user_id: int, active: bool) -> dict:
    _touch_session()
    def _do():
        _require_admin()
        toggle_user_active(user_id, active)
        log_action('toggle_user_active', {'user_id': user_id, 'active': not active},
                   {'user_id': user_id, 'active': active}, current_user['id'])
        vault.save()
    return _safe_call(_do)


@eel.expose
def change_own_password(old_password: str, new_password: str) -> dict:
    _touch_session()
    def _do():
        _require_auth()
        user = get_user_by_id(current_user['id'])
        conn = db_module.get_db()
        row = conn.execute(
            "SELECT password_hash, salt FROM users WHERE id = ?", (current_user['id'],)
        ).fetchone()
        if not verify_password(old_password, row['salt'], row['password_hash']):
            raise ValueError("Current password is incorrect.")
        if len(new_password) < 4:
            raise ValueError("New password must be at least 4 characters.")
        change_password(current_user['id'], new_password)
        vault.save()
    return _safe_call(_do)


# ---------------------------------------------------------------------------
# Data clearing
# ---------------------------------------------------------------------------

@eel.expose
def clear_data(clear_type: str, target: Any, admin_password: str, reason: str) -> dict:
    _touch_session()
    def _do():
        _require_admin()
        if not reason or not reason.strip():
            raise ValueError("A reason is required for data clearing.")

        # Re-authenticate admin
        conn = db_module.get_db()
        row = conn.execute(
            "SELECT password_hash, salt FROM users WHERE id = ?", (current_user['id'],)
        ).fetchone()
        if not verify_password(admin_password, row['salt'], row['password_hash']):
            raise ValueError("Incorrect admin password. Data clearing cancelled.")

        # Auto-backup before clearing
        os.makedirs(BACKUP_FOLDER, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(BACKUP_FOLDER, f'pre_clear_{ts}.db.enc')
        vault.backup_to(backup_path)

        count = clear_entries(clear_type, target, current_user['id'], reason)
        vault.save()
        return {'deleted': count, 'backup': backup_path}

    return _safe_call(_do)


@eel.expose
def get_clear_preview(clear_type: str, target: Any) -> dict:
    """Return count of entries that would be deleted."""
    _touch_session()
    def _do():
        _require_admin()
        from datetime import date, timedelta
        conn = db_module.get_db()

        if clear_type == 'all':
            count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        elif clear_type == 'smith':
            count = conn.execute(
                "SELECT COUNT(*) FROM entries WHERE smith_id = ?", (int(target),)
            ).fetchone()[0]
        elif clear_type == 'before_date':
            count = conn.execute(
                "SELECT COUNT(*) FROM entries WHERE entry_date < ?", (str(target),)
            ).fetchone()[0]
        elif clear_type == 'older_than_2weeks':
            cutoff = (date.today() - timedelta(weeks=2)).isoformat()
            count = conn.execute(
                "SELECT COUNT(*) FROM entries WHERE entry_date < ?", (cutoff,)
            ).fetchone()[0]
        elif clear_type == 'older_than_1month':
            cutoff = (date.today() - timedelta(days=30)).isoformat()
            count = conn.execute(
                "SELECT COUNT(*) FROM entries WHERE entry_date < ?", (cutoff,)
            ).fetchone()[0]
        else:
            raise ValueError(f"Unknown clear_type: {clear_type}")
        return {'count': count}

    return _safe_call(_do)


# ---------------------------------------------------------------------------
# Backup / Restore
# ---------------------------------------------------------------------------

@eel.expose
def backup_database(destination_path: str = None) -> dict:
    _touch_session()
    def _do():
        _require_admin()
        os.makedirs(BACKUP_FOLDER, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        if not destination_path:
            dest = os.path.join(BACKUP_FOLDER, f'backup_{ts}.db.enc')
        else:
            dest = destination_path
        vault.backup_to(dest)
        log_action('backup', None, {'destination': dest}, current_user['id'])
        vault.save()
        return {'path': dest}
    return _safe_call(_do)


@eel.expose
def restore_database(backup_path: str, master_password: str) -> dict:
    _touch_session()
    def _do():
        _require_admin()
        vault.restore_from(backup_path, master_password)
        log_action('restore', {'backup_path': backup_path}, None, current_user['id'])
        _do_logout()  # Force re-login after restore
        return {'message': 'Restore successful. Please log in again.'}
    return _safe_call(_do)


@eel.expose
def save_vault_now() -> dict:
    """Manual save trigger (e.g., after USB re-insertion)."""
    _touch_session()
    def _do():
        _require_auth()
        vault.save()
    return _safe_call(_do)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

@eel.expose
def get_audit_log_entries(filters: dict = None, limit: int = 200, offset: int = 0) -> dict:
    _touch_session()
    def _do():
        _require_admin()
        f = filters or {}
        return get_audit_log(
            action_filter=f.get('action'),
            user_filter=f.get('user_id'),
            date_from=f.get('date_from'),
            date_to=f.get('date_to'),
            limit=limit,
            offset=offset
        )
    return _safe_call(_do)


@eel.expose
def get_dashboard_stats() -> dict:
    _touch_session()
    def _do():
        _require_auth()
        conn = db_module.get_db()
        total_smiths = conn.execute("SELECT COUNT(*) FROM smiths").fetchone()[0]
        total_entries = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        pending_requests = conn.execute(
            "SELECT COUNT(*) FROM change_requests WHERE status='pending'"
        ).fetchone()[0]

        # Recent 10 entries
        recent = get_entries(limit=10, offset=0)
        # Reverse for most-recent-first display
        recent.reverse()

        my_requests = []
        if current_user['role'] == 'employee':
            my_requests = get_requests(status=None, user_id=current_user['id'])[:5]

        return {
            'total_smiths': total_smiths,
            'total_entries': total_entries,
            'pending_requests': pending_requests,
            'recent_entries': recent,
            'my_requests': my_requests
        }
    return _safe_call(_do)


@eel.expose
def recalc_smith_balance(smith_id: int) -> dict:
    _touch_session()
    def _do():
        _require_admin()
        balance = recalculate_smith_balance(smith_id)
        vault.save()
        return {'balance': balance}
    return _safe_call(_do)


# ---------------------------------------------------------------------------
# Application startup
# ---------------------------------------------------------------------------

def main():
    global vault

    logger.info("GoldVault Ledger starting. APP_DIR=%s", APP_DIR)
    logger.info("DATA_FOLDER=%s", DATA_FOLDER)

    # Verify data folder is accessible
    if not os.path.exists(APP_DIR):
        logger.error("Application directory not found: %s", APP_DIR)
        sys.exit(1)

    # Initialise Eel
    frontend_path = os.path.join(APP_DIR, 'frontend')
    if not os.path.exists(frontend_path):
        # PyInstaller bundle: frontend is in _MEIPASS
        if hasattr(sys, '_MEIPASS'):
            frontend_path = os.path.join(sys._MEIPASS, 'frontend')
        else:
            logger.error("Frontend folder not found: %s", frontend_path)
            sys.exit(1)

    eel.init(frontend_path)

    # Start background threads
    usb_thread = threading.Thread(target=_usb_poll_thread, daemon=True)
    usb_thread.start()

    session_thread = threading.Thread(target=_session_timeout_thread, daemon=True)
    session_thread.start()

    logger.info("Starting Eel application...")
    try:
        eel.start(
            'index.html',
            size=(1280, 800),
            port=0,  # Random available port
            mode='chrome-app',  # Use Chrome in app mode if available
            cmdline_args=['--disable-web-security', '--allow-file-access-from-files']
        )
    except (SystemExit, MemoryError, KeyboardInterrupt):
        pass
    except Exception as e:
        logger.error("Eel start error: %s", e)
        # Fallback: try default browser
        try:
            eel.start('index.html', size=(1280, 800), port=0)
        except Exception as e2:
            logger.error("Fallback start error: %s", e2)


if __name__ == '__main__':
    main()
