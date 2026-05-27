"""Schemas de autenticacao — login, registro, verificacao, recuperacao."""

from app.schemas import APIModel


class CheckRequest(APIModel):
    """Verifica se CPF/phone/external_id existe e dispara OTP.

    Respostas uniformizadas (COD-32): nunca diferencia found=true/false.
    """

    cpf: str | None = None
    phone: str | None = None
    external_id: str | None = None


class RecoverRequest(APIModel):
    """Recupera external_id por CPF ou phone e dispara OTP.

    Respostas uniformizadas (COD-32): nunca expoe external_id na resposta.
    """

    cpf: str | None = None
    phone: str | None = None


class LoginRequest(APIModel):
    """Login — verifica role, valida OTP, emite JWT."""

    external_id: str
    otp: str
    role: str


class RegisterRequest(APIModel):
    """Registra novo usuario — sincrono ate criacao, async para provisionamento."""

    role: str
    phone: str
    cpf: str


class TokenResponse(APIModel):
    """Resposta de login com tokens JWT."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class CheckResponse(APIModel):
    """Resposta de /check.

    Funil simplificado: retorna `found` + `external_id` quando achou,
    e `whatsapp_valid` quando o check foi por phone — front decide
    OTP (found=true) vs CPF (found=false, whatsapp_valid=true).
    """

    otp_sent: bool = True
    otp_wait: int | None = None
    found: bool | None = None
    external_id: str | None = None
    whatsapp_valid: bool | None = None


class OTPSentResponse(APIModel):
    """Resposta generica de envio de OTP."""

    otp_sent: bool = True
    otp_wait: int | None = None
    found: bool | None = None  # /recover retorna found=true sempre
