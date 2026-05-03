"""
GoldVault Ledger - Encrypted Database Layer
Handles AES-256-GCM encryption/decryption of SQLite database stored on disk.
The database lives entirely in memory while the app is running.
"""

import os
import sqlite3
import tempfile
import logging
from typing import Optional

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin','employee')),
    active INTEGER DEFAULT 1,
    created_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS smiths (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    balance REAL DEFAULT 0.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY,
    entry_number INTEGER NOT NULL,
    entry_date TEXT NOT NULL,
    entry_time TEXT NOT NULL,
    smith_id INTEGER NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('Smith to Moozhayil','Moozhayil to Smith')),
    raw_weight REAL NOT NULL,
    purity REAL NOT NULL,
    converted_weight REAL NOT NULL,
    balance_after REAL NOT NULL,
    user_id INTEGER NOT NULL,
    remarks TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (smith_id) REFERENCES smiths(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS change_requests (
    id INTEGER PRIMARY KEY,
    entry_id INTEGER NOT NULL,
    requested_changes TEXT NOT NULL,
    reason TEXT NOT NULL,
    requested_by INTEGER NOT NULL,
    requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
    approved_by INTEGER,
    approved_at TEXT,
    admin_remarks TEXT,
    FOREIGN KEY (entry_id) REFERENCES entries(id),
    FOREIGN KEY (requested_by) REFERENCES users(id),
    FOREIGN KEY (approved_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,
    original_data TEXT,
    new_data TEXT,
    changed_by INTEGER NOT NULL,
    approved_by INTEGER,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    remarks TEXT,
    FOREIGN KEY (changed_by) REFERENCES users(id),
    FOREIGN KEY (approved_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

INITIAL_SETTINGS = [
    ('db_version', '1'),
    ('next_entry_number', '1'),
]

PBKDF2_ITERATIONS = 600_000
SALT_SIZE = 32
NONCE_SIZE = 12


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit AES key from password + salt using PBKDF2-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
        backend=default_backend()
    )
    return kdf.derive(password.encode('utf-8'))


def _encrypt(data: bytes, key: bytes) -> bytes:
    """
    Encrypt data with AES-256-GCM.
    Returns: SALT(32) + NONCE(12) + CIPHERTEXT+TAG
    Note: salt is already embedded in the file; here we just use the nonce.
    This function is called with the key already derived, so we only prepend nonce.
    """
    nonce = os.urandom(NONCE_SIZE)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return nonce + ciphertext


def _decrypt(nonce_and_ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt AES-256-GCM data. Input: NONCE(12) + CIPHERTEXT+TAG"""
    nonce = nonce_and_ciphertext[:NONCE_SIZE]
    ciphertext = nonce_and_ciphertext[NONCE_SIZE:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def _db_to_bytes(conn: sqlite3.Connection) -> bytes:
    """
    Export an in-memory SQLite connection to raw bytes.
    Uses a temporary file as an intermediate step for broad Python version compatibility.
    """
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Backup in-memory DB to temp file
        dest = sqlite3.connect(tmp_path)
        conn.backup(dest)
        dest.close()

        with open(tmp_path, 'rb') as f:
            return f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _bytes_to_db(data: bytes) -> sqlite3.Connection:
    """
    Load raw SQLite bytes into an in-memory connection.
    Uses a temporary file as an intermediate step.
    """
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        src = sqlite3.connect(tmp_path)
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        src.backup(conn)
        src.close()
        return conn
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


class EncryptedVault:
    """
    Manages the AES-256-GCM encrypted SQLite database.

    File format on disk:
        SALT (32 bytes) | NONCE (12 bytes) | CIPHERTEXT + GCM TAG (rest)

    The database lives in memory (self.conn) while unlocked.
    """

    def __init__(self, data_folder: str):
        self.data_folder = data_folder
        self.vault_path = os.path.join(data_folder, 'ledger.enc')
        self.conn: Optional[sqlite3.Connection] = None
        self._master_key: Optional[bytes] = None  # kept in memory for saves

    # ------------------------------------------------------------------
    # First-run setup
    # ------------------------------------------------------------------
    def setup_first_run(self, master_password: str, admin_username: str, admin_password: str) -> None:
        """
        Create a brand-new encrypted vault:
        1. Create in-memory DB with schema
        2. Insert admin user
        3. Encrypt and write to disk
        """
        os.makedirs(self.data_folder, exist_ok=True)

        # Create in-memory DB
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)

        # Insert initial settings
        for key, value in INITIAL_SETTINGS:
            self.conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )
        self.conn.commit()

        # Insert admin user (import here to avoid circular imports)
        from backend.auth import hash_password
        salt_hex, hash_hex = hash_password(admin_password)
        self.conn.execute(
            """INSERT INTO users (username, password_hash, salt, role, active, created_by)
               VALUES (?, ?, ?, 'admin', 1, NULL)""",
            (admin_username, hash_hex, salt_hex)
        )
        self.conn.commit()

        # Generate master key and save
        salt = os.urandom(SALT_SIZE)
        self._master_key = _derive_key(master_password, salt)
        self._write_to_disk(salt)
        logger.info("New vault created at %s", self.vault_path)

    # ------------------------------------------------------------------
    # Load existing vault
    # ------------------------------------------------------------------
    def load(self, master_password: str) -> None:
        """
        Decrypt the vault file and load into in-memory SQLite.
        Raises ValueError on wrong password or corrupt file.
        """
        if not os.path.exists(self.vault_path):
            raise FileNotFoundError(f"Vault not found: {self.vault_path}")

        with open(self.vault_path, 'rb') as f:
            file_data = f.read()

        if len(file_data) < SALT_SIZE + NONCE_SIZE + 16:
            raise ValueError("Vault file is too small or corrupt.")

        salt = file_data[:SALT_SIZE]
        nonce_and_ct = file_data[SALT_SIZE:]

        key = _derive_key(master_password, salt)

        try:
            db_bytes = _decrypt(nonce_and_ct, key)
        except Exception:
            raise ValueError("Incorrect master password or corrupt vault.")

        self.conn = _bytes_to_db(db_bytes)
        self._master_key = key
        logger.info("Vault loaded successfully from %s", self.vault_path)

    # ------------------------------------------------------------------
    # Save (encrypt and write to disk)
    # ------------------------------------------------------------------
    def save(self) -> None:
        """
        Export in-memory DB to bytes, encrypt, and write to disk.
        Raises OSError if disk write fails (e.g., USB removed).
        """
        if self.conn is None:
            raise RuntimeError("No database loaded.")
        if self._master_key is None:
            raise RuntimeError("Master key not available.")

        # Read existing salt from file (we keep the same salt)
        if os.path.exists(self.vault_path):
            with open(self.vault_path, 'rb') as f:
                salt = f.read(SALT_SIZE)
        else:
            salt = os.urandom(SALT_SIZE)

        self._write_to_disk(salt)

    def _write_to_disk(self, salt: bytes) -> None:
        """Internal: export DB, encrypt, write SALT+NONCE+CT to vault_path."""
        db_bytes = _db_to_bytes(self.conn)
        encrypted = _encrypt(db_bytes, self._master_key)
        # Write atomically: write to temp file then rename
        tmp_path = self.vault_path + '.tmp'
        with open(tmp_path, 'wb') as f:
            f.write(salt)
            f.write(encrypted)
        os.replace(tmp_path, self.vault_path)
        logger.debug("Vault saved to %s", self.vault_path)

    # ------------------------------------------------------------------
    # Backup / Restore
    # ------------------------------------------------------------------
    def backup_to(self, destination_path: str) -> None:
        """Copy the current encrypted vault file to destination_path."""
        import shutil
        if not os.path.exists(self.vault_path):
            raise FileNotFoundError("No vault file to back up.")
        shutil.copy2(self.vault_path, destination_path)
        logger.info("Backup created at %s", destination_path)

    def restore_from(self, backup_path: str, master_password: str) -> None:
        """
        Validate backup can be decrypted, then replace current vault and reload.
        """
        with open(backup_path, 'rb') as f:
            file_data = f.read()

        if len(file_data) < SALT_SIZE + NONCE_SIZE + 16:
            raise ValueError("Backup file is too small or corrupt.")

        salt = file_data[:SALT_SIZE]
        nonce_and_ct = file_data[SALT_SIZE:]
        key = _derive_key(master_password, salt)

        try:
            db_bytes = _decrypt(nonce_and_ct, key)
        except Exception:
            raise ValueError("Cannot decrypt backup: wrong password or corrupt file.")

        # Close existing connection
        self.close()

        # Replace vault file
        import shutil
        shutil.copy2(backup_path, self.vault_path)

        # Reload
        self.conn = _bytes_to_db(db_bytes)
        self._master_key = key
        logger.info("Vault restored from %s", backup_path)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    def close(self) -> None:
        """Close the in-memory database and clear sensitive data."""
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
        self._master_key = None
        logger.info("Vault closed.")

    def is_open(self) -> bool:
        return self.conn is not None

    def exists(self) -> bool:
        return os.path.exists(self.vault_path)

    def get_conn(self) -> sqlite3.Connection:
        if self.conn is None:
            raise RuntimeError("Vault is not open.")
        return self.conn


# ---------------------------------------------------------------------------
# Global vault instance (set by main.py)
# ---------------------------------------------------------------------------
vault: Optional[EncryptedVault] = None


def get_vault() -> EncryptedVault:
    global vault
    if vault is None:
        raise RuntimeError("Vault not initialised.")
    return vault


def get_db() -> sqlite3.Connection:
    return get_vault().get_conn()
