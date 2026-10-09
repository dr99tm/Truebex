# Secrets for the API host

Encrypted with [SOPS](https://github.com/getsops/sops) and [age](https://github.com/FiloSottile/age);
only `*.sops.env` files (encrypted) are committed. `infra/deploy.ps1` decrypts them on the owner's PC and
copies them to `/opt/truebex/secrets/` on the VM (mode 0600). Plain `*.env` files here are gitignored.

| Encrypted file | Template | Becomes on the VM |
|---|---|---|
| `server.sops.env` | `server.env.example` | `secrets/server.env` (the `api` and `worker` containers) |
| `postgres.sops.env` | `postgres.env.example` | `secrets/postgres.env` (Postgres and wal-g) |
| `host.sops.env` | `host.env.example` | `secrets/host.env` (`bin/host-check.sh`) |
| `origin.sops.env` | — | `secrets/origin.pem`, `secrets/origin.key` (Caddy) |

First time:

```powershell
age-keygen -o "$env:APPDATA\sops\age\keys.txt"      # keep a copy offline; losing it loses the secrets
age-keygen -y "$env:APPDATA\sops\age\keys.txt"      # put this public key into infra/.sops.yaml
cd infra
copy secrets\server.env.example secrets\server.env   # fill in, then:
sops --encrypt secrets\server.env > secrets\server.sops.env
del secrets\server.env
# the same for postgres and host; for the origin certificate (after `tofu apply`):
tofu -chdir=tofu output -raw origin_certificate > secrets\origin.pem
tofu -chdir=tofu output -raw origin_private_key > secrets\origin.key
sops --encrypt --input-type binary secrets\origin.pem > secrets\origin.pem.sops.env
sops --encrypt --input-type binary secrets\origin.key > secrets\origin.key.sops.env
del secrets\origin.pem, secrets\origin.key
```

Edit later with `sops secrets\server.sops.env` (it decrypts into the editor and re-encrypts on save).
One S3 key per role: the API and worker key reads and writes the data bucket; the Postgres key writes the
backup bucket and nothing else.
