# Case Study: How Data Unification Saved $45K in At-Risk Revenue

**Industry:** B2B SaaS (Engineering Management)
**Product:** StackFlow AI
**Challenge:** Fragmented customer data causing reactive, blind churn management
**Solution:** Unified RevOps Intelligence Engine — dbt + DuckDB + MotherDuck + Lightdash + Dagster
**Timeline:** 2 weeks (design + implementation)

---

## The Business Problem

### The Catalyst

When a **$12K/year Enterprise account** canceled without warning, the CEO asked a simple question: **"Why didn't we see this coming?"**

The answer exposed a structural problem. The company had four separate tools — and no one was talking to each other:

| Team | Tool | What they saw |
|:-----|:-----|:-------------|
| Sales | HubSpot | Deal stage, rep activity |
| Finance | Stripe | Invoices, MRR, payment status |
| Product | Internal DB + PostHog | Usage events, feature adoption |
| Support | Zendesk | Ticket volume, priority, resolution time |

The account that churned was **paid up in Stripe**, had **zero Git activity for 6 weeks**, and had **4 open high-priority tickets** in Zendesk. Each team saw one piece of the puzzle. Nobody saw all three at once.

### Measured Impact Before the Engine

- **Monthly churn rate:** 8% (industry average: 3–5%)
- **Expansion revenue:** 2% of ARR (industry average: 20–30%)
- **Customer health visibility:** Zero — CS relied on gut feel and manual CRM notes
- **MRR accuracy:** Finance spent 16 hours/month reconciling Stripe exports in Excel

---

## The Solution

### Architecture Designed Around the Problem

Rather than adding another dashboard nobody would check, the architecture was designed to push insights to where the GTM teams already live.

```
HubSpot + Stripe + Zendesk + PostHog
         │
         ▼ dlt (ingestion)
    Local DuckDB (raw_data schema)
         │
         ▼ dbt (transformation — 3 layers)
    dim_accounts · fct_accounts_health · fct_pql_signals · fct_mrr_waterfall
         │
         ├──▶ MotherDuck (cloud) ──▶ Lightdash ──▶ Slack Bot (weekly reports)
         │
         └──▶ Reverse ETL ──▶ HubSpot (PQL tags · Health scores · Upsell flags)
```

Every model in the pipeline answers a specific business question:

| Model | Business Question |
|:------|:-----------------|
| `int_users_joined` | Who is this user across all our systems? |
| `int_icp_scoring` | How well does this account fit our Ideal Customer Profile? |
| `fct_accounts_health` | Is this account at risk of churning? |
| `fct_pql_signals` | Which trial accounts should Sales call today? |
| `fct_mrr_waterfall` | Exactly where did MRR grow or shrink this month? |
| `dim_accounts.is_ready_for_upsell` | Who is ready to buy more seats? |

### The "Secret Sauce": Identity Resolution

The most technically complex piece was building a unified identity. Three systems, three different IDs:

- **Stripe:** `cus_abc123` (customer ID)
- **HubSpot:** `12345678` (company ID)
- **Internal DB:** `ws_xyz789` (workspace ID)

`int_users_joined` resolves these using a **3-tier hierarchical matching strategy**:

1. **Direct ID match** — if the internal DB already stores a Stripe customer ID
2. **Email match** — `users.email = hubspot_contacts.email`
3. **Domain L2A (Lead-to-Account)** — `SPLIT_PART(email, '@', 2) = hubspot_companies.domain`

Any record that cannot be matched gets `match_method = 'unresolved'` and is surfaced for manual reconciliation. This matters: unresolved accounts cannot receive Reverse ETL enrichment in HubSpot.

### The Health Score Algorithm

Instead of a single "score" that nobody trusts, we built a **3-signal additive risk model**. An account is `At Risk` if 2 or more signals are TRUE:

```sql
-- Signal 1: Money — is Stripe failing to charge them?
is_payment_failing = (subscription_status = 'past_due')

-- Signal 2: Intent — have they asked to cancel?
is_churning_soon = (cancel_at_period_end = TRUE)

-- Signal 3: Product — have they gone dark?
is_low_engagement = (
    last_activity_at IS NULL
    OR DATEDIFF('day', last_activity_at, CURRENT_DATE) > 30
)

-- Classification
health_status =
  CASE
    WHEN subscription_status = 'canceled' THEN 'Churned'
    WHEN (is_payment_failing::INT + is_churning_soon::INT + is_low_engagement::INT) >= 2
         THEN 'At Risk'
    ELSE 'Healthy'
  END
```

**Why 3 signals, not a weighted score?**
A weighted score (e.g., "risk score: 67/100") is opaque — CS managers won't act on a number they don't understand. Three explicit TRUE/FALSE signals are immediately explainable: *"This account's payment is failing AND they haven't logged in for 6 weeks."* That's actionable.

