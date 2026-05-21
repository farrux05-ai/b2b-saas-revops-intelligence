"""
dagster_pipeline.py
===================
SentinelGuard B2B SaaS — RevOps Intelligence Engine
Orchestration layer: Dagster manages the full ELT pipeline lifecycle.

PIPELINE OQIMI (Data Flow):
  [1] ingestion_dlt      — Tashqi manbalar (API/JSON) → DuckDB raw_data
  [2] revops_dbt_assets  — raw_data → staging → intermediate → marts
  [3] motherduck_sync    — Local DuckDB → MotherDuck Cloud
  [4] dlt_reverse_etl   — marts (DuckDB) → HubSpot CRM

MUHIM ARXITEKTURA QARORLARI:
  - Har bir asset o'z xatosini Dagster UI'da ko'rsatadi (monitoring)
  - RetryPolicy: API chaqiruvlardagi vaqtinchalik xatolar avtomatik hal bo'ladi
  - AssetSelection.all(): Dagster o'zi qaramliklar grafini qurib, to'g'ri tartibda ishlatadi
  - dbt_executable: shutil.which() — local'da ham, Cloud Docker'da ham dbt'ni topadi
  - Barcha secrets: os.getenv() orqali — .env (local) yoki Dagster Cloud Env Vars (production)
"""

import os
import shutil
from pathlib import Path

from dagster import (
    AssetExecutionContext,
    AssetSelection,
    Backoff,
    Definitions,
    RetryPolicy,
    ScheduleDefinition,
    asset,
    define_asset_job,
)
from dagster_dbt import DbtCliResource, dbt_assets

from ingestion.stackflow_pipeline import run_pipeline as run_ingestion
from scripts.reverse_etl_dlt import run as run_reverse_etl_sync
from scripts.sync_to_motherduck import sync_to_motherduck as run_motherduck_sync

# ===========================================================================
# PATHS — Barcha yo'laklar bu yerda markazlashtirilgan
# Path(__file__).parent → bu faylning joylashgan papkasi
# .resolve() → nisbiy yo'lakni mutlaq yo'lakka aylantiradi (ishonchli)
# ===========================================================================

DBT_PROJECT_DIR = Path(__file__).parent.resolve()

# shutil.which() — xuddi Linux'dagi `which dbt` komandasidek ishlaydi.
# Local'da: .venv/bin/dbt | Docker/Cloud'da: /usr/local/bin/dbt
# Agar dbt topilmasa — ishga tushishda darhol xato beradi (muammo yashirinmaydi)
_dbt_executable = shutil.which("dbt") or str(
    DBT_PROJECT_DIR / ".venv" / "bin" / "dbt"
)

# ===========================================================================
# LAYER 1: EXTRACT & LOAD — Ingestion
#
# Nima qiladi:
#   dlt library yordamida HubSpot, Stripe, Zendesk, Internal ma'lumotlarni
#   DuckDB'ga yuklaydi (raw_data schema).
#
# PRODUCTION ESLATMASI:
#   Bu loyihada ma'lumotlar JSON fayllardan o'qiladi (o'quv maqsadida).
#   Real production'da bu yerda to'g'ridan-to'g'ri API chaqiruvi bo'ladi:
#     hubspot_source(api_key=os.getenv("HUBSPOT_API_KEY"))
#   va write_disposition="merge" bilan incremental loading ishlatiladi.
#
# RetryPolicy:
#   max_retries=3  → 3 marta urinadi
#   delay=60       → har urinish orasida 60 soniya kutadi
#   backoff=EXPONENTIAL → 60s → 120s → 240s (serverlarni zo'riqtirmaslik uchun)
# ===========================================================================

