# enrollment.advance — Notificação ao matriculando a cada etapa

**Quando:** após `POST /api/v1/authenticated/{profile,address,documents/submit,education,selfie}` (CONVENTION §13).
**Destinatário:** matriculando (`external_id` do JWT).
**Canal:** WhatsApp/SMS (decidido por `notify`).

Conteúdo por status (catálogo em `app/services/notifications.py::_ADVANCE_MESSAGES`):

- `profile` → "Perfil salvo. Agora preencha seu endereço para continuar a matrícula."
- `address` → "Endereço salvo. Envie seu RG (frente e verso) para continuar."
- `documents` → "RG recebido. Informe seu último ano de estudo, quando foi e em que escola."
- `education` → "Dados educacionais salvos. Última etapa: envie uma selfie para concluir o envio."
- `awaiting_release` → "Cadastro completo. Sua matrícula está aguardando a liberação do coordenador do polo."
- `completed` → "Parabéns! Sua matrícula foi liberada e você já é aluno."
