"""
Token-authenticated agent API (`/api/agent/*`).

This is the surface Refold (or any orchestrator) calls: read context, write
actions, log runs — all attributed to the agent service account, all
audit-logged. Auth is a bearer token, not a browser session, so a machine can
call in without logging in. Every write goes through here so the CRM stays the
system of record.
"""
import json
from functools import wraps
from datetime import datetime, date

from flask import Blueprint, request, jsonify, current_app
from database import db
from models import AgentRun, AgentDraft
import agent_core as core

agent_bp = Blueprint("agent_api", __name__, url_prefix="/api/agent")


def require_agent_token(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
        token = token or request.headers.get("X-Agent-Token")
        if not token or token != current_app.config["AGENT_API_TOKEN"]:
            return jsonify(error="unauthorized",
                           hint="send Authorization: Bearer <AGENT_API_TOKEN>"), 401
        return f(*args, **kwargs)
    return wrapper


def _body():
    return request.get_json(silent=True) or {}


def _parse_date(v):
    if not v:
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


# --------------------------------------------------------------- health
@agent_bp.route("/ping")
@require_agent_token
def ping():
    u = core.agent_user()
    return jsonify(ok=True, agent=u.email if u else None,
                   agents_enabled=core.agents_enabled())


# --------------------------------------------------------------- context (read)
@agent_bp.route("/meetings-upcoming")
@require_agent_token
def meetings_upcoming():
    hours = request.args.get("hours", default=24, type=int)
    meetings = core.upcoming_meetings(hours)
    return jsonify(count=len(meetings), hours=hours, meetings=[
        {"id": m.id, "title": m.title, "type": m.meeting_type,
         "start_time": m.start_time.isoformat() if m.start_time else None,
         "account_id": m.account_id, "organizer_id": m.organizer_id,
         "is_executive": m.is_executive} for m in meetings])


@agent_bp.route("/meeting-context/<int:meeting_id>")
@require_agent_token
def meeting_context(meeting_id):
    from models import Meeting
    m = db.session.get(Meeting, meeting_id)
    if not m:
        return jsonify(error="meeting not found"), 404
    return jsonify(core.meeting_context(m))


@agent_bp.route("/renewals-upcoming")
@require_agent_token
def renewals_upcoming():
    days = request.args.get("days", default=90, type=int)
    rows = core.upcoming_renewals(days)
    return jsonify(count=len(rows), days=days, renewals=[
        {"id": r.id, "account_id": r.account_id,
         "account": r.account.name if r.account else None,
         "renewal_date": r.renewal_date.isoformat() if r.renewal_date else None,
         "amount": r.amount, "likelihood": r.likelihood, "status": r.status,
         "owner_id": r.owner_id} for r in rows])


@agent_bp.route("/renewal-context/<int:renewal_id>")
@require_agent_token
def renewal_context(renewal_id):
    from models import Renewal
    r = db.session.get(Renewal, renewal_id)
    if not r:
        return jsonify(error="renewal not found"), 404
    return jsonify(core.renewal_context(r))


@agent_bp.route("/at-risk-accounts")
@require_agent_token
def at_risk_accounts():
    limit = request.args.get("limit", default=10, type=int)
    rows = core.at_risk_accounts(limit)
    return jsonify(count=len(rows), limit=limit, accounts=[
        {"id": a.id, "account": a.name, "arr": a.arr,
         "csm": a.csm.name if a.csm else None,
         "csm_id": a.csm.id if a.csm else None,
         "health_score": h.score, "health_status": h.status, "trend": h.trend,
         "nps": h.nps, "product_usage": h.product_usage, "adoption": h.adoption}
        for a, h in rows])


@agent_bp.route("/account-churn-context/<int:account_id>")
@require_agent_token
def account_churn_context(account_id):
    from models import Account
    a = db.session.get(Account, account_id)
    if not a:
        return jsonify(error="account not found"), 404
    return jsonify(core.account_churn_context(a))


@agent_bp.route("/briefing-context")
@require_agent_token
def briefing_context():
    days = request.args.get("days", default=7, type=int)
    return jsonify(core.briefing_context(days))


@agent_bp.route("/stale-opportunities")
@require_agent_token
def stale_opportunities():
    limit = request.args.get("limit", default=10, type=int)
    rows = core.stale_opportunities(limit)
    return jsonify(count=len(rows), limit=limit, opportunities=[
        {"id": o.id, "name": o.name, "stage": o.stage, "amount": o.amount,
         "ai_score": o.ai_score, "next_step": o.next_step,
         "expected_close": o.expected_close.isoformat() if o.expected_close else None,
         "account": o.account.name if o.account else None, "account_id": o.account_id,
         "owner": o.owner.name if o.owner else None, "owner_id": o.owner_id,
         "age_days": age, "issues": issues}
        for o, issues, age in rows])


@agent_bp.route("/opportunity-context/<int:opportunity_id>")
@require_agent_token
def opportunity_context(opportunity_id):
    from models import Opportunity
    o = db.session.get(Opportunity, opportunity_id)
    if not o:
        return jsonify(error="opportunity not found"), 404
    return jsonify(core.opportunity_context(o))


# --------------------------------------------------------------- actions (write)
@agent_bp.route("/notes", methods=["POST"])
@require_agent_token
def post_note():
    b = _body()
    if not b.get("account_id") or not b.get("body"):
        return jsonify(error="account_id and body are required"), 400
    a = core.create_note(b["account_id"], b["body"])
    db.session.commit()
    return jsonify(a), 201


@agent_bp.route("/notifications", methods=["POST"])
@require_agent_token
def post_notification():
    b = _body()
    if not b.get("user_id") or not b.get("message"):
        return jsonify(error="user_id and message are required"), 400
    a = core.create_notification(b["user_id"], b.get("category", "Activity"),
                                 b["message"], b.get("link"))
    db.session.commit()
    return jsonify(a), 201


@agent_bp.route("/tasks", methods=["POST"])
@require_agent_token
def post_task():
    b = _body()
    if not b.get("title") or not b.get("owner_id"):
        return jsonify(error="title and owner_id are required"), 400
    a = core.create_task(b["title"], b.get("account_id"), b["owner_id"],
                         due_date=_parse_date(b.get("due_date")),
                         priority=b.get("priority", "Medium"))
    db.session.commit()
    return jsonify(a), 201


@agent_bp.route("/drafts", methods=["POST"])
@require_agent_token
def post_draft():
    b = _body()
    for req in ("agent_name", "kind", "title"):
        if not b.get(req):
            return jsonify(error=f"{req} is required"), 400
    a = core.create_draft(b["agent_name"], b["kind"], b.get("account_id"),
                          b["title"], b.get("payload", {}), b.get("run_id"))
    db.session.commit()
    return jsonify(a), 201


@agent_bp.route("/drafts")
@require_agent_token
def list_drafts():
    status = request.args.get("status", "draft")
    q = AgentDraft.query
    if status != "all":
        q = q.filter_by(status=status)
    rows = q.order_by(AgentDraft.created_at.desc()).limit(50).all()
    return jsonify(count=len(rows), drafts=[
        {"id": d.id, "agent": d.agent_name, "kind": d.kind, "title": d.title,
         "account_id": d.account_id, "status": d.status,
         "payload": json.loads(d.payload_json or "{}"),
         "created_at": d.created_at.isoformat()} for d in rows])


# --------------------------------------------------------------- runs (audit/idempotency)
@agent_bp.route("/runs")
@require_agent_token
def get_runs():
    key = request.args.get("key")
    if key:
        r = core.get_run(key)
        return jsonify(exists=r is not None, run=(_run_dict(r) if r else None))
    agent = request.args.get("agent")
    q = AgentRun.query
    if agent:
        q = q.filter_by(agent_name=agent)
    rows = q.order_by(AgentRun.created_at.desc()).limit(50).all()
    return jsonify(count=len(rows), runs=[_run_dict(r) for r in rows])


@agent_bp.route("/runs", methods=["POST"])
@require_agent_token
def post_run():
    b = _body()
    if not b.get("key") or not b.get("agent_name"):
        return jsonify(error="key and agent_name are required"), 400
    if core.run_exists(b["key"]):
        return jsonify(error="run already exists for key", key=b["key"]), 409
    r = core.log_run(b["key"], b["agent_name"], b.get("entity_type", ""),
                     b.get("entity_id"), b.get("window_key", ""),
                     status=b.get("status", "proposed"),
                     verdict=b.get("verdict"), actions=b.get("actions"),
                     trigger=b.get("trigger", "refold"))
    db.session.commit()
    return jsonify(_run_dict(r)), 201


def _run_dict(r):
    return {"id": r.id, "key": r.key, "agent": r.agent_name,
            "entity_type": r.entity_type, "entity_id": r.entity_id,
            "window_key": r.window_key, "status": r.status,
            "trigger": r.trigger,
            "verdict": json.loads(r.verdict_json) if r.verdict_json else None,
            "actions": json.loads(r.actions_json) if r.actions_json else None,
            "created_at": r.created_at.isoformat()}
