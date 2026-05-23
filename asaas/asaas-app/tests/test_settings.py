from app import config


def test_webhook_events_inclui_transfer_done():
    """WEBHOOK_EVENTS e a lista registrada no Asaas em /config/key/confirm."""
    assert "TRANSFER_DONE" in config.WEBHOOK_EVENTS
    assert "TRANSFER_FAILED" in config.WEBHOOK_EVENTS


def test_webhook_events_inclui_payment_received_para_charges():
    """Charges (kind=charge) dependem de PAYMENT_* events para mudar de status."""
    for evt in ("PAYMENT_RECEIVED", "PAYMENT_CONFIRMED", "PAYMENT_OVERDUE", "PAYMENT_DELETED"):
        assert evt in config.WEBHOOK_EVENTS


def test_settings_sandbox_flag_default_false():
    """Production-only por default; sandbox precisa ser opt-in."""
    s = config.Settings()
    assert s.asaas_allow_sandbox is False


def test_settings_charge_default_due_days_positivo():
    s = config.Settings()
    assert s.charge_default_due_days > 0
