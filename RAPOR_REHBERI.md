# 📋 PROJE RAPORU YAZIM REHBERİ

## 🎯 RAPOR YAPISI

### 1. GİRİŞ (1-2 sayfa)
- **Proje Amacı**: Güvenli, gerçek zamanlı mesajlaşma uygulaması
- **Kullanılan Teknolojiler**: Python (Flask, Flask-SocketIO), SQLite, HTML/CSS/JavaScript
- **Ödev Gereksinimleri**: 3 tip mesajlaşma, E2E şifreleme, hash ile veritabanı kaydı, offline mesaj desteği

---

## 2. SİSTEM MİMARİSİ (2-3 sayfa)

### 2.1 Genel Mimari
```
┌─────────────┐         WebSocket          ┌─────────────┐
│   Client    │◄─────────────────────────►│   Server    │
│ (Browser)   │                            │  (Flask)    │
│             │                            │             │
│ JavaScript  │                            │   Python    │
└─────────────┘                            └─────────────┘
                                                    │
                                                    ▼
                                            ┌─────────────┐
                                            │  SQLite DB  │
                                            └─────────────┘
```

**Bahsetmen Gerekenler:**
- **WebSocket Protokolü**: TCP tabanlı, gerçek zamanlı iki yönlü iletişim
- **Flask-SocketIO**: WebSocket bağlantılarını yönetir (`app.py:13`)
- **Event-Driven Mimari**: Her mesaj tipi için ayrı event handler'lar

### 2.2 Dosya Yapısı
```
📁 Proje Yapısı:
├── app.py              # Ana Flask uygulaması ve WebSocket handler'ları
├── database.py          # Veritabanı işlemleri (CRUD operasyonları)
├── encryption.py        # Şifreleme/çözme modülü
├── templates/          # HTML şablonları
│   ├── login.html
│   ├── register.html
│   └── chat.html
└── static/
    ├── css/style.css
    └── js/app.js       # Client-side WebSocket ve UI mantığı
```

---

## 3. VERİTABANI TASARIMI (2-3 sayfa)

### 3.1 Tablo Yapıları

#### 📊 **users** Tablosu (`database.py:19-28`)
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,        -- PBKDF2-SHA256 hash
    is_online INTEGER DEFAULT 0,       -- Online durumu
    last_seen TIMESTAMP,
    created_at TIMESTAMP
)
```

**Bahsetmen Gerekenler:**
- **Password Hashing**: `werkzeug.security.generate_password_hash()` kullanılıyor (PBKDF2-SHA256 + salt)
- **Online Status Tracking**: `is_online` alanı ile gerçek zamanlı durum takibi
- **Unique Constraint**: Kullanıcı adı benzersiz olmalı

#### 📊 **messages** Tablosu (`database.py:30-47`)
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL,
    receiver_id INTEGER,               -- NULL ise broadcast
    group_id INTEGER,                  -- NULL ise direct/broadcast
    encrypted_content TEXT NOT NULL,    -- Şifrelenmiş mesaj
    content_hash TEXT NOT NULL,         -- SHA-256 hash
    is_broadcast INTEGER DEFAULT 0,
    is_group INTEGER DEFAULT 0,
    is_delivered INTEGER DEFAULT 0,    -- Offline mesaj takibi
    created_at TIMESTAMP,
    delivered_at TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES users(id),
    FOREIGN KEY (receiver_id) REFERENCES users(id),
    FOREIGN KEY (group_id) REFERENCES groups(id)
)
```

**Bahsetmen Gerekenler:**
- **Üç Mesaj Tipi**: 
  - `is_broadcast=1, receiver_id=NULL` → Tüm kullanıcılara
  - `is_group=1, group_id!=NULL` → Grup mesajı
  - `receiver_id!=NULL, is_broadcast=0` → Direct mesaj
- **Hash Mekanizması**: Her mesaj için SHA-256 hash hesaplanıyor (`database.py:171-172`)
- **Offline Mesaj Desteği**: `is_delivered=0` olan mesajlar kullanıcı online olduğunda gönderilir

#### 📊 **groups** Tablosu (`database.py:49-57`)
```sql
CREATE TABLE groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    creator_id INTEGER NOT NULL,
    created_at TIMESTAMP,
    FOREIGN KEY (creator_id) REFERENCES users(id)
)
```

