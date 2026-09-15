from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .provider_accounts import activate_account, check_provider, list_accounts, remove_account, save_account

router = APIRouter(prefix="/api/v1/provider-accounts", tags=["provider-accounts"])


class ProviderAccountInput(BaseModel):
    provider: str = "oddspapi"
    label: str = Field(default="", max_length=100)
    email: str = Field(default="", max_length=200)
    api_key: str = Field(default="", max_length=500)
    account_id: str | None = Field(default=None, max_length=100)
    base_url: str | None = Field(default=None, max_length=500)
    auth_location: str = Field(default="query", pattern="^(query|header)$")
    auth_name: str = Field(default="apiKey", max_length=100)
    test_path: str = Field(default="/account", max_length=200)


@router.get("")
def accounts(): return {"accounts": list_accounts()}


@router.post("/check")
async def check_account(data: ProviderAccountInput):
    if not data.api_key.strip(): return {"valid": False, "error": "La API Key es obligatoria"}
    try: return await check_provider(data.provider,data.api_key,data.base_url,data.auth_location,data.auth_name,data.test_path)
    except Exception as exc: return {"valid":False,"error":str(exc)}


@router.post("/connect")
async def connect_account(data: ProviderAccountInput):
    if not data.api_key.strip(): raise HTTPException(status_code=400,detail="La API Key es obligatoria")
    try: checked=await check_provider(data.provider,data.api_key,data.base_url,data.auth_location,data.auth_name,data.test_path)
    except Exception as exc: raise HTTPException(status_code=502,detail=f"No se pudo comprobar el proveedor: {exc}") from exc
    try:
        saved=save_account(data.provider,data.label,data.email,data.api_key,data.account_id,data.base_url,data.auth_location,data.auth_name,data.test_path)
        account=activate_account(saved["id"])
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc
    return {"connected":True,"account":account,"usage":checked.get("usage",{}),"plan":checked.get("plan"),"subscription_status":checked.get("subscription_status"),"valid_from":checked.get("valid_from"),"valid_until":checked.get("valid_until")}


@router.post("")
def create_or_update_account(data: ProviderAccountInput):
    try: return {"account":save_account(data.provider,data.label,data.email,data.api_key,data.account_id,data.base_url,data.auth_location,data.auth_name,data.test_path)}
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc


@router.post("/{account_id}/activate")
def activate(account_id:str):
    try: return {"account":activate_account(account_id)}
    except ValueError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc


@router.delete("/{account_id}")
def remove(account_id:str):
    try: remove_account(account_id); return {"deleted":True}
    except ValueError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc
