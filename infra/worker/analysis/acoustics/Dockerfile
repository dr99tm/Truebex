# The acoustics runner (PF11): our own stochastic energy ray tracer, standard
# library Python only (no third-party solver).
FROM python:3.12-slim
ARG TRUEBEX_IMAGE=truebex-analysis-acoustics:1
RUN useradd -u 1000 -m -s /bin/bash truebex
COPY runners /opt/truebex/runners
COPY run.sh /opt/truebex/run.sh
RUN chmod 0755 /opt/truebex/run.sh
ENV PYTHONPATH=/opt/truebex TRUEBEX_IMAGE=${TRUEBEX_IMAGE}
USER 1000
WORKDIR /job
ENTRYPOINT ["/opt/truebex/run.sh", "acoustics"]
