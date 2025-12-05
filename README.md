# 🔐 Secure Web Messaging Agent

Güvenli, gerçek zamanlı mesajlaşma uygulaması. Python (Flask + WebSocket), SQLite veritabanı ve HTML/CSS/JavaScript web istemcisi ile geliştirilmiştir.

## ✨ Özellikler

### 🔑 Kimlik Doğrulama
- Kullanıcı kaydı ve giriş sistemi
- Güvenli şifre hash'leme (Werkzeug)
- Oturum yönetimi (Flask-Login)

### 📡 Gerçek Zamanlı Mesajlaşma
- WebSocket tabanlı anlık iletişim
- Doğrudan mesajlaşma (1-1)
- Broadcast mesajları (tüm kullanıcılara)
- Yazıyor göstergesi

### 🔒 Güvenlik
- AES-256 şifreleme (E2E Encryption)
- SHA-256 mesaj bütünlük kontrolü
- Tüm mesajlar veritabanında şifreli saklanır

### 💾 Veri Yönetimi
- SQLite veritabanı
- Çevrimdışı mesaj teslimi
- Mesaj geçmişi

### 👥 Kullanıcı Durumu
- Çevrimiçi/çevrimdışı takibi
- Gerçek zamanlı durum güncellemeleri

## 🛠️ Kurulum

### 1. Gereksinimleri Yükleyin

```bash
pip install -r requirements.txt
```

### 2. Uygulamayı Başlatın

```bash
python app.py
```

### 3. Tarayıcıda Açın

```
http://127.0.0.1:5000
```

## 📁 Proje Yapısı

```
├── app.py              # Ana Flask sunucusu
├── database.py         # SQLite veritabanı işlemleri
├── encryption.py       # E2E şifreleme modülü
├── requirements.txt    # Python bağımlılıkları
├── messaging.db        # SQLite veritabanı (otomatik oluşur)
├── static/
│   ├── css/
│   │   └── style.css   # Cyberpunk temalı stiller
│   └── js/
│       └── app.js      # Frontend JavaScript
└── templates/
    ├── login.html      # Giriş sayfası
    ├── register.html   # Kayıt sayfası
    └── chat.html       # Ana sohbet sayfası
```

## 🎯 Kullanım

1. **Kayıt Ol**: Yeni hesap oluşturun
2. **Giriş Yap**: Kullanıcı adı ve şifrenizle giriş yapın
3. **Broadcast**: Sol menüden "Broadcast" seçerek tüm kullanıcılara mesaj gönderin
4. **Doğrudan Mesaj**: Kullanıcı listesinden bir kişi seçerek özel mesaj gönderin
5. **Çevrimdışı Mesajlar**: Giriş yaptığınızda, çevrimdışıyken gelen mesajlar otomatik teslim edilir

## 🔐 Güvenlik Detayları

### Şifreleme
- **AES-256-CBC**: Mesaj şifreleme
- **SHA-256**: Mesaj bütünlük hash'i
- **PBKDF2**: Şifre hash'leme

### Veri Güvenliği
- Tüm mesajlar veritabanında şifreli saklanır
- Her mesajın SHA-256 hash'i kaydedilir
- Şifreler salt'lı hash olarak saklanır

## 📊 Veritabanı Şeması

### Users Tablosu
| Alan | Tip | Açıklama |
|------|-----|----------|
| id | INTEGER | Birincil anahtar |
| username | TEXT | Benzersiz kullanıcı adı |
| password_hash | TEXT | Hash'lenmiş şifre |
| is_online | INTEGER | Çevrimiçi durumu |
| last_seen | TIMESTAMP | Son görülme |

### Messages Tablosu
| Alan | Tip | Açıklama |
|------|-----|----------|
| id | INTEGER | Birincil anahtar |
| sender_id | INTEGER | Gönderen ID |
| receiver_id | INTEGER | Alıcı ID (null = broadcast) |
| encrypted_content | TEXT | Şifreli mesaj |
| content_hash | TEXT | SHA-256 hash |
| is_broadcast | INTEGER | Broadcast bayrağı |
| is_delivered | INTEGER | Teslim durumu |

## 🎨 Arayüz

- **Tema**: Cyberpunk / Neon
- **Renkler**: Cyan, Magenta, Deep Space
- **Animasyonlar**: CSS tabanlı efektler
- **Responsive**: Mobil uyumlu tasarım

## 📝 Notlar

- Uygulama varsayılan olarak `5000` portunda çalışır
- İlk çalıştırmada veritabanı otomatik oluşturulur
- Birden fazla tarayıcı sekmesi/penceresi ile test edebilirsiniz

## 🚀 Geliştirme

```bash
# Debug modunda çalıştır
python app.py

# Veritabanını sıfırla
rm messaging.db && python app.py
```

---

**🔐 Secure Web Messaging Agent** - Tüm mesajlarınız uçtan uca şifrelidir.

