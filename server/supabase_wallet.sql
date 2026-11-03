-- Scryptian "slippers" wallet (centralized in Supabase).
--
-- Run this in the Supabase SQL editor. The RPC functions use SECURITY DEFINER
-- so the anon key can call them even when Row Level Security is enabled on the
-- tables (the client never touches the tables directly).

CREATE TABLE IF NOT EXISTS wallets (
    user_id TEXT PRIMARY KEY,
    balance INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS transactions (
    id BIGSERIAL PRIMARY KEY,
    payer_id TEXT NOT NULL,
    payee_id TEXT NOT NULL,
    amount INTEGER NOT NULL,
    fee INTEGER NOT NULL,
    skill_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Register a user. Grants the initial balance only when the wallet is new.
CREATE OR REPLACE FUNCTION ensure_wallet(p_user TEXT, p_grant INT)
RETURNS INT AS $$
DECLARE
    bal INT;
BEGIN
    INSERT INTO wallets (user_id, balance)
    VALUES (p_user, p_grant)
    ON CONFLICT (user_id) DO NOTHING;

    SELECT balance INTO bal FROM wallets WHERE user_id = p_user;
    RETURN bal;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ── Purchases (Stripe) ─────────────────────────────────────────

-- Idempotency ledger: one Stripe checkout session = one credit.
CREATE TABLE IF NOT EXISTS stripe_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    amount INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Credit slippers after a successful Stripe payment.
-- SECURITY DEFINER + revoked from anon/authenticated so only the
-- webhook (service role) can call it.
CREATE OR REPLACE FUNCTION credit_slippers(
    p_user TEXT, p_amount INT, p_session TEXT
)
RETURNS INT AS $$
DECLARE
    bal INT;
BEGIN
    IF EXISTS (SELECT 1 FROM stripe_sessions WHERE session_id = p_session) THEN
        SELECT balance INTO bal FROM wallets WHERE user_id = p_user;
        RETURN COALESCE(bal, 0);
    END IF;

    INSERT INTO stripe_sessions (session_id, user_id, amount)
    VALUES (p_session, p_user, p_amount);

    INSERT INTO wallets (user_id, balance) VALUES (p_user, p_amount)
    ON CONFLICT (user_id) DO UPDATE SET balance = wallets.balance + EXCLUDED.balance;

    INSERT INTO transactions (payer_id, payee_id, amount, fee, skill_id, reason)
    VALUES (p_user, 'scryptian', p_amount, 0, 'purchase', 'purchase');

    SELECT balance INTO bal FROM wallets WHERE user_id = p_user;
    RETURN bal;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Only the service role (webhook) may credit slippers.
GRANT EXECUTE ON FUNCTION credit_slippers(TEXT, INT, TEXT) TO service_role;
REVOKE EXECUTE ON FUNCTION credit_slippers(TEXT, INT, TEXT) FROM anon, authenticated;

-- ── Escrow (reserve → settle/refund) ───────────────────────────

-- Reserve: atomically deduct from the user before running a skill.
CREATE OR REPLACE FUNCTION reserve_slippers(p_user TEXT, p_amount INT)
RETURNS BOOLEAN AS $$
DECLARE
    bal INT;
BEGIN
    SELECT balance INTO bal FROM wallets WHERE user_id = p_user FOR UPDATE;
    IF bal IS NULL OR bal < p_amount THEN
        RETURN FALSE;
    END IF;

    UPDATE wallets SET balance = balance - p_amount WHERE user_id = p_user;
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Settle: pay author (70%) + platform (30%) from the reserved amount.
CREATE OR REPLACE FUNCTION settle_slippers(
    p_payer TEXT, p_author TEXT, p_amount INT, p_fee INT, p_skill TEXT
)
RETURNS BOOLEAN AS $$
DECLARE
    author_share INT;
BEGIN
    author_share := p_amount - p_fee;

    INSERT INTO wallets (user_id, balance) VALUES (p_author, 0)
    ON CONFLICT (user_id) DO NOTHING;
    UPDATE wallets SET balance = balance + author_share WHERE user_id = p_author;

    INSERT INTO wallets (user_id, balance) VALUES ('scryptian', 0)
    ON CONFLICT (user_id) DO NOTHING;
    UPDATE wallets SET balance = balance + p_fee WHERE user_id = 'scryptian';

    INSERT INTO transactions (payer_id, payee_id, amount, fee, skill_id, reason)
    VALUES (p_payer, p_author, author_share, p_fee, p_skill, 'skill_run');

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Refund: return the reserved amount to the user on failure.
CREATE OR REPLACE FUNCTION refund_slippers(p_user TEXT, p_amount INT)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE wallets SET balance = balance + p_amount WHERE user_id = p_user;
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
