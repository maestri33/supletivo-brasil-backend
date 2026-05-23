#TODO: Remova, desnecessário, só polui o código

"""Endpoint público de documentação da API — markdown raw e HTML renderizado.

Serve `services/lead/app/docs/api_guide.md` (espelho do `.claude/skills/v7m-api/
SKILL.md`) em três variantes via content-negotiation:

- `GET /api/v1/public/docs`       → HTML renderizado (default, abrir no browser)
- `GET /api/v1/public/docs.md`    → markdown bruto (text/markdown; pra scripts/AI)
- `GET /api/v1/public/docs.html`  → HTML renderizado (explícito)

A renderização HTML é feita 100% client-side via marked.js + github-markdown-css +
highlight.js carregados de CDN. Nenhuma dep Python nova; o servidor entrega só o
markdown embutido num shell HTML mínimo. Resultado: bundle de ~3KB no servidor,
renderização nativa de tabela/code-block/heading no browser.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse

router = APIRouter(prefix="/api/v1/public/docs", tags=["public", "docs"])

_DOC_FILE = Path(__file__).parent.parent.parent / "docs" / "api_guide.md"


def _strip_frontmatter(text: str) -> str:
    """Remove bloco YAML frontmatter (`---\\n...\\n---\\n`) do topo, se presente.

    O api_guide.md eh fonte unica compartilhada com a skill Claude Code, que exige
    frontmatter (name/description/trigger). Browsers e scripts externos nao precisam

        ver esses metadados — strip antes de servir.
    """
    if not text.startswith("---\n"):
        return text
    # Procura o segundo '---' que fecha o bloco
    end_idx = text.find("\n---\n", 4)
    if end_idx == -1:
        return text  # frontmatter mal-formado; serve original sem quebrar
    return text[end_idx + 5 :].lstrip()


def _read_doc() -> str:
    """Lê o arquivo markdown e remove frontmatter. Cacheado em memória após o
    primeiro hit (I/O barata + arquivo é small, mas evita re-ler em cada request)."""
    if not hasattr(_read_doc, "_cache"):
        raw = _DOC_FILE.read_text(encoding="utf-8")
        _read_doc._cache = _strip_frontmatter(raw)
    return _read_doc._cache


_HTML_SHELL = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>v7m API — Documentação</title>
  <link rel="stylesheet"
        href="https://cdn.jsdelivr.net/npm/github-markdown-css@5/github-markdown-light.min.css">
  <link rel="stylesheet"
        href="https://cdn.jsdelivr.net/npm/highlight.js@11/styles/github.min.css">
  <style>
    body {{
      box-sizing: border-box;
      min-width: 200px;
      max-width: 1024px;
      margin: 0 auto;
      padding: 32px 24px 96px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f6f8fa;
    }}
    .markdown-body {{
      background: #ffffff;
      padding: 48px 64px;
      border-radius: 12px;
      border: 1px solid #d0d7de;
      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0 16px 16px;
      margin-bottom: 16px;
      color: #57606a;
      font-size: 13px;
    }}
    .header a {{
      color: #0969da;
      text-decoration: none;
    }}
    .header a:hover {{ text-decoration: underline; }}
    @media (max-width: 768px) {{
      body {{ padding: 16px 8px 64px; }}
      .markdown-body {{ padding: 24px 20px; }}
    }}
  </style>
</head>
<body>
  <div class="header">
    <span>Supletivo · api.v7m.org</span>
    <span>
      <a href="/api/v1/public/docs.md">raw markdown</a>
      &nbsp;·&nbsp;
      <a href="https://supletivo.net.br">supletivo.net.br</a>
    </span>
  </div>
  <article class="markdown-body" id="content"></article>

  <script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/highlight.js@11/lib/core.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/highlight.js@11/lib/languages/bash.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/highlight.js@11/lib/languages/python.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/highlight.js@11/lib/languages/json.min.js"></script>
  <script>
    hljs.registerLanguage('bash', window.hljsLanguages?.bash || hljs.listLanguages().includes('bash'));
    // Renderiza markdown com gfm + tabelas + highlight.js
    marked.setOptions({{
      gfm: true,
      breaks: false,
      highlight: function(code, lang) {{
        try {{
          if (lang && hljs.getLanguage(lang)) {{
            return hljs.highlight(code, {{ language: lang }}).value;
          }}
          return hljs.highlightAuto(code).value;
        }} catch (e) {{
          return code;
        }}
      }}
    }});

    // Markdown source embarcado pelo servidor — escapado pra ser literal JS string
    const MARKDOWN_SRC = {markdown_json};

    document.getElementById('content').innerHTML = marked.parse(MARKDOWN_SRC);

    // Highlight blocks que o marked não tocou (segurança extra)
    document.querySelectorAll('pre code').forEach(b => {{
      try {{ hljs.highlightElement(b); }} catch (e) {{}}
    }});
  </script>
</body>
</html>
"""


@router.get(
    "",
    response_class=HTMLResponse,
    summary="Documentação renderizada (HTML)",
)
async def docs_root() -> HTMLResponse:
    return await docs_html()


@router.get(
    ".md",
    response_class=PlainTextResponse,
    summary="Documentação em markdown bruto",
)
async def docs_md() -> PlainTextResponse:

    return PlainTextResponse(
        _read_doc(),
        media_type="text/markdown; charset=utf-8",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get(
    ".html",
    response_class=HTMLResponse,
    summary="Documentação renderizada (HTML explícito)",
)
async def docs_html() -> HTMLResponse:
    import json

    # json.dumps escapa quebras de linha, aspas, e \, garantindo que o markdown
    # vire string JS válida (literal entre aspas) sem quebrar o documento.
    markdown_json = json.dumps(_read_doc(), ensure_ascii=False)
    body = _HTML_SHELL.format(markdown_json=markdown_json)
    return HTMLResponse(
        body,
        headers={"Cache-Control": "public, max-age=300"},
    )
