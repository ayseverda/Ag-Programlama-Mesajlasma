"""
Secure Web Messaging Agent - Main Application
Flask + WebSocket server with E2E encryption support
"""

import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

import database as db
from encryption import session_manager, EncryptionManager

# Flask Application Setup
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'SecureMessaging2024!SuperSecretKey')

# Initialize SocketIO with eventlet for better async support
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Flask-Login Setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Store active connections: {user_id: [sid1, sid2, ...]}
active_connections = {}
# Store user session keys: {sid: encryption_key}
user_session_keys = {}


class User(UserMixin):
    """User model for Flask-Login"""
    def __init__(self, user_id, username):
        self.id = user_id
        self.username = username


@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login"""
    user_data = db.get_user_by_id(int(user_id))
    if user_data:
        return User(user_data['id'], user_data['username'])
    return None


# ============== HTTP ROUTES ==============

@app.route('/')
def index():
    """Redirect to chat if logged in, otherwise to login"""
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler"""
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            return render_template('login.html', error='Kullanıcı adı ve şifre gereklidir!')
        
        result = db.authenticate_user(username, password)
        
        if result['success']:
            user = User(result['user_id'], result['username'])
            login_user(user)
            db.set_user_online(result['user_id'], True)
            return redirect(url_for('chat'))
        else:
            return render_template('login.html', error=result['error'])
    
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page and handler"""
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not username or not password:
            return render_template('register.html', error='Tüm alanlar gereklidir!')
        
        if len(username) < 3:
            return render_template('register.html', error='Kullanıcı adı en az 3 karakter olmalıdır!')
        
        if len(password) < 6:
            return render_template('register.html', error='Şifre en az 6 karakter olmalıdır!')
        
        if password != confirm_password:
            return render_template('register.html', error='Şifreler eşleşmiyor!')
        
        result = db.create_user(username, password)
        
        if result['success']:
            user = User(result['user_id'], result['username'])
            login_user(user)
            db.set_user_online(result['user_id'], True)
            return redirect(url_for('chat'))
        else:
            return render_template('register.html', error=result['error'])
    
    return render_template('register.html')


@app.route('/chat')
@login_required
def chat():
    """Main chat page"""
    return render_template('chat.html', username=current_user.username, user_id=current_user.id)


@app.route('/logout')
@login_required
def logout():
    """Logout handler"""
    db.set_user_online(current_user.id, False)
    logout_user()
    return redirect(url_for('login'))


@app.route('/api/users')
@login_required
def get_users():
    """API endpoint to get all users"""
    users = db.get_all_users()
    # Filter out current user
    users = [u for u in users if u['id'] != current_user.id]
    return jsonify(users)


@app.route('/api/online-users')
@login_required
def get_online_users():
    """API endpoint to get online users"""
    users = db.get_online_users()
    # Filter out current user
    users = [u for u in users if u['id'] != current_user.id]
    return jsonify(users)


@app.route('/api/groups')
@login_required
def get_groups():
    """API endpoint to get user's groups"""
    groups = db.get_user_groups(current_user.id)
    return jsonify(groups)


@app.route('/api/groups/<int:group_id>/members')
@login_required
def get_group_members(group_id):
    """API endpoint to get group members"""
    if not db.is_group_member(group_id, current_user.id):
        return jsonify({"error": "Not a member of this group"}), 403
    members = db.get_group_members(group_id)
    return jsonify(members)


# ============== WEBSOCKET EVENTS ==============

@socketio.on('connect')
def handle_connect():
    """Handle new WebSocket connection"""
    if current_user.is_authenticated:
        user_id = current_user.id
        sid = request.sid
        
        # Add connection to active connections
        if user_id not in active_connections:
            active_connections[user_id] = []
        active_connections[user_id].append(sid)
        
        # Generate session encryption key for this connection
        session_key = session_manager.create_session_key(sid)
        user_session_keys[sid] = session_key
        
        # Join user's private room
        join_room(f'user_{user_id}')
        join_room('broadcast')  # Join broadcast room
        
        # Join all group rooms
        user_groups = db.get_user_groups(user_id)
        for group in user_groups:
            join_room(f'group_{group["id"]}')
        
        # Update online status
        db.set_user_online(user_id, True)
        
        # Emit session key to client
        emit('session_key', {'key': session_key})
        
        # Notify others about online status
        emit('user_online', {
            'user_id': user_id,
            'username': current_user.username
        }, room='broadcast', include_self=False)
        
        # Deliver any undelivered messages
        deliver_offline_messages(user_id, sid)
        
        print(f"✅ User {current_user.username} connected (sid: {sid})")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    if current_user.is_authenticated:
        user_id = current_user.id
        sid = request.sid
        
        # Remove connection
        if user_id in active_connections:
            if sid in active_connections[user_id]:
                active_connections[user_id].remove(sid)
            
            # If no more connections, set user offline
            if not active_connections[user_id]:
                del active_connections[user_id]
                db.set_user_online(user_id, False)
                
                # Notify others
                emit('user_offline', {
                    'user_id': user_id,
                    'username': current_user.username
                }, room='broadcast', include_self=False)
        
        # Clean up session key
        if sid in user_session_keys:
            session_manager.remove_session(sid)
            del user_session_keys[sid]
        
        print(f"❌ User {current_user.username} disconnected (sid: {sid})")


