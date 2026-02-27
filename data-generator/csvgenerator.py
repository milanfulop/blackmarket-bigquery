"""
shadowmarket_generator.py  –  causal signals edition
Same as fixed edition but exit scam vendors now have
DETERMINISTIC fraud signals so the ML model can actually learn.

CAUSAL FIXES FOR EXIT SCAM VENDORS:
  1. Risk scores always escalate over time (low → high)
  2. Reputation always drops in latest snapshot (high → low)
  3. Orders always get buyer_claimed_not_received fraud flag
  4. Payments always use crypto
  5. Sessions use many distinct IPs (geo anomaly)
"""

import csv
import os
import random
import shutil
from datetime import datetime, timedelta

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

random.seed(42)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
num_users      = int(input("Total users (e.g. 100000): ")        or "100000")
pct_vendors    = float(input("Percent vendors (0-100, e.g. 20): ") or "20")
num_categories = int(input("Categories (e.g. 12): ")             or "12")
num_listings   = int(input("Listings (e.g. 400000): ")           or "400000")
num_orders     = int(input("Orders (e.g. 8000000): ")            or "8000000")
_num_reviews   = int(input("Reviews approx (e.g. 5000000): ")    or "5000000")
OUT_DIR        = input("Output directory: ").strip() or "out_shadowmarket"

os.makedirs(OUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# FAST HELPERS
# ─────────────────────────────────────────────────────────────────────────────
_EPOCH = datetime(2022, 1, 1)
_NOW   = datetime.now()

def rand_dt(start: datetime = _EPOCH, end: datetime = _NOW) -> datetime:
    delta = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, max(1, delta)))

def rand_dt_iso(start: datetime = _EPOCH, end: datetime = _NOW) -> str:
    return rand_dt(start, end).isoformat()

def fast_uid(prefix: str = "") -> str:
    return prefix + os.urandom(6).hex()

def dt_or_empty(dt):
    return dt.isoformat() if dt else ""

# ─────────────────────────────────────────────────────────────────────────────
# PRE-BUILT POOLS
# ─────────────────────────────────────────────────────────────────────────────
print("Building random pools...")

POOL = 5_000

_WORDS = [
    "Alpha","Beta","Gamma","Delta","Echo","Foxtrot","Ghost","Helix","Indigo",
    "Jade","Krypto","Lunar","Mirage","Nova","Onyx","Pulse","Quartz","Raven",
    "Shadow","Titan","Ultra","Vortex","Wraith","Xenon","Yield","Zephyr",
    "Amber","Blaze","Cipher","Dusk","Ember","Flare","Glitch","Haze","Iron",
    "Jinx","Knell","Lotus","Mystic","Neon","Orbit","Prism","Quiet","Ridge",
    "Storm","Talon","Umbra","Vapor","Wisp","Xero","Yarn","Zinc",
]

def _rand_sentence(n):
    return " ".join(random.choice(_WORDS) for _ in range(n)) + "."

POOL_SENTENCES_SHORT = [_rand_sentence(4)  for _ in range(POOL)]
POOL_SENTENCES_LONG  = [_rand_sentence(12) for _ in range(POOL)]
POOL_REVIEW_TEXT     = [_rand_sentence(random.randint(5, 20)) for _ in range(POOL)]
POOL_USERNAMES = [f"user_{random.randint(10000,9999999)}" for _ in range(POOL)]
POOL_EMAILS    = [
    f"u{random.randint(10000,9999999)}@{random.choice(_WORDS).lower()}.{''.join(random.choices('abcdefghijklmnopqrstuvwxyz',k=3))}"
    for _ in range(POOL)
]

# FIX: two separate IP pools
# legit vendors use a small pool (same IPs over time)
# exit scam vendors use a huge pool (many distinct IPs = geo anomaly)
POOL_IPS_LEGIT = [
    f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
    for _ in range(500)
]
POOL_IPS_SCAM = [
    f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
    for _ in range(5_000)
]