#### 📊 **group_members** Tablosu (`database.py:59-69`)
```sql
CREATE TABLE group_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    joined_at TIMESTAMP,
    UNIQUE(group_id, user_id)  -- Bir kullanıcı aynı gruba iki kez eklenemez
)
```

**Bahsetmen Gerekenler:**
- **Many-to-Many İlişki**: Bir kullanıcı birden fazla gruba, bir grup birden fazla kullanıcıya sahip olabilir
- **Unique Constraint**: Aynı kullanıcı aynı gruba iki kez eklenemez

---

## 4. SOKET PROGRAMLAMA (3-4 sayfa)

### 4.1 WebSocket Bağlantı Yönetimi

#### 🔌 **Bağlantı Kurma** (`app.py:152-184`)
```python
@socketio.on('connect')
def handle_connect():
    user_id = current_user.id
    sid = request.sid  # Session ID
    
    # Aktif bağlantıları takip et
    active_connections[user_id].append(sid)
    
    # Session key oluştur (E2E için)
    session_key = session_manager.create_session_key(sid)
    
    # Odaya katıl
    join_room(f'user_{user_id}')      # Kullanıcıya özel oda
    join_room('broadcast')             # Broadcast odası
    # Grup odalarına katıl
    for group in user_groups:
        join_room(f'group_{group["id"]}')
    
    # Offline mesajları gönder
    deliver_offline_messages(user_id, sid)
```

**Bahsetmen Gerekenler:**
- **Room-Based Messaging**: Her kullanıcı/grup için ayrı oda (room) sistemi
- **Session Key**: Her bağlantı için benzersiz şifreleme anahtarı
- **Connection Tracking**: `active_connections` dictionary ile aktif kullanıcılar takip ediliyor

#### 🔌 **Bağlantı Kopma** (`app.py:187-212`)
```python
@socketio.on('disconnect')
def handle_disconnect():
    # Bağlantıyı listeden çıkar
    # Eğer kullanıcının başka bağlantısı yoksa offline yap
    # Session key'i temizle
```

### 4.2 Mesaj Gönderme Event Handler'ları

#### 📤 **Direct/Broadcast Mesaj** (`app.py:215-271`)
```python
@socketio.on('send_message')
def handle_send_message(data):
    is_broadcast = data.get('is_broadcast', False)
    receiver_id = data.get('receiver_id')
    
    if is_broadcast:
        # Tüm kullanıcılara gönder
        emit('new_message', {...}, room='broadcast', include_self=False)
    else:
        # Tek kullanıcıya gönder
        emit('new_message', {...}, room=f'user_{receiver_id}')
    
    # Veritabanına kaydet (hash ile)
    message_id = db.save_message(...)
```

**Bahsetmen Gerekenler:**
- **Broadcast Mesaj**: `room='broadcast'` ile tüm online kullanıcılara gönderilir
- **Direct Mesaj**: `room=f'user_{receiver_id}'` ile sadece hedef kullanıcıya gönderilir
- **include_self=False**: Gönderen kendi mesajını tekrar almaz (client-side eklenir)

#### 📤 **Grup Mesajı** (`app.py:388-432`)
```python
@socketio.on('send_group_message')
def handle_send_group_message(data):
    group_id = data.get('group_id')
    
    # Grup üyeliği kontrolü
    if not db.is_group_member(group_id, current_user.id):
        emit('error', {'message': 'Bu grubun üyesi değilsiniz!'})
        return
    
    # Grubun tüm üyelerine gönder
    emit('new_group_message', {...}, room=f'group_{group_id}', include_self=False)
    
    # Veritabanına kaydet
    message_id = db.save_group_message(...)
```

**Bahsetmen Gerekenler:**
- **Grup Üyelik Kontrolü**: Mesaj göndermeden önce kullanıcının grup üyesi olup olmadığı kontrol edilir
- **Room-Based Delivery**: Grup mesajları `group_{group_id}` odasına gönderilir

### 4.3 Mesaj Geçmişi

