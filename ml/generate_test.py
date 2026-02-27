"""
generate_vendor_features.py
Generates a realistic vendor features CSV for testing predict.py.
Follows the same business rules as the shadowmarket generator.

Usage:
  python generate_vendor_features.py
  python generate_vendor_features.py --vendors 500 --output ./ml/test_vendors.csv
  python generate_vendor_features.py --no-label   <- omits is_exit_scammer (for predict.py)
"""

import csv
import random
import argparse
import os

random.seed(99)

# ─────────────────────────────────────────────────────────────────────────────
# ARGS
# ─────────────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Generate vendor features CSV")
parser.add_argument("--vendors",   type=int, default=200,                    help="Number of vendors to generate")
parser.add_argument("--scam-pct",  type=float, default=0.03,                 help="Fraction of exit scammers (default 0.03)")
parser.add_argument("--output",    default="./ml/test_vendors.csv",          help="Output CSV path")
parser.add_argument("--no-label",  action="store_true",                      help="Omit is_exit_scammer column (for predict.py)")
args = parser.parse_args()

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def rand_float(lo, hi, decimals=4):
    return round(random.uniform(lo, hi), decimals)

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

# ─────────────────────────────────────────────────────────────────────────────
# GENERATE
# ─────────────────────────────────────────────────────────────────────────────
num_vendors    = args.vendors
num_scammers   = max(1, int(num_vendors * args.scam_pct))
scammer_ids    = set(random.sample(range(1, num_vendors + 1), k=num_scammers))

rows = []

for user_id in range(1, num_vendors + 1):
    is_scammer = user_id in scammer_ids

    if is_scammer:
        # ── EXIT SCAM VENDOR ─────────────────────────────────────────────
        # High incomplete orders, always crypto, many flags, dropping rating,
        # escalating risk score, many distinct IPs

        total_orders            = random.randint(20, 200)
        total_incomplete_orders = int(total_orders * rand_float(0.7, 0.95))
        pct_incomplete_orders   = round(total_incomplete_orders / total_orders, 4)
        total_revenue_usd       = rand_float(500, 50000, 2)
        avg_order_value_usd     = round(total_revenue_usd / total_orders, 2)
        pct_crypto_payments     = rand_float(0.85, 1.0)       # almost always crypto
        not_received_flag_count = random.randint(10, total_incomplete_orders)

        # reputation: started high, ended low
        early_rating  = rand_float(4.2, 5.0)
        recent_rating = rand_float(1.0, 2.5)
        avg_rating    = round((early_rating + recent_rating) / 2, 4)
        total_reviews = random.randint(5, 80)
        rating_trajectory = round(recent_rating - early_rating, 4)  # always negative

        # risk: escalated over time
        early_risk   = rand_float(0.1, 0.3)
        recent_risk  = rand_float(0.75, 1.0)
        avg_risk_score       = round((early_risk + recent_risk) / 2, 4)
        risk_score_trajectory = round(recent_risk - early_risk, 4)  # always positive

        distinct_ip_logins = random.randint(15, 60)  # many IPs = geo anomaly

    else:
        # ── LEGIT VENDOR ─────────────────────────────────────────────────
        # Low incomplete orders, mixed payments, few flags, stable rating,
        # stable risk score, few IPs

        total_orders            = random.randint(10, 500)
        total_incomplete_orders = int(total_orders * rand_float(0.02, 0.15))
        pct_incomplete_orders   = round(total_incomplete_orders / total_orders, 4)
        total_revenue_usd       = rand_float(200, 200000, 2)
        avg_order_value_usd     = round(total_revenue_usd / total_orders, 2)
        pct_crypto_payments     = rand_float(0.0, 0.35)       # mostly card/wallet
        not_received_flag_count = random.randint(0, 3)

        # reputation: stable or improving
        base_rating   = rand_float(3.5, 5.0)
        drift         = rand_float(-0.3, 0.5)
        avg_rating    = round(clamp(base_rating + drift / 2, 1.0, 5.0), 4)
        total_reviews = random.randint(0, 500)
        rating_trajectory = round(clamp(drift, -1.0, 1.0), 4)

        # risk: stable and low
        base_risk     = rand_float(0.0, 0.35)
        risk_drift    = rand_float(-0.1, 0.15)
        avg_risk_score        = round(clamp(base_risk + risk_drift / 2, 0.0, 1.0), 4)
        risk_score_trajectory = round(clamp(risk_drift, -0.5, 0.5), 4)

        distinct_ip_logins = random.randint(1, 8)  # same few IPs

    row = {
        "user_id":                user_id,
        "total_orders":           total_orders,
        "total_incomplete_orders": total_incomplete_orders,
        "pct_incomplete_orders":  pct_incomplete_orders,
        "total_revenue_usd":      total_revenue_usd,
        "avg_order_value_usd":    avg_order_value_usd,
        "pct_crypto_payments":    pct_crypto_payments,
        "not_received_flag_count": not_received_flag_count,
        "avg_rating":             avg_rating,
        "total_reviews":          total_reviews,
        "rating_trajectory":      rating_trajectory,
        "avg_risk_score":         avg_risk_score,
        "risk_score_trajectory":  risk_score_trajectory,
        "distinct_ip_logins":     distinct_ip_logins,
    }

    if not args.no_label:
        row["is_exit_scammer"] = 1 if is_scammer else 0

    rows.append(row)

# ─────────────────────────────────────────────────────────────────────────────
# WRITE CSV
# ─────────────────────────────────────────────────────────────────────────────
os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)

fieldnames = list(rows[0].keys())
with open(args.output, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {num_vendors} vendors ({num_scammers} scammers) → {args.output}")
if not args.no_label:
    print(f"Scammer IDs: {sorted(scammer_ids)}")