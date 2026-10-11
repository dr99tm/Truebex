# The wind runner (PF11): OpenFOAM v2406, steady RANS (simpleFoam, k-epsilon).
# OpenFOAM is GPL-3.0: it runs as a service on the platform's workers and is
# never distributed with the app. Built by build.ps1 -Kind wind (the context
# holds runners/ and run.sh).
FROM opencfd/openfoam-default:2406
ARG TRUEBEX_IMAGE=truebex-analysis-wind:1
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 \
 && rm -rf /var/lib/apt/lists/* \
 && (id -u 1000 >/dev/null 2>&1 || useradd -u 1000 -m -s /bin/bash truebex)
COPY runners /opt/truebex/runners
COPY run.sh /opt/truebex/run.sh
RUN chmod 0755 /opt/truebex/run.sh
ENV PYTHONPATH=/opt/truebex TRUEBEX_IMAGE=${TRUEBEX_IMAGE}
USER 1000
WORKDIR /job
ENTRYPOINT ["/opt/truebex/run.sh", "wind"]
