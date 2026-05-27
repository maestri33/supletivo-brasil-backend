"""
Integracoes com servicos externos.

Cada arquivo aqui encapsula a comunicacao com um servico externo especifico.
"""

from app.integrations.mailcow import MailcowClient
from app.integrations.smtp import SMTPClient
from app.integrations.whatsapp import WhatsAppClient

__all__ = [
    "MailcowClient",
    "SMTPClient",
    "WhatsAppClient",
]