#### 📜 **Mesaj Geçmişi Çekme** (`app.py:274-299`)
```python
@socketio.on('get_history')
def handle_get_history(data):
    other_user_id = data.get('other_user_id')  # NULL ise broadcast
    
    messages = db.get_message_history(current_user.id, other_user_id, limit)
    
    # Şifreli mesajları çöz
    for msg in messages:
        decrypted = session_manager.decrypt_from_storage(msg['encrypted_content'])
        decrypted_messages.append({...})
    
    emit('message_history', {'messages': decrypted_messages})
```

**Bahsetmen Gerekenler:**
- **Query Parametreleri**: `other_user_id` NULL ise broadcast, değilse direct mesaj geçmişi
- **Decryption**: Veritabanından çekilen şifreli mesajlar master key ile çözülür

---

## 5. ŞİFRELEME SİSTEMİ (2-3 sayfa)

### 5.1 Şifreleme Katmanları

#### 🔐 **İki Katmanlı Şifreleme** (`encryption.py`)

**1. Client-Server Şifreleme (E2E):**
```python
# Her WebSocket bağlantısı için benzersiz session key
session_key = session_manager.create_session_key(sid)  # 32 hex karakter

# Client mesajı session key ile şifreler
encrypted = Encryption.encrypt(message, session_key)
```

**2. Storage Şifreleme (Veritabanı):**
```python
# Sunucu mesajı master key ile tekrar şifreler
storage_encrypted = session_manager.encrypt_for_storage(encrypted_content)
# Veritabanına kaydedilir
```

**Bahsetmen Gerekenler:**
- **CustomCipher Sınıfı**: XOR + bit rotation tabanlı özel şifreleme algoritması
- **LCG (Linear Congruential Generator)**: Key stream üretimi için
- **Master Key**: Sunucu tarafında veritabanı şifrelemesi için (`MASTERKEY-SERVER-ONLY`)

### 5.2 Hash Mekanizması

#### 🔒 **SHA-256 Hash** (`database.py:171-172, 180`)
```python
def calculate_message_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

# Mesaj kaydedilirken
content_hash = calculate_message_hash(encrypted_content)
# Veritabanına kaydedilir
```

**Bahsetmen Gerekenler:**
- **Bütünlük Kontrolü**: Her mesaj için SHA-256 hash hesaplanır
- **Doğrulama Fonksiyonu**: `verify_message_integrity()` ile mesaj bütünlüğü kontrol edilebilir
- **Hash Kullanımı**: Veritabanında saklanan hash ile mesaj değişiklikleri tespit edilebilir

---

## 6. OFFLINE MESAJ DESTEĞİ (1-2 sayfa)

### 6.1 Offline Mesaj Sistemi

#### 📬 **Offline Mesaj Teslimi** (`app.py:483-506`)
```python
def deliver_offline_messages(user_id: int, sid: str):
    # Teslim edilmemiş mesajları getir
    undelivered = db.get_undelivered_messages(user_id)
    
    for msg in undelivered:
        # Mesajı çöz
        decrypted = session_manager.decrypt_from_storage(msg['encrypted_content'])
        
        # Kullanıcıya gönder
        socketio.emit('offline_message', {
            'sender_username': msg['sender_username'],
            'content': decrypted,
            'is_broadcast': msg['is_broadcast'],
            'created_at': msg['created_at']
        }, room=sid)
        
        # Teslim edildi olarak işaretle
        message_ids.append(msg['id'])
    
    db.mark_messages_delivered(message_ids)
```

**Bahsetmen Gerekenler:**
- **is_delivered Flag**: Mesaj gönderildiğinde alıcı online değilse `is_delivered=0` olarak kaydedilir
- **Otomatik Teslim**: Kullanıcı online olduğunda `handle_connect()` içinde otomatik çağrılır
- **Query**: `get_undelivered_messages()` fonksiyonu broadcast ve direct mesajları getirir

#### 📬 **Veritabanı Sorgusu** (`database.py:195-222`)
```sql
SELECT m.*, u.username as sender_username
FROM messages m
JOIN users u ON m.sender_id = u.id
WHERE (m.receiver_id = ? OR m.is_broadcast = 1) 
  AND m.is_delivered = 0
  AND m.sender_id != ?
ORDER BY m.created_at ASC
```

---

## 7. API ENDPOINT'LERİ (1-2 sayfa)

### 7.1 REST API'ler (`app.py:118-147`)

#### 👥 **Kullanıcı API'leri**
```python
GET /api/users              # Tüm kullanıcıları listele
GET /api/online-users       # Online kullanıcıları listele
```

