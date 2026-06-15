# Olist Customer Retention Analysis

### Why 97% of customers never return, what drives it, and what recovering them is worth

A full-stack data analytics project on the Olist Brazilian e-commerce dataset (Kaggle / olistbr). It answers one C-suite question: why do almost all customers buy exactly once, and what is the revenue opportunity if even a fraction come back?

## Headline numbers

| Metric | Value |
|---|---|
| Unique customers analysed | 93.350 |
| One-time buyers (bought once, never returned) | **97,0%** |
| Repeat buyers | 3,0% (2.801 customers) |
| Total payment revenue (2016 to 2018) | R$ 15.421.083 |
| Average order value | R$ 159,86 |
| Late delivery rate | 6,8% |
| Review score, late orders | 2,30 stars |
| Review score, on-time orders | 4,27 stars |
| ML model ROC-AUC | 0,61 |

> **The business case:** moving the repeat rate from 3% to 6%, still far below any e-commerce benchmark, is a modelled opportunity of **+R$ 498.000 in incremental revenue** at an assumed retention cost of R$ 40 per customer (net ROI: +R$ 386.000). It is a sizing estimate to scope the retention spend, not a booked result, and every assumption is shown.

## Business problem

Olist runs as a customer-acquisition engine with no retention flywheel. Every real spent attracting a customer buys one order, and then the customer disappears. The platform has:

- No structural loyalty programme
- No post-purchase re-engagement workflow
- Delivery failures in North and Northeast Brazil that destroy satisfaction and repeat intent

The most valuable question the data can answer: which factors predict whether a customer returns, and which levers does Olist control?

## Repository structure

```
olist_pipeline.py        Python pipeline: cleaning, EDA, feature engineering, ML, ROI, export
requirements.txt         Python dependencies
data/
  olist_powerbi_export.csv     96.470 rows x 24 columns, locale-safe, ML probability included
  feature_importance.csv       Ranked Random Forest feature importances
output/
  olist_executive_report.html  3-page A4 print-ready executive report with ROI model
  olist_executive_workbook.xlsx  Multi-tab Excel report (consulting style)
  olist_retention_dashboard.pbix  Power BI dashboard (3 pages)
screenshots/             Dashboard preview images
README.md
.gitignore
```

## Skills demonstrated

| Area | Detail |
|---|---|
| Data cleaning | Explicit treatment of missing values, outliers, and scope decisions |
| EDA | Revenue trends, geographic distribution, delivery analysis |
| Feature engineering | 17 features across delivery, payment, product, and geographic signals |
| Machine learning | Random Forest classifier with class-imbalance handling |
| Business framing | ROI scenario model and executive recommendations with quantified impact |
| BI dashboarding | Power BI (3 pages, DAX, slicers, scatter plots, choropleth map) |
| Excel reporting | Consulting-style multi-tab workbook with formulas |
| Python | pandas, scikit-learn, numpy |

## How to run the pipeline

```bash
pip install -r requirements.txt
```

Download the 9 CSV files from [Kaggle, Olist dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) and place them in the same folder as `olist_pipeline.py`, then:

```bash
python olist_pipeline.py
```

The script writes `olist_powerbi_export.csv` and `feature_importance.csv` into the `data/` subfolder.

> **Locale note:** the export uses a period (.) as the decimal separator. On a Dutch-locale Windows machine, import into Power BI or Excel with the locale set to English (United States) for the numeric columns so decimals are read correctly.

## Key findings

### 1. The retention crisis
97% of customers place exactly one order and never return. The platform has no mechanism, no loyalty programme, no re-engagement email, no personalisation, to bring buyers back. Every marketing spend is a one-shot event.

### 2. Late delivery destroys satisfaction
6,8% of delivered orders arrived after the estimated date. Late orders average **2,30 stars** versus **4,27 stars** for on-time orders, a 1,97-star gap that directly suppresses repeat intent.

Worst-affected states, all in the North and Northeast:
- Alagoas (AL): 21,4% late, 24,0-day average delivery (397 orders)
- Maranhão (MA): 17,4% late, 21,1-day average delivery (717 orders)
- Ceará (CE): 13,8% late, 20,8-day average delivery (1.279 orders)

### 3. What predicts return (ML findings)
The Random Forest model (AUC 0,61) ranks the strongest predictors of repeat purchase:

| Rank | Feature | Importance | Business meaning |
|---|---|---|---|
| 1 | Total order value | 0,117 | Higher spenders are more engaged buyers |
| 2 | Average item price | 0,117 | Premium product buyers show more loyalty |
| 3 | Freight ratio | 0,115 | A low freight-to-value ratio signals better perceived value |
| 4 | Product category | 0,103 | Category drives repeat behaviour (Health & Beauty vs Telephony) |
| 5 | Product revenue | 0,103 | Larger baskets correlate with higher repeat likelihood |
| 6 | Payment installments | 0,098 | Instalment users are higher-commitment buyers |

> **On the AUC:** 0,61 is modest, and deliberately reported as such. Repeat purchase is genuinely hard to predict from a single first order, where the dataset carries almost no behavioural history. The model earns its place by ranking levers and customer segments, not by making high-stakes individual predictions. A higher headline AUC here would more likely signal target leakage than real skill.

### Model critique and path to production

