"""
Synthetic Grocery Store Sales Dataset Generator
=================================================
Generates a realistic 1-year daily sales dataset for a general grocery /
kirana store, deliberately engineered so every "hidden test case" from the
problem statement is present and verifiable:

  1. Festival sales spike        -> festival event tags + per-product multipliers
  2. Product was out of stock    -> stock_available cap creates true 0-sales days
  3. New product, little history -> Product P20 launches 25 days before dataset end
  4. Weekend vs weekday variation-> built into every product's weekday factor
  5. Missing sales records       -> ~2% of (date, product) rows are dropped
  6. One-day abnormal sales      -> unexplained single-day spike, no event tag
  7. Promotion-related spike     -> random promo days per product with uplift

Outputs (CSV):
  products.csv   - product master data
  calendar.csv   - date-level context (weekday, weekend, salary period, event, weather)
  sales.csv      - the raw transactional data (what the prediction system ingests)
  ground_truth.csv - the TRUE generation parameters per product (for later evaluation only,
                      not to be used by the prediction system itself)
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta

rng = np.random.default_rng(42)

# ----------------------------------------------------------------------
# 1. Date range: one full year
# ----------------------------------------------------------------------
START = date(2025, 1, 1)
END = date(2025, 12, 31)
all_dates = pd.date_range(START, END, freq="D")
n_days = len(all_dates)

# ----------------------------------------------------------------------
# 2. Products master data (general grocery / kirana store)
#    base_daily_demand = TRUE average units/day on a normal weekday
#    weekend_factor    = TRUE multiplier on Sat/Sun
# ----------------------------------------------------------------------
products = [
    # product_id, name,                 category,        price,  base_daily_demand, weekend_factor
    ("P01", "Rice 5kg",                 "Staples",        320,   18,  1.15),
    ("P02", "Wheat Flour 5kg",          "Staples",        250,   15,  1.10),
    ("P03", "Sunflower Oil 1L",         "Staples",        180,   22,  1.20),
    ("P04", "Toor Dal 1kg",             "Staples",        140,   12,  1.10),
    ("P05", "Sugar 1kg",                "Staples",         50,   20,  1.15),
    ("P06", "Milk 500ml",               "Dairy",           28,   65,  1.30),
    ("P07", "Curd 400g",                "Dairy",           35,   40,  1.35),
    ("P08", "Paneer 200g",              "Dairy",           70,   14,  1.45),
    ("P09", "Potato Chips 52g",         "Snacks",          20,   45,  1.60),
    ("P10", "Biscuit Pack",             "Snacks",          30,   38,  1.40),
    ("P11", "Namkeen 200g",             "Snacks",          45,   25,  1.55),
    ("P12", "Soft Drink 750ml",         "Beverages",       45,   30,  1.70),
    ("P13", "Tea Powder 250g",          "Beverages",      120,   16,  1.10),
    ("P14", "Instant Coffee 100g",      "Beverages",      150,    9,  1.15),
    ("P15", "Detergent Powder 1kg",     "Household",      110,   11,  1.05),
    ("P16", "Dish Wash Bar",            "Household",       15,   28,  1.05),
    ("P17", "Tomato 1kg",               "Produce",          30,   35,  1.25),
    ("P18", "Onion 1kg",                "Produce",          35,   33,  1.20),
    ("P19", "Umbrella",                 "Household",       250,    3,  1.10),
    ("P20", "Herbal Face Wash",         "Personal Care",    99,   10,  1.15),  # NEW PRODUCT
]
products_df = pd.DataFrame(
    products,
    columns=["product_id", "product_name", "category", "unit_price",
             "base_daily_demand", "weekend_factor"],
)

# P20 is a brand-new product: only launched 25 days before the dataset ends
NEW_PRODUCT_ID = "P20"
NEW_PRODUCT_LAUNCH = END - timedelta(days=25)

launch_dates = {pid: START for pid in products_df.product_id}
launch_dates[NEW_PRODUCT_ID] = NEW_PRODUCT_LAUNCH
products_df["launch_date"] = products_df.product_id.map(launch_dates)

# ----------------------------------------------------------------------
# 3. Calendar: weekday/weekend, salary period, festivals/holidays, weather
# ----------------------------------------------------------------------
# Festivals relevant to a Tamil Nadu / general Indian retail calendar (fictionalized
# dates kept close to real 2025 occasions for realism)
festivals = {
    date(2025, 1, 14): "Pongal",
    date(2025, 1, 15): "Pongal",
    date(2025, 3, 14): "Holi",
    date(2025, 4, 14): "Tamil New Year",
    date(2025, 8, 27): "Local Trade Fair",       # local event example
    date(2025, 10, 20): "Diwali",
    date(2025, 10, 21): "Diwali",
    date(2025, 12, 25): "Christmas",
    date(2025, 12, 31): "New Year Eve",
}
holidays = {
    date(2025, 1, 26): "Republic Day",
    date(2025, 8, 15): "Independence Day",
    date(2025, 10, 2): "Gandhi Jayanti",
}

promo_uplift_products = {  # products that respond strongly to promotions
    "P09": 2.2, "P10": 2.0, "P12": 2.3, "P11": 1.9, "P03": 1.6,
}
festival_uplift_products = {  # products that spike hard during festivals
    "P05": 3.0, "P03": 2.6, "P11": 3.2, "P09": 2.8, "P08": 2.4, "P06": 1.8,
    "P01": 1.6, "P04": 1.7,
}
weather_sensitive_products = {  # rain days
    "P19": ("Rain", 6.0),   # umbrellas spike hard on rainy days
    "P12": ("Hot", 1.6),    # cold drinks spike on hot days
}

cal_rows = []
for d in all_dates:
    dd = d.date()
    dow = d.strftime("%A")
    is_weekend = dow in ("Saturday", "Sunday")
    day_of_month = dd.day
    salary_period = (day_of_month <= 5) or (day_of_month >= 28)
    event = festivals.get(dd) or holidays.get(dd) or None
    # simple weather simulation: ~8% rain days, ~15% hot days, rest normal
    w_roll = rng.random()
    if w_roll < 0.08:
        weather = "Rain"
    elif w_roll < 0.23:
        weather = "Hot"
    else:
        weather = "Normal"
    cal_rows.append([dd, dow, int(is_weekend), int(salary_period), event, weather])

calendar_df = pd.DataFrame(
    cal_rows, columns=["date", "day_of_week", "is_weekend", "is_salary_period", "event", "weather"]
)

# ----------------------------------------------------------------------
# 4. Promotions: each product gets a handful of random promo days
# ----------------------------------------------------------------------
promo_days = {}  # product_id -> set of dates on promo
for pid in products_df.product_id:
    n_promos = rng.integers(4, 9)
    days = rng.choice(n_days, size=n_promos, replace=False)
    promo_days[pid] = set(all_dates[days].date)

# ----------------------------------------------------------------------
# 5. One unexplained single-day abnormal spike (pure noise, no event tag)
#    e.g. a bus tour randomly stops and buys a ton of biscuits
# ----------------------------------------------------------------------
ANOMALY_PRODUCT = "P10"
ANOMALY_DATE = date(2025, 6, 17)  # an ordinary Tuesday, no festival/promo
ANOMALY_MULTIPLIER = 7.0

# Guaranteed, clean stock-out stretch (so the hidden test case is unambiguous):
# Potato Chips (P09) sells out and stays out for 4 straight days after a supplier delay
FORCED_STOCKOUT_PRODUCT = "P09"
FORCED_STOCKOUT_START = date(2025, 9, 10)
FORCED_STOCKOUT_END = date(2025, 9, 13)

# ----------------------------------------------------------------------
# 6. Generate daily sales per product
# ----------------------------------------------------------------------
sales_rows = []
cal_lookup = calendar_df.set_index("date")

for _, prod in products_df.iterrows():
    pid = prod.product_id
    base = prod.base_daily_demand
    wk_factor = prod.weekend_factor
    launch = prod.launch_date
    # running "stock" simulation
    stock = int(base * 16)  # start with ~16 days of buffer stock
    restock_cycle = rng.integers(4, 7)  # days between restocks
    days_since_restock = 0

    for d in all_dates:
        dd = d.date()
        if dd < launch:
            continue  # product doesn't exist yet

        cal = cal_lookup.loc[dd]
        demand = base

        # weekend effect
        if cal.is_weekend:
            demand *= wk_factor

        # salary period effect (modest uplift store-wide)
        if cal.is_salary_period:
            demand *= 1.12

        # festival / holiday effect
        if cal.event is not None:
            mult = festival_uplift_products.get(pid, 1.4)  # default mild uplift
            demand *= mult

        # weather effect
        if pid in weather_sensitive_products:
            trigger_weather, w_mult = weather_sensitive_products[pid]
            if cal.weather == trigger_weather:
                demand *= w_mult

        # promotion effect
        on_promo = dd in promo_days[pid]
        if on_promo:
            demand *= promo_uplift_products.get(pid, 1.5)

        # unexplained one-day anomaly (noise, not a real pattern)
        if pid == ANOMALY_PRODUCT and dd == ANOMALY_DATE:
            demand *= ANOMALY_MULTIPLIER

        # natural day-to-day random noise (+/- ~15%)
        demand *= rng.normal(1.0, 0.15)
        demand = max(0, demand)

        true_demand = int(round(demand))

        # --- restock simulation: periodically top up stock ---
        days_since_restock += 1
        if days_since_restock >= restock_cycle:
            stock += int(base * rng.integers(10, 16))
            days_since_restock = 0

        # forced supplier-delay stock-out window for the demo product
        if pid == FORCED_STOCKOUT_PRODUCT and FORCED_STOCKOUT_START <= dd <= FORCED_STOCKOUT_END:
            stock = 0

        # units actually sold is capped by available stock -> creates real stock-outs
        units_sold = min(true_demand, stock)
        stock -= units_sold

        price_today = prod.unit_price * (0.85 if on_promo else 1.0)

        sales_rows.append([
            dd, pid, units_sold, stock, int(on_promo), round(price_today, 2)
        ])

sales_df = pd.DataFrame(
    sales_rows,
    columns=["date", "product_id", "units_sold", "stock_available_end_of_day",
             "promotion_flag", "unit_price"],
)

# ----------------------------------------------------------------------
# 7. Missing sales records: randomly drop ~2% of rows (store failed to log)
# ----------------------------------------------------------------------
drop_frac = 0.02
n_drop = int(len(sales_df) * drop_frac)
drop_idx = rng.choice(sales_df.index, size=n_drop, replace=False)
sales_df = sales_df.drop(index=drop_idx).reset_index(drop=True)
sales_df = sales_df.sort_values(["product_id", "date"]).reset_index(drop=True)

# ----------------------------------------------------------------------
# 8. Ground truth reference (for evaluating the prediction system later —
#    NOT to be fed into the prediction model itself)
# ----------------------------------------------------------------------
ground_truth = products_df[["product_id", "product_name", "base_daily_demand", "weekend_factor"]].copy()
ground_truth["festival_multiplier"] = ground_truth.product_id.map(festival_uplift_products).fillna(1.4)
ground_truth["promo_multiplier"] = ground_truth.product_id.map(promo_uplift_products).fillna(1.5)
ground_truth["anomaly_date"] = ground_truth.product_id.apply(lambda p: ANOMALY_DATE if p == ANOMALY_PRODUCT else None)
ground_truth["launch_date"] = ground_truth.product_id.map(launch_dates)

# ----------------------------------------------------------------------
# 9. Save all outputs
# ----------------------------------------------------------------------
out_dir = "/home/claude/dataset"
products_df.to_csv(f"{out_dir}/products.csv", index=False)
calendar_df.to_csv(f"{out_dir}/calendar.csv", index=False)
sales_df.to_csv(f"{out_dir}/sales.csv", index=False)
ground_truth.to_csv(f"{out_dir}/ground_truth.csv", index=False)

# ----------------------------------------------------------------------
# 10. Quick summary printout
# ----------------------------------------------------------------------
print(f"Date range: {START} to {END}  ({n_days} days)")
print(f"Products: {len(products_df)}  (new product: {NEW_PRODUCT_ID}, launched {NEW_PRODUCT_LAUNCH})")
print(f"Sales rows generated: {len(sales_df)}  (after dropping {n_drop} rows as missing records)")
print(f"Festivals/holidays tagged: {len(festivals) + len(holidays)}")
print(f"Anomaly: product {ANOMALY_PRODUCT} on {ANOMALY_DATE}, x{ANOMALY_MULTIPLIER} unexplained spike")
print(f"Forced stock-out: product {FORCED_STOCKOUT_PRODUCT} from {FORCED_STOCKOUT_START} to {FORCED_STOCKOUT_END}")

stockout_days = sales_df[sales_df.units_sold == 0].shape[0]
print(f"Zero-sale rows (possible stock-outs or true zero demand): {stockout_days}")

print("\nSample rows from sales.csv:")
print(sales_df.head(8).to_string(index=False))

print("\nProducts:")
print(products_df.to_string(index=False))
