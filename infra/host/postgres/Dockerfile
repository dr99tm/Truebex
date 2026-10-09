# Postgres 18 with wal-g (Apache-2.0) for continuous WAL archiving and
# nightly base backups to the backup bucket at a second provider (PF14).
FROM postgres:18-bookworm

ARG WALG_VERSION=v3.0.9
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl libsodium23; \
    curl -fsSL -o /tmp/wal-g.tar.gz \
      "https://github.com/wal-g/wal-g/releases/download/${WALG_VERSION}/wal-g-pg-22.04-amd64.tar.gz"; \
    curl -fsSL -o /tmp/wal-g.tar.gz.sha256 \
      "https://github.com/wal-g/wal-g/releases/download/${WALG_VERSION}/wal-g-pg-22.04-amd64.tar.gz.sha256"; \
    echo "$(cut -d' ' -f1 /tmp/wal-g.tar.gz.sha256)  /tmp/wal-g.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/wal-g.tar.gz -C /tmp; \
    install -m 0755 /tmp/wal-g-pg-22.04-amd64 /usr/local/bin/wal-g; \
    rm -rf /tmp/wal-g* /var/lib/apt/lists/*; \
    apt-get purge -y --auto-remove curl; \
    wal-g --version

COPY restore-into.sh /usr/local/bin/restore-into.sh
RUN chmod 0755 /usr/local/bin/restore-into.sh