@socketio.on('send_message')
def handle_send_message(data):
    """Handle sending a message"""
    if not current_user.is_authenticated:
        return
    
    sender_id = current_user.id
    receiver_id = data.get('receiver_id')
    encrypted_content = data.get('encrypted_content')
    is_broadcast = data.get('is_broadcast', False)
    
    if not encrypted_content:
        emit('error', {'message': 'Mesaj içeriği boş olamaz!'})
        return
    
    # For storage, we re-encrypt with master key
    storage_encrypted = session_manager.encrypt_for_storage(encrypted_content)
    
    # Check if receiver is online for direct delivery
    is_delivered = False
    
    if is_broadcast:
        # Broadcast message to all online users
        receiver_id = None
        is_delivered = len(active_connections) > 1  # At least one other user
        
        emit('new_message', {
            'sender_id': sender_id,
            'sender_username': current_user.username,
            'encrypted_content': encrypted_content,
            'is_broadcast': True,
            'timestamp': datetime.now().isoformat()
        }, room='broadcast', include_self=False)
        
    else:
        # Direct message to specific user
        if receiver_id and receiver_id in active_connections:
            is_delivered = True
            emit('new_message', {
                'sender_id': sender_id,
                'sender_username': current_user.username,
                'encrypted_content': encrypted_content,
                'is_broadcast': False,
                'timestamp': datetime.now().isoformat()
            }, room=f'user_{receiver_id}')
    
    # Save message to database
    message_id = db.save_message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        encrypted_content=storage_encrypted,
        is_broadcast=is_broadcast,
        is_delivered=is_delivered
    )
    
    # Confirm to sender
    emit('message_sent', {
        'message_id': message_id,
        'receiver_id': receiver_id,
        'is_delivered': is_delivered
    })
    
    print(f"📤 Message from {current_user.username} -> {'broadcast' if is_broadcast else receiver_id}")


@socketio.on('get_history')
def handle_get_history(data):
    """Get message history"""
    if not current_user.is_authenticated:
        return
    
    other_user_id = data.get('other_user_id')
    limit = data.get('limit', 50)
    
    messages = db.get_message_history(current_user.id, other_user_id, limit)
    
    # Decrypt messages for client
    decrypted_messages = []
    for msg in messages:
        try:
            decrypted_content = session_manager.decrypt_from_storage(msg['encrypted_content'])
            decrypted_messages.append({
                'id': msg['id'],
                'sender_id': msg['sender_id'],
                'sender_username': msg['sender_username'],
                'content': decrypted_content,
                'is_broadcast': msg['is_broadcast'],
                'created_at': msg['created_at']
            })
        except Exception as e:
            print(f"Error decrypting message {msg['id']}: {e}")
    
    emit('message_history', {'messages': decrypted_messages})


@socketio.on('typing')
def handle_typing(data):
    """Handle typing indicator"""
    if not current_user.is_authenticated:
        return
    
    receiver_id = data.get('receiver_id')
    is_broadcast = data.get('is_broadcast', False)
    
    typing_data = {
        'user_id': current_user.id,
        'username': current_user.username
    }
    
    if is_broadcast:
        emit('user_typing', typing_data, room='broadcast', include_self=False)
    elif receiver_id:
        emit('user_typing', typing_data, room=f'user_{receiver_id}')


@socketio.on('stop_typing')
def handle_stop_typing(data):
    """Handle stop typing indicator"""
    if not current_user.is_authenticated:
        return
    
    receiver_id = data.get('receiver_id')
    is_broadcast = data.get('is_broadcast', False)
    
    typing_data = {
        'user_id': current_user.id,
        'username': current_user.username
    }
    
    if is_broadcast:
        emit('user_stop_typing', typing_data, room='broadcast', include_self=False)
    elif receiver_id:
        emit('user_stop_typing', typing_data, room=f'user_{receiver_id}')


# ============== GROUP WEBSOCKET EVENTS ==============

