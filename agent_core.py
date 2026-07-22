"""
Shared agent data-plane.

The CRM exposes only deterministic reads and writes — NO LLM, NO reasoning.
Refold (or any orchestrator) owns the trigger, the LLM node and the loop; it
calls these helpers via routes/agent_api.py to gather context and to write
actions whose content Refold supplies. Every write is attributed to the agent
service account and audit-logged, so the CRM stays the single source of truth.
"""
import json
from datetime import datetime, date, timedelta

from flask import current_app
from database import db
from models import (User, Account, Meeting, Opportunity, Renewal, Activity,
                    Task, Note, Email, Notification, AuditLog, AgentRun, AgentDraft)


# ------------------------------------------------------------------ config
def agents_enabled():
    """Global kill switch — orchestrators should check this before a run."""
    return bool(current_app.config.get("AGENTS_ENABLED", True))


def agent_user():
    """The service account every agent write is attributed to."""
    return User.query.filter_by(email=current_app.config["AGENT_EMAIL"]).first()


def _audit(action, entity, entity_id):
    u = agent_user()
    db.session.add(AuditLog(user_id=u.id if u else None,
                            action=action, entity=entity, entity_id=entity_id))


# ------------------------------------------------------- idempotency + runs
def run_key(agent, entity_id, window):
    return f"{agent}:{entity_id}:{window}"


def run_exists(key):
    return db.session.query(AgentRun.id).filter_by(key=key).first() is not None


def get_run(key):
    return AgentRun.query.filter_by(key=key).first()


def log_run(key, agent_name, entity_type, entity_id, window_key,
            status="proposed", verdict=None, actions=None, trigger="refold"):
    run = AgentRun(
        key=key, agent_name=agent_name, entity_type=entity_type,
        entity_id=entity_id, window_key=str(window_key), status=status,
        verdict_json=json.dumps(verdict) if verdict is not None else None,
        actions_json=json.dumps(actions) if actions is not None else None,
        trigger=trigger)
    db.session.add(run)
    db.session.flush()
    return run


# ------------------------------------------------------------ write actions
# Content (note body, task title, draft payload) is supplied by the caller —
# the CRM never generates it. These just persist and attribute.
def create_note(account_id, body):
    n = Note(body=body, account_id=account_id, author_id=agent_user().id)
    db.session.add(n)
    db.session.flush()
    _audit("Agent filed a note", "note", n.id)
    return {"type": "note", "id": n.id, "account_id": account_id}


def create_notification(user_id, category, message, link=None):
    n = Notification(user_id=user_id, category=category, message=message, link=link)
    db.session.add(n)
    db.session.flush()
    return {"type": "notification", "id": n.id, "user_id": user_id}


def create_task(title, account_id, owner_id, due_date=None, priority="Medium"):
    t = Task(title=title, account_id=account_id, owner_id=owner_id,
             due_date=due_date or date.today(), priority=priority, status="Open")
    db.session.add(t)
    db.session.flush()
    _audit(f"Agent created task: {title}", "task", t.id)
    return {"type": "task", "id": t.id, "owner_id": owner_id}


def create_draft(agent_name, kind, account_id, title, payload, run_id=None):
    """Never-sent proposal that lands in the Approvals queue for a human."""
    d = AgentDraft(agent_name=agent_name, kind=kind, account_id=account_id,
                   title=title, payload_json=json.dumps(payload),
                   status="draft", run_id=run_id)
    db.session.add(d)
    db.session.flush()
    _audit(f"Agent drafted {kind} for approval", "agent_draft", d.id)
    return {"type": "draft", "id": d.id, "kind": kind}


# ----------------------------------------------------------- read / context
def upcoming_meetings(hours=24):
    now = datetime.utcnow()
    end = now + timedelta(hours=hours)
    return (Meeting.query
            .filter(Meeting.start_time > now,
                    Meeting.start_time <= end,
                    Meeting.account_id.isnot(None))
            .order_by(Meeting.start_time).all())


def upcoming_renewals(days=90):
    today = date.today()
    end = today + timedelta(days=days)
    return (Renewal.query
            .filter(Renewal.renewal_date >= today,
                    Renewal.renewal_date <= end,
                    Renewal.account_id.isnot(None))
            .order_by(Renewal.renewal_date).all())


