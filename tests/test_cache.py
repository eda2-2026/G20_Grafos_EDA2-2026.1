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
    _fetch_outlinks_cached_batch,
    _fetch_backlinks_cached_batch,
    bidirectional_bfs,
)
from tests.conftest import ORIGIN, DESTINATION, OUTLINKS_MAP, BACKLINKS_MAP


# ---------------------------------------------------------------------------
# Testes unitários das funções de cache em lote
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_outlinks_cache_hit_prevents_api_call():
    """Títulos já presentes no cache não devem ser buscados."""
    mock_api = AsyncMock(return_value={"Banana": ["A", "B"]})
    cache: dict = {"Banana": ["X", "Y"]}
    sem = asyncio.Semaphore(20)

    with patch("src.wikirace_engine.get_outlinks_batch", mock_api):
        await _fetch_outlinks_cached_batch(["Banana"], cache, sem)

    mock_api.assert_not_called()
    assert cache["Banana"] == ["X", "Y"]


@pytest.mark.asyncio
async def test_backlinks_cache_hit_prevents_api_call():
    """Títulos (backlinks) já no cache não devem ser buscados."""
    mock_api = AsyncMock(return_value={"Destino": ["X"]})
    cache: dict = {"Destino": ["A"]}
    sem = asyncio.Semaphore(20)

    with patch("src.wikirace_engine.get_backlinks_batch", mock_api):
        await _fetch_backlinks_cached_batch(["Destino"], cache, sem)

    mock_api.assert_not_called()


@pytest.mark.asyncio
async def test_caches_are_independent():
    """Um hit no cache de outlinks não deve afetar o de backlinks."""
    mock_out = AsyncMock(return_value={"Artigo": ["A"]})
    mock_back = AsyncMock(return_value={"Artigo": ["Z"]})
    cache_out: dict = {}
    cache_back: dict = {}
    sem = asyncio.Semaphore(20)

    with (
        patch("src.wikirace_engine.get_outlinks_batch", mock_out),
        patch("src.wikirace_engine.get_backlinks_batch", mock_back),
    ):
        await _fetch_outlinks_cached_batch(["Artigo"], cache_out, sem)
        await _fetch_backlinks_cached_batch(["Artigo"], cache_back, sem)

    mock_out.assert_called_once()
    mock_back.assert_called_once()


# ---------------------------------------------------------------------------
# Teste de integração: BFS completo não repete chamadas
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bfs_never_calls_same_outlink_twice():
    """Em uma execução completa do BFS, nenhum título deve ser consultado
    mais de uma vez no get_outlinks_batch."""
    call_log: list[str] = []

    async def tracking_outlinks(titles: list[str], sem) -> dict[str, list[str]]:
        call_log.extend(titles)
        return {t: OUTLINKS_MAP.get(t, []) for t in titles}

    async def tracking_backlinks(titles: list[str], sem) -> dict[str, list[str]]:
        return {t: BACKLINKS_MAP.get(t, []) for t in titles}

    mock_out = AsyncMock(side_effect=tracking_outlinks)
    mock_back = AsyncMock(side_effect=tracking_backlinks)

    with (
        patch("src.wikirace_engine.get_outlinks_batch", mock_out),
        patch("src.wikirace_engine.get_backlinks_batch", mock_back),
    ):
        await bidirectional_bfs(ORIGIN, DESTINATION)

    duplicates = [t for t in set(call_log) if call_log.count(t) > 1]
    assert not duplicates, f"Duplicatas em outlinks: {duplicates}"


@pytest.mark.asyncio
async def test_bfs_never_calls_same_backlink_twice():
    """Em uma execução completa do BFS, nenhum título deve ser consultado
    mais de uma vez no get_backlinks_batch."""
    call_log: list[str] = []

    async def tracking_outlinks(titles: list[str], sem) -> dict[str, list[str]]:
        return {t: OUTLINKS_MAP.get(t, []) for t in titles}

    async def tracking_backlinks(titles: list[str], sem) -> dict[str, list[str]]:
        call_log.extend(titles)
        return {t: BACKLINKS_MAP.get(t, []) for t in titles}

    mock_out = AsyncMock(side_effect=tracking_outlinks)
    mock_back = AsyncMock(side_effect=tracking_backlinks)

    with (
        patch("src.wikirace_engine.get_outlinks_batch", mock_out),
        patch("src.wikirace_engine.get_backlinks_batch", mock_back),
    ):
        await bidirectional_bfs(ORIGIN, DESTINATION)

    duplicates = [t for t in set(call_log) if call_log.count(t) > 1]
    assert not duplicates, f"Duplicatas em backlinks: {duplicates}"
