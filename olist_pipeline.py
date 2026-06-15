"""
=============================================================================
OLIST BRAZILIAN E-COMMERCE, CUSTOMER RETENTION ANALYSIS PIPELINE
=============================================================================
Author  : Ying Zhao, Data Analyst
Dataset : Olist Public E-Commerce Dataset (Kaggle / olistbr)
Period  : September 2016 to October 2018, 9 CSV files, about 100K orders
Purpose : Portfolio project demonstrating end-to-end analytical capability

BUSINESS PROBLEM
----------------
97% of Olist customers buy exactly once and never return. The platform runs
as a customer-acquisition machine with no retention engine, so every real
(R$) spent on acquisition is wasted when customers do not come back.

THE BUSINESS QUESTION THIS DATA CAN ANSWER FOR THE C-SUITE
----------------------------------------------------------
Which factors predict whether a customer returns, and what is the incremental
revenue from recovering even one percentage point of repeat rate?

DELIVERABLES PRODUCED BY THIS SCRIPT
-------------------------------------
  1. data/olist_powerbi_export.csv  : 96.470 rows, 24 columns (Power BI source)
  2. data/feature_importance.csv    : ranked ML feature importances
  The executive HTML report, Power BI dashboard, and README are delivered
  alongside this script.

LOCALE NOTE
-----------
Currency values are Brazilian Real (R$). Python writes decimals with a period
because its float representation is locale-independent. When opening the CSV
in Excel or Power BI on a Dutch-locale machine, import with the decimal set to
period so the figures are read correctly.

USAGE
-----
  python olist_pipeline.py

  Place the 9 raw Kaggle CSV files in the same folder as this script.
  Outputs are written to the data/ subfolder.

=============================================================================
"""

import os
import warnings
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, roc_auc_score, confusion_matrix
)
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 0 · CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
# DATA_DIR holds the 9 raw Kaggle CSV files (the script's own folder by default).
# OUT_DIR receives the processed exports and is created if it does not exist.
DATA_DIR  = "."
OUT_DIR   = "data"

os.makedirs(OUT_DIR, exist_ok=True)


def path(filename):
    return os.path.join(DATA_DIR, filename)


def out(filename):
    return os.path.join(OUT_DIR, filename)


print("=" * 70)
print("OLIST RETENTION ANALYSIS PIPELINE")
print("=" * 70)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 · DATA LOADING
# All 9 CSVs use semicolons as delimiters (European format).
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1/7] Loading datasets...")

orders    = pd.read_csv(path("olist_orders_dataset.csv"),            sep=";")
customers = pd.read_csv(path("olist_customers_dataset.csv"),         sep=";")
items     = pd.read_csv(path("olist_order_items_dataset.csv"),       sep=";")
payments  = pd.read_csv(path("olist_order_payments_dataset.csv"),    sep=";")
reviews   = pd.read_csv(path("olist_order_reviews_dataset.csv"),     sep=";")
products  = pd.read_csv(path("olist_products_dataset.csv"),          sep=";")
sellers   = pd.read_csv(path("olist_sellers_dataset.csv"),           sep=";")
geo       = pd.read_csv(path("olist_geolocation_dataset.csv"),       sep=";")
cat_trans = pd.read_csv(path("product_category_name_translation.csv"), sep=";")

print(f"  orders:   {orders.shape[0]:>7,} rows")
print(f"  customers:{customers.shape[0]:>7,} rows")
print(f"  items:    {items.shape[0]:>7,} rows")
print(f"  payments: {payments.shape[0]:>7,} rows")
print(f"  reviews:  {reviews.shape[0]:>7,} rows")
print(f"  products: {products.shape[0]:>7,} rows")
print(f"  sellers:  {sellers.shape[0]:>7,} rows")
print(f"  geo:      {geo.shape[0]:>7,} rows")
print(f"  cat_trans:{cat_trans.shape[0]:>7,} rows")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 · DATA CLEANING
# Every decision is documented with business rationale.
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/7] Cleaning data, documenting every decision...")

# --- 2a. Date parsing ---
# Dates are stored as strings in DD/MM/YYYY HH:MM format (European).
# dayfirst=True ensures correct parsing on any locale.
date_columns = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]
for col in date_columns:
    orders[col] = pd.to_datetime(orders[col], dayfirst=True, errors="coerce")