#### 👥 **Grup API'leri**
```python
GET /api/groups                    # Kullanıcının gruplarını listele
GET /api/groups/<id>/members       # Grup üyelerini listele
```

**Bahsetmen Gerekenler:**
- **Authentication**: Tüm API'ler `@login_required` decorator'ı ile korunuyor
- **JSON Response**: `jsonify()` ile JSON formatında döner
- **Filtering**: `/api/users` endpoint'i kendi kullanıcısını filtreler

---

## 8. CLIENT-SIDE İMPLEMENTASYON (1-2 sayfa)

### 8.1 WebSocket Client (`static/js/app.js`)

#### 🔌 **Bağlantı Kurma**
```javascript
socket = io({
    transports: ['websocket', 'polling']
});

socket.on('connect', () => {
    console.log('✅ Socket connected');
    loadUsers();
    loadGroups();
});
```

#### 📤 **Mesaj Gönderme**
```javascript
function sendMessage(content) {
    const messageData = {
        encrypted_content: content,
        is_broadcast: currentTarget.type === 'broadcast',
        receiver_id: currentTarget.type === 'direct' ? currentTarget.id : null
    };
    
    socket.emit('send_message', messageData);
}
```

#### 📥 **Mesaj Alma**
```javascript
socket.on('new_message', (data) => {
    // Sadece aktif chat'te göster
    if (currentTarget && shouldShow) {
        UI.addMessage({
            sender_username: data.sender_username,
            content: data.encrypted_content,
            is_broadcast: data.is_broadcast
        });
    }
});
```

**Bahsetmen Gerekenler:**
- **Event-Driven**: Her mesaj tipi için ayrı event listener
- **Real-time Updates**: Kullanıcı online/offline durumları anlık güncellenir
- **UI State Management**: `currentTarget` ile aktif chat takibi

---

## 9. GÜVENLİK ÖZELLİKLERİ (1-2 sayfa)

### 9.1 Kimlik Doğrulama
- **Flask-Login**: Session-based authentication
- **Password Hashing**: PBKDF2-SHA256 + salt (`werkzeug.security`)

### 9.2 Şifreleme
- **E2E Encryption**: Client-server arası session key ile
- **Storage Encryption**: Veritabanında master key ile
- **Hash Verification**: SHA-256 ile mesaj bütünlüğü

### 9.3 Yetkilendirme
- **Group Membership Check**: Grup mesajı göndermeden önce kontrol
- **Room-Based Access**: Sadece üye olduğu odalara mesaj gönderilebilir

---

## 10. TEST SENARYOLARI (1 sayfa)

### 10.1 Test Edilmesi Gerekenler
1. ✅ **Broadcast Mesaj**: Tüm online kullanıcılara mesaj gönderme
2. ✅ **Direct Mesaj**: Tek kullanıcıya mesaj gönderme
3. ✅ **Grup Mesajı**: Grup üyelerine mesaj gönderme
4. ✅ **Offline Mesaj**: Offline kullanıcıya mesaj gönderme ve online olduğunda teslim
5. ✅ **Hash Doğrulama**: Mesaj hash'lerinin doğru hesaplandığı
6. ✅ **Şifreleme**: Mesajların veritabanında şifreli saklandığı

---

## 11. SONUÇ (0.5-1 sayfa)

### 11.1 Başarılan Özellikler
- ✅ 3 tip mesajlaşma (broadcast, direct, group)
- ✅ WebSocket ile gerçek zamanlı iletişim
- ✅ E2E şifreleme
- ✅ SHA-256 hash ile mesaj bütünlüğü
- ✅ Offline mesaj desteği

### 11.2 Teknik Detaylar
- **Protocol**: WebSocket (TCP tabanlı)
- **Database**: SQLite (4 tablo)
- **Encryption**: Custom cipher + SHA-256
- **Architecture**: Event-driven, room-based messaging

---

## 📊 TABLO ÖZETLERİ

