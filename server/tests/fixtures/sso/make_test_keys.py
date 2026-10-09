r"""Writes the SSO test keys and certificates in this folder (TEST ONLY: they
sign the local mock providers' tokens and assertions and are worthless
anywhere else). Run from server/: .venv\Scripts\python.exe tests/fixtures/sso/make_test_keys.py
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

HERE = Path(__file__).parent


def _key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _pem(key) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


def _cert(key, cn: str) -> bytes:
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=3650))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM)


def main() -> None:
    (HERE / "oidc_test_key.pem").write_bytes(_pem(_key()))
    for name, cn in (("saml_idp", "Truebex test IdP"), ("saml_other", "Some other IdP")):
        key = _key()
        (HERE / f"{name}_key.pem").write_bytes(_pem(key))
        (HERE / f"{name}_cert.pem").write_bytes(_cert(key, cn))
    print("written to", HERE)


if __name__ == "__main__":
    main()
