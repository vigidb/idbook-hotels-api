"""Exactly-one owner rule: wallet / wallet-transaction rows must have precisely one of user, company, or agent."""

from __future__ import annotations

from django.core.exceptions import ValidationError

EXCLUSIVE_WALLET_OWNER_MESSAGE = (
    "Exactly one of user, company, or agent must be set; the others must be empty."
)


def validate_exclusive_wallet_owner(
    *, user_id=None, company_id=None, agent_id=None
) -> None:
    present = sum(
        1 for x in (user_id, company_id, agent_id) if x is not None
    )
    if present != 1:
        raise ValidationError(EXCLUSIVE_WALLET_OWNER_MESSAGE)


def normalize_wallet_owner_ids(user_id=None, company_id=None, agent_id=None):
    """
    If more than one owner id is set, keep a single scope using priority:
    company > agent > user (matches recharge / ledger routing elsewhere).
    """
    has_u = user_id is not None
    has_c = company_id is not None
    has_a = agent_id is not None
    total = has_u + has_c + has_a
    if total <= 1:
        return user_id, company_id, agent_id
    if has_c:
        return None, company_id, None
    if has_a:
        return None, None, agent_id
    return user_id, None, None


def wallet_owner_kwargs_from_wallet(wallet) -> dict:
    """Build create/update kwargs with exactly one FK for a Wallet instance."""
    if wallet.company_id:
        return {"company_id": wallet.company_id, "user_id": None, "agent_id": None}
    if wallet.agent_id:
        return {"agent_id": wallet.agent_id, "user_id": None, "company_id": None}
    if wallet.user_id:
        return {"user_id": wallet.user_id, "company_id": None, "agent_id": None}
    raise ValidationError(EXCLUSIVE_WALLET_OWNER_MESSAGE)


def normalize_wallet_transaction_create_payload(data: dict) -> dict:
    """
    Build a dict safe for WalletTransaction.objects.create: strips mixed owner
    keys and applies company > agent > user priority when multiple were passed.
    """
    payload = dict(data)
    user_obj = payload.pop("user", None)
    company_obj = payload.pop("company", None)
    agent_obj = payload.pop("agent", None)

    uid = payload.pop("user_id", None)
    cid = payload.pop("company_id", None)
    aid = payload.pop("agent_id", None)

    if uid is None and user_obj is not None:
        uid = user_obj.pk
    if cid is None and company_obj is not None:
        cid = company_obj.pk
    if aid is None and agent_obj is not None:
        aid = agent_obj.pk

    uid, cid, aid = normalize_wallet_owner_ids(uid, cid, aid)
    validate_exclusive_wallet_owner(user_id=uid, company_id=cid, agent_id=aid)

    if cid is not None:
        payload["company_id"] = cid
    elif aid is not None:
        payload["agent_id"] = aid
    else:
        payload["user_id"] = uid

    return payload
