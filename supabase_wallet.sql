-- Scryptian "swords" wallet (centralized in Supabase).
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

-- Transfer swords from payer to author (70%) + platform (30%).
-- Atomic: either the whole transfer happens or nothing does.
CREATE OR REPLACE FUNCTION transfer_swords(
    p_payer TEXT, p_payee TEXT, p_amount INT, p_fee INT, p_skill TEXT
)
RETURNS BOOLEAN AS $$
DECLARE
    bal INT;
    author_share INT;
BEGIN
    SELECT balance INTO bal FROM wallets WHERE user_id = p_payer FOR UPDATE;
    IF bal IS NULL OR bal < p_amount THEN
        RETURN FALSE;
    END IF;

    author_share := p_amount - p_fee;

    UPDATE wallets SET balance = balance - p_amount WHERE user_id = p_payer;

    INSERT INTO wallets (user_id, balance) VALUES (p_payee, 0)
    ON CONFLICT (user_id) DO NOTHING;
    UPDATE wallets SET balance = balance + author_share WHERE user_id = p_payee;

    INSERT INTO wallets (user_id, balance) VALUES ('scryptian', 0)
    ON CONFLICT (user_id) DO NOTHING;
    UPDATE wallets SET balance = balance + p_fee WHERE user_id = 'scryptian';

    INSERT INTO transactions (payer_id, payee_id, amount, fee, skill_id, reason)
    VALUES (p_payer, p_payee, author_share, p_fee, p_skill, 'skill_run');

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
