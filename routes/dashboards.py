from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from database import db
from models import (Account, Opportunity, Contract, Renewal, CustomerHealth,
                    Activity, Meeting, Task, User, Role, Email, Notification)

dash_bp = Blueprint("dash", __name__)
TODAY = date.today

OPEN_STAGES = ["Lead", "Qualified", "Discovery", "Proposal", "Negotiation"]


def _open_opps():
    return Opportunity.query.filter(Opportunity.stage.in_(OPEN_STAGES))


def kpis_company():
    arr = db.session.query(func.sum(Account.arr)).filter(Account.is_customer == True).scalar() or 0
    pipeline = db.session.query(func.sum(Opportunity.amount)).filter(Opportunity.stage.in_(OPEN_STAGES)).scalar() or 0
    weighted = db.session.query(func.sum(Opportunity.amount * Opportunity.probability / 100)) \
        .filter(Opportunity.stage.in_(OPEN_STAGES)).scalar() or 0
    q_start = date(TODAY().year, 3 * ((TODAY().month - 1) // 3) + 1, 1)
    bookings = db.session.query(func.sum(Opportunity.amount)).filter(
        Opportunity.stage == "Closed Won", Opportunity.closed_at >= q_start).scalar() or 0
    renewals_90 = db.session.query(func.sum(Renewal.amount)).filter(
        Renewal.renewal_date.between(TODAY(), TODAY() + timedelta(days=90)),
        Renewal.status.in_(["Upcoming", "In Progress", "At Risk"])).scalar() or 0
    expansion = db.session.query(func.sum(Opportunity.amount)).filter(
        Opportunity.stage.in_(OPEN_STAGES), Opportunity.opp_type == "Expansion").scalar() or 0
    health_counts = dict(db.session.query(CustomerHealth.status, func.count()).group_by(CustomerHealth.status).all())
    return dict(arr=arr, mrr=arr / 12, pipeline=pipeline, forecast=weighted, bookings=bookings,
                renewals_90=renewals_90, expansion=expansion, health=health_counts)


@dash_bp.route("/")
@login_required
def home():
    slug = current_user.active_role_slug or (current_user.role.slug if current_user.role else "sales_rep")
    view = {"ceo": ceo, "vp_sales": vp_sales, "sales_rep": sales_rep, "csm": csm,
            "finance": finance, "sales_ops": sales_ops, "exec_assistant": exec_assistant}.get(slug)
    return view() if view else sales_rep()


def ceo():
    k = kpis_company()
    top_risks = (db.session.query(Account, CustomerHealth)
                 .join(CustomerHealth, CustomerHealth.account_id == Account.id)
                 .filter(CustomerHealth.status == "Red").order_by(Account.arr.desc()).limit(6).all())
    expansion_opps = (_open_opps().filter(Opportunity.opp_type == "Expansion")
                      .order_by(Opportunity.amount.desc()).limit(6).all())
    upcoming_renewals = (Renewal.query.filter(Renewal.renewal_date >= TODAY(),
                                              Renewal.status.in_(["Upcoming", "In Progress", "At Risk"]))
                         .order_by(Renewal.renewal_date).limit(8).all())
    return render_template("dashboards/ceo.html", k=k, top_risks=top_risks,
                           expansion_opps=expansion_opps, upcoming_renewals=upcoming_renewals)


def vp_sales():
    k = kpis_company()
    reps = User.query.join(Role).filter(Role.slug == "sales_rep").all()
    leaderboard = []
    for r in reps:
        won = db.session.query(func.sum(Opportunity.amount)).filter(
            Opportunity.owner_id == r.id, Opportunity.stage == "Closed Won").scalar() or 0
        pipe = db.session.query(func.sum(Opportunity.amount)).filter(
            Opportunity.owner_id == r.id, Opportunity.stage.in_(OPEN_STAGES)).scalar() or 0
        leaderboard.append(dict(rep=r, won=won, pipe=pipe,
                                attain=(won / r.quota * 100) if r.quota else 0))
    leaderboard.sort(key=lambda x: -x["won"])
    won_n = Opportunity.query.filter_by(stage="Closed Won").count()
    lost_n = Opportunity.query.filter_by(stage="Closed Lost").count()
    win_rate = won_n / (won_n + lost_n) * 100 if (won_n + lost_n) else 0
    avg_deal = db.session.query(func.avg(Opportunity.amount)).filter(Opportunity.stage == "Closed Won").scalar() or 0
    likely = _open_opps().filter(Opportunity.ai_score >= 75).order_by(Opportunity.amount.desc()).limit(5).all()
    at_risk = _open_opps().filter(Opportunity.ai_score <= 35).order_by(Opportunity.amount.desc()).limit(5).all()
    recent_activity = Activity.query.order_by(Activity.activity_date.desc()).limit(10).all()
    return render_template("dashboards/vp_sales.html", k=k, leaderboard=leaderboard[:10],
                           win_rate=win_rate, avg_deal=avg_deal, likely=likely, at_risk=at_risk,
                           recent_activity=recent_activity)


def sales_rep():
    uid = current_user.id
    my_opps = _open_opps().filter(Opportunity.owner_id == uid).order_by(Opportunity.expected_close).all()
    if not my_opps:  # demo fallback so any user sees data
        my_opps = _open_opps().order_by(Opportunity.expected_close).limit(12).all()
    my_pipe = sum(o.amount for o in my_opps)
    won = db.session.query(func.sum(Opportunity.amount)).filter(
        Opportunity.owner_id == uid, Opportunity.stage == "Closed Won").scalar() or 0
    tasks = (Task.query.filter(Task.owner_id == uid, Task.status == "Open").order_by(Task.due_date).limit(8).all()
             or Task.query.filter(Task.status == "Open").order_by(Task.due_date).limit(8).all())
    meetings = (Meeting.query.filter(Meeting.start_time >= datetime.utcnow())
                .order_by(Meeting.start_time).limit(6).all())
    accounts = Account.query.filter_by(owner_id=uid).limit(8).all() or Account.query.limit(8).all()
    emails = Email.query.order_by(Email.sent_at.desc()).limit(6).all()
    activities = Activity.query.filter_by(user_id=uid).order_by(Activity.activity_date.desc()).limit(8).all() \
        or Activity.query.order_by(Activity.activity_date.desc()).limit(8).all()
    return render_template("dashboards/sales_rep.html", my_opps=my_opps[:10], my_pipe=my_pipe, won=won,
                           tasks=tasks, meetings=meetings, accounts=accounts, emails=emails,
                           activities=activities, quota=current_user.quota or 1_500_000)


def csm():
    uid = current_user.id
    my_accounts = Account.query.filter_by(csm_id=uid).all() or Account.query.filter_by(is_customer=True).limit(25).all()
    ids = [a.id for a in my_accounts]
    healths = {h.account_id: h for h in CustomerHealth.query.filter(CustomerHealth.account_id.in_(ids)).all()}
    renewals = (Renewal.query.filter(Renewal.account_id.in_(ids), Renewal.renewal_date >= TODAY())
                .order_by(Renewal.renewal_date).limit(10).all())
    qbrs = (Meeting.query.filter(Meeting.meeting_type == "QBR", Meeting.start_time >= datetime.utcnow())
            .order_by(Meeting.start_time).limit(6).all())
    green = sum(1 for h in healths.values() if h.status == "Green")
    yellow = sum(1 for h in healths.values() if h.status == "Yellow")
    red = sum(1 for h in healths.values() if h.status == "Red")
    expansion = (_open_opps().filter(Opportunity.account_id.in_(ids), Opportunity.opp_type == "Expansion")
                 .order_by(Opportunity.amount.desc()).limit(6).all())
    book = sum(a.arr for a in my_accounts)
    return render_template("dashboards/csm.html", my_accounts=my_accounts, healths=healths,
                           renewals=renewals, qbrs=qbrs, green=green, yellow=yellow, red=red,
                           expansion=expansion, book=book)


def finance():
    k = kpis_company()
    contracts = Contract.query.filter_by(status="Active").all()
    billings = sum(c.value / c.term_months * 12 for c in contracts)
    late = [c for c in contracts if c.payment_status == "Late"]
    delinquent = [c for c in contracts if c.payment_status == "Delinquent"]
    upcoming_renewals = (Renewal.query.filter(Renewal.renewal_date >= TODAY())
                         .order_by(Renewal.renewal_date).limit(10).all())
    collections_pct = (1 - (len(late) + len(delinquent)) / max(1, len(contracts))) * 100
    return render_template("dashboards/finance.html", k=k, billings=billings, late=late,
                           delinquent=delinquent, upcoming_renewals=upcoming_renewals,
                           n_contracts=len(contracts), collections_pct=collections_pct)


def sales_ops():
    missing_next = _open_opps().filter((Opportunity.next_step == None) | (Opportunity.next_step == "")).count()
    missing_comp = _open_opps().filter(Opportunity.competitor == None).count()
    stale_date = datetime.utcnow() - timedelta(days=120)
    inactive = _open_opps().filter(Opportunity.created_at < stale_date).order_by(Opportunity.amount.desc()).limit(10).all()
    # naive duplicate detection: same first word
    accounts = Account.query.all()
    seen, dupes = {}, []
    for a in accounts:
        key = a.name.split()[0]
        if key in seen:
            dupes.append((seen[key], a))
        else:
            seen[key] = a
    stage_counts = dict(db.session.query(Opportunity.stage, func.count())
                        .filter(Opportunity.stage.in_(OPEN_STAGES)).group_by(Opportunity.stage).all())
    region_pipe = (db.session.query(Account.region, func.sum(Opportunity.amount))
                   .join(Opportunity, Opportunity.account_id == Account.id)
                   .filter(Opportunity.stage.in_(OPEN_STAGES)).group_by(Account.region).all())
    open_total = _open_opps().count()
    return render_template("dashboards/sales_ops.html", missing_next=missing_next,
                           missing_comp=missing_comp, inactive=inactive, dupes=dupes[:8],
                           stage_counts=stage_counts, region_pipe=region_pipe, open_total=open_total,
                           forecast_accuracy=91.4)


def exec_assistant():
    exec_meetings = (Meeting.query.filter(Meeting.is_executive == True, Meeting.start_time >= datetime.utcnow())
                     .order_by(Meeting.start_time).limit(8).all())
    top_customers = Account.query.filter_by(is_customer=True).order_by(Account.arr.desc()).limit(8).all()
    upcoming_renewals = (Renewal.query.filter(Renewal.renewal_date >= TODAY())
                         .order_by(Renewal.renewal_date).limit(8).all())
    escalations = (db.session.query(Account, CustomerHealth)
                   .join(CustomerHealth, CustomerHealth.account_id == Account.id)
                   .filter(CustomerHealth.status == "Red").order_by(Account.arr.desc()).limit(6).all())
    return render_template("dashboards/exec_assistant.html", exec_meetings=exec_meetings,
                           top_customers=top_customers, upcoming_renewals=upcoming_renewals,
                           escalations=escalations)


@dash_bp.route("/briefing")
@login_required
def briefing():
    k = kpis_company()
    since = datetime.utcnow() - timedelta(hours=48)
    new_won = Opportunity.query.filter(Opportunity.stage == "Closed Won",
                                       Opportunity.closed_at >= TODAY() - timedelta(days=7)).limit(5).all()
    recent_meetings = Meeting.query.filter(Meeting.start_time.between(datetime.utcnow(), datetime.utcnow() + timedelta(days=2))) \
        .order_by(Meeting.start_time).limit(6).all()
    health_drops = (db.session.query(Account, CustomerHealth)
                    .join(CustomerHealth, CustomerHealth.account_id == Account.id)
                    .filter(CustomerHealth.trend == "down").order_by(Account.arr.desc()).limit(6).all())
    renewals_30 = Renewal.query.filter(Renewal.renewal_date.between(TODAY(), TODAY() + timedelta(days=30))) \
        .order_by(Renewal.renewal_date).all()
    recent_activity = Activity.query.filter(Activity.activity_date >= since) \
        .order_by(Activity.activity_date.desc()).limit(10).all()
    return render_template("briefing.html", k=k, new_won=new_won, recent_meetings=recent_meetings,
                           health_drops=health_drops, renewals_30=renewals_30, recent_activity=recent_activity,
                           mp_windows=current_app.config["MEETING_PREP_WINDOWS"])


@dash_bp.route("/scenarios")
@login_required
def scenarios():
    open_opps = _open_opps().all()
    pipe = sum(o.amount for o in open_opps)
    weighted = sum(o.amount * o.probability / 100 for o in open_opps)
    renewals = Renewal.query.filter(Renewal.renewal_date.between(TODAY(), TODAY() + timedelta(days=180)),
                                    Renewal.status.in_(["Upcoming", "In Progress", "At Risk"])).all()
    renew_base = sum(r.amount for r in renewals)
    renew_weighted = sum(r.amount * r.likelihood / 100 for r in renewals)
    at_risk_amt = sum(r.amount for r in renewals if r.likelihood < 60)
    return render_template("scenarios.html", pipe=pipe, weighted=weighted, n_open=len(open_opps),
                           renew_base=renew_base, renew_weighted=renew_weighted,
                           n_renewals=len(renewals), at_risk_amt=at_risk_amt)
