# enrollment.coordinator_awaiting_release — Notifica coordenador do hub

**Quando:** matriculando enviou a selfie (POST `/authenticated/selfie`) e o
status virou `awaiting_release`. Disparada **async** via `BackgroundTasks`
(CONVENTION §13 — não bloqueia a resposta HTTP).
**Destinatário:** coordenador do hub do promotor. O hub_external_id sai do
agregado de matrícula; até o serviço `hub` existir, é enviado ao próprio
`hub_external_id` (best-effort) — sem hub, só loga e segue.
**Canal:** WhatsApp/SMS (decidido por `notify`).

Conteúdo:

> Matriculando {external_id} completou o envio de dados. Acesse o painel
> para liberar a matrícula.

Flags do payload:
- `enrollment_external_id` — UUID do matriculando
- `promoter_external_id` — UUID do promotor que indicou (pode ser null)
