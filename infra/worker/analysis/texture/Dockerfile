# The texture runner (PF11; the platform keeps the kind off until
# AI_TEXTURE_ENABLED). An open image model whose licence allows commercial
# hosting, baked in at build: -BuildArg "TEXTURE_MODEL=<model id>" (check its
# licence first; GD3 names the gpu-ai class). Runs with --gpus all.
FROM pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime
ARG TRUEBEX_IMAGE=truebex-analysis-texture:1
ARG TEXTURE_MODEL=
RUN pip install --no-cache-dir diffusers==0.30.3 transformers==4.44.2 accelerate==0.34.2 safetensors==0.4.5 pillow==10.4.0 numpy==1.26.4 \
 && useradd -u 1000 -m -s /bin/bash truebex
RUN test -n "$TEXTURE_MODEL" || (echo "Set TEXTURE_MODEL (a model whose licence allows commercial hosting) with --build-arg" >&2; exit 1) \
 && python -c "import torch, diffusers; diffusers.AutoPipelineForText2Image.from_pretrained('$TEXTURE_MODEL', torch_dtype=torch.float16).save_pretrained('/opt/truebex/models/texture')"
COPY runners /opt/truebex/runners
COPY run.sh /opt/truebex/run.sh
RUN chmod 0755 /opt/truebex/run.sh && chown -R 1000 /opt/truebex/models
ENV PYTHONPATH=/opt/truebex TRUEBEX_IMAGE=${TRUEBEX_IMAGE} TEXTURE_MODEL_VERSION=${TEXTURE_MODEL} HF_HUB_OFFLINE=1
USER 1000
WORKDIR /job
ENTRYPOINT ["/opt/truebex/run.sh", "texture"]
