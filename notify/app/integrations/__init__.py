"""
Integracoes com servicos externos.

Cada arquivo aqui encapsula a comunicacao com um servico externo especifico.
"""

from app.integrations.smtp import SMTPClient
from app.integrations.whatsapp import WhatsAppClient

__all__ = [
    "SMTPClient",
    "WhatsAppClient",
]
