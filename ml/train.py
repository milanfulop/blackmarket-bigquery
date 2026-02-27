"""
train.py
Trains and compares:
  - Decision Tree
  - Random Forest (with different tree counts)
  - Logistic Regression

Uses mart_vendor_features from BigQuery.
Caches data locally as CSV so BigQuery is only hit once.
75% training / 25% validation split.

Usage:
  python train.py            <- loads from cache if exists, BQ otherwise
  python train.py --refresh  <- force re-fetch from BQ
"""

from google.cloud import bigquery
import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score
)
from sklearn.preprocessing import StandardScaler
import pickle
import os
import sys
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
PROJECT_ID    = "blackmarket-488113"
TABLE         = f"{PROJECT_ID}.ml.vendor_features"
CACHE_PATH    = "./cache/vendor_features_cache.csv"
MODEL_PATH    = "./model.pkl"
FORCE_REFRESH = "--refresh" in sys.argv

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
LABEL = "is_exit_scammer"

# ─────────────────────────────────────────────────────────────────────────────
# 1. LOAD DATA (local cache or BigQuery)
# ─────────────────────────────────────────────────────────────────────────────
os.makedirs("./cache", exist_ok=True)

if not FORCE_REFRESH and os.path.exists(CACHE_PATH):
    print(f"Loading data from local cache ({CACHE_PATH})...")
    print("  (run with --refresh to re-fetch from BigQuery)")
    df = pd.read_csv(CACHE_PATH)
else:
    print("Loading data from BigQuery...")
    client = bigquery.Client(project=PROJECT_ID)
    df = client.query(f"SELECT * FROM `{TABLE}`").to_dataframe()
    df.to_csv(CACHE_PATH, index=False)
    print(f"  Cached locally to {CACHE_PATH}")

print(f"  {len(df):,} vendors loaded")
print(f"  Exit scammers: {df[LABEL].sum():,} ({df[LABEL].mean()*100:.1f}%)\n")

# ─────────────────────────────────────────────────────────────────────────────
# 2. PREPARE
# ─────────────────────────────────────────────────────────────────────────────
df = df.dropna(subset=FEATURES + [LABEL])
print(f"  After dropping nulls: {len(df):,} vendors\n")

X = df[FEATURES]
y = df[LABEL]

X_train, X_val, y_train, y_val = train_test_split(
    X, y,
    test_size=0.25,
    random_state=42,
    stratify=y
)
print(f"Training set:   {len(X_train):,} vendors")
print(f"Validation set: {len(X_val):,} vendors\n")

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_val_scaled   = scaler.transform(X_val)

# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────
def evaluate(name, model, X_t, y_t, X_v, y_v):
    model.fit(X_t, y_t)
    preds = model.predict(X_v)
    proba = model.predict_proba(X_v)[:, 1] if hasattr(model, "predict_proba") else None

    print(f"{'─'*60}")
    print(f"  {name}")
    print(f"{'─'*60}")
    print(classification_report(y_v, preds, target_names=["legit", "scammer"]))

    if proba is not None:
        auc = roc_auc_score(y_v, proba)
        print(f"  ROC-AUC: {auc:.4f}")

    cm = confusion_matrix(y_v, preds)
    print(f"  Confusion matrix:")
    print(f"    TN={cm[0,0]}  FP={cm[0,1]}")
    print(f"    FN={cm[1,0]}  TP={cm[1,1]}")
    print()

    return model

# ─────────────────────────────────────────────────────────────────────────────
# 3. DECISION TREE
# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════")
print("  DECISION TREE")
print("══════════════════════════════════════════\n")

dt = evaluate(
    "Decision Tree (max_depth=5)",
    DecisionTreeClassifier(class_weight="balanced", max_depth=5, random_state=42),
    X_train, y_train, X_val, y_val
)

# ─────────────────────────────────────────────────────────────────────────────
# 4. RANDOM FOREST — different tree counts
# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════")
print("  RANDOM FOREST (varying n_estimators)")
print("══════════════════════════════════════════\n")

best_rf      = None
best_rf_auc  = 0
best_rf_name = ""

