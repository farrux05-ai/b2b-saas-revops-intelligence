# Lightdash Dashboards as Code

## Directory Structure

```
lightdash/
├── executive-overview.yml           # Executive C-Suite Dashboard
├── cs-account-health.yml            # Customer Success & Churn Risk Dashboard
├── finance-revenue-analytics.yml    # Finance & MRR Waterfall Dashboard
├── sales-pipeline.yml               # Sales Pipeline & Win Rate Dashboard
└── product-plg-signals.yml          # Product-Qualified Leads & Activation Dashboard
```

## Dashboards Overview

| Dashboard | Target Audience | Primary Focus |
|---|---|---|
| `executive-overview` | CEO, CFO, C-Suite | Total MRR, At-Risk ARR, Account Health Distribution |
| `finance-revenue-analytics` | CFO, Finance Team | MRR Waterfall, NRR vs GRR Trends, Cohorts |
| `cs-account-health` | Customer Success Team | 3-Signal Churn Prevention, At-Risk Accounts Table |
| `sales-pipeline` | VP Sales, AEs, SDRs | Weighted Pipeline by Stage, Win Rate, Stale Deals |
| `product-plg-signals` | PMs, Growth Leaders | Activation Funnel, GTM Priority Matrix, Trial Risks |

## CLI — Initial Deployment

```bash
# 1. Install Lightdash CLI globally
npm install -g @lightdash/cli

# 2. Login to your Lightdash cloud instance
lightdash login https://your-lightdash.cloud

# 3. Select project
lightdash config set-project

# 4. Deploy dbt semantic layer (dbt meta tags)
lightdash deploy

# 5. Upload all dashboards as code
lightdash upload --force
```

## CLI — Incremental Updates

```bash
# Upload only modified dashboards
lightdash upload

# Upload a single dashboard with embedded charts
lightdash upload -d cs-account-health --include-charts

# Upload a single chart
lightdash upload -c cs-mrr-at-risk
```

## Validation & Linting

```bash
# Validate dashboard YAML syntax before deployment
lightdash lint
```

## CI/CD Integration (GitHub Actions)

```yaml
name: Deploy Lightdash Dashboards

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm install -g @lightdash/cli
      - run: lightdash login ${{ secrets.LIGHTDASH_URL }} --token ${{ secrets.LIGHTDASH_API_KEY }}
      - run: lightdash config set-project --project ${{ secrets.LIGHTDASH_PROJECT }}
      - run: lightdash deploy          # Semantic layer (dbt meta)
      - run: lightdash upload --force  # Dashboards + charts
```

## Adding Semantic Meta Tags in `schema.yml` (`dim_accounts` Example)

```yaml
models:
  - name: dim_accounts
    meta:
      label: "Accounts"
      group_label: "Core"
    columns:
      - name: mrr
        meta:
          dimension:
            hidden: true
          metrics:
            total_mrr:
              type: sum
              label: "Total MRR"
              format: "usd"
```
