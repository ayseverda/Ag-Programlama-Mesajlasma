/**
 * Secure Web Messaging Agent - Frontend Application
 * Handles WebSocket communication, E2E encryption, and UI interactions
 */

// ============== GLOBAL STATE ==============
let socket = null;
let sessionKey = null;
let currentTarget = {
    type: 'broadcast',
    id: null,
    name: 'Broadcast',
    username: null
};
let typingTimeout = null;
let users = [];
let groups = [];

// ============== ENCRYPTION UTILITIES ==============
const Encryption = {
    /**
     * Encrypt message using AES with session key
     */
    encrypt(message, key) {
        try {
            // Generate random IV
            const iv = CryptoJS.lib.WordArray.random(16);
            const encrypted = CryptoJS.AES.encrypt(message, CryptoJS.enc.Base64.parse(key), {
                iv: iv,
                mode: CryptoJS.mode.CBC,
                padding: CryptoJS.pad.Pkcs7
            });
            // Combine IV + ciphertext and encode as base64
            const combined = iv.concat(encrypted.ciphertext);
            return CryptoJS.enc.Base64.stringify(combined);
        } catch (error) {
            console.error('Encryption error:', error);
            return null;
        }
    },

    /**
     * Decrypt message using AES with session key
     */
    decrypt(encryptedMessage, key) {
        try {
            // Decode base64
            const combined = CryptoJS.enc.Base64.parse(encryptedMessage);
            // Extract IV (first 16 bytes = 4 words)
            const iv = CryptoJS.lib.WordArray.create(combined.words.slice(0, 4), 16);
            // Extract ciphertext
            const ciphertext = CryptoJS.lib.WordArray.create(
                combined.words.slice(4),
                combined.sigBytes - 16
            );
            
            const decrypted = CryptoJS.AES.decrypt(
                { ciphertext: ciphertext },
                CryptoJS.enc.Base64.parse(key),
                {
                    iv: iv,
                    mode: CryptoJS.mode.CBC,
                    padding: CryptoJS.pad.Pkcs7
                }
            );
            return decrypted.toString(CryptoJS.enc.Utf8);
        } catch (error) {
            console.error('Decryption error:', error);
            return '[Şifre çözülemedi]';
        }
    },

    /**
     * Calculate SHA-256 hash of message
     */
    hash(message) {
        return CryptoJS.SHA256(message).toString();
    }
};

