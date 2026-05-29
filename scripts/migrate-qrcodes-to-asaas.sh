#!/usr/bin/env bash
# Migra QR PNGs persistidos no `lead` para o servico `asaas` (post-refactor
# que moveu ownership do binario). Renomeia `<external_id>.png` para
# `<provider_payment_id>.png` (chave nova, asaas-side).
#
# Pre-requisitos:
#   - docker-compose em execucao com os containers `lead` e `asaas`
#   - acesso ao Postgres central (default: docker exec postgres psql ...)
#   - rodar ANTES da alembic migration 0004_qrcode_url_to_asaas, que
#     assume os arquivos ja copiados
#
# Idempotente: pular arquivos ja copiados (asaas tem o destino).
# Read-only no `lead`: nao remove arquivos de la — fica como fallback.
#
# Usage:
#   ./scripts/migrate-qrcodes-to-asaas.sh                 # dry-run (default)
#   APPLY=1 ./scripts/migrate-qrcodes-to-asaas.sh         # executa
#   COMPOSE_FILE=docker-compose.prod.yml APPLY=1 ./...    # prod
#
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.dev.yml}"
COMPOSE_BIN="${COMPOSE_BIN:-docker compose}"
APPLY="${APPLY:-0}"
LEAD_SVC="${LEAD_SVC:-lead}"
ASAAS_SVC="${ASAAS_SVC:-asaas}"
PG_SVC="${PG_SVC:-postgres}"
PG_USER="${POSTGRES_USER:-postgres}"
PG_DB="${POSTGRES_DB:-v7m}"

if [[ "$APPLY" != "1" ]]; then
  echo "DRY-RUN — defina APPLY=1 para executar copia + renomeacao."
fi

# 1) Pega lista (external_id, provider_payment_id) das charges asaas.
echo "==> Lendo lead.checkouts no Postgres ($PG_SVC)..."
mapping=$(
  $COMPOSE_BIN -f "$COMPOSE_FILE" exec -T "$PG_SVC" \
    psql -U "$PG_USER" -d "$PG_DB" -At -F $'\t' -c \
    "SELECT external_id, provider_payment_id
       FROM lead.checkouts
      WHERE provider = 'asaas'
        AND provider_payment_id IS NOT NULL
        AND qrcode_image IS NOT NULL;"
)

total=$(echo "$mapping" | grep -c . || true)
echo "==> $total charges asaas com QR a migrar."
if [[ "$total" -eq 0 ]]; then
  echo "Nada a fazer."
  exit 0
fi

ok=0
skipped=0
missing=0

while IFS=$'\t' read -r eid pid; do
  [[ -z "$eid" || -z "$pid" ]] && continue
  src="/app/media/qrcodes/${eid}.png"
  dst="/app/media/qrcodes/${pid}.png"

  # Source check
  if ! $COMPOSE_BIN -f "$COMPOSE_FILE" exec -T "$LEAD_SVC" test -f "$src" 2>/dev/null; then
    echo "  miss: lead:$src"
    missing=$((missing + 1))
    continue
  fi
  # Dest already exists -> skip (idempotente)
  if $COMPOSE_BIN -f "$COMPOSE_FILE" exec -T "$ASAAS_SVC" test -f "$dst" 2>/dev/null; then
    skipped=$((skipped + 1))
    continue
  fi

  if [[ "$APPLY" == "1" ]]; then
    # Pipe binario lead -> host -> asaas. `docker cp` direto entre 2
    # containers nao existe — passamos pelo stdout do host.
    $COMPOSE_BIN -f "$COMPOSE_FILE" exec -T "$LEAD_SVC" cat "$src" |
      $COMPOSE_BIN -f "$COMPOSE_FILE" exec -T "$ASAAS_SVC" \
        sh -c "mkdir -p /app/media/qrcodes && cat > $dst"
    ok=$((ok + 1))
    echo "  copy: ${eid}.png -> ${pid}.png"
  else
    echo "  plan: ${eid}.png -> ${pid}.png"
    ok=$((ok + 1))
  fi
done <<< "$mapping"

echo "==> Resumo:"
echo "    sucesso/planejado: $ok"
echo "    pulados (ja existe): $skipped"
echo "    sem PNG no lead   : $missing"

if [[ "$APPLY" != "1" ]]; then
  echo "Re-rode com APPLY=1 para executar."
fi
