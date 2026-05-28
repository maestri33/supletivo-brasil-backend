"""Schema de login — verifica role, valida OTP, emite JWT."""

from app.schemas import APIModel


class LoginRequest(APIModel):
    """Login — verifica role, valida OTP, emite JWT.

    Fields:
        external_id: UUID do usuario
        otp: Codigo OTP enviado ao phone do usuario
        role: Role que o usuario pretende assumir nesta sessao
    """

    external_id: str
    otp: str
    role: str


class LoginResponse(APIModel):
    """Resposta de login com tokens JWT.

    Fields:
        access_token: Token JWT de acesso
        token_type: Tipo do token (sempre 'bearer')
    """

    access_token: str
    token_type: str = "bearer"