@asset(
    group_name="ingestion",
    retry_policy=RetryPolicy(
        max_retries=3,
        delay=60,
        backoff=Backoff.EXPONENTIAL,
    ),
    description="HubSpot, Stripe, Zendesk, Internal — barcha xom ma'lumotlarni DuckDB raw_data'ga yuklaydi.",
)
def ingestion_dlt(context: AssetExecutionContext):
    context.log.info("▶ 1/4 — dlt ingestion boshlandi...")
    context.log.info("  Manbalar: HubSpot | Stripe | Zendesk | Internal DB")
    run_ingestion()
    context.log.info("✅ dlt ingestion muvaffaqiyatli yakunlandi.")


# ===========================================================================
# LAYER 2: TRANSFORM — dbt
#
# Nima qiladi:
#   1. `dbt source freshness` — Manbalar eskirib ketmaganligini tekshiradi.
#      Agar ma'lumot 24 soatdan eski bo'lsa → xato beradi, pipeline to'xtaydi.
#      Bu "garbage in, garbage out" muammosidan himoya qiladi.
#
#   2. `dbt build --store-failures` — Barcha modellarni (staging → intermediate → marts)
#      ketma-ket quradi. Testlar o'tsa davom etadi, o'tmasa xato qaydlaydi.
#      --store-failures: test muvaffaqiyatsiz bo'lsa, xato qatorlar DuckDB'da
#      saqlanadi — debug qilish osonlashadi.
#
# MUHIM: @dbt_assets — bu Dagster'ga dbt manifest'dan barcha modellar ro'yxatini
#   o'qib, ularni alohida asset sifatida ko'rsatish imkonini beradi.
#   Dagster UI'da har bir dbt model ko'rinadi va monitoring qilinadi.
#
# deps=ingestion_dlt:
#   Dagster grafida ingestion → dbt bog'lanishini rasmiy tasdiqlaydi.
#   Bu ingestion tugamasdan dbt HECH QACHON boshlanmasligini kafolatlaydi.
# ===========================================================================

@dbt_assets(
    manifest=DBT_PROJECT_DIR / "target" / "manifest.json",
    # dagster_dbt v0.29+ dan boshlab select= parametri bilan
    # faqat kerakli modellarni tanlash mumkin (optimizatsiya uchun)
)
def revops_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    """dbt: raw_data → staging → intermediate → marts. Source freshness + build + tests."""

    context.log.info("▶ 2/4 — dbt source freshness tekshirilmoqda...")

    # Birinchi navbatda manba ma'lumotlari eskirmaganligini tekshiramiz.
    # Agar manba konfiguratsiyasida warn_after/error_after belgilangan bo'lsa,
    # bu buyruq ularni baholaydi va muammo bo'lsa xato qaytaradi.
    yield from dbt.cli(["source", "freshness"], context=context).stream()

    context.log.info("✅ Freshness OK. dbt build boshlandi...")

    # --store-failures: test xatolari raw_data.dbt_test__audit jadvaliga yoziladi.
    # Bu production'da juda muhim — xato qatorlarni ko'rish va tuzatish mumkin bo'ladi.
    yield from dbt.cli(["build", "--store-failures"], context=context).stream()

    context.log.info("✅ dbt build muvaffaqiyatli yakunlandi.")


# ===========================================================================
# LAYER 3: SYNC — MotherDuck Cloud
#
# Nima qiladi:
#   Mahalliy DuckDB'dagi barcha schema'larni (raw_data, main_staging, main_marts)
#   MotherDuck Cloud omboriga SQL ATTACH + CREATE OR REPLACE yordamida ko'chiradi.
#
# Nima uchun bu usul (ATTACH pattern)?
#   dlt → MotherDuck to'g'ridan-to'g'ri ulanishda ba'zan timeout bo'ladi.
#   ATTACH usuli esa DuckDB'ning o'z protokolini ishlatadi — tez va ishonchli.
#   Python xotirasida hech narsa yuklanmaydi (memory-efficient).
#
# deps=[revops_dbt_assets]:
#   dbt barcha modellarni qurmasdan MotherDuck'ga yuborilmaydi.
#   Chala ma'lumot Cloud'ga tushmasligi kafolatlanadi.
# ===========================================================================

