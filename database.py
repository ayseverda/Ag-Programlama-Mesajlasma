import os
import base64
import time
import sqlite3

from datetime import datetime

class PasswordHasher:
    def __init__(self, rounds=2000, salt_bytes=16):
        self.rounds = rounds
        self.salt_bytes = salt_bytes

    def generate_salt(self, length=None):
        if length is None:
            length = self.salt_bytes
        return os.urandom(length).hex()

    def _rotate_left(self, x, n, bits=64):
        return ((x << n) | (x >> (bits - n))) & ((1 << bits) - 1)

    def _rotate_right(self, x, n, bits=64):
        return ((x >> n) | (x << (bits - n))) & ((1 << bits) - 1)

    def _mix_block(self, val, salt_val):
        val ^= salt_val
        val = (val * 0xA5A5A5A5A5A5A5A5) & ((1 << 64) - 1)
        val = self._rotate_left(val, 13)
        val ^= (val >> 7)
        val = self._rotate_right(val, 17)
        val = (val * 0x9E3779B97F4A7C15) & ((1 << 64) - 1)
        return val

    def hash(self, password: str, salt: str = None) -> dict:
        if salt is None:
            salt = self.generate_salt()

        state = 0
        for b in password.encode():
            state = (state * 1315423911 + b) & ((1 << 64) - 1)

        salt_int = int.from_bytes(bytes.fromhex(salt), "big")

        for _ in range(self.rounds):
            state = self._mix_block(state, salt_int)

        hash_b64 = base64.b64encode(state.to_bytes(8, "big")).decode()

        return {
            "hash": hash_b64,
            "salt": salt,
            "rounds": str(self.rounds)
        }

    def verify(self, password, hash_value, salt, rounds):
        original = self.rounds
        self.rounds = int(rounds)

        try:
            h2 = self.hash(password, salt)["hash"]
            result = 0
            for a, b in zip(h2, hash_value):
                result |= ord(a) ^ ord(b)
            return result == 0
        finally:
            self.rounds = original


password_hasher = PasswordHasher()

class MessageHasher:
    def __init__(self):
        self.fnv_prime = 0x100000001b3
        self.fnv_offset = 0xcbf29ce484222325

    def _fnv1a(self, data):
        h = self.fnv_offset
        for b in data:
            h ^= b
            h = (h * self.fnv_prime) & 0xFFFFFFFFFFFFFFFF
        return h

    def _djb2(self, data):
        h = 5381
        for b in data:
            h = ((h << 5) + h + b) & 0xFFFFFFFF
        return h

    def generate(self, content, sender_id, timestamp=None):
        if timestamp is None:
            timestamp = str(time.time())

        data = f"{content}|{sender_id}|{timestamp}".encode()
        h1 = self._fnv1a(data)
        h2 = self._djb2(data)

        combined = (h1 ^ (h2 << 32)) & 0xFFFFFFFFFFFFFFFF
        return format(combined, "016x")


