from datetime import datetime, date
from flask_login import UserMixin
from database import db


class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)   # e.g. CEO
    slug = db.Column(db.String(50), unique=True, nullable=False)   # e.g. ceo
    description = db.Column(db.String(255))
    users = db.relationship("User", backref="role", lazy=True)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), default="demo123")
    title = db.Column(db.String(120))
    region = db.Column(db.String(60))
    phone = db.Column(db.String(40))
    quota = db.Column(db.Float, default=0)
    avatar_color = db.Column(db.String(10), default="#6366f1")
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"))
    active_role_slug = db.Column(db.String(50))  # for role switching
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def initials(self):
        parts = self.name.split()
        return (parts[0][0] + parts[-1][0]).upper() if len(parts) > 1 else parts[0][:2].upper()


class Account(db.Model):
    __tablename__ = "accounts"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    industry = db.Column(db.String(80))
    region = db.Column(db.String(60))
    segment = db.Column(db.String(40))          # Enterprise / Mid-Market / SMB
    website = db.Column(db.String(150))
    employees = db.Column(db.Integer)
    arr = db.Column(db.Float, default=0)
    is_customer = db.Column(db.Boolean, default=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    csm_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owner = db.relationship("User", foreign_keys=[owner_id])
    csm = db.relationship("User", foreign_keys=[csm_id])
    contacts = db.relationship("Contact", backref="account", lazy=True)
    opportunities = db.relationship("Opportunity", backref="account", lazy=True)
    contracts = db.relationship("Contract", backref="account", lazy=True)
    health = db.relationship("CustomerHealth", backref="account", uselist=False, lazy=True)


class Contact(db.Model):
    __tablename__ = "contacts"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(60))
    last_name = db.Column(db.String(60))
    title = db.Column(db.String(120))
    email = db.Column(db.String(150))
    phone = db.Column(db.String(40))
    is_executive_sponsor = db.Column(db.Boolean, default=False)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80))
    list_price = db.Column(db.Float)
    description = db.Column(db.String(255))


class Opportunity(db.Model):
    __tablename__ = "opportunities"
    STAGES = ["Lead", "Qualified", "Discovery", "Proposal", "Negotiation", "Closed Won", "Closed Lost"]
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    stage = db.Column(db.String(40), default="Lead")
    amount = db.Column(db.Float, default=0)
    probability = db.Column(db.Integer, default=10)
    expected_close = db.Column(db.Date)
    opp_type = db.Column(db.String(30), default="New Business")  # New Business / Expansion / Renewal
    competitor = db.Column(db.String(80))
    next_step = db.Column(db.String(200))
    ai_score = db.Column(db.Integer, default=50)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.Date)

    owner = db.relationship("User", foreign_keys=[owner_id])
    product = db.relationship("Product", foreign_keys=[product_id])


class Contract(db.Model):
    __tablename__ = "contracts"
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(30), unique=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    value = db.Column(db.Float)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    term_months = db.Column(db.Integer, default=36)
    status = db.Column(db.String(30), default="Active")  # Active / Expired / Pending
    payment_status = db.Column(db.String(30), default="Current")  # Current / Late / Delinquent
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Renewal(db.Model):
    __tablename__ = "renewals"
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    contract_id = db.Column(db.Integer, db.ForeignKey("contracts.id"))
    renewal_date = db.Column(db.Date)
    amount = db.Column(db.Float)
    status = db.Column(db.String(30), default="Upcoming")  # Upcoming / In Progress / Renewed / Churned / At Risk
    likelihood = db.Column(db.Integer, default=80)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    account = db.relationship("Account", foreign_keys=[account_id])
    contract = db.relationship("Contract", foreign_keys=[contract_id])
    owner = db.relationship("User", foreign_keys=[owner_id])