// ============== UI UTILITIES ==============
const UI = {
    /**
     * Show toast notification
     */
    showToast(message, type = 'info', duration = 4000) {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icons = {
            success: '✓',
            error: '✕',
            info: 'ℹ',
            warning: '⚠'
        };
        
        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || icons.info}</span>
            <span class="toast-message">${message}</span>
            <button class="toast-close">×</button>
        `;
        
        container.appendChild(toast);
        
        // Close button handler
        toast.querySelector('.toast-close').addEventListener('click', () => {
            toast.style.animation = 'toastOut 0.3s ease-out forwards';
            setTimeout(() => toast.remove(), 300);
        });
        
        // Auto remove
        setTimeout(() => {
            if (toast.parentElement) {
                toast.style.animation = 'toastOut 0.3s ease-out forwards';
                setTimeout(() => toast.remove(), 300);
            }
        }, duration);
    },

    /**
     * Update connection status indicator
     */
    updateConnectionStatus(status) {
        const statusEl = document.getElementById('connection-status');
        const statusText = statusEl.querySelector('.status-text');
        
        statusEl.classList.remove('connected', 'disconnected');
        
        switch (status) {
            case 'connected':
                statusEl.classList.add('connected');
                statusText.textContent = 'Bağlı';
                break;
            case 'disconnected':
                statusEl.classList.add('disconnected');
                statusText.textContent = 'Bağlantı Kesildi';
                break;
            default:
                statusText.textContent = 'Bağlanıyor...';
        }
    },

    /**
     * Add message to chat
     */
    addMessage(data, isSent = false) {
        const messagesContainer = document.getElementById('messages-list');
        const welcomeMsg = messagesContainer.querySelector('.welcome-message');
        if (welcomeMsg) welcomeMsg.remove();
        
        const message = document.createElement('div');
        message.className = `message ${isSent ? 'sent' : 'received'}`;
        
        const senderName = isSent ? currentUser.username : (data.sender_username || 'Anonim');
        const initial = senderName.charAt(0).toUpperCase();
        const time = data.timestamp ? new Date(data.timestamp).toLocaleTimeString('tr-TR', { 
            hour: '2-digit', 
            minute: '2-digit' 
        }) : new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
        
        const broadcastBadge = data.is_broadcast ? '<span class="broadcast-badge">Broadcast</span>' : '';
        
        message.innerHTML = `
            <div class="message-avatar">${initial}</div>
            <div class="message-content">
                <div class="message-header">
                    <span class="message-sender">${senderName}</span>
                    <span class="message-time">${time}</span>
                    ${broadcastBadge}
                </div>
                <div class="message-bubble">
                    ${this.escapeHtml(data.content)}
                </div>
            </div>
        `;
        
        messagesContainer.appendChild(message);
        this.scrollToBottom();
    },

    /**
     * Scroll messages to bottom
     */
    scrollToBottom() {
        const container = document.getElementById('messages-container');
        container.scrollTop = container.scrollHeight;
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * Update users list in sidebar
     */
    updateUsersList(usersList) {
        const container = document.getElementById('users-list');
        container.innerHTML = '';
        
        if (usersList.length === 0) {
            container.innerHTML = `
                <div class="no-users">
                    <span style="color: var(--text-muted); font-size: 0.85rem;">
                        Başka kullanıcı yok
                    </span>
                </div>
            `;
            return;
        }
        
        usersList.forEach(user => {
            const userEl = document.createElement('div');
            userEl.className = 'user-item';
            userEl.dataset.userId = user.id;
            userEl.dataset.username = user.username;
            
            const initial = user.username.charAt(0).toUpperCase();
            const statusClass = user.is_online ? 'online' : '';
            const statusText = user.is_online ? 'Çevrimiçi' : 'Çevrimdışı';
            
            userEl.innerHTML = `
                <div class="user-avatar">
                    ${initial}
                    <span class="status-dot ${statusClass}"></span>
                </div>
                <div class="user-details">
                    <span class="name">${UI.escapeHtml(user.username)}</span>
                    <span class="user-status ${statusClass}">${statusText}</span>
                </div>
            `;
            
            userEl.addEventListener('click', () => selectUser(user));
            container.appendChild(userEl);
        });
    },

    /**
     * Update chat header for selected target
     */
    updateChatHeader() {
        const icon = document.getElementById('target-icon');
        const name = document.getElementById('target-name');
        const status = document.getElementById('target-status');
        
        if (currentTarget.type === 'broadcast') {
            icon.textContent = '🌐';
            name.textContent = 'Broadcast';
            status.textContent = 'Tüm kullanıcılara mesaj gönder';
        } else if (currentTarget.type === 'group') {
            const group = groups.find(g => g.id === currentTarget.id);
            icon.textContent = '👥';
            name.textContent = currentTarget.name;
            status.textContent = `${group?.member_count || '?'} üye`;
        } else {
            const user = users.find(u => u.id === currentTarget.id);
            icon.textContent = currentTarget.name.charAt(0).toUpperCase();
            name.textContent = currentTarget.name;
            status.textContent = user?.is_online ? 'Çevrimiçi' : 'Çevrimdışı';
        }
    },

    /**
     * Show/hide typing indicator
     */
    showTyping(username, show = true) {
        const indicator = document.getElementById('typing-indicator');
        const text = document.getElementById('typing-text');
        
        if (show) {
            text.textContent = `${username} yazıyor...`;
            indicator.style.display = 'flex';
        } else {
            indicator.style.display = 'none';
        }
    },

    /**
     * Clear messages
     */
    clearMessages() {
        const container = document.getElementById('messages-list');
        container.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">💬</div>
                <h2>Yeni Sohbet</h2>
                <p>Mesaj göndermek için yazın</p>
            </div>
        `;
    },

    /**
     * Update groups list in sidebar
     */
    updateGroupsList(groupsList) {
        const container = document.getElementById('groups-list');
        container.innerHTML = '';
        
        if (groupsList.length === 0) {
            container.innerHTML = `
                <div class="no-groups" style="color: var(--text-muted); font-size: 0.85rem; padding: 10px;">
                    Henüz grup yok
                </div>
            `;
            return;
        }
        
        groupsList.forEach(group => {
            const groupEl = document.createElement('div');
            groupEl.className = 'group-item';
            groupEl.dataset.groupId = group.id;
            
            groupEl.innerHTML = `
                <div class="group-avatar">👥</div>
                <div class="group-details">
                    <span class="name">${UI.escapeHtml(group.name)}</span>
                    <span class="member-count">${group.member_count} üye</span>
                </div>
            `;
            
            groupEl.addEventListener('click', () => selectGroup(group));
            container.appendChild(groupEl);
        });
    },

    /**
     * Show/hide modal
     */
    showModal(show = true) {
        const modal = document.getElementById('create-group-modal');
        if (show) {
            modal.classList.add('active');
        } else {
            modal.classList.remove('active');
        }
        
        if (show) {
            // Populate member selection with users
            const memberSelection = document.getElementById('member-selection');
            if (users.length === 0) {
                memberSelection.innerHTML = '<div class="no-members-msg">Eklenecek kullanıcı yok</div>';
            } else {
                memberSelection.innerHTML = users.map(user => `
                    <label class="member-checkbox">
                        <input type="checkbox" value="${user.id}" data-username="${user.username}">
                        <span class="checkmark"></span>
                        <div class="member-info">
                            <div class="member-avatar">${user.username.charAt(0).toUpperCase()}</div>
                            <span class="member-name">${UI.escapeHtml(user.username)}</span>
                        </div>
                    </label>
                `).join('');
            }
            document.getElementById('group-name').value = '';
            document.getElementById('group-name').focus();
        }
    },

    /**
     * Add group message to chat
     */
    addGroupMessage(data, isSent = false) {
        const messagesContainer = document.getElementById('messages-list');
        const welcomeMsg = messagesContainer.querySelector('.welcome-message');
        if (welcomeMsg) welcomeMsg.remove();
        
        const message = document.createElement('div');
        message.className = `message ${isSent ? 'sent' : 'received'}`;
        
        const senderName = isSent ? currentUser.username : (data.sender_username || 'Anonim');
        const initial = senderName.charAt(0).toUpperCase();
        const time = data.timestamp ? new Date(data.timestamp).toLocaleTimeString('tr-TR', { 
            hour: '2-digit', 
            minute: '2-digit' 
        }) : new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
        
        message.innerHTML = `
            <div class="message-avatar">${initial}</div>
            <div class="message-content">
                <div class="message-header">
                    <span class="message-sender">${senderName}</span>
                    <span class="message-time">${time}</span>
                    <span class="group-badge">${data.group_name || 'Grup'}</span>
                </div>
                <div class="message-bubble">
                    ${this.escapeHtml(data.content)}
                </div>
            </div>
        `;
        
        messagesContainer.appendChild(message);
        this.scrollToBottom();
    }
};

