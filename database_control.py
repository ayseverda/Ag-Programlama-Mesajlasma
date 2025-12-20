from database import get_db_connection


# =====================================================
# 📦 TÜM TABLOLARI LİSTELE
# =====================================================

def inspect_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
    """)
    tables = cursor.fetchall()
    conn.close()

    print("\n📦 DATABASE TABLES")
    for t in tables:
        print(" -", t["name"])


# =====================================================
# 🧱 TABLO ŞEMASI
# =====================================================

def inspect_table_schema(table_name: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    conn.close()

    print(f"\n🧱 TABLE SCHEMA: {table_name}")
    for col in columns:
        print(f" - {col['name']} ({col['type']})")


# =====================================================
# 👤 USERS TABLOSU
# =====================================================

def inspect_users():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, username, is_online, created_at
        FROM users
    """)
    rows = cursor.fetchall()
    conn.close()

    print("\n👤 USERS")
    for r in rows:
        print(dict(r))


# =====================================================
# 💬 MESAJLAR (GENEL)
# =====================================================

def inspect_messages(limit=20):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, sender_id, receiver_id, group_id,
               is_broadcast, is_group, is_delivered,
               message_hash, created_at
        FROM messages
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    print("\n💬 MESSAGES")
    for r in rows:
        print(dict(r))


# =====================================================
# 📢 BROADCAST MESAJLAR
# =====================================================

def inspect_broadcast_messages():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, sender_id, receiver_id,
               is_broadcast, is_delivered, created_at
        FROM messages
        WHERE is_broadcast = 1
    """)
    rows = cursor.fetchall()
    conn.close()

    print("\n📢 BROADCAST MESSAGES")
    for r in rows:
        print(dict(r))


# =====================================================
# 👥 GROUP MESAJLAR
# =====================================================

def inspect_group_messages():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, sender_id, group_id,
               is_group, created_at
        FROM messages
        WHERE is_group = 1
    """)
    rows = cursor.fetchall()
    conn.close()

    print("\n👥 GROUP MESSAGES")
    for r in rows:
        print(dict(r))


# =====================================================
# 🧪 HEPSİ TEK SEFERDE
# =====================================================

def full_database_check():
    inspect_tables()
    inspect_users()
    inspect_messages()
    inspect_broadcast_messages()
    inspect_group_messages()




if __name__ == "__main__":
    print("🔍 DATABASE KONTROL BAŞLADI")
    full_database_check()
