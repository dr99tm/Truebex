# The energy runner (PF11): EnergyPlus (BSD-3-Clause) from its official
# release archive. Confirm the asset name and its SHA-256 on the release page
# at writing time and pass them:
#   build.ps1 -Kind energy -BuildArg "ENERGYPLUS_URL=<url>","ENERGYPLUS_SHA256=<sha>"
# The build stops without a checksum.
FROM ubuntu:22.04
ARG TRUEBEX_IMAGE=truebex-analysis-energy:1
ARG ENERGYPLUS_VERSION=24.2.0
ARG ENERGYPLUS_URL=https://github.com/NREL/EnergyPlus/releases/download/v24.2.0/EnergyPlus-24.2.0-94a887817b-Linux-Ubuntu22.04-x86_64.tar.gz
ARG ENERGYPLUS_SHA256=
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl python3 libgomp1 libx11-6 \
 && rm -rf /var/lib/apt/lists/*
RUN test -n "$ENERGYPLUS_SHA256" || (echo "Set ENERGYPLUS_SHA256 (the release asset's checksum) with --build-arg" >&2; exit 1) \
 && curl -fsSL "$ENERGYPLUS_URL" -o /tmp/energyplus.tar.gz \
 && echo "$ENERGYPLUS_SHA256  /tmp/energyplus.tar.gz" | sha256sum -c - \
 && mkdir -p /opt/energyplus \
 && tar -xzf /tmp/energyplus.tar.gz -C /opt/energyplus --strip-components=1 \
 && rm /tmp/energyplus.tar.gz \
 && ln -s /opt/energyplus/energyplus /usr/local/bin/energyplus \
 && useradd -u 1000 -m -s /bin/bash truebex
COPY runners /opt/truebex/runners
COPY run.sh /opt/truebex/run.sh
RUN chmod 0755 /opt/truebex/run.sh
ENV PYTHONPATH=/opt/truebex TRUEBEX_IMAGE=${TRUEBEX_IMAGE} ENERGYPLUS_VERSION=${ENERGYPLUS_VERSION}
USER 1000
WORKDIR /job
ENTRYPOINT ["/opt/truebex/run.sh", "energy"]
