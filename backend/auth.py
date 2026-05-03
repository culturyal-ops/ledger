"""
GoldVault Ledger - Authentication & User Management
Handles password hashing, user CRUD, and session management.
"""

import os
import hashlib
import logging
from typing import Optional, Dict, Any

from backend.database import get_db

logger = logging.getLogger(__name__)

PBKDF2_ITERATIONS = 600_000
HASH_ALGORITHM = 'sha256'
KEY_LENGTH = 32  # bytes


def hash_password(password: str, salt_hex: Optional[str] = None) -> tuple[str, str]:
    """
    Hash a password using PBKDF2-HMAC-SHA256.

    Args:
        password: Plain-text password.
        salt_hex: Hex-encoded salt. If None, a new random salt is generated.

    Returns:
        (salt_hex, hash_hex) tuple.
    """
    if salt_hex is None:
        salt = os.urandom(32)
        salt_hex = salt.hex()
    else:
        salt = bytes.fromhex(salt_hex)

    dk = hashlib.pbkdf2_hmac(
        HASH_ALGORITHM,
        password.encode('utf-8'),
        salt,
        PBKDF2_ITERATIONS,
        dklen=KEY_LENGTH
    )
    return salt_hex, dk.hex()


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    """Verify a password against stored salt and hash."""
    _, computed_hash = hash_password(password, salt_hex)
    # Constant-time comparison to prevent timing attacks
    return hashlib.compare_digest(computed_hash, hash_hex)


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate a user by username and password.

    Returns:
        User dict (id, username, role, active) on success, None on failure.
    """
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, password_hash, salt, role, active FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    if row is None:
        logger.warning("Login attempt for unknown user: %s", username)
        return None

    if not row['active']:
        logger.warning("Login attempt for inactive user: %s", username)
        return None

    if not verify_password(password, row['salt'], row['password_hash']):
        logger.warning("Failed login for user: %s", username)
        return None

    logger.info("User authenticated: %s (role=%s)", username, row['role'])
    return {
        'id': row['id'],
        'username': row['username'],
        'role': row['role'],
        'active': row['active']
    }


def create_user(username: str, password: str, role: str, created_by: Optional[int]) -> int:
    """
    Create a new user.

    Args:
        username: Must be unique, minimum 3 characters.
        password: Plain-text password.
        role: 'admin' or 'employee'.
        created_by: User ID of the creator (None for first admin).

    Returns:
        New user's ID.

    Raises:
        ValueError: If username is too short, role is invalid, or username already exists.
    """
    if len(username.strip()) < 3:
        raise ValueError("Username must be at least 3 characters.")
    if role not in ('admin', 'employee'):
        raise ValueError("Role must be 'admin' or 'employee'.")

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if existing:
        raise ValueError(f"Username '{username}' already exists.")

    salt_hex, hash_hex = hash_password(password)
    cursor = conn.execute(
        """INSERT INTO users (username, password_hash, salt, role, active, created_by)
           VALUES (?, ?, ?, ?, 1, ?)""",
        (username, hash_hex, salt_hex, role, created_by)
    )
    conn.commit()
    logger.info("User created: %s (role=%s) by user_id=%s", username, role, created_by)
    return cursor.lastrowid


def get_users() -> list:
    """Return all users with creator username."""
    conn = get_db()
    rows = conn.execute(
        """SELECT u.id, u.username, u.role, u.active, u.created_at,
                  c.username AS created_by_name
           FROM users u
           LEFT JOIN users c ON u.created_by = c.id
           ORDER BY u.created_at ASC"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Return a single user dict by ID."""
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, role, active, created_at FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    return dict(row) if row else None


def edit_user(user_id: int, username: Optional[str], password: Optional[str],
              role: Optional[str], active: Optional[int]) -> None:
    """
    Edit an existing user. Only provided (non-None) fields are updated.

    Raises:
        ValueError: If new username conflicts or role is invalid.
    """
    conn = get_db()
    current = conn.execute(
        "SELECT id, username, role, active FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not current:
        raise ValueError(f"User ID {user_id} not found.")

    new_username = username if username is not None else current['username']
    new_role = role if role is not None else current['role']
    new_active = active if active is not None else current['active']

    if len(new_username.strip()) < 3:
        raise ValueError("Username must be at least 3 characters.")
    if new_role not in ('admin', 'employee'):
        raise ValueError("Role must be 'admin' or 'employee'.")

    # Check username uniqueness (excluding self)
    conflict = conn.execute(
        "SELECT id FROM users WHERE username = ? AND id != ?", (new_username, user_id)
    ).fetchone()
    if conflict:
        raise ValueError(f"Username '{new_username}' already exists.")

    if password:
        salt_hex, hash_hex = hash_password(password)
        conn.execute(
            """UPDATE users SET username=?, password_hash=?, salt=?, role=?, active=?
               WHERE id=?""",
            (new_username, hash_hex, salt_hex, new_role, new_active, user_id)
        )
    else:
        conn.execute(
            "UPDATE users SET username=?, role=?, active=? WHERE id=?",
            (new_username, new_role, new_active, user_id)
        )
    conn.commit()
    logger.info("User %d updated.", user_id)


def delete_user(user_id: int) -> None:
    """
    Delete a user. Raises ValueError if the user has any entries.
    """
    conn = get_db()
    entry_count = conn.execute(
        "SELECT COUNT(*) FROM entries WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    if entry_count > 0:
        raise ValueError(
            "Cannot delete user with existing entries. Archive them first or reassign."
        )
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    logger.info("User %d deleted.", user_id)


def toggle_user_active(user_id: int, active: bool) -> None:
    """Activate or deactivate a user."""
    conn = get_db()
    conn.execute(
        "UPDATE users SET active = ? WHERE id = ?",
        (1 if active else 0, user_id)
    )
    conn.commit()
    logger.info("User %d active=%s", user_id, active)


def change_password(user_id: int, new_password: str) -> None:
    """Change a user's password."""
    salt_hex, hash_hex = hash_password(new_password)
    conn = get_db()
    conn.execute(
        "UPDATE users SET password_hash=?, salt=? WHERE id=?",
        (hash_hex, salt_hex, user_id)
    )
    conn.commit()
    logger.info("Password changed for user %d.", user_id)
