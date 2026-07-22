"""Generate realistic demo data for CloudVision Analytics CRM."""
import random
from datetime import datetime, date, timedelta
from database import db
from models import (Role, User, Account, Contact, Product, Opportunity, Contract,
                    Renewal, Activity, Meeting, Task, Note, CustomerHealth,
                    UsageMetric, Email, Notification, AIHistory, AuditLog)

random.seed(42)
TODAY = date.today()

FIRST = ["James","Mary","Robert","Patricia","John","Jennifer","Michael","Linda","David","Elizabeth",
         "William","Barbara","Richard","Susan","Joseph","Jessica","Thomas","Sarah","Charles","Karen",
         "Priya","Wei","Carlos","Fatima","Yuki","Ahmed","Elena","Raj","Sofia","Omar","Anika","Lucas",
         "Emma","Noah","Olivia","Liam","Ava","Ethan","Mia","Diego","Chloe","Arjun","Zara","Kenji",
         "Ingrid","Marco","Nadia","Pavel","Amara","Tomas"]
LAST = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez",
        "Chen","Patel","Kim","Nguyen","Singh","Kumar","Ali","Khan","Lopez","Gonzalez","Wilson","Anderson",
        "Taylor","Thomas","Moore","Jackson","Martin","Lee","Thompson","White","Tanaka","Ivanov","Silva",
        "Müller","Rossi","Kowalski","Andersson","O'Brien","Fischer","Novak"]
COMPANY_A = ["Apex","Summit","Vertex","Nova","Quantum","Stellar","Pinnacle","Horizon","Atlas","Titan",
             "Fusion","Vector","Orbit","Prime","Core","Nexus","Pulse","Spark","Forge","Beacon","Cascade",
             "Granite","Harbor","Iron","Juniper","Keystone","Lumen","Meridian","Northwind","Oakmont",
             "Pacific","Redwood","Sterling","Crestline","Bluepeak","Everstone","Falcon","Glacier",
             "Highland","Ironclad"]
COMPANY_B = ["Systems","Technologies","Industries","Solutions","Group","Corporation","Labs","Dynamics",
             "Holdings","Enterprises","Logistics","Manufacturing","Healthcare","Financial","Retail",
             "Energy","Networks","Analytics","Global","Partners"]
INDUSTRIES = ["Manufacturing","Financial Services","Healthcare","Retail","Technology","Energy",
              "Telecommunications","Pharmaceuticals","Logistics","Consumer Goods","Insurance","Media"]
REGIONS = ["North America","EMEA","APAC","LATAM"]
SEGMENTS = ["Enterprise","Mid-Market","SMB"]
TITLES = ["CFO","VP Finance","Director of Analytics","CIO","VP Data & Analytics","Controller",
          "Head of BI","CTO","Director of IT","VP Operations","Chief Data Officer","Finance Manager",
          "Analytics Manager","Senior Data Engineer","VP Supply Chain","CEO"]
COMPETITORS = ["Tableau","Power BI","Looker","Qlik","Domo","ThoughtSpot", None, None]
NEXT_STEPS = ["Schedule technical deep-dive","Send proposal","Security review call","Align on pricing",
              "Executive sponsor meeting","POC kickoff","Legal review","Reference call","Demo for finance team",
              "Contract redlines"]

AVATAR_COLORS = ["#6366f1","#8b5cf6","#ec4899","#f59e0b","#10b981","#3b82f6","#ef4444","#14b8a6"]


def _name():
    return random.choice(FIRST), random.choice(LAST)


def _company(used):
    while True:
        n = f"{random.choice(COMPANY_A)} {random.choice(COMPANY_B)}"
        if n not in used:
            used.add(n)
            return n


