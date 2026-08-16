# Lightdash Dashboards as Code

## Fayl tuzilishi

```
lightdash/
├── spaces/          # 6 ta space (jamoa bo'yicha)
├── charts/          # 17 ta chart
└── dashboards/      # 5 ta dashboard
```

## Dashboardlar

| Dashboard | Space | Auditoriya |
|---|---|---|
| `executive-overview` | Executive Overview | CEO, CFO |
| `finance-revenue-analytics` | Finance | CFO, Finance jamoasi |
| `cs-account-health` | Customer Success | CS jamoasi |
| `sales-pipeline` | Sales | AE, SDR |
| `marketing-lead-funnel` | Marketing | Marketing jamoasi |
| `product-plg-signals` | Product | PM, Growth |

## CLI — Birinchi marta deploy

```bash
# 1. CLI o'rnatish
npm install -g @lightdash/cli

# 2. Login (Snowflake ulangan Lightdash instance)
lightdash login https://your-lightdash.cloud

# 3. Loyihani tanlash
lightdash config set-project

# 4. dbt modellarni deploy (semantic layer)
lightdash deploy

# 5. Barcha dashboardlarni birga deploy
lightdash upload --force
```

## CLI — O'zgarishlar deploy

```bash
# Faqat o'zgargan fayllar upload qilinadi
lightdash upload

# Bitta dashboard
lightdash upload -d cs-account-health --include-charts

# Bitta chart
lightdash upload -c cs-mrr-at-risk
```

## Validation (deploy oldidan)

```bash
lightdash lint
```

## CI/CD (GitHub Actions)

```yaml
# .github/workflows/lightdash.yml
name: Deploy Lightdash

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: npm install -g @lightdash/cli
      - run: lightdash login ${{ secrets.LIGHTDASH_URL }} --token ${{ secrets.LIGHTDASH_API_KEY }}
      - run: lightdash config set-project --project ${{ secrets.LIGHTDASH_PROJECT }}
      - run: lightdash deploy          # semantic layer (dbt meta)
      - run: lightdash upload --force  # dashboards + charts
```

## .gitignore ga qo'shish

```
lightdash/.lightdash-metadata.json
```

## schema.yml da meta tag qo'shish (dim_accounts misoli)

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
