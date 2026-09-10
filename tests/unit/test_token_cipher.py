"""AES-256-GCM custody for OAuth tokens at rest (ADR-036).

Keys here are generated per test with `os.urandom`. No key, and no key
material, appears in this file or in the repository.
"""

from __future__ import annotations

import base64
import os

import pytest

from juval.infrastructure.crypto.token_cipher import (
    KEYRING_ENV,
    SCHEME,
    TokenCipher,
    TokenCryptoUnavailable,
    TokenDecryptionError,
    _Key,
    context_for,
)

TOKEN = "an-opaque-oauth-token-value"
CTX = context_for("a" * 64, "access_token")


def _key(key_id: str = "k1") -> _Key:
    return _Key(key_id=key_id, material=os.urandom(32))


def _keyring_env(*keys: _Key) -> str:
    return ",".join(f"{k.key_id}:{base64.b64encode(k.material).decode()}" for k in keys)


# --- round trip --------------------------------------------------------


def test_round_trip():
    cipher = TokenCipher(_key())
    assert cipher.decrypt(cipher.encrypt(TOKEN, context=CTX), context=CTX) == TOKEN


def test_ciphertext_does_not_contain_the_plaintext():
    cipher = TokenCipher(_key())
    envelope = cipher.encrypt(TOKEN, context=CTX)
    assert TOKEN not in envelope


def test_envelope_is_versioned_and_names_its_key():
    cipher = TokenCipher(_key("primary-2026-09"))
    scheme, key_id, nonce, sealed = cipher.encrypt(TOKEN, context=CTX).split(".", 3)
    assert scheme == SCHEME
    assert key_id == "primary-2026-09"
    assert nonce and sealed


def test_nonce_is_fresh_for_every_encryption():
    # GCM loses both confidentiality and authenticity on nonce reuse, so this
    # is a security property, not a style preference.
    cipher = TokenCipher(_key())
    nonces = {cipher.encrypt(TOKEN, context=CTX).split(".")[2] for _ in range(50)}
    assert len(nonces) == 50


# --- failure modes -----------------------------------------------------


def test_wrong_key_cannot_decrypt():
    envelope = TokenCipher(_Key("k1", os.urandom(32))).encrypt(TOKEN, context=CTX)
    other = TokenCipher(_Key("k1", os.urandom(32)))  # same id, different material
    with pytest.raises(TokenDecryptionError):
        other.decrypt(envelope, context=CTX)


def test_unknown_key_id_is_rejected():
    envelope = TokenCipher(_key("retired")).encrypt(TOKEN, context=CTX)
    with pytest.raises(TokenDecryptionError):
        TokenCipher(_key("current")).decrypt(envelope, context=CTX)


@pytest.mark.parametrize(
    "mangle",
    [
        lambda e: e[:-1] + ("A" if e[-1] != "A" else "B"),   # flipped tag byte
        lambda e: e.replace(SCHEME, "v9", 1),                # unsupported scheme
        lambda e: e.split(".", 1)[1],                        # truncated envelope
        lambda e: "",                                        # empty
    ],
    ids=["tampered", "unknown-scheme", "truncated", "empty"],
)
def test_corrupt_ciphertext_is_rejected(mangle):
    cipher = TokenCipher(_key())
    with pytest.raises(TokenDecryptionError):
        cipher.decrypt(mangle(cipher.encrypt(TOKEN, context=CTX)), context=CTX)


def test_ciphertext_is_bound_to_its_column():
    cipher = TokenCipher(_key())
    envelope = cipher.encrypt(TOKEN, context=context_for("digest-a", "access_token"))
    with pytest.raises(TokenDecryptionError):
        cipher.decrypt(envelope, context=context_for("digest-a", "refresh_token"))


def test_ciphertext_is_bound_to_its_row():
    cipher = TokenCipher(_key())
    envelope = cipher.encrypt(TOKEN, context=context_for("digest-a", "access_token"))
    with pytest.raises(TokenDecryptionError):
        cipher.decrypt(envelope, context=context_for("digest-b", "access_token"))


def test_failure_message_never_echoes_the_ciphertext_or_context():
    cipher = TokenCipher(_key())
    envelope = cipher.encrypt(TOKEN, context=CTX)
    with pytest.raises(TokenDecryptionError) as exc:
        cipher.decrypt(envelope, context=context_for("other", "access_token"))
    assert envelope not in str(exc.value)
    assert TOKEN not in str(exc.value)


# --- rotation ----------------------------------------------------------


def test_old_key_still_decrypts_after_rotation():
    old, new = _key("old"), _key("new")
    envelope = TokenCipher(old).encrypt(TOKEN, context=CTX)
    rotated = TokenCipher(primary=new, others=(old,))
    assert rotated.decrypt(envelope, context=CTX) == TOKEN
    assert rotated.primary_key_id == "new"


def test_needs_reencryption_flags_old_key_and_old_scheme():
    old, new = _key("old"), _key("new")
    envelope = TokenCipher(old).encrypt(TOKEN, context=CTX)
    rotated = TokenCipher(primary=new, others=(old,))
    assert rotated.needs_reencryption(envelope) is True
    assert rotated.needs_reencryption(rotated.encrypt(TOKEN, context=CTX)) is False
    assert rotated.needs_reencryption("garbage") is True


# --- keyring parsing ---------------------------------------------------


def test_from_environment_uses_the_first_entry_as_primary():
    a, b = _key("a"), _key("b")
    cipher = TokenCipher.from_environment({KEYRING_ENV: _keyring_env(a, b)})
    assert cipher.primary_key_id == "a"
    envelope = TokenCipher(b).encrypt(TOKEN, context=CTX)
    assert cipher.decrypt(envelope, context=CTX) == TOKEN


@pytest.mark.parametrize(
    "value",
    ["", "   ", "no-colon", "k1:not-base64!!", f"k1:{base64.b64encode(os.urandom(16)).decode()}"],
    ids=["empty", "blank", "no-separator", "not-base64", "wrong-length"],
)
def test_bad_keyring_fails_closed(value):
    with pytest.raises(TokenCryptoUnavailable):
        TokenCipher.from_environment({KEYRING_ENV: value})


def test_missing_keyring_fails_closed():
    with pytest.raises(TokenCryptoUnavailable):
        TokenCipher.from_environment({})


def test_key_id_may_not_contain_the_envelope_separator():
    bad = _Key("has.dot", os.urandom(32))
    with pytest.raises(TokenCryptoUnavailable):
        TokenCipher.from_environment({KEYRING_ENV: _keyring_env(bad)})
