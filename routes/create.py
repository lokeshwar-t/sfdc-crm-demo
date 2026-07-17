"""Quick-create routes for the global '+ New' menu."""
from datetime import datetime, date
from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required, current_user
from database import db
from models import (Account, Contact, Opportunity, Task, Note, Meeting,
                    CustomerHealth, AuditLog)

create_bp = Blueprint("create", __name__, url_prefix="/new")

STAGE_PROB = {"Lead": 10, "Qualified": 25, "Discovery": 45, "Proposal": 65, "Negotiation": 80}


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


@create_bp.route("/account", methods=["POST"])
@login_required
def account():
    name = _f("name")
    if not name:
        flash("Account name is required.", "danger")
        return redirect(request.referrer or url_for("mod.accounts"))
    a = Account(name=name, industry=_f("industry") or "Technology",
                region=_f("region") or "North America", segment=_f("segment") or "Mid-Market",
                website=_f("website") or f"www.{name.split()[0].lower()}.com",
                employees=int(_f("employees") or 0) or None,
                arr=float(_f("arr") or 0),
                is_customer=_f("type") == "customer",
                owner_id=current_user.id)
    db.session.add(a)
    db.session.flush()
    if a.is_customer:
        db.session.add(CustomerHealth(account_id=a.id, score=70, status="Green",
                                      product_usage=70, exec_meetings=0, training_completion=50,
                                      nps=30, adoption=60, trend="flat"))
    _audit(f"Created account {a.name}", "account", a.id)
    db.session.commit()
    flash(f"Account “{a.name}” created.", "success")
    return redirect(url_for("mod.account_360", account_id=a.id))


@create_bp.route("/contact", methods=["POST"])
@login_required
def contact():
    first, last = _f("first_name"), _f("last_name")
    if not (first and last):
        flash("First and last name are required.", "danger")
        return redirect(request.referrer or url_for("mod.contacts"))
    c = Contact(first_name=first, last_name=last, title=_f("title"),
                email=_f("email"), phone=_f("phone"),
                is_executive_sponsor=bool(request.form.get("is_executive_sponsor")),
                account_id=int(_f("account_id") or 0) or None)
    db.session.add(c)
    db.session.flush()
    _audit(f"Created contact {c.name}", "contact", c.id)
    db.session.commit()
    flash(f"Contact “{c.name}” created.", "success")
    if c.account_id:
        return redirect(url_for("mod.account_360", account_id=c.account_id))
    return redirect(url_for("mod.contacts"))


@create_bp.route("/opportunity", methods=["POST"])
@login_required
def opportunity():
    name = _f("name")
    account_id = int(_f("account_id") or 0) or None
    if not name or not account_id:
        flash("Opportunity name and account are required.", "danger")
        return redirect(request.referrer or url_for("mod.opportunities"))
    stage = _f("stage") or "Lead"
    o = Opportunity(name=name, stage=stage,
                    amount=float(_f("amount") or 0),
                    probability=STAGE_PROB.get(stage, 10),
                    expected_close=_date("expected_close"),
                    opp_type=_f("opp_type") or "New Business",
                    competitor=_f("competitor") or None,
                    next_step=_f("next_step") or None,
                    ai_score=STAGE_PROB.get(stage, 10) + 10,
                    account_id=account_id,
                    owner_id=current_user.id,
                    product_id=int(_f("product_id") or 0) or None)
    db.session.add(o)
    db.session.flush()
    _audit(f"Created opportunity {o.name}", "opportunity", o.id)
    db.session.commit()
    flash(f"{'Lead' if stage == 'Lead' else 'Opportunity'} “{o.name}” created.", "success")
    return redirect(url_for("mod.leads") if stage in ("Lead", "Qualified") else url_for("mod.opportunities"))


@create_bp.route("/task", methods=["POST"])
@login_required
def task():
    title = _f("title")
    if not title:
        flash("Task title is required.", "danger")
        return redirect(request.referrer or url_for("mod.tasks"))
    t = Task(title=title, due_date=_date("due_date") or date.today(),
             priority=_f("priority") or "Medium", status="Open",
             account_id=int(_f("account_id") or 0) or None,
             owner_id=current_user.id)
    db.session.add(t)
    db.session.flush()
    _audit(f"Created task {t.title}", "task", t.id)
    db.session.commit()
    flash("Task created.", "success")
    return redirect(request.referrer or url_for("mod.tasks"))


@create_bp.route("/note", methods=["POST"])
@login_required
def note():
    body = _f("body")
    if not body:
        flash("Note text is required.", "danger")
        return redirect(request.referrer or url_for("mod.notes"))
    n = Note(body=body, account_id=int(_f("account_id") or 0) or None,
             author_id=current_user.id)
    db.session.add(n)
    db.session.flush()
    _audit("Created note", "note", n.id)
    db.session.commit()
    flash("Note saved.", "success")
    if n.account_id:
        return redirect(url_for("mod.account_360", account_id=n.account_id))
    return redirect(url_for("mod.notes"))


@create_bp.route("/meeting", methods=["POST"])
@login_required
def meeting():
    title = _f("title")
    if not title:
        flash("Meeting title is required.", "danger")
        return redirect(request.referrer or url_for("mod.meetings"))
    dt = None
    if _f("start_date"):
        try:
            dt = datetime.strptime(_f("start_date") + " " + (_f("start_time") or "09:00"), "%Y-%m-%d %H:%M")
        except ValueError:
            dt = datetime.utcnow()
    m = Meeting(title=title, meeting_type=_f("meeting_type") or "Discovery",
                start_time=dt or datetime.utcnow(),
                duration_min=int(_f("duration_min") or 60),
                location=_f("location") or "Zoom",
                is_executive=bool(request.form.get("is_executive")),
                account_id=int(_f("account_id") or 0) or None,
                organizer_id=current_user.id)
    db.session.add(m)
    db.session.flush()
    _audit(f"Created meeting {m.title}", "meeting", m.id)
    db.session.commit()
    flash("Meeting scheduled.", "success")
    return redirect(url_for("mod.meetings"))
