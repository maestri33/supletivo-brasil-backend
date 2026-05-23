"""
Geracao da mensagem de confirmacao de pagamento.

Migrado para chamar o AI service v7m via HTTP (sem tool_calling).
Fallback robusto se o AI service estiver fora ou retornar erro.
"""

from app.ai.ai_service_client import AiServiceError, chat
from app.ai.client import ai_enabled


def generate_receipt_message(
    customer_name: str, product: str, price_cents: int, receipt_url: str
) -> str:
    """Gera mensagem curta de confirmação personalizada."""
    price_reais = price_cents / 100

    fallback = (
        f"Oi {customer_name}! "
        f"Seu pagamento de R$ {price_reais:.2f} "
        f"pelo {product} foi confirmado."
    )

    if not ai_enabled():
        return f"Pagamento confirmado: {product} - R$ {price_reais:.2f}"

    system_msg = (
        "Gere mensagem curta de confirmacao de pagamento em pt-BR. "
        "Seja amigavel mas profissional. Maximo 2 frases. "
        "Inclua nome do cliente, produto e valor. "
        "NAO inclua links."
    )
    user_msg = (
        f"Cliente: {customer_name}\n"
        f"Produto: {product}\n"
        f"Valor: R$ {price_reais:.2f}"
    )

    try:
        result = chat(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            model="deepseek-v4-flash",
            max_tokens=150,
            temperature=0.7,
        )
        return result.content.strip() or fallback
    except AiServiceError:
        return fallback
