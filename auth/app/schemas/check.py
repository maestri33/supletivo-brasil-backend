"""Schema de verificacao — consulta CPF/phone/external_id e dispara OTP."""

from app.schemas import APIModel


class CheckRequest(APIModel):
    """Verifica se CPF, phone ou external_id existe e dispara OTP.

    Respostas uniformizadas (COD-32): nunca diferencia found=true/false.
    Pelo menos um dos campos deve ser informado.

    Fields:
        cpf: CPF do usuario (opcional)
        phone: Telefone do usuario (opcional)
        external_id: UUID do usuario (opcional)
    """

    cpf: str | None = None
    phone: str | None = None
    external_id: str | None = None
