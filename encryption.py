import base64
import secrets

class CustomCipher:

    def __init__(self, key: str):
        self.key = key
        self.seed = self._seed_from_key(key)

    def _seed_from_key(self, key: str) -> int:
        """Key içindeki ascii değerlerin toplamından bir seed üretir."""
        return sum(ord(c) for c in key) % 9973  # Prime-based

    def _keystream(self, length: int):
        """Basit bir LCG tabanlı key stream üreticisi."""
        a = 1103515245
        c = 12345
        m = 2**31
        seed = self.seed

        for _ in range(length):
            seed = (a * seed + c) % m
            yield seed % 256

    def _rotate_left(self, val: int, r: int) -> int:
        return ((val << r) & 0xFF) | (val >> (8 - r))

    def _rotate_right(self, val: int, r: int) -> int:
        return (val >> r) | ((val << (8 - r)) & 0xFF)

    def encrypt(self, plaintext: str) -> str:
        data = plaintext.encode()
        keystream = self._keystream(len(data))

        result = bytearray()
        for i, b in enumerate(data):
            k = next(keystream)
            x = b ^ k
            r = (k % 7) + 1
            x = self._rotate_left(x, r)
            result.append(x)

        return base64.b64encode(result).decode()

    def decrypt(self, ciphertext: str) -> str:
        data = base64.b64decode(ciphertext.encode())
        keystream = self._keystream(len(data))

        result = bytearray()
        for i, b in enumerate(data):
            k = next(keystream)
            r = (k % 7) + 1
            x = self._rotate_right(b, r)
            x = x ^ k
            result.append(x)

        return result.decode()


class SessionManager:
    """SocketIO bağlantısı için oturum anahtarlarını yönetir."""

    def __init__(self):
        self.sessions = {}
        self.master_key = "MASTERKEY-SERVER-ONLY"  # Sunucu için gizli key
        self.master_cipher = CustomCipher(self.master_key)

    def create_session_key(self, sid: str) -> str:
        """Her websocket bağlantısı için rastgele bir key oluştur."""
        key = secrets.token_hex(16)
        self.sessions[sid] = CustomCipher(key)
        return key

    def remove_session(self, sid: str):
        self.sessions.pop(sid, None)

    def encrypt_client_message(self, sid: str, plaintext: str) -> str:
        """İstemcinin mesaj göndermesi için."""
        return self.sessions[sid].encrypt(plaintext)

    def decrypt_client_message(self, sid: str, ciphertext: str) -> str:
        """Sunucu gelen mesajı çözer."""
        return self.sessions[sid].decrypt(ciphertext)

    def encrypt_for_storage(self, plaintext: str) -> str:
        """Veritabanına kaydetmek için master key ile yeniden şifreler."""
        return self.master_cipher.encrypt(plaintext)

    def decrypt_from_storage(self, ciphertext: str) -> str:
        """Veritabanından okunan mesajı çöz."""
        return self.master_cipher.decrypt(ciphertext)