message_hasher = MessageHasher()
DATABASE_NAME = "messaging.db"
def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("""
      CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password_hash TEXT,
    salt TEXT,
    rounds TEXT,
    is_online INTEGER DEFAULT 0,
    last_seen TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            receiver_id INTEGER,
            group_id INTEGER,
            encrypted_content TEXT,
            message_hash TEXT,
            is_broadcast INTEGER DEFAULT 0,
            is_group INTEGER DEFAULT 0,
           is_delivered INTEGER DEFAULT 0,
           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
           delivered_at TIMESTAMP
        )
    """)
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            creator_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (creator_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES groups(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(group_id, user_id)
        )
    ''')
    

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")


def create_user(username: str, password: str) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        password_data = password_hasher.hash(password)

        cursor.execute(
            '''
            INSERT INTO users (username, password_hash, salt, rounds)
            VALUES (?, ?, ?, ?)
            ''',
            (
                username,
                password_data["hash"],
                password_data["salt"],
                password_data["rounds"]
            )
        )
        conn.commit()
        user_id = cursor.lastrowid

        return {
            "success": True,
            "user_id": user_id,
            "username": username
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        conn.close()



def authenticate_user(username: str, password: str) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        'SELECT * FROM users WHERE username = ?',
        (username,)
    )
    user = cursor.fetchone()
    conn.close()

    if not user:
        return {"success": False, "error": "Kullanıcı bulunamadı"}

    if not password_hasher.verify(
        password,
        user["password_hash"],
        user["salt"],
        user["rounds"]
    ):
        return {"success": False, "error": "Şifre hatalı"}

    return {
        "success": True,
        "user_id": user["id"],
        "username": user["username"]
    }


def set_user_online(user_id: int, is_online: bool = True):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        'UPDATE users SET is_online = ?, last_seen = ? WHERE id = ?',
        (1 if is_online else 0, datetime.now(), user_id)
    )
    conn.commit()
    conn.close()


def get_online_users() -> list:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, username FROM users WHERE is_online = 1')
    users = [{"id": row['id'], "username": row['username']} for row in cursor.fetchall()]
    conn.close()
    return users


def get_all_users() -> list:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, username, is_online FROM users')
    users = [{"id": row['id'], "username": row['username'], "is_online": bool(row['is_online'])} 
             for row in cursor.fetchall()]
    conn.close()
    return users


def get_user_by_id(user_id: int) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, username, is_online FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {"id": user['id'], "username": user['username'], "is_online": bool(user['is_online'])}
    return None


def get_user_by_username(username: str) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, username, is_online FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {"id": user['id'], "username": user['username'], "is_online": bool(user['is_online'])}
    return None
def save_message(sender_id, receiver_id, encrypted_content, is_broadcast, is_delivered):
    conn = get_db_connection()
    cursor = conn.cursor()

    msg_hash = message_hasher.generate(
        encrypted_content,
        sender_id
    )

    cursor.execute("""
        INSERT INTO messages
        (sender_id, receiver_id, encrypted_content, message_hash,
         is_broadcast, is_group, is_delivered)
        VALUES (?, ?, ?, ?, ?, 0, ?)
    """, (
        sender_id,
        receiver_id,
        encrypted_content,
        msg_hash,
        int(is_broadcast),
        int(is_delivered)
    ))

    conn.commit()
    message_id = cursor.lastrowid
    conn.close()
    return message_id

def get_undelivered_messages(user_id: int) -> list:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.id, m.sender_id, u.username AS sender_username,
               m.encrypted_content, m.message_hash,
               m.is_broadcast, m.created_at
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE m.sender_id != ?
          AND (
              (m.receiver_id = ? AND m.is_broadcast = 0)
              OR
              (m.is_broadcast = 1 AND m.receiver_id IS NULL)
          )
          AND m.is_delivered = 0
        ORDER BY m.created_at ASC
    """, (user_id, user_id))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def mark_messages_delivered(message_ids: list):
    if not message_ids:
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    placeholders = ','.join('?' * len(message_ids))
    cursor.execute(f"""
        UPDATE messages
        SET is_delivered = 1,
            delivered_at = ?
        WHERE id IN ({placeholders})
    """, [datetime.now()] + message_ids)

    
    conn.commit()
    conn.close()

def get_message_history(user_id: int, other_user_id: int = None, limit=50):
    conn = get_db_connection()
    cursor = conn.cursor()

    if other_user_id:
        cursor.execute('''
            SELECT m.*, u.username as sender_username
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.is_broadcast = 0 
              AND m.is_group = 0
              AND ((m.sender_id = ? AND m.receiver_id = ?)
                   OR (m.sender_id = ? AND m.receiver_id = ?))
            ORDER BY m.created_at DESC
            LIMIT ?
        ''', (user_id, other_user_id, other_user_id, user_id, limit))
    else:
        cursor.execute('''
            SELECT m.*, u.username as sender_username
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.is_broadcast = 1 
              AND m.receiver_id IS NULL
            ORDER BY m.created_at DESC
            LIMIT ?
        ''', (limit,))

    rows = cursor.fetchall()
    conn.close()
    
    messages = []
    for row in rows:
        messages.append({
            "id": row['id'],
            "sender_id": row['sender_id'],
            "sender_username": row['sender_username'],
            "receiver_id": row['receiver_id'],
            "encrypted_content": row['encrypted_content'],
            "message_hash": row['message_hash'],
            "is_broadcast": bool(row['is_broadcast']),
            "created_at": row['created_at']
        })
    
    return list(reversed(messages))


def verify_message_integrity(message_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT encrypted_content, message_hash, sender_id, created_at
        FROM messages
        WHERE id = ?
    """, (message_id,))
    
    row = cursor.fetchone()
    conn.close()

    if not row:
        return False

    recalculated = message_hasher.generate(
        row["encrypted_content"],
        row["sender_id"],
        row["created_at"]
    )

    return recalculated == row["message_hash"]



# ============== GROUP FUNCTIONS ==============

def create_group(name: str, creator_id: int, member_ids: list) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            'INSERT INTO groups (name, creator_id) VALUES (?, ?)',
            (name, creator_id)
        )
        group_id = cursor.lastrowid
        
        cursor.execute(
            'INSERT INTO group_members (group_id, user_id) VALUES (?, ?)',
            (group_id, creator_id)
        )
        
        for member_id in member_ids:
            if member_id != creator_id:
                cursor.execute(
                    'INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?, ?)',
                    (group_id, member_id)
                )
        
        conn.commit()
        return {"success": True, "group_id": group_id, "name": name}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_user_groups(user_id: int) -> list:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT g.id, g.name, g.creator_id, g.created_at,
               (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) as member_count
        FROM groups g
        JOIN group_members gm ON g.id = gm.group_id
        WHERE gm.user_id = ?
        ORDER BY g.created_at DESC
    ''', (user_id,))
    
    groups = []
    for row in cursor.fetchall():
        groups.append({
            "id": row['id'],
            "name": row['name'],
            "creator_id": row['creator_id'],
            "member_count": row['member_count'],
            "created_at": row['created_at']
        })
    
    conn.close()
    return groups


