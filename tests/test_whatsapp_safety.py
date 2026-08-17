import hashlib
import hmac
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
import app.services.whatsapp as whatsapp_service
import app.routers.whatsapp as whatsapp_router
from app.models import Message


def settings(**overrides):
    values = {
        'whatsapp_send_enabled': False,
        'whatsapp_allowed_numbers': (),
        'whatsapp_access_token': 'token',
        'whatsapp_phone_number_id': 'phone-id',
        'whatsapp_api_version': 'v23.0',
        'whatsapp_app_secret': 'secret',
        'environment': 'production',
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_kill_switch_blocks_network_call(monkeypatch):
    monkeypatch.setattr(whatsapp_service, 'settings', settings(whatsapp_send_enabled=False, whatsapp_allowed_numbers=('*',)))
    monkeypatch.setattr(whatsapp_service.requests, 'post', lambda *a, **k: pytest.fail('No debe llamar a Meta'))
    result = whatsapp_service.send_text_message('+52 55 1234 5678', 'hola')
    assert result['sent'] is False
    assert result['blocked'] is True
    assert result['reason'] == 'WHATSAPP_SEND_ENABLED=false'


def test_allowlist_blocks_unknown_number(monkeypatch):
    monkeypatch.setattr(whatsapp_service, 'settings', settings(whatsapp_send_enabled=True, whatsapp_allowed_numbers=('5215511111111',)))
    monkeypatch.setattr(whatsapp_service.requests, 'post', lambda *a, **k: pytest.fail('No debe llamar a Meta'))
    result = whatsapp_service.send_text_message('5215522222222', 'hola')
    assert result['reason'] == 'recipient_not_allowed'


def test_allowlist_normalizes_number_and_sends(monkeypatch):
    monkeypatch.setattr(whatsapp_service, 'settings', settings(whatsapp_send_enabled=True, whatsapp_allowed_numbers=('+52 1 55 1234 5678',)))
    captured = {}
    class Response:
        def raise_for_status(self): return None
        def json(self): return {'messages': [{'id': 'wamid.test'}]}
    def fake_post(url, headers, json, timeout):
        captured['json'] = json
        return Response()
    monkeypatch.setattr(whatsapp_service.requests, 'post', fake_post)
    result = whatsapp_service.send_text_message('5215512345678', 'hola')
    assert result['sent'] is True
    assert captured['json']['to'] == '5215512345678'


def test_empty_allowlist_blocks_even_when_enabled(monkeypatch):
    monkeypatch.setattr(whatsapp_service, 'settings', settings(whatsapp_send_enabled=True, whatsapp_allowed_numbers=()))
    result = whatsapp_service.send_text_message('5215512345678', 'hola')
    assert result['sent'] is False
    assert result['reason'] == 'recipient_not_allowed'


def test_valid_meta_signature(monkeypatch):
    monkeypatch.setattr(whatsapp_router, 'settings', settings(whatsapp_app_secret='super-secret'))
    body = b'{"object":"whatsapp_business_account"}'
    signature = 'sha256=' + hmac.new(b'super-secret', body, hashlib.sha256).hexdigest()
    whatsapp_router.verify_signature(body, signature)


def test_invalid_meta_signature_is_rejected(monkeypatch):
    monkeypatch.setattr(whatsapp_router, 'settings', settings(whatsapp_app_secret='super-secret'))
    with pytest.raises(HTTPException) as exc:
        whatsapp_router.verify_signature(b'{}', 'sha256=bad')
    assert exc.value.status_code == 401


def test_production_rejects_unsigned_webhooks_without_app_secret(monkeypatch):
    monkeypatch.setattr(whatsapp_router, 'settings', settings(whatsapp_app_secret='', environment='production'))
    with pytest.raises(HTTPException) as exc:
        whatsapp_router.verify_signature(b'{}', None)
    assert exc.value.status_code == 503


def test_provider_message_id_has_unique_constraint():
    assert Message.__table__.c.provider_message_id.unique is True


def test_extract_message_keeps_phone_number_id():
    payload = {'entry': [{'changes': [{'value': {'metadata': {'phone_number_id': '123'}, 'messages': [{'from': '52155', 'id': 'wamid.1', 'text': {'body': 'Hola'}}]}}]}]}
    messages = whatsapp_service.extract_messages(payload)
    assert messages[0]['phone_number_id'] == '123'
