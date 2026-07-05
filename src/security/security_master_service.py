"""V1.4.2 Security master sync service."""

from __future__ import annotations

from src.data_sources.field_mapper import normalise_symbol_exchange
from src.repositories.security_master_repo import SecurityMasterRepository


def upsert_security(symbol: str, exchange: str, **kwargs) -> dict:
    repo = SecurityMasterRepository()
    sym, ex = normalise_symbol_exchange(symbol, exchange)
    sec = repo.add_or_update(sym, ex, **kwargs)
    return {"symbol": sym, "exchange": ex, "security_id": sec.security_id}
