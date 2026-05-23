from tortoise.models import Model
from tortoise import fields


class CNH(Model):
    id = fields.IntField(pk=True)
    numero = fields.CharField(max_length=30, null=True)
    categoria = fields.CharField(max_length=5, null=True)
    data_nascimento = fields.DateField(null=True)
    validade = fields.DateField(null=True)
    registro_nacional = fields.CharField(max_length=30, null=True)
    foto_frente = fields.CharField(max_length=500, null=True)
    foto_verso = fields.CharField(max_length=500, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "cnh"
