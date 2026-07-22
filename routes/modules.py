from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from database import db
from models import (Account, Contact, Opportunity, Product, Contract, Renewal,
                    Activity, Meeting, Task, Note, CustomerHealth, UsageMetric,
                    Email, Notification, User, Role, AIHistory)

mod_bp = Blueprint("mod", __name__)
OPEN_STAGES = ["Lead", "Qualified", "Discovery", "Proposal", "Negotiation"]


@mod_bp.route("/accounts")
@login_required
def accounts():
    q = Account.query
    seg = request.args.get("segment")
    region = request.args.get("region")
    kind = request.args.get("type")
    if seg: q = q.filter_by(segment=seg)
    if region: q = q.filter_by(region=region)
    if kind == "customer": q = q.filter_by(is_customer=True)
    if kind == "prospect": q = q.filter_by(is_customer=False)
    rows = q.order_by(Account.arr.desc()).all()
    healths = {h.account_id: h for h in CustomerHealth.query.all()}
    return render_template("accounts.html", rows=rows, healths=healths)


@mod_bp.route("/accounts/<int:account_id>")
@login_required
def account_360(account_id):
    a = db.session.get(Account, account_id) or Account.query.first()
    h = a.health
    open_opps = [o for o in a.opportunities if o.stage in OPEN_STAGES]
    renewals = Renewal.query.filter_by(account_id=a.id).order_by(Renewal.renewal_date).all()
    meetings = (Meeting.query.filter_by(account_id=a.id).order_by(Meeting.start_time.desc()).limit(8).all())
    activities = (Activity.query.filter_by(account_id=a.id).order_by(Activity.activity_date.desc()).limit(10).all())
    notes = Note.query.filter_by(account_id=a.id).order_by(Note.created_at.desc()).limit(5).all()
    emails = Email.query.filter_by(account_id=a.id).order_by(Email.sent_at.desc()).limit(5).all()
    usage = (UsageMetric.query.filter_by(account_id=a.id).order_by(UsageMetric.metric_date).all())
    sponsors = [c for c in a.contacts if c.is_executive_sponsor]
    expansion = [o for o in open_opps if o.opp_type == "Expansion"]
    risk_score = 100 - (h.score if h else 70)
    suggested = []
    if h and h.status == "Red":
        suggested = ["Schedule executive save-play meeting this week",
                     "Launch adoption recovery plan with CSM",
                     "Review open support escalations before renewal call"]
    elif h and h.status == "Yellow":
        suggested = ["Book QBR within 30 days", "Run admin training refresh",
                     "Confirm executive sponsor engagement"]
    else:
        suggested = ["Propose Data Apps expansion", "Capture reference / case study",
                     "Introduce AI Insights Engine in next sync"]
    return render_template("account_360.html", a=a, h=h, open_opps=open_opps, renewals=renewals,
                           meetings=meetings, activities=activities, notes=notes, emails=emails,
                           usage=usage, sponsors=sponsors, expansion=expansion,
                           risk_score=risk_score, suggested=suggested)


@mod_bp.route("/contacts")
@login_required
def contacts():
    rows = Contact.query.order_by(Contact.last_name).limit(500).all()
    return render_template("contacts.html", rows=rows)


@mod_bp.route("/leads")
@login_required
def leads():
    rows = Opportunity.query.filter(Opportunity.stage.in_(["Lead", "Qualified"])) \
        .order_by(Opportunity.created_at.desc()).all()
    return render_template("leads.html", rows=rows)


@mod_bp.route("/opportunities")
@login_required
def opportunities():
    view = request.args.get("view", "kanban")
    stage = request.args.get("stage")
    q = Opportunity.query
    if stage:
        q = q.filter_by(stage=stage)
    rows = q.order_by(Opportunity.amount.desc()).limit(600).all()
    by_stage = {s: [] for s in OPEN_STAGES + ["Closed Won"]}
    for o in rows:
        if o.stage in by_stage and len(by_stage[o.stage]) < 12:
            by_stage[o.stage].append(o)
    stage_totals = {s: db.session.query(func.sum(Opportunity.amount)).filter(Opportunity.stage == s).scalar() or 0
                    for s in by_stage}
    return render_template("opportunities.html", rows=rows[:300], by_stage=by_stage,
                           stage_totals=stage_totals, view=view, stages=OPEN_STAGES)


@mod_bp.route("/activities")
@login_required
def activities():
    rows = Activity.query.order_by(Activity.activity_date.desc()).limit(300).all()
    return render_template("activities.html", rows=rows)


@mod_bp.route("/contracts")
@login_required
def contracts():
    rows = Contract.query.order_by(Contract.end_date).all()
    return render_template("contracts.html", rows=rows)


