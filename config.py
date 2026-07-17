import os

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
