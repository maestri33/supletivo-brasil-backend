"""
Geracao de pares de chaves RSA para assinatura de JWTs.

Usa a biblioteca cryptography (instalada via pyjwt[crypto]).
As chaves seguem os formatos padrao:
  - Privada: PKCS8 PEM (sem criptografia — usar apenas em DMZ)
  - Publica:  SPKI PEM (SubjectPublicKeyInfo)

Tamanho de chave:
  - 2048 bits e' o minimo recomendado para RSA (NIST SP 800-57)
  - Suficiente para tokens JWT de curta duracao
  - Se precisar de mais seguranca, usar 4096 (mais lento pra gerar)

Exportacao:
  - private_bytes() com encoding PEM e format PKCS8
  - public_bytes() com encoding PEM e format SubjectPublicKeyInfo
  - Ambas sem criptografia (NoEncryption) — ambiente DMZ controlado
"""

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_rsa_key_pair(key_size: int = 2048) -> tuple[str, str]:
    """
    Gera um par de chaves RSA e retorna (private_key_pem, public_key_pem).

    Args:
      key_size: Tamanho da chave em bits (default 2048).

    Returns:
      tuple[str, str]: (chave_privada_pem, chave_publica_pem)

    Exemplo de saida:
      private_key = "-----BEGIN PRIVATE KEY-----\nMIIEv..."
      public_key  = "-----BEGIN PUBLIC KEY-----\nMIIBI..."
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,    # expoente publico padrao (F4)
        key_size=key_size,
        backend=default_backend(),
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )

    return private_pem, public_pem
