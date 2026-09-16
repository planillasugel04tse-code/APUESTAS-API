import json
from fastapi.testclient import TestClient
import betano_analyzer.provider_accounts as accounts_module
import betano_analyzer.provider_accounts_api as accounts_api
from betano_analyzer.main import app

client=TestClient(app)


def test_provider_accounts_page_and_api_are_exposed():
    accounts_module.clear_session()
    page=client.get('/provider-accounts')
    assert page.status_code==200
    assert 'API Key' in page.text
    assert 'CONFIGURAR PROVEEDORES' in page.text
    response=client.get('/api/v1/provider-accounts')
    assert response.status_code==200 and 'accounts' in response.json()


def test_save_account_does_not_persist_api_key(tmp_path,monkeypatch):
    accounts_module.clear_session()
    accounts_file=tmp_path/'provider_accounts.json'
    monkeypatch.setattr(accounts_module,'ACCOUNTS_FILE',accounts_file);monkeypatch.setattr(accounts_module,'DATA_DIR',tmp_path)
    saved=accounts_module.save_account('oddspapi','OddsPapi','usuario@example.com','abcdefghijklmnop1234')
    assert saved['connected'] is True and saved['api_key_masked'].startswith('abcd')
    raw=accounts_file.read_text(encoding='utf-8')
    assert 'abcdefghijklmnop1234' not in raw and 'api_key' not in raw
    accounts_module.clear_session()


def test_register_provider_without_credentials(tmp_path,monkeypatch):
    accounts_module.clear_session()
    accounts_file=tmp_path/'provider_accounts.json'
    monkeypatch.setattr(accounts_module,'ACCOUNTS_FILE',accounts_file);monkeypatch.setattr(accounts_module,'DATA_DIR',tmp_path)
    saved=accounts_module.save_account('otro-proveedor','Otro','', '', base_url='https://example.com/v1', test_path='/account')
    assert saved['connected'] is False and saved['active'] is False
    assert json.loads(accounts_file.read_text(encoding='utf-8'))[0]['provider']=='otro-proveedor'


def test_connect_validates_then_keeps_key_in_session(tmp_path,monkeypatch):
    accounts_module.clear_session()
    accounts_file=tmp_path/'provider_accounts.json'
    monkeypatch.setattr(accounts_module,'ACCOUNTS_FILE',accounts_file);monkeypatch.setattr(accounts_module,'DATA_DIR',tmp_path)
    async def fake_check(provider,api_key,*args):
        assert provider=='oddspapi';assert api_key=='valid-key-123';return {'valid':True,'usage':{'display':'10 / 500'},'plan':'test'}
    monkeypatch.setattr(accounts_api,'check_provider',fake_check)
    response=client.post('/api/v1/provider-accounts/connect',json={'provider':'oddspapi','label':'Panel','email':'','api_key':'valid-key-123'})
    assert response.status_code==200, response.text
    payload=response.json()
    assert payload['connected'] is True and payload['account']['active'] is True
    assert payload['account']['api_key_masked']!='valid-key-123'
    assert 'valid-key-123' not in accounts_file.read_text(encoding='utf-8')
    assert accounts_module.session_key('oddspapi')=='valid-key-123'
    accounts_module.clear_session()
    assert accounts_module.session_key('oddspapi')==''