def seed():
    print("Seeding roles & users...")
    roles = {}
    for name, slug, desc in [
        ("CEO", "ceo", "Chief Executive Officer"),
        ("VP Sales", "vp_sales", "Vice President of Sales"),
        ("Sales Rep", "sales_rep", "Account Executive"),
        ("Customer Success", "csm", "Customer Success Manager"),
        ("Finance", "finance", "Finance & Revenue Operations"),
        ("Sales Operations", "sales_ops", "Sales Operations Analyst"),
        ("Executive Assistant", "exec_assistant", "Executive Assistant"),
        ("Employee", "employee", "Employee"),
    ]:
        r = Role(name=name, slug=slug, description=desc)
        db.session.add(r)
        roles[slug] = r
    db.session.flush()

    def mk_user(name, email, slug, title, quota=0, region="North America"):
        u = User(name=name, email=email, role_id=roles[slug].id, active_role_slug=slug,
                 title=title, quota=quota, region=region,
                 phone=f"+1 (415) 555-{random.randint(1000,9999)}",
                 avatar_color=random.choice(AVATAR_COLORS))
        db.session.add(u)
        return u

    # Named demo users
    demo_users = {
        "ceo": mk_user("Alexandra Reyes", "ceo@cloudvision.com", "ceo", "Chief Executive Officer"),
        "vp_sales": mk_user("Marcus Webb", "vpsales@cloudvision.com", "vp_sales", "VP of Sales", quota=24_000_000),
        "sales_rep": mk_user("Jordan Ellis", "rep@cloudvision.com", "sales_rep", "Enterprise Account Executive", quota=1_500_000),
        "csm": mk_user("Sophia Laurent", "csm@cloudvision.com", "csm", "Senior Customer Success Manager"),
        "finance": mk_user("Daniel Osei", "finance@cloudvision.com", "finance", "VP of Finance"),
        "sales_ops": mk_user("Rachel Kim", "salesops@cloudvision.com", "sales_ops", "Director of Sales Operations"),
        "exec_assistant": mk_user("Taylor Morgan", "ea@cloudvision.com", "exec_assistant", "Executive Assistant to CEO"),
    }

    reps = [demo_users["sales_rep"]]
    for i in range(29):
        f, l = _name()
        reps.append(mk_user(f"{f} {l}", f"rep{i+1}@cloudvision.com", "sales_rep",
                            "Account Executive", quota=random.choice([800_000, 1_000_000, 1_200_000, 1_500_000]),
                            region=random.choice(REGIONS)))
    csms = [demo_users["csm"]]
    for i in range(9):
        f, l = _name()
        csms.append(mk_user(f"{f} {l}", f"csm{i+1}@cloudvision.com", "csm",
                            "Customer Success Manager", region=random.choice(REGIONS)))
    # other employees to reach ~300
    for i in range(253):
        f, l = _name()
        mk_user(f"{f} {l}", f"emp{i+1}@cloudvision.com", "employee",
                random.choice(["Software Engineer","Product Manager","Support Engineer","Marketing Manager",
                               "Data Scientist","HR Partner","Solutions Architect"]),
                region=random.choice(REGIONS))
    db.session.flush()

    print("Seeding products...")
    products = []
    for name, cat, price, desc in [
        ("CloudVision Platform", "Core", 120_000, "Unified analytics platform with direct data mapping"),
        ("Data Apps Module", "Add-on", 45_000, "Prebuilt analytics applications for ERP data"),
        ("Advanced Security", "Add-on", 30_000, "Row-level security, SSO, audit and compliance"),
        ("AI Insights Engine", "Add-on", 60_000, "ML-powered forecasting and anomaly detection"),
        ("Embedded Analytics", "Add-on", 50_000, "White-label dashboards for customer-facing apps"),
        ("Premium Support", "Services", 25_000, "24/7 support with dedicated TAM"),
        ("Training & Enablement", "Services", 15_000, "Admin and analyst certification programs"),
    ]:
        p = Product(name=name, category=cat, list_price=price, description=desc)
        products.append(p)
        db.session.add(p)
    db.session.flush()

    print("Seeding accounts (200 customers + 60 prospects)...")
    used = set()
    accounts, customers = [], []
    for i in range(260):
        is_cust = i < 200
        seg = random.choices(SEGMENTS, weights=[0.35, 0.45, 0.20])[0]
        arr = 0
        if is_cust:
            arr = {"Enterprise": random.randint(250, 900) * 1000,
                   "Mid-Market": random.randint(80, 250) * 1000,
                   "SMB": random.randint(25, 80) * 1000}[seg]
        name = _company(used)
        a = Account(name=name, industry=random.choice(INDUSTRIES), region=random.choice(REGIONS),
                    segment=seg, website=f"www.{name.split()[0].lower()}.com",
                    employees=random.randint(200, 20000), arr=arr, is_customer=is_cust,
                    owner_id=random.choice(reps).id,
                    csm_id=random.choice(csms).id if is_cust else None,
                    created_at=datetime.utcnow() - timedelta(days=random.randint(100, 1400)))
        db.session.add(a)
        accounts.append(a)
        if is_cust:
            customers.append(a)
    db.session.flush()

    print("Seeding contacts (500)...")
    contacts = []
    for i in range(500):
        a = random.choice(accounts)
        f, l = _name()
        c = Contact(first_name=f, last_name=l, title=random.choice(TITLES),
                    email=f"{f.lower()}.{l.lower().replace(chr(39),'').replace('ü','u')}@{a.website[4:]}",
                    phone=f"+1 ({random.randint(200,989)}) 555-{random.randint(1000,9999)}",
                    is_executive_sponsor=random.random() < 0.15, account_id=a.id)
        db.session.add(c)
        contacts.append(c)
    db.session.flush()

    print("Seeding opportunities (600)...")
    stages_open = ["Lead", "Qualified", "Discovery", "Proposal", "Negotiation"]
    opp_names = ["Platform Expansion","Analytics Modernization","Data Apps Rollout","Enterprise License",
                 "BI Consolidation","Cloud Migration Analytics","Finance Analytics","Supply Chain Analytics",
                 "Embedded Analytics Deal","AI Insights Upgrade","Multi-Year Renewal","Global Rollout"]
    opps = []
    for i in range(600):
        a = random.choice(accounts)
        closed = random.random() < 0.45
        if closed:
            stage = random.choices(["Closed Won", "Closed Lost"], weights=[0.6, 0.4])[0]
            prob = 100 if stage == "Closed Won" else 0
            close_dt = TODAY - timedelta(days=random.randint(5, 540))
            expected = close_dt
        else:
            stage = random.choices(stages_open, weights=[0.25, 0.22, 0.2, 0.18, 0.15])[0]
            prob = {"Lead": 10, "Qualified": 25, "Discovery": 45, "Proposal": 65, "Negotiation": 80}[stage]
            close_dt = None
            expected = TODAY + timedelta(days=random.randint(7, 200))
        amount = random.randint(30, 600) * 1000
        o = Opportunity(name=f"{a.name} — {random.choice(opp_names)}", stage=stage, amount=amount,
                        probability=prob, expected_close=expected,
                        opp_type=random.choices(["New Business", "Expansion", "Renewal"], weights=[0.5, 0.3, 0.2])[0],
                        competitor=random.choice(COMPETITORS), next_step=random.choice(NEXT_STEPS),
                        ai_score=min(99, max(5, prob + random.randint(-25, 25))),
                        account_id=a.id, owner_id=a.owner_id or random.choice(reps).id,
                        product_id=random.choice(products).id,
                        created_at=datetime.utcnow() - timedelta(days=random.randint(10, 700)),
                        closed_at=close_dt)
        db.session.add(o)
        opps.append(o)
    db.session.flush()

    print("Seeding contracts & renewals (300)...")
    for i, a in enumerate(customers):
        n_contracts = 2 if i < 100 else 1  # 300 total
        for j in range(n_contracts):
            # Spread renewals across ~ -8 to +23 months so near-term windows
            # (30/60/90/180d) have content. Same single randint draw as before,
            # so the downstream RNG stream — and all other seeded data — is unchanged.
            off = random.randint(60, 1000)
            end = TODAY + timedelta(days=off - 300)   # renewal (contract end) date
            start = end - timedelta(days=365 * 3)
            value = a.arr * 3 * random.uniform(0.8, 1.1)
            c = Contract(number=f"CV-{2023 + j}-{1000 + i * 2 + j}", account_id=a.id, value=value,
                         start_date=start, end_date=end, term_months=36,
                         status="Active" if end > TODAY else "Expired",
                         payment_status=random.choices(["Current", "Late", "Delinquent"], weights=[0.85, 0.1, 0.05])[0])
            db.session.add(c)
            db.session.flush()
            rl = random.randint(45, 98)
            rdate = end
            status = "Upcoming"
            if rdate < TODAY:
                status = random.choices(["Renewed", "Churned"], weights=[0.9, 0.1])[0]
            elif rl < 60:
                status = "At Risk"
            elif (rdate - TODAY).days < 90:
                status = "In Progress"
            db.session.add(Renewal(account_id=a.id, contract_id=c.id, renewal_date=rdate,
                                   amount=a.arr * random.uniform(0.95, 1.15), status=status,
                                   likelihood=rl, owner_id=a.csm_id))

    print("Seeding customer health (200)...")
    for a in customers:
        score = random.choices([random.randint(75, 98), random.randint(50, 74), random.randint(20, 49)],
                               weights=[0.62, 0.26, 0.12])[0]
        status = "Green" if score >= 75 else ("Yellow" if score >= 50 else "Red")
        db.session.add(CustomerHealth(
            account_id=a.id, score=score, status=status,
            product_usage=max(5, min(100, score + random.randint(-15, 15))),
            exec_meetings=random.randint(0, 4) if score > 50 else random.randint(0, 1),
            training_completion=max(5, min(100, score + random.randint(-20, 20))),
            nps=random.randint(20, 80) if status == "Green" else (random.randint(-10, 40) if status == "Yellow" else random.randint(-60, 10)),
            adoption=max(5, min(100, score + random.randint(-10, 10))),
            trend=random.choices(["up", "flat", "down"], weights=[0.4, 0.35, 0.25] if status == "Green" else [0.15, 0.3, 0.55])[0]))

    print("Seeding activities (800)...")
    subjects = {"Call": ["Discovery call","Pricing discussion","Renewal check-in","Intro call","Escalation call"],
                "Email": ["Sent proposal","Follow-up on demo","Shared case study","Renewal reminder","QBR agenda"],
                "Meeting": ["Product demo","QBR","Executive briefing","Technical deep-dive","Roadmap review"],
                "Demo": ["Platform demo","Data Apps walkthrough","AI Insights demo"],
                "Note": ["Account research","Competitive intel","Champion left company","Budget confirmed"]}
    all_users = reps + csms
    for i in range(800):
        t = random.choice(list(subjects.keys()))
        a = random.choice(accounts)
        db.session.add(Activity(activity_type=t, subject=random.choice(subjects[t]),
                                detail=f"{t} with {a.name} regarding analytics initiative.",
                                activity_date=datetime.utcnow() - timedelta(days=random.randint(0, 120),
                                                                            hours=random.randint(0, 23)),
                                account_id=a.id,
                                opportunity_id=random.choice(opps).id if random.random() < 0.5 else None,
                                user_id=random.choice(all_users).id))

    print("Seeding meetings (400)...")
    mtypes = ["QBR", "Demo", "Discovery", "Executive", "Kickoff"]
    for i in range(400):
        a = random.choice(accounts)
        mt = random.choice(mtypes)
        past = random.random() < 0.6
        start = (datetime.utcnow() - timedelta(days=random.randint(1, 90)) if past
                 else datetime.utcnow() + timedelta(days=random.randint(0, 45), hours=random.randint(1, 8)))
        db.session.add(Meeting(title=f"{mt}: {a.name}", meeting_type=mt,
                               start_time=start.replace(minute=random.choice([0, 30]), second=0, microsecond=0),
                               duration_min=random.choice([30, 45, 60, 90]),
                               location=random.choice(["Zoom", "Google Meet", "On-site", "Teams"]),
                               is_executive=(mt == "Executive" or random.random() < 0.15),
                               account_id=a.id, organizer_id=random.choice(all_users).id))

    print("Seeding tasks (300)...")
    task_titles = ["Send follow-up email","Update opportunity next steps","Prepare QBR deck","Call executive sponsor",
                   "Review contract redlines","Log meeting notes","Send renewal quote","Schedule technical review",
                   "Update forecast category","Check adoption dashboard"]
    for i in range(300):
        a = random.choice(accounts)
        db.session.add(Task(title=random.choice(task_titles),
                            due_date=TODAY + timedelta(days=random.randint(-5, 21)),
                            priority=random.choices(["High", "Medium", "Low"], weights=[0.3, 0.5, 0.2])[0],
                            status=random.choices(["Open", "Done"], weights=[0.65, 0.35])[0],
                            account_id=a.id, owner_id=random.choice(all_users).id))

    print("Seeding notes (5000)...")
    note_bodies = ["Customer confirmed budget for expansion in Q4.",
                   "Champion is very engaged; wants weekly syncs during POC.",
                   "Concern raised about SSO integration timeline.",
                   "CFO asked for 3-year TCO comparison vs current stack.",
                   "Adoption improving after admin training session.",
                   "Security questionnaire returned; legal review next.",
                   "Competitor mentioned in evaluation: Power BI.",
                   "Exec sponsor changed — need to rebuild relationship.",
                   "Positive QBR; NPS survey sent to stakeholders.",
                   "Usage dipped during holiday period; monitoring."]
    notes = [Note(body=random.choice(note_bodies), account_id=random.choice(accounts).id,
                  author_id=random.choice(all_users).id,
                  created_at=datetime.utcnow() - timedelta(days=random.randint(0, 365)))
             for _ in range(5000)]
    db.session.bulk_save_objects(notes)

    print("Seeding usage metrics (2000)...")
    usage = []
    sample_custs = random.sample(customers, 100)
    for a in sample_custs:
        base = random.randint(20, 400)
        for w in range(20):
            d = TODAY - timedelta(weeks=20 - w)
            usage.append(UsageMetric(account_id=a.id, metric_date=d,
                                     active_users=max(1, int(base * random.uniform(0.7, 1.3))),
                                     queries_run=random.randint(500, 20000),
                                     dashboards_viewed=random.randint(50, 3000)))
    db.session.bulk_save_objects(usage)

    print("Seeding emails (300)...")
    email_subjects = ["Re: Proposal for analytics modernization","QBR agenda for next week",
                      "Renewal quote attached","Following up on our demo","Security review documents",
                      "Introduction — new CSM","Pricing options discussed","POC success criteria"]
    for i in range(300):
        a = random.choice(accounts)
        c = random.choice(contacts)
        u = random.choice(all_users)
        outbound = random.random() < 0.5
        db.session.add(Email(subject=random.choice(email_subjects),
                             snippet="Thanks for the time today — sharing a quick summary of what we discussed and proposed next steps...",
                             sender=u.email if outbound else c.email,
                             recipient=c.email if outbound else u.email,
                             sent_at=datetime.utcnow() - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23)),
                             account_id=a.id, user_id=u.id))

    print("Seeding notifications...")
    notif_templates = [
        ("Renewal", "Renewal for {a} due in {d} days — {v}", "/renewals"),
        ("Contract", "Contract with {a} expires in {d} days", "/contracts"),
        ("Health", "Health score dropped for {a} — now in {s} status", "/customer-success"),
        ("Deal", "Deal '{a} — Expansion' has had no activity for 21 days", "/opportunities"),
        ("Task", "Task due today: Send renewal quote to {a}", "/tasks"),
        ("Meeting", "Meeting with {a} starts in 30 minutes", "/meetings"),
        ("Activity", "No customer activity on {a} in 30 days", "/accounts"),
    ]
    for u in demo_users.values():
        for i in range(random.randint(4, 7)):
            cat, msg, link = random.choice(notif_templates)
            a = random.choice(customers)
            db.session.add(Notification(
                user_id=u.id, category=cat,
                message=msg.format(a=a.name, d=random.randint(5, 60),
                                   v=f"${random.randint(50,500)}K", s=random.choice(["Yellow", "Red"])),
                link=link, is_read=random.random() < 0.3,
                created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 72))))

    db.session.add(AuditLog(user_id=demo_users["ceo"].id, action="Database seeded", entity="system", entity_id=0))
    db.session.commit()
    print("Seed complete.")
