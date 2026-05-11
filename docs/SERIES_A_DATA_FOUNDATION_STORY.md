# The Series A Data Chaos: Breaking Down SaaS Data Silos

## Background: Meet StackFlow AI
**StackFlow AI** is a rapidly growing B2B Engineering Management SaaS platform. 
After successfully raising a $10M Series A round, the company is experiencing hyper-growth: headcount has grown from 15 to 60+, and Annual Recurring Revenue (ARR) has crossed the $3M mark. 

However, this rapid growth has introduced a new, critical bottleneck: **Data Silos**.

## The Architecture of Chaos (The "Before" State)
As the company scaled, different departments adopted best-in-class SaaS tools to manage their specific operations. While these tools are great individually, they do not talk to each other natively in a way that answers complex RevOps questions.

The current tech stack consists of:
1. **Sales & Marketing (HubSpot):** 
   - Tracks incoming Leads, Accounts, and the sales pipeline. 
   - Sales knows the pipeline, but not if those leads actually "activate" (e.g., connect Git) in the product.

2. **Finance & Billing (Stripe):** 
   - Handles subscriptions and payments. 
   - Finance knows the MRR, but can't link it to the specific marketing campaign that brought the customer in.

3. **Customer Success (Zendesk):** 
   - Managing support tickets. 
   - CS knows who is complaining, but doesn't know the "Seat Utilization" or "Activation Tier" of the complaining account.

4. **Product Team (Internal Application Database):**
   - Tracks actual product usage: Project creation, Git connections, and AI-prioritization usage.

## The Breaking Point: The "Friday VLOOKUP" Nightmare
Currently, the Revenue Operations (RevOps) Manager spends every Friday afternoon downloading massive CSV exports from HubSpot, Stripe, and Zendesk. 

They spend hours doing complex Excel `VLOOKUP`s to answer basic questions:
- *"Which trial accounts are 'Product Qualified' (PQL) and should be called by Sales today?"*
- *"Are customers with low 'Git Connection' activity at a higher risk of churning their Stripe subscription?"*
- *"What is our exact MRR Waterfall (New, Expansion, Churn) across different customer segments?"*

## The Mission: The RevOps Intelligence Engine
As the first Senior Analytics Engineer hired at **StackFlow AI**, your mission is to build the **Single Source of Truth** using a modern, efficient stack.

**The Strategy:**
1.  **Ingestion (dlt):** Use the Data Load Tool to ingest raw JSON from HubSpot, Stripe, Zendesk, and the internal DB into a local **DuckDB** instance.
2.  **Transformation (dbt):** Implement a 3-layer architecture (Identity, Domains, Integration) to resolve the "Account Identity" across all silos.
3.  **Activation (Reverse ETL):** Push critical signals (PQL tags, Health scores) back into the tools (HubSpot/Zendesk) where the GTM teams actually work.

By building this engine, you move the Data Warehouse from a passive "Cost Center" to an active **"Revenue Center"**.
