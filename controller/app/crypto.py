from cryptography.fernet import Fernet

from .settings import Settings


class SecretCipher:
    def __init__(self, settings: Settings) -> None:
        self._fernet = Fernet(settings.read_secret(settings.encryption_key_file, "encryption key").encode())

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode()).decode()
