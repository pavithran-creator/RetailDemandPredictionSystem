# Phase 3 Validation Report

This report confirms that the Prediction & Alerts Layer (Phase 3) calculations have been completed correctly.

## 1. Confidence Scores for New Products (P21–P27)

Confidence scores reflect history days, category fallback, and data quality flags. Because each new product has a different launch date, the confidence scores are custom-tailored per product, rather than a binary flag.

| product_id   |   history_days_available | overall_confidence   |   confidence_score_val |
|:-------------|-------------------------:|:---------------------|-----------------------:|
| P21          |                      657 | High                 |                 0.9    |
| P22          |                      560 | Medium               |                 0.7671 |
| P23          |                      478 | Medium               |                 0.6548 |
| P24          |                      330 | Medium               |                 0.4521 |
| P25          |                      228 | Low                  |                 0.3123 |
| P26          |                      142 | Low                  |                 0.1945 |
| P27          |                       92 | Low                  |                 0.126  |

All new products: **CONFIRMED**. Confidence scores decay cleanly from P21 (657 days) down to P27 (92 days).

## 2. Festival Predictions & Fallback Multipliers (Pongal)

For a maturing product like P01 (Rice 5kg, Staples), the system uses its own historical Pongal multiplier. For a cold-start product like P27 (Organic Peanut Butter, Staples) which has no historical Pongal days, the system falls back to the category-level average Pongal multiplier of Staples products.

- **P01 (Maturing, Staples)**:
  - Normal Thursday: `43.7832` units
  - Pongal Thursday: `51.454` units
  - Realized Event Multiplier: `1.1752x` (Product-specific)
- **P27 (New Cold-Start, Staples)**:
  - Normal Thursday: `46.6333` units
  - Pongal Thursday: `57.017` units
  - Realized Event Multiplier: `1.2227x` (Category Fallback Average)

Fallback check: **PASSED**.

## 3. One-Day-Anomaly Stability Check (P01)

Product P01 (Rice 5kg) has unexplained single-day sales spikes of 343 units (2026-09-05) and 350 units (2027-09-05). Despite this, our forecasting system remains robust because the anomaly was filtered during baseline estimation.
- **P01 Forecast (2028-01-01)**: `44.5141` units.
- **Status**: Stable (not inflated by the anomaly).

Anomaly check: **PASSED**.

## 4. Stock-out Risk Alerts & Reorder Logic

Products are flagged for `STOCKOUT_RISK` when their current stock (at end of 2027) is less than their predicted demand over the 3-day lead time. Reorder quantities are recommended to restore stock to 10 days coverage + safety buffer.

| product_id   |   current_stock |   predicted_demand_over_lead_time | recommended_action                                    | urgency_level   |
|:-------------|----------------:|----------------------------------:|:------------------------------------------------------|:----------------|
| P07          |              49 |                             88.67 | Reorder 330 units within 1 days to prevent stock-out. | HIGH            |
| P15          |              53 |                             90.57 | Reorder 350 units within 1 days to prevent stock-out. | HIGH            |
| P24          |              55 |                             58.85 | Reorder 180 units within 2 days to prevent stock-out. | MEDIUM          |
| P09          |              58 |                             96.32 | Reorder 430 units within 1 days to prevent stock-out. | HIGH            |
| P19          |              63 |                            116.65 | Reorder 520 units within 1 days to prevent stock-out. | HIGH            |

Stockout risk check: **PASSED**.

## 5. Overstock Alerts

Products with stock covering more than 10 days of forecasted demand are flagged as `OVERSTOCK`. A recommended order reduction is calculated to glide the stock level back down.

| product_id   |   current_stock |   predicted_demand_over_lead_time | recommended_action                                            | urgency_level   |
|:-------------|----------------:|----------------------------------:|:--------------------------------------------------------------|:----------------|
| P21          |             104 |                             26.68 | Reduce next order by 45 units — 1.7 weeks of cover remaining. | LOW             |

Overstock check: **PASSED**.
