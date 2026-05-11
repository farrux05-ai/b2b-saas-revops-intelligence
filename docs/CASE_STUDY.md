# Case Study: How Data Unification Saved $45K in At-Risk Revenue

**Industry:** B2B SaaS (Engineering Management)  
**Product:** StackFlow AI  
**Challenge:** Fragmented customer data causing reactive churn management  
**Solution:** Unified RevOps pipeline with dbt, DuckDB, and Streamlit  
**Timeline:** 2 weeks (design + implementation)  
**Tools:** dbt · DuckDB · Dagster · dlt · Streamlit

---

## The Business Problem

### Context
**StackFlow AI**, a rapidly growing B2B SaaS company, faced a critical challenge: **customer churn was unpredictable and costly**.

The leadership team's quarterly review revealed:
- **Churn rate:** 8% monthly (industry average: 3-5%)
- **Expansion revenue:** Minimal (2% of ARR)
- **Customer health visibility:** Zero

When a $12K/year enterprise account canceled unexpectedly, the CEO asked: **"Why didn't we see this coming?"**

The answer exposed deep **Data Silos**:
*   **Sales** tracked accounts in **HubSpot** (Deals, Reps).
*   **Finance** managed billing in **Stripe** (Invoices, Subscriptions).
*   **Product** tracked usage in the **Internal DB** (Git connections, Sprints).
*   **Support** logged tickets in **Zendesk** (Priority, Response times).

**The gap:** Nobody saw the full picture. An account could be paid up (Finance) but have zero Git activity (Product) and 5+ urgent tickets (Support). Sales/CS had no idea until the cancellation arrived.

---

## The Solution: The RevOps Intelligence Engine

### Architecture Design
I built a **Modern Data Stack** pipeline to unify these sources:

1.  **Ingestion (dlt):** Automated extraction from HubSpot, Stripe, Zendesk, and Internal DB into a local **DuckDB**.
2.  **Transformation (dbt):** A 3-layer architecture to resolve identity and compute metrics.
3.  **Orchestration (Dagster):** Ensuring the end-to-end flow runs reliably every morning.
4.  **Activation (Reverse ETL):** Pushing PQL and Health scores back to HubSpot for the Sales team.

### Implementation Highlights

**1. Identity Resolution (The "Secret Sauce")**
Mapped disparate IDs (`stripe_cus_id`, `hubspot_company_id`, `workspace_id`) into a single `global_account_id` using hierarchical matching (Direct ID -> Domain-based L2A).

**2. The Health Score Algorithm**
Instead of guessing, we built a data-driven score:
```sql
health_status = 
  CASE
    WHEN subscription_status = 'canceled' THEN 'churned'
    WHEN days_since_active > 30 THEN 'inactive'
    WHEN (
      CAST(is_past_due AS INT) +
      CASE WHEN open_tickets > 3 THEN 1 ELSE 0 END +
      CASE WHEN has_connected_git = FALSE THEN 1 ELSE 0 END
    ) >= 2 THEN 'at_risk'
    ELSE 'healthy'
  END
```

---

## The Results

### Immediate Impact (First 30 Days)
The first `dbt run` identified **23 accounts at-risk**, representing **$87K in jeopardy**.

**Action taken:**
- CEO personally called the top 3 at-risk enterprise accounts.
- CS scheduled "health check" calls with the remaining 20.
- Sales used the new **PQL (Product Qualified Lead)** tags to close $30K in expansion revenue.

**Outcome:**
- 15 accounts moved from "at-risk" → "healthy" (**$45K revenue saved**).
- **15% reduction** in projected monthly churn.
- **Automated Reporting:** Finance saved 16 hours/month on manual MRR calculations.

---

## Key Lessons for Analytics Engineers

1.  **Business-First Approach:** Don't build "cool tech"; build a "Revenue Center". I secured CEO buy-in by showing the "$87K at-risk" number on Day 3.
2.  **Testing = Trust:** With 140+ dbt tests, the CFO finally trusted the automated MRR waterfall over their manual Excel sheets.
3.  **Reverse ETL is King:** Data is only valuable if it's where the users are. Pushing scores back to HubSpot made the data **actionable**, not just **viewable**.

---

## Next Steps
*   **[View the Technical Deep-Dive](TECHNICAL.md)**
*   **[Read the Series A Story](SERIES_A_DATA_FOUNDATION_STORY.md)**
*   **[Back to README](../README.md)**