import json
import time

from app.ai.client import ai_enabled, get_client, get_model, get_pro_model
from app.ai.tools import SYSTEM_PROMPT, TOOLS, execute_tool

# Perguntas com essas palavras-chave usam pro (análise profunda)
PRO_KEYWORDS = [
    "analise", "análise", "tendencia", "tendência", "padrão", "padrao",
    "por que", "porque", "explique", "explica", "perfil", "compara",
    "relatorio", "relatório", "prevê", "preve", "projeta", "sugere",
    "recomenda", "estratégia", "insight", "segmenta", "conversão",
    "conversao", "saudável", "saudavel", "preocupa", "melhora",
]


def _is_deep_question(question: str, force_pro: bool) -> bool:
    if force_pro:
        return True
    q = question.lower()
    return any(kw in q for kw in PRO_KEYWORDS)


def ask(question: str, deep: bool = False) -> dict:
    if not ai_enabled():
        return {"answer": "AI features desabilitadas.", "enabled": False}

    use_pro = _is_deep_question(question, deep)
    model = get_pro_model() if use_pro else get_model()

    client = get_client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    t0 = time.time()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=TOOLS,
        temperature=0.3,
    )
    msg = response.choices[0].message

    tool_calls_executed = []
    while msg.tool_calls:
        messages.append(msg)
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            result = execute_tool(tc.function.name, args)
            tool_calls_executed.append({"tool": tc.function.name, "args": args})

            # Truncate large results para nao estourar contexto
            truncated = result if len(result) < 8000 else result[:8000] + "...[truncado]"
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": truncated,
                }
            )

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
        )
        msg = response.choices[0].message

    elapsed_ms = int((time.time() - t0) * 1000)

    return {
        "answer": msg.content or "(sem resposta)",
        "enabled": True,
        "model": model,
        "elapsed_ms": elapsed_ms,
        "tools_called": tool_calls_executed,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
            "completion_tokens": response.usage.completion_tokens if response.usage else None,
        },
    }
