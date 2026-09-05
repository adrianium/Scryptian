# wallet.py — Centralized "swords" wallet (Supabase).
#
# Pay-per-outcome: a skill's manifest declares a price and an author_id.
# On a successful outcome the runner transfers swords from the user to the
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
    """Register the user and grant the initial 221 swords if new. Returns balance or None."""
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


def balance():
    """Current balance (cached). Ensures the wallet exists on first call."""
    global _balance
    if _balance is None:
        ensure_wallet()
    return _balance


def cached_balance():
    """Cached balance without triggering a network call. Returns None if unknown."""
    return _balance


def can_afford(price):
    """True if the user can pay `price`. Wallet unavailable → allow (no block)."""
    if price <= 0:
        return True
    bal = balance()
    if bal is None:
        return True
    return bal >= price


def charge(price, author_id, skill_id):
    """Transfer `price` from user to author (70%) + platform (30%). Returns True on success."""
    global _balance
    if price <= 0 or not author_id:
        return True
    if not _configured():
        return False
    fee = price * COMMISSION_PCT // 100
    try:
        ok = _rpc("transfer_swords", {
            "p_payer": user_id(),
            "p_payee": author_id,
            "p_amount": price,
            "p_fee": fee,
            "p_skill": skill_id,
        })
        if ok is True or (isinstance(ok, list) and ok and ok[0] is True):
            if _balance is not None:
                _balance = max(0, _balance - price)
            return True
    except Exception:
        pass
    return False