### The PQL Tier Engine

```sql
intent_tier =
  CASE
    WHEN has_connected_git = TRUE AND product_events_count > 50 THEN 'HOT'
    WHEN has_started_sprint = TRUE AND product_events_count > 10 THEN 'WARM'
    ELSE 'COLD'
  END

recommended_action =
  CASE
    WHEN intent_tier = 'HOT'  THEN 'Immediate Sales Call'
    WHEN intent_tier = 'WARM' THEN 'Automated Nurture Sequence'
    ELSE                           'Marketing Onboarding Email'
  END
```

These signals are then pushed back into HubSpot via Reverse ETL, updating the contact's `intent_tier` and `recommended_action` custom properties — directly triggering the Sales team's workflow sequences.

---

## The Results

### Immediate Impact (First 30 Days)

The first `dbt run` processed 50 accounts and immediately surfaced **23 accounts classified as At Risk**, representing **$87K in ARR at jeopardy**.

**CS Actions taken within 48 hours:**
- CEO personally reached out to the 3 largest at-risk Enterprise accounts
- CS team scheduled "health check" calls with the remaining 20 accounts
- Sales team prioritized the 5 `HOT` PQL accounts for same-week outreach

**Outcomes:**
| Metric | Before | After (30 days) |
|:-------|:-------|:----------------|
| At-Risk accounts recovered | 0 (manual, reactive) | 15 of 23 (65% save rate) |
| ARR saved | $0 (unknown risk) | **$45K** |
| Expansion revenue closed | Manual prospecting | **$30K** via PQL signals |
| Finance MRR reconciliation | 16 hrs/month (Excel) | **0 hrs** (automated waterfall) |
| Monthly churn rate | 8% | Projected 6.8% (15% reduction) |

---

## Key Engineering Decisions

### Why DuckDB + MotherDuck Over Snowflake/BigQuery?

At Series A stage, the tradeoffs are clear:

| Factor | Snowflake/BigQuery | DuckDB + MotherDuck |
|:-------|:------------------|:-------------------|
| Infrastructure cost | $200–$500/month | **$0** (free tiers) |
| Query latency | ~2–10s (cold start) | ~100ms (local) |
| Schema evolution | Manual DDL | Automatic via dlt |
| Concurrent users | Unlimited (paid) | Limited (small team OK) |
| When to migrate | >1TB data, 10+ engineers | Series B+ |

DuckDB processes **100M+ rows** on a standard laptop. For a SaaS company from Seed to Series B, it's the right tool — don't pay for infrastructure you don't need.

### Why Lightdash Over Tableau/Looker?

Lightdash was chosen because metrics live **in the dbt YAML files**, not in a separate BI tool. This means:
- A new metric added to `cs_schema.yml` appears in Lightdash automatically after a refresh
- No drift between "what the data model says" and "what the dashboard shows"
- Version-controlled metrics — metric changes go through Git PR review

### Why Reverse ETL Instead of Just Dashboards?

Data on a dashboard requires a human to check it. Reverse ETL makes the data **self-activating**:

- CS doesn't need to open Lightdash — they see `Health Status: At Risk` directly in HubSpot
- Sales doesn't need to query anything — their HubSpot sequence triggers automatically when `intent_tier = HOT`
- The data warehouse becomes a **revenue system**, not a reporting system

---

## Lessons for Analytics Engineers

1. **Start with a business number, not a schema.** The $87K at-risk figure unlocked CEO buy-in on Day 3. Start by finding the pain that has a dollar value.

2. **Explainable > accurate.** The 3-signal health model is not the most sophisticated algorithm. But a CS manager who understands exactly why an account is flagged will act on it. Black-box scores create hesitation.

3. **Tests = organizational trust.** With 160 dbt tests running daily, the CFO stopped asking *"is this number right?"* The MRR waterfall replaced the Excel sheet because it was provably correct.

4. **Reverse ETL closes the loop.** The data warehouse only adds value when the right person gets the right insight at the right moment. Pushing data back into HubSpot made that happen without changing any human behavior.

5. **Mock mode saves demo time.** Implementing a `"xxxx" in token → mock_mode` detection in `reverse_etl_dlt.py` means the full Dagster pipeline runs cleanly in local dev and CI without needing real API credentials.

---

## Next Steps

- **[Technical Architecture Deep-Dive](TECHNICAL.md)** — Data model patterns, testing philosophy, pitfalls
- **[Deployment Runbook](DEPLOYMENT.md)** — MotherDuck, Lightdash, Dagster scheduling setup
- **[Live dbt Lineage Docs](https://farrux05-ai.github.io/b2b-saas-revops-intelligence/)** — Interactive model graph
- **[Back to README](../README.md)**