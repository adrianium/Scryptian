# wallet.py — Centralized "slippers" wallet (Supabase).
#
# Pay-per-outcome: a skill's manifest declares a price and an author_id.
# On a successful outcome the runner transfers slippers from the user to the
# author (70%) and the platform (30%). The wallet is centralized in Supabase;
# the local balance is only a cache for fast pre-checks.

import json
import threading
from urllib import request

import telemetry
import store

PLATFORM_ID = "scryptian"
INITIAL_GRANT = 221
COMMISSION_PCT = 30

_lock = threading.Lock()
_balance = None


def user_id():
    return telemetry._get_id()


def _configured():
    return bool(store.SUPABASE_URL and store.SUPABASE_ANON_KEY)


def _rpc(fn, params):
    if not _configured():
        return None
    url = f"{store.SUPABASE_URL}/rest/v1/rpc/{fn}"
    body = json.dumps(params).encode("utf-8")
    req = request.Request(url, data=body, headers={
        **store._headers(),
        "Content-Type": "application/json",
    })
    with request.urlopen(req, timeout=10, context=store._ssl_ctx()) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _as_int(value):
    if isinstance(value, list):
        value = value[0] if value else None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def ensure_wallet():
    """Register the user and grant the initial 221 slippers if new. Returns balance or None."""
    global _balance
    if not _configured():
        return None
    try:
        bal = _as_int(_rpc("ensure_wallet", {"p_user": user_id(), "p_grant": INITIAL_GRANT}))
        if bal is not None:
            _balance = bal
        return _balance
    except Exception:
        return _balance


def cached_balance():
    """Cached balance without triggering a network call. Returns None if unknown."""
    return _balance


def refresh():
    """Force re-fetch the balance from Supabase. Returns balance or None."""
    global _balance
    _balance = None
    return ensure_wallet()


def reserve(price):
    """Reserve `price` before running a skill. Returns True if reserved (or free)."""
    global _balance
    if price <= 0:
        return True
    if not _configured():
        return True
    try:
        ok = _rpc("reserve_slippers", {"p_user": user_id(), "p_amount": price})
        if ok is True or (isinstance(ok, list) and ok and ok[0] is True):
            if _balance is not None:
                _balance = max(0, _balance - price)
            return True
    except Exception as e:
        print(f"[Wallet] reserve failed: {e}")
    return False


def settle(price, author_id, skill_id):
    """Pay author (70%) + platform (30%) from a reserved amount."""
    if price <= 0 or not author_id:
        return
    if not _configured():
        return
    fee = price * COMMISSION_PCT // 100
    try:
        _rpc("settle_slippers", {
            "p_payer": user_id(),
            "p_author": author_id,
            "p_amount": price,
            "p_fee": fee,
            "p_skill": skill_id,
        })
    except Exception as e:
        print(f"[Wallet] settle failed: {e}")


def refund(price):
    """Return a reserved amount to the user (on failure)."""
    global _balance
    if price <= 0:
        return
    if not _configured():
        return
    try:
        _rpc("refund_slippers", {"p_user": user_id(), "p_amount": price})
        if _balance is not None:
            _balance += price
    except Exception as e:
        print(f"[Wallet] refund failed: {e}")
