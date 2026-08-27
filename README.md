# Synthetic Grocery Store Dataset — Phase 1

One year of daily sales (2025-01-01 to 2025-12-31) for a general grocery /
kirana store with 20 products, generated so every hidden test case from the
problem statement is present and verifiable.

## Files

**products.csv** — product master data
| column | meaning |
|---|---|
| product_id | e.g. P01 |
| product_name | e.g. Rice 5kg |
| category | Staples / Dairy / Snacks / Beverages / Household / Produce / Personal Care |
| unit_price | normal selling price |
| base_daily_demand | *(design value, not for the model to read directly — use for validation only)* |
| weekend_factor | *(design value — use for validation only)* |
| launch_date | when the product first appears in sales.csv |

**calendar.csv** — date-level context (what a store manager would actually know in advance)
| column | meaning |
|---|---|
| date | |
| day_of_week | |
| is_weekend | 1 if Sat/Sun |
| is_salary_period | 1 if day-of-month ≤5 or ≥28 |
| event | festival/holiday name, or blank |
| weather | Normal / Rain / Hot |

**sales.csv** — the raw transactional data (this is what the prediction system ingests)
| column | meaning |
|---|---|
| date | |
| product_id | |
| units_sold | actual units sold that day (capped by stock on hand) |
| stock_available_end_of_day | shelf stock remaining after that day's sales |
| promotion_flag | 1 if product was on promotion that day |
| unit_price | actual price that day (discounted if on promotion) |

**ground_truth.csv** — the true generation parameters (baseline, multipliers, anomaly
date, launch date) per product. **For evaluating the prediction system's accuracy
afterward only — never feed this into the model itself**, since it's the "answer key."

## Hidden test cases embedded in this data

| Case | Where to find it |
|---|---|
| Festival sales spike | 12 festival/holiday dates tagged in calendar.csv; sugar (P05), namkeen (P11), chips (P09) spike hardest |
| Product was out of stock | Potato Chips (P09) forced to 0 stock, 2025-09-10 to 2025-09-13+ (stays at 0 until next restock cycle) |
| New product, little history | Herbal Face Wash (P20) launched 2025-12-06 — only 26 days of history |
| Weekend vs weekday variation | Every product has a distinct weekend_factor; Milk (P06) averages ~123/weekday vs ~161/weekend |
| Missing sales records | ~2% of (date, product) rows randomly removed from sales.csv entirely |
| One-day abnormal sales | Biscuit Pack (P10) spikes to ~434 units on 2025-06-17 (normal range ~50-90), no event tag that day |
| Promotion-related spike | Each product has 4-8 random promo days (promotion_flag=1) with its own uplift multiplier |

## Notes for Phase 2

- Zero-sales rows are a mix of **true stock-outs** (stock_available_end_of_day = 0)
  and genuinely low natural demand — Phase 2's stock-out detection logic should key
  off `stock_available_end_of_day`, not `units_sold` alone.
- Weather is included as a simple categorical signal (Rain boosts Umbrella sales,
  Hot boosts Soft Drink sales) — a lightweight stand-in for a real weather API.
- Do not use `base_daily_demand`, `weekend_factor`, or `ground_truth.csv` inside the
  prediction system — they exist only so we can later measure how close our
  calculated baseline/multipliers come to the true values used to generate the data.
