# Tarefa: refatorar `notify.SMTPClient` para usar Mailcow via SSH

## Objetivo

Fazer o serviço `notify` enviar emails pelo **Mailcow real** (VM 150, `mail.v7m.org`)
preservando DKIM/SPF/DMARC do domínio `v7m.org`, sem depender de relay externo.

## Estado atual (2026-05-28)

- **Notify roda em `backend-notify-1`** (porta host `8015`). Código em
  `/home/maestri33/coders/backend/notify/` (host) — observe que o arquivo
  `app/integrations/smtp.py` existe **dentro do container** mas **NÃO** no host
  (build copia a pasta `app/`). Pra editar, edite no host e rebuild:
  `cd /home/maestri33/coders/backend && docker compose -f docker-compose.dev.yml up -d --build notify`.
- O cliente atual (`SMTPClient.send_email`) faz `smtplib.SMTP(host,587).starttls().login().send_message()`.
- Hoje configurado em `/backend/.env` apontando pra `smtp.gmail.com` (workaround
  com app-pass de `v7maestri@gmail.com`). Funciona mas **perde DKIM** do v7m.org.
- A rota TCP direta deste host (`10.1.20.30`) pra `mail.v7m.org:587` (IP público
  `135.181.216.147`) está **firewalled** — `OSError(101, Network is unreachable)`.

## O caminho destravado

A VM 150 do Mailcow é alcançável via SSH **interno** da LAN:

```bash
ssh root@10.1.30.150 'hostname -f'
# → mail.v7m.org   (key já confiável, sem prompt)
```

A receita canônica (skill `send-mail-mailcow` do user) injeta a mensagem direto
no Postfix do container, sem SMTP AUTH, com DKIM assinado pelo rspamd:

```bash
ssh root@10.1.30.150 'cat > /tmp/mail.eml <<EOF
From: "Supletivo" <noreply@v7m.org>
To: victormaestri@gmail.com
Subject: Teste
MIME-Version: 1.0
Content-Type: text/html; charset=UTF-8

<HTML aqui>
EOF
docker exec -i mailcowdockerized-postfix-mailcow-1 sendmail -t -f noreply@v7m.org < /tmp/mail.eml
echo "exit=$?"'
```

Verificação de entrega:
```bash
ssh root@10.1.30.150 'docker logs --tail 200 mailcowdockerized-postfix-mailcow-1 2>&1 | grep -iE "<subject-unico>|<destinatario>"'
# Sucesso: status=sent (250 ...) seguido de removed
ssh root@10.1.30.150 'docker logs --tail 200 mailcowdockerized-rspamd-mailcow-1 2>&1 | grep "<QID>"'
# DKIM_SIGNED presente, score < 5
```

## O que fazer

1. **Refatorar `SMTPClient.send_email()`** (preservar a assinatura pública —
   `to_email, subject, html_body, plain_body, attachments, inline_images`) para
   shell-out via `subprocess.run(['ssh', 'root@10.1.30.150', ...])` em vez de
   TCP/SMTP. Use o mesmo `MIMEMultipart` que já tem; só troca o caminho de envio:
   - Serialize `msg.as_bytes()` localmente
   - Faz `ssh root@10.1.30.150 'docker exec -i mailcowdockerized-postfix-mailcow-1 sendmail -t -f <from>'` passando o bytes via stdin
   - Captura exit code, retorna o dict `{to, subject, from, refused}` no mesmo formato

2. **Container precisa de SSH client + chave**. Opções (escolha):
   - **A)** Adicionar `openssh-client` no `Dockerfile` do notify + montar
     `~/.ssh/id_*` do host como volume readonly em `/root/.ssh/` no
     `docker-compose.dev.yml`. Validar `known_hosts` (pin do fingerprint da VM 150).
   - **B)** Usar a key dedicada `/etc/notify/mailcow_id_ed25519` (gerar nova, copiar
     `.pub` pra `/root/.ssh/authorized_keys` da VM 150) — mais limpo, sem
     vazar a key pessoal do user pro container.
   - Recomendo **B** (key dedicada, escopo `command=` restringindo ao
     `docker exec sendmail` no `authorized_keys`).

3. **Config**: novas envs no `/backend/.env`:
   ```env
   MAILCOW_SSH_HOST=root@10.1.30.150
   MAILCOW_SSH_KEY=/root/.ssh/mailcow_id_ed25519
   MAILCOW_POSTFIX_CONTAINER=mailcowdockerized-postfix-mailcow-1
   MAILCOW_FROM_EMAIL=noreply@v7m.org
   MAILCOW_FROM_NAME=Supletivo
   ```
   Aposentar `MAILCOW_SMTP_HOST/PORT/USER/PASS` (manter no `config.py` por
   compatibilidade mas marcar `deprecated`, ou remover de vez).

4. **Aceite (teste E2E)**:
   ```bash
   curl -X POST http://localhost:8015/api/v1/messages/test-email \
     -H "Content-Type: application/json" \
     -d '{"to_email":"victormaestri@gmail.com","title":"Teste Mailcow via SSH","content":"Validacao da refatoracao."}'
   # Espera: {"sent":true,...}
   ```
   Depois confirmar nos logs do Mailcow:
   ```bash
   ssh root@10.1.30.150 'docker logs --tail 50 mailcowdockerized-postfix-mailcow-1 2>&1 | grep victormaestri'
   # status=sent (250 2.0.0 OK)
   ssh root@10.1.30.150 'docker logs --tail 50 mailcowdockerized-rspamd-mailcow-1 2>&1 | grep <QID>'
   # DKIM_SIGNED(0.00){v7m.org:s=dkim;}
   ```
   E claro: confirmar visualmente que o email chegou (inbox ou spam — `v7m.org`
   tem `p=quarantine` no DMARC, Gmail pode mandar pra spam).

## Restrições

- **NÃO mexer no docker-compose linter-aplicado** — manter `env_file: .env` e
  os anchors `x-common-env/x-postgres-url/x-service-urls`.
- **NÃO commitar a chave SSH** privada no repo. Caminho da key fica no `.env`.
- **NÃO usar `--no-verify`** em git nem desabilitar hooks de build.
- Manter `SMTPClient` como nome do classe (chamado em vários lugares do
  `message_service.py`).

## Referências

- Skill canônica: o user colou um markdown com `name: send-mail-mailcow` —
  guarde como referência (não está no repo, está só na conversa anterior).
- Wiki atualizada: `/home/maestri33/coders/backend/wiki/notify.md` seção
  "Padrões validados (2026-05-28)".
- Padrões SendMedia WhatsApp (já documentados na mesma wiki) — não
  precisa refatorar, já funciona via Evolution API.

## Contexto da sessão anterior

- Cost da sessão de descoberta foi $54+ (caro pq fiquei tentando diagnosticar
  egress firewall e scan de LAN). A refatoração em si deve custar bem menos
  porque o caminho já está mapeado.
- Contato de teste no banco: id 2, external_id
  `caddcdfd-ab01-4c5a-8634-60e92cb6d295`, phone `5542999384069`, email
  `diandra@example.com`. Use **outro** email para testar (ex:
  `victormaestri@gmail.com`) pra não poluir o do contato.
- Mensagens já enviadas com sucesso pra validar partes do fluxo: ids 8 (TTS
  WhatsApp), 11 (PNG inline WhatsApp), 12 (imagem URL local WhatsApp), 13
  (email via Gmail relay com `<img>` embedado). Numeração de `notify.messages`
  pode ter avançado.
