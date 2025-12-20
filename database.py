import sqlite3
import hashlib
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_NAME = "messaging.db"


def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_online INTEGER DEFAULT 0,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER,
            group_id INTEGER,
            encrypted_content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            is_broadcast INTEGER DEFAULT 0,
            is_group INTEGER DEFAULT 0,
            is_delivered INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            delivered_at TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users(id),
            FOREIGN KEY (receiver_id) REFERENCES users(id),
            FOREIGN KEY (group_id) REFERENCES groups(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            creator_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (creator_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
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
        password_hash = generate_password_hash(password)
        cursor.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            (username, password_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid
        return {"success": True, "user_id": user_id, "username": username}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Username already exists"}
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user and check_password_hash(user['password_hash'], password):
        return {
            "success": True,
            "user_id": user['id'],
            "username": user['username']
        }
    return {"success": False, "error": "Invalid username or password"}


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


def calculate_message_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def save_message(sender_id: int, receiver_id: int, encrypted_content: str, 
                 is_broadcast: bool = False, is_delivered: bool = False) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    content_hash = calculate_message_hash(encrypted_content)
    
    cursor.execute('''
        INSERT INTO messages 
        (sender_id, receiver_id, encrypted_content, content_hash, is_broadcast, is_delivered)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (sender_id, receiver_id, encrypted_content, content_hash, 
          1 if is_broadcast else 0, 1 if is_delivered else 0))
    
    conn.commit()
    message_id = cursor.lastrowid
    conn.close()
    return message_id


def get_undelivered_messages(user_id: int) -> list:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT m.*, u.username as sender_username
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE (m.receiver_id = ? OR m.is_broadcast = 1) 
        AND m.is_delivered = 0
        AND m.sender_id != ?
        ORDER BY m.created_at ASC
    ''', (user_id, user_id))
    
    messages = []
    for row in cursor.fetchall():
        messages.append({
            "id": row['id'],
            "sender_id": row['sender_id'],
            "sender_username": row['sender_username'],
            "encrypted_content": row['encrypted_content'],
            "content_hash": row['content_hash'],
            "is_broadcast": bool(row['is_broadcast']),
            "created_at": row['created_at']
        })
    
    conn.close()
    return messages


def mark_messages_delivered(message_ids: list):
    if not message_ids:
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    placeholders = ','.join('?' * len(message_ids))
    cursor.execute(f'''
        UPDATE messages 
        SET is_delivered = 1, delivered_at = ? 
        WHERE id IN ({placeholders})
    ''', [datetime.now()] + message_ids)
    
    conn.commit()
    conn.close()


def get_message_history(user_id: int, other_user_id: int = None, limit: int = 50) -> list:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if other_user_id:
        cursor.execute('''
            SELECT m.*, 
                   s.username as sender_username,
                   r.username as receiver_username
            FROM messages m
            JOIN users s ON m.sender_id = s.id
            LEFT JOIN users r ON m.receiver_id = r.id
            WHERE m.is_broadcast = 0 
              AND m.is_group = 0
              AND ((m.sender_id = ? AND m.receiver_id = ?)
                   OR (m.sender_id = ? AND m.receiver_id = ?))
            ORDER BY m.created_at DESC
            LIMIT ?
        ''', (user_id, other_user_id, other_user_id, user_id, limit))
    else:
        cursor.execute('''
            SELECT m.*, 
                   s.username as sender_username,
                   r.username as receiver_username
            FROM messages m
            JOIN users s ON m.sender_id = s.id
            LEFT JOIN users r ON m.receiver_id = r.id
            WHERE m.is_broadcast = 1
            ORDER BY m.created_at DESC
            LIMIT ?
        ''', (limit,))
    
    messages = []
    for row in cursor.fetchall():
        messages.append({
            "id": row['id'],
            "sender_id": row['sender_id'],
            "sender_username": row['sender_username'],
            "receiver_id": row['receiver_id'],
            "receiver_username": row['receiver_username'],
            "encrypted_content": row['encrypted_content'],
            "content_hash": row['content_hash'],
            "is_broadcast": bool(row['is_broadcast']),
            "created_at": row['created_at']
        })
    
    conn.close()
    return list(reversed(messages))


def verify_message_integrity(message_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT encrypted_content, content_hash FROM messages WHERE id = ?', (message_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        calculated_hash = calculate_message_hash(row['encrypted_content'])
        return calculated_hash == row['content_hash']
    return False


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


def save_group_message(sender_id: int, group_id: int, encrypted_content: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    content_hash = calculate_message_hash(encrypted_content)
    
    cursor.execute('''
        INSERT INTO messages 
        (sender_id, group_id, encrypted_content, content_hash, is_group, is_delivered)
        VALUES (?, ?, ?, ?, 1, 0)
    ''', (sender_id, group_id, encrypted_content, content_hash))
    
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
            "content_hash": row['content_hash'],
            "created_at": row['created_at']
        })
    
    conn.close()
    return list(reversed(messages))


def get_undelivered_group_messages(user_id: int) -> list:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT m.*, u.username as sender_username, g.name as group_name
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        JOIN groups g ON m.group_id = g.id
        JOIN group_members gm ON m.group_id = gm.group_id
        WHERE gm.user_id = ? 
        AND m.is_group = 1 
        AND m.sender_id != ?
        AND m.created_at > (
            SELECT COALESCE(MAX(delivered_at), '1970-01-01') 
            FROM messages 
            WHERE group_id = m.group_id AND is_group = 1
        )
        ORDER BY m.created_at ASC
    ''', (user_id, user_id))
    
    messages = []
    for row in cursor.fetchall():
        messages.append({
            "id": row['id'],
            "sender_id": row['sender_id'],
            "sender_username": row['sender_username'],
            "group_id": row['group_id'],
            "group_name": row['group_name'],
            "encrypted_content": row['encrypted_content'],
            "created_at": row['created_at']
        })
    
    conn.close()
    return messages

if __name__ == "__main__":
    init_db()

