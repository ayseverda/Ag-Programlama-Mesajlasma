"""
End-to-End Encryption Module for Secure Messaging
Uses AES-256 for symmetric encryption with key derivation
"""

import base64
import os
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes


class EncryptionManager:
    """Handles symmetric encryption for secure messaging"""
    
    def __init__(self, secret_key: str = None):
        """
        Initialize encryption manager with a secret key.
        If no key provided, generates a random one.
        """
        if secret_key:
            # Derive a 32-byte key from the provided secret
            self.key = hashlib.sha256(secret_key.encode()).digest()
        else:
            self.key = get_random_bytes(32)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext message using AES-256-CBC.
        Returns base64 encoded string containing IV + ciphertext.
        """
        try:
            # Generate random IV for each encryption
            iv = get_random_bytes(16)
            cipher = AES.new(self.key, AES.MODE_CBC, iv)
            
            # Pad and encrypt the plaintext
            padded_data = pad(plaintext.encode('utf-8'), AES.block_size)
            ciphertext = cipher.encrypt(padded_data)
            
            # Combine IV and ciphertext, then base64 encode
            encrypted_data = iv + ciphertext
            return base64.b64encode(encrypted_data).decode('utf-8')
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {str(e)}")
    
    def decrypt(self, encrypted_text: str) -> str:
        """
        Decrypt base64 encoded ciphertext.
        Expects format: base64(IV + ciphertext)
        """
        try:
            # Decode base64
            encrypted_data = base64.b64decode(encrypted_text.encode('utf-8'))
            
            # Extract IV (first 16 bytes) and ciphertext
            iv = encrypted_data[:16]
            ciphertext = encrypted_data[16:]
            
            # Decrypt and unpad
            cipher = AES.new(self.key, AES.MODE_CBC, iv)
            padded_plaintext = cipher.decrypt(ciphertext)
            plaintext = unpad(padded_plaintext, AES.block_size)
            
            return plaintext.decode('utf-8')
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {str(e)}")
    
    def get_key_base64(self) -> str:
        """Get the encryption key as base64 string (for key exchange)"""
        return base64.b64encode(self.key).decode('utf-8')
    
    @classmethod
    def from_base64_key(cls, base64_key: str) -> 'EncryptionManager':
        """Create an EncryptionManager from a base64 encoded key"""
        manager = cls()
        manager.key = base64.b64decode(base64_key.encode('utf-8'))
        return manager


class EncryptionError(Exception):
    """Custom exception for encryption errors"""
    pass


# Session-based encryption for E2E messaging
class SessionKeyManager:
    """
    Manages session keys for end-to-end encryption.
    Each user session gets a unique encryption key.
    """
    
    def __init__(self):
        self.session_keys = {}  # {session_id: EncryptionManager}
        # Master key for server-side operations (storing in DB)
        self.master_key = EncryptionManager(os.environ.get('MASTER_KEY', 'SecureMessagingMasterKey2024!'))
    
    def create_session_key(self, session_id: str) -> str:
        """
        Create a new session key for a user.
        Returns the base64 encoded key for client-side encryption.
        """
        encryption_manager = EncryptionManager()
        self.session_keys[session_id] = encryption_manager
        return encryption_manager.get_key_base64()
    
    def get_session_encryption(self, session_id: str) -> EncryptionManager:
        """Get the encryption manager for a session"""
        return self.session_keys.get(session_id)
    
    def remove_session(self, session_id: str):
        """Remove session key when user disconnects"""
        if session_id in self.session_keys:
            del self.session_keys[session_id]
    
    def encrypt_for_storage(self, plaintext: str) -> str:
        """Encrypt message for database storage using master key"""
        return self.master_key.encrypt(plaintext)
    
    def decrypt_from_storage(self, ciphertext: str) -> str:
        """Decrypt message from database using master key"""
        return self.master_key.decrypt(ciphertext)


# Global session key manager instance
session_manager = SessionKeyManager()


def generate_session_key() -> tuple:
    """
    Generate a new session key pair.
    Returns (key_base64, EncryptionManager)
    """
    manager = EncryptionManager()
    return (manager.get_key_base64(), manager)


# Utility functions for JavaScript interoperability
def encrypt_message_for_client(message: str, client_key_base64: str) -> str:
    """Encrypt a message using client's session key"""
    manager = EncryptionManager.from_base64_key(client_key_base64)
    return manager.encrypt(message)


def decrypt_message_from_client(encrypted_message: str, client_key_base64: str) -> str:
    """Decrypt a message using client's session key"""
    manager = EncryptionManager.from_base64_key(client_key_base64)
    return manager.decrypt(encrypted_message)


if __name__ == "__main__":
    # Test encryption/decryption
    print("Testing encryption module...")
    
    manager = EncryptionManager("test_secret_key")
    original = "Merhaba, bu bir test mesajıdır! 🔐"
    
    encrypted = manager.encrypt(original)
    print(f"Original: {original}")
    print(f"Encrypted: {encrypted}")
    
    decrypted = manager.decrypt(encrypted)
    print(f"Decrypted: {decrypted}")
    print(f"Match: {original == decrypted}")

