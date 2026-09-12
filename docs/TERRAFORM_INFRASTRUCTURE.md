# Snowflake Infrastructure Architecture (Terraform IaC)

Ushbu hujjat **B2B SaaS RevOps Intelligence** loyihasi uchun Terraform (IaC) yordamida qurilgan Snowflake infratuzilmasi, nomlash standartlari (naming conventions), RBAC xavfsizlik modeli va CI/CD davomiyligi haqida to'liq texnik ma'lumot beradi.

---

## 📐 General Architecture Overview

```
                      +-------------------------------------------------+
                      |              SNOWFLAKE ACCOUNT                  |
                      +-------------------------------------------------+
                                              |
                     +------------------------+------------------------+
                     |                                                 |
         +-----------------------+                         +-----------------------+
         |      WAREHOUSES       |                         |       DATABASE        |
         +-----------------------+                         +-----------------------+
         | * COMPUTE_WH (SMALL)  |                         | REVOPS_INTELLIGENCE   |
         | * CI_WH (X-SMALL)     |                         +-----------------------+
         | * LOADING_WH (X-SMALL)|                                     |
         +-----------------------+                                     | 11 Schemas
                                             +-------------------------+-------------------------+
                                             |                         |                         |
                                     +---------------+         +---------------+         +---------------+
                                     |  RAW & INGEST |         | DBT TRANSFORM |         |  OBSERVE & CI |
                                     +---------------+         +---------------+         +---------------+
                                     | RAW_DATA      |         | STAGING       |         | ELEMENTARY    |
                                     +---------------+         | IDENTITY      |         | MARTS_CI      |
                                                               | DOMAINS       |         | MARTS_ELEM.   |
                                                               | INTEGRATION   |         +---------------+
                                                               | MARTS         |
                                                               | SEMANTIC_LAYER|
                                                               +---------------+

                               +----------------------------------------+
                               |        RBAC & SERVICE ACCOUNTS         |
                               +----------------------------------------+
                               | LOADER      ---> DLT_LOADER_USER       |
                               | TRANSFORMER ---> DBT_PROD / DBT_CI     |
                               | REPORTER    ---> LIGHTDASH_USER        |
                               +----------------------------------------+
```

---

## 🗄️ 1. Database & Schemas (Nomlash va Tuzilishi)

Barcha ma'lumotlar yagona production ma'lumotlar bazasi ichida mantiqiy qatlamlarga (schemas) ajratilgan.

* **Database Nomi:** `REVOPS_INTELLIGENCE`
* **Data Retention:** `1 kun` (Snowflake Standard Trial litsenziyasiga moslashtirilgan)

### Schemalar Ro'yxati (11 ta Schema):

| # | Schema Nomi | Qatlam (Layer) | Vazifasi va Kontenti |
|---|---|---|---|
| 1 | `RAW_DATA` | Ingestion (dlt) | CRM (HubSpot), Billing (Stripe), In-app event xom ma'lumotlari saqlanadi. |
| 2 | `STAGING` | Transformation | dbt `stg_` modellari — tip o'zgartirish, tozalash va standartlashtirish. |
| 3 | `IDENTITY` | Core Domain | Foydalanuvchi va kompaniyalarni yagona ID (Identity Resolution) bilan bog'lash. |
| 4 | `DOMAINS` | Core Domain | CRM (Deals, Contacts) va Billing (Subscriptions, Invoices) mantiqiy modellar. |
| 5 | `INTEGRATION` | Core Domain | Cross-system churn va revenue attribution modellarini birlashtirish. |
| 6 | `MARTS` | Presentation | Business intelligence va reporting uchun tayyor Dim/Fact jadvallar (ARR, NRR, CAC, LTV). |
| 7 | `SEMANTIC_LAYER` | Analytics | Lightdash va boshqa BI vositalari uchun semantik va aggregat qatlam. |
| 8 | `MARTS_CI` | CI / Testing | Pull Request testlari uchun vaqtinchalik dbt CI modellari. |
| 9 | `ELEMENTARY` | Observability | Data quality monitoring, test natijalari va anomaliyalarni kuzatish. |
| 10 | `MARTS_ELEMENTARY` | Observability | Production elementary monitoring hisobotlari. |
| 11 | `MARTS_ELEMENTARY_CI` | CI Observability | CI paytidagi Elementary test natijalari. |

---

## ⚡ 2. Virtual Warehouses (Resurslar va Izolyatsiya)

Hisoblash resurslarini to'qnashuvlarsiz va xarajatlarni optimallashtirgan holda ajratish uchun 3 ta alohida Warehouse yaratilgan:

| Warehouse Nomi | Hajmi (Size) | Auto-Suspend | Auto-Resume | Vazifasi |
|---|---|---|---|---|
| `COMPUTE_WH` | `SMALL` | `60 sek` | `TRUE` | Production dbt jadvallarini qayta qurish va Lightdash BI so'rovlari uchun. |
| `CI_WH` | `X-SMALL` | `30 sek` | `TRUE` | GitHub Actions CI/CD run'laridagi avtomatik testlar uchun. |
| `LOADING_WH` | `X-SMALL` | `60 sek` | `TRUE` | `dlt` (data load tool) orqali ma'lumotlarni tushirish va yuklash uchun. |

---

## 🔐 3. RBAC (Role-Based Access Control) va Service Accounts