def get_group_by_id(group_id: int) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM groups WHERE id = ?', (group_id,))
    group = cursor.fetchone()
    conn.close()
    
    if group:
        return {
            "id": group['id'],
            "name": group['name'],
            "creator_id": group['creator_id'],
            "created_at": group['created_at']
        }
    return None


def get_group_members(group_id: int) -> list:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT u.id, u.username, u.is_online
        FROM users u
        JOIN group_members gm ON u.id = gm.user_id
        WHERE gm.group_id = ?
    ''', (group_id,))
    
    members = []
    for row in cursor.fetchall():
        members.append({
            "id": row['id'],
            "username": row['username'],
            "is_online": bool(row['is_online'])
        })
    
    conn.close()
    return members


def is_group_member(group_id: int, user_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?',
        (group_id, user_id)
    )
    result = cursor.fetchone() is not None
    conn.close()
    return result


def add_group_member(group_id: int, user_id: int) -> bool:

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            'INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?, ?)',
            (group_id, user_id)
        )
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()


def remove_group_member(group_id: int, user_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        'DELETE FROM group_members WHERE group_id = ? AND user_id = ?',
        (group_id, user_id)
    )
    conn.commit()
    conn.close()
    return True


def save_group_message(sender_id, group_id, encrypted_content):
    conn = get_db_connection()
    cursor = conn.cursor()

    created_at = datetime.now().isoformat()

    msg_hash = message_hasher.generate(
        encrypted_content,
        sender_id,
        created_at
    )

    cursor.execute("""
        INSERT INTO messages
        (sender_id, receiver_id, group_id, encrypted_content,
         message_hash, is_group, is_broadcast, is_delivered, created_at)
        VALUES (?, NULL, ?, ?, ?, 1, 0, 0, ?)
    """, (
        sender_id,
        group_id,
        encrypted_content,
        msg_hash,
        created_at
    ))

    conn.commit()
    message_id = cursor.lastrowid
    conn.close()
    return message_id
def save_broadcast_message(sender_id: int, encrypted_content: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    created_at = datetime.now().isoformat()
    msg_hash = message_hasher.generate(encrypted_content, sender_id, created_at)

    cursor.execute("""
        INSERT INTO messages
        (sender_id, receiver_id, encrypted_content, message_hash,
         is_broadcast, is_group, is_delivered, created_at)
        VALUES (?, NULL, ?, ?, 1, 0, 0, ?)
    """, (sender_id, encrypted_content, msg_hash, created_at))

    conn.commit()
    message_id = cursor.lastrowid
    conn.close()

    return message_id
    


def get_group_message_history(group_id: int, limit: int = 50) -> list:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT m.*, u.username as sender_username
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE m.group_id = ? AND m.is_group = 1
        ORDER BY m.created_at DESC
        LIMIT ?
    ''', (group_id, limit))
    
    messages = []
    for row in cursor.fetchall():
        messages.append({
            "id": row['id'],
            "sender_id": row['sender_id'],
            "sender_username": row['sender_username'],
            "group_id": row['group_id'],
            "encrypted_content": row['encrypted_content'],
            "message_hash": row['message_hash'],
            "created_at": row['created_at']
        })
    
    conn.close()
    return list(reversed(messages))

if __name__ == "__main__":
    init_db()