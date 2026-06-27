"""
test_cache.py
=============
Testes de cache isolado do wikirace_engine.

Garantia central: para um mesmo título, a API simulada (get_outlinks /
get_backlinks) jamais deve ser invocada mais de uma vez durante uma
execução do BFS — independentemente de quantas vezes aquele nó apareça
na fronteira de busca.

Cenários cobertos:
  1. Cache de outlinks: mesmo título não dispara segunda chamada à API.
  2. Cache de backlinks: mesmo título não dispara segunda chamada à API.
  3. Os dois caches são independentes: hit no outlinks não afeta o backlinks.
  4. Títulos distintos geram chamadas distintas (cache não confunde entradas).
  5. Integração end-to-end: ao rodar o BFS completo, nenhum título é
     consultado duas vezes no mesmo cache.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, call

from src.wikirace_engine import (
    _fetch_outlinks_cached,
    _fetch_backlinks_cached,
    bidirectional_bfs,
)
from tests.conftest import ORIGIN, DESTINATION, OUTLINKS_MAP, BACKLINKS_MAP


# ---------------------------------------------------------------------------
# Testes unitários das funções de cache isoladas
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_outlinks_cache_hit_prevents_second_api_call():
    """Dois acessos ao mesmo título devem resultar em apenas 1 chamada à API."""
    mock_api = AsyncMock(return_value=["A", "B"])
    cache: dict = {}
    sem = asyncio.Semaphore(20)

    with patch("src.wikirace_engine.get_outlinks", mock_api):
        await _fetch_outlinks_cached("Banana", cache, sem)
        await _fetch_outlinks_cached("Banana", cache, sem)  # deve ser cache HIT

    mock_api.assert_called_once_with("Banana")


@pytest.mark.asyncio
async def test_backlinks_cache_hit_prevents_second_api_call():
    """Dois acessos ao mesmo título (backlinks) resultam em apenas 1 chamada."""
    mock_api = AsyncMock(return_value=["X", "Y"])
    cache: dict = {}
    sem = asyncio.Semaphore(20)

    with patch("src.wikirace_engine.get_backlinks", mock_api):
        await _fetch_backlinks_cached("Destino", cache, sem)
        await _fetch_backlinks_cached("Destino", cache, sem)  # cache HIT

    mock_api.assert_called_once_with("Destino")


@pytest.mark.asyncio
async def test_caches_are_independent():
    """Um hit no cache de outlinks não deve ser confundido com o de backlinks."""
    mock_out = AsyncMock(return_value=["A"])
    mock_back = AsyncMock(return_value=["Z"])
    cache_out: dict = {}
    cache_back: dict = {}
    sem = asyncio.Semaphore(20)

    with (
        patch("src.wikirace_engine.get_outlinks", mock_out),
        patch("src.wikirace_engine.get_backlinks", mock_back),
    ):
        # Popula cache de outlinks para "Artigo"
        await _fetch_outlinks_cached("Artigo", cache_out, sem)
        # Consulta backlinks do mesmo título — deve chamar a API de backlinks
        await _fetch_backlinks_cached("Artigo", cache_back, sem)

    mock_out.assert_called_once_with("Artigo")
    mock_back.assert_called_once_with("Artigo")


@pytest.mark.asyncio
async def test_different_titles_generate_separate_calls():
    """Títulos distintos devem gerar chamadas distintas à API."""
    mock_api = AsyncMock(return_value=[])
    cache: dict = {}
    sem = asyncio.Semaphore(20)

    with patch("src.wikirace_engine.get_outlinks", mock_api):
        await _fetch_outlinks_cached("Banana", cache, sem)
        await _fetch_outlinks_cached("Maçã", cache, sem)

    assert mock_api.call_count == 2
    mock_api.assert_has_calls([call("Banana"), call("Maçã")], any_order=True)


@pytest.mark.asyncio
async def test_cache_returns_correct_value():
    """O valor retornado na segunda chamada (cache HIT) deve ser idêntico ao da primeira."""
    expected_links = ["Link1", "Link2", "Link3"]
    mock_api = AsyncMock(return_value=expected_links)
    cache: dict = {}
    sem = asyncio.Semaphore(20)

    with patch("src.wikirace_engine.get_outlinks", mock_api):
        first  = await _fetch_outlinks_cached("Artigo", cache, sem)
        second = await _fetch_outlinks_cached("Artigo", cache, sem)

    assert first == expected_links
    assert second == expected_links
    assert first is second  # deve ser o mesmo objeto em memória (cache real)


# ---------------------------------------------------------------------------
# Teste de integração: BFS completo não repete chamadas
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bfs_never_calls_same_outlink_twice():
    """Em uma execução completa do BFS, nenhum título deve ser consultado
    mais de uma vez no get_outlinks."""
    call_log: list[str] = []

    async def tracking_outlinks(title: str) -> list[str]:
        call_log.append(title)
        return OUTLINKS_MAP.get(title, [])

    async def tracking_backlinks(title: str) -> list[str]:
        return BACKLINKS_MAP.get(title, [])

    mock_out = AsyncMock(side_effect=tracking_outlinks)
    mock_back = AsyncMock(side_effect=tracking_backlinks)

    with (
        patch("src.wikirace_engine.get_outlinks", mock_out),
        patch("src.wikirace_engine.get_backlinks", mock_back),
    ):
        await bidirectional_bfs(ORIGIN, DESTINATION)

    # Verifica que nenhum título aparece duplicado no log
    duplicates = [t for t in set(call_log) if call_log.count(t) > 1]
    assert not duplicates, (
        f"Os seguintes títulos foram consultados mais de uma vez "
        f"no get_outlinks: {duplicates}"
    )


@pytest.mark.asyncio
async def test_bfs_never_calls_same_backlink_twice():
    """Em uma execução completa do BFS, nenhum título deve ser consultado
    mais de uma vez no get_backlinks."""
    call_log: list[str] = []

    async def tracking_outlinks(title: str) -> list[str]:
        return OUTLINKS_MAP.get(title, [])

    async def tracking_backlinks(title: str) -> list[str]:
        call_log.append(title)
        return BACKLINKS_MAP.get(title, [])

    mock_out = AsyncMock(side_effect=tracking_outlinks)
    mock_back = AsyncMock(side_effect=tracking_backlinks)

    with (
        patch("src.wikirace_engine.get_outlinks", mock_out),
        patch("src.wikirace_engine.get_backlinks", mock_back),
    ):
        await bidirectional_bfs(ORIGIN, DESTINATION)

    duplicates = [t for t in set(call_log) if call_log.count(t) > 1]
    assert not duplicates, (
        f"Os seguintes títulos foram consultados mais de uma vez "
        f"no get_backlinks: {duplicates}"
    )
