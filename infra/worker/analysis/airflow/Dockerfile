# The airflow runner (PF11c, render-jobs 1.2.0 section 6.5.3): the orifice network
# between rooms on the wind job's Cp, standard library Python only (no
# third-party solver). Its own image beside acoustics, so the engine it names
# is truebex-analysis-airflow.
FROM python:3.12-slim
ARG TRUEBEX_IMAGE=truebex-analysis-airflow:1
RUN useradd -u 1000 -m -s /bin/bash truebex
COPY runners /opt/truebex/runners
COPY run.sh /opt/truebex/run.sh
RUN chmod 0755 /opt/truebex/run.sh
ENV PYTHONPATH=/opt/truebex TRUEBEX_IMAGE=${TRUEBEX_IMAGE}
USER 1000
WORKDIR /job
ENTRYPOINT ["/opt/truebex/run.sh", "airflow"]
