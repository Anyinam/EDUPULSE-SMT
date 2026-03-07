import logging
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import Text, TypeDecorator

logger = logging.getLogger(__name__)

DEV_FERNET_KEY = "Q7dG5vjXFn340xkmevogawqruIgndlsWdz4mg0PjkmI="


@lru_cache(maxsize=1)
def get_fernet():
    key = os.getenv("DATA_ENCRYPTION_KEY")
    if not key:
        key = DEV_FERNET_KEY
        logger.warning("DATA_ENCRYPTION_KEY not set; using dev key")
    if isinstance(key, str):
        key = key.encode("utf-8")
    return Fernet(key)


def encrypt_value(value):
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    token = get_fernet().encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_value(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    try:
        return get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # Backward compatibility: return plaintext for legacy rows
        return value


class EncryptedString(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_value(value)

    def process_result_value(self, value, dialect):
        return decrypt_value(value)
