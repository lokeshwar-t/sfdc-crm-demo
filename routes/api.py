import json
import urllib.request
import urllib.error
from datetime import date, timedelta
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from database import db
from models import Account, Opportunity, Renewal, CustomerHealth, User, Role, UsageMetric
import ai_service
import agent_core as core

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


# Upcoming meetings for the briefing panel — uses the SAME source the agent
# briefs (agent_core.upcoming_meetings), so the list mirrors the workflow's set.
@api_bp.route("/meetings/upcoming")
@login_required
def meetings_upcoming_ui():
    try:
        hours = int(request.args.get("hours", 24))
    except (TypeError, ValueError):
        hours = 24
    if hours not in current_app.config["MEETING_PREP_WINDOWS"]:
        hours = 24
    meetings = core.upcoming_meetings(hours)
    return jsonify(hours=hours, count=len(meetings), meetings=[
        {"id": m.id, "title": m.title,
         "start_time": m.start_time.isoformat() if m.start_time else None,
         "location": m.location, "account_id": m.account_id} for m in meetings])


# ---------------- Meeting-Prep agent trigger ----------------
# The button on the Briefing page fires Refold's Meeting-Prep workflow and polls
# for its result. The CRM does NOT reason — Refold owns the LLM node and pulls
# context back through the token-authed /api/agent/* surface. The workflow runs
# async: `run` starts it and returns an execution id; the browser then polls
# `status/<id>` until the execution reaches a terminal state.
_EXEC_SUCCESS = {"success", "succeeded", "successful", "completed", "complete",
                 "done", "finished", "ok"}
_EXEC_FAILURE = {"failed", "failure", "error", "errored", "cancelled",
                 "canceled", "timeout", "timed_out", "aborted", "rejected"}


def _refold_configured():
    c = current_app.config
    return bool(c.get("REFOLD_API_KEY") and c.get("REFOLD_LINKED_ACCOUNT_ID"))


def _short(v, n=600):
    s = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
    return s[:n]


def _refold_call(method, url, headers, body=None):
    """Make one Refold request. Returns (ok, status_code, parsed). Never raises."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    timeout = current_app.config.get("REFOLD_HTTP_TIMEOUT", 30)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw, code = resp.read().decode("utf-8"), resp.getcode()
    except urllib.error.HTTPError as e:
        raw, code = e.read().decode("utf-8", "replace"), e.code
    except urllib.error.URLError as e:
        return False, 502, {"error": "network", "detail": str(e.reason)}
    except Exception as e:  # timeout, etc.
        return False, 502, {"error": "request_failed", "detail": str(e)}
    try:
        parsed = json.loads(raw) if raw else {}
    except ValueError:
        parsed = {"raw": raw}
    return (200 <= code < 300), code, parsed


def _extract_execution_id(resp):
    if not isinstance(resp, dict):
        return None
    for k in ("execution_id", "executionId", "_id", "id", "execution"):
        v = resp.get(k)
        if isinstance(v, str) and v:
            return v
        if isinstance(v, dict):  # nested object holding the id
            nested = _extract_execution_id(v)
            if nested:
                return nested
    if isinstance(resp.get("data"), dict):
        return _extract_execution_id(resp["data"])
    return None


def _execution_state(resp):
    """Normalize Refold's execution status into running | success | error."""
    if not isinstance(resp, dict):
        return "running", ""
    data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
    status = str(resp.get("status") or resp.get("state")
                 or data.get("status") or data.get("state") or "").lower()
    if status in _EXEC_SUCCESS:
        return "success", status
    if status in _EXEC_FAILURE:
        return "error", status
    return "running", status


# Shared Cobalt calls — every agent fires/polls the same way; only the workflow
# id, slug, and trigger body differ per agent.
def _start_workflow(workflow_id, slug, body):
    c = current_app.config
    url = (f"{c['REFOLD_API_BASE'].rstrip('/')}"
           f"/api/v1/workflow/{workflow_id}/execute")
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": c["REFOLD_API_KEY"],
        "linked_account_id": c["REFOLD_LINKED_ACCOUNT_ID"],
        "sync_execution": "false",
    }
    if slug:
        headers["slug"] = slug
    if c.get("REFOLD_CONFIG_ID"):
        headers["config_id"] = c["REFOLD_CONFIG_ID"]
    return _refold_call("POST", url, headers, body=body)


def _poll_execution(execution_id):
    c = current_app.config
    url = (f"{c['REFOLD_API_BASE'].rstrip('/')}"
           f"/api/v2/public/execution/{execution_id}")
    headers = {
        "x-api-key": c["REFOLD_API_KEY"],
        "linked_account_id": c["REFOLD_LINKED_ACCOUNT_ID"],
    }
    return _refold_call("GET", url, headers)


def _status_payload(execution_id):
    """Shared status handler used by every agent's status route."""
    ok, code, resp = _poll_execution(execution_id)
    if not ok:
        return jsonify(error="Could not fetch workflow status.",
                       detail=_short(resp), status=code), 502
    state, status_raw = _execution_state(resp)
    return jsonify(ok=True, state=state, status=status_raw,
                   execution_id=execution_id, result=resp)