### Tablo 1: WebSocket Event'leri
| Event | Açıklama | Dosya:Satır |
|-------|----------|-------------|
| `connect` | Bağlantı kurulduğunda | app.py:152 |
| `disconnect` | Bağlantı koptuğunda | app.py:187 |
| `send_message` | Direct/Broadcast mesaj | app.py:215 |
| `send_group_message` | Grup mesajı | app.py:388 |
| `get_history` | Mesaj geçmişi | app.py:274 |
| `get_group_history` | Grup mesaj geçmişi | app.py:435 |
| `create_group` | Grup oluşturma | app.py:342 |
| `typing` | Yazıyor göstergesi | app.py:302 |

### Tablo 2: Veritabanı Fonksiyonları
| Fonksiyon | Açıklama | Dosya:Satır |
|-----------|----------|-------------|
| `save_message()` | Mesaj kaydetme + hash | database.py:175 |
| `get_undelivered_messages()` | Offline mesajlar | database.py:195 |
| `get_message_history()` | Mesaj geçmişi | database.py:243 |
| `save_group_message()` | Grup mesajı kaydetme | database.py:450 |
| `calculate_message_hash()` | SHA-256 hash | database.py:171 |

### Tablo 3: Şifreleme Fonksiyonları
| Fonksiyon | Açıklama | Dosya:Satır |
|-----------|----------|-------------|
| `create_session_key()` | Session key oluştur | encryption.py:68 |
| `encrypt_for_storage()` | Veritabanı şifreleme | encryption.py:85 |
| `decrypt_from_storage()` | Veritabanı çözme | encryption.py:89 |
| `CustomCipher.encrypt()` | Mesaj şifreleme | encryption.py:31 |
| `CustomCipher.decrypt()` | Mesaj çözme | encryption.py:45 |

---

## 💡 RAPORDA VURGULAMAN GEREKEN NOKTALAR

1. **WebSocket = TCP Tabanlı**: WebSocket protokolü TCP üzerinde çalışır, bu yüzden ödev gereksinimini karşılar
2. **3 Tip Mesajlaşma**: Her biri için ayrı room ve event handler
3. **Hash Mekanizması**: Her mesaj için SHA-256 hash hesaplanıyor ve veritabanına kaydediliyor
4. **Offline Mesaj**: `is_delivered` flag'i ile takip ediliyor ve kullanıcı online olduğunda otomatik teslim ediliyor
5. **E2E Şifreleme**: Client-server arası session key ile şifreleme
6. **Veritabanı Şifreleme**: Master key ile ikinci katman şifreleme

---

## 📝 ÖRNEK RAPOR BÖLÜMLERİ

### Örnek 1: Mesaj Gönderme Akışı
```
1. Client: socket.emit('send_message', {encrypted_content, is_broadcast, receiver_id})
2. Server: handle_send_message() fonksiyonu çalışır
3. Server: Mesajı master key ile tekrar şifreler (storage için)
4. Server: SHA-256 hash hesaplanır
5. Server: Veritabanına kaydedilir (save_message())
6. Server: Alıcı online ise room'a emit edilir
7. Server: Alıcı offline ise is_delivered=0 olarak kaydedilir
8. Client: new_message event'i ile mesaj alınır
```

### Örnek 2: Offline Mesaj Teslimi
```
1. Kullanıcı offline iken mesaj gönderilir
2. Mesaj veritabanına is_delivered=0 ile kaydedilir
3. Kullanıcı online olduğunda handle_connect() çalışır
4. deliver_offline_messages() fonksiyonu çağrılır
5. get_undelivered_messages() ile teslim edilmemiş mesajlar getirilir
6. Her mesaj decrypt edilir ve kullanıcıya gönderilir
7. mark_messages_delivered() ile is_delivered=1 yapılır
```

---

## ✅ KONTROL LİSTESİ

Raporunda şunlar olmalı:
- [ ] WebSocket protokolünün TCP tabanlı olduğu belirtilmeli
- [ ] 3 tip mesajlaşma (broadcast, direct, group) açıklanmalı
- [ ] Her mesaj tipi için kod örnekleri verilmeli
- [ ] SHA-256 hash mekanizması açıklanmalı
- [ ] Offline mesaj sistemi detaylı anlatılmalı
- [ ] Şifreleme katmanları (E2E + storage) açıklanmalı
- [ ] Veritabanı tabloları ve ilişkileri gösterilmeli
- [ ] API endpoint'leri listelenmeli
- [ ] Test senaryoları belirtilmeli

---

**İyi çalışmalar! 🚀**