for n_trees in [10, 50, 100, 200]:
    rf = RandomForestClassifier(
        class_weight="balanced",
        n_estimators=n_trees,
        max_depth=10,
        random_state=42,
        n_jobs=-1
    )
    rf = evaluate(
        f"Random Forest (n_estimators={n_trees})",
        rf, X_train, y_train, X_val, y_val
    )
    auc = roc_auc_score(y_val, rf.predict_proba(X_val)[:, 1])
    if auc > best_rf_auc:
        best_rf_auc  = auc
        best_rf      = rf
        best_rf_name = f"Random Forest (n_estimators={n_trees})"

print(f"  Best Random Forest: {best_rf_name} — AUC {best_rf_auc:.4f}\n")

# ─────────────────────────────────────────────────────────────────────────────
# 5. LOGISTIC REGRESSION
# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════")
print("  LOGISTIC REGRESSION")
print("══════════════════════════════════════════\n")

lr = evaluate(
    "Logistic Regression",
    LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42),
    X_train_scaled, y_train, X_val_scaled, y_val
)

# ─────────────────────────────────────────────────────────────────────────────
# 6. XGBOOST
# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════")
print("  XGBOOST")
print("══════════════════════════════════════════\n")

from xgboost import XGBClassifier

scale = len(y_train[y_train==0]) / len(y_train[y_train==1])

xgb = evaluate(
    "XGBoost",
    XGBClassifier(
        scale_pos_weight=scale,
        n_estimators=100,
        max_depth=5,
        random_state=42,
        verbosity=0
    ),
    X_train, y_train, X_val, y_val
)# ─────────────────────────────────────────────────────────────────────────────
# 6. XGBOOST
# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════")
print("  XGBOOST")
print("══════════════════════════════════════════\n")

from xgboost import XGBClassifier

scale = len(y_train[y_train==0]) / len(y_train[y_train==1])

xgb = evaluate(
    "XGBoost",
    XGBClassifier(
        scale_pos_weight=scale,
        n_estimators=100,
        max_depth=5,
        random_state=42,
        verbosity=0
    ),
    X_train, y_train, X_val, y_val
)# ─────────────────────────────────────────────────────────────────────────────
# 6. XGBOOST
# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════")
print("  XGBOOST")
print("══════════════════════════════════════════\n")

from xgboost import XGBClassifier

scale = len(y_train[y_train==0]) / len(y_train[y_train==1])

xgb = evaluate(
    "XGBoost",
    XGBClassifier(
        scale_pos_weight=scale,
        n_estimators=100,
        max_depth=5,
        random_state=42,
        verbosity=0
    ),
    X_train, y_train, X_val, y_val
)# ─────────────────────────────────────────────────────────────────────────────
# 6. XGBOOST
# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════")
print("  XGBOOST")
print("══════════════════════════════════════════\n")

from xgboost import XGBClassifier

scale = len(y_train[y_train==0]) / len(y_train[y_train==1])

xgb = evaluate(
    "XGBoost",
    XGBClassifier(
        scale_pos_weight=scale,
        n_estimators=100,
        max_depth=5,
        random_state=42,
        verbosity=0
    ),
    X_train, y_train, X_val, y_val
)

xgb_auc = roc_auc_score(y_val, xgb.predict_proba(X_val)[:, 1])
if xgb_auc > best_rf_auc:
    best_rf      = xgb
    best_rf_auc  = xgb_auc
    best_rf_name = "XGBoost"

# ─────────────────────────────────────────────────────────────────────────────
# 7. FEATURE IMPORTANCE (best random forest)
# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════")
print("  FEATURE IMPORTANCE (Best Random Forest)")
print("══════════════════════════════════════════\n")

importances = pd.Series(best_rf.feature_importances_, index=FEATURES)
importances = importances.sort_values(ascending=False)

for feat, score in importances.items():
    bar = "█" * int(score * 50)
    print(f"  {feat:<35} {score:.4f}  {bar}")

# ─────────────────────────────────────────────────────────────────────────────
# 8. SAVE BEST MODEL
# ─────────────────────────────────────────────────────────────────────────────
print(f"\nSaving best model to {MODEL_PATH}...")
with open(MODEL_PATH, "wb") as f:
    pickle.dump({"model": best_rf, "scaler": scaler, "features": FEATURES}, f)
print("  Done.")