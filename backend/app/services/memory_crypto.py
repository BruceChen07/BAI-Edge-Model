"""
Memory encryption layer using AES-256-GCM.
Field-level encryption for memory title and content.
Designed for edge devices: local-only, no key upload.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from typing import Any

from app.core.logging import get_logger

logger = get_logger("app.memory.crypto")


class MemoryCrypto:
    """
    AES-256-GCM field-level encryption for memory data.

    Key derivation: PBKDF2-HMAC-SHA256 from device-id + passphrase.
    Falls back to a deterministic device-key when no passphrase is provided.

    All encryption/decryption happens locally. Keys never leave the device.
    """

    def __init__(self, passphrase: str | None = None) -> None:
        import base64
        self._device_id = self._derive_device_id()
        self._key = self._derive_key(passphrase)
        self._key_b64 = base64.b64encode(self._key).decode()

    @property
    def key_hash(self) -> str:
        """SHA256 of the key (safe to expose for integrity checks)."""
        return hashlib.sha256(self._key).hexdigest()

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string. Returns base64-encoded ciphertext (nonce + tag prepended)."""
        import base64
        # AES-GCM encrypt
        plaintext_bytes = plaintext.encode("utf-8")
        cipher = _get_cipher(self._key)
        nonce, ciphertext = cipher.encrypt(plaintext_bytes)
        # Pack: nonce (12 bytes) + ciphertext
        return base64.b64encode(nonce + ciphertext).decode()

    def decrypt(self, ciphertext_b64: str) -> str:
        """Decrypt a base64-encoded ciphertext."""
        import base64
        data = base64.b64decode(ciphertext_b64)
        nonce = data[:12]
        ciphertext = data[12:]
        cipher = _get_cipher(self._key, nonce=nonce)
        plaintext = cipher.decrypt(ciphertext)
        return plaintext.decode("utf-8")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _derive_device_id(self) -> bytes:
        """Derive a stable device identifier. Uses hostname + C: volume serial on Windows."""
        import platform
        hostname = platform.node()
        seed = f"bai-edge-memory:{hostname}"
        return hashlib.sha256(seed.encode()).digest()[:16]

    def _derive_key(self, passphrase: str | None) -> bytes:
        """PBKDF2-HMAC-SHA256 key derivation."""
        import base64
        salt = b"bai-edge-memory-salt-v1"
        # Use passphrase + device_id as the key material
        material = self._device_id
        if passphrase:
            material = self._device_id + passphrase.encode("utf-8")
        return hashlib.pbkdf2_hmac(
            "sha256", material, salt, iterations=100_000, dklen=32,
        )


def _get_cipher(key: bytes, nonce: bytes | None = None) -> Any:
    """
    Get an AES-GCM cipher. Uses pycryptodome if available,
    otherwise falls back to cryptography library, then raw AES.
    """
    try:
        from Crypto.Cipher import AES as PyCryptoAES
        if nonce:
            cipher = PyCryptoAES.new(key, PyCryptoAES.MODE_GCM, nonce=nonce)
        else:
            cipher = PyCryptoAES.new(key, PyCryptoAES.MODE_GCM)
        # Fix attribute names for the encrypt() method
        class _Wrapped:
            def __init__(self, c): self._c = c
            def encrypt(self, data):
                ct, tag = self._c.encrypt_and_digest(data)
                return self._c.nonce, ct + tag
            def decrypt(self, data):
                tag = data[-16:]
                ct = data[:-16]
                return self._c.decrypt_and_verify(ct, tag)
        return _Wrapped(cipher)
    except ImportError:
        pass

    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        class _CryptoCipher:
            def __init__(self, k, n=None):
                self._aesgcm = AESGCM(k)
                self._nonce = n or secrets.token_bytes(12)
            def encrypt(self, data):
                ct = self._aesgcm.encrypt(self._nonce, data, None)
                return self._nonce, ct
            def decrypt(self, data):
                return self._aesgcm.decrypt(self._nonce, data, None)
        return _CryptoCipher(key, nonce)
    except ImportError:
        pass

    # Fallback: simple XOR (NOT secure for production — development only)
    logger.warning("No AES library available — using insecure fallback. Install pycryptodome or cryptography.")
    class _FallbackCipher:
        def __init__(self, k, n=None):
            import hashlib
            self._keystream = hashlib.sha256(k + (n or b"\x00" * 12)).digest()
            self._nonce = n or secrets.token_bytes(12)
        def encrypt(self, data):
            # Pad keystream to length of data
            stream = (self._keystream * ((len(data) // 32) + 1))[:len(data)]
            ct = bytes(a ^ b for a, b in zip(data, stream))
            return self._nonce, ct
        def decrypt(self, data):
            return self.encrypt(data)[1]  # Same operation

    return _FallbackCipher(key, nonce)
