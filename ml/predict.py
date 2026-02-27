"""
predict.py
Runs the trained model on new vendor data from a CSV file.
The CSV must have the same schema as mart_vendor_features
but WITHOUT the is_exit_scammer column.

Usage:
  python predict.py --input vendors.csv
  python predict.py --input vendors.csv --output results.csv
  python predict.py --input vendors.csv --threshold 0.4
"""

import pandas as pd
import pickle
import argparse
import os
import sys

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
MODEL_PATH = "./model.pkl"

FEATURES = [
    "total_orders",
    "total_incomplete_orders",
    "pct_incomplete_orders",
    "total_revenue_usd",
    "avg_order_value_usd",
    "pct_crypto_payments",
    "not_received_flag_count",
    "avg_rating",
    "total_reviews",
    "rating_trajectory",
    "avg_risk_score",
    "risk_score_trajectory",
    "distinct_ip_logins",
]

# ─────────────────────────────────────────────────────────────────────────────
# ARGS
# ─────────────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Run exit scam prediction on vendor CSV")
parser.add_argument("--input",     required=True,             help="Path to input CSV")
parser.add_argument("--output",    default="./ml/predictions.csv", help="Path to output CSV")
parser.add_argument("--threshold", type=float, default=0.5,   help="Scam probability threshold (default 0.5)")
args = parser.parse_args()

# ─────────────────────────────────────────────────────────────────────────────
# 1. LOAD MODEL
# ─────────────────────────────────────────────────────────────────────────────
if not os.path.exists(MODEL_PATH):
    print(f"No model found at {MODEL_PATH}. Run train.py first.")
    sys.exit(1)

print(f"Loading model from {MODEL_PATH}...")
with open(MODEL_PATH, "rb") as f:
    bundle = pickle.load(f)

model    = bundle["model"]
features = bundle["features"]
print("  Model loaded.\n")

# ─────────────────────────────────────────────────────────────────────────────
# 2. LOAD INPUT DATA
# ─────────────────────────────────────────────────────────────────────────────
print(f"Loading input data from {args.input}...")
df = pd.read_csv(args.input)
print(f"  {len(df):,} vendors loaded\n")

# check all required features exist
missing = [f for f in FEATURES if f not in df.columns]
if missing:
    print(f"Missing columns in input CSV: {missing}")
    sys.exit(1)

# warn if label column accidentally included
if "is_exit_scammer" in df.columns:
    print("  Warning: is_exit_scammer column found — ignoring it for prediction.\n")

# ─────────────────────────────────────────────────────────────────────────────
# 3. PREPARE
# ─────────────────────────────────────────────────────────────────────────────
X = df[FEATURES].fillna(0)  # fill nulls with 0 same as training

# ─────────────────────────────────────────────────────────────────────────────
# 4. PREDICT
# ─────────────────────────────────────────────────────────────────────────────
print(f"Running predictions (threshold = {args.threshold})...")
proba  = model.predict_proba(X)[:, 1]
labels = (proba >= args.threshold).astype(int)

# ─────────────────────────────────────────────────────────────────────────────
# 5. BUILD OUTPUT
# ─────────────────────────────────────────────────────────────────────────────
results = df.copy()
results["scam_probability"] = proba.round(4)
results["predicted_scammer"] = labels
results["risk_tier"] = pd.cut(
    proba,
    bins=[0, 0.3, 0.6, 1.0],
    labels=["low", "medium", "high"],
    include_lowest=True
)

# sort by highest risk first
results = results.sort_values("scam_probability", ascending=False)

# ─────────────────────────────────────────────────────────────────────────────
# 6. PRINT SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
flagged = labels.sum()
print(f"\n  Total vendors scored : {len(df):,}")
print(f"  Flagged as scammer   : {flagged:,} ({flagged/len(df)*100:.1f}%)")
print(f"  High risk (>0.6)     : {(proba > 0.6).sum():,}")
print(f"  Medium risk (0.3-0.6): {((proba >= 0.3) & (proba <= 0.6)).sum():,}")
print(f"  Low risk (<0.3)      : {(proba < 0.3).sum():,}")

print(f"\nTop 10 highest risk vendors:")
print(f"{'─'*60}")
top10_cols = ["user_id", "scam_probability", "risk_tier", "total_orders",
              "pct_incomplete_orders", "not_received_flag_count"]
top10_cols = [c for c in top10_cols if c in results.columns]
print(results[top10_cols].head(10).to_string(index=False))

# ─────────────────────────────────────────────────────────────────────────────
# 7. SAVE OUTPUT
# ─────────────────────────────────────────────────────────────────────────────
os.makedirs(os.path.dirname(args.output), exist_ok=True)
results.to_csv(args.output, index=False)
print(f"\nResults saved to {args.output}")