# SSO test keys (TEST ONLY)

Keys and self-signed certificates for the local mock identity providers
(`tests/mock_oidc.py`, `tests/mock_saml_idp.py`). They sign test tokens and
test SAML assertions and are worthless anywhere else; no server setting ever
points at them. `make_test_keys.py` writes a fresh set. The repo ignores
`*.pem`, so they are not committed: the mocks write a set on first import
when a file is missing (`make_test_keys.ensure()`).

| File | Used by |
|---|---|
| `oidc_test_key.pem` | mock OIDC provider: signs ID tokens (RS256, kid `mock-1`) |
| `saml_idp_key.pem`, `saml_idp_cert.pem` | mock SAML IdP: signs responses; the certificate goes into the SSO connection |
| `saml_other_key.pem`, `saml_other_cert.pem` | a different IdP, for "signed by the wrong key" tests |
