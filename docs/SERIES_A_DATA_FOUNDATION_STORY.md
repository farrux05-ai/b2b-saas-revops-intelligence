# The Series A Data Chaos: Breaking Down SaaS Data Silos

## Background: Meet StackFlow AI
**StackFlow AI** is a rapidly growing B2B workflow automation SaaS platform. 
After successfully raising a $10M Series A round, the company is experiencing hyper-growth: headcount has grown from 15 to 60+, and Annual Recurring Revenue (ARR) has crossed the $3M mark. 

However, this rapid growth has introduced a new, critical bottleneck: **Data Silos**.

## The Architecture of Chaos (The "Before" State)
As the company scaled, different departments adopted best-in-class SaaS tools to manage their specific operations. While these tools are great individually, they do not talk to each other natively in a way that answers complex RevOps questions.

The current tech stack consists of:
1. **Sales & Marketing (HubSpot):** 
   - Tracks incoming Leads, Accounts (Companies), and the sales pipeline (Deals). 
   - The Sales team knows exactly how many deals are in the pipeline, but they have no idea if those deals actually lead to retained, paying customers after 6 months.

2. **Finance & Billing (Stripe):** 
   - Handles subscriptions, invoice generation, and processes payments. 
   - The Finance team knows exactly what the Monthly Recurring Revenue (MRR) is, but they cannot trace an invoice back to the specific marketing campaign or webinar that originally brought the customer in.

3. **Customer Success (Zendesk):** 
   - Managing support tickets and customer interactions. 
   - The CS team knows who is complaining the most, but they don't know the MRR size of the complaining customer. They might be accidentally prioritizing a $50/month user over a $5,000/month enterprise client.

4. **Product Team (Internal PostgreSQL/App Database):**
   - Tracks actual product usage, user logins, and organization setups.

## The Breaking Point: The "Friday VLOOKUP" Nightmare
Currently, the Revenue Operations (RevOps) Manager spends every Friday afternoon downloading massive CSV exports from HubSpot, Stripe, and Zendesk. 

They spend hours doing complex Excel `VLOOKUP`s and Pivot Tables to answer basic management questions:
- *"What is our Time-to-Revenue for Enterprise Deals created in HubSpot?"*
- *"Are customers with high Zendesk ticket volumes at a higher risk of churning their Stripe subscription?"*
- *"What was the exact Return on Investment (ROI) of our Q1 Marketing Campaign in terms of actual collected cash, not just 'Closed/Won' deals?"*

## The Mission: Phase 1 Data Foundation
As the first Senior Analytics Engineer hired at FlowSync, your immediate mission is **not** to build predictive machine learning models or complex Reverse ETL pipelines. 

**Your mission is to build the Single Source of Truth.**

The first step is moving away from generic abstractions, and bringing the literal SaaS tools into the staging layer of the Data Warehouse. 
By extracting raw data and mapping it exactly into `stg_hubspot`, `stg_stripe`, and `stg_zendesk`, you will build a solid foundation. 

Once the data is modeled from the perspective of the tools in the Staging layer, you can use the Intermediate layer to resolve entities (matching `HubSpot Company Domain` to `Stripe Customer Email`) and finally build the core business models (`dim_accounts`, `fct_mrr`) that the CEO desperately needs.