@asset(
    group_name="sync",
    deps=[revops_dbt_assets],
    retry_policy=RetryPolicy(
        max_retries=2,
        delay=30,
        backoff=Backoff.EXPONENTIAL,
    ),
    description="Local DuckDB → MotherDuck Cloud. ATTACH + CREATE OR REPLACE usuli bilan.",
)
def motherduck_sync(context: AssetExecutionContext):
    context.log.info("▶ 3/4 — MotherDuck sinxronizatsiyasi boshlandi...")

    # MOTHERDUCK_REQUIRED=true bo'lsa, ulanish muvaffaqiyatsiz bo'lganda
    # pipeline xato beradi. false bo'lsa — ogohlantirish bilan o'tib ketadi.
    # Bu local ishlab chiqishda qulay: token bo'lmasa ham pipeline ishlayveradi.
    context.log.info(
        f"  MOTHERDUCK_REQUIRED={os.getenv('MOTHERDUCK_REQUIRED', 'false')}"
    )
    run_motherduck_sync()
    context.log.info("✅ MotherDuck sinxronizatsiyasi yakunlandi.")


# ===========================================================================
# LAYER 4: REVERSE ETL — HubSpot CRM'ga qaytarish
#
# Nima qiladi:
#   DuckDB mart qatlamidagi tahliliy natijalarni HubSpot CRM'ga yuboradi:
#     - Company enrichment: MRR, ARR, health_status, segment → HubSpot Companies
#     - PQL signals: intent_tier, recommended_action → HubSpot Contacts
#     - L2A associations: kontaktlarni kompaniyalarga bog'laydi
#
# Bu "RevOps loop"ning yakunlanish nuqtasi:
#   Ma'lumot API'dan keladi → qayta ishlanadi → Sales'ning CRM'ida paydo bo'ladi.
#   Sales hech narsa qilmaydi — ma'lumot o'zi yangilanib turadi.
#
# Nima uchun motherduck_sync'dan keyin?
#   Reverse ETL mahalliy DuckDB'dan o'qiydi. motherduck_sync'dan keyin
#   qo'yilgani uchun: agar sync muvaffaqiyatsiz bo'lsa, biz CRM'ga
#   eskirgan ma'lumot yubormagan bo'lamiz. (ushbu loyihada zaruriy emas,
#   lekin real production'da bu tartib muhim)
# ===========================================================================

@asset(
    group_name="reverse_etl",
    deps=[motherduck_sync],
    retry_policy=RetryPolicy(
        max_retries=3,
        delay=60,
        backoff=Backoff.EXPONENTIAL,
    ),
    description="DuckDB marts → HubSpot CRM. Company enrichment + PQL signals + L2A associations.",
)
def dlt_reverse_etl(context: AssetExecutionContext):
    context.log.info("▶ 4/4 — Reverse ETL (DuckDB → HubSpot) boshlandi...")

    hubspot_token = os.getenv("HUBSPOT_ACCESS_TOKEN", "")
    if not hubspot_token or "xxxx" in hubspot_token:
        context.log.warning(
            "⚠️  HUBSPOT_ACCESS_TOKEN o'rnatilmagan yoki placeholder. "
            "Reverse ETL o'tkazib yuborildi. "
            "Production'da Dagster Cloud Env Vars'ga real token qo'shing."
        )
        return

    run_reverse_etl_sync()
    context.log.info("✅ Reverse ETL muvaffaqiyatli yakunlandi.")


# ===========================================================================
# JOBS — Dagster'da "Job" bu: bir guruh asset'larni ishga tushirish buyrug'i.
#
# revops_full_pipeline_job:
#   AssetSelection.all() → barcha 4 ta asset'ni qaramlik grafiga ko'ra ishlatadi.
#   Dagster o'zi: ingestion → dbt → sync → reverse_etl tartibini tushunadi.
#   Bu eng ishonchli usul: yangi asset qo'shilsa, job'ni o'zgartirish shart emas.
#
# revops_ingestion_only_job:
#   Faqat ingestion'ni alohida ishga tushirish uchun (debug yoki qo'lda yuklash).
#   Masalan: API ishlamay qoldi, faqat ma'lumot tortib olish kerak bo'ldi.
#
# revops_transform_only_job:
#   Ingestion'siz faqat dbt + sync'ni ishlatish uchun.
#   Masalan: ma'lumot allaqachon bor, lekin dbt model o'zgardi.
# ===========================================================================

