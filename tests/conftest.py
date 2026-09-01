import os
import tempfile

# Must run before anything under app/ is imported anywhere in the test
# session (app.config reads these at import time), otherwise app.db would
# fall back to the default sqlite+aiosqlite:///./data/bot.db and create a
# stray data/ directory in the repo when tests import app.models.
os.environ.setdefault("BOT_TOKEN", "123456:test-token")
os.environ.setdefault("ADMIN_USERNAME", "test")
os.environ.setdefault("ADMIN_PASSWORD", "test-password-12345")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{tempfile.mktemp(suffix='.db')}")
