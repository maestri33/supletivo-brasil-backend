from enum import Enum

from tortoise import fields, models


class LeadStatus(str, Enum):
    CAPTURED = "captured"
    PERSONAL = "personal"
    EDUCATION = "education"
    BIRTH = "birth"
    ADDRESS = "address"
    WAITING = "waiting"
    CHECKOUT = "checkout"
    COMPLETED = "completed"


class TimestampMixin:
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)


class Lead(models.Model, TimestampMixin):
    id = fields.BigIntField(pk=True)

    external_id = fields.CharField(
        max_length=36,
        unique=True,
        index=True,
        description="UUID do usuario vindo do Auth",
    )

    status = fields.CharEnumField(
        enum_type=LeadStatus,
        default=LeadStatus.CAPTURED,
        description="Estado atual do lead",
    )

    hub_external_id = fields.CharField(
        max_length=36,
        null=True,
        index=True,
        description="UUID do hub",
    )

    class Meta:
        table = "leads"
        ordering = ["-created_at"]

    def __str__(self):
        return f"<Lead {self.external_id}>"


class Checkout(models.Model, TimestampMixin):
    id = fields.BigIntField(pk=True)

    external_id = fields.CharField(
        max_length=36,
        unique=True,
        index=True,
        description="UUID do lead",
    )

    checkout_url = fields.CharField(max_length=1024, null=True)
    receipt_url = fields.CharField(max_length=1024, null=True)
    invoice_slug = fields.CharField(max_length=255, null=True, index=True)
    transaction_nsu = fields.CharField(max_length=255, null=True, index=True)
    capture_method = fields.CharField(max_length=50, null=True)
    installments = fields.SmallIntField(null=True)
    is_paid = fields.BooleanField(default=False, index=True)

    class Meta:
        table = "checkouts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"<Checkout {self.external_id}>"


class Message(models.Model, TimestampMixin):
    id = fields.BigIntField(pk=True)

    message_id = fields.IntField(
        null=True, index=True, description="ID retornado pelo notify"
    )

    external_id = fields.CharField(
        max_length=36, index=True, description="UUID do lead"
    )

    direction = fields.CharField(
        max_length=10, default="out", description="out (envio) | in (webhook)"
    )

    channel = fields.CharField(
        max_length=20, null=True, description="whatsapp | email | tts"
    )

    content = fields.TextField(null=True)

    status = fields.CharField(
        max_length=30, null=True, index=True, description="sent | delivered | read | failed"
    )

    event = fields.CharField(
        max_length=50, null=True, description="message.sent | message.delivered | message.failed"
    )

    meta = fields.JSONField(
        null=True, description="Dados extras do webhook"
    )

    class Meta:
        table = "messages"
        ordering = ["-created_at"]

    def __str__(self):
        return f"<Message {self.message_id}>"