POOL_COUNTRIES = [
    "United States","Germany","Netherlands","United Kingdom","Australia",
    "Canada","France","Sweden","Brazil","Japan","Singapore","South Korea",
    "Mexico","Spain","Poland","Ukraine","India","China","Argentina","Nigeria",
    "Switzerland","Austria","Denmark","Norway","Finland","Czech Republic",
    "Belgium","Portugal","Romania","Hungary",
]
POOL_WORDS = [w.title() for w in _WORDS]

def _expand(weights_list, n=10_000):
    total = sum(w for _, w in weights_list)
    out = []
    for item, w in weights_list:
        out.extend([item] * max(1, round(w / total * n)))
    return out

_STATUS_POOL      = _expand([("active",0.85),("suspended",0.10),("banned",0.05)])
_CURRENCY_POOL    = _expand([("USD",0.85),("BTC",0.07),("ETH",0.08)])
_DEVICE_POOL      = _expand([("mobile",0.6),("desktop",0.35),("tablet",0.05)])
_PAY_METHOD_POOL  = _expand([("card",0.6),("crypto",0.25),("wallet",0.15)])
_LISTING_ST_POOL  = _expand([("active",0.8),("paused",0.1),("removed",0.1)])
_FLAG_REASON_POOL = _expand([("buyer_claimed_not_received",0.5),("chargeback",0.2),
                              ("suspicious_payment",0.2),("policy_violation",0.1)])
_SESSION_CNT_POOL = _expand([(0,0.2),(1,0.4),(2,0.2),(3,0.15),(5,0.05)])
_RATING_POOL      = _expand([(5,0.45),(4,0.25),(3,0.15),(2,0.1),(1,0.05)])

# ─────────────────────────────────────────────────────────────────────────────
# StreamCSV
# ─────────────────────────────────────────────────────────────────────────────
class StreamCSV:
    def __init__(self, name, fieldnames, bufsize=1 << 20):
        self.path = os.path.join(OUT_DIR, name)
        self._f   = open(self.path, "w", newline="", encoding="utf-8", buffering=bufsize)
        self._w   = csv.DictWriter(self._f, fieldnames=fieldnames)
        self._w.writeheader()
        self.count = 0

    def write(self, row):
        self._w.writerow(row)
        self.count += 1

    def close(self):
        self._f.close()
        print(f"  ok  {self.count:>12,} rows  -> {os.path.basename(self.path)}")

    def __enter__(self):  return self
    def __exit__(self, *_): self.close()

# ─────────────────────────────────────────────────────────────────────────────
# 1) USERS
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] Users...")
num_vendors = max(1, int(num_users * pct_vendors / 100))
six_mo_ago  = _NOW - timedelta(days=180)

users      = []
vendor_ids = set()

for i in range(1, num_users + 1):
    if len(vendor_ids) < num_vendors:
        role = "vendor" if random.random() < 0.9 else "dual"
        vendor_ids.add(i)
    elif random.random() < 0.05:
        role = "dual"
    else:
        role = "buyer"
    users.append({
        "user_id":    i,
        "username":   random.choice(POOL_USERNAMES),
        "email":      random.choice(POOL_EMAILS),
        "role":       role,
        "created_at": rand_dt_iso(_EPOCH, six_mo_ago),
        "status":     random.choice(_STATUS_POOL),
    })

vendor_list = [u["user_id"] for u in users if u["role"] in ("vendor","dual")]
buyer_list  = [u["user_id"] for u in users if u["role"] in ("buyer","dual")]

num_exit_scams    = max(1, int(len(vendor_list) * 0.03))
exit_scam_vendors = set(random.sample(vendor_list, k=num_exit_scams))
num_bots          = max(1, int(len(buyer_list)  * 0.03))
bot_buyers        = set(random.sample(buyer_list, k=num_bots))

for u in users:
    if u["user_id"] in exit_scam_vendors:
        u["status"] = "banned"

with StreamCSV("users.csv", ["user_id","username","email","role","created_at","status"]) as f:
    for u in users:
        f.write(u)