// ============== SOCKET HANDLERS ==============
function initSocket() {
    socket = io({
        transports: ['websocket', 'polling']
    });

    // Connection events
    socket.on('connect', () => {
        console.log('✅ Socket connected');
        UI.updateConnectionStatus('connected');
        UI.showToast('Sunucuya bağlandı', 'success');
        loadUsers();
        loadGroups();
    });

    socket.on('disconnect', () => {
        console.log('❌ Socket disconnected');
        UI.updateConnectionStatus('disconnected');
        UI.showToast('Bağlantı kesildi', 'error');
    });

    socket.on('connect_error', (error) => {
        console.error('Connection error:', error);
        UI.updateConnectionStatus('disconnected');
    });

    // Session key from server
    socket.on('session_key', (data) => {
        sessionKey = data.key;
        console.log('🔐 Session key received');
    });

    // New message received
    socket.on('new_message', (data) => {
        console.log('📨 New message:', data);
        
        const content = data.encrypted_content;
        
        // Only show message if we're in the correct channel
        const shouldShow = (data.is_broadcast && currentTarget.type === 'broadcast') ||
                          (!data.is_broadcast && currentTarget.type === 'direct' && 
                           currentTarget.id === data.sender_id);
        
        if (shouldShow) {
            UI.addMessage({
                sender_username: data.sender_username,
                content: content,
                is_broadcast: data.is_broadcast,
                timestamp: data.timestamp
            }, false);
        } else {
            // Show notification for messages in other channels
            const channelName = data.is_broadcast ? 'Broadcast' : data.sender_username;
            UI.showToast(`[${channelName}] ${data.sender_username}: ${content.substring(0, 30)}...`, 'info');
        }
    });

    // Offline messages delivery
    socket.on('offline_message', (data) => {
        console.log('📬 Offline message:', data);
        
        // Only show if we're in the correct channel
        const shouldShow = (data.is_broadcast && currentTarget.type === 'broadcast') ||
                          (!data.is_broadcast && currentTarget.type === 'direct' && 
                           currentTarget.id === data.sender_id);
        
        if (shouldShow) {
            UI.addMessage({
                sender_username: data.sender_username,
                content: data.content,
                is_broadcast: data.is_broadcast,
                timestamp: data.created_at
            }, false);
        } else {
            // Show notification
            const channelName = data.is_broadcast ? 'Broadcast' : data.sender_username;
            UI.showToast(`[${channelName}] Yeni mesaj: ${data.content.substring(0, 30)}...`, 'info');
        }
    });

    // Message sent confirmation
    socket.on('message_sent', (data) => {
        console.log('✅ Message sent:', data);
    });

    // Message history
    socket.on('message_history', (data) => {
        UI.clearMessages();
        data.messages.forEach(msg => {
            const isSent = msg.sender_id === currentUser.id;
            UI.addMessage({
                sender_username: msg.sender_username,
                content: msg.content,
                is_broadcast: msg.is_broadcast,
                timestamp: msg.created_at
            }, isSent);
        });
    });

    // User online/offline events
    socket.on('user_online', (data) => {
        console.log('👤 User online:', data.username);
        UI.showToast(`${data.username} çevrimiçi oldu`, 'success');
        updateUserStatus(data.user_id, true);
    });

    socket.on('user_offline', (data) => {
        console.log('👤 User offline:', data.username);
        UI.showToast(`${data.username} çevrimdışı oldu`, 'info');
        updateUserStatus(data.user_id, false);
    });

    // Typing indicators
    socket.on('user_typing', (data) => {
        if (data.user_id !== currentUser.id) {
            UI.showTyping(data.username, true);
        }
    });

    socket.on('user_stop_typing', (data) => {
        UI.showTyping(data.username, false);
    });

    // Error handling
    socket.on('error', (data) => {
        UI.showToast(data.message, 'error');
    });

    // ============== GROUP SOCKET EVENTS ==============
    
    // Group created confirmation
    socket.on('group_created', (data) => {
        console.log('👥 Group created:', data.name);
        UI.showToast(`Grup "${data.name}" oluşturuldu!`, 'success');
        UI.showModal(false);
        loadGroups();
    });

    // Added to a group
    socket.on('added_to_group', (data) => {
        console.log('👥 Added to group:', data.name);
        UI.showToast(`${data.added_by} sizi "${data.name}" grubuna ekledi`, 'info');
        loadGroups();
    });

    // New group message received
    socket.on('new_group_message', (data) => {
        console.log('📨 New group message:', data);
        
        // Only show if we're viewing this group
        if (currentTarget.type === 'group' && currentTarget.id === data.group_id) {
            UI.addGroupMessage({
                sender_username: data.sender_username,
                content: data.encrypted_content,
                group_name: data.group_name,
                timestamp: data.timestamp
            }, false);
        } else {
            // Show notification
            UI.showToast(`[${data.group_name}] ${data.sender_username}: ${data.encrypted_content.substring(0, 30)}...`, 'info');
        }
    });

    // Group message sent confirmation
    socket.on('group_message_sent', (data) => {
        console.log('✅ Group message sent:', data);
    });

    // Group message history
    socket.on('group_message_history', (data) => {
        UI.clearMessages();
        data.messages.forEach(msg => {
            const isSent = msg.sender_id === currentUser.id;
            UI.addGroupMessage({
                sender_username: msg.sender_username,
                content: msg.content,
                group_name: currentTarget.name,
                timestamp: msg.created_at
            }, isSent);
        });
    });
}

