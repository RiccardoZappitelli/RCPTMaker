import base64
from nacl.secret import SecretBox
from nacl.utils import random

class SimpleFernet:
    KEY_SIZE = SecretBox.KEY_SIZE  # 32 bytes

    @staticmethod
    def generate_key() -> bytes:
        """
        Generates a URL-safe base64-encoded 32-byte key,
        compatible with Fernet-style usage.
        """
        key = random(SimpleFernet.KEY_SIZE)
        return base64.urlsafe_b64encode(key)

    def __init__(self, key: bytes, header: bytes = b""):
        """
        Accepts a URL-safe base64-encoded key (like Fernet).
        """
        self._header = header
        raw_key = base64.urlsafe_b64decode(key)
        if len(raw_key) != self.KEY_SIZE:
            raise ValueError("Invalid key length")
        self.box = SecretBox(raw_key)

    def encrypt(self, data: bytes) -> bytes:
        encrypted = self.box.encrypt(data)
        return self._header+base64.urlsafe_b64encode(encrypted)

    def decrypt(self, token: bytes) -> bytes:
        decoded = base64.urlsafe_b64decode(token[len(self._header):])
        return self.box.decrypt(decoded)