@socketio.on('create_group')
def handle_create_group(data):
    """Handle group creation"""
    if not current_user.is_authenticated:
        return
    
    name = data.get('name', '').strip()
    member_ids = data.get('member_ids', [])
    
    if not name:
        emit('error', {'message': 'Grup adı gereklidir!'})
        return
    
    if len(name) < 2:
        emit('error', {'message': 'Grup adı en az 2 karakter olmalıdır!'})
        return
    
    # Create the group
    result = db.create_group(name, current_user.id, member_ids)
    
    if result['success']:
        group_id = result['group_id']
        
        # Join creator to group room
        join_room(f'group_{group_id}')
        
        # Notify creator
        emit('group_created', {
            'group_id': group_id,
            'name': name,
            'member_count': len(member_ids) + 1
        })
        
        # Notify members who are online
        for member_id in member_ids:
            if member_id in active_connections:
                # Make member join the group room
                for sid in active_connections[member_id]:
                    socketio.server.enter_room(sid, f'group_{group_id}')
                
                emit('added_to_group', {
                    'group_id': group_id,
                    'name': name,
                    'added_by': current_user.username
                }, room=f'user_{member_id}')
        
        print(f"👥 Group '{name}' created by {current_user.username}")
    else:
        emit('error', {'message': result['error']})


@socketio.on('send_group_message')
def handle_send_group_message(data):
    """Handle sending a message to a group"""
    if not current_user.is_authenticated:
        return
    
    group_id = data.get('group_id')
    encrypted_content = data.get('encrypted_content')
    
    if not group_id or not encrypted_content:
        emit('error', {'message': 'Grup ID ve mesaj içeriği gereklidir!'})
        return
    
    # Check if user is a member of the group
    if not db.is_group_member(group_id, current_user.id):
        emit('error', {'message': 'Bu grubun üyesi değilsiniz!'})
        return
    
    # Get group info
    group = db.get_group_by_id(group_id)
    if not group:
        emit('error', {'message': 'Grup bulunamadı!'})
        return
    
    # Encrypt for storage
    storage_encrypted = session_manager.encrypt_for_storage(encrypted_content)
    
    # Save message to database
    message_id = db.save_group_message(
        sender_id=current_user.id,
        group_id=group_id,
        encrypted_content=storage_encrypted
    )
    
    # Send to all group members (except sender)
    emit('new_group_message', {
        'message_id': message_id,
        'group_id': group_id,
        'group_name': group['name'],
        'sender_id': current_user.id,
        'sender_username': current_user.username,
        'encrypted_content': encrypted_content,
        'timestamp': datetime.now().isoformat()
    }, room=f'group_{group_id}', include_self=False)
    
    # Confirm to sender
    emit('group_message_sent', {
        'message_id': message_id,
        'group_id': group_id
    })
    
    print(f"📤 Group message from {current_user.username} -> group {group_id}")


@socketio.on('get_group_history')
def handle_get_group_history(data):
    """Get message history for a group"""
    if not current_user.is_authenticated:
        return
    
    group_id = data.get('group_id')
    limit = data.get('limit', 50)
    
    if not group_id:
        return
    
    # Check if user is a member
    if not db.is_group_member(group_id, current_user.id):
        emit('error', {'message': 'Bu grubun üyesi değilsiniz!'})
        return
    
    messages = db.get_group_message_history(group_id, limit)
    
    # Decrypt messages for client
    decrypted_messages = []
    for msg in messages:
        try:
            decrypted_content = session_manager.decrypt_from_storage(msg['encrypted_content'])
            decrypted_messages.append({
                'id': msg['id'],
                'sender_id': msg['sender_id'],
                'sender_username': msg['sender_username'],
                'group_id': msg['group_id'],
                'content': decrypted_content,
                'created_at': msg['created_at']
            })
        except Exception as e:
            print(f"Error decrypting group message {msg['id']}: {e}")
    
    emit('group_message_history', {
        'group_id': group_id,
        'messages': decrypted_messages
    })


@socketio.on('join_group_rooms')
def handle_join_group_rooms():
    """Join all group rooms for the current user"""
    if not current_user.is_authenticated:
        return
    
    groups = db.get_user_groups(current_user.id)
    for group in groups:
        join_room(f'group_{group["id"]}')


def deliver_offline_messages(user_id: int, sid: str):
    """Deliver undelivered messages to a user who just came online"""
    undelivered = db.get_undelivered_messages(user_id)
    
    if undelivered:
        print(f"📨 Delivering {len(undelivered)} offline messages to user {user_id}")
        
        message_ids = []
        for msg in undelivered:
            try:
                # Decrypt from storage and send to client
                decrypted = session_manager.decrypt_from_storage(msg['encrypted_content'])
                
                socketio.emit('offline_message', {
                    'sender_id': msg['sender_id'],
                    'sender_username': msg['sender_username'],
                    'content': decrypted,
                    'is_broadcast': msg['is_broadcast'],
                    'created_at': msg['created_at']
                }, room=sid)
                
                message_ids.append(msg['id'])
            except Exception as e:
                print(f"Error delivering message {msg['id']}: {e}")
        
        # Mark messages as delivered
        db.mark_messages_delivered(message_ids)


# ============== MAIN ==============

if __name__ == '__main__':
    # Initialize database
    db.init_db()
    
    print("=" * 50)
    print("🔐 Secure Web Messaging Agent")
    print("=" * 50)
    print("🚀 Starting server on http://127.0.0.1:5000")
    print("=" * 50)
    
    # Run with eventlet for WebSocket support
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