@api_bp.route("/meeting-prep/run", methods=["POST"])
@login_required
def meeting_prep_run():
    data = request.get_json(silent=True) or {}
    try:
        hours = int(data.get("hours", 24))
    except (TypeError, ValueError):
        hours = 24
    if hours not in current_app.config["MEETING_PREP_WINDOWS"]:
        return jsonify(error=f"hours must be one of "
                             f"{current_app.config['MEETING_PREP_WINDOWS']}"), 400
    if not _refold_configured():
        return jsonify(error="Meeting-Prep workflow is not configured.",
                       hint="Set REFOLD_API_KEY and REFOLD_LINKED_ACCOUNT_ID."), 503
    c = current_app.config
    ok, code, resp = _start_workflow(c["REFOLD_MEETING_PREP_WORKFLOW_ID"],
                                     c.get("REFOLD_MEETING_PREP_SLUG"),
                                     {"hours": str(hours)})
    if not ok:
        return jsonify(error="Could not start the Meeting-Prep workflow.",
                       detail=_short(resp), status=code), 502
    exec_id = _extract_execution_id(resp)
    if not exec_id:
        return jsonify(error="Workflow started but no execution id was returned.",
                       detail=_short(resp)), 502
    return jsonify(ok=True, execution_id=exec_id, window_hours=hours)


@api_bp.route("/meeting-prep/status/<execution_id>")
@login_required
def meeting_prep_status(execution_id):
    if not _refold_configured():
        return jsonify(error="Meeting-Prep workflow is not configured."), 503
    return _status_payload(execution_id)


@api_bp.route("/renewal-prep/run", methods=["POST"])
@login_required
def renewal_prep_run():
    data = request.get_json(silent=True) or {}
    try:
        days = int(data.get("days", 90))
    except (TypeError, ValueError):
        days = 90
    if days not in current_app.config["RENEWAL_WINDOWS"]:
        return jsonify(error=f"days must be one of "
                             f"{current_app.config['RENEWAL_WINDOWS']}"), 400
    if not _refold_configured():
        return jsonify(error="Renewal workflow is not configured.",
                       hint="Set REFOLD_API_KEY and REFOLD_LINKED_ACCOUNT_ID."), 503
    c = current_app.config
    if not c.get("REFOLD_RENEWAL_WORKFLOW_ID"):
        return jsonify(error="Renewal workflow is not configured.",
                       hint="Set REFOLD_RENEWAL_WORKFLOW_ID to the Cobalt workflow id."), 503
    ok, code, resp = _start_workflow(c["REFOLD_RENEWAL_WORKFLOW_ID"],
                                     c.get("REFOLD_RENEWAL_SLUG"),
                                     {"days": str(days)})
    if not ok:
        return jsonify(error="Could not start the Renewal workflow.",
                       detail=_short(resp), status=code), 502
    exec_id = _extract_execution_id(resp)
    if not exec_id:
        return jsonify(error="Workflow started but no execution id was returned.",
                       detail=_short(resp)), 502
    return jsonify(ok=True, execution_id=exec_id, window_days=days)


@api_bp.route("/renewal-prep/status/<execution_id>")
@login_required
def renewal_prep_status(execution_id):
    if not _refold_configured():
        return jsonify(error="Renewal workflow is not configured."), 503
    return _status_payload(execution_id)


@api_bp.route("/churn-sentinel/run", methods=["POST"])
@login_required
def churn_sentinel_run():
    data = request.get_json(silent=True) or {}
    try:
        limit = int(data.get("limit", 10))
    except (TypeError, ValueError):
        limit = 10
    if limit not in current_app.config["CHURN_LIMITS"]:
        return jsonify(error=f"limit must be one of "
                             f"{current_app.config['CHURN_LIMITS']}"), 400
    if not _refold_configured():
        return jsonify(error="Churn Sentinel workflow is not configured.",
                       hint="Set REFOLD_API_KEY and REFOLD_LINKED_ACCOUNT_ID."), 503
    c = current_app.config
    if not c.get("REFOLD_CHURN_WORKFLOW_ID"):
        return jsonify(error="Churn Sentinel workflow is not configured.",
                       hint="Set REFOLD_CHURN_WORKFLOW_ID to the Cobalt workflow id."), 503
    ok, code, resp = _start_workflow(c["REFOLD_CHURN_WORKFLOW_ID"],
                                     c.get("REFOLD_CHURN_SLUG"),
                                     {"limit": str(limit)})
    if not ok:
        return jsonify(error="Could not start the Churn Sentinel workflow.",
                       detail=_short(resp), status=code), 502
    exec_id = _extract_execution_id(resp)
    if not exec_id:
        return jsonify(error="Workflow started but no execution id was returned.",
                       detail=_short(resp)), 502
    return jsonify(ok=True, execution_id=exec_id, window_limit=limit)


@api_bp.route("/churn-sentinel/status/<execution_id>")
@login_required
def churn_sentinel_status(execution_id):
    if not _refold_configured():
        return jsonify(error="Churn Sentinel workflow is not configured."), 503
    return _status_payload(execution_id)


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
