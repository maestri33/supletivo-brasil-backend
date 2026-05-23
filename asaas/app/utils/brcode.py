"""Parser minimo de BR Code (EMVCo QR Code para PIX).

Extrai valor (tag 54) e indica se eh estatico ou dinamico.
"""

from __future__ import annotations


def parse_tlv(payload: str) -> dict[str, str]:
    """Extrai todos os campos TLV de nível raiz do BR Code."""
    fields: dict[str, str] = {}
    i = 0
    while i + 4 <= len(payload):
        tag = payload[i : i + 2]
        try:
            length = int(payload[i + 2 : i + 4])
        except ValueError:
            break
        value = payload[i + 4 : i + 4 + length]
        fields[tag] = value
        i += 4 + length
    return fields


def _parse_nested_tlv(value: str) -> dict[str, str]:
    return parse_tlv(value)


def extract_amount(payload: str) -> float | None:
    """Retorna o valor fixo do QR (tag 54) ou None se variavel/ausente."""
    fields = parse_tlv(payload.strip())
    raw = fields.get("54")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def is_dynamic(payload: str) -> bool:
    """Retorna True quando o QR PIX usa URL de payload dinamico.

    Todo QR PIX costuma ter Merchant Account Information na tag 26. QR estatico
    usa subtag 01 com a chave PIX; QR dinamico usa subtag 25 com uma URL.
    """
    fields = parse_tlv(payload.strip())
    merchant_account = fields.get("26")
    if not merchant_account:
        return False
    nested = _parse_nested_tlv(merchant_account)
    return "25" in nested


def analyze(payload: str) -> dict:
    """Analisa um BR Code PIX sem fazer chamada externa nem pagar."""
    raw = payload.strip()
    fields = parse_tlv(raw)
    merchant = _parse_nested_tlv(fields.get("26", ""))
    point_of_initiation = fields.get("01")
    amount = extract_amount(raw)
    dynamic = "25" in merchant
    pix_key = merchant.get("01") if not dynamic else None
    dynamic_url = merchant.get("25") if dynamic else None
    merchant_name = fields.get("59")
    merchant_city = fields.get("60")
    reference = None
    additional = _parse_nested_tlv(fields.get("62", ""))
    if additional:
        reference = additional.get("05")

    warnings: list[str] = []
    if not fields.get("63"):
        warnings.append("crc_missing")
    if amount is None:
        warnings.append("amount_not_fixed")
    if dynamic:
        warnings.append("dynamic_qrcode_may_expire")
        warnings.append("scheduled_dynamic_qrcode_not_supported")

    return {
        "valid_tlv": bool(fields),
        "kind": "dynamic" if dynamic else "static",
        "point_of_initiation_method": point_of_initiation,
        "amount": amount,
        "allows_amount_edit": amount is None,
        "can_schedule": not dynamic,
        "pix_key": pix_key,
        "dynamic_url": dynamic_url,
        "merchant_name": merchant_name,
        "merchant_city": merchant_city,
        "reference": reference,
        "has_crc": bool(fields.get("63")),
        "warnings": warnings,
        "raw_fields": fields,
        "merchant_account_fields": merchant,
        "additional_data_fields": additional,
    }
