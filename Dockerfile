# Container image for Google Cloud Run.
#
# Cloud Run can build from source with buildpacks and no Dockerfile, but this
# image does two things buildpacks would not, and both matter here:
#
#   1. installs the CPU-only build of PyTorch. The default PyPI wheel carries
#      CUDA libraries -- around 2 GB of GPU code that a Cloud Run CPU
#      instance can never use.
#   2. downloads the pinned embedding model at build time, so a cold start
#      loads it from the image instead of fetching 87 MB from the Hugging
#      Face Hub, and the running container needs no network access at all.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache

WORKDIR /app

# Installed from PyTorch's own index first, so the requirements install below
# finds torch already satisfied and never reaches for the CUDA build.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
        torch==2.10.0

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# Fetch the model pinned in search.py into the image. A build fails here
# rather than a container failing to start in production.
RUN python -c "import search; search.load_model()" \
    && chmod -R a+rX /opt/hf-cache

# The application owns nothing it needs to write, so it runs unprivileged.
RUN useradd --create-home --uid 1001 portfolio
USER portfolio

ENV APP_ENV=production \
    HF_HUB_OFFLINE=1

# Cloud Run sets PORT; 8080 is its default and the local fallback.
EXPOSE 8080
# JSON form so signals reach the process; `exec` inside sh replaces the shell,
# which is what lets Cloud Run's SIGTERM shut uvicorn down cleanly. The shell
# is only there to expand $PORT.
#
# Deliberately no --proxy-headers. With --forwarded-allow-ips='*' uvicorn
# rewrites the client address from the LEFT-most X-Forwarded-For entry,
# which any visitor can set. security.client_identity() reads the header
# itself and takes the right-most entry instead -- the one Google's front
# end appended. See TRUSTED_PROXY_HOPS in security.py.
CMD ["sh", "-c", "exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080}"]
