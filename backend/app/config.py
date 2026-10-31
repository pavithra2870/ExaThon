"""Settings, paths and the dataset adapter registry."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
DATA_DIR = ROOT / "data"
SQL_DIR = BACKEND_DIR / "sql"

load_dotenv(ROOT / ".env")

SCHEMA = os.environ.get("EXA_SCHEMA", "PROMOLENS").upper()
BOOTSTRAP_RESAMPLES = 200
BOOTSTRAP_SEED = 20260131
HOLDOUT_SHARE = 0.3


def exa_settings() -> dict[str, str]:
    missing = [k for k in ("EXA_DSN", "EXA_USER", "EXA_PASSWORD") if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            f"Missing {', '.join(missing)}. Copy .env.example to .env at the repo root and fill it in."
        )
    return {
        "dsn": os.environ["EXA_DSN"],
        "user": os.environ["EXA_USER"],
        "password": os.environ["EXA_PASSWORD"],
    }


# ---------------------------------------------------------------------------
# Dataset adapters. Adding a dataset = one entry here plus its raw and frame SQL.
# Every frame table <PREFIX>_FRAME has: client_id, treatment (0/1, NULL for the
# unlabelled audience), target (0/1 or NULL) and one DOUBLE column per feature.
# ---------------------------------------------------------------------------

# Default group thresholds for the four estimated groups (see README, "Method").
# u: an estimated uplift of at least 1 percentage point counts as "tipped" or "put off".
# p0_cut: an estimated chance of acting without the message of at least 50%
# counts as "would act anyway".
DEFAULT_U = 0.01
DEFAULT_P0_CUT = 0.5


@dataclass(frozen=True)
class Feature:
    name: str
    label: str
    flag: bool = False  # 0/1 indicator; explained as yes/no rather than higher/lower


@dataclass(frozen=True)
class Dataset:
    id: str
    prefix: str
    name: str
    channel: str
    treatment_label: str
    target_label: str
    outcome: str
    outcome_plural: str
    source: str
    note: str
    raw_sql: str
    frame_sql: str
    features: tuple[Feature, ...]
    u: float = DEFAULT_U
    p0_cut: float = DEFAULT_P0_CUT
    has_audience: bool = False
    limitations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def feature_names(self) -> list[str]:
        return [f.name for f in self.features]

    def feature(self, name: str) -> Feature:
        return next((f for f in self.features if f.name == name), Feature(name, name))

    def label(self, name: str) -> str:
        return self.feature(name).label


HILLSTROM = Dataset(
    id="hillstrom",
    prefix="HILL",
    name="Hillstrom email test",
    channel="Email",
    treatment_label="Received an email (men's or women's version)",
    target_label="Bought within two weeks",
    outcome="purchase",
    outcome_plural="purchases",
    source="Kevin Hillstrom, MineThatData E-Mail Analytics challenge, 2008 (US online retailer)",
    note=(
        "US email campaign from 2008, 64,000 customers. The two email versions are pooled into "
        "one treatment. Under 1% bought, so estimates are noisy. Not Indian data."
    ),
    raw_sql="01_hill_raw.sql",
    frame_sql="11_hill_frame.sql",
    features=(
        Feature("recency", "Months since last purchase"),
        Feature("history_log", "Past spend level (log)"),
        Feature("mens", "Bought men's merchandise last year", flag=True),
        Feature("womens", "Bought women's merchandise last year", flag=True),
        Feature("newbie", "New customer in the last 12 months", flag=True),
        Feature("zip_urban", "Lives in an urban area", flag=True),
        Feature("zip_rural", "Lives in a rural area", flag=True),
        Feature("channel_web", "Bought only on the web last year", flag=True),
        Feature("channel_multi", "Bought on web and phone last year", flag=True),
    ),
    limitations=(
        "Under 1% bought, so per-customer estimates are very uncertain.",
        "The two email versions are pooled, so the effect is an average of both.",
    ),
)

LENTA = Dataset(
    id="lenta",
    prefix="LENTA",
    name="Lenta SMS campaign",
    channel="SMS",
    treatment_label="Received an SMS",
    target_label="Visited a store afterwards",
    outcome="store visit",
    outcome_plural="store visits",
    source="Lenta (Russian grocery chain) uplift dataset, via scikit-uplift",
    note=(
        "Russian grocery chain, about 687,000 customers; 75% received an SMS. The outcome is a "
        "store visit, not a purchase. 30 of 193 columns are used. Not Indian data."
    ),
    raw_sql="02_lenta_raw.sql",
    frame_sql="12_lenta_frame.sql",
    features=(
        Feature("age", "Age"),
        Feature("age_missing", "Age not recorded or implausible", flag=True),
        Feature("gender_f", "Recorded as female", flag=True),
        Feature("gender_m", "Recorded as male", flag=True),
        Feature("children", "Number of children"),
        Feature("main_format", "Shops mainly in store format 1", flag=True),
        Feature("months_from_register", "Months since joining the loyalty programme"),
        Feature("response_sms", "Past response rate to SMS"),
        Feature("response_viber", "Past response rate to Viber messages"),
        Feature("food_share_15d", "Share of food in baskets, last 15 days"),
        Feature("food_share_1m", "Share of food in baskets, last month"),
        Feature("promo_share_15d", "Share of promo items, last 15 days"),
        Feature("mean_discount_depth_15d", "Average promo price depth, last 15 days"),
        Feature("stdev_discount_depth_15d", "Spread of promo price depth, last 15 days"),
        Feature("k_var_discount_depth_15d", "Variation in promo price depth, last 15 days"),
        Feature("k_var_cheque_15d", "Variation in basket size, last 15 days"),
        Feature("k_var_cheque_3m", "Variation in basket size, last 3 months"),
        Feature("k_var_cheque_category_width_15d", "Variation in categories per basket, last 15 days"),
        Feature("k_var_days_between_visits_15d", "Irregularity of visits, last 15 days"),
        Feature("k_var_days_between_visits_1m", "Irregularity of visits, last month"),
        Feature("k_var_days_between_visits_3m", "Irregularity of visits, last 3 months"),
        Feature("k_var_sku_per_cheque_15d", "Variation in items per basket, last 15 days"),
        Feature("stdev_days_between_visits_15d", "Spread of days between visits, last 15 days"),
        Feature("perdelta_days_between_visits_15_30d", "Change in visit gap, 15 vs 30 days"),
        Feature("recent15_missing", "Too few visits in the last 15 days to measure", flag=True),
        Feature("crazy_cheques_1m_log", "Unusually large baskets, last month (log)"),
        Feature("crazy_cheques_3m_log", "Unusually large baskets, last 3 months (log)"),
        Feature("crazy_cheques_12m_log", "Unusually large baskets, last 12 months (log)"),
        Feature("crazy_goods_12m_log", "Items in unusually large baskets, last 12 months (log)"),
        Feature("cheque_count_3m_g20_log", "Visits buying category group 20, last 3 months (log)"),
        Feature("cheque_count_12m_g20_log", "Visits buying category group 20, last 12 months (log)"),
        Feature("sale_count_3m_g24_log", "Units bought in category group 24, last 3 months (log)"),
        Feature("sale_count_12m_g32_log", "Units bought in category group 32, last 12 months (log)"),
    ),
    limitations=(
        "The outcome is a store visit, which is not the same as a purchase.",
        "Category groups (g20, g24, g32) are anonymised in the source data.",
    ),
)

X5 = Dataset(
    id="x5",
    prefix="X5",
    name="X5 RetailHero SMS campaign",
    channel="SMS",
    treatment_label="Received an SMS",
    target_label="Bought during the campaign",
    outcome="purchase",
    outcome_plural="purchases",
    source="X5 Retail Group, RetailHero uplift contest, 2019 (Russian grocery chain)",
    note=(
        "Russian grocery chain, 200,039 labelled customers in an SMS test, plus about 45.8 "
        "million earlier purchase lines. Features are built in Exasol from that history. "
        "Unlabelled contest customers appear only in the customer list. Not Indian data."
    ),
    raw_sql="03_x5_raw.sql",
    frame_sql="10_x5_features.sql",
    features=(
        Feature("recency_days", "Days since last purchase"),
        Feature("tx_30d_log", "Purchases in the last 30 days (log)"),
        Feature("tx_90d_log", "Purchases in the last 90 days (log)"),
        Feature("tx_180d_log", "Purchases in the last 180 days (log)"),
        Feature("tx_all_log", "Purchases, all history (log)"),
        Feature("spend_30d_log", "Spend in the last 30 days (log)"),
        Feature("spend_90d_log", "Spend in the last 90 days (log)"),
        Feature("spend_180d_log", "Spend in the last 180 days (log)"),
        Feature("spend_all_log", "Spend, all history (log)"),
        Feature("avg_basket_log", "Average basket size (log)"),
        Feature("n_stores", "Number of stores visited"),
        Feature("n_products_log", "Number of distinct products (log)"),
        Feature("n_level1", "Number of top-level categories bought"),
        Feature("own_brand_share", "Share of spend on own-brand products"),
        Feature("alcohol_share", "Share of spend on alcohol"),
        Feature("points_received_log", "Loyalty points received (log)"),
        Feature("points_spent_log", "Loyalty points spent (log)"),
        Feature("points_paid_share", "Share of spend paid with points"),
        Feature("express_share", "Share of points from express offers"),
        Feature("tenure_days", "Days since joining the loyalty programme"),
        Feature("redeemed", "Has ever redeemed points", flag=True),
        Feature("age", "Age"),
        Feature("age_missing", "Age not recorded or implausible", flag=True),
        Feature("gender_f", "Recorded as female", flag=True),
        Feature("gender_m", "Recorded as male", flag=True),
    ),
    has_audience=True,
    limitations=(
        "Purchase history comes before the campaign; exact campaign dates are not published.",
        "Unlabelled contest customers are scored for the customer list only, never evaluated.",
    ),
)

DATASETS: dict[str, Dataset] = {d.id: d for d in (HILLSTROM, LENTA, X5)}


def get_dataset(ds: str) -> Dataset:
    try:
        return DATASETS[ds]
    except KeyError:
        raise KeyError(f"Unknown dataset '{ds}'. Choose one of: {', '.join(DATASETS)}") from None
