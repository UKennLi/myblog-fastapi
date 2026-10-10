import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
import uuid
import bcrypt
import re


def active_url(value):
    normalized = re.sub(r"[\x00-\x20\x7f]", "", value or "").lower()
    return normalized.startswith(("javascript:", "vbscript:", "data:"))


def verify_password(password, stored):
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], stored.encode("ascii"))
    except (ValueError, TypeError, UnicodeError):
        return False


def encode_password(password):
    # Spring BCrypt's historical 72-byte input behavior; keep existing hashes usable.
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=10, prefix=b"2a")).decode()


def masked_csrf(raw):
    raw = raw.encode()
    mask = secrets.token_bytes(len(raw))
    return base64.urlsafe_b64encode(mask + bytes(a ^ b for a, b in zip(mask, raw))).decode()


def valid_csrf(value, raw):
    if not value:
        return False
    try:
        payload = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        half = len(payload) // 2
        decoded = bytes(a ^ b for a, b in zip(payload[:half], payload[half:]))
        return len(payload) == 2 * len(raw.encode()) and hmac.compare_digest(decoded, raw.encode())
    except (ValueError, TypeError):
        return False


class SessionStore:
    """Server-side, revocable sessions shared by workers without changing MySQL."""
    def __init__(self, settings):
        self.path = settings.session_file
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.secret = settings.session_secret.get_secret_value().encode()
        self.timeout = settings.session_timeout
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS sessions (key TEXT PRIMARY KEY, user_id INTEGER, username TEXT, csrf TEXT NOT NULL, expires REAL NOT NULL)")
        os.chmod(self.path, 0o600)

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        return connection

    def key(self, token):
        return hmac.new(self.secret, token.encode(), hashlib.sha256).hexdigest()

    def get(self, token):
        if not token or len(token) > 128:
            return None
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE key=? AND expires>?", (self.key(token), time.time())).fetchone()
            if row:
                db.execute("UPDATE sessions SET expires=? WHERE key=?", (time.time() + self.timeout, row["key"]))
                return dict(row)
        return None

    def create(self, user_id=None, username=None):
        token = secrets.token_hex(16).upper()
        session = dict(key=self.key(token), user_id=user_id, username=username, csrf=str(uuid.uuid4()), expires=time.time() + self.timeout)
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
            db.execute("INSERT INTO sessions VALUES (:key,:user_id,:username,:csrf,:expires)", session)
        return token, session

    def delete(self, token):
        if token:
            with self.connect() as db:
                db.execute("DELETE FROM sessions WHERE key=?", (self.key(token),))

    def clear(self):
        with self.connect() as db:
            db.execute("DELETE FROM sessions")