revops_full_pipeline_job = define_asset_job(
    name="revops_full_pipeline_job",
    # AssetSelection.all() — barcha asset'lar + ularning qaramliklari
    # tartibini Dagster o'zi hal qiladi. Qo'lda tartib belgilash shart emas.
    selection=AssetSelection.all(),
    description="To'liq ELT zanjiri: Ingestion → dbt → MotherDuck → HubSpot Reverse ETL",
)

revops_ingestion_only_job = define_asset_job(
    name="revops_ingestion_only_job",
    selection=AssetSelection.assets(ingestion_dlt),
    description="Faqat dlt ingestion. Debug yoki qo'lda ma'lumot yuklash uchun.",
)

revops_transform_only_job = define_asset_job(
    name="revops_transform_only_job",
    selection=AssetSelection.assets(revops_dbt_assets, motherduck_sync),
    description="Ingestion'siz: dbt build + MotherDuck sync. Model o'zgarganda ishlatiladi.",
)


# ===========================================================================
# SCHEDULES — Avtomatik ishga tushirish jadvali
#
# cron_schedule="0 7 * * *" → Har kuni soat 07:00 UTC (12:00 Toshkent vaqti)
# Nima uchun 07:00 UTC?
#   - Bu vaqtda Yevropa va AQSH birlashadi (Yevropa ish kuni boshlaydi,
#     AQSH kechasi API limit yangilanadi)
#   - Sales jamoasi Toshkentda ish boshlashidan oldin ma'lumot tayyor bo'ladi
#
# execution_timezone="UTC": Dagster Cloud barcha joyda bir xil UTC ishlatadi.
# Timezone muammolari (DST, yozgi vaqt) bo'lmasligi uchun.
# ===========================================================================

revops_daily_schedule = ScheduleDefinition(
    name="revops_daily_07_utc",
    job=revops_full_pipeline_job,
    cron_schedule="0 7 * * *",
    execution_timezone="UTC",
)


# ===========================================================================
# DEFINITIONS — Dagster'ga loyiha tarkibini e'lon qilish
#
# Bu Dagster'ning "ro'yxat sahifasi" — barcha asset, job, schedule va
# resource'lar shu yerda ro'yxatga olinadi.
#
# DbtCliResource:
#   project_dir: dbt loyiha papkasi (bu fayl bilan bir joyda)
#   dbt_executable: shutil.which() — qaysi muhitda bo'lsa ham dbt'ni topadi
#     • Local  → .venv/bin/dbt (agar topilmasa, fallback qiladi)
#     • Docker → /usr/local/bin/dbt (requirements.txt orqali o'rnatiladi)
#     • Cloud  → PATH'dagi dbt
#
# Secrets (tokenlar) haqida:
#   Local: .env fayli orqali os.getenv() bilan o'qiladi
#   Dagster Cloud: Deployment Settings → Environment Variables bo'limida
#   saqlanadi va avtomatik tarzda os.getenv() orqali o'qiladi.
#   Hech qachon kodni ichiga token yozmang!
# ===========================================================================

defs = Definitions(
    assets=[
        ingestion_dlt,
        revops_dbt_assets,
        motherduck_sync,
        dlt_reverse_etl,
    ],
    jobs=[
        revops_full_pipeline_job,
        revops_ingestion_only_job,
        revops_transform_only_job,
    ],
    schedules=[
        revops_daily_schedule,
    ],
    resources={
        "dbt": DbtCliResource(
            project_dir=os.fspath(DBT_PROJECT_DIR),
            dbt_executable=_dbt_executable,
        ),
    },
)