# --- 2b. Scope: delivered orders only ---
# METHODOLOGY NOTE: The denominator for retention rate is customers with at
# least one fully delivered order.  Orders in status 'shipped', 'processing',
# 'invoiced', 'approved', or 'cancelled' are excluded because:
#   - A customer cannot decide to return before their order arrives.
#   - Including undelivered orders would inflate the denominator and
#     artificially depress the apparent repeat rate.
# Cancelled orders (625 rows) are excluded for the same reason.
all_statuses = orders["order_status"].value_counts()
print(f"  Order status breakdown:")
for status, count in all_statuses.items():
    print(f"    {status:<20} {count:>6,}")

delivered = orders[orders["order_status"] == "delivered"].copy()
print(f"\n  Keeping 'delivered' orders only: {len(delivered):,} "
      f"({len(delivered)/len(orders)*100:.1f}% of total)")

# --- 2c. Delivery time metrics ---
delivered["delivery_days"] = (
    delivered["order_delivered_customer_date"] -
    delivered["order_purchase_timestamp"]
).dt.days

delivered["days_vs_estimate"] = (
    delivered["order_delivered_customer_date"] -
    delivered["order_estimated_delivery_date"]
).dt.days

# is_late: positive days_vs_estimate means delivered after estimated date
delivered["is_late"] = (delivered["days_vs_estimate"] > 0).astype(int)

# DATA QUALITY FLAG: 8 rows have NaT for delivery date, both order and
# delivery timestamps are missing.  These rows cannot contribute delivery
# metrics and are excluded from the model (not from EDA counts).
missing_delivery = delivered["delivery_days"].isna().sum()
print(f"\n  DATA QUALITY: {missing_delivery} rows missing delivery date "
      f"(both timestamps absent, not imputable, excluded from model only)")

# DATA QUALITY FLAG: 0 negative delivery days (sanity check passed)
neg_delivery = (delivered["delivery_days"] < 0).sum()
print(f"  DATA QUALITY: {neg_delivery} rows with negative delivery days "
      f"(sanity check {'PASSED' if neg_delivery == 0 else 'FAILED'})")

# --- 2d. Payments aggregation ---
# Some orders have multiple payment rows (split payments, installments).
# We aggregate to one row per order.
# payment_installments: take max (reflects the highest installment plan used)
# payment_value: sum (total amount paid across all payment methods)
payments["payment_value"] = pd.to_numeric(payments["payment_value"], errors="coerce")
pay_agg = payments.groupby("order_id").agg(
    total_payment     = ("payment_value",       "sum"),
    payment_installments = ("payment_installments", "max"),
    n_payment_types   = ("payment_type",        "nunique"),
    used_credit_card  = ("payment_type", lambda x: int("credit_card" in x.values)),
    used_boleto       = ("payment_type", lambda x: int("boleto" in x.values)),
    used_voucher      = ("payment_type", lambda x: int("voucher" in x.values)),
).reset_index()

# --- 2e. Items aggregation ---
items["price"]         = pd.to_numeric(items["price"],         errors="coerce")
items["freight_value"] = pd.to_numeric(items["freight_value"], errors="coerce")

items_agg = items.groupby("order_id").agg(
    n_items            = ("order_item_id",  "count"),
    product_revenue    = ("price",          "sum"),
    freight_value      = ("freight_value",  "sum"),
    n_unique_sellers   = ("seller_id",      "nunique"),
    avg_price          = ("price",          "mean"),
).reset_index()

# freight_ratio = freight / product revenue.  Add 0.01 to denominator to
# avoid division by zero on theoretical R$0 orders (none exist in data,
# but defensive coding is visible to reviewers).
items_agg["freight_ratio"] = (
    items_agg["freight_value"] / (items_agg["product_revenue"] + 0.01)
)

# --- 2f. Review aggregation ---
# 1,932 orders have no review (customer did not respond to review request).
# TREATMENT: impute review_score = 3.0 (neutral).
# RATIONALE: Missing reviews are neither the best nor worst experiences;
# a neutral score avoids biasing the model in either direction.
# The flag column 'has_comment' separately captures whether text was left.
reviews["review_score"] = pd.to_numeric(reviews["review_score"], errors="coerce")
rev_agg = reviews.groupby("order_id").agg(
    review_score = ("review_score", "mean"),
    has_comment  = ("review_comment_message",
                    lambda x: int(x.notna().any())),
).reset_index()

missing_reviews = delivered["order_id"].shape[0] - delivered["order_id"].isin(
    rev_agg["order_id"]).sum()
