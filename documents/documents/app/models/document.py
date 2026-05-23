from tortoise.models import Model
from tortoise import fields


CERTIDAO_TIPOS = {"nascimento", "casamento", "obito"}


class Document(Model):
    id = fields.IntField(pk=True)
    external_id = fields.CharField(max_length=50, unique=True, index=True)

    rg = fields.ForeignKeyField("models.RG", null=True, on_delete=fields.SET_NULL)
    cnh = fields.ForeignKeyField("models.CNH", null=True, on_delete=fields.SET_NULL)
    carteira_trabalho = fields.ForeignKeyField("models.CarteiraTrabalho", null=True, on_delete=fields.SET_NULL)
    passaporte = fields.ForeignKeyField("models.Passaporte", null=True, on_delete=fields.SET_NULL)

    # Certidão (nascimento / casamento / óbito)
    certidao_tipo = fields.CharField(max_length=20, null=True)
    certidao_numero = fields.CharField(max_length=50, null=True)
    certidao_cartorio = fields.CharField(max_length=100, null=True)
    certidao_livro = fields.CharField(max_length=20, null=True)
    certidao_folha = fields.CharField(max_length=20, null=True)
    certidao_termo = fields.CharField(max_length=20, null=True)
    certidao_data_emissao = fields.DateField(null=True)
    certidao_foto = fields.CharField(max_length=500, null=True)

    # Reservista
    reservista_numero = fields.CharField(max_length=30, null=True)
    reservista_serie = fields.CharField(max_length=20, null=True)
    reservista_categoria = fields.CharField(max_length=20, null=True)
    reservista_ra = fields.CharField(max_length=20, null=True)
    reservista_foto = fields.CharField(max_length=500, null=True)

    # Comprovante de residência
    comprovante_residencia_foto = fields.CharField(max_length=500, null=True)

    # Foto geral (opcional)
    foto = fields.CharField(max_length=500, null=True)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "documentos"
