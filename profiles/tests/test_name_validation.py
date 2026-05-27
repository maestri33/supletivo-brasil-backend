"""Testes de normalização e validação de nome.

Cobre:
- Normalização: trim agressivo, unicode NFC, capitalização inteligente
- Validação: min letras, max size, bloqueio de símbolos/números/nonsense/blacklist
- Canonicalização: representação interna para dedup/busca
"""

from httpx import AsyncClient

VALID_CPF = "52998224725"


async def _criar(client: AsyncClient, external_id: str, cpf: str = None) -> None:
    await client.post(
        "/api/v1/profiles", json={"external_id": external_id, "cpf": cpf or VALID_CPF}
    )


async def _patch(client: AsyncClient, external_id: str, field: str, value: str):
    return await client.patch(f"/api/v1/profiles/{external_id}", json={field: value})


# ── Normalização: deve aceitar e transformar ───────────────────────────


async def test_normalize_trim_agressivo(client: AsyncClient) -> None:
    """Espaços duplos, tabs, newlines viram espaço simples."""
    await _criar(client, "nt1")
    resp = await _patch(client, "nt1", "name", "   Victor   \t\nMaestri   ")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Victor Maestri"


async def test_normalize_unicode_nfc(client: AsyncClient) -> None:
    """Unicode combinado normaliza para NFC (João → João)."""
    await _criar(client, "nt2")
    # 'João' com til combinado (NFD: João)
    nfd = "João Silva"
    resp = await _patch(client, "nt2", "name", nfd)
    assert resp.status_code == 200
    assert resp.json()["name"] == "João Silva"


async def test_normalize_capitalize_simples(client: AsyncClient) -> None:
    """Tudo minúsculo vira Title Case."""
    await _criar(client, "nt3")
    resp = await _patch(client, "nt3", "name", "victor maestri")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Victor Maestri"


async def test_normalize_conectivos_minusculos(client: AsyncClient) -> None:
    """da, de, do, das, dos, e ficam minúsculos."""
    await _criar(client, "nt4")
    resp = await _patch(client, "nt4", "name", "josé da silva")
    assert resp.status_code == 200
    assert resp.json()["name"] == "José da Silva"


async def test_normalize_dos_santos(client: AsyncClient) -> None:
    await _criar(client, "nt5")
    resp = await _patch(client, "nt5", "name", "joão dos santos")
    assert resp.status_code == 200
    assert resp.json()["name"] == "João dos Santos"


async def test_normalize_apostrofo_d_avila(client: AsyncClient) -> None:
    """D'Ávila mantém capitalização após apóstrofo."""
    await _criar(client, "nt6")
    resp = await _patch(client, "nt6", "name", "maria d'ávila")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Maria D'Ávila"


async def test_normalize_oconnor(client: AsyncClient) -> None:
    await _criar(client, "nt7")
    resp = await _patch(client, "nt7", "name", "john o'connor")
    assert resp.status_code == 200
    assert resp.json()["name"] == "John O'Connor"


async def test_normalize_mother_name(client: AsyncClient) -> None:
    """mother_name também passa pela normalização."""
    await _criar(client, "nt8")
    resp = await _patch(client, "nt8", "mother_name", "  maria   da silva  ")
    assert resp.status_code == 200
    assert resp.json()["mother_name"] == "Maria da Silva"


# ── Casos que devem ser aceitos ────────────────────────────────────────


async def test_aceitar_nome_simples(client: AsyncClient) -> None:
    await _criar(client, "ac1")
    resp = await _patch(client, "ac1", "name", "Victor")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Victor"


async def test_aceitar_nome_completo(client: AsyncClient) -> None:
    await _criar(client, "ac2")
    resp = await _patch(client, "ac2", "name", "Victor Maestri")
    assert resp.status_code == 200


async def test_aceitar_joao(client: AsyncClient) -> None:
    await _criar(client, "ac3")
    resp = await _patch(client, "ac3", "name", "João")
    assert resp.status_code == 200


async def test_aceitar_ana_clara(client: AsyncClient) -> None:
    await _criar(client, "ac4")
    resp = await _patch(client, "ac4", "name", "Ana-Clara")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Ana-Clara"


async def test_aceitar_d_avila(client: AsyncClient) -> None:
    await _criar(client, "ac5")
    resp = await _patch(client, "ac5", "name", "D'Ávila")
    assert resp.status_code == 200


async def test_aceitar_ideogramas(client: AsyncClient) -> None:
    await _criar(client, "ac6")
    resp = await _patch(client, "ac6", "name", "李小龙")
    assert resp.status_code == 200


async def test_aceitar_arabico(client: AsyncClient) -> None:
    await _criar(client, "ac7")
    resp = await _patch(client, "ac7", "name", "محمد")
    assert resp.status_code == 200


async def test_aceitar_nome_vazio(client: AsyncClient) -> None:
    """Nome vazio é permitido (compatível com onboarding incompleto)."""
    await _criar(client, "ac8")
    resp = await _patch(client, "ac8", "name", "")
    assert resp.status_code == 200
    assert resp.json()["name"] == ""


# ── Rejeições ──────────────────────────────────────────────────────────


async def test_rejeitar_apenas_numeros(client: AsyncClient) -> None:
    await _criar(client, "rj1")
    resp = await _patch(client, "rj1", "name", "12345")
    assert resp.status_code == 422


