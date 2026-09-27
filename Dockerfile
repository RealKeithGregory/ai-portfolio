# Container image for Google Cloud Run.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# The application owns nothing it needs to write, so it runs unprivileged.
RUN useradd --create-home --uid 1001 portfolio
USER portfolio

ENV APP_ENV=production

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
