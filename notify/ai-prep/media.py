"""
Caminho fixo para arquivos de midia gerados.

Estrutura: data/public/media/<tipo>/<uuid>.<ext>
"""

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_ROOT = os.path.join(PROJECT_ROOT, "data", "public", "media")


def save_media(tipo: str, filename: str, data: bytes) -> str:
    """Salva em data/public/media/<tipo>/<filename>. Retorna o path completo."""
    path = os.path.join(MEDIA_ROOT, tipo)
    os.makedirs(path, exist_ok=True)
    filepath = os.path.join(path, filename)
    with open(filepath, "wb") as f:
        f.write(data)
    return filepath
