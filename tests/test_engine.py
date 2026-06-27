"""
test_engine.py
==============
Testes do motor de busca bidirecional (wikirace_engine.bidirectional_bfs).

Estratégia:
  - As funções `get_outlinks` e `get_backlinks` do Membro A são substituídas
    por AsyncMock que retornam os dados do grafo fictício definido no conftest.
  - Isso garante que os testes rodem sem conexão de rede e de forma
    determinística, validando apenas a lógica algorítmica do BFS.

Cenários cobertos:
  1. Caminho simples de comprimento 3 (4 nós).
  2. Origem e destino são vizinhos diretos (comprimento 1).
  3. Origem e destino são a mesma página (deve lançar ValueError).
  4. Sem caminho dentro do limite de profundidade (retorna lista vazia).
  5. O caminho retornado começa pela origem e termina pelo destino.
"""

import pytest
from unittest.mock import AsyncMock, patch

from src.wikirace_engine import bidirectional_bfs
from tests.conftest import ORIGIN, DESTINATION, OUTLINKS_MAP, BACKLINKS_MAP


# ---------------------------------------------------------------------------
# Helpers de mock
# ---------------------------------------------------------------------------

def _make_outlinks_mock(outlinks_map: dict[str, list[str]]) -> AsyncMock:
    """Cria um AsyncMock que simula get_outlinks usando o mapa fornecido."""
    async def _mock(title: str) -> list[str]:
        return outlinks_map.get(title, [])
    return AsyncMock(side_effect=_mock)


def _make_backlinks_mock(backlinks_map: dict[str, list[str]]) -> AsyncMock:
    """Cria um AsyncMock que simula get_backlinks usando o mapa fornecido."""
    async def _mock(title: str) -> list[str]:
        return backlinks_map.get(title, [])
    return AsyncMock(side_effect=_mock)


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

async def test_finds_optimal_path(simple_outlinks, simple_backlinks, expected_path):
    """O BFS bidirecional deve encontrar o caminho ótimo de comprimento 3."""
    mock_out = _make_outlinks_mock(simple_outlinks)
    mock_back = _make_backlinks_mock(simple_backlinks)

    with (
        patch("src.wikirace_engine.get_outlinks", mock_out),
        patch("src.wikirace_engine.get_backlinks", mock_back),
    ):
        path, _, _ = await bidirectional_bfs(ORIGIN, DESTINATION)

    assert path == expected_path, (
        f"Esperado {expected_path}, obtido {path}"
    )


async def test_path_length_is_correct(simple_outlinks, simple_backlinks, expected_path):
    """O comprimento do caminho encontrado deve ser igual ao do caminho ótimo."""
    mock_out = _make_outlinks_mock(simple_outlinks)
    mock_back = _make_backlinks_mock(simple_backlinks)

    with (
        patch("src.wikirace_engine.get_outlinks", mock_out),
        patch("src.wikirace_engine.get_backlinks", mock_back),
    ):
        path, _, _ = await bidirectional_bfs(ORIGIN, DESTINATION)

    assert len(path) == len(expected_path)


async def test_direct_neighbors():
    """Quando destino é vizinho direto da origem, o caminho deve ter 2 nós."""
    outlinks = {"Origem": ["Destino"], "Destino": []}
    backlinks = {"Destino": ["Origem"], "Origem": []}

    mock_out = _make_outlinks_mock(outlinks)
    mock_back = _make_backlinks_mock(backlinks)

    with (
        patch("src.wikirace_engine.get_outlinks", mock_out),
        patch("src.wikirace_engine.get_backlinks", mock_back),
    ):
        path, _, _ = await bidirectional_bfs("Origem", "Destino")

    assert path == ["Origem", "Destino"]


async def test_same_origin_and_destination_raises():
    """Origem e destino iguais devem lançar ValueError antes de fazer qualquer requisição."""
    with pytest.raises(ValueError, match="iguais"):
        await bidirectional_bfs("Banana", "Banana")


async def test_no_path_within_depth_limit():
    """Grafo desconexo deve retornar lista vazia sem travar."""
    # Grafo em que Origem e Destino não têm nenhum link em comum
    outlinks = {"Origem": ["A"], "A": [], "Destino": []}
    backlinks = {"Destino": [], "A": [], "Origem": []}

    mock_out = _make_outlinks_mock(outlinks)
    mock_back = _make_backlinks_mock(backlinks)

    with (
        patch("src.wikirace_engine.get_outlinks", mock_out),
        patch("src.wikirace_engine.get_backlinks", mock_back),
    ):
        path, _, _ = await bidirectional_bfs("Origem", "Destino", max_depth=2)

    assert path == [], f"Esperava lista vazia para grafo desconexo, obteve {path}"


async def test_path_starts_with_origin_and_ends_with_destination(
    simple_outlinks, simple_backlinks
):
    """O caminho retornado sempre deve começar na origem e terminar no destino."""
    mock_out = _make_outlinks_mock(simple_outlinks)
    mock_back = _make_backlinks_mock(simple_backlinks)

    with (
        patch("src.wikirace_engine.get_outlinks", mock_out),
        patch("src.wikirace_engine.get_backlinks", mock_back),
    ):
        path, _, _ = await bidirectional_bfs(ORIGIN, DESTINATION)

    assert path[0] == ORIGIN,       f"Primeiro nó deveria ser '{ORIGIN}', foi '{path[0]}'"
    assert path[-1] == DESTINATION, f"Último nó deveria ser '{DESTINATION}', foi '{path[-1]}'"


async def test_returns_parents_maps(simple_outlinks, simple_backlinks):
    """O engine deve retornar os mapas de pais FWD e BWD não-vazios."""
    mock_out = _make_outlinks_mock(simple_outlinks)
    mock_back = _make_backlinks_mock(simple_backlinks)

    with (
        patch("src.wikirace_engine.get_outlinks", mock_out),
        patch("src.wikirace_engine.get_backlinks", mock_back),
    ):
        path, parents_fwd, parents_bwd = await bidirectional_bfs(ORIGIN, DESTINATION)

    assert ORIGIN in parents_fwd, "parents_fwd deve conter a origem"
    assert DESTINATION in parents_bwd, "parents_bwd deve conter o destino"
