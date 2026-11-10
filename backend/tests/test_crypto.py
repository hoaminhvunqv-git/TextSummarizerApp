import base64
import os

import pytest
from cryptography.exceptions import InvalidTag

try:
    from backend.services.crypto_service import CryptoService, KEY_BYTES, NONCE_BYTES
except ImportError:
    from services.crypto_service import CryptoService, KEY_BYTES, NONCE_BYTES

VIETNAMESE_TEXT = "Hôm nay trời mưa. Tôi ở Hà Nội, nhớ Hà Nội một ngày thu Hà Nội."


@pytest.fixture
def crypto():
    return CryptoService(os.urandom(KEY_BYTES))


def test_round_trip_vietnamese_and_emoji(crypto):
    text = f"{VIETNAMESE_TEXT} 🎉 ă â ê ô ơ ư đ"
    assert crypto.decrypt(crypto.encrypt(text)) == text


def test_round_trip_empty_and_long_text(crypto):
    assert crypto.decrypt(crypto.encrypt("")) == ""
    long_text = "Văn bản tiếng Việt. " * 1500  # ~27.000 ký tự
    assert crypto.decrypt(crypto.encrypt(long_text)) == long_text


def test_same_plaintext_never_produces_same_ciphertext(crypto):
    """Nonce ngẫu nhiên: hai bản mã của cùng một văn bản phải khác nhau."""
    first = crypto.encrypt(VIETNAMESE_TEXT)
    second = crypto.encrypt(VIETNAMESE_TEXT)
    assert first != second
    assert crypto.decrypt(first) == crypto.decrypt(second) == VIETNAMESE_TEXT


def test_token_is_base64_and_contains_no_plaintext(crypto):
    token = crypto.encrypt(VIETNAMESE_TEXT)
    raw = base64.b64decode(token, validate=True)
    assert len(raw) > NONCE_BYTES
    assert VIETNAMESE_TEXT.encode("utf-8") not in raw
    assert VIETNAMESE_TEXT not in token


def test_wrong_key_is_rejected():
    other = CryptoService(os.urandom(KEY_BYTES))
    token = other.encrypt(VIETNAMESE_TEXT)
    with pytest.raises(InvalidTag):
        CryptoService(os.urandom(KEY_BYTES)).decrypt(token)


def test_tampered_ciphertext_is_rejected(crypto):
    raw = bytearray(base64.b64decode(crypto.encrypt(VIETNAMESE_TEXT)))
    raw[-1] ^= 0x01
    with pytest.raises(InvalidTag):
        crypto.decrypt(base64.b64encode(bytes(raw)).decode("ascii"))


def test_truncated_token_is_rejected(crypto):
    raw = base64.b64decode(crypto.encrypt(VIETNAMESE_TEXT))
    with pytest.raises(ValueError, match="thiếu hoặc sai"):
        crypto.decrypt(base64.b64encode(raw[:NONCE_BYTES]).decode("ascii"))


def test_key_must_be_32_bytes():
    with pytest.raises(ValueError, match="32 byte"):
        CryptoService(os.urandom(KEY_BYTES - 1))


def test_from_b64_key_matches_env_format():
    """ENCRYPTION_KEY trong .env là base64 của đúng 32 byte."""
    key_b64 = base64.b64encode(os.urandom(KEY_BYTES)).decode("ascii")
    service = CryptoService.from_b64_key(f"  {key_b64}  ")
    assert service.decrypt(service.encrypt("xin chào")) == "xin chào"


def test_from_b64_key_rejects_bad_input():
    for bad in ("", "   ", "không phải base64 @@@", base64.b64encode(b"ngan").decode()):
        with pytest.raises(ValueError):
            CryptoService.from_b64_key(bad)