class Activity(db.Model):
    __tablename__ = "activities"
    id = db.Column(db.Integer, primary_key=True)
    activity_type = db.Column(db.String(30))  # Call / Email / Meeting / Demo / Note
    subject = db.Column(db.String(200))
    detail = db.Column(db.Text)
    activity_date = db.Column(db.DateTime, default=datetime.utcnow)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    opportunity_id = db.Column(db.Integer, db.ForeignKey("opportunities.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    account = db.relationship("Account", foreign_keys=[account_id])
    user = db.relationship("User", foreign_keys=[user_id])


class Meeting(db.Model):
    __tablename__ = "meetings"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    meeting_type = db.Column(db.String(40))  # QBR / Demo / Discovery / Executive / Kickoff
    start_time = db.Column(db.DateTime)
    duration_min = db.Column(db.Integer, default=60)
    location = db.Column(db.String(120), default="Zoom")
    is_executive = db.Column(db.Boolean, default=False)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    organizer_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    account = db.relationship("Account", foreign_keys=[account_id])
    organizer = db.relationship("User", foreign_keys=[organizer_id])


class Task(db.Model):
    __tablename__ = "tasks"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    due_date = db.Column(db.Date)
    priority = db.Column(db.String(20), default="Medium")
    status = db.Column(db.String(20), default="Open")  # Open / Done
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    account = db.relationship("Account", foreign_keys=[account_id])
    owner = db.relationship("User", foreign_keys=[owner_id])


class Note(db.Model):
    __tablename__ = "notes"
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    account = db.relationship("Account", foreign_keys=[account_id])
    author = db.relationship("User", foreign_keys=[author_id])


class CustomerHealth(db.Model):
    __tablename__ = "customer_health"
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), unique=True)
    score = db.Column(db.Integer, default=70)          # 0-100
    status = db.Column(db.String(10), default="Green")  # Green / Yellow / Red
    product_usage = db.Column(db.Integer, default=70)
    exec_meetings = db.Column(db.Integer, default=2)    # last 90 days
    training_completion = db.Column(db.Integer, default=60)
    nps = db.Column(db.Integer, default=30)
    adoption = db.Column(db.Integer, default=65)
    trend = db.Column(db.String(10), default="flat")    # up / down / flat
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class UsageMetric(db.Model):
    __tablename__ = "usage_metrics"
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    metric_date = db.Column(db.Date)
    active_users = db.Column(db.Integer)
    queries_run = db.Column(db.Integer)
    dashboards_viewed = db.Column(db.Integer)

    account = db.relationship("Account", foreign_keys=[account_id])


class Email(db.Model):
    __tablename__ = "emails"
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(200))
    snippet = db.Column(db.String(400))
    sender = db.Column(db.String(150))
    recipient = db.Column(db.String(150))
    sent_at = db.Column(db.DateTime)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    account = db.relationship("Account", foreign_keys=[account_id])


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    category = db.Column(db.String(40))  # Renewal / Contract / Health / Deal / Task / Meeting / Activity
    message = db.Column(db.String(300))
    link = db.Column(db.String(200))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AIHistory(db.Model):
    __tablename__ = "ai_history"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    prompt = db.Column(db.Text)
    response = db.Column(db.Text)
    context = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(200))
    entity = db.Column(db.String(60))
    entity_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AgentRun(db.Model):
    """Idempotency guard + audit trail for every agent execution."""
    __tablename__ = "agent_runs"
    id = db.Column(db.Integer, primary_key=True)
    agent_name = db.Column(db.String(50))
    entity_type = db.Column(db.String(40))
    entity_id = db.Column(db.Integer)
    window_key = db.Column(db.String(120))
    key = db.Column(db.String(220), unique=True, index=True)  # agent:entity:window
    status = db.Column(db.String(20), default="proposed")  # proposed/approved/auto/skipped/failed
    verdict_json = db.Column(db.Text)
    actions_json = db.Column(db.Text)
    trigger = db.Column(db.String(30), default="manual")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"))


class AgentDraft(db.Model):
    """Never-sent agent proposals awaiting human approval (the Approvals queue)."""
    __tablename__ = "agent_drafts"
    id = db.Column(db.Integer, primary_key=True)
    agent_name = db.Column(db.String(50))
    kind = db.Column(db.String(30))  # email / close_lost / merge / meeting
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    title = db.Column(db.String(200))
    payload_json = db.Column(db.Text)
    status = db.Column(db.String(20), default="draft")  # draft/approved/sent/rejected
    run_id = db.Column(db.Integer, db.ForeignKey("agent_runs.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    decided_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    decided_at = db.Column(db.DateTime)
