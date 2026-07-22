import os

# Load a local .env (gitignored) for development secrets. No-op in production,
# where the host (Railway/Render) injects real env vars — so this never reads a
# committed secret. Safe if python-dotenv or the file is absent.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "cloudvision-demo-secret-key")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "crm_demo.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    COMPANY_NAME = "CloudVision Analytics"
    DEMO_PASSWORD = "demo123"

    # --- Agent layer ---
    AGENT_EMAIL = "agent@cloudvision.com"
    AGENT_API_TOKEN = os.environ.get("AGENT_API_TOKEN", "refold-demo-agent-token")
    AGENTS_ENABLED = os.environ.get("AGENTS_ENABLED", "1") == "1"  # global kill switch

    # --- Refold (Cobalt) workflow integration ---
    # The CRM only fires the workflow and polls for its result; Refold owns the
    # LLM node and calls back into /api/agent/* for context. API key + linked
    # account are shared credentials, configured globally via env.
    REFOLD_API_BASE = os.environ.get("REFOLD_API_BASE", "https://cobalt-skc.uscentral1.gocobalt.io")
    REFOLD_API_KEY = os.environ.get("REFOLD_API_KEY", "")                      # global — X-API-Key (secret, env-only)
    REFOLD_LINKED_ACCOUNT_ID = os.environ.get("REFOLD_LINKED_ACCOUNT_ID", "")  # global — linked_account_id (env-only)
    REFOLD_MEETING_PREP_WORKFLOW_ID = os.environ.get("REFOLD_MEETING_PREP_WORKFLOW_ID", "6a5f73903284520f7515020f")
    REFOLD_MEETING_PREP_SLUG = os.environ.get("REFOLD_MEETING_PREP_SLUG", "Coba-8517")
    # Renewal agent — set once the Cobalt workflow exists (empty → button reports "not configured")
    REFOLD_RENEWAL_WORKFLOW_ID = os.environ.get("REFOLD_RENEWAL_WORKFLOW_ID", "")
    REFOLD_RENEWAL_SLUG = os.environ.get("REFOLD_RENEWAL_SLUG", "")
    REFOLD_CONFIG_ID = os.environ.get("REFOLD_CONFIG_ID", "")                   # optional per-run config
    REFOLD_HTTP_TIMEOUT = int(os.environ.get("REFOLD_HTTP_TIMEOUT", "30"))      # per-request seconds
    MEETING_PREP_WINDOWS = [4, 8, 24, 48]  # selectable time windows (hours)
    RENEWAL_WINDOWS = [30, 60, 90, 180]    # selectable renewal windows (days)