@mod_bp.route("/renewals")
@login_required
def renewals():
    rows = Renewal.query.order_by(Renewal.renewal_date).all()
    today = date.today()
    upcoming = [r for r in rows if r.renewal_date and r.renewal_date >= today]
    past = [r for r in rows if r.renewal_date and r.renewal_date < today][::-1]  # most recent first
    # group next 6 months for calendar strip
    months = []
    for i in range(6):
        m = (date.today().month - 1 + i) % 12 + 1
        y = date.today().year + (date.today().month - 1 + i) // 12
        amt = sum(r.amount for r in upcoming if r.renewal_date.month == m and r.renewal_date.year == y)
        cnt = sum(1 for r in upcoming if r.renewal_date.month == m and r.renewal_date.year == y)
        months.append(dict(label=date(y, m, 1).strftime("%b %Y"), amount=amt, count=cnt))
    return render_template("renewals.html", upcoming_rows=upcoming[:300],
                           past_rows=past[:300], months=months,
                           rn_windows=current_app.config["RENEWAL_WINDOWS"])


@mod_bp.route("/customer-success")
@login_required
def customer_success():
    pairs = (db.session.query(Account, CustomerHealth)
             .join(CustomerHealth, CustomerHealth.account_id == Account.id)
             .order_by(CustomerHealth.score).all())
    counts = {"Green": 0, "Yellow": 0, "Red": 0}
    for _, h in pairs:
        counts[h.status] = counts.get(h.status, 0) + 1
    return render_template("customer_success.html", pairs=pairs, counts=counts,
                           cs_limits=current_app.config["CHURN_LIMITS"])


@mod_bp.route("/products")
@login_required
def products():
    rows = Product.query.all()
    rev = {p.id: db.session.query(func.sum(Opportunity.amount)).filter(
        Opportunity.product_id == p.id, Opportunity.stage == "Closed Won").scalar() or 0 for p in rows}
    return render_template("products.html", rows=rows, rev=rev)


@mod_bp.route("/users")
@login_required
def users():
    rows = User.query.join(Role).filter(Role.slug != "employee").order_by(User.name).all()
    return render_template("users.html", rows=rows)


@mod_bp.route("/tasks")
@login_required
def tasks():
    rows = Task.query.order_by(Task.status.desc(), Task.due_date).limit(300).all()
    return render_template("tasks.html", rows=rows, today=date.today())


@mod_bp.route("/meetings")
@login_required
def meetings():
    upcoming = Meeting.query.filter(Meeting.start_time >= datetime.utcnow()).order_by(Meeting.start_time).limit(100).all()
    past = Meeting.query.filter(Meeting.start_time < datetime.utcnow()).order_by(Meeting.start_time.desc()).limit(100).all()
    return render_template("meetings.html", upcoming=upcoming, past=past)


@mod_bp.route("/notes")
@login_required
def notes():
    rows = Note.query.order_by(Note.created_at.desc()).limit(100).all()
    return render_template("notes.html", rows=rows)


@mod_bp.route("/notifications")
@login_required
def notifications():
    rows = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    for n in rows:
        n.is_read = True
    db.session.commit()
    return render_template("notifications.html", rows=rows)


@mod_bp.route("/reports")
@login_required
def reports():
    return render_template("reports.html")


@mod_bp.route("/ai-chat")
@login_required
def ai_chat():
    history = AIHistory.query.filter_by(user_id=current_user.id).order_by(AIHistory.created_at.desc()).limit(10).all()
    return render_template("ai_chat.html", history=history)


@mod_bp.route("/search")
@login_required
def search():
    term = request.args.get("q", "").strip()
    like = f"%{term}%"
    results = dict(accounts=[], contacts=[], opportunities=[], contracts=[], users=[], tasks=[], meetings=[])
    if term:
        results["accounts"] = Account.query.filter(Account.name.ilike(like)).limit(10).all()
        results["contacts"] = Contact.query.filter(or_(Contact.first_name.ilike(like),
                                                       Contact.last_name.ilike(like),
                                                       Contact.email.ilike(like))).limit(10).all()
        results["opportunities"] = Opportunity.query.filter(Opportunity.name.ilike(like)).limit(10).all()
        results["contracts"] = Contract.query.filter(Contract.number.ilike(like)).limit(10).all()
        results["users"] = User.query.filter(or_(User.name.ilike(like), User.email.ilike(like))).limit(10).all()
        results["tasks"] = Task.query.filter(Task.title.ilike(like)).limit(10).all()
        results["meetings"] = Meeting.query.filter(Meeting.title.ilike(like)).limit(10).all()
    total = sum(len(v) for v in results.values())
    return render_template("search.html", term=term, results=results, total=total)
