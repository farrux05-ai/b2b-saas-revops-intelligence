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
TWO_YEARS_AGO = NOW - timedelta(days=730)
YEAR_AGO = NOW - timedelta(days=365)
SIX_M = NOW - timedelta(days=180)
THREE_M = NOW - timedelta(days=90)

# ── company profiles ──────────────────────────────────────────────────────────

INDUSTRIES = [
    "Software", "FinTech", "HealthTech", "E-commerce",
    "Cybersecurity", "DevTools", "MarTech", "EdTech",
    "HRTech", "LegalTech", "PropTech", "InsurTech",
]

COMPANIES = [
    # (name, domain, industry, employee_count, segment)
    # segment: at_risk | expansion | pql | healthy

    # ── at_risk (16 companies) ────────────────────────────────────────────────
    ("Acme Corp",          "acme.com",          "Software",      120,  "at_risk"),
    ("Brightwave Labs",    "brightwave.io",     "FinTech",        85,  "at_risk"),
    ("Cascadia Systems",   "cascadiasys.com",   "HealthTech",    200,  "at_risk"),
    ("DeltaCore Inc",      "deltacore.com",     "E-commerce",     60,  "at_risk"),
    ("Evergreen Digital",  "evergreen.io",      "MarTech",        95,  "at_risk"),
    ("Forge Analytics",    "forgeanalytics.co", "DevTools",       75,  "at_risk"),
    ("GridSpark",          "gridspark.com",     "Software",      110,  "at_risk"),
    ("HorizonAI",          "horizonai.io",      "Software",      180,  "at_risk"),
    ("Inkwell Data",       "inkwelldata.com",   "MarTech",        45,  "at_risk"),
    ("JunctionSoft",       "junctionsoft.io",   "Software",       90,  "at_risk"),
    ("Kestrel Labs",       "kestrel.io",        "FinTech",       130,  "at_risk"),
    ("Lantern Systems",    "lanternsys.com",    "HealthTech",     70,  "at_risk"),
    ("Marble Cloud",       "marblecloud.io",    "E-commerce",    115,  "at_risk"),
    ("NorthStar Analytics","northstar.io",      "DevTools",       55,  "at_risk"),
    ("Outpost Tech",       "outposttech.com",   "Cybersecurity", 160,  "at_risk"),
    ("Pinecrest Software", "pinecrest.io",      "Software",       80,  "at_risk"),

    # ── expansion (10 companies) ──────────────────────────────────────────────
    ("IronMesh",           "ironmesh.com",      "Cybersecurity", 250,  "expansion"),
    ("JetStream Cloud",    "jetstream.cloud",   "Software",      320,  "expansion"),
    ("KineticHR",          "kineticher.com",    "FinTech",       140,  "expansion"),
    ("LatticeOps",         "latticeops.io",     "DevTools",      190,  "expansion"),
    ("Meridian Tech",      "meridiantech.com",  "Software",      410,  "expansion"),
    ("Quartzite Systems",  "quartzite.io",      "Cybersecurity", 380,  "expansion"),
    ("RidgeLine Cloud",    "ridgeline.cloud",   "Software",      295,  "expansion"),
    ("Stratosphere Dev",   "stratosphere.dev",  "DevTools",      225,  "expansion"),
    ("Titanfall Labs",     "titanfall.io",      "FinTech",       345,  "expansion"),
    ("UpperCut Analytics", "uppercut.io",       "MarTech",       175,  "expansion"),

    # ── pql (8 companies) ─────────────────────────────────────────────────────
    ("NovaBuild",          "novabuild.dev",     "DevTools",       22,  "pql"),
    ("OmniStack",          "omnistack.io",      "Software",       18,  "pql"),
    ("PeakFlow",           "peakflow.co",       "MarTech",        31,  "pql"),
    ("Rapidfire Dev",      "rapidfire.dev",     "Software",       14,  "pql"),
    ("ShiftBoard",         "shiftboard.io",     "HRTech",         27,  "pql"),
    ("TracerIO",           "tracerio.com",      "DevTools",       19,  "pql"),
    ("Umbra Analytics",    "umbra.io",          "Software",       35,  "pql"),
    ("Velo Systems",       "velosys.io",        "FinTech",        23,  "pql"),

    # ── healthy (86 companies) ────────────────────────────────────────────────
    ("Quantum Leap",       "quantumleap.ai",    "Software",      150,  "healthy"),
    ("RootSignal",         "rootsignal.com",    "Cybersecurity", 220,  "healthy"),
    ("SkyBridge",          "skybridge.io",      "FinTech",        90,  "healthy"),
    ("TerraScale",         "terrascale.com",    "E-commerce",    175,  "healthy"),
    ("Unified.io",         "unified.io",        "DevTools",      130,  "healthy"),
    ("VaultEdge",          "vaultedge.com",     "Cybersecurity", 300,  "healthy"),
    ("WavePath",           "wavepath.io",       "MarTech",        80,  "healthy"),
    ("XenonData",          "xenondata.com",     "Software",      160,  "healthy"),
    ("YieldBridge",        "yieldbridge.co",    "FinTech",       210,  "healthy"),
    ("ZenithOps",          "zenithops.io",      "DevTools",      240,  "healthy"),
    ("Arclight Systems",   "arclight.io",       "Software",      100,  "healthy"),
    ("BluePeak",           "bluepeak.com",      "HealthTech",    280,  "healthy"),
    ("Cobalt Labs",        "cobaltlabs.io",     "Software",       70,  "healthy"),
    ("DataForge",          "dataforge.com",     "DevTools",      190,  "healthy"),
    ("Embark Analytics",   "embark.io",         "MarTech",       120,  "healthy"),
    ("FluxPoint",          "fluxpoint.com",     "E-commerce",     55,  "healthy"),
    ("GlacierTech",        "glaciertech.io",    "Software",      145,  "healthy"),
    ("Helix Security",     "helixsec.com",      "Cybersecurity", 310,  "healthy"),
    ("Impulse AI",         "impulseai.io",      "Software",      230,  "healthy"),
    ("Juno Platforms",     "juno.io",           "FinTech",       160,  "healthy"),
    ("Kinetic Data",       "kineticdata.com",   "DevTools",       95,  "healthy"),
    ("Luminos Labs",       "luminos.io",        "Software",      185,  "healthy"),
    ("Moonsail Tech",      "moonsail.io",       "HealthTech",    125,  "healthy"),
    ("Nexwave",            "nexwave.com",       "Software",      270,  "healthy"),
    ("Orbital Systems",    "orbital.io",        "E-commerce",    200,  "healthy"),
    ("Prism Analytics",    "prism.io",          "MarTech",       140,  "healthy"),
    ("Quasar Dev",         "quasar.dev",        "DevTools",       65,  "healthy"),
    ("Radius Cloud",       "radiuscloud.io",    "Software",      310,  "healthy"),
    ("Solaris Labs",       "solaris.io",        "Cybersecurity", 175,  "healthy"),
    ("Tidal Systems",      "tidalsys.com",      "Software",      135,  "healthy"),
    ("Ultrawave",          "ultrawave.io",      "FinTech",       290,  "healthy"),
    ("Vantage IO",         "vantage.io",        "DevTools",      155,  "healthy"),
    ("WhiteLight Tech",    "whitelight.com",    "Software",       85,  "healthy"),
    ("Zephyr Analytics",   "zephyr.io",         "MarTech",       220,  "healthy"),
    ("Amber Systems",      "ambersys.io",       "HRTech",        105,  "healthy"),
    ("BridgeCode",         "bridgecode.io",     "Software",      175,  "healthy"),
    ("ClearPath Labs",     "clearpath.io",      "DevTools",      115,  "healthy"),
    ("Dawnrise Tech",      "dawnrise.tech",     "EdTech",        135,  "healthy"),
    ("EdgeForm",           "edgeform.io",       "Software",       95,  "healthy"),
    ("FalconOps",          "falconops.com",     "Cybersecurity", 260,  "healthy"),
    ("Granite Analytics",  "graniteanalytics.io","MarTech",      145,  "healthy"),
    ("Harborlight",        "harborlight.com",   "FinTech",       195,  "healthy"),
    ("Inertia Labs",       "inertialabs.io",    "Software",       85,  "healthy"),
    ("Jasper Cloud",       "jaspercloud.io",    "E-commerce",    170,  "healthy"),
    ("Keyframe Dev",       "keyframe.dev",      "DevTools",       75,  "healthy"),
    ("Lodestar AI",        "lodestar.ai",       "Software",      215,  "healthy"),
    ("Mosaic Data",        "mosaicdata.io",     "MarTech",       130,  "healthy"),
    ("Nautilus Systems",   "nautilussys.com",   "Software",      245,  "healthy"),
    ("Obsidian Cloud",     "obsidian.cloud",    "Cybersecurity", 185,  "healthy"),
    ("Parallax Labs",      "parallax.io",       "DevTools",      110,  "healthy"),
    ("Quorum Analytics",   "quorum.io",         "FinTech",       230,  "healthy"),
    ("Raven Systems",      "ravensys.com",      "Software",      155,  "healthy"),
    ("SandBar Tech",       "sandbar.tech",      "E-commerce",     60,  "healthy"),
    ("Topaz Cloud",        "topaz.cloud",       "Software",      280,  "healthy"),
    ("UrbanStack",         "urbanstack.io",     "PropTech",      120,  "healthy"),
    ("Vertex Labs",        "vertexlabs.io",     "Software",      195,  "healthy"),
    ("Whetstone Data",     "whetstone.io",      "DevTools",      140,  "healthy"),
    ("Xeno Analytics",     "xenoanalytics.com", "MarTech",       165,  "healthy"),
    ("Yellowstone Dev",    "yellowstone.dev",   "Software",       90,  "healthy"),
    ("Zenon Systems",      "zenon.io",          "Cybersecurity", 210,  "healthy"),
    ("Apex Digital",       "apexdigital.io",    "MarTech",       125,  "healthy"),
    ("Basin Analytics",    "basinanalytics.com","FinTech",       155,  "healthy"),
    ("Crestline Labs",     "crestline.io",      "HealthTech",    175,  "healthy"),
    ("Driftwood Tech",     "driftwood.tech",    "Software",       95,  "healthy"),
    ("Ember Systems",      "embersys.io",       "DevTools",      145,  "healthy"),
    ("Fieldstone Data",    "fieldstone.io",     "E-commerce",    115,  "healthy"),
    ("Groundswell Labs",   "groundswell.io",    "Software",      200,  "healthy"),
    ("Hillside Analytics", "hillside.io",       "MarTech",       130,  "healthy"),
    ("Ironwood Cloud",     "ironwood.cloud",    "Cybersecurity", 255,  "healthy"),
    ("Junction Labs",      "junctionlabs.io",   "Software",      170,  "healthy"),
    ("Keystone Data",      "keystonedata.io",   "FinTech",       225,  "healthy"),
    ("Limestone Labs",     "limestone.io",      "DevTools",      100,  "healthy"),
    ("Millstone Tech",     "millstone.tech",    "Software",      185,  "healthy"),
    ("Nightfall Systems",  "nightfall.io",      "Cybersecurity", 270,  "healthy"),
    ("Oakwood Analytics",  "oakwood.io",        "MarTech",       150,  "healthy"),
    ("Pebblebrook Labs",   "pebblebrook.io",    "EdTech",        115,  "healthy"),
    ("Quarry Systems",     "quarrysys.com",     "Software",      195,  "healthy"),
    ("Ridgecrest Data",    "ridgecrest.io",     "FinTech",       165,  "healthy"),
    ("Stonewall Labs",     "stonewall.io",      "DevTools",       80,  "healthy"),
    ("Timberline Tech",    "timberline.tech",   "Software",      235,  "healthy"),
    ("Underhill Systems",  "underhill.io",      "HRTech",        140,  "healthy"),
    ("Valleyview Labs",    "valleyview.io",     "HealthTech",    195,  "healthy"),
    ("Westbrook Data",     "westbrook.io",      "Software",      155,  "healthy"),
    ("Xerxes Analytics",   "xerxes.io",         "MarTech",       175,  "healthy"),
    ("Yarrow Systems",     "yarrow.io",         "LegalTech",     120,  "healthy"),
    ("Zircon Labs",        "zircon.io",         "Software",      205,  "healthy"),
    ("Alluvial Data",      "alluvial.io",       "DevTools",      135,  "healthy"),
    ("Basalt Systems",     "basalt.io",         "Cybersecurity", 245,  "healthy"),
    ("Cairn Analytics",    "cairn.io",          "FinTech",       185,  "healthy"),
    ("Dolomite Labs",      "dolomite.io",       "Software",      110,  "healthy"),
    ("Esker Cloud",        "esker.cloud",       "E-commerce",    160,  "healthy"),
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
    "dashboard_viewed", "export_triggered", "api_key_created",
    "webhook_configured", "automation_rule_created", "bulk_import",
    "slack_integration_connected", "sso_enabled", "audit_log_viewed",
    "custom_field_created", "template_used", "roadmap_updated",
]

