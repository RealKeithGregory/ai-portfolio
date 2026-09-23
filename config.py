"""Environment-driven settings.

The only setting is which environment the app is running in. Production
values come from real environment variables set by the deployment platform;
`.env.example` lists every variable the app reads. There is deliberately no
secret here: the site has no API keys, no database, and no third-party
service to authenticate against.
"""

import os

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()

# Production is assumed to be served over HTTPS by the platform's proxy.
# That assumption gates HSTS and the interactive API docs, so it must never
# be the default -- a misread variable has to fail towards development.
IS_PRODUCTION = APP_ENV == "production"
