"""Edit routes for existing records + kanban stage-change API."""
from datetime import datetime, date
from flask import Blueprint, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from database import db
from models import Account, Contact, Opportunity, Task, AuditLog, Meeting, Renewal, CustomerHealth

edit_bp = Blueprint("edit", __name__, url_prefix="/edit")

STAGE_PROB = {"Lead": 10, "Qualified": 25, "Discovery": 45, "Proposal": 65,
              "Negotiation": 80, "Closed Won": 100, "Closed Lost": 0}
VALID_STAGES = list(STAGE_PROB.keys())


def _f(name, default=""):
    return (request.form.get(name) or default).strip()


def _date(name):
    v = _f(name)
    try:
        return datetime.strptime(v, "%Y-%m-%d").date() if v else None
    except ValueError:
        return None


def _audit(action, entity, entity_id):
    db.session.add(AuditLog(user_id=current_user.id, action=action, entity=entity, entity_id=entity_id))


def _back(fallback):
    return redirect(request.referrer or fallback)


@edit_bp.route("/account/<int:rid>", methods=["POST"])
@login_required
def account(rid):
    a = db.session.get(Account, rid)
    if not a:
        flash("Account not found.", "danger")
        return _back(url_for("mod.accounts"))
    a.name = _f("name") or a.name
    a.industry = _f("industry") or a.industry
    a.region = _f("region") or a.region
    a.segment = _f("segment") or a.segment
    a.website = _f("website") or a.website
    if _f("employees"): a.employees = int(_f("employees"))
    if _f("arr"): a.arr = float(_f("arr"))
    a.is_customer = _f("type") == "customer"
    _audit(f"Edited account {a.name}", "account", a.id)
    db.session.commit()
    flash(f"Account “{a.name}” updated.", "success")
    return _back(url_for("mod.account_360", account_id=a.id))


@edit_bp.route("/contact/<int:rid>", methods=["POST"])
@login_required
def contact(rid):
    c = db.session.get(Contact, rid)
    if not c:
        flash("Contact not found.", "danger")
        return _back(url_for("mod.contacts"))
    c.first_name = _f("first_name") or c.first_name
    c.last_name = _f("last_name") or c.last_name
    c.title = _f("title") or c.title
    c.email = _f("email") or c.email
    c.phone = _f("phone") or c.phone
    c.is_executive_sponsor = bool(request.form.get("is_executive_sponsor"))
    if _f("account_id"): c.account_id = int(_f("account_id"))
    _audit(f"Edited contact {c.name}", "contact", c.id)
    db.session.commit()
    flash(f"Contact “{c.name}” updated.", "success")
    return _back(url_for("mod.contacts"))


@edit_bp.route("/opportunity/<int:rid>", methods=["POST"])
@login_required
def opportunity(rid):
    o = db.session.get(Opportunity, rid)
    if not o:
        flash("Opportunity not found.", "danger")
        return _back(url_for("mod.opportunities"))
    o.name = _f("name") or o.name
    new_stage = _f("stage")
    if new_stage in VALID_STAGES and new_stage != o.stage:
        o.stage = new_stage
        o.probability = STAGE_PROB[new_stage]
        o.closed_at = date.today() if new_stage.startswith("Closed") else None
    if _f("amount"): o.amount = float(_f("amount"))
    o.opp_type = _f("opp_type") or o.opp_type
    o.competitor = _f("competitor") or None
    o.next_step = _f("next_step") or o.next_step
    if _date("expected_close"): o.expected_close = _date("expected_close")
    if _f("product_id"): o.product_id = int(_f("product_id"))
    _audit(f"Edited opportunity {o.name}", "opportunity", o.id)
    db.session.commit()
    flash(f"Opportunity “{o.name}” updated.", "success")
    return _back(url_for("mod.opportunities"))


@edit_bp.route("/task/<int:rid>", methods=["POST"])
@login_required
def task(rid):
    t = db.session.get(Task, rid)
    if not t:
        flash("Task not found.", "danger")
        return _back(url_for("mod.tasks"))
    t.title = _f("title") or t.title
    t.priority = _f("priority") or t.priority
    t.status = _f("status") or t.status
    if _date("due_date"): t.due_date = _date("due_date")
    if _f("account_id"): t.account_id = int(_f("account_id"))
    _audit(f"Edited task {t.title}", "task", t.id)
    db.session.commit()
    flash("Task updated.", "success")
    return _back(url_for("mod.tasks"))


