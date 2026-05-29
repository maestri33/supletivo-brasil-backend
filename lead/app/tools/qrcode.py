"""Helpers de QR Code remanescentes no lead.

Apos o refactor que moveu persistencia do PNG pro asaas (commit
"refactor: move QR PNG persistence from lead to asaas"), o lead nao
salva mais o binario localmente — `checkout.qrcode_image` ja vem como
URL absoluta servida pelo `asaas` em
`/api/v1/public/media/qrcodes/<payment_id>.png`.

O unico helper que sobrou e' `make_data_uri`: monta o `data:image/png;base64,...`
usado pra anexar o QR como midia inline no notify (WhatsApp recebe imagem
binaria; email recebe CID embed). O base64 ainda vem direto do asaas no
campo `pix.encoded_image`.
"""


def make_data_uri(encoded_image_b64: str, mime: str = "image/png") -> str:
    """Monta um data URI base64 para enviar como `media_url` ao notify.

    Notify aceita `data:` URIs em `media_url` — nessa forma, o WhatsApp
    recebe a IMAGEM ANEXADA (nao um link de texto). O `content` da mensagem
    vira o caption abaixo da imagem.
    """
    # Asaas devolve o base64 puro sem prefixo data:; concatenamos aqui.
    return f"data:{mime};base64,{encoded_image_b64}"