ACTIVATION_EVENTS = {"git_integration_connected", "project_created", "invite_sent"}

TICKET_TAGS = {
    "at_risk":   [
        ["billing", "churn-risk"], ["bug", "churn-risk"], ["onboarding"],
        ["billing", "escalated"], ["performance", "churn-risk"], ["access", "churn-risk"],
    ],
    "expansion": [
        ["feature-request"], ["onboarding"], ["api"], ["integration"], ["enterprise-feature"],
    ],
    "pql":       [
        ["onboarding"], ["bug"], ["trial-support"], ["setup-help"],
    ],
    "healthy":   [
        ["feature-request"], ["bug"], ["onboarding"],
        ["api"], ["integration"], ["performance"],
    ],
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

    created_at = rand_date(TWO_YEARS_AGO, SIX_M)

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
    utm_source = random.choice([
        "Organic Search", "Google Ads", "LinkedIn", "Direct", "Referral",
        "Product Hunt", "Newsletter", "Twitter", "Podcast", "Webinar",
    ])
    utm_campaign_map = {
        "Organic Search": random.choice(["SEO_2023", "SEO_2024_Q1", "Blog_DevTools"]),
        "Google Ads":     random.choice(["Q1_Competitor_Keywords", "Retargeting_V2", "Brand_Protection", "Q4_Enterprise"]),
        "LinkedIn":       random.choice(["B2B_SaaS_Leaders", "DevOps_Personas", "Enterprise_IT"]),
        "Product Hunt":   random.choice(["PH_Launch_2023", "PH_Featured_2024"]),
        "Newsletter":     random.choice(["Weekly_Digest", "State_of_DevOps"]),
        "Twitter":        random.choice(["Dev_Awareness", "OSS_Community"]),
        "Podcast":        random.choice(["Software_Eng_Podcast", "SaaStr_Sponsorship"]),
        "Webinar":        random.choice(["Q1_Webinar_CI_CD", "Enterprise_Demo_Day"]),
    }
    utm_campaign = utm_campaign_map.get(utm_source, "None")

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

    # ── HubSpot contacts (2-5 per company) ──
    company_contact_emails = []
    roles = [
        "CTO", "VP Engineering", "Engineering Manager", "Lead Developer", "DevOps Lead",
        "VP Product", "Head of IT", "Platform Engineer", "Software Architect",
        "Director of Engineering", "CEO", "COO", "VP Operations",
    ]
    first_names = [
        "Alex","Jordan","Taylor","Morgan","Casey","Riley","Drew","Quinn",
        "Blake","Cameron","Avery","Logan","Reese","Skyler","Peyton","Rowan",
        "Dana","Jesse","Finley","Kendall","Parker","Sage","Spencer","Tatum",
    ]
    last_names = [
        "Smith","Johnson","Lee","Brown","Davis","Wilson","Moore","Clark",
        "Anderson","Martinez","Garcia","Rodriguez","Harris","Jackson","Thompson",
        "White","Lewis","Walker","Hall","Allen","Young","Hernandez","King","Wright",
    ]
    for _ in range(random.randint(2, 5)):
        fname = random.choice(first_names)
        lname = random.choice(last_names)
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
    n_engagements = random.randint(8, 30) if segment != "pql" else random.randint(0, 3)
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

    # ── Stripe invoices (up to 24 months) ──
    for m in range(24):
        inv_date = sub_start + timedelta(days=30 * m)
        if inv_date > NOW:
            break
        mrr = price_cents * seats_used
        if segment == "at_risk" and m >= 18:
            inv_status = random.choice(["open", "uncollectible", "void"])
            paid_at = None
        elif segment == "at_risk" and m >= 12:
            inv_status = random.choices(["paid", "open", "uncollectible"], weights=[4, 3, 3])[0]
            paid_at = iso(inv_date + timedelta(days=random.randint(0, 3))) if inv_status == "paid" else None
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
        n_events = random.randint(10, 40)
        event_window_end = NOW - timedelta(days=30)
    elif segment == "expansion":
        n_events = random.randint(400, 900)
        event_window_end = NOW
    elif segment == "pql":
        n_events = random.randint(50, 120)
        event_window_end = NOW
    else:
        n_events = random.randint(100, 400)
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
        n_tickets = random.randint(8, 20)
        priorities = ["high", "urgent"]
    elif segment == "expansion":
        n_tickets = random.randint(2, 8)
        priorities = ["normal", "low"]
    elif segment == "pql":
        n_tickets = random.randint(1, 4)
        priorities = ["normal", "low"]
    else:
        n_tickets = random.randint(1, 10)
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
    count = segments.count(s)
    print(f"  {s:12s}: {count:3d} companies")

print(f"\nTotal companies: {len(COMPANIES)}")