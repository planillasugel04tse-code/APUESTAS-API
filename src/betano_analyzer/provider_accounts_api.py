from __future__ import annotations
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .provider_accounts import activate_account, active_account, check_provider, list_accounts, remove_account, save_account, session_key
from .oddspapi_key_store import delete_api_key, key_configured, load_api_key, masked_api_key, save_api_key

router=APIRouter(prefix="/api/v1/provider-accounts",tags=["provider-accounts"])

class ProviderAccountInput(BaseModel):
    provider:str="oddspapi"; label:str=Field(default="",max_length=100); email:str=Field(default="",max_length=200); api_key:str=Field(default="",max_length=500); account_id:str|None=Field(default=None,max_length=100); base_url:str|None=Field(default=None,max_length=500); auth_location:str=Field(default="query",pattern="^(query|header)$"); auth_name:str=Field(default="apiKey",max_length=100); test_path:str=Field(default="/account",max_length=200); remember_key:bool=True

@router.get("")
def accounts(): return {"accounts":list_accounts(),"saved_key":key_configured(),"saved_key_masked":masked_api_key()}

@router.get("/status")
async def status():
    account=active_account()
    if not account: return {"connected":False,"account":None,"saved_key":key_configured(),"saved_key_masked":masked_api_key()}
    key=session_key(account["provider"])
    if not key and account["provider"].lower()=="oddspapi": key=load_api_key() or ""
    base={"connected":bool(key),"account":account,"usage":{},"plan":None,"subscription_status":None,"valid_from":None,"valid_until":None,"saved_key":key_configured(),"saved_key_masked":masked_api_key()}
    if not key: return base|{"error":"API Key no disponible en esta sesión"}
    try:
        checked=await asyncio.wait_for(check_provider(account["provider"],key,account["base_url"],account["auth_location"],account["auth_name"],account["test_path"]),timeout=8.0)
        base.update({"usage":checked.get("usage",{}),"plan":checked.get("plan"),"subscription_status":checked.get("subscription_status"),"valid_from":checked.get("valid_from"),"valid_until":checked.get("valid_until")})
        return base
    except Exception as exc:
        base["verification_error"]=str(exc); return base

@router.post("/check")
async def check_account(data:ProviderAccountInput):
    if not data.api_key.strip(): return {"valid":False,"error":"La API Key es obligatoria"}
    try: return await check_provider(data.provider,data.api_key,data.base_url,data.auth_location,data.auth_name,data.test_path)
    except Exception as exc: return {"valid":False,"error":str(exc)}

@router.post("/connect")
async def connect_account(data:ProviderAccountInput):
    if not data.api_key.strip(): raise HTTPException(status_code=400,detail="La API Key es obligatoria")
    try: checked=await check_provider(data.provider,data.api_key,data.base_url,data.auth_location,data.auth_name,data.test_path)
    except Exception as exc: raise HTTPException(status_code=502,detail=f"No se pudo comprobar el proveedor: {exc}") from exc
    try:
        saved=save_account(data.provider,data.label,data.email,data.api_key,data.account_id,data.base_url,data.auth_location,data.auth_name,data.test_path); account=activate_account(saved["id"])
        if data.provider.lower()=="oddspapi":
            if data.remember_key: save_api_key(data.api_key)
            else: delete_api_key()
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc
    return {"connected":True,"account":account,"usage":checked.get("usage",{}),"plan":checked.get("plan"),"subscription_status":checked.get("subscription_status"),"valid_from":checked.get("valid_from"),"valid_until":checked.get("valid_until"),"saved_key":key_configured(),"saved_key_masked":masked_api_key()}

@router.post("/saved-key/remove")
def remove_saved_key():
    delete_api_key(); return {"saved_key":False,"saved_key_masked":""}

@router.post("")
def create_or_update_account(data:ProviderAccountInput):
    try: return {"account":save_account(data.provider,data.label,data.email,"",data.account_id,data.base_url,data.auth_location,data.auth_name,data.test_path)}
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc

@router.post("/{account_id}/activate")
def activate(account_id:str):
    try: return {"account":activate_account(account_id)}
    except ValueError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc

@router.delete("/{account_id}")
def remove(account_id:str):
    try: remove_account(account_id); return {"deleted":True}
    except ValueError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc
