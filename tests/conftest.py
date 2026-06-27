"""
conftest.py
===========
Fixtures e configurações compartilhadas entre todos os arquivos de teste.

Contém:
  - Grafos de grafo fictícios simples para teste controlado.
  - Helpers para construir mapas de pais (parents_fwd / parents_bwd)
    sem precisar executar o BFS real.
  - Configuração do pytest-asyncio para que todos os testes async
    sejam detectados automaticamente.
"""

import pytest
import pytest_asyncio  # noqa: F401  (garante que o plugin está registrado)

# ---------------------------------------------------------------------------
# Configuração global do pytest-asyncio
# ---------------------------------------------------------------------------
# Faz com que qualquer função marcada com `async def` seja tratada como
# corrotina de teste sem precisar de @pytest.mark.asyncio em cada uma.
# Requer pytest-asyncio >= 0.21.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Grafos fictícios reutilizáveis nos testes
# ---------------------------------------------------------------------------
#
# Topologia usada na maioria dos testes:
#
#   ORIGEM ──outlinks──► A ──► B ──► DESTINO
#                              │
#   DESTINO ─backlinks─► B ◄───┘
#
# Caminho ótimo esperado: ["Origem", "A", "B", "Destino"]
# Nó de interseção: "B"
# ---------------------------------------------------------------------------

ORIGIN = "Origem"
DESTINATION = "Destino"

# Mapa de outlinks: quem cada artigo aponta
OUTLINKS_MAP: dict[str, list[str]] = {
    "Origem":  ["A", "X"],
    "A":       ["B", "Y"],
    "B":       ["Destino"],
    "X":       ["Y"],
    "Y":       [],
    "Destino": [],
}

# Mapa de backlinks: quem aponta para cada artigo (inverso do grafo)
BACKLINKS_MAP: dict[str, list[str]] = {
    "Destino": ["B"],
    "B":       ["A"],
    "A":       ["Origem"],
    "Y":       ["A", "X"],
    "X":       ["Origem"],
    "Origem":  [],
}


@pytest.fixture
def simple_outlinks() -> dict[str, list[str]]:
    """Retorna o mapa de outlinks do grafo de teste simples."""
    return dict(OUTLINKS_MAP)


@pytest.fixture
def simple_backlinks() -> dict[str, list[str]]:
    """Retorna o mapa de backlinks do grafo de teste simples."""
    return dict(BACKLINKS_MAP)


@pytest.fixture
def expected_path() -> list[str]:
    """Caminho ótimo esperado para o grafo de teste simples."""
    return [ORIGIN, "A", "B", DESTINATION]


@pytest.fixture
def parents_fwd_fixture() -> dict[str, str | None]:
    """Mapa de pais FWD pré-construído para testes de reconstrução de caminho."""
    return {
        ORIGIN: None,
        "A":    ORIGIN,
        "B":    "A",
        "X":    ORIGIN,
        "Y":    "A",
    }


@pytest.fixture
def parents_bwd_fixture() -> dict[str, str | None]:
    """Mapa de pais BWD pré-construído para testes de reconstrução de caminho."""
    return {
        DESTINATION: None,
        "B":         DESTINATION,
    }