print(f"  DATA QUALITY: {missing_reviews:,} orders have no review "
      f"(imputed as 3.0, neutral)")

# --- 2g. Product category (top-value item per order) ---
items_cat = (
    items
    .merge(products[["product_id", "product_category_name"]], on="product_id", how="left")
    .merge(cat_trans, on="product_category_name", how="left")
)
top_cat = (
    items_cat
    .sort_values("price", ascending=False)
    .groupby("order_id")
    .first()[["product_category_name_english"]]
    .reset_index()
)
top_cat.columns = ["order_id", "top_category"]

# --- 2h. Seller state ---
seller_state = (
    items
    .merge(sellers[["seller_id", "seller_state"]], on="seller_id", how="left")
    .groupby("order_id")["seller_state"]
    .first()
    .reset_index()
)

# --- 2i. Master frame ---
df = (
    delivered
    .merge(customers[["customer_id", "customer_unique_id",
                       "customer_state", "customer_city"]], on="customer_id", how="left")
    .merge(pay_agg,      on="order_id", how="left")
    .merge(items_agg,    on="order_id", how="left")
    .merge(rev_agg,      on="order_id", how="left")
    .merge(top_cat,      on="order_id", how="left")
    .merge(seller_state, on="order_id", how="left")
)

print(f"\n  Master frame: {df.shape[0]:,} rows × {df.shape[1]} columns")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 · TARGET VARIABLE
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/7] Defining target variable: is_repeat_buyer...")

# METHODOLOGY: Repeat buyer = customer_unique_id appears in 2+ delivered orders.
# customer_unique_id (not customer_id) is used because the dataset documentation
# states that customer_id changes per order (anonymous per-transaction ID),
# while customer_unique_id is the true customer-level identifier.
# Denominator = all unique customer_unique_id values with ≥1 delivered order.

purchase_counts = df.groupby("customer_unique_id")["order_id"].count()
total_unique_customers = len(purchase_counts)
repeat_set = set(purchase_counts[purchase_counts >= 2].index)

df["is_repeat_buyer"] = df["customer_unique_id"].isin(repeat_set).astype(int)

one_time  = (purchase_counts == 1).sum()
repeat_n  = len(repeat_set)
repeat_pct = repeat_n / total_unique_customers * 100

print(f"  Total unique customers (denominator): {total_unique_customers:,}")
print(f"  One-time buyers: {one_time:,}  ({one_time/total_unique_customers*100:.1f}%)")
print(f"  Repeat buyers:   {repeat_n:,}  ({repeat_pct:.1f}%)")
print()
print(f"  *** HEADLINE FINDING: {one_time/total_unique_customers*100:.0f}% of customers never return ***")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 · EXPLORATORY DATA ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────
print("\n[4/7] Exploratory Data Analysis...")

# -- Revenue
total_rev         = df["total_payment"].sum()
avg_order_value   = df["total_payment"].mean()
median_order_val  = df["total_payment"].median()
print(f"  Total payment revenue:    R$ {total_rev:>15,.2f}")
print(f"  Avg order value:          R$ {avg_order_value:>15,.2f}")
print(f"  Median order value:       R$ {median_order_val:>15,.2f}")

# -- Delivery
avg_delivery_days = df["delivery_days"].mean()
late_rate         = df["is_late"].mean()
print(f"  Avg delivery days:        {avg_delivery_days:.1f}")
print(f"  Late delivery rate:       {late_rate*100:.1f}%")

# -- Review scores split by late/on-time
late_rev_score    = df[df["is_late"] == 1]["review_score"].mean()
ontime_rev_score  = df[df["is_late"] == 0]["review_score"].mean()
print(f"  Avg review, late orders:    {late_rev_score:.2f} stars")
print(f"  Avg review, on-time orders: {ontime_rev_score:.2f} stars")
print(f"  Late delivery review gap: {ontime_rev_score:.2f} on-time vs "
      f"{late_rev_score:.2f} late = {ontime_rev_score - late_rev_score:.2f} stars")

# -- Top 5 categories by revenue
df_cat_rev = (
    df.groupby("top_category")["product_revenue"]
    .sum()
    .sort_values(ascending=False)
    .head(5)
)
print(f"\n  Top 5 categories by revenue:")
for cat, rev in df_cat_rev.items():
    print(f"    {cat:<35} R$ {rev:>10,.0f}")

