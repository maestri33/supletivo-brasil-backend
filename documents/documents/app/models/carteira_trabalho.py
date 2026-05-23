from tortoise.models import Model
from tortoise import fields


class CarteiraTrabalho(Model):
    id = fields.IntField(pk=True)
    numero = fields.CharField(max_length=30, null=True)
    serie = fields.CharField(max_length=20, null=True)
    uf = fields.CharField(max_length=2, null=True)
    data_emissao = fields.DateField(null=True)
    foto_frente = fields.CharField(max_length=500, null=True)
    foto_verso = fields.CharField(max_length=500, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "carteiras_trabalho"
