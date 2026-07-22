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
    # Renewal agent
    REFOLD_RENEWAL_WORKFLOW_ID = os.environ.get("REFOLD_RENEWAL_WORKFLOW_ID", "6a60aa5b3284520f75231770")
    REFOLD_RENEWAL_SLUG = os.environ.get("REFOLD_RENEWAL_SLUG", "Coba-8517")
    # Churn Sentinel agent
    REFOLD_CHURN_WORKFLOW_ID = os.environ.get("REFOLD_CHURN_WORKFLOW_ID", "6a60c26a3284520f75282851")
    REFOLD_CHURN_SLUG = os.environ.get("REFOLD_CHURN_SLUG", "Coba-8517")
    # Briefing agent
    REFOLD_BRIEFING_WORKFLOW_ID = os.environ.get("REFOLD_BRIEFING_WORKFLOW_ID", "6a60e4013284520f752b331c")
    REFOLD_BRIEFING_SLUG = os.environ.get("REFOLD_BRIEFING_SLUG", "Coba-8517")
    # Pipeline Hygiene agent
    REFOLD_PIPELINE_WORKFLOW_ID = os.environ.get("REFOLD_PIPELINE_WORKFLOW_ID", "6a61064a3284520f752f06b2")
    REFOLD_PIPELINE_SLUG = os.environ.get("REFOLD_PIPELINE_SLUG", "Coba-8517")
    # Forecast agent
    REFOLD_FORECAST_WORKFLOW_ID = os.environ.get("REFOLD_FORECAST_WORKFLOW_ID", "6a610c2e3284520f7530adc0")
    REFOLD_FORECAST_SLUG = os.environ.get("REFOLD_FORECAST_SLUG", "Coba-8517")
    REFOLD_CONFIG_ID = os.environ.get("REFOLD_CONFIG_ID", "")                   # optional per-run config
    REFOLD_HTTP_TIMEOUT = int(os.environ.get("REFOLD_HTTP_TIMEOUT", "30"))      # per-request seconds
    MEETING_PREP_WINDOWS = [4, 8, 24, 48]  # selectable time windows (hours)
    RENEWAL_WINDOWS = [15, 30, 60, 90, 180]  # selectable renewal windows (days)
    CHURN_LIMITS = [5, 10, 15, 20]           # selectable # of riskiest accounts to sweep
    BRIEFING_WINDOWS = [1, 7, 14, 30]        # selectable briefing look-back windows (days)
    PIPELINE_LIMITS = [5, 10, 15, 20]        # selectable # of messiest deals to sweep
    FORECAST_WINDOWS = [30, 60, 90, 180]     # selectable forecast horizons (days)