# -- Geography: top 5 states by order volume
top_states = df["customer_state"].value_counts().head(5)
print(f"\n  Top 5 states by orders:")
for state, cnt in top_states.items():
    print(f"    {state}: {cnt:,} orders ({cnt/len(df)*100:.1f}%)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 · MACHINE LEARNING  ·  Predict Repeat Purchase
# ─────────────────────────────────────────────────────────────────────────────
print("\n[5/7] Machine Learning: Random Forest classifier...")
print("  Target: is_repeat_buyer (1 = returned for a 2nd+ order)")
print("  Class imbalance handled via class_weight='balanced'")

# -- Prepare features
df_model = df[df["delivery_days"].notna()].copy()
df_model["review_score"]   = df_model["review_score"].fillna(3.0)
df_model["has_comment"]    = df_model["has_comment"].fillna(0)

# Cap freight_ratio at 99th percentile, extreme outliers from near-zero
# product prices cause ratio > 100, which would dominate the model.
p99 = df_model["freight_ratio"].quantile(0.99)
df_model["freight_ratio_capped"] = df_model["freight_ratio"].clip(upper=p99)

# Label-encode categoricals
le_cat  = LabelEncoder()
le_cst  = LabelEncoder()
le_sel  = LabelEncoder()
df_model["top_category_enc"]     = le_cat.fit_transform(df_model["top_category"].fillna("unknown"))
df_model["customer_state_enc"]   = le_cst.fit_transform(df_model["customer_state"].fillna("unknown"))
df_model["seller_state_enc"]     = le_sel.fit_transform(df_model["seller_state"].fillna("unknown"))

FEATURES = [
    "delivery_days",
    "days_vs_estimate",
    "is_late",
    "review_score",
    "has_comment",
    "total_payment",
    "payment_installments",
    "n_payment_types",
    "used_credit_card",
    "used_boleto",
    "n_items",
    "product_revenue",
    "freight_ratio_capped",
    "avg_price",
    "top_category_enc",
    "customer_state_enc",
    "seller_state_enc",
]

X = df_model[FEATURES].fillna(0)
y = df_model["is_repeat_buyer"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42, stratify=y
)
print(f"  Train: {len(X_train):,} rows  |  Test: {len(X_test):,} rows")

rf = RandomForestClassifier(
    n_estimators=200,
    max_depth=10,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,
)
rf.fit(X_train, y_train)

y_prob = rf.predict_proba(X_test)[:, 1]
y_pred = rf.predict(X_test)
auc    = roc_auc_score(y_test, y_prob)

print(f"\n  ROC-AUC: {auc:.4f}")
print(f"\n  Classification report:")
print(classification_report(y_test, y_pred, target_names=["One-time", "Repeat"]))

# -- Feature importances
fi = (
    pd.DataFrame({"feature": FEATURES, "importance": rf.feature_importances_})
    .sort_values("importance", ascending=False)
    .reset_index(drop=True)
)
print("  Top 10 predictive features:")
for _, row in fi.head(10).iterrows():
    bar = "█" * int(row["importance"] * 100)
    print(f"    {row['feature']:<30} {row['importance']:.4f}  {bar}")

fi.to_csv(out("feature_importance.csv"), index=False)
print(f"\n  Saved: data/feature_importance.csv")

# -- Attach predicted probability back to model frame
df_model["repeat_purchase_probability"] = rf.predict_proba(X)[:, 1]
df_model["churn_risk_tier"] = pd.cut(
    1 - df_model["repeat_purchase_probability"],
    bins=[0, 0.60, 0.80, 1.0],
    labels=["Low Risk", "Medium Risk", "High Risk"],
)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 · ROI SCENARIO MODEL
# ─────────────────────────────────────────────────────────────────────────────
print("\n[6/7] ROI scenario model...")
print("  Assumptions:")
print(f"    Avg order value:            R$ {avg_order_value:.2f}  (from actual data)")
print(f"    Avg orders per repeat cust: {purchase_counts[purchase_counts>=2].mean():.2f}  (from actual data)")
print(f"    Cost-per-acquisition:       R$ 40.00  (assumption, adjust in Excel)")
print()
print("  SCENARIO TABLE")
print(f"  {'Target Rate':>12}  {'Extra Repeat Custs':>20}  "
      f"{'Additional Revenue':>20}  {'Retention Cost':>16}  {'Net ROI':>14}")
print("  " + "-" * 90)

avg_orders_repeat = purchase_counts[purchase_counts >= 2].mean()
cpa               = 40.0   # R$ cost per acquired returning customer (assumption)

for target_rate in [0.04, 0.05, 0.06, 0.08, 0.10]:
    extra_cust = int((target_rate - repeat_pct / 100) * total_unique_customers)
    if extra_cust < 0:
        continue
    extra_rev    = extra_cust * avg_order_value * (avg_orders_repeat - 1)
    ret_cost     = extra_cust * cpa
    net_roi      = extra_rev - ret_cost
    print(f"  {target_rate*100:>11.0f}%  {extra_cust:>20,}  "
          f"R$ {extra_rev:>17,.0f}  R$ {ret_cost:>13,.0f}  R$ {net_roi:>11,.0f}")

print()
print("  NOTE: CPA of R$40 is an assumption. Replace in Excel model.")
print("  NOTE: 'Additional Revenue' = extra_customers × avg_order_value × (extra_orders)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7 · EXPORT POWER BI CSV
# ─────────────────────────────────────────────────────────────────────────────
print("\n[7/7] Exporting Power BI CSV...")

# 24 columns, matching data/olist_powerbi_export.csv exactly.
pbi_cols = [
    "order_id", "customer_id", "customer_unique_id", "customer_state",
    "order_purchase_timestamp", "order_delivered_customer_date",
    "order_estimated_delivery_date",
    "delivery_days", "days_vs_estimate", "is_late",
    "review_score", "has_comment",
    "total_payment", "payment_installments", "used_credit_card", "used_boleto",
    "n_items", "product_revenue", "freight_value", "freight_ratio_capped",
    "top_category", "seller_state",
    "is_repeat_buyer", "repeat_purchase_probability",
]

# Only df_model has the ML probability column; merge back
ml_cols = df_model[["order_id", "repeat_purchase_probability", "churn_risk_tier"]].copy()
pbi_df  = df.merge(ml_cols, on="order_id", how="left")

# For orders excluded from model (8 missing delivery dates), set probability to NaN
pbi_out = pbi_df[pbi_cols].copy()

# Format timestamps as plain dates for Power BI compatibility
pbi_out["order_purchase_timestamp"]       = pd.to_datetime(
    pbi_out["order_purchase_timestamp"]).dt.strftime("%Y-%m-%d")
pbi_out["order_delivered_customer_date"]  = pd.to_datetime(
    pbi_out["order_delivered_customer_date"], errors="coerce").dt.strftime("%Y-%m-%d")
pbi_out["order_estimated_delivery_date"]  = pd.to_datetime(
    pbi_out["order_estimated_delivery_date"], errors="coerce").dt.strftime("%Y-%m-%d")

pbi_out.to_csv(out("olist_powerbi_export.csv"), index=False)

print(f"  Saved: data/olist_powerbi_export.csv  ({len(pbi_out):,} rows, {len(pbi_cols)} columns)")
print()
print("  POWER BI IMPORT NOTE:")
print("  When importing this CSV on a Dutch-locale Windows machine:")
print("  1. In Power BI: Home > Get Data > Text/CSV")
print("  2. In the preview dialog, click 'Transform Data'")
print("  3. Select all numeric columns > Transform > Data Type >")
print("     'Using Locale...' then choose 'English (United States)'")
print("  4. This prevents Dutch Power Query from interpreting '.' as")
print("     a thousands separator instead of a decimal separator.")


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 70)
print("PIPELINE COMPLETE: KEY FIGURES (use these in all deliverables)")
print("=" * 70)
print(f"  Total delivered orders:   {len(df):>10,}")
print(f"  Total unique customers:   {total_unique_customers:>10,}")
print(f"  One-time buyers:          {one_time:>10,}  ({one_time/total_unique_customers*100:.1f}%)")
print(f"  Repeat buyers:            {repeat_n:>10,}  ({repeat_pct:.1f}%)")
print(f"  Total payment revenue:    R$ {total_rev:>12,.2f}")
print(f"  Avg order value:          R$ {avg_order_value:>12,.2f}")
print(f"  Avg delivery days:        {avg_delivery_days:>10.1f}")
print(f"  Late delivery rate:       {late_rate*100:>10.1f}%")
print(f"  Avg review score:         {df['review_score'].mean():>10.2f} stars")
print(f"  ML ROC-AUC:               {auc:>10.4f}")
print()
print("  Output files written:")
print("    - data/olist_powerbi_export.csv")
print("    - data/feature_importance.csv")
print("=" * 70)
