"""Workers do asaas — loops assincronos rodando junto do FastAPI app.

- outbound_queue: entrega notify interno (charge/payment/qrcode) com retry
  exponencial, claim atomico, persiste falhas pra reenvio.
"""