# ─────────────────────────────────────────────────────────────────────────────
# 2) SESSIONS
# FIX: exit scam vendors use huge IP pool = many distinct IPs
# ─────────────────────────────────────────────────────────────────────────────
print("[2] Sessions...")
with StreamCSV("user_sessions.csv",
               ["session_id","user_id","ip_address","device_type","login_at","logout_at"]) as f:
    sess_id = 1
    for u in users:
        u_created = datetime.fromisoformat(u["created_at"])
        is_scammer = u["user_id"] in exit_scam_vendors

        # scam vendors have more sessions and from more IPs
        session_count = (
            random.randint(10, 30) if is_scammer
            else random.choice(_SESSION_CNT_POOL)
        )
        ip_pool = POOL_IPS_SCAM if is_scammer else POOL_IPS_LEGIT

        for _ in range(session_count):
            login  = rand_dt(u_created, _NOW)
            logout = login + timedelta(minutes=random.randint(1, 180))
            f.write({
                "session_id":  sess_id,
                "user_id":     u["user_id"],
                "ip_address":  random.choice(ip_pool),
                "device_type": random.choice(_DEVICE_POOL),
                "login_at":    login.isoformat(),
                "logout_at":   logout.isoformat(),
            })
            sess_id += 1

# ─────────────────────────────────────────────────────────────────────────────
# 3) CATEGORIES
# ─────────────────────────────────────────────────────────────────────────────
print("[3] Categories...")
categories = [{"category_id": i, "name": random.choice(POOL_WORDS), "parent_category_id": ""}
              for i in range(1, num_categories + 1)]