// ============== USER MANAGEMENT ==============
async function loadUsers() {
    try {
        const response = await fetch('/api/users');
        users = await response.json();
        UI.updateUsersList(users);
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

// ============== GROUP MANAGEMENT ==============
async function loadGroups() {
    try {
        const response = await fetch('/api/groups');
        groups = await response.json();
        UI.updateGroupsList(groups);
    } catch (error) {
        console.error('Error loading groups:', error);
    }
}

function selectGroup(group) {
    // Update active state in sidebar
    document.querySelectorAll('.user-item, .channel-item, .group-item').forEach(el => {
        el.classList.remove('active');
    });
    
    const groupEl = document.querySelector(`[data-group-id="${group.id}"]`);
    if (groupEl) groupEl.classList.add('active');
    
    // Update current target
    currentTarget = {
        type: 'group',
        id: group.id,
        name: group.name
    };
    
    UI.updateChatHeader();
    UI.clearMessages();
    
    // Load group message history
    socket.emit('get_group_history', { group_id: group.id });
}

function createGroup() {
    const nameInput = document.getElementById('group-name');
    const name = nameInput.value.trim();
    
    if (!name) {
        UI.showToast('Grup adı gereklidir!', 'error');
        return;
    }
    
    if (name.length < 2) {
        UI.showToast('Grup adı en az 2 karakter olmalıdır!', 'error');
        return;
    }
    
    // Get selected members
    const checkboxes = document.querySelectorAll('#member-selection input[type="checkbox"]:checked');
    const memberIds = Array.from(checkboxes).map(cb => parseInt(cb.value));
    
    if (memberIds.length === 0) {
        UI.showToast('En az bir üye seçmelisiniz!', 'error');
        return;
    }
    
    // Send create group event
    socket.emit('create_group', {
        name: name,
        member_ids: memberIds
    });
}

function updateUserStatus(userId, isOnline) {
    const user = users.find(u => u.id === userId);
    if (user) {
        user.is_online = isOnline;
        UI.updateUsersList(users);
        
        // Update header if viewing this user
        if (currentTarget.type === 'direct' && currentTarget.id === userId) {
            UI.updateChatHeader();
        }
    } else {
        // Reload users list if new user
        loadUsers();
    }
}

function selectUser(user) {
    // Update active state in sidebar
    document.querySelectorAll('.user-item, .channel-item, .group-item').forEach(el => {
        el.classList.remove('active');
    });
    
    const userEl = document.querySelector(`[data-user-id="${user.id}"]`);
    if (userEl) userEl.classList.add('active');
    
    // Update current target
    currentTarget = {
        type: 'direct',
        id: user.id,
        name: user.username,
        username: user.username
    };
    
    UI.updateChatHeader();
    UI.clearMessages();
    
    // Load message history with this user
    socket.emit('get_history', { other_user_id: user.id });
}

function selectBroadcast() {
    // Update active state
    document.querySelectorAll('.user-item, .channel-item, .group-item').forEach(el => {
        el.classList.remove('active');
    });
    document.querySelector('[data-channel="broadcast"]').classList.add('active');
    
    // Update current target
    currentTarget = {
        type: 'broadcast',
        id: null,
        name: 'Broadcast',
        username: null
    };
    
    UI.updateChatHeader();
    UI.clearMessages();
    
    // Load broadcast history
    socket.emit('get_history', {});
}

// ============== MESSAGE HANDLING ==============
function sendMessage(content) {
    if (!content.trim() || !socket?.connected) return;
    
    // Handle group messages
    if (currentTarget.type === 'group') {
        socket.emit('send_group_message', {
            group_id: currentTarget.id,
            encrypted_content: content
        });
        
        // Add to local chat
        UI.addGroupMessage({
            sender_username: currentUser.username,
            content: content,
            group_name: currentTarget.name,
            timestamp: new Date().toISOString()
        }, true);
        return;
    }
    
    // For now, we send the content directly
    // In a full E2E implementation, we would encrypt here
    const messageData = {
        encrypted_content: content,
        is_broadcast: currentTarget.type === 'broadcast',
        receiver_id: currentTarget.type === 'direct' ? currentTarget.id : null
    };
    
    socket.emit('send_message', messageData);
    
    // Add to local chat
    UI.addMessage({
        sender_username: currentUser.username,
        content: content,
        is_broadcast: currentTarget.type === 'broadcast',
        timestamp: new Date().toISOString()
    }, true);
}

function handleTyping() {
    if (!socket?.connected) return;
    
    socket.emit('typing', {
        receiver_id: currentTarget.type === 'direct' ? currentTarget.id : null,
        is_broadcast: currentTarget.type === 'broadcast'
    });
    
    // Clear previous timeout
    if (typingTimeout) clearTimeout(typingTimeout);
    
    // Set timeout to stop typing indicator
    typingTimeout = setTimeout(() => {
        socket.emit('stop_typing', {
            receiver_id: currentTarget.type === 'direct' ? currentTarget.id : null,
            is_broadcast: currentTarget.type === 'broadcast'
        });
    }, 2000);
}

// ============== EVENT LISTENERS ==============
document.addEventListener('DOMContentLoaded', () => {
    // Initialize socket connection
    initSocket();
    
    // Message form submission
    const messageForm = document.getElementById('message-form');
    const messageInput = document.getElementById('message-input');
    
    messageForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const content = messageInput.value.trim();
        if (content) {
            sendMessage(content);
            messageInput.value = '';
        }
    });
    
    // Typing indicator
    messageInput.addEventListener('input', handleTyping);
    
    // Broadcast channel click
    document.querySelector('[data-channel="broadcast"]').addEventListener('click', selectBroadcast);
    
    // History button
    document.getElementById('btn-history').addEventListener('click', () => {
        if (currentTarget.type === 'group') {
            socket.emit('get_group_history', { group_id: currentTarget.id });
        } else {
            socket.emit('get_history', {
                other_user_id: currentTarget.type === 'direct' ? currentTarget.id : null
            });
        }
        UI.showToast('Mesaj geçmişi yükleniyor...', 'info');
    });
    
    // Create group button
    document.getElementById('btn-create-group').addEventListener('click', () => {
        UI.showModal(true);
    });
    
    // Modal close buttons
    document.getElementById('close-modal').addEventListener('click', () => {
        UI.showModal(false);
    });
    
    document.getElementById('cancel-create-group').addEventListener('click', () => {
        UI.showModal(false);
    });
    
    document.getElementById('confirm-create-group').addEventListener('click', () => {
        createGroup();
    });
    
    // Close modal on overlay click
    document.querySelector('.modal-overlay')?.addEventListener('click', () => {
        UI.showModal(false);
    });
    
    // Focus input on page load
    messageInput.focus();
});

// Add CSS animation for toast out
const style = document.createElement('style');
style.textContent = `
    @keyframes toastOut {
        from { opacity: 1; transform: translateX(0); }
        to { opacity: 0; transform: translateX(100%); }
    }
`;
document.head.appendChild(style);

