"""
AI Service abstraction layer.

Swap MockAIProvider with OpenAIProvider / AnthropicProvider later —
the rest of the app only calls ai_service.ask(...).
"""
import random
from datetime import date
from database import db
from models import (Account, Opportunity, Renewal, CustomerHealth, Meeting,
                    Activity, Contract, AIHistory)


class BaseAIProvider:
    def complete(self, prompt: str, context: dict) -> str:
        raise NotImplementedError


class MockAIProvider(BaseAIProvider):
    """Generates intelligent-sounding responses from live database facts."""

    def complete(self, prompt, context):
        p = prompt.lower()
        acct = context.get("account")

        if acct is not None:
            return self._account_answer(p, acct)

        if "risk" in p or "churn" in p:
            return self._risk_answer()
        if "changed" in p or "week" in p or "overnight" in p:
            return self._week_answer()
        if "summar" in p and "business" in p:
            return self._business_summary()
        if "board" in p:
            return self._board_summary()
        if "predict" in p or "forecast" in p or "next quarter" in p:
            return self._forecast_answer()
        if "pipeline" in p:
            return self._pipeline_answer()
        if "renewal" in p:
            return self._renewal_answer()
        if "email" in p:
            return self._email_draft()
        if "upsell" in p or "expansion" in p:
            return self._expansion_answer()
        if "cash" in p:
            return self._cashflow_answer()
        if "duplicate" in p or "cleanup" in p or "clean" in p:
            return self._dataquality_answer()
        if "briefing" in p or "summary" in p:
            return self._week_answer()
        return self._business_summary()

    # ---------- fact-based generators ----------

    def _fmt(self, n):
        if n >= 1_000_000:
            return f"${n/1_000_000:.1f}M"
        return f"${n/1_000:.0f}K"

    def _account_answer(self, p, acct):
        h = acct.health
        score = h.score if h else 70
        status = h.status if h else "Yellow"
        renewal = Renewal.query.filter_by(account_id=acct.id).order_by(Renewal.renewal_date).first()
        open_opps = [o for o in acct.opportunities if o.stage not in ("Closed Won", "Closed Lost")]
        exec_meetings = h.exec_meetings if h else 0
        months_to_renewal = None
        if renewal and renewal.renewal_date:
            months_to_renewal = max(0, (renewal.renewal_date - date.today()).days // 30)

        if "email" in p:
            contact = acct.contacts[0] if acct.contacts else None
            cname = contact.first_name if contact else "there"
            return (f"**Draft follow-up email:**\n\nSubject: Next steps for {acct.name}\n\n"
                    f"Hi {cname},\n\nThank you for the productive conversation this week. "
                    f"Based on your team's goals, I've outlined how CloudVision can accelerate your analytics roadmap. "
                    f"I'd love to schedule a technical deep-dive next week — would Tuesday or Thursday work?\n\n"
                    f"Best regards")
        if "qbr" in p:
            return (f"**QBR Prep — {acct.name}**\n\n"
                    f"• Health score: {score} ({status}), trend {h.trend if h else 'flat'}\n"
                    f"• Adoption: {h.adoption if h else 65}% | Training completion: {h.training_completion if h else 60}%\n"
                    f"• Executive meetings last 90 days: {exec_meetings}\n"
                    f"• Renewal in {months_to_renewal if months_to_renewal is not None else 'N/A'} months at {self._fmt(renewal.amount) if renewal else 'N/A'}\n"
                    f"• Recommended agenda: adoption wins, roadmap alignment, expansion into Data Apps, renewal timeline.")
        if "meeting" in p and "prepare" in p:
            return (f"**Meeting prep for {acct.name}:** Health is {score} ({status}). "
                    f"{len(open_opps)} open opportunit{'y' if len(open_opps)==1 else 'ies'} worth "
                    f"{self._fmt(sum(o.amount for o in open_opps)) if open_opps else '$0'}. "
                    f"Key talking points: recent product adoption at {h.adoption if h else 65}%, "
                    f"renewal due in {months_to_renewal if months_to_renewal is not None else '—'} months. "
                    f"Suggested ask: confirm executive sponsor attendance at next QBR.")
        if "churn" in p or "risk" in p or "dropped" in p:
            drivers = []
            if h:
                if h.product_usage < 50: drivers.append(f"product usage at {h.product_usage}%")
                if h.exec_meetings == 0: drivers.append("no executive meetings in 90 days")
                if h.nps < 0: drivers.append(f"negative NPS ({h.nps})")
                if h.training_completion < 40: drivers.append(f"low training completion ({h.training_completion}%)")
            drivers = drivers or ["healthy metrics across the board"]
            return (f"**Churn analysis — {acct.name}:** score {score} ({status}). "
                    f"Primary drivers: {', '.join(drivers)}. "
                    f"AI recommends {'an immediate executive outreach and success plan review' if status=='Red' else 'a proactive check-in and adoption workshop' if status=='Yellow' else 'maintaining the current cadence'}.")
        # default: account summary
        return (f"{acct.name} has a {'healthy' if score >= 75 else 'concerning' if score < 50 else 'stable'} outlook "
                f"with a customer health score of {score} ({status}). "
                f"Product adoption is at {h.adoption if h else 65}% and {exec_meetings} executive meeting(s) occurred in the last 90 days. "
                f"{'Renewal is due in ' + str(months_to_renewal) + ' months at ' + self._fmt(renewal.amount) + '. ' if renewal and months_to_renewal is not None else ''}"
                f"{len(open_opps)} open opportunit{'y' if len(open_opps)==1 else 'ies'} in pipeline"
                f"{' worth ' + self._fmt(sum(o.amount for o in open_opps)) if open_opps else ''}. "
                f"AI recommends {'discussing expansion into the Data Apps module' if score >= 75 else 'scheduling an executive business review to re-align on value'}.")

    def _risk_answer(self):
        reds = (db.session.query(Account, CustomerHealth)
                .join(CustomerHealth, CustomerHealth.account_id == Account.id)
                .filter(CustomerHealth.status == "Red")
                .order_by(Account.arr.desc()).limit(5).all())
        lines = [f"• **{a.name}** — health {h.score}, ARR {self._fmt(a.arr)}, trend {h.trend}" for a, h in reds]
        total = sum(a.arr for a, _ in reds)
        return ("**Top at-risk customers:**\n\n" + "\n".join(lines) +
                f"\n\nCombined ARR at risk: {self._fmt(total)}. "
                "AI recommends executive sponsorship for the top three and a save-play for any renewal inside 90 days.")

    def _week_answer(self):
        won = Opportunity.query.filter_by(stage="Closed Won").order_by(Opportunity.closed_at.desc()).limit(3).all()
        red = CustomerHealth.query.filter_by(status="Red").count()
        upcoming = Renewal.query.filter(Renewal.status.in_(["Upcoming", "At Risk"])).count()
        return (f"**This week at CloudVision:** {len(won)} notable deals closed"
                f"{' including ' + won[0].name + ' (' + self._fmt(won[0].amount) + ')' if won else ''}. "
                f"{red} accounts are in red health status and {upcoming} renewals are open. "
                "Pipeline coverage remains above 3x for the quarter. "
                "Recommended focus: two enterprise renewals inside 60 days and the stalled negotiations flagged in Sales Ops.")

    def _business_summary(self):
        arr = db.session.query(db.func.sum(Account.arr)).filter(Account.is_customer == True).scalar() or 0
        custs = Account.query.filter_by(is_customer=True).count()
        pipe = db.session.query(db.func.sum(Opportunity.amount)).filter(
            ~Opportunity.stage.in_(["Closed Won", "Closed Lost"])).scalar() or 0
        green = CustomerHealth.query.filter_by(status="Green").count()
        return (f"**Business summary:** CloudVision Analytics serves {custs} customers generating {self._fmt(arr)} ARR. "
                f"Open pipeline stands at {self._fmt(pipe)}. "
                f"{green} of {custs} customers are in green health. "
                f"Net revenue retention is trending at ~112% driven by Data Apps expansion. "
                "Key watch items: red-health enterprise accounts and Q3 renewal concentration.")

    def _board_summary(self):
        arr = db.session.query(db.func.sum(Account.arr)).filter(Account.is_customer == True).scalar() or 0
        pipe = db.session.query(db.func.sum(Opportunity.amount)).filter(
            ~Opportunity.stage.in_(["Closed Won", "Closed Lost"])).scalar() or 0
        return ("**Board Meeting Summary — Q3 FY26**\n\n"
                f"1. ARR: {self._fmt(arr)}, up 24% YoY; NRR 112%.\n"
                f"2. Pipeline: {self._fmt(pipe)} open, 3.2x coverage on Q3 target.\n"
                "3. Customer health: 68% green, 22% yellow, 10% red; churn save-plays active on top 5 red accounts.\n"
                "4. Product: Data Apps module driving 40% of expansion bookings.\n"
                "5. Asks: approve two enterprise CSM hires; EMEA expansion budget for FY27.")

    def _forecast_answer(self):
        pipe = db.session.query(db.func.sum(Opportunity.amount * Opportunity.probability / 100)).filter(
            ~Opportunity.stage.in_(["Closed Won", "Closed Lost"])).scalar() or 0
        return (f"**Next quarter prediction:** Weighted pipeline suggests {self._fmt(pipe)} in probable bookings. "
                "AI models (based on stage conversion and rep attainment history) put the likely range at "
                f"{self._fmt(pipe*0.85)}–{self._fmt(pipe*1.15)}. "
                "Renewal base is 94% secure; two enterprise renewals drive most downside risk. "
                "Confidence: moderate-high.")

    def _pipeline_answer(self):
        stalled = Opportunity.query.filter(
            ~Opportunity.stage.in_(["Closed Won", "Closed Lost"]),
            Opportunity.ai_score < 40).count()
        return (f"**Pipeline inspection:** {stalled} open deals have AI scores below 40 (stalled or low-engagement). "
                "Common patterns: no activity in 21+ days, missing next steps, and single-threaded contacts. "
                "AI recommends requalifying deals older than 120 days and multi-threading the top 10 by value.")

    def _renewal_answer(self):
        soon = Renewal.query.filter(Renewal.status.in_(["Upcoming", "At Risk"])).order_by(Renewal.renewal_date).limit(5).all()
        lines = [f"• {r.account.name} — {r.renewal_date.strftime('%b %d, %Y')}, {self._fmt(r.amount)}, {r.likelihood}% likely" for r in soon if r.account]
        return "**Upcoming renewals:**\n\n" + "\n".join(lines) + "\n\nAI flags any renewal below 70% likelihood for executive engagement."

    def _email_draft(self):
        return ("**Draft email:**\n\nSubject: Following up on our conversation\n\n"
                "Hi {first name},\n\nThanks for your time today. As discussed, I'm sharing a summary of how "
                "CloudVision can reduce your reporting cycle from days to minutes. Happy to set up a technical "
                "deep-dive with your analytics team next week.\n\nBest regards")

    def _expansion_answer(self):
        cands = (db.session.query(Account, CustomerHealth)
                 .join(CustomerHealth, CustomerHealth.account_id == Account.id)
                 .filter(CustomerHealth.score >= 80, Account.is_customer == True)
                 .order_by(Account.arr.desc()).limit(5).all())
        lines = [f"• **{a.name}** — health {h.score}, ARR {self._fmt(a.arr)}: strong Data Apps fit" for a, h in cands]
        return "**Top expansion opportunities:**\n\n" + "\n".join(lines) + "\n\nAI suggests bundling Data Apps + Advanced Security in renewal conversations."

    def _cashflow_answer(self):
        late = Contract.query.filter(Contract.payment_status != "Current").count()
        return (f"**Cash flow forecast:** Collections are healthy; {late} contracts show late or delinquent payments. "
                "Projected Q3 cash receipts: $14.2M (92% of billings). "
                "AI recommends dunning outreach on delinquent accounts before month-end close.")

    def _dataquality_answer(self):
        return ("**Data quality scan:** Found 14 potential duplicate accounts (name similarity > 90%), "
                "37 opportunities missing next steps, and 22 deals with no activity in 30+ days. "
                "AI recommends merging the duplicate pairs listed in Sales Ops → Duplicates, and a pipeline "
                "hygiene sprint before forecast lock.")


# ------------------------------------------------------------------
provider = MockAIProvider()


def ask(prompt: str, user=None, account=None, context_label=None) -> str:
    """Main entry point used by routes."""
    response = provider.complete(prompt, {"account": account})
    try:
        if user is not None:
            db.session.add(AIHistory(user_id=user.id, prompt=prompt, response=response,
                                     context=context_label or "global"))
            db.session.commit()
    except Exception:
        db.session.rollback()
    return response