for c in random.sample(categories, k=max(0, min(3, len(categories) // 3))):
    opts = [x for x in categories if x["category_id"] != c["category_id"]]
    if opts:
        random.choice(opts)["parent_category_id"] = c["category_id"]
cat_ids = [c["category_id"] for c in categories]

with StreamCSV("categories.csv", ["category_id","name","parent_category_id"]) as f:
    for c in categories:
        f.write(c)

# ─────────────────────────────────────────────────────────────────────────────
# 4) LISTINGS
# ─────────────────────────────────────────────────────────────────────────────
print("[4] Listings...")
listing_pool = []

with StreamCSV("listings.csv",
               ["listing_id","vendor_id","category_id","title","description",
                "base_price","currency","stock_quantity","created_at","status"]) as f:
    for lid in range(1, num_listings + 1):
        if lid % 100_000 == 0:
            print(f"  {lid:>10,} / {num_listings:,}", flush=True)
        vendor     = random.choice(vendor_list)
        base_price = round(random.uniform(5.0, 1200.0), 2)
        currency   = random.choice(_CURRENCY_POOL)
        f.write({
            "listing_id":     lid,
            "vendor_id":      vendor,
            "category_id":    random.choice(cat_ids),
            "title":          random.choice(POOL_SENTENCES_SHORT),
            "description":    random.choice(POOL_SENTENCES_LONG),
            "base_price":     base_price,
            "currency":       currency,
            "stock_quantity": random.randint(0, 200),
            "created_at":     rand_dt_iso(_EPOCH, _NOW),
            "status":         random.choice(_LISTING_ST_POOL),
        })
        listing_pool.append((lid, vendor, base_price, currency))

hot_listings = random.sample(listing_pool, k=max(1, int(len(listing_pool) * 0.02)))

# ─────────────────────────────────────────────────────────────────────────────
# 5) WALLETS
# ─────────────────────────────────────────────────────────────────────────────
print("[5] Wallets...")
wallet_id_map = {}

with StreamCSV("wallets.csv", ["wallet_id","user_id","currency","created_at"]) as wf, \
     StreamCSV("wallet_transactions.csv",
               ["transaction_id","wallet_id","order_id",
                "transaction_type","amount","created_at"]) as wtf:
    for wid, u in enumerate(users, start=1):
        currency  = random.choice(_CURRENCY_POOL)
        balance   = round(
            random.uniform(50, 20000) if u["role"] != "vendor"
            else random.uniform(0, 1000), 2)
        created_w = rand_dt_iso(datetime.fromisoformat(u["created_at"]), _NOW)
        wf.write({"wallet_id": wid, "user_id": u["user_id"],
                  "currency": currency, "created_at": created_w})
        wtf.write({"transaction_id": fast_uid("wt_"), "wallet_id": wid,
                   "order_id": "", "transaction_type": "deposit",
                   "amount": balance, "created_at": created_w})
        wallet_id_map[u["user_id"]] = wid

# ─────────────────────────────────────────────────────────────────────────────
# 6) ORDERS + everything that hangs off them
# ─────────────────────────────────────────────────────────────────────────────
print(f"[6] Orders ({num_orders:,}) – longest step...")

_review_rate = min(0.95, _num_reviews / max(1, int(num_orders * 0.48 * 0.7)))
REPORT_EVERY = max(100_000, num_orders // 20)
shipment_seq   = 1
order_item_seq = 1

with StreamCSV("orders.csv",
               ["order_id","buyer_id","vendor_id","order_status",
                "total_amount","currency","created_at","completed_at"]) as ord_f, \
     StreamCSV("order_items.csv",
               ["order_item_id","order_id","listing_id",
                "quantity","price_at_purchase"]) as oi_f, \
     StreamCSV("payments.csv",
               ["payment_id","order_id","buyer_id","amount","currency",
                "payment_method","created_at","confirmed_at"]) as pay_f, \
     StreamCSV("escrows.csv",
               ["escrow_id","order_id","held_amount",
                "release_status","held_at","released_at"]) as esc_f, \
     StreamCSV("shipments.csv",
               ["shipment_id","order_id","origin_region","destination_region",
                "estimated_delivery_days","shipped_at","delivered_at",
                "delivery_status"]) as ship_f, \
     StreamCSV("delivery_events.csv",
               ["event_id","shipment_id","event_type","event_time"]) as de_f, \
     StreamCSV("fraud_flags.csv",
               ["flag_id","entity_type","entity_id",
                "flag_reason","flagged_at","resolved_flag"]) as ff_f, \
     StreamCSV("reviews.csv",
               ["review_id","order_id","reviewer_id","reviewed_user_id",
                "rating","review_text","created_at"]) as rev_f, \
     open(os.path.join(OUT_DIR, "_wt_orders.csv"), "w",
          newline="", encoding="utf-8", buffering=1 << 20) as _wto_raw:

    _wto_fields = ["transaction_id","wallet_id","order_id",
                   "transaction_type","amount","created_at"]
    wto_w = csv.DictWriter(_wto_raw, fieldnames=_wto_fields)
    wto_w.writeheader()

    for order_id in range(1, num_orders + 1):

        if order_id % REPORT_EVERY == 0:
            print(f"  {order_id:>10,} / {num_orders:,}  "
                  f"({order_id/num_orders*100:.0f}%)", flush=True)

        buyer = random.choice(buyer_list)
        listing = (random.choice(hot_listings) if random.random() < 0.07
                   else random.choice(listing_pool))
        lid, vendor, base_price, currency = listing
        is_scammer = vendor in exit_scam_vendors

        qty   = random.choices([1,2,3], weights=[0.75,0.15,0.10])[0]
        price = round(base_price * random.uniform(0.9, 1.2), 2)
        total = round(price * qty, 2)
        created  = rand_dt(_EPOCH, _NOW)
        age_days = (_NOW - created).days

        # ── ORDER STATUS ──────────────────────────────────────────────────
        if is_scammer:
            if random.random() < 0.8:
                order_status = "pending"
                if age_days > 30 and random.random() < 0.6:
                    order_status = "cancelled"
            else:
                order_status = "disputed"
        else:
            r = random.random()
            if   r < 0.02: order_status = "cancelled"
            elif r < 0.12: order_status = "disputed"
            elif r < 0.60: order_status = "completed"
            elif r < 0.90: order_status = "shipped"
            else:          order_status = "pending"

        if order_status == "completed":
            completed_at = created + timedelta(days=random.randint(2, 30))
        elif order_status == "shipped":
            completed_at = created + timedelta(days=random.randint(1, 14))
        elif order_status == "disputed":
            completed_at = created + timedelta(days=random.randint(2, 30))
        else:
            completed_at = None

        ord_f.write({
            "order_id":      order_id,
            "buyer_id":      buyer,
            "vendor_id":     vendor,
            "order_status":  order_status,
            "total_amount":  total,
            "currency":      currency,
            "created_at":    created.isoformat(),
            "completed_at":  dt_or_empty(completed_at),
        })

        oi_f.write({
            "order_item_id":     order_item_seq,
            "order_id":          order_id,
            "listing_id":        lid,
            "quantity":          qty,
            "price_at_purchase": price,
        })
        order_item_seq += 1

        if order_status == "cancelled":
            continue

        pay_time  = created + timedelta(minutes=random.randint(0, 2880))
        confirmed = random.random() > 0.03
        conf_time = (pay_time + timedelta(hours=random.randint(0, 72))
                     if confirmed and random.random() < 0.15
                     else (pay_time if confirmed else None))

        # FIX: exit scam vendors always receive crypto payments
        payment_method = "crypto" if is_scammer else random.choice(_PAY_METHOD_POOL)

        pay_f.write({
            "payment_id":     fast_uid("pay_"),
            "order_id":       order_id,
            "buyer_id":       buyer,
            "amount":         total,
            "currency":       currency,
            "payment_method": payment_method,
            "created_at":     pay_time.isoformat(),
            "confirmed_at":   dt_or_empty(conf_time),
        })

        buyer_wallet = wallet_id_map[buyer]
        wto_w.writerow({
            "transaction_id":   fast_uid("wt_"),
            "wallet_id":        buyer_wallet,
            "order_id":         order_id,
            "transaction_type": "escrow_hold",
            "amount":           -total,
            "created_at":       pay_time.isoformat(),
        })

        # ── ESCROW ────────────────────────────────────────────────────────
        escrow_status   = "held"
        escrow_released = None

        if order_status == "completed":
            release_time    = completed_at + timedelta(days=random.randint(1, 3))
            escrow_status   = "released"
            escrow_released = release_time
            vendor_wallet   = wallet_id_map.get(vendor)
            if vendor_wallet:
                wto_w.writerow({
                    "transaction_id":   fast_uid("wt_"),
                    "wallet_id":        vendor_wallet,
                    "order_id":         order_id,
                    "transaction_type": "escrow_release",
                    "amount":           total,
                    "created_at":       release_time.isoformat(),
                })

        elif order_status == "shipped":
            escrow_status = "held"

        elif order_status == "disputed":
            if random.random() < 0.7:
                refund_time     = created + timedelta(days=random.randint(1, 30))
                escrow_status   = "refunded"
                escrow_released = refund_time
                wto_w.writerow({
                    "transaction_id":   fast_uid("wt_"),
                    "wallet_id":        buyer_wallet,
                    "order_id":         order_id,
                    "transaction_type": "refund",
                    "amount":           total,
                    "created_at":       refund_time.isoformat(),
                })

        elif order_status == "pending":
            if age_days > 120 and random.random() < 0.7:
                auto_release    = pay_time + timedelta(days=random.randint(7, 90))
                escrow_status   = "released"
                escrow_released = auto_release

        # ── SHIPMENT ──────────────────────────────────────────────────────
        if order_status in ("shipped", "completed"):
            origin      = random.choice(POOL_COUNTRIES)
            destination = random.choice(POOL_COUNTRIES)
            est_days    = random.randint(1, 10)

            if is_scammer and random.random() < 0.9:
                ship_f.write({
                    "shipment_id":             shipment_seq,
                    "order_id":                order_id,
                    "origin_region":           origin,
                    "destination_region":      destination,
                    "estimated_delivery_days": est_days,
                    "shipped_at":              "",
                    "delivered_at":            "",
                    "delivery_status":         "not_shipped",
                })
            else:
                shipped_at = created + timedelta(days=random.randint(0, 5))
                if order_status == "completed":
                    delivery_status = "delivered"
                    delivered_at    = shipped_at + timedelta(days=random.randint(1, 10))
                else:
                    delivery_status = random.choices(
                        ["in_transit", "delivered"], weights=[0.35, 0.65]
                    )[0]
                    delivered_at = (
                        shipped_at + timedelta(days=random.randint(1, 10))
                        if delivery_status == "delivered" else None
                    )

                ship_f.write({
                    "shipment_id":             shipment_seq,
                    "order_id":                order_id,
                    "origin_region":           origin,
                    "destination_region":      destination,
                    "estimated_delivery_days": est_days,
                    "shipped_at":              shipped_at.isoformat(),
                    "delivered_at":            dt_or_empty(delivered_at),
                    "delivery_status":         delivery_status,
                })

                de_f.write({
                    "event_id":    fast_uid("de_"),
                    "shipment_id": shipment_seq,
                    "event_type":  "pickup",
                    "event_time":  (shipped_at + timedelta(hours=random.randint(1, 24))).isoformat(),
                })
                for _ in range(random.choices([0, 1, 2], weights=[0.5, 0.35, 0.15])[0]):
                    de_f.write({
                        "event_id":    fast_uid("de_"),
                        "shipment_id": shipment_seq,
                        "event_type":  "transit_stop",
                        "event_time":  (shipped_at + timedelta(days=random.randint(1, 5))).isoformat(),
                    })
                if delivered_at:
                    de_f.write({
                        "event_id":    fast_uid("de_"),
                        "shipment_id": shipment_seq,
                        "event_type":  "delivered",
                        "event_time":  delivered_at.isoformat(),
                    })

                if order_status == "shipped" and delivery_status == "delivered" and delivered_at:
                    release_time    = delivered_at + timedelta(days=random.randint(1, 5))
                    escrow_status   = "released"
                    escrow_released = release_time
                    vendor_wallet   = wallet_id_map.get(vendor)
                    if vendor_wallet:
                        wto_w.writerow({
                            "transaction_id":   fast_uid("wt_"),
                            "wallet_id":        vendor_wallet,
                            "order_id":         order_id,
                            "transaction_type": "escrow_release",
                            "amount":           total,
                            "created_at":       release_time.isoformat(),
                        })

            shipment_seq += 1

        elif order_status == "disputed":
            if random.random() < 0.2:
                shipped_at = created + timedelta(days=random.randint(0, 5))
                ship_f.write({
                    "shipment_id":             shipment_seq,
                    "order_id":                order_id,
                    "origin_region":           random.choice(POOL_COUNTRIES),
                    "destination_region":      random.choice(POOL_COUNTRIES),
                    "estimated_delivery_days": random.randint(1, 10),
                    "shipped_at":              shipped_at.isoformat(),
                    "delivered_at":            "",
                    "delivery_status":         "lost",
                })
                de_f.write({
                    "event_id":    fast_uid("de_"),
                    "shipment_id": shipment_seq,
                    "event_type":  "pickup",
                    "event_time":  (shipped_at + timedelta(hours=random.randint(1, 24))).isoformat(),
                })
                shipment_seq += 1

        esc_f.write({
            "escrow_id":      fast_uid("esc_"),
            "order_id":       order_id,
            "held_amount":    total,
            "release_status": escrow_status,
            "held_at":        pay_time.isoformat(),
            "released_at":    dt_or_empty(escrow_released),
        })

        # ── FRAUD FLAGS ───────────────────────────────────────────────────
        # FIX: exit scam vendor orders ALWAYS get buyer_claimed_not_received
        if is_scammer and order_status in ("pending", "disputed"):
            ff_f.write({
                "flag_id":       fast_uid("fl_"),
                "entity_type":   "order",
                "entity_id":     order_id,
                "flag_reason":   "buyer_claimed_not_received",
                "flagged_at":    (created + timedelta(days=random.randint(0, 14))).isoformat(),
                "resolved_flag": False,
            })
        elif order_status == "disputed" or (order_status == "pending" and random.random() < 0.03):
            ff_f.write({
                "flag_id":       fast_uid("fl_"),
                "entity_type":   "order",
                "entity_id":     order_id,
                "flag_reason":   random.choice(_FLAG_REASON_POOL),
                "flagged_at":    (created + timedelta(days=random.randint(0, 14))).isoformat(),
                "resolved_flag": False,
            })

        if buyer in bot_buyers and random.random() < 0.3:
            ff_f.write({
                "flag_id":       fast_uid("fl_"),
                "entity_type":   "user",
                "entity_id":     buyer,
                "flag_reason":   "bot_activity",
                "flagged_at":    (created + timedelta(days=random.randint(0, 60))).isoformat(),
                "resolved_flag": False,
            })

        if order_status == "completed" and escrow_released and random.random() < _review_rate:
            rev_f.write({
                "review_id":        fast_uid("rv_"),
                "order_id":         order_id,
                "reviewer_id":      buyer,
                "reviewed_user_id": vendor,
                "rating":           random.choice(_RATING_POOL),
                "review_text":      random.choice(POOL_REVIEW_TEXT),
                "created_at":       (escrow_released + timedelta(days=random.randint(0, 10))).isoformat(),
            })

    print("  Adding listing fraud flags...")
    for _ in range(max(1, int(num_listings * 0.01))):
        lid2, *_ = random.choice(listing_pool)
        ff_f.write({
            "flag_id":       fast_uid("fl_"),
            "entity_type":   "listing",
            "entity_id":     lid2,
            "flag_reason":   random.choice(["counterfeit","policy_violation","suspicious_description"]),
            "flagged_at":    rand_dt_iso(_EPOCH, _NOW),
            "resolved_flag": random.random() < 0.3,
        })

# ─────────────────────────────────────────────────────────────────────────────
# MERGE WALLET TRANSACTIONS
# ─────────────────────────────────────────────────────────────────────────────
print("  Merging wallet_transactions...")
wt_main  = os.path.join(OUT_DIR, "wallet_transactions.csv")
wt_extra = os.path.join(OUT_DIR, "_wt_orders.csv")
wt_tmp   = os.path.join(OUT_DIR, "_wt_merged.csv")
with open(wt_tmp, "w", newline="", encoding="utf-8") as out_f:
    with open(wt_main,  "r", encoding="utf-8") as f: shutil.copyfileobj(f, out_f)
    with open(wt_extra, "r", encoding="utf-8") as f:
        next(f)
        shutil.copyfileobj(f, out_f)
os.replace(wt_tmp, wt_main)
os.remove(wt_extra)
print("  ok  wallet_transactions merged")

# ─────────────────────────────────────────────────────────────────────────────
# 7) REPUTATION SNAPSHOTS
# FIX: exit scam vendors always start high and end low (deterministic drop)
# ─────────────────────────────────────────────────────────────────────────────
print("[7] Reputation snapshots...")
with StreamCSV("reputation_snapshots.csv",
               ["snapshot_id","user_id","avg_rating","total_reviews","calculated_at"]) as f:
    snap_seq  = 1
    year_ago  = _NOW - timedelta(days=365)

    for v in vendor_list:
        if v in exit_scam_vendors:
            continue  # handled separately below

        n_snaps       = random.choices([1,2,3], weights=[0.5,0.35,0.15])[0]
        snap_date     = year_ago
        avg_rating    = round(random.uniform(3.0, 4.8), 2)
        total_reviews = random.randint(0, 40)
        for _ in range(n_snaps):
            f.write({"snapshot_id": snap_seq, "user_id": v,
                     "avg_rating": avg_rating, "total_reviews": total_reviews,
                     "calculated_at": snap_date.isoformat()})
            snap_seq += 1
            snap_date     += timedelta(days=random.randint(30, 240))
            avg_rating     = round(max(1.0, min(5.0, avg_rating + random.uniform(-0.5, 0.5))), 2)
            total_reviews += random.randint(0, 200)

    # FIX: exit scam vendors get 3 snapshots: high → medium → low
    for v in exit_scam_vendors:
        early_rating  = round(random.uniform(4.2, 5.0), 2)   # starts great
        mid_rating    = round(random.uniform(2.5, 3.5), 2)   # drops
        recent_rating = round(random.uniform(1.0, 2.0), 2)   # tanks

        f.write({"snapshot_id": snap_seq, "user_id": v,
                 "avg_rating": early_rating,
                 "total_reviews": random.randint(50, 300),
                 "calculated_at": (_NOW - timedelta(days=180)).isoformat()})
        snap_seq += 1

        f.write({"snapshot_id": snap_seq, "user_id": v,
                 "avg_rating": mid_rating,
                 "total_reviews": random.randint(20, 100),
                 "calculated_at": (_NOW - timedelta(days=60)).isoformat()})
        snap_seq += 1

        f.write({"snapshot_id": snap_seq, "user_id": v,
                 "avg_rating": recent_rating,
                 "total_reviews": random.randint(1, 30),
                 "calculated_at": (_NOW - timedelta(days=7)).isoformat()})
        snap_seq += 1

# ─────────────────────────────────────────────────────────────────────────────
# 8) RISK SCORES
# FIX: exit scam vendors always escalate low → high over time
# ─────────────────────────────────────────────────────────────────────────────
print("[8] Risk scores...")
with StreamCSV("risk_scores.csv",
               ["risk_id","user_id","risk_score","risk_level","calculated_at"]) as f:
    risk_seq = 1
    year_ago = _NOW - timedelta(days=365)

    for u in users:
        uid        = u["user_id"]
        is_scammer = uid in exit_scam_vendors

        if is_scammer:
            # FIX: always 3 scores, always escalating: low → medium → high
            scores = sorted([
                round(random.uniform(0.1, 0.3), 2),   # early: low
                round(random.uniform(0.4, 0.6), 2),   # mid: medium
                round(random.uniform(0.75, 1.0), 2),  # recent: high
            ])
            times = [
                year_ago,
                year_ago + timedelta(days=random.randint(90, 180)),
                _NOW - timedelta(days=random.randint(1, 30)),
            ]
            for score, t in zip(scores, times):
                f.write({
                    "risk_id":       risk_seq,
                    "user_id":       uid,
                    "risk_score":    score,
                    "risk_level":    "high" if score > 0.7 else ("medium" if score > 0.4 else "low"),
                    "calculated_at": t.isoformat(),
                })
                risk_seq += 1
        else:
            base = round(random.uniform(0, 0.4), 2)
            if uid in bot_buyers:
                base = round(base + random.uniform(0.3, 0.6), 2)
            n = random.choices([1,2,3], weights=[0.6,0.3,0.1])[0]
            t = year_ago
            for _ in range(n):
                score = round(min(1.0, max(0.0, base + random.uniform(-0.1, 0.3))), 2)
                f.write({
                    "risk_id":       risk_seq,
                    "user_id":       uid,
                    "risk_score":    score,
                    "risk_level":    "high" if score > 0.7 else ("medium" if score > 0.4 else "low"),
                    "calculated_at": t.isoformat(),
                })
                risk_seq += 1
                t += timedelta(days=random.randint(30, 180))

# ─────────────────────────────────────────────────────────────────────────────
# DONE
# ─────────────────────────────────────────────────────────────────────────────

# save exit scam vendor IDs as ground truth seed
seed_path = os.path.join(OUT_DIR, "exit_scam_vendors.csv")
with open(seed_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["user_id", "is_exit_scammer"])
    for vid in sorted(exit_scam_vendors):
        w.writerow([vid, 1])
print(f"\n  Ground truth saved → {seed_path}")

print(f"\nAll files written to: {OUT_DIR}/")
print(f"  Exit-scam vendors  : {sorted(exit_scam_vendors)}")
print(f"  Bot buyers (first 10): {sorted(list(bot_buyers))[:10]}")
print("\nCausal signals enforced for exit scam vendors:")
print("  ✓ Risk scores always escalate low → medium → high")
print("  ✓ Reputation always drops high → medium → low (3 snapshots)")
print("  ✓ All orders get buyer_claimed_not_received flag")
print("  ✓ All payments are crypto")
print("  ✓ Sessions use large distinct IP pool")
print("  ✓ Ground truth saved to exit_scam_vendors.csv")