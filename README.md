# StackFlow — Business Context & Source Schema

## The Company

**StackFlow** is a B2B SaaS project management tool built for **software engineering teams at mid-market companies** (50–500 employees). Think Linear + Jira hybrid — fast UI, Git integrations, sprint tracking, and AI-powered issue prioritization.

**Pricing model:** Seat-based subscription

| Plan | Price | Contract |
|---|---|---|
| Starter | $12 / seat / month | Monthly |
| Growth | $25 / seat / month | Monthly or Annual |
| Enterprise | $60 / seat / month | Annual only |

**GTM motion:** Mixed — **Sales-Led** for Enterprise, **Product-Led** for Starter/Growth (free trial → convert).

---

## The Core Business Problem

StackFlow hit **$4.2M ARR** after its Seed round. The board asked one question:

> *"We're growing, but net revenue retention is 94%. That's a slow bleed. Where are we losing money and why?"*

The CEO pulled three people for an answer:

- **Finance** opened Stripe — raw payments, no customer context
- **Sales** opened HubSpot — deal history, no product signal
- **CS** opened Zendesk — support tickets, no financial context

**Nobody could answer the question.** Three tools, three versions of truth, zero shared language.

### Specific Pain Points

**1. Expansion blind spot**
Sales had no visibility into which accounts were hitting their seat limits in the product. Upsell opportunities were being missed every month because the signal lived in the Internal DB, not in HubSpot.

**2. Silent churn**
Customer Success didn't see Stripe payment failures until the account was already gone. By the time a `past_due` subscription showed up in a manual report, the customer had mentally churned weeks earlier.

**3. PLG leakage**
Free trial users who completed activation (connected Git, created their first sprint, invited a teammate) were never handed off to Sales. There was no "Product Qualified Lead" signal in HubSpot, so activated accounts were left to self-serve and eventually drop off.

**4. MRR math was wrong**
Finance calculated MRR from Stripe invoice totals, missing mid-month plan upgrades and prorated charges. The number in the board deck was structurally incorrect.

---

## Source Systems

| Source | Tool | What lives here |
|---|---|---|
| CRM | HubSpot | Companies, Contacts, Deals, Activities |
| Billing | Stripe | Subscriptions, Invoices, Payments |
| Product | Internal PostgreSQL | Users, Workspaces, Events |
| Support | Zendesk | Tickets, SLA data |

---

## Raw Source Schema

These are the actual fields that come out of each API or database. This is the ground truth that the staging layer reads from.

---

### HubSpot

#### `hubspot.companies`
```
hs_object_id           -- HubSpot internal company ID
name
domain                 -- e.g. "acme.com" — primary key for identity resolution
industry
employee_count
hs_lead_status         -- NEW | OPEN | IN_PROGRESS | QUALIFIED | UNQUALIFIED
lifecyclestage         -- lead | marketingqualifiedlead | salesqualifiedlead | customer
hubspot_owner_id
createdate
hs_lastmodifieddate
```

#### `hubspot.deals`
```
hs_object_id
dealname
dealstage              -- appointmentscheduled | qualifiedtobuy | presentationscheduled
                       -- decisionmakerboughtin | contractsent | closedwon | closedlost
amount
closedate
pipeline
associated_company_id  -- FK → companies.hs_object_id
hs_deal_stage_probability
createdate
```

#### `hubspot.contacts`
```
hs_object_id
email
firstname
lastname
jobtitle
associated_company_id  -- FK → companies.hs_object_id
hs_lead_status
createdate
lastmodifieddate
```

---

### Stripe

#### `stripe.subscriptions`
```
id                     -- "sub_xxx"
customer_id            -- "cus_xxx"
status                 -- active | past_due | canceled | trialing | unpaid
plan_id                -- plan_starter_monthly | plan_growth_annual | plan_enterprise_annual
quantity               -- seat count
unit_amount            -- price per seat in cents
currency
current_period_start
current_period_end
cancel_at_period_end   -- boolean — soft churn signal
created
canceled_at
trial_end
metadata               -- JSON: {"workspace_id": "ws_xxx", "hubspot_company_id": "123"}
```

#### `stripe.invoices`
```
id
subscription_id
customer_id
status                 -- paid | open | void | uncollectible
amount_due
amount_paid
amount_remaining
currency
period_start
period_end
due_date
paid_at
created
billing_reason         -- subscription_cycle | subscription_update | manual
```

#### `stripe.payments`
```
id
invoice_id
customer_id
amount
currency
status                 -- succeeded | failed | pending
failure_code           -- card_declined | insufficient_funds | ...
created
```

---

### Internal PostgreSQL

#### `internal.workspaces`

This is the **central bridge entity** of the entire data model. Every other system maps back to a workspace.

```
id                     -- "ws_xxx" — primary entity across the stack
name
plan                   -- starter | growth | enterprise
seat_limit
created_at
trial_started_at
trial_ended_at
converted_at           -- NULL = still in trial or churned
owner_user_id
stripe_customer_id     -- FK → Stripe (direct bridge)
hubspot_company_id     -- FK → HubSpot (direct bridge)
```

#### `internal.users`
```
id
workspace_id           -- FK → workspaces.id
email
role                   -- owner | admin | member | viewer
invited_at
activated_at           -- timestamp of first meaningful action
last_seen_at
created_at
is_deleted
```

#### `internal.events`
```
id
workspace_id
user_id
event_name             -- project_created | issue_assigned | sprint_started
                       -- git_integration_connected | ai_prioritization_used
                       -- invite_sent | comment_added | report_viewed
properties             -- JSON: event-specific payload
occurred_at
```

---

### Zendesk

#### `zendesk.tickets`
```
id
subject
status                 -- new | open | pending | solved | closed
priority               -- low | normal | high | urgent
requester_email        -- used for identity resolution → users.email → workspace_id
assignee_id
created_at
updated_at
solved_at
first_reply_at
tags                   -- array: billing | bug | onboarding | churn-risk
satisfaction_rating    -- good | bad | null
```

---

## Identity Resolution

The core modeling challenge: **four systems with no shared ID.**

```
HubSpot company  ←——————————→  Internal workspace  ←——————————→  Stripe customer
                   domain match      ↑     ↑            stripe_customer_id
                   (fallback)        |     |
                              hubspot_company_id      (direct, set at signup)
                              (direct, set at signup)

Zendesk ticket  →  requester_email  →  users.email  →  workspace_id
```

`internal.workspaces` is the **bridge table**. It stores both `stripe_customer_id` and `hubspot_company_id` as foreign keys, set at the moment a workspace is created or a deal is closed. The `int_accounts_spine` model in the intermediate layer uses this table as the anchor, joining everything else to it. When the direct ID link is missing, the fallback is domain matching between `hubspot.companies.domain` and the owner's email domain in `internal.users`.
