"""Mensagem de confirmacao de pagamento (gerada pelo app `ai`).

Fallback robusto se o app `ai` estiver fora, desabilitado ou retornar erro —
o fluxo de checkout nunca quebra por causa disso.
"""

from __future__ import annotations

from app.config import get_settings
from app.integrations.ai import AiServiceError, ai_enabled, chat


async def generate_receipt_message(
    customer_name: str, product: str, price_cents: int, receipt_url: str
) -> str:
    """Gera mensagem curta de confirmacao personalizada (pt-BR)."""
    price_reais = price_cents / 100

    fallback = (
        f"Oi {customer_name}! Seu pagamento de R$ {price_reais:.2f} pelo {product} foi confirmado."
    )

    if not ai_enabled():
        return f"Pagamento confirmado: {product} - R$ {price_reais:.2f}"

    system_msg = (
        "Gere mensagem curta de confirmacao de pagamento em pt-BR. "
        "Seja amigavel mas profissional. Maximo 2 frases. "
        "Inclua nome do cliente, produto e valor. "
        "NAO inclua links."
    )
    user_msg = f"Cliente: {customer_name}\nProduto: {product}\nValor: R$ {price_reais:.2f}"

    try:
        result = await chat(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            model=get_settings().ai_model,
            max_tokens=150,
            temperature=0.7,
        )
        return result.content.strip() or fallback
    except AiServiceError:
        return fallback
