from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .provider_accounts import activate_account, check_oddspapi, list_accounts, save_account


router = APIRouter(prefix="/api/v1/provider-accounts", tags=["provider-accounts"])


class ProviderAccountInput(BaseModel):
    provider: str = "oddspapi"
    label: str = Field(default="", max_length=100)
    email: str = Field(default="", max_length=200)
    api_key: str = Field(min_length=1, max_length=500)
    account_id: str | None = Field(default=None, max_length=100)


@router.get("")
def accounts():
    return {"accounts": list_accounts()}


@router.post("/check")
async def check_account(data: ProviderAccountInput):
    if data.provider.strip().lower() != "oddspapi":
        raise HTTPException(status_code=400, detail="Proveedor no soportado")
    try:
        return await check_oddspapi(data.api_key)
    except Exception as exc:
        return {"valid": False, "error": str(exc)}


@router.post("")
def create_or_update_account(data: ProviderAccountInput):
    try:
        return {"account": save_account(data.provider, data.label, data.email, data.api_key, data.account_id)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{account_id}/activate")
def activate(account_id: str):
    try:
        return {"account": activate_account(account_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
