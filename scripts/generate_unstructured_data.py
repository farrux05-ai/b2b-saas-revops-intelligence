"""
StackFlow RevOps — Unstructured Data Generator
===============================================

Generates 3 types of realistic unstructured text data for Vector Engine ingestion:

  1. hubspot_sales_notes.json
     ↳ Source: HubSpot CRM → Engagement Notes (API: POST /engagements/v1/engagements)
     ↳ Format: JSON array, each record has {id, engagement_type, body (raw HTML/text), metadata}
     ↳ Real tool: HubSpot Engagements API — notes are stored as plain text or HTML in body field

  2. zendesk_ticket_comments.json
     ↳ Source: Zendesk Support → Ticket Comments (API: GET /api/v2/tickets/{id}/comments)
     ↳ Format: JSON array of comment threads, each with {ticket_id, comments: [{author, body, ...}]}
     ↳ Real tool: Zendesk REST API — conversations are threaded comment arrays per ticket

  3. gong_call_transcripts.json
     ↳ Source: Gong Revenue Intelligence → Call Transcripts (API: POST /v2/calls/transcript)
     ↳ Format: JSON array, each call has {call_id, parties, transcript: [{speaker, start_time, sentences}]}
     ↳ Real tool: Gong API — transcripts are segmented by speaker with timestamps

All records are cross-referenced to existing company IDs from generate_mock_data.py output.
Run generate_mock_data.py first, then this script.

Output: data/raw/unstructured/
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

random.seed(99)  # reproducible but different from structured data seed

# ── load existing structured data for cross-referencing ──────────────────────

RAW_DIR = Path("data/raw")
UNSTRUCTURED_DIR = RAW_DIR / "unstructured"
UNSTRUCTURED_DIR.mkdir(parents=True, exist_ok=True)

def load_json(fname):
    p = RAW_DIR / fname
    if not p.exists():
        raise FileNotFoundError(f"Run generate_mock_data.py first! Missing: {p}")
    with open(p) as f:
        return json.load(f)

companies    = load_json("hubspot_companies.json")
contacts     = load_json("hubspot_contacts.json")
deals        = load_json("hubspot_deals.json")
engagements  = load_json("hubspot_engagements.json")
zd_tickets   = load_json("zendesk_tickets.json")

# ── helpers ──────────────────────────────────────────────────────────────────

def uid(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:12]}"

def rand_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, max(1, int(delta.total_seconds()))))

def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

NOW      = datetime(2024, 6, 1)
YEAR_AGO = NOW - timedelta(days=365)
SIX_M    = NOW - timedelta(days=180)

# build lookup: company_id -> company info
company_map = {c["hs_object_id"]: c for c in companies}

# build lookup: company_id -> contacts
contacts_by_company = {}
for ct in contacts:
    cid = ct.get("associated_company_id")
    if cid:
        contacts_by_company.setdefault(cid, []).append(ct)

# build lookup: company_id -> deals
deals_by_company = {}
for d in deals:
    cid = d.get("associated_company_id")
    if cid:
        deals_by_company.setdefault(cid, []).append(d)

# ── SALES REPS (internal personas) ───────────────────────────────────────────
SALES_REPS = [
    {"id": "1", "name": "Sarah Mitchell",   "email": "s.mitchell@stackflow.io",  "title": "Account Executive"},
    {"id": "2", "name": "James Okafor",     "email": "j.okafor@stackflow.io",    "title": "Account Executive"},
    {"id": "3", "name": "Emily Zhao",       "email": "e.zhao@stackflow.io",      "title": "Senior AE"},
    {"id": "4", "name": "Carlos Hernandez", "email": "c.hernandez@stackflow.io", "title": "Account Executive"},
    {"id": "5", "name": "Priya Nair",       "email": "p.nair@stackflow.io",      "title": "Enterprise AE"},
    {"id": "6", "name": "Tom Bergstrom",    "email": "t.bergstrom@stackflow.io", "title": "SDR"},
    {"id": "7", "name": "Lisa Fontaine",    "email": "l.fontaine@stackflow.io",  "title": "Customer Success Manager"},
    {"id": "8", "name": "Kevin Park",       "email": "k.park@stackflow.io",      "title": "CSM"},
]
SUPPORT_AGENTS = [
    {"id": "1", "name": "Ana Rodriguez",   "email": "support+ana@stackflow.io"},
    {"id": "2", "name": "Mike Thompson",   "email": "support+mike@stackflow.io"},
    {"id": "3", "name": "Yuki Tanaka",     "email": "support+yuki@stackflow.io"},
    {"id": "4", "name": "Omar Hassan",     "email": "support+omar@stackflow.io"},
    {"id": "5", "name": "Sophie Laurent",  "email": "support+sophie@stackflow.io"},
]

# ══════════════════════════════════════════════════════════════════════════════
# 1. HUBSPOT SALES NOTES
# ══════════════════════════════════════════════════════════════════════════════
# Real format: HubSpot Engagements API v1
# POST /engagements/v1/engagements
# {
#   "engagement": {"type": "NOTE", "timestamp": 1234567890000, "ownerId": 123},
#   "associations": {"companyIds": [100000]},
#   "metadata": {"body": "<p>Call notes here...</p>"}
# }
# We store the flattened version that arrives after ingestion via Fivetran/dlt.

NOTE_TEMPLATES_AT_RISK = [
    (
        "Churn Risk — {contact} not responding",
        "Called {contact} ({title}) at {company} — went to voicemail again. "
        "This is the 3rd unanswered attempt this week. Last login was 47 days ago per product data. "
        "Invoice #{inv_id} has been past due for {days} days. "
        "Escalating to CSM team. Need to loop in {csm} for an emergency check-in. "
        "If no response by EOW, flagging for churn review committee."
    ),
    (
        "Follow-up: billing dispute unresolved",
        "Spoke with {contact} ({title}) at {company} for 8 mins. "
        "They're frustrated with the auto-renewal charge — said nobody approved it internally. "
        "Billing team needs to pull invoice {inv_id}. "
        "They mentioned their CFO is reviewing all SaaS subscriptions this quarter. "
        "Risk: high. They have 2 competitors shortlisted (Notion + Linear). "
        "Action: send ROI doc by tomorrow, schedule exec call for next week."
    ),
    (
        "Discovery call — re-engagement attempt",
        "Got {contact} on a quick 15-min call. Tone was cold but not hostile. "
        "Key blocker: their eng team is understaffed and hasn't had bandwidth to adopt the platform. "
        "They have {seats} seats but only ~{active_seats} DAU. "
        "Proposed a dedicated onboarding session with their lead dev. "
        "They said they'd 'think about it'. Sending a Loom walkthrough of the new AI features. "
        "Next step: follow-up in 5 days if no reply."
    ),
    (
        "Executive check-in prep notes",
        "Internal prep for EBC with {company} next Thursday. "
        "Key stakeholders: {contact} (champion), and their new VP of Eng (unknown — need to find on LinkedIn). "
        "Pain points from last 3 tickets: slow API response times, confusion on permission roles, billing transparency. "
        "Competitor intel: they trialed Jira for 30 days, reverted. Linear is still on their radar. "
        "Must show: roadmap slide for Q3, new analytics dashboard, SOC2 cert status."
    ),
    (
        "At-risk account: internal handoff note",
        "Handing {company} to {csm} (CSM) for rescue play. "
        "Background: Closed {deal_amount} deal in {close_date}. "
        "Since then: 4 support tickets (2 billing, 2 bugs), seat utilization dropped to {util}%. "
        "Last sales touch: {days} days ago. "
        "Recommended play: product-led outreach via in-app message + direct email from CEO to {contact}."
    ),
]

NOTE_TEMPLATES_EXPANSION = [
    (
        "Upsell opportunity identified — seat limit approaching",
        "Checked usage dashboard before the call with {contact} ({title}) at {company}. "
        "They're at {seats_used}/{seat_limit} seats — {pct}% utilization! "
        "On the call, {contact} mentioned they have 3 new hires starting next month. "
        "Pitched the Enterprise plan ({enterprise_price}/mo) — they were receptive. "
        "Sent pricing PDF. Decision timeline: 2 weeks. "
        "Deal in pipeline: {deal_amount} expansion potential. Champion: strong."
    ),
    (
        "QBR notes — expansion discussion",
        "45-min QBR with {contact} and their VP. Very positive. "
        "They cited {company}'s team velocity improvement since adopting StackFlow. "
        "Metrics they shared: 30% fewer missed sprint deadlines, 2x faster code review cycles. "
        "Discussed upgrading from Growth to Enterprise for: SSO, audit logs, dedicated CSM. "
        "They want a custom SLA. Looping in Solutions Engineering for a scoping call."
    ),
    (
        "Referral potential + expansion",
        "Call with {contact} at {company} — went great. "
        "They're happy customers and mentioned 2 portfolio companies (VC-backed) who might be interested: "
        "one is a fintech in Series B, another is a dev tools startup. "
        "Asked {contact} for warm intro. They agreed. "
        "Also confirmed they want to add a second workspace for their new product team. "
        "Action: draft referral email template + send expansion proposal."
    ),
]

NOTE_TEMPLATES_PQL = [
    (
        "PQL triggered — reached out",
        "System alert: {company} hit PQL threshold. "
        "They've connected GitHub, created 3 projects, and invited 4 team members in the last 7 days. "
        "Sent personalized outreach to {contact} ({title}). "
        "Referenced their tech stack (they're a {industry} startup, ~{emp} employees). "
        "Offered a 30-min product walkthrough + Q&A. Waiting on reply."
    ),
    (
        "Trial check-in call — high engagement",
        "Quick 20-min call with {contact} from {company}. "
        "They signed up {days} days ago and love the AI sprint prioritization. "
        "Pain they're solving: their previous tool (Asana) had no dev-native integrations. "
        "Key question they asked: 'Does Enterprise have API rate limit increases?' → YES, confirmed. "
        "Trial ends in {trial_days} days. Likely to convert. "
        "Proposal: Growth plan at $2,500/mo for 15 seats."
    ),
]

NOTE_TEMPLATES_HEALTHY = [
    (
        "Annual renewal discussion",
        "Called {contact} at {company} to start renewal conversation early (90 days out). "
        "They're happy but want to renegotiate pricing — their CFO is pushing for a 10% discount. "
        "Current ARR: {deal_amount}. "
        "Willing to offer 5% discount in exchange for 2-year commit. "
        "They'll discuss internally and come back by end of month."
    ),
    (
        "Check-in call — healthy account",
        "30-min call with {contact} ({title}) — no major issues. "
        "They asked about the roadmap for {company}'s use case ({industry}). "
        "Highlighted upcoming: advanced analytics, Slack integration v2, and mobile app. "
        "They're presenting StackFlow internally for budget review in Q3. "
        "Sent case study from a similar {industry} company. All good."
    ),
    (
        "Multi-threaded: new stakeholder intro",
        "Introduced via email to {contact2} at {company} — they're the new Head of Platform Eng. "
        "Set up a 30-min discovery call for next week. "
        "Original champion {contact} is moving to a new role internally — need to rebuild relationship. "
        "Stakeholder map updated in CRM. Added {contact2} as secondary contact."
    ),
]

def pick_note_template(segment):
    if segment == "at_risk":
        return random.choice(NOTE_TEMPLATES_AT_RISK)
    elif segment == "expansion":
        return random.choice(NOTE_TEMPLATES_EXPANSION)
    elif segment == "pql":
        return random.choice(NOTE_TEMPLATES_PQL)
    else:
        return random.choice(NOTE_TEMPLATES_HEALTHY)


def generate_sales_notes():
    notes = []
    for company in companies:
        cid        = company["hs_object_id"]
        segment    = _infer_segment(company)
        domain     = company["domain"]
        cname      = company["name"]
        industry   = company["industry"]
        emp_count  = company["employee_count"]

        # Get related data
        company_contacts = contacts_by_company.get(cid, [])
        company_deals    = deals_by_company.get(cid, [])
        rep              = SALES_REPS[int(company.get("hubspot_owner_id", "1")) - 1]
        csm              = random.choice([r for r in SALES_REPS if "CSM" in r["title"]])

        # Number of notes per segment
        if segment == "at_risk":
            n_notes = random.randint(3, 7)
        elif segment == "expansion":
            n_notes = random.randint(2, 5)
        elif segment == "pql":
            n_notes = random.randint(1, 3)
        else:
            n_notes = random.randint(1, 4)

        contact    = random.choice(company_contacts) if company_contacts else {"firstname": "The team", "jobtitle": "Contact", "email": f"contact@{domain}"}
        contact2   = random.choice(company_contacts) if len(company_contacts) > 1 else contact
        deal       = company_deals[0] if company_deals else {"amount": 0, "closedate": "2024-01-01T00:00:00Z"}

        close_date_str = deal.get("closedate", "2024-01-01T00:00:00Z")
        close_date_fmt = close_date_str[:10]

        for _ in range(n_notes):
            title_tpl, body_tpl = pick_note_template(segment)

            # Fill template placeholders
            contact_name  = f"{contact.get('firstname','User')} {contact.get('lastname','')}"
            contact2_name = f"{contact2.get('firstname','User')} {contact2.get('lastname','')}"
            seats         = random.randint(30, 45)
            seat_limit    = 50
            active_seats  = random.randint(5, 20)

            body = body_tpl.format(
                contact       = contact_name.strip(),
                contact2      = contact2_name.strip(),
                title         = contact.get("jobtitle", "Manager"),
                company       = cname,
                industry      = industry,
                emp           = emp_count,
                inv_id        = uid("INV-"),
                days          = random.randint(15, 60),
                trial_days    = random.randint(3, 12),
                csm           = csm["name"],
                seats         = seats,
                seats_used    = seats,
                seat_limit    = seat_limit,
                active_seats  = active_seats,
                pct           = round(seats / seat_limit * 100),
                enterprise_price = "6,000",
                deal_amount   = f"${deal['amount']:,.0f}",
                close_date    = close_date_fmt,
                util          = random.randint(15, 40),
            )

            note_ts = rand_date(SIX_M, NOW)

            # HubSpot Engagements API flattened format (as stored after Fivetran/dlt ingestion)
            notes.append({
                # HubSpot native fields
                "hs_engagement_id":       uid("eng_note_"),
                "engagement_type":        "NOTE",
                "associated_company_id":  cid,
                "associated_company_name": cname,
                "associated_contact_email": contact.get("email", ""),
                "owner_id":               rep["id"],
                "owner_name":             rep["name"],
                "owner_email":            rep["email"],
                # Core unstructured field — this goes into vector index
                "body":                   body,
                "body_preview":           body[:120] + "...",
                # Metadata for filtering / hybrid search
                "note_title":             title_tpl.replace("{contact}", contact_name.strip())
                                                    .replace("{company}", cname),
                "segment":                segment,
                "tags":                   _note_tags(segment),
                "deal_id":                deal.get("hs_object_id", None),
                "deal_amount":            deal.get("amount", 0),
                "sentiment":              _note_sentiment(segment),
                # Timestamps
                "created_at":             iso(note_ts),
                "last_modified":          iso(note_ts + timedelta(minutes=random.randint(0, 30))),
                # Ingestion metadata
                "_source":                "hubspot_engagements_api",
                "_api_version":           "v1",
            })

    return notes


# ══════════════════════════════════════════════════════════════════════════════
# 2. ZENDESK TICKET COMMENTS (Support Conversations)
# ══════════════════════════════════════════════════════════════════════════════
# Real format: Zendesk REST API
# GET /api/v2/tickets/{id}/comments
# Response: { "comments": [ { "id": 123, "author_id": 456, "body": "...", "public": true, ... } ] }
# After ingestion, we store per-ticket comment thread as a document.

SUPPORT_CONV_TEMPLATES = {
    "billing": [
        ("Customer",  "Hi, I'm seeing a charge of ${amount} on my credit card from StackFlow but I don't recognize it. Can you help?"),
        ("Agent",     "Hi {name}! Thanks for reaching out. I can see invoice #{inv_id} for ${amount} was generated on {date} for your {plan} subscription ({seats} seats × ${unit_price}/month). Does that match your records?"),
        ("Customer",  "Hmm, we did upgrade seats last month but I thought the price was going to be prorated. The charge seems higher than expected."),
        ("Agent",     "Totally understand! Let me pull up the proration details. The upgrade happened mid-cycle on {prorate_date}, so the charge covers {seats_added} additional seats for {days_remaining} days at the daily rate of ${daily_rate}. I'll send a detailed breakdown to your billing email."),
        ("Customer",  "OK that makes sense now. Can you also send it to our CFO? Her email is cfo@{domain}. Also, can we get a PDF invoice for accounting?"),
        ("Agent",     "Absolutely! I've updated the billing contacts and a PDF invoice is on its way. Is there anything else I can help you with?"),
        ("Customer",  "That's all. Thank you!"),
        ("Agent",     "Happy to help! I'm marking this ticket as resolved. Don't hesitate to reach back out. 😊"),
    ],
    "billing_dispute": [
        ("Customer",  "We've been double-charged this month. Two invoices for the same amount. This is unacceptable."),
        ("Agent",     "Hi {name}, I'm so sorry for the inconvenience. I can see 2 invoices: #{inv_id} and #{inv_id2}. One is from your previous billing cycle and the other is the current cycle. They're not duplicates, but I completely understand the confusion — the dates are very close. I'll add a note to your account."),
        ("Customer",  "Our finance team says they are both for the same period. I need this escalated."),
        ("Agent",     "Of course! I'm escalating this to our Billing Specialist team. You'll hear back within 4 business hours. Case #{case_id} has been created. I apologize for the experience."),
        ("Customer",  "Fine. Please make it quick."),
        ("Agent",     "Understood. I've marked this as urgent. Our billing team will reach out directly to {name}@{domain}. Thank you for your patience."),
    ],
    "integration": [
        ("Customer",  "Our GitHub integration stopped syncing commits since yesterday. We're not seeing any activity in StackFlow."),
        ("Agent",     "Hi {name}! Oh no, let's get this sorted. Can you confirm: (1) which GitHub org is connected? (2) Are you seeing any error messages in Settings > Integrations?"),
        ("Customer",  "The org is {company_slug}. No error messages, it just shows 'Last synced: 2 days ago' and nothing updates."),
        ("Agent",     "Got it. This is a known intermittent issue with GitHub webhooks when the app token expires. Can you go to Settings > Integrations > GitHub > Reconnect and use the OAuth flow? This usually resolves it instantly."),
        ("Customer",  "That worked! Commits are syncing now. Why did the token expire though?"),
        ("Agent",     "GitHub rotates OAuth tokens every 8 hours as a security measure. We're shipping a fix in v2.3.1 (ETA: next week) that will auto-refresh tokens silently. I've added you to the notify list for that release."),
        ("Customer",  "Great, thanks for the fast response!"),
        ("Agent",     "Anytime! Marking as solved. Feel free to reopen if it happens again."),
    ],
    "performance": [
        ("Customer",  "The platform has been very slow for the last 3 days. Page loads take 8-10 seconds. Our team is frustrated."),
        ("Agent",     "Hi {name}, I sincerely apologize for this. Can you share: (1) approximate time when it's slowest, (2) which specific pages/features, (3) your browser and OS?"),
        ("Customer",  "It's worst between 9am-12pm EST. Mainly the Sprint Board and Analytics pages. Chrome on Mac."),
        ("Agent",     "Thank you. We're aware of elevated latency on Sprint Board for workspaces with >50 active sprints. Our engineering team deployed a fix 2 hours ago. Can you do a hard refresh (Cmd+Shift+R) and let me know if it's improved?"),
        ("Customer",  "Still slow. Hard refresh didn't help."),
        ("Agent",     "I'm adding your workspace ID to our monitoring queue. Our on-call engineer will investigate your specific workspace config. I'll update you within 2 hours. Again, I'm very sorry for the disruption."),
        ("Customer",  "OK. We have a sprint planning session at 2pm so please prioritize."),
        ("Agent",     "Escalated to P1. Our engineering lead has been looped in directly. I'll update this ticket before your 2pm session."),
        ("Customer",  "Seems faster now. Whatever you did helped."),
        ("Agent",     "Glad to hear it! The fix was a query optimization on the sprint aggregation logic. Marking resolved. Please reach out if it recurs."),
    ],
    "access": [
        ("Customer",  "One of our admins accidentally removed a team member and now they can't log in. The user is {user_email}."),
        ("Agent",     "Hi {name}! No worries, I can help. For security, I'll need to verify you're an admin on this workspace. Can you confirm the last 4 digits of the card on file?"),
        ("Customer",  "It's {card_digits}."),
        ("Agent",     "Verified! I've re-invited {user_email} to your workspace. They should receive an email in the next 2 minutes. Note: as a security best practice, only workspace owners can permanently delete members."),
        ("Customer",  "Got it. The invite landed. Thanks!"),
        ("Agent",     "Great! Marking as solved. Have a good one!"),
    ],
    "onboarding": [
        ("Customer",  "We just signed up and I'm not sure how to get started. The onboarding checklist mentions 'connecting an integration' but I don't see where to do that."),
        ("Agent",     "Welcome to StackFlow, {name}! 🎉 So excited to have {company} on board. The integrations page is at: Settings → Workspace → Integrations. You'll see GitHub, Jira, Slack, and more. Which one would you like to connect first?"),
        ("Customer",  "We use GitHub and Slack mainly."),
        ("Agent",     "Perfect combo! Here's a quick start: 1) Connect GitHub first (it auto-imports your repos), 2) then Slack (for sprint notifications). I've also sent you our 'First Week with StackFlow' guide to your email. Any questions just reply here!"),
        ("Customer",  "Amazing, this is so helpful. One more thing — can we import our existing Jira board?"),
        ("Agent",     "Yes! We have a Jira importer under Settings → Import → Jira. It migrates epics, stories, and sprints. It takes ~10 mins for large boards. Here's the doc: [link]. Want me to schedule a 15-min onboarding call with our CS team?"),
        ("Customer",  "That would be great! Please."),
        ("Agent",     "Done! Check your email for a Calendly link from our CS team. You'll be up and running in no time! Marking this as solved but feel free to write back anytime."),
    ],
    "churn_risk": [
        ("Customer",  "We're evaluating whether to continue with StackFlow. We've had too many issues and my team is frustrated."),
        ("Agent",     "Hi {name}, I'm really sorry to hear that. Your experience matters a lot to us. Can you share the specific issues so I can make sure they're addressed? I'm also going to loop in your CSM, {csm_name}, who can set up a dedicated call to work through everything."),
        ("Customer",  "We've had 3 billing issues, the GitHub sync broke twice, and the sprint board is still slow. We have a board meeting next month and need to justify this cost."),
        ("Agent",     "I completely understand. I'm pulling up your full ticket history now. I can see those 3 billing tickets — 2 have been resolved and 1 is in progress. For the sync issues, we released a permanent fix last week. For sprint board performance: our engineering team has made significant improvements in the last 2 releases. I'd love for your team to give it another look. Can I have {csm_name} reach out directly with a personalized performance report for your workspace?"),
        ("Customer",  "Fine. But if we don't see improvement, we'll cancel at renewal."),
        ("Agent",     "I hear you. {csm_name} will reach out within 24 hours. I've marked your account as VIP priority and flagged the renewal timeline. We're committed to earning your trust back."),
    ],
}

def generate_zendesk_comments():
    """
    For each existing Zendesk ticket, generate a realistic comment thread.
    Output format mirrors Zendesk API GET /api/v2/tickets/{id}/comments response.
    """
    ticket_comments = []

    for ticket in zd_tickets:
        tid          = ticket["id"]
        subject      = ticket["subject"]
        req_email    = ticket["requester_email"]
        tags         = ticket.get("tags", [])
        priority     = ticket.get("priority", "normal")
        created_ts   = datetime.strptime(ticket["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        domain       = req_email.split("@")[-1] if "@" in req_email else "company.com"
        company_name = domain.replace(".com","").replace(".io","").replace(".co","").title()

        # Map ticket subject/tags to conversation type
        topic = "onboarding"
        for t in tags:
            if "billing"   in t: topic = random.choice(["billing", "billing_dispute"]); break
            if "churn"     in t: topic = "churn_risk"; break
            if "bug"       in t: topic = random.choice(["integration", "performance"]); break
            if "feature"   in t: topic = "access"; break
        if "integration" in subject: topic = "integration"
        elif "performance" in subject or "slow" in subject: topic = "performance"
        elif "access"    in subject: topic = "access"
        elif "onboarding" in subject: topic = "onboarding"
        elif "billing"   in subject: topic = random.choice(["billing", "billing_dispute"])

        agent         = SUPPORT_AGENTS[int(ticket["assignee_id"]) - 1]
        customer_name = req_email.split("@")[0].replace(".", " ").replace("user0", "the user").title()
        csm_name      = random.choice([r for r in SALES_REPS if "CSM" in r["title"]])["name"]

        template = SUPPORT_CONV_TEMPLATES.get(topic, SUPPORT_CONV_TEMPLATES["onboarding"])

        comments = []
        current_ts = created_ts
        comment_id_base = int(tid) * 1000

        for i, (speaker, text_tpl) in enumerate(template):
            current_ts = current_ts + timedelta(minutes=random.randint(3, 180))
            is_public  = True  # all public-facing in this dataset

            # Fill placeholders
            body = text_tpl.format(
                name           = customer_name,
                company        = company_name,
                company_slug   = company_name.lower().replace(" ", "-"),
                domain         = domain,
                amount         = random.randint(250, 6000),
                inv_id         = uid("INV-"),
                inv_id2        = uid("INV-"),
                plan           = random.choice(["Starter", "Growth", "Enterprise"]),
                seats          = random.randint(5, 100),
                seats_added    = random.randint(1, 20),
                unit_price     = random.choice([25, 50, 120]),
                daily_rate     = round(random.uniform(0.80, 4.0), 2),
                days_remaining = random.randint(5, 25),
                prorate_date   = (created_ts - timedelta(days=random.randint(5, 15))).strftime("%b %d"),
                date           = created_ts.strftime("%b %d, %Y"),
                case_id        = uid("CASE-"),
                user_email     = f"developer@{domain}",
                card_digits    = str(random.randint(1000, 9999)),
                csm_name       = csm_name,
            )

            if speaker == "Agent":
                author_id    = int(agent["id"])
                author_name  = agent["name"]
                author_email = agent["email"]
                author_type  = "agent"
            else:
                author_id    = int(tid) + 90000
                author_name  = customer_name
                author_email = req_email
                author_type  = "end_user"

            comments.append({
                "id":           comment_id_base + i,
                "type":         "Comment",
                "author_id":    author_id,
                "author_name":  author_name,
                "author_email": author_email,
                "author_type":  author_type,
                "body":         body,
                "html_body":    f"<p>{body}</p>",
                "public":       is_public,
                "created_at":   iso(current_ts),
                "attachments":  [],
            })

        # Full conversation document — this is the unit ingested into vector store
        full_conversation_text = "\n\n".join(
            f"[{c['author_type'].upper()} — {c['author_name']}]: {c['body']}"
            for c in comments
        )

        ticket_comments.append({
            # Zendesk ticket metadata (for filtering)
            "ticket_id":          tid,
            "subject":            subject,
            "status":             ticket["status"],
            "priority":           priority,
            "topic":              topic,
            "tags":               tags,
            "requester_email":    req_email,
            "requester_domain":   domain,
            "assignee_id":        ticket["assignee_id"],
            "assignee_name":      agent["name"],
            "created_at":         ticket["created_at"],
            "updated_at":         ticket.get("updated_at"),
            "solved_at":          ticket.get("solved_at"),
            "satisfaction_rating": ticket.get("satisfaction_rating"),
            # Comment thread
            "comment_count":      len(comments),
            "comments":           comments,
            # Denormalized full text for vector embedding
            "full_conversation":  full_conversation_text,
            # Ingestion metadata
            "_source":            "zendesk_api_v2",
            "_endpoint":          f"/api/v2/tickets/{tid}/comments",
        })

    return ticket_comments


# ══════════════════════════════════════════════════════════════════════════════
# 3. GONG CALL TRANSCRIPTS
# ══════════════════════════════════════════════════════════════════════════════
# Real format: Gong API v2
# POST /v2/calls/transcript (body: {filter: {callIds: [...]}})
# Response: {
#   "callTranscripts": [{
#     "callId": "...",
#     "transcript": [{"speakerId": "...", "topic": "...", "sentences": [{"start": 0, "end": 5.2, "text": "..."}]}]
#   }]
# }
# We generate realistic multi-party call transcripts with speaker diarization.

CALL_TOPICS = {
    "discovery": [
        ("rep",      "Thanks for making time today. I'll keep us to 30 minutes. So, tell me a bit about what brought you to StackFlow — what problems are you trying to solve?"),
        ("prospect", "Sure. We're a team of about {emp} engineers and our biggest pain point is sprint visibility. Our PMs can't see what engineers are working on in real time, so there's a lot of slack messages and status meetings that eat up hours."),
        ("rep",      "That's a really common pattern we hear from {industry} teams. The context-switching cost alone is massive. How are you managing it today — Jira? Linear?"),
        ("prospect", "We use Jira but it's just a dumping ground at this point. Nobody updates tickets. The engineers hate it."),
        ("rep",      "Yeah, the manual update problem. StackFlow auto-updates task status based on git commits and PR states — so engineers don't have to touch Jira at all. Would that solve the visibility problem for your PMs?"),
        ("prospect", "That would be a game changer honestly. How does that work exactly?"),
        ("rep",      "Great question. You connect GitHub or GitLab, map branches to tasks, and we automatically move cards when PRs are opened, reviewed, and merged. I can show you a live demo — want to see it now or schedule a separate session?"),
        ("prospect", "Let's see it now, we have time."),
        ("rep",      "Perfect. Let me share my screen..."),
    ],
    "demo": [
        ("rep",      "Welcome back! Last time we talked about the sprint visibility problem. Today I want to show you 3 things specifically: the git integration, the AI prioritization engine, and the analytics dashboard."),
        ("prospect", "Sounds great. Our CTO is also joining in a few minutes, by the way."),
        ("rep",      "Perfect, happy to have them. So first, let me show you the GitHub integration flow. As you can see here, when I create a task and link it to branch 'feature/payment-refactor', it auto-populates the git activity timeline..."),
        ("cto",      "Sorry I'm late. What did I miss?"),
        ("rep",      "No worries! I was just showing the GitHub integration. I'll do a quick recap: StackFlow auto-syncs commits and PRs to tasks, so your engineers never have to manually update status."),
        ("cto",      "How does it handle monorepos? We have a pretty complex setup."),
        ("rep",      "Great question — monorepo support is fully native. You can map tasks to specific subdirectory paths, and we use path-based filtering on the webhook payload. Here, let me show you the config..."),
        ("cto",      "OK that's actually impressive. What about the AI prioritization?"),
        ("rep",      "So the AI looks at: deadline proximity, blocking dependencies, team member availability, and historical velocity per engineer. It gives each sprint item a priority score and recommends reordering. You can override it manually too."),
        ("prospect", "Does it integrate with our on-call schedules? We use PagerDuty."),
        ("rep",      "PagerDuty integration is on the Q3 roadmap — ETA September. Right now you can manually mark engineers as unavailable. Let me put that in my notes as a requirement for your account."),
        ("cto",      "What's the pricing for our size?"),
        ("rep",      "For {emp} engineers on the Growth plan, you're looking at ${price}/month billed monthly, or we can do annual with a 15% discount — that brings it to ${annual_price}/year. Enterprise adds SSO, audit logs, and a dedicated CSM."),
        ("cto",      "We'll need SSO. That's a non-negotiable for us security-wise."),
        ("rep",      "Absolutely, Enterprise it is. I'll put together a formal proposal with SSO included and send it over by EOD. Any other questions?"),
        ("prospect", "I think we're good for now. Very impressive demo."),
        ("rep",      "Fantastic! I'll send the proposal + SOC2 cert document. Let's plan for a follow-up call in a week to discuss terms?"),
    ],
    "negotiation": [
        ("rep",      "Thanks for getting back to me on the proposal. I know your procurement team had some questions."),
        ("prospect", "Yes. So overall we love the product. The sticking points are: price and the data residency question."),
        ("rep",      "Understood. On price — what's the target budget your CFO is working with?"),
        ("prospect", "We were hoping for something closer to ${target_price}/month. The ${current_price} is a stretch for Q3."),
        ("rep",      "I hear you. Here's what I can do: if you commit to an annual contract today, I can bring it down to ${discounted_price}/month, which is a {discount}% reduction. I can also front-load the onboarding and give you a dedicated CSM at no extra cost for the first 6 months."),
        ("prospect", "The CSM is actually really valuable to us given our team size. What about data residency — we need EU hosting."),
        ("rep",      "EU data residency is available on Enterprise. Your data would be hosted in AWS eu-west-1 (Ireland). I can get that in writing in the MSA. Want me to loop in our legal team to accelerate the DPA?"),
        ("prospect", "Yes please. And can we have a 30-day out clause in the first 6 months?"),
        ("rep",      "I can offer a 60-day notice period after month 3 as a compromise. That gives your team time to evaluate without feeling locked in. Is that workable?"),
        ("prospect", "Let me check with our CFO and legal. Give me until Thursday."),
        ("rep",      "Absolutely. I'll hold the pricing until end of week. Talk Thursday!"),
    ],
    "qbr": [
        ("csm",      "Welcome to your Q2 QBR, {name}! I'm {csm_name}, your CSM. I've prepared a review of your team's usage and outcomes over the last 90 days."),
        ("customer", "Great, looking forward to it. We have our VP and 2 leads joining."),
        ("csm",      "Perfect. So in Q2, your workspace had {dau} daily active users on average, up {growth}% from Q1. Sprint completion rate improved from 71% to 84%. You merged {prs} PRs linked to StackFlow tasks."),
        ("customer", "Those numbers are strong. Our team has really adopted it."),
        ("csm",      "I'm glad! Now I want to be transparent — I did notice your seat utilization is at {util}%. You have {unused} seats unused. Would it make sense to reclaim those, or are you expecting headcount growth?"),
        ("customer", "We're hiring 5 engineers in Q3, so we'll need those seats actually."),
        ("csm",      "Perfect, I'll make a note. I also want to share some upcoming features your team will love: Slack v2 integration with thread syncing, advanced analytics with burndown forecasting, and a mobile app in beta."),
        ("customer", "The mobile app is something our remote leads have asked for. When's the beta?"),
        ("csm",      "July 15th. I'll send you an invite code directly. Now, any pain points from Q2 you want to flag?"),
        ("customer", "The sprint board was slow in early May. We filed tickets. Was that resolved?"),
        ("csm",      "Yes, we released a fix on May 9th — query optimization reduced load time by 65%. I'll add the incident summary to this report. Any other concerns?"),
        ("customer", "No, all good. Very satisfied overall."),
        ("csm",      "Wonderful! I'll send the full QBR deck by end of day. Let's schedule Q3 QBR for late August?"),
    ],
    "churn_save": [
        ("csm",      "Hi {name}, thanks for agreeing to this call. I know you've had some frustrations and I genuinely want to understand what's happened."),
        ("customer", "Honestly, our team has lost confidence in the platform. Too many bugs and the support response times were poor."),
        ("csm",      "I hear you, and I take full responsibility for the experience. Let me address each point directly. On bugs: our engineering team has resolved {bugs_fixed} of the issues you reported in the last 30 days. We're at 98.9% uptime this month. On support: we've added 3 agents to the queue and our average first response time is now under 2 hours."),
        ("customer", "That's better but we've already started evaluating Linear."),
        ("csm",      "I understand. Can I ask — what would it take for you to give us another 60 days before making a decision?"),
        ("customer", "We'd need a dedicated point of contact, faster escalation path, and honestly some credit for the downtime."),
        ("csm",      "I can do all three. I'm your dedicated CSM going forward — my direct line is in this calendar invite. For escalation, I'm giving you my personal Slack. For credit — I'm authorized to offer {credit_days} days of service credit, which is about ${credit_amount} off your next invoice."),
        ("customer", "That's... actually a meaningful gesture. We'll give it 60 more days."),
        ("csm",      "Thank you for the chance. I will not let you down. I'm creating a success plan for your account right now. Weekly check-ins, OK?"),
        ("customer", "OK. Let's try this."),
    ],
}

def _gong_speaker_id(role, company_id, idx=0):
    return f"spk_{role}_{company_id}_{idx}"

def generate_gong_transcripts():
    """
    Generates Gong-style call transcripts.
    Gong API response format: POST /v2/calls/transcript
    One transcript per call, with speaker diarization and timestamped sentences.
    """
    transcripts = []

    for company in companies:
        cid        = company["hs_object_id"]
        segment    = _infer_segment(company)
        cname      = company["name"]
        industry   = company["industry"]
        emp_count  = company["employee_count"]
        domain     = company["domain"]

        company_contacts = contacts_by_company.get(cid, [])
        company_deals    = deals_by_company.get(cid, [])
        rep              = SALES_REPS[int(company.get("hubspot_owner_id", "1")) - 1]
        csm              = random.choice([r for r in SALES_REPS if "CSM" in r["title"]])

        contact  = random.choice(company_contacts) if company_contacts else {"firstname": "Alex", "lastname": "Smith", "jobtitle": "VP Engineering", "email": f"alex@{domain}"}
        deal     = company_deals[0] if company_deals else {"amount": 5000, "hs_object_id": uid("deal_")}

        customer_name = f"{contact.get('firstname','Alex')} {contact.get('lastname','Smith')}".strip()
        deal_amount   = deal.get("amount", 5000)

        # Call types per segment
        if segment == "at_risk":
            call_types = random.choices(["churn_save", "qbr"], weights=[3, 1], k=random.randint(1, 3))
        elif segment == "expansion":
            call_types = random.choices(["qbr", "negotiation", "demo"], weights=[2, 2, 1], k=random.randint(1, 3))
        elif segment == "pql":
            call_types = random.choices(["discovery", "demo"], weights=[2, 1], k=random.randint(1, 2))
        else:
            call_types = random.choices(["discovery", "demo", "negotiation", "qbr"], weights=[1, 2, 1, 2], k=random.randint(1, 3))

        for call_idx, call_type in enumerate(call_types):
            call_id   = uid("call_")
            call_date = rand_date(SIX_M, NOW)
            duration_secs = random.randint(15 * 60, 55 * 60)  # 15–55 min

            # Participants
            parties = [
                {
                    "speakerId":    _gong_speaker_id("rep", cid, 0),
                    "name":         rep["name"],
                    "email":        rep["email"],
                    "title":        rep["title"],
                    "affiliation":  "Internal",
                    "phoneNumber":  None,
                },
                {
                    "speakerId":    _gong_speaker_id("customer", cid, 0),
                    "name":         customer_name,
                    "email":        contact.get("email", f"contact@{domain}"),
                    "title":        contact.get("jobtitle", "Engineering Lead"),
                    "affiliation":  "External",
                    "phoneNumber":  None,
                },
            ]

            # For QBR and churn_save, CSM joins instead of (or with) AE
            if call_type in ("qbr", "churn_save"):
                parties[0] = {
                    "speakerId":   _gong_speaker_id("csm", cid, 0),
                    "name":        csm["name"],
                    "email":       csm["email"],
                    "title":       csm["title"],
                    "affiliation": "Internal",
                    "phoneNumber": None,
                }

            # For demo, CTO sometimes joins
            if call_type == "demo" and random.random() < 0.5:
                parties.append({
                    "speakerId":   _gong_speaker_id("cto", cid, 0),
                    "name":        f"CTO @ {cname}",
                    "email":       f"cto@{domain}",
                    "title":       "CTO",
                    "affiliation": "External",
                    "phoneNumber": None,
                })

            # Build transcript from template
            template_lines = CALL_TOPICS.get(call_type, CALL_TOPICS["discovery"])
            transcript_segments = []
            current_time = 0.0

            seats_used   = random.randint(30, 90)
            seat_limit   = 100
            price_mo     = round(deal_amount / 12)
            price_annual = round(price_mo * 12 * 0.85)
            discount_pct = random.randint(10, 20)

            for speaker_role, text_tpl in template_lines:
                # Fill placeholders
                text = text_tpl.format(
                    name          = customer_name,
                    csm_name      = csm["name"],
                    company       = cname,
                    industry      = industry,
                    emp           = emp_count,
                    price         = f"{price_mo:,}",
                    annual_price  = f"{price_annual:,}",
                    target_price  = f"{round(price_mo * 0.8):,}",
                    current_price = f"{price_mo:,}",
                    discounted_price = f"{round(price_mo * (1 - discount_pct/100)):,}",
                    discount      = discount_pct,
                    dau           = random.randint(15, seats_used),
                    growth        = random.randint(5, 35),
                    prs           = random.randint(50, 500),
                    util          = round(seats_used / seat_limit * 100),
                    unused        = seat_limit - seats_used,
                    bugs_fixed    = random.randint(3, 12),
                    credit_days   = random.randint(7, 30),
                    credit_amount = random.randint(200, 2000),
                )

                # Map speaker role to speakerId
                if speaker_role == "rep":
                    speaker_id = _gong_speaker_id("rep", cid, 0)
                elif speaker_role == "csm":
                    speaker_id = _gong_speaker_id("csm", cid, 0)
                elif speaker_role == "cto":
                    speaker_id = _gong_speaker_id("cto", cid, 0)
                else:
                    # prospect / customer
                    speaker_id = _gong_speaker_id("customer", cid, 0)

                # Split into sentences for realistic Gong format
                sentences_raw = [s.strip() for s in text.replace("...", ".").split(".") if s.strip()]
                sentences = []
                for sent in sentences_raw:
                    word_count  = len(sent.split())
                    duration    = round(word_count * 0.45 + random.uniform(0.1, 0.5), 2)  # ~133 wpm
                    end_time    = round(current_time + duration, 2)
                    sentences.append({
                        "start": round(current_time, 2),
                        "end":   end_time,
                        "text":  sent + ".",
                    })
                    current_time = end_time + random.uniform(0.2, 1.5)  # pause between sentences

                transcript_segments.append({
                    "speakerId": speaker_id,
                    "topic":     call_type,
                    "sentences": sentences,
                })

            # Denormalized full text for vector embedding
            full_transcript_text = "\n".join(
                f"[{seg['speakerId']}]: " + " ".join(s["text"] for s in seg["sentences"])
                for seg in transcript_segments
            )

            # Gong API response format (flattened for ingestion)
            transcripts.append({
                # Gong call metadata
                "call_id":              call_id,
                "call_type":            call_type,
                "call_date":            iso(call_date),
                "duration_seconds":     duration_secs,
                "duration_minutes":     round(duration_secs / 60, 1),
                # Company context (for hybrid search filtering)
                "associated_company_id":   cid,
                "associated_company_name": cname,
                "associated_deal_id":      deal.get("hs_object_id"),
                "associated_deal_amount":  deal_amount,
                "segment":                 segment,
                "industry":                industry,
                # Parties
                "parties":              parties,
                "internal_attendees":   [p["name"] for p in parties if p["affiliation"] == "Internal"],
                "external_attendees":   [p["name"] for p in parties if p["affiliation"] == "External"],
                # Transcript — Gong native format
                "transcript":           transcript_segments,
                # Denormalized for vector embedding
                "full_transcript":      full_transcript_text,
                # Gong-style call analytics (simulated)
                "talk_ratio": {
                    "rep":      round(random.uniform(0.35, 0.55), 2),
                    "customer": round(random.uniform(0.35, 0.55), 2),
                },
                "longest_monologue_secs": random.randint(45, 180),
                "interactivity_score":    round(random.uniform(0.5, 0.95), 2),
                "sentiment":              _call_sentiment(call_type, segment),
                # Ingestion metadata
                "_source":              "gong_api_v2",
                "_api_endpoint":        "/v2/calls/transcript",
            })

    return transcripts


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _infer_segment(company: dict) -> str:
    """Infer segment from company metadata (reproduce generate_mock_data.py logic)."""
    name = company["name"]
    at_risk_names    = {"Acme Corp","Brightwave Labs","Cascadia Systems","DeltaCore Inc",
                        "Evergreen Digital","Forge Analytics","GridSpark","HorizonAI"}
    expansion_names  = {"IronMesh","JetStream Cloud","KineticHR","LatticeOps","Meridian Tech"}
    pql_names        = {"NovaBuild","OmniStack","PeakFlow"}
    if name in at_risk_names:    return "at_risk"
    if name in expansion_names:  return "expansion"
    if name in pql_names:        return "pql"
    return "healthy"

def _note_tags(segment: str) -> list:
    tag_map = {
        "at_risk":   ["churn-risk", "urgent", "billing", "re-engagement"],
        "expansion": ["upsell", "expansion", "renewal", "referral"],
        "pql":       ["pql", "trial", "conversion", "onboarding"],
        "healthy":   ["renewal", "multi-thread", "qbr", "check-in"],
    }
    pool = tag_map.get(segment, ["general"])
    return random.sample(pool, k=min(2, len(pool)))

def _note_sentiment(segment: str) -> str:
    if segment == "at_risk":   return random.choice(["negative", "neutral"])
    if segment == "expansion": return random.choice(["positive", "very_positive"])
    if segment == "pql":       return random.choice(["positive", "neutral"])
    return random.choice(["positive", "neutral"])

def _call_sentiment(call_type: str, segment: str) -> str:
    positive_calls = {"discovery", "demo", "qbr"}
    negative_calls = {"churn_save"}
    if call_type in positive_calls:  return "positive"
    if call_type in negative_calls:  return random.choice(["negative", "neutral"])
    return "neutral"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — generate and write all unstructured files
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🔍 Loading structured data from data/raw/...")

    print("\n📝 Generating HubSpot Sales Notes...")
    sales_notes = generate_sales_notes()
    print(f"   → {len(sales_notes)} notes across {len(companies)} companies")

    print("\n💬 Generating Zendesk Ticket Comments...")
    ticket_comments = generate_zendesk_comments()
    print(f"   → {len(ticket_comments)} ticket conversations")

    print("\n🎙️  Generating Gong Call Transcripts...")
    call_transcripts = generate_gong_transcripts()
    print(f"   → {len(call_transcripts)} call transcripts")

    # ── write files ──────────────────────────────────────────────────────────
    files = {
        "hubspot_sales_notes.json":     sales_notes,
        "zendesk_ticket_comments.json": ticket_comments,
        "gong_call_transcripts.json":   call_transcripts,
    }

    print(f"\n💾 Writing to {UNSTRUCTURED_DIR.resolve()}/")
    print("-" * 60)
    for fname, data in files.items():
        path = UNSTRUCTURED_DIR / fname
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        size_kb = path.stat().st_size / 1024
        print(f"  ✓ {fname:<40s} {len(data):>4} records  ({size_kb:>7.1f} KB)")

    print(f"\n✅ Done! Unstructured data written to: {UNSTRUCTURED_DIR.resolve()}")
    print("\n📊 Summary:")
    print(f"   Sales notes          : {len(sales_notes)} records")
    print(f"   Ticket conversations : {len(ticket_comments)} records")
    print(f"   Call transcripts     : {len(call_transcripts)} records")
    print(f"   Total text documents : {len(sales_notes) + len(ticket_comments) + len(call_transcripts)}")
    print("\n🔮 Next step: run vector_ingest.py to embed and load into your vector store.")