def _int(name, current, lo=0, hi=100):
    v = _f(name)
    if v == "":
        return current
    try:
        return max(lo, min(hi, int(float(v))))
    except ValueError:
        return current


@edit_bp.route("/meeting/<int:rid>", methods=["POST"])
@login_required
def meeting(rid):
    m = db.session.get(Meeting, rid)
    if not m:
        flash("Meeting not found.", "danger")
        return _back(url_for("mod.meetings"))
    m.title = _f("title") or m.title
    m.meeting_type = _f("meeting_type") or m.meeting_type
    start = _f("start")  # datetime-local: YYYY-MM-DDTHH:MM
    if start:
        try:
            m.start_time = datetime.strptime(start, "%Y-%m-%dT%H:%M")
        except ValueError:
            pass
    if _f("duration_min"):
        m.duration_min = _int("duration_min", m.duration_min, lo=0, hi=1440)
    m.location = _f("location") or m.location
    m.is_executive = bool(request.form.get("is_executive"))
    m.account_id = int(_f("account_id")) if _f("account_id") else None
    _audit(f"Edited meeting {m.title}", "meeting", m.id)
    db.session.commit()
    flash(f"Meeting “{m.title}” updated.", "success")
    return _back(url_for("mod.meetings"))


@edit_bp.route("/renewal/<int:rid>", methods=["POST"])
@login_required
def renewal(rid):
    r = db.session.get(Renewal, rid)
    if not r:
        flash("Renewal not found.", "danger")
        return _back(url_for("mod.renewals"))
    if _date("renewal_date"):
        r.renewal_date = _date("renewal_date")
    if _f("amount"):
        r.amount = float(_f("amount"))
    r.likelihood = _int("likelihood", r.likelihood, lo=0, hi=100)
    r.status = _f("status") or r.status
    _audit(f"Edited renewal for {r.account.name if r.account else r.id}", "renewal", r.id)
    db.session.commit()
    flash("Renewal updated.", "success")
    return _back(url_for("mod.renewals"))


@edit_bp.route("/health/<int:rid>", methods=["POST"])
@login_required
def health(rid):
    h = db.session.get(CustomerHealth, rid)
    if not h:
        flash("Health record not found.", "danger")
        return _back(url_for("mod.customer_success"))
    h.score = _int("score", h.score)
    h.status = _f("status") or h.status
    h.trend = _f("trend") or h.trend
    h.product_usage = _int("product_usage", h.product_usage)
    h.adoption = _int("adoption", h.adoption)
    h.training_completion = _int("training_completion", h.training_completion)
    h.nps = _int("nps", h.nps, lo=-100, hi=100)
    h.exec_meetings = _int("exec_meetings", h.exec_meetings, lo=0, hi=999)
    _audit(f"Edited health for account {h.account_id}", "customer_health", h.id)
    db.session.commit()
    flash("Customer health updated.", "success")
    return _back(url_for("mod.customer_success"))


# ---------- kanban drag & drop ----------

@edit_bp.route("/api/opportunity/<int:rid>/stage", methods=["POST"])
@login_required
def change_stage(rid):
    o = db.session.get(Opportunity, rid)
    data = request.get_json(force=True)
    stage = data.get("stage")
    if not o or stage not in VALID_STAGES:
        return jsonify({"ok": False, "error": "Invalid opportunity or stage"}), 400
    old = o.stage
    o.stage = stage
    o.probability = STAGE_PROB[stage]
    o.closed_at = date.today() if stage.startswith("Closed") else None
    # nudge AI score toward the new stage's typical range
    o.ai_score = max(5, min(99, (o.ai_score + STAGE_PROB[stage] + 10) // 2))
    _audit(f"Moved '{o.name}' from {old} to {stage}", "opportunity", o.id)
    db.session.commit()
    return jsonify({"ok": True, "id": o.id, "stage": stage,
                    "probability": o.probability, "ai_score": o.ai_score})