Prinsip: **Least Privilege Principal** (Har bir xizmatga faqat o'ziga kerakli ruxsatlar beriladi).

```
                      +-------------------+
                      |   ACCOUNTADMIN    |
                      +-------------------+
                                |
               +----------------+----------------+
               |                                 |
     +-------------------+             +-------------------+
     |   LOADER (Role)   |             | TRANSFORMER (Role)|
     +-------------------+             +-------------------+
     | Access: RAW_DATA  |             | Access: STAGING,  |
     | WH: LOADING_WH    |             | MARTS, SEMANTIC   |
     +-------------------+             | WH: COMPUTE/CI_WH |
               |                       +-------------------+
     +-------------------+                       |
     |  DLT_LOADER_USER  |         +-------------+-------------+
     +-------------------+         |                           |
                         +-------------------+       +-------------------+
                         |   DBT_PROD_USER   |       |    DBT_CI_USER    |
                         +-------------------+       +-------------------+

                               +-------------------+
                               |  REPORTER (Role)  |
                               +-------------------+
                               | Access: MARTS,    |
                               | SEMANTIC (Select) |
                               | WH: COMPUTE_WH    |
                               +-------------------+
                                         |
                               +-------------------+
                               |  LIGHTDASH_USER   |
                               +-------------------+
```

### Roles va Permissions:

1. **`LOADER` Role:**
   - **Ruxsatlar:** `RAW_DATA` schemasiga to'liq yozish/o'qish, future tables yaratish, `LOADING_WH` ishlatish.
   - **Foydalanuvchisi:** `DLT_LOADER_USER`

2. **`TRANSFORMER` Role:**
   - **Ruxsatlar:** `RAW_DATA` dan faqat o'qish (`SELECT`), dbt transformation va presentation schemalarida (`STAGING`, `MARTS`, va boshqalar) jadvallar yaratish/o'chirish (`ALL PRIVILEGES`), `COMPUTE_WH` va `CI_WH` ishlatish.
   - **Foydalanuvchilari:** `DBT_PROD_USER` (Production dbt), `DBT_CI_USER` (GitHub Actions CI)

3. **`REPORTER` Role:**
   - **Ruxsatlar:** Faqat `MARTS` va `SEMANTIC_LAYER` schemalaridagi jadvallar hamda view'lardan o'qish (`SELECT`), `COMPUTE_WH` ishlatish.
   - **Foydalanuvchisi:** `LIGHTDASH_USER` (BI Dashboard)

---

## 🛠️ 4. Terraform Kod Strukturasi

Infratuzilma kodi modulli arxitektura asosida tashkillashtirilgan:

```
terraform/
├── main.tf                        # Root Provider sozlamalari (snowflakedb/snowflake)
├── variables.tf                   # Asosiy o'zgaruvchilar
├── outputs.tf                     # dbt va pipeline uchun kerakli outputlar
├── .gitignore                     # Xavfsizlik qoidalari
├── README.md                      # Qisqa yo'riqnoma
│
├── modules/                       # Reusable modullar
│   ├── database/
│   │   ├── main.tf               # Database + 11 ta Schema yaratish
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── warehouse/
│   │   ├── main.tf               # COMPUTE_WH, CI_WH, LOADING_WH
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── rbac/
│       ├── main.tf               # 3 Role, 4 User va 20+ Grantlar
│       ├── variables.tf
│       └── outputs.tf
│
└── environments/                  # Muhitlar
    └── prod/                      # Production muhit
        ├── main.tf               # Modullarni jamlash va sim bilan bog'lash
        ├── variables.tf
        └── terraform.tfstate.enc # AES-256 bilan shifrlangan holat fayli
```

---

## 🔄 5. CI/CD & Encrypted State Security (.github/workflows/terraform_snowflake.yml)

Public GitHub repository bo'lgani sababli `terraform.tfstate` ochiq holatda git-ga qo'shilmaydi. Buning uchun **AES-256-CBC Encrypted State** mexanizmi yo'lga qo'yilgan.

### Ishlash prinsipi:
1. `terraform/environments/prod/terraform.tfstate.enc` shifrlangan fayli git-da saqlanadi.
2. GitHub Actions ishga tushganda `SNOWFLAKE_TF_PASSWORD` secret paroli orqali `openssl` yordamida state-ni xotirada deshifrlaydi.
3. `terraform init`, `terraform plan` va `terraform apply` bajariladi.
4. Muvaffaqiyatli o'tgach, yangilangan state qayta AES-256 bilan shifrlanadi va `[skip ci]` tegi bilan git-ga xavfsiz avto-commit qilinadi.
5. `permissions: contents: write` botga push qilish uchun yetarli ruxsat beradi.

---

## 🚀 Quick Verification Commands

Local mashinada Terraform-ni tekshirish uchun:

```bash
cd terraform/environments/prod

# 1. State-ni deshifrlash (agar kerak bo'lsa)
openssl enc -d -aes-256-cbc -pbkdf2 -in terraform.tfstate.enc -out terraform.tfstate -pass pass:"<PASSWORD>"

# 2. Status ko'rish
terraform init
terraform plan

# 3. State-ni qayta shifrlash
openssl enc -aes-256-cbc -pbkdf2 -in terraform.tfstate -out terraform.tfstate.enc -pass pass:"<PASSWORD>"
```