async def test_rejeitar_exclamacoes(client: AsyncClient) -> None:
    await _criar(client, "rj2")
    resp = await _patch(client, "rj2", "name", "!!!!")
    assert resp.status_code == 422


async def test_rejeitar_underscores(client: AsyncClient) -> None:
    await _criar(client, "rj3")
    resp = await _patch(client, "rj3", "name", "____")
    assert resp.status_code == 422


async def test_rejeitar_script_tag(client: AsyncClient) -> None:
    await _criar(client, "rj4")
    resp = await _patch(client, "rj4", "name", "<script>")
    assert resp.status_code == 422


async def test_rejeitar_emojis(client: AsyncClient) -> None:
    await _criar(client, "rj5")
    resp = await _patch(client, "rj5", "name", "Victor 🙂")
    assert resp.status_code == 422


async def test_rejeitar_apenas_duas_letras(client: AsyncClient) -> None:
    """'aa' tem 2 letras mas baixa entropia (repetição)."""
    await _criar(client, "rj6")
    resp = await _patch(client, "rj6", "name", "aa")
    assert resp.status_code == 422


async def test_rejeitar_blacklist_admin(client: AsyncClient) -> None:
    await _criar(client, "rj7")
    resp = await _patch(client, "rj7", "name", "admin")
    assert resp.status_code == 422


async def test_rejeitar_blacklist_root(client: AsyncClient) -> None:
    await _criar(client, "rj8")
    resp = await _patch(client, "rj8", "name", "root")
    assert resp.status_code == 422


async def test_rejeitar_blacklist_null(client: AsyncClient) -> None:
    await _criar(client, "rj9")
    resp = await _patch(client, "rj9", "name", "null")
    assert resp.status_code == 422


async def test_rejeitar_blacklist_undefined(client: AsyncClient) -> None:
    await _criar(client, "rj10")
    resp = await _patch(client, "rj10", "name", "undefined")
    assert resp.status_code == 422


async def test_rejeitar_blacklist_system(client: AsyncClient) -> None:
    await _criar(client, "rj11")
    resp = await _patch(client, "rj11", "name", "system")
    assert resp.status_code == 422


async def test_rejeitar_blacklist_suporte(client: AsyncClient) -> None:
    await _criar(client, "rj12")
    resp = await _patch(client, "rj12", "name", "suporte")
    assert resp.status_code == 422


async def test_rejeitar_separadores_consecutivos(client: AsyncClient) -> None:
    """Victor-----Maestri bloqueado."""
    await _criar(client, "rj13")
    resp = await _patch(client, "rj13", "name", "Victor-----Maestri")
    assert resp.status_code == 422


async def test_rejeitar_apostrofos_consecutivos(client: AsyncClient) -> None:
    await _criar(client, "rj14")
    resp = await _patch(client, "rj14", "name", "Victor'''Maestri")
    assert resp.status_code == 422


async def test_rejeitar_nonsense_repeticao(client: AsyncClient) -> None:
    """aaaaaa bloqueado por baixa entropia."""
    await _criar(client, "rj15")
    resp = await _patch(client, "rj15", "name", "aaaaaa")
    assert resp.status_code == 422


async def test_rejeitar_nonsense_alternante(client: AsyncClient) -> None:
    """ababab bloqueado por padrão alternante."""
    await _criar(client, "rj16")
    resp = await _patch(client, "rj16", "name", "ababab")
    assert resp.status_code == 422


async def test_rejeitar_nome_maior_120_chars(client: AsyncClient) -> None:
    await _criar(client, "rj17")
    resp = await _patch(client, "rj17", "name", "A" * 121)
    assert resp.status_code == 422


async def test_rejeitar_apenas_hifen_com_uma_letra(client: AsyncClient) -> None:
    """--a-- tem só 1 letra, menos que mínimo de 2."""
    await _criar(client, "rj18")
    resp = await _patch(client, "rj18", "name", "--a--")
    assert resp.status_code == 422


# ── Edge cases ──────────────────────────────────────────────────────────


async def test_nome_com_hifen_valido(client: AsyncClient) -> None:
    """Hífen é permitido se fizer parte do nome."""
    await _criar(client, "ed1")
    resp = await _patch(client, "ed1", "name", "Ana-Clara Moreira")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Ana-Clara Moreira"


async def test_nome_com_cedilha(client: AsyncClient) -> None:
    await _criar(client, "ed2")
    resp = await _patch(client, "ed2", "name", "açucena")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Açucena"


async def test_nome_max_120_ok(client: AsyncClient) -> None:
    await _criar(client, "ed3")
    # Nome realista com 119 caracteres (menor que max 120)
    nome = "A" + "b c" * 39  # 1 + 3*39 = 118 chars, com espaços
    nome = nome[:119]
    resp = await _patch(client, "ed3", "name", nome)
    assert resp.status_code == 200
    assert len(resp.json()["name"]) <= 120


async def test_nome_com_ponto(client: AsyncClient) -> None:
    """Ponto é tratado — vira parte do nome (ex: abreviações)."""
    await _criar(client, "ed4")
    resp = await _patch(client, "ed4", "name", "J. R. R. Tolkien")
    assert resp.status_code == 200