What the model does well: it separates the first-order signals that actually move repeat behaviour (spend level, freight ratio, category) from the ones that do not (review score ranks 10th of 17), and it does so on a held-out test set with class weights set to counter the 97:3 imbalance. That is enough to prioritise retention spend by segment.

Where it falls short, and what a production version would change:

- **Class imbalance.** `class_weight="balanced"` reweights the loss but does not create signal. At a 3% positive rate, precision on the repeat class stays low. A production model would test resampling (SMOTE or undersampling), calibrate probabilities, and pick a decision threshold from the cost of a wasted retention contact rather than the default 0,5.
- **No temporal validation.** The split is random, so a customer's first order can land in train while the platform's later months leak into test. The honest setup trains on orders up to a cutoff date and tests on orders after it, which is how the model would actually run.
- **Leakage risk to watch.** Order-level value and freight are known at first purchase, so they are fair game. Any feature that summarises a customer's full history would leak the target and must stay out until per-customer time windows are built.
- **Thin behavioural history.** The single biggest lift would come from features the raw data does not carry: time since first order, email open and click activity, browse sessions. Repeat prediction is a behavioural problem, and the first order alone is a weak proxy for it.

### 4. Revenue concentration
- São Paulo drives 42% of all orders
- Top 3 categories (Health & Beauty, Watches & Gifts, Bed/Bath) account for 26% of product revenue
- Office Furniture, a high-ticket category, carries the lowest satisfaction of any major category at 3,63 stars

## ROI scenario model

| Target repeat rate | Extra repeat customers | Incremental revenue | Retention cost (R$ 40/cust) | Net ROI |
|---|---|---|---|---|
| Current: 3% | Baseline | n/a | n/a | n/a |
| 4% | +933 | +R$ 166.131 | R$ 37.320 | +R$ 128.811 |
| **6% (target)** | **+2.800** | **+R$ 498.571** | **R$ 112.000** | **+R$ 386.571** |
| 8% | +4.667 | +R$ 831.010 | R$ 186.680 | +R$ 644.330 |
| 10% | +6.534 | +R$ 1.163.450 | R$ 261.360 | +R$ 902.090 |

**Assumptions:** average order value R$ 159,86 (from data), average 2,11 orders per repeat customer (from data), retention cost R$ 40 per customer (assumed; replace with actual CPA). Incremental revenue = extra customers x R$ 159,86 x (2,11 − 1).

## Power BI dashboard

Three pages, built from `data/olist_powerbi_export.csv`:

### Page 1, Executive Overview
![Executive Overview Dashboard](screenshots/dashboard_overview.png)
KPI cards, monthly revenue trend, top 10 categories by revenue, choropleth map by state.

### Page 2, Delivery Performance
![Delivery Performance Dashboard](screenshots/dashboard_delivery.png)
Late rate vs delivery days per state, review-score comparison, delivery trend by month.

### Page 3, ML Insights and ROI
![ML Insights Dashboard](screenshots/dashboard_ml.png)
Repeat-probability distribution, ROI scenario slider (what-if parameter), repeat rate by category.

## Data quality log

Every treatment decision is documented, because the first interview question is "how did you calculate this".

| Issue | Rows affected | Treatment | Rationale |
|---|---|---|---|
| Non-delivered orders | 2.971 | Excluded from retention analysis | A customer cannot decide to return before receiving the order (99.441 total orders minus 96.470 delivered) |
| Missing review scores | 1.932 | Imputed as 3,0 (neutral) | Non-responses are neither the best nor worst experiences |
| Missing delivery dates | 8 | Excluded from the ML model only | Both timestamps absent, not imputable |
| Freight ratio outliers | ~1% of orders | Capped at the 99th percentile | Extreme ratios from near-zero product prices would dominate the model |
| customer_unique_id | All | Used instead of customer_id | customer_id changes per order (privacy anonymisation) |

## Methodology notes

- **Retention denominator:** all unique `customer_unique_id` values with at least one fully delivered order (93.350 customers).
- **Revenue definition:** sum of `payment_value` (product price plus freight). Product-only revenue is R$ 13,2M, matching the Excel report.
- **Repeat buyer:** a `customer_unique_id` appearing in 2 or more distinct delivered orders.
- **Number format:** Dutch locale, a period (.) separates thousands and a comma (,) marks the decimal (for example R$ 159,86 and R$ 15.421.083).
- **Consistency:** every figure is computed from raw data. The pipeline, README, executive report, and dashboard reconcile to the same numbers.

## Dataset

**Brazilian E-Commerce Public Dataset by Olist.**
Source: [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). License: CC BY-NC-SA 4.0.
9 CSV files, 99.441 orders, September 2016 to October 2018.

## About

**Ying Zhao**, BI &amp; Data Analyst for commercial and supply-chain teams. Antwerp on-site, Belgium remote.

Eight years on the commercial side (a EUR 2M client book at 95% retention) before I built the analytics, so I read data the way an owner reads a P&L: start from the decision, then build the SQL and the model that move it.

Tools: Python (pandas, scikit-learn), SQL, Power BI, Excel, Git.

- Portfolio: [ying-data.github.io/portfolio](https://ying-data.github.io/portfolio/)
- LinkedIn: [weiying-zhao](https://www.linkedin.com/in/weiying-zhao/)
- Email: [weiying.data@gmail.com](mailto:weiying.data@gmail.com)
