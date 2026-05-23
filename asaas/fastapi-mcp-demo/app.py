"""
FastAPI-MCP Demo — Exemplo completo de API REST exposta como tools MCP.

Estrutura:
  - /items/         → CRUD público (qualquer um chama)
  - /admin/         → Endpoints protegidos (requer token)
  - /mcp            → MCP server público (HTTP transport)
  - /protected-mcp  → MCP server protegido (HTTP transport + auth)
"""

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi_mcp import FastApiMCP, AuthConfig
from pydantic import BaseModel, Field
from typing import Optional

# ---------------------------------------------------------------------------
# App & Auth
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FastAPI-MCP Demo",
    description="API de exemplo demonstrando integração FastAPI + MCP",
    version="1.0.0",
)

security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Valida token Bearer. Em produção, use JWT ou OAuth."""
    if credentials.credentials != "demo-secret-token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )
    return credentials.credentials


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Item(BaseModel):
    """Item do inventário."""
    id: int
    name: str = Field(description="Nome do item")
    price: float = Field(gt=0, description="Preço unitário em reais")
    in_stock: bool = Field(default=True, description="Disponível em estoque")


class ItemCreate(BaseModel):
    """Payload para criar um novo item."""
    name: str = Field(description="Nome do item")
    price: float = Field(gt=0, description="Preço unitário em reais")
    in_stock: bool = Field(default=True, description="Disponível em estoque")


class ItemUpdate(BaseModel):
    """Payload para atualizar um item existente (todos os campos opcionais)."""
    name: Optional[str] = Field(default=None, description="Novo nome")
    price: Optional[float] = Field(default=None, gt=0, description="Novo preço")
    in_stock: Optional[bool] = Field(default=None, description="Disponibilidade")


# ---------------------------------------------------------------------------
# Banco de dados fake
# ---------------------------------------------------------------------------

_db: dict[int, Item] = {
    1: Item(id=1, name="Martelo", price=29.90, in_stock=True),
    2: Item(id=2, name="Chave de fenda", price=14.50, in_stock=True),
    3: Item(id=3, name="Serra circular", price=199.90, in_stock=False),
}


# ---------------------------------------------------------------------------
# Endpoints públicos (tags=["items"])
# ---------------------------------------------------------------------------

@app.get(
    "/items/",
    tags=["items"],
    operation_id="list_items",
    response_model=list[Item],
    description="Lista todos os itens do inventário.",
)
async def list_items(
    skip: int = Query(default=0, description="Itens para pular"),
    limit: int = Query(default=10, description="Máximo de itens"),
) -> list[Item]:
    return list(_db.values())[skip : skip + limit]


@app.get(
    "/items/{item_id}",
    tags=["items"],
    operation_id="get_item",
    response_model=Item,
    description="Obtém um item específico pelo ID.",
)
async def get_item(item_id: int) -> Item:
    if item_id not in _db:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    return _db[item_id]


@app.post(
    "/items/",
    tags=["items"],
    operation_id="create_item",
    response_model=Item,
    status_code=201,
    description="Cria um novo item no inventário.",
)
async def create_item(payload: ItemCreate) -> Item:
    new_id = max(_db.keys()) + 1 if _db else 1
    item = Item(id=new_id, **payload.model_dump())
    _db[new_id] = item
    return item


@app.put(
    "/items/{item_id}",
    tags=["items"],
    operation_id="update_item",
    response_model=Item,
    description="Atualiza um item existente.",
)
async def update_item(item_id: int, payload: ItemUpdate) -> Item:
    if item_id not in _db:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    current = _db[item_id]
    updated = current.model_copy(update=payload.model_dump(exclude_none=True))
    _db[item_id] = updated
    return updated


@app.delete(
    "/items/{item_id}",
    tags=["items"],
    operation_id="delete_item",
    description="Remove um item do inventário.",
)
async def delete_item(item_id: int) -> dict:
    if item_id not in _db:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    del _db[item_id]
    return {"deleted": True, "item_id": item_id}


# ---------------------------------------------------------------------------
# Endpoints administrativos protegidos (tags=["admin"])
# ---------------------------------------------------------------------------

@app.get(
    "/admin/stats",
    tags=["admin"],
    operation_id="admin_stats",
    description="Estatísticas do inventário (requer autenticação).",
)
async def admin_stats(token: str = Depends(verify_token)) -> dict:
    items = list(_db.values())
    in_stock = sum(1 for i in items if i.in_stock)
    return {
        "total_items": len(items),
        "in_stock": in_stock,
        "out_of_stock": len(items) - in_stock,
        "total_value": sum(i.price for i in items),
    }


# ---------------------------------------------------------------------------
# MCP — Servidor público (expõe só endpoints com tag "items")
# ---------------------------------------------------------------------------

public_mcp = FastApiMCP(
    app,
    name="Inventário API (Público)",
    description="MCP server que expõe os endpoints públicos do inventário.",
    include_tags=["items"],
    describe_full_response_schema=True,
    describe_all_responses=True,
)
public_mcp.mount_http(mount_path="/mcp")


# ---------------------------------------------------------------------------
# MCP — Servidor protegido (expõe admin + items, exige token)
# ---------------------------------------------------------------------------

protected_mcp = FastApiMCP(
    app,
    name="Inventário API (Admin)",
    description="MCP server protegido com acesso administrativo completo.",
    exclude_tags=[],  # expõe tudo
    headers=["authorization"],
    auth_config=AuthConfig(
        dependencies=[Depends(security)],
    ),
    describe_full_response_schema=True,
    describe_all_responses=True,
)
protected_mcp.mount_http(mount_path="/protected-mcp")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
