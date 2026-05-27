"""Schema de recuperacao — usuario perdeu external_id, recupera via cpf ou phone."""

from app.schemas import APIModel


class RecoverRequest(APIModel):
    """Recupera external_id por CPF ou phone e dispara OTP no canal conhecido.

    Diferente de /check, este endpoint tem semantica explicita de recovery:
    - Aceita apenas cpf ou phone (nunca external_id — voce esta recuperando ele)
    - Resposta sempre uniforme para evitar enumeracao de usuarios (COD-32)

    Fields:
        cpf: CPF do usuario (opcional)
        phone: Telefone do usuario (opcional)
    """

    cpf: str | None = None
    phone: str | None = None
