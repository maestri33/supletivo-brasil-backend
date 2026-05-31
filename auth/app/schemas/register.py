"""Schema de registro — cria usuario e provisiona servicos."""

from app.schemas import APIModel


class RegisterRequest(APIModel):
    """Registra novo usuario — sincrono ate criacao, async para provisionamento.

    Fields:
        role: Role de entrada (ex.: 'barber', 'customer')
        phone: Telefone do usuario (validado contra Notify)
        cpf: CPF do usuario (validado contra Profiles)
    """

    role: str
    phone: str
    cpf: str
