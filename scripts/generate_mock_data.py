"""
StackFlow RevOps — Mock Data Generator
Phase 2 of PROJECT_PLAN.md

Generates realistic B2B SaaS data with intentional business patterns:
- 8 "at risk" accounts (past_due + low activity)
- 5 "expansion ready" accounts (near seat limit)
- 3 "PQL" accounts (trial + activated, not yet in Sales)
- Rest: healthy mix of starter/growth/enterprise

Output: data/raw/*.json
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)  # reproducible

# ── helpers ──────────────────────────────────────────────────────────────────

def uid(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:8]}"

def rand_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))

def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

NOW = datetime(2024, 6, 1)
YEAR_AGO = NOW - timedelta(days=365)
SIX_M = NOW - timedelta(days=180)

# ── company profiles ──────────────────────────────────────────────────────────

INDUSTRIES = [
    "Software", "FinTech", "HealthTech", "E-commerce",
    "Cybersecurity", "DevTools", "MarTech", "EdTech",
]

COMPANIES = [
    # (name, domain, industry, employee_count, segment)
    # segment: at_risk | expansion | pql | healthy
    ("Acme Corp",         "acme.com",         "Software",      120,  "at_risk"),
    ("Brightwave Labs",   "brightwave.io",    "FinTech",        85,  "at_risk"),
    ("Cascadia Systems",  "cascadiasys.com",  "HealthTech",    200,  "at_risk"),
    ("DeltaCore Inc",     "deltacore.com",    "E-commerce",     60,  "at_risk"),
    ("Evergreen Digital", "evergreen.io",     "MarTech",        95,  "at_risk"),
    ("Forge Analytics",   "forgeanalytics.co","DevTools",       75,  "at_risk"),
    ("GridSpark",         "gridspark.com",    "Software",      110,  "at_risk"),
    ("HorizonAI",         "horizonai.io",     "Software",      180,  "at_risk"),
    ("IronMesh",          "ironmesh.com",     "Cybersecurity", 250,  "expansion"),
    ("JetStream Cloud",   "jetstream.cloud",  "Software",      320,  "expansion"),
    ("KineticHR",         "kineticher.com",   "FinTech",       140,  "expansion"),
    ("LatticeOps",        "latticeops.io",    "DevTools",      190,  "expansion"),
    ("Meridian Tech",     "meridiantech.com", "Software",      410,  "expansion"),
    ("NovaBuild",         "novabuild.dev",    "DevTools",       22,  "pql"),
    ("OmniStack",         "omnistack.io",     "Software",       18,  "pql"),
    ("PeakFlow",          "peakflow.co",      "MarTech",        31,  "pql"),
    ("Quantum Leap",      "quantumleap.ai",   "Software",      150,  "healthy"),
    ("RootSignal",        "rootsignal.com",   "Cybersecurity", 220,  "healthy"),
    ("SkyBridge",         "skybridge.io",     "FinTech",        90,  "healthy"),
    ("TerraScale",        "terrascale.com",   "E-commerce",    175,  "healthy"),
    ("Unified.io",        "unified.io",       "DevTools",      130,  "healthy"),
    ("VaultEdge",         "vaultedge.com",    "Cybersecurity", 300,  "healthy"),
    ("WavePath",          "wavepath.io",      "MarTech",        80,  "healthy"),
    ("XenonData",         "xenondata.com",    "Software",      160,  "healthy"),
    ("YieldBridge",       "yieldbridge.co",   "FinTech",       210,  "healthy"),
    ("ZenithOps",         "zenithops.io",     "DevTools",      240,  "healthy"),
    ("Arclight Systems",  "arclight.io",      "Software",      100,  "healthy"),
    ("BluePeak",          "bluepeak.com",     "HealthTech",    280,  "healthy"),
    ("Cobalt Labs",       "cobaltlabs.io",    "Software",       70,  "healthy"),
    ("DataForge",         "dataforge.com",    "DevTools",      190,  "healthy"),
    ("Embark Analytics",  "embark.io",        "MarTech",       120,  "healthy"),
    ("FluxPoint",         "fluxpoint.com",    "E-commerce",     55,  "healthy"),
    ("GlacierTech",       "glaciertech.io",   "Software",      145,  "healthy"),
    ("Helix Security",    "helixsec.com",     "Cybersecurity", 310,  "healthy"),
    ("Impulse AI",        "impulseai.io",     "Software",      230,  "healthy"),
    ("Juno Platforms",    "juno.io",          "FinTech",       160,  "healthy"),
    ("Kinetic Data",      "kineticdata.com",  "DevTools",       95,  "healthy"),
    ("Luminos Labs",      "luminos.io",       "Software",      185,  "healthy"),
    ("Moonsail Tech",     "moonsail.io",      "HealthTech",    125,  "healthy"),
    ("Nexwave",           "nexwave.com",      "Software",      270,  "healthy"),
    ("Orbital Systems",   "orbital.io",       "E-commerce",    200,  "healthy"),
    ("Prism Analytics",   "prism.io",         "MarTech",       140,  "healthy"),
    ("Quasar Dev",        "quasar.dev",       "DevTools",       65,  "healthy"),
    ("Radius Cloud",      "radiuscloud.io",   "Software",      310,  "healthy"),
    ("Solaris Labs",      "solaris.io",       "Cybersecurity", 175,  "healthy"),
    ("Tidal Systems",     "tidalsys.com",     "Software",      135,  "healthy"),
    ("Ultrawave",         "ultrawave.io",     "FinTech",       290,  "healthy"),
    ("Vantage IO",        "vantage.io",       "DevTools",      155,  "healthy"),
    ("WhiteLight Tech",   "whitelight.com",   "Software",       85,  "healthy"),
    ("Zephyr Analytics",  "zephyr.io",        "MarTech",       220,  "healthy"),
]

PLANS = {
    "starter":    {"price_cents": 1200, "seat_limit": 10},
    "growth":     {"price_cents": 2500, "seat_limit": 50},
    "enterprise": {"price_cents": 6000, "seat_limit": 500},
}

DEAL_STAGES = [
    "appointmentscheduled",
    "qualifiedtobuy",
    "presentationscheduled",
    "decisionmakerboughtin",
    "contractsent",
    "closedwon",
    "closedlost",
]

LIFECYCLE_STAGES = {
    "at_risk":    "customer",
    "expansion":  "customer",
    "pql":        "marketingqualifiedlead",
    "healthy":    "customer",
}

LEAD_STATUSES = {
    "at_risk":   "IN_PROGRESS",
    "expansion": "OPEN",
    "pql":       "NEW",
    "healthy":   "OPEN",
}

EVENTS = [
    "project_created", "issue_assigned", "sprint_started",
    "git_integration_connected", "ai_prioritization_used",
    "invite_sent", "comment_added", "report_viewed",
]

ACTIVATION_EVENTS = {"git_integration_connected", "project_created", "invite_sent"}

TICKET_TAGS = {
    "at_risk":   [["billing", "churn-risk"], ["bug", "churn-risk"], ["onboarding"]],
    "expansion": [["feature-request"], ["onboarding"]],
    "pql":       [["onboarding"], ["bug"]],
    "healthy":   [["feature-request"], ["bug"], ["onboarding"]],
}

# ── state containers ──────────────────────────────────────────────────────────

hs_companies   = []
hs_deals       = []
hs_contacts    = []
hs_engagements = []
stripe_subs    = []
stripe_inv     = []
stripe_pay     = []
int_workspaces = []
int_users      = []
int_events     = []
zd_tickets     = []

# ── build each company ────────────────────────────────────────────────────────

for idx, (name, domain, industry, emp_count, segment) in enumerate(COMPANIES):

    # ── IDs ──
    hs_company_id    = str(100_000 + idx)
    ws_id            = uid("ws_")
    stripe_cust_id   = uid("cus_")
    stripe_sub_id    = uid("sub_")

    created_at = rand_date(YEAR_AGO, SIX_M)

    # ── plan assignment ──
    if segment == "pql":
        plan = "starter"
        sub_status = "trialing"
        trial_end = NOW + timedelta(days=random.randint(3, 14))
    elif segment == "at_risk":
        plan = random.choice(["starter", "growth"])
        sub_status = random.choice(["past_due", "unpaid"])
        trial_end = None
    elif segment == "expansion":
        plan = random.choice(["growth", "enterprise"])
        sub_status = "active"
        trial_end = None
    else:
        plan = random.choices(
            ["starter", "growth", "enterprise"], weights=[5, 3, 2]
        )[0]
        sub_status = "active"
        trial_end = None

    seat_limit = PLANS[plan]["seat_limit"]
    price_cents = PLANS[plan]["price_cents"]

    # seat usage
    if segment == "expansion":
        seats_used = int(seat_limit * random.uniform(0.85, 0.98))
    elif segment == "at_risk":
        seats_used = int(seat_limit * random.uniform(0.2, 0.5))
    elif segment == "pql":
        seats_used = random.randint(2, 6)
    else:
        seats_used = int(seat_limit * random.uniform(0.4, 0.75))

    # ── Marketing Attribution ──
    utm_source = random.choice(["Organic Search", "Google Ads", "LinkedIn", "Direct", "Referral"])
    if utm_source == "Organic Search":
        utm_campaign = "SEO_2023"
    elif utm_source == "Google Ads":
        utm_campaign = random.choice(["Q1_Competitor_Keywords", "Retargeting_V2"])
    elif utm_source == "LinkedIn":
        utm_campaign = "B2B_SaaS_Leaders"
    else:
        utm_campaign = "None"

    # ── HubSpot company ──
    hs_companies.append({
        "hs_object_id":       hs_company_id,
        "name":               name,
        "domain":             domain,
        "industry":           industry,
        "employee_count":     emp_count,
        "hs_lead_status":     LEAD_STATUSES[segment],
        "lifecyclestage":     LIFECYCLE_STAGES[segment],
        "hubspot_owner_id":   str(random.randint(1, 8)),
        "utm_source":         utm_source,
        "utm_campaign":       utm_campaign,
        "createdate":         iso(created_at),
        "hs_lastmodifieddate": iso(rand_date(created_at, NOW)),
    })

    # ── HubSpot deals (1-2 per company) ──
    n_deals = 1 if segment == "pql" else random.randint(1, 2)
    for d in range(n_deals):
        stage = "closedwon" if segment in ("at_risk", "expansion", "healthy") \
                else random.choice(DEAL_STAGES[:4])
        close_dt = rand_date(created_at, NOW) if stage == "closedwon" \
                   else rand_date(NOW, NOW + timedelta(days=90))
        hs_deals.append({
            "hs_object_id":              uid("deal_"),
            "dealname":                  f"{name} — {plan.title()} {'Renewal' if d > 0 else 'New'}",
            "dealstage":                 stage,
            "amount":                    price_cents * seats_used * 12 / 100,
            "closedate":                 iso(close_dt),
            "pipeline":                  "default",
            "associated_company_id":     hs_company_id,
            "hs_deal_stage_probability": 1.0 if stage == "closedwon" else round(random.uniform(0.1, 0.7), 2),
            "createdate":                iso(created_at),
        })

    # ── HubSpot contacts (2-4 per company) ──
    company_contact_emails = []
    roles = ["CTO", "VP Engineering", "Engineering Manager", "Lead Developer", "DevOps Lead"]
    for _ in range(random.randint(2, 4)):
        fname = random.choice(["Alex","Jordan","Taylor","Morgan","Casey","Riley","Drew","Quinn"])
        lname = random.choice(["Smith","Johnson","Lee","Brown","Davis","Wilson","Moore","Clark"])
        email = f"{fname.lower()}.{lname.lower()}@{domain}"
        company_contact_emails.append(email)
        hs_contacts.append({
            "hs_object_id":        uid("contact_"),
            "email":               email,
            "firstname":           fname,
            "lastname":            lname,
            "jobtitle":            random.choice(roles),
            "associated_company_id": hs_company_id if random.random() < 0.8 else None,
            "hs_lead_status":      LEAD_STATUSES[segment],
            "linkedin_url":        f"https://linkedin.com/in/{fname.lower()}-{lname.lower()}-{uid('')}",
            "is_enriched":         True if random.random() < 0.8 else False,
            "createdate":          iso(created_at),
            "lastmodifieddate":    iso(rand_date(created_at, NOW)),
        })

    # ── HubSpot Engagements (Sales Activities) ──
    n_engagements = random.randint(3, 15) if segment != "pql" else random.randint(0, 2)
    for _ in range(n_engagements):
        eng_type = random.choices(["CALL", "EMAIL", "MEETING"], weights=[3, 6, 2])[0]
        eng_time = rand_date(created_at, NOW)
        hs_engagements.append({
            "hs_engagement_id":      uid("eng_"),
            "engagement_type":       eng_type,
            "associated_company_id": hs_company_id,
            "owner_id":              str(random.randint(1, 8)),
            "created_at":            iso(eng_time)
        })

    # ── Stripe subscription ──
    sub_start = created_at if segment != "pql" else NOW - timedelta(days=random.randint(7, 21))
    cancel_at_period_end = segment == "at_risk" and random.random() < 0.4

    stripe_subs.append({
        "id":                   stripe_sub_id,
        "customer_id":          stripe_cust_id,
        "status":               sub_status,
        "plan_id":              f"plan_{plan}_{'annual' if plan == 'enterprise' else 'monthly'}",
        "quantity":             seats_used,
        "unit_amount":          price_cents,
        "currency":             "usd",
        "current_period_start": iso(sub_start),
        "current_period_end":   iso(sub_start + timedelta(days=30)),
        "cancel_at_period_end": cancel_at_period_end,
        "created":              iso(sub_start),
        "canceled_at":          None,
        "trial_end":            iso(trial_end) if trial_end else None,
        "metadata": {
            "workspace_id":        ws_id,
            "hubspot_company_id":  hs_company_id,
        },
    })

    # ── Stripe invoices (12 months) ──
    for m in range(12):
        inv_date = sub_start + timedelta(days=30 * m)
        if inv_date > NOW:
            break
        mrr = price_cents * seats_used
        if segment == "at_risk" and m >= 9:
            inv_status = random.choice(["open", "uncollectible"])
            paid_at = None
        else:
            inv_status = "paid"
            paid_at = iso(inv_date + timedelta(days=random.randint(0, 3)))

        inv_id = uid("in_")
        stripe_inv.append({
            "id":              inv_id,
            "subscription_id": stripe_sub_id,
            "customer_id":     stripe_cust_id,
            "status":          inv_status,
            "amount_due":      mrr,
            "amount_paid":     mrr if inv_status == "paid" else 0,
            "amount_remaining": 0 if inv_status == "paid" else mrr,
            "currency":        "usd",
            "period_start":    iso(inv_date),
            "period_end":      iso(inv_date + timedelta(days=30)),
            "due_date":        iso(inv_date + timedelta(days=7)),
            "paid_at":         paid_at,
            "created":         iso(inv_date),
            "billing_reason":  "subscription_cycle",
        })

        # payment per invoice
        pay_status = "succeeded" if inv_status == "paid" else "failed"
        failure_codes = ["card_declined", "insufficient_funds", "expired_card"]
        stripe_pay.append({
            "id":           uid("ch_"),
            "invoice_id":   inv_id,
            "customer_id":  stripe_cust_id,
            "amount":       mrr,
            "currency":     "usd",
            "status":       pay_status,
            "failure_code": random.choice(failure_codes) if pay_status == "failed" else None,
            "created":      iso(inv_date + timedelta(hours=random.randint(0, 2))),
        })

    # ── Internal workspace ──
    converted_at = created_at + timedelta(days=random.randint(7, 21)) \
                   if segment != "pql" else None
    int_workspaces.append({
        "id":                 ws_id,
        "name":               f"{name} Workspace",
        "plan":               plan,
        "seat_limit":         seat_limit,
        "created_at":         iso(created_at),
        "trial_started_at":   iso(created_at),
        "trial_ended_at":     iso(created_at + timedelta(days=14)) if segment != "pql" else None,
        "converted_at":       iso(converted_at) if converted_at else None,
        "owner_user_id":      None,  # filled below
        "stripe_customer_id": stripe_cust_id,
        "hubspot_company_id": hs_company_id,
    })

    # ── Internal users ──
    ws_users = []
    n_users = seats_used
    for u in range(n_users):
        user_id = uid("usr_")
        if u == 0:
            role = "owner"
            int_workspaces[-1]["owner_user_id"] = user_id
        elif u == 1:
            role = "admin"
        elif u < 4:
            role = "member"
        else:
            role = random.choice(["member", "viewer"])

        if segment == "at_risk":
            last_seen = rand_date(NOW - timedelta(days=60), NOW - timedelta(days=30))
        elif segment == "pql":
            last_seen = rand_date(NOW - timedelta(days=7), NOW)
        else:
            last_seen = rand_date(NOW - timedelta(days=14), NOW)

        activated = created_at + timedelta(days=random.randint(1, 5))
        
        # FIX: Real-world noise. Not all users match HubSpot (identity resolution leakage)
        # 70% match probability for the first few users
        if u < len(company_contact_emails) and random.random() < 0.7:
            email = company_contact_emails[u]
        else:
            # Use random names or generic emails to simulate unmatched users
            email = f"user{u}@{domain}" if random.random() < 0.5 else f"{uid('u')}@gmail.com"

        ws_users.append(user_id)
        int_users.append({
            "id":           user_id,
            "workspace_id": ws_id,
            "email":        email,
            "role":         role,
            "invited_at":   iso(created_at),
            "activated_at": iso(activated),
            "last_seen_at": iso(last_seen),
            "created_at":   iso(created_at),
            "is_deleted":   False,
        })

    # ── Internal events ──
    # PQL must hit all 3 activation events
    if segment == "pql":
        for ae in ACTIVATION_EVENTS:
            int_events.append({
                "id":           uid("evt_"),
                "workspace_id": ws_id,
                "user_id":      random.choice(ws_users),
                "event_name":   ae,
                "properties":   {},
                "occurred_at":  iso(rand_date(NOW - timedelta(days=14), NOW - timedelta(days=3))),
            })

    # at_risk: very few events, old timestamps
    if segment == "at_risk":
        n_events = random.randint(5, 20)
        event_window_end = NOW - timedelta(days=45)
    elif segment == "expansion":
        n_events = random.randint(200, 500)
        event_window_end = NOW
    elif segment == "pql":
        n_events = random.randint(30, 80)
        event_window_end = NOW
    else:
        n_events = random.randint(50, 200)
        event_window_end = NOW

    for _ in range(n_events):
        int_events.append({
            "id":           uid("evt_"),
            "workspace_id": ws_id,
            "user_id":      random.choice(ws_users),
            "event_name":   random.choice(EVENTS),
            "properties":   {},
            "occurred_at":  iso(rand_date(SIX_M, event_window_end)),
        })

    # ── Zendesk tickets ──
    if segment == "at_risk":
        n_tickets = random.randint(5, 12)
        priorities = ["high", "urgent"]
    elif segment == "expansion":
        n_tickets = random.randint(1, 4)
        priorities = ["normal", "low"]
    elif segment == "pql":
        n_tickets = random.randint(0, 2)
        priorities = ["normal"]
    else:
        n_tickets = random.randint(0, 5)
        priorities = ["low", "normal", "high"]

    for _ in range(n_tickets):
        created_t = rand_date(SIX_M, NOW)
        priority = random.choice(priorities)
        is_solved = random.random() < 0.6
        tags = random.choice(TICKET_TAGS[segment])
        solved_at = rand_date(created_t, NOW) if is_solved else None
        first_reply_hours = random.uniform(1, 72) if segment == "at_risk" else random.uniform(0.5, 8)

        zd_tickets.append({
            "id":                str(random.randint(10000, 99999)),
            "subject":           f"Issue with {random.choice(['billing', 'integration', 'performance', 'access', 'onboarding'])}",
            "status":            "solved" if is_solved else random.choice(["open", "pending"]),
            "priority":          priority,
            "requester_email":   f"user0@{domain}",
            "assignee_id":       str(random.randint(1, 5)),
            "created_at":        iso(created_t),
            "updated_at":        iso(rand_date(created_t, NOW)),
            "solved_at":         iso(solved_at) if solved_at else None,
            "first_reply_at":    iso(created_t + timedelta(hours=first_reply_hours)),
            "tags":              tags,
            "satisfaction_rating": random.choice(["good", "bad", None]) if is_solved else None,
        })

# ── write output ──────────────────────────────────────────────────────────────

out = Path("data/raw")
out.mkdir(parents=True, exist_ok=True)

files = {
    "hubspot_companies.json":    hs_companies,
    "hubspot_deals.json":        hs_deals,
    "hubspot_contacts.json":     hs_contacts,
    "hubspot_engagements.json":  hs_engagements,
    "stripe_subscriptions.json": stripe_subs,
    "stripe_invoices.json":      stripe_inv,
    "stripe_payments.json":      stripe_pay,
    "internal_workspaces.json":  int_workspaces,
    "internal_users.json":       int_users,
    "internal_events.json":      int_events,
    "zendesk_tickets.json":      zd_tickets,
}

for fname, data in files.items():
    path = out / fname
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✓ {fname:40s} {len(data):>5} records")

print(f"\n✅ Done. Files written to {out.resolve()}")

# ── summary ───────────────────────────────────────────────────────────────────
segments = [c[4] for c in COMPANIES]
print(f"\nSegment breakdown:")
for s in ["at_risk", "expansion", "pql", "healthy"]:
    print(f"  {s:12s}: {segments.count(s)} companies")