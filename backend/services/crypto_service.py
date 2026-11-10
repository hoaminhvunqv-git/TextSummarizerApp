"""Mã hóa từng cột cho dữ liệu người dùng (docs/SPEC.md 5.8).

AES-256-GCM với key 32 byte base64 trong `ENCRYPTION_KEY`; nonce 12 byte ngẫu
nhiên cho mỗi lần mã hóa; giá trị lưu vào cột `*_enc` là
`base64(nonce + ciphertext_with_tag)`. Cùng một văn bản luôn cho ra hai chuỗi
khác nhau — đó là tính chất, không phải lỗi.
"""

import base64
import os
from typing import Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_BYTES = 32
NONCE_BYTES = 12


class CryptoService:
    """Bọc AESGCM thành cặp encrypt/decrypt cho chuỗi UTF-8."""

    def __init__(self, key: bytes):
        if len(key) != KEY_BYTES:
            raise ValueError(f"ENCRYPTION_KEY phải là 32 byte base64, nhận được {len(key)} byte.")
        self._aesgcm = AESGCM(key)

    @classmethod
    def from_b64_key(cls, key_b64: Union[str, bytes]) -> "CryptoService":
        if not key_b64 or not str(key_b64).strip():
            raise ValueError("ENCRYPTION_KEY chưa được cấu hình.")
        try:
            key = base64.b64decode(str(key_b64).strip(), validate=True)
        except Exception as exc:
            raise ValueError("ENCRYPTION_KEY không phải base64 hợp lệ.") from exc
        return cls(key)

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(NONCE_BYTES)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, token: str) -> str:
        raw = base64.b64decode(token, validate=True)
        if len(raw) <= NONCE_BYTES:
            raise ValueError("Dữ liệu mã hóa bị thiếu hoặc sai định dạng.")
        nonce, ciphertext = raw[:NONCE_BYTES], raw[NONCE_BYTES:]
        # Sai key hoặc dữ liệu bị sửa → InvalidTag, để app.py đổi thành 500 INTERNAL_ERROR.
        return self._aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