def at_risk_accounts(limit=10):
    """The riskiest customer accounts (lowest health first) for Churn Sentinel."""
    from models import CustomerHealth
    return (db.session.query(Account, CustomerHealth)
            .join(CustomerHealth, CustomerHealth.account_id == Account.id)
            .order_by(CustomerHealth.score.asc(),
                      CustomerHealth.nps.asc())
            .limit(limit).all())


def _months_to(d):
    return None if not d else max(0, (d - date.today()).days // 30)


def _days_to(d):
    return None if not d else max(0, (d - date.today()).days)


def meeting_context(m):
    """The compact JSON block Refold's Meeting-Prep LLM reasons over.

    Pure assembly of existing records — deterministic, no intelligence.
    """
    acct = m.account
    h = acct.health if acct else None
    open_opps = [o for o in acct.opportunities
                 if o.stage not in ("Closed Won", "Closed Lost")] if acct else []
    renewal = (Renewal.query.filter_by(account_id=acct.id)
               .order_by(Renewal.renewal_date).first()) if acct else None
    acts = (Activity.query.filter_by(account_id=acct.id)
            .order_by(Activity.activity_date.desc()).limit(5).all()) if acct else []
    emails = (Email.query.filter_by(account_id=acct.id)
              .order_by(Email.sent_at.desc()).limit(5).all()) if acct else []
    tasks = (Task.query.filter_by(account_id=acct.id, status="Open").all()) if acct else []

    return {
        "meeting": {
            "id": m.id, "title": m.title, "type": m.meeting_type,
            "start_time": m.start_time.isoformat() if m.start_time else None,
            "duration_min": m.duration_min, "location": m.location,
            "is_executive": m.is_executive,
            "organizer": {"id": m.organizer.id, "name": m.organizer.name,
                          "title": m.organizer.title} if m.organizer else None,
        },
        "account": {
            "id": acct.id, "name": acct.name, "industry": acct.industry,
            "segment": acct.segment, "arr": acct.arr,
            "csm": acct.csm.name if acct.csm else None,
        } if acct else None,
        "health": {
            "score": h.score, "status": h.status, "trend": h.trend,
            "product_usage": h.product_usage, "adoption": h.adoption,
            "exec_meetings_90d": h.exec_meetings, "nps": h.nps,
            "training_completion": h.training_completion,
        } if h else None,
        "open_opportunities": [
            {"name": o.name, "stage": o.stage, "amount": o.amount,
             "ai_score": o.ai_score, "next_step": o.next_step}
            for o in open_opps],
        "renewal": {
            "date": renewal.renewal_date.isoformat() if renewal.renewal_date else None,
            "months_out": _months_to(renewal.renewal_date),
            "amount": renewal.amount, "likelihood": renewal.likelihood,
            "status": renewal.status,
        } if renewal else None,
        "contacts": [
            {"name": c.name, "title": c.title,
             "exec_sponsor": c.is_executive_sponsor} for c in (acct.contacts if acct else [])],
        "recent_activities": [
            {"type": a.activity_type, "subject": a.subject,
             "date": a.activity_date.isoformat() if a.activity_date else None}
            for a in acts],
        "recent_emails": [
            {"subject": e.subject, "snippet": e.snippet,
             "sent_at": e.sent_at.isoformat() if e.sent_at else None} for e in emails],
        "open_tasks": [{"title": t.title, "priority": t.priority} for t in tasks],
    }


def account_churn_context(acct):
    """The compact JSON block Refold's Churn Sentinel LLM reasons over.

    Pure assembly of existing records — deterministic, no intelligence.
    """
    h = acct.health
    open_opps = [o for o in acct.opportunities
                 if o.stage not in ("Closed Won", "Closed Lost")]
    renewal = (Renewal.query.filter_by(account_id=acct.id)
               .order_by(Renewal.renewal_date).first())
    acts = (Activity.query.filter_by(account_id=acct.id)
            .order_by(Activity.activity_date.desc()).limit(5).all())
    emails = (Email.query.filter_by(account_id=acct.id)
              .order_by(Email.sent_at.desc()).limit(5).all())
    tasks = Task.query.filter_by(account_id=acct.id, status="Open").all()

    return {
        "account": {
            "id": acct.id, "name": acct.name, "industry": acct.industry,
            "segment": acct.segment, "arr": acct.arr,
            "csm": acct.csm.name if acct.csm else None,
            "csm_id": acct.csm.id if acct.csm else None,
        },
        "health": {
            "score": h.score, "status": h.status, "trend": h.trend,
            "product_usage": h.product_usage, "adoption": h.adoption,
            "exec_meetings_90d": h.exec_meetings, "nps": h.nps,
            "training_completion": h.training_completion,
        } if h else None,
        "renewal": {
            "date": renewal.renewal_date.isoformat() if renewal and renewal.renewal_date else None,
            "days_out": _days_to(renewal.renewal_date) if renewal else None,
            "amount": renewal.amount, "likelihood": renewal.likelihood,
            "status": renewal.status,
        } if renewal else None,
        "open_opportunities": [
            {"name": o.name, "stage": o.stage, "amount": o.amount,
             "ai_score": o.ai_score, "next_step": o.next_step}
            for o in open_opps],
        "contacts": [
            {"name": c.name, "title": c.title,
             "exec_sponsor": c.is_executive_sponsor} for c in acct.contacts],
        "recent_activities": [
            {"type": a.activity_type, "subject": a.subject,
             "date": a.activity_date.isoformat() if a.activity_date else None}
            for a in acts],
        "recent_emails": [
            {"subject": e.subject, "snippet": e.snippet,
             "sent_at": e.sent_at.isoformat() if e.sent_at else None} for e in emails],
        "open_tasks": [{"title": t.title, "priority": t.priority} for t in tasks],
    }


def renewal_context(r):
    """The compact JSON block Refold's Renewal LLM reasons over.

    Pure assembly of existing records — deterministic, no intelligence.
    """
    acct = r.account
    h = acct.health if acct else None
    open_opps = [o for o in acct.opportunities
                 if o.stage not in ("Closed Won", "Closed Lost")] if acct else []
    acts = (Activity.query.filter_by(account_id=acct.id)
            .order_by(Activity.activity_date.desc()).limit(5).all()) if acct else []
    emails = (Email.query.filter_by(account_id=acct.id)
              .order_by(Email.sent_at.desc()).limit(5).all()) if acct else []
    tasks = (Task.query.filter_by(account_id=acct.id, status="Open").all()) if acct else []

    return {
        "renewal": {
            "id": r.id,
            "date": r.renewal_date.isoformat() if r.renewal_date else None,
            "days_out": _days_to(r.renewal_date),
            "months_out": _months_to(r.renewal_date),
            "amount": r.amount, "likelihood": r.likelihood, "status": r.status,
            "owner": r.owner.name if r.owner else None,
        },
        "account": {
            "id": acct.id, "name": acct.name, "industry": acct.industry,
            "segment": acct.segment, "arr": acct.arr,
            "csm": acct.csm.name if acct.csm else None,
        } if acct else None,
        "health": {
            "score": h.score, "status": h.status, "trend": h.trend,
            "product_usage": h.product_usage, "adoption": h.adoption,
            "exec_meetings_90d": h.exec_meetings, "nps": h.nps,
            "training_completion": h.training_completion,
        } if h else None,
        "open_opportunities": [
            {"name": o.name, "stage": o.stage, "amount": o.amount,
             "ai_score": o.ai_score, "next_step": o.next_step}
            for o in open_opps],
        "contacts": [
            {"name": c.name, "title": c.title,
             "exec_sponsor": c.is_executive_sponsor} for c in (acct.contacts if acct else [])],
        "recent_activities": [
            {"type": a.activity_type, "subject": a.subject,
             "date": a.activity_date.isoformat() if a.activity_date else None}
            for a in acts],
        "recent_emails": [
            {"subject": e.subject, "snippet": e.snippet,
             "sent_at": e.sent_at.isoformat() if e.sent_at else None} for e in emails],
        "open_tasks": [{"title": t.title, "priority": t.priority} for t in tasks],
    }


def briefing_context(days=7):
    """Business-wide snapshot Refold's Briefing LLM turns into an exec summary.

    Pure assembly across entities — deterministic, no intelligence.
    """
    from models import CustomerHealth
    today = date.today()
    since = datetime.utcnow() - timedelta(days=days)

    wins = (Opportunity.query
            .filter(Opportunity.stage == "Closed Won",
                    Opportunity.closed_at >= today - timedelta(days=days))
            .order_by(Opportunity.amount.desc()).limit(10).all())
    at_risk = (db.session.query(Account, CustomerHealth)
               .join(CustomerHealth, CustomerHealth.account_id == Account.id)
               .filter(db.or_(CustomerHealth.status == "Red", CustomerHealth.trend == "down"))
               .order_by(CustomerHealth.score.asc()).limit(8).all())
    renewals = upcoming_renewals(90)
    open_opps = (Opportunity.query
                 .filter(Opportunity.stage.notin_(["Closed Won", "Closed Lost"])).all())
    top_open = sorted(open_opps, key=lambda o: -(o.amount or 0))[:5]
    meetings = upcoming_meetings(48)
    acts = Activity.query.filter(Activity.activity_date >= since).count()

    return {
        "period_days": days,
        "wins": [
            {"name": o.name, "amount": o.amount,
             "account": o.account.name if o.account else None,
             "closed_at": o.closed_at.isoformat() if o.closed_at else None} for o in wins],
        "at_risk_accounts": [
            {"account": a.name, "arr": a.arr, "score": h.score,
             "status": h.status, "trend": h.trend} for a, h in at_risk],
        "renewals_next_90d": {
            "count": len(renewals),
            "amount": sum(r.amount or 0 for r in renewals),
            "top": [{"account": r.account.name if r.account else None, "amount": r.amount,
                     "date": r.renewal_date.isoformat() if r.renewal_date else None,
                     "likelihood": r.likelihood} for r in renewals[:5]]},
        "pipeline": {
            "open_count": len(open_opps),
            "open_value": sum(o.amount or 0 for o in open_opps),
            "top": [{"name": o.name, "amount": o.amount, "stage": o.stage,
                     "account": o.account.name if o.account else None} for o in top_open]},
        "upcoming_meetings_48h": len(meetings),
        "recent_activity_count": acts,
    }


def stale_opportunities(limit=10):
    """Open opps with hygiene problems, worst-first, for Pipeline Hygiene.

    Deterministic flagging only — the LLM decides what to do about them.
    """
    today = date.today()
    opps = (Opportunity.query
            .filter(Opportunity.stage.notin_(["Closed Won", "Closed Lost"])).all())
    flagged = []
    for o in opps:
        age = (today - o.created_at.date()).days if o.created_at else 0
        issues = []
        if not o.next_step:
            issues.append("No next step set")
        if o.expected_close and o.expected_close < today:
            issues.append("Close date is in the past")
        if not o.amount:
            issues.append("Missing amount")
        if o.owner_id is None:
            issues.append("No owner assigned")
        if age > 90:
            issues.append(f"Open {age} days with no close")
        if (o.ai_score or 0) < 40:
            issues.append(f"Low AI score ({o.ai_score})")
        if issues:
            flagged.append((o, issues, age))
    flagged.sort(key=lambda t: (-len(t[1]), -t[2]))
    return flagged[:limit]


def opportunity_context(o):
    """Compact context for a single opportunity (Pipeline Hygiene LLM input)."""
    acct = o.account
    h = acct.health if acct else None
    today = date.today()
    acts = (Activity.query.filter_by(account_id=acct.id)
            .order_by(Activity.activity_date.desc()).limit(5).all()) if acct else []
    return {
        "opportunity": {
            "id": o.id, "name": o.name, "stage": o.stage, "amount": o.amount,
            "probability": o.probability, "ai_score": o.ai_score,
            "opp_type": o.opp_type, "competitor": o.competitor,
            "next_step": o.next_step,
            "expected_close": o.expected_close.isoformat() if o.expected_close else None,
            "age_days": (today - o.created_at.date()).days if o.created_at else None,
            "owner": o.owner.name if o.owner else None,
            "owner_id": o.owner_id,
        },
        "account": {
            "id": acct.id, "name": acct.name, "industry": acct.industry,
            "segment": acct.segment, "arr": acct.arr,
            "csm": acct.csm.name if acct.csm else None,
        } if acct else None,
        "health": {
            "score": h.score, "status": h.status, "trend": h.trend,
        } if h else None,
        "recent_activities": [
            {"type": a.activity_type, "subject": a.subject,
             "date": a.activity_date.isoformat() if a.activity_date else None}
            for a in acts],
    }
