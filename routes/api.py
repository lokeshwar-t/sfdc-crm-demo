from datetime import date, timedelta
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import func
from database import db
from models import Account, Opportunity, Renewal, CustomerHealth, User, Role, UsageMetric
import ai_service

api_bp = Blueprint("api", __name__, url_prefix="/api")
OPEN_STAGES = ["Lead", "Qualified", "Discovery", "Proposal", "Negotiation"]


@api_bp.route("/ai/chat", methods=["POST"])
@login_required
def ai_chat():
    data = request.get_json(force=True)
    prompt = data.get("prompt", "")
    account = None
    if data.get("account_id"):
        account = db.session.get(Account, int(data["account_id"]))
    answer = ai_service.ask(prompt, user=current_user, account=account,
                            context_label=data.get("context", "global"))
    return jsonify({"response": answer})


# ---------------- chart data ----------------

@api_bp.route("/charts/arr-growth")
@login_required
def arr_growth():
    total_arr = db.session.query(func.sum(Account.arr)).filter(Account.is_customer == True).scalar() or 0
    labels, values = [], []
    growth = [0.55, 0.60, 0.66, 0.71, 0.76, 0.80, 0.84, 0.88, 0.91, 0.94, 0.97, 1.0]
    today = date.today()
    for i, g in enumerate(growth):
        m = today - timedelta(days=30 * (11 - i))
        labels.append(m.strftime("%b %y"))
        values.append(round(total_arr * g / 1_000_000, 2))
    return jsonify({"labels": labels, "values": values})


@api_bp.route("/charts/pipeline-funnel")
@login_required
def pipeline_funnel():
    rows = (db.session.query(Opportunity.stage, func.sum(Opportunity.amount))
            .filter(Opportunity.stage.in_(OPEN_STAGES)).group_by(Opportunity.stage).all())
    d = dict(rows)
    return jsonify({"labels": OPEN_STAGES,
                    "values": [round((d.get(s) or 0) / 1_000_000, 2) for s in OPEN_STAGES]})


@api_bp.route("/charts/renewal-calendar")
@login_required
def renewal_calendar():
    labels, values = [], []
    today = date.today()
    for i in range(6):
        m = (today.month - 1 + i) % 12 + 1
        y = today.year + (today.month - 1 + i) // 12
        start, end = date(y, m, 1), (date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1))
        amt = db.session.query(func.sum(Renewal.amount)).filter(
            Renewal.renewal_date >= start, Renewal.renewal_date < end).scalar() or 0
        labels.append(start.strftime("%b %Y"))
        values.append(round(amt / 1_000_000, 2))
    return jsonify({"labels": labels, "values": values})


@api_bp.route("/charts/regional-revenue")
@login_required
def regional_revenue():
    rows = (db.session.query(Account.region, func.sum(Account.arr))
            .filter(Account.is_customer == True).group_by(Account.region).all())
    return jsonify({"labels": [r[0] for r in rows],
                    "values": [round((r[1] or 0) / 1_000_000, 2) for r in rows]})


@api_bp.route("/charts/industry-revenue")
@login_required
def industry_revenue():
    rows = (db.session.query(Account.industry, func.sum(Account.arr))
            .filter(Account.is_customer == True).group_by(Account.industry)
            .order_by(func.sum(Account.arr).desc()).all())
    return jsonify({"labels": [r[0] for r in rows],
                    "values": [round((r[1] or 0) / 1_000_000, 2) for r in rows]})


@api_bp.route("/charts/health-distribution")
@login_required
def health_distribution():
    rows = dict(db.session.query(CustomerHealth.status, func.count()).group_by(CustomerHealth.status).all())
    return jsonify({"labels": ["Green", "Yellow", "Red"],
                    "values": [rows.get("Green", 0), rows.get("Yellow", 0), rows.get("Red", 0)]})


@api_bp.route("/charts/segmentation")
@login_required
def segmentation():
    rows = (db.session.query(Account.segment, func.count())
            .filter(Account.is_customer == True).group_by(Account.segment).all())
    return jsonify({"labels": [r[0] for r in rows], "values": [r[1] for r in rows]})


@api_bp.route("/charts/top-products")
@login_required
def top_products():
    from models import Product
    rows = (db.session.query(Product.name, func.sum(Opportunity.amount))
            .join(Opportunity, Opportunity.product_id == Product.id)
            .filter(Opportunity.stage == "Closed Won").group_by(Product.name)
            .order_by(func.sum(Opportunity.amount).desc()).all())
    return jsonify({"labels": [r[0] for r in rows],
                    "values": [round((r[1] or 0) / 1_000_000, 2) for r in rows]})


@api_bp.route("/charts/quota-attainment")
@login_required
def quota_attainment():
    reps = User.query.join(Role).filter(Role.slug == "sales_rep").limit(10).all()
    labels, values = [], []
    for r in reps:
        won = db.session.query(func.sum(Opportunity.amount)).filter(
            Opportunity.owner_id == r.id, Opportunity.stage == "Closed Won").scalar() or 0
        labels.append(r.name.split()[0])
        values.append(round(won / r.quota * 100, 1) if r.quota else 0)
    return jsonify({"labels": labels, "values": values})


@api_bp.route("/charts/usage/<int:account_id>")
@login_required
def usage(account_id):
    rows = (UsageMetric.query.filter_by(account_id=account_id)
            .order_by(UsageMetric.metric_date).all())
    return jsonify({"labels": [u.metric_date.strftime("%b %d") for u in rows],
                    "values": [u.active_users for u in rows]})


@api_bp.route("/charts/revenue-trend")
@login_required
def revenue_trend():
    labels, bookings, billings = [], [], []
    today = date.today()
    for i in range(8):
        end = today - timedelta(days=30 * (7 - i))
        start = end - timedelta(days=30)
        amt = db.session.query(func.sum(Opportunity.amount)).filter(
            Opportunity.stage == "Closed Won",
            Opportunity.closed_at >= start, Opportunity.closed_at < end).scalar() or 0
        labels.append(end.strftime("%b"))
        bookings.append(round(amt / 1_000_000, 2))
        billings.append(round(amt / 1_000_000 * 0.92, 2))
    return jsonify({"labels": labels, "bookings": bookings, "billings": billings})


@api_bp.route("/scenario", methods=["POST"])
@login_required
def scenario():
    d = request.get_json(force=True)
    win_adj = float(d.get("win_adj", 0))        # -20..+20 pct points
    renew_adj = float(d.get("renew_adj", 0))
    deal_adj = float(d.get("deal_adj", 0))      # % change in deal size
    opps = Opportunity.query.filter(Opportunity.stage.in_(OPEN_STAGES)).all()
    pipeline = sum(o.amount * (1 + deal_adj / 100) for o in opps)
    forecast = sum(o.amount * (1 + deal_adj / 100) * min(100, max(0, o.probability + win_adj)) / 100 for o in opps)
    renewals = Renewal.query.filter(Renewal.renewal_date >= date.today(),
                                    Renewal.renewal_date <= date.today() + timedelta(days=180),
                                    Renewal.status.in_(["Upcoming", "In Progress", "At Risk"])).all()
    renew_forecast = sum(r.amount * min(100, max(0, r.likelihood + renew_adj)) / 100 for r in renewals)
    renew_base = sum(r.amount for r in renewals)
    return jsonify({
        "pipeline": pipeline, "forecast": forecast,
        "renew_base": renew_base, "renew_forecast": renew_forecast,
        "churn_exposure": renew_base - renew_forecast,
        "total_outlook": forecast + renew_forecast,
    })
