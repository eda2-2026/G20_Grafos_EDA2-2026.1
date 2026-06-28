"""
wiki_client.py
==============
Cliente HTTP assíncrono para consumo da MediaWiki API (Wikipédia em Português).

Implementa busca de links de saída (outlinks) com suporte a paginação e
busca de links de entrada (backlinks) limitados, ambos com suporte a retry
automático com backoff exponencial.
"""

import asyncio
import logging
from typing import Optional

import aiohttp

from src.config import (
    API_URL,
    MAX_BACKLINKS,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_DELAYS,
    USER_AGENT,
    POLITE_DELAY,
)

logger = logging.getLogger(__name__)

_session: Optional[aiohttp.ClientSession] = None
_request_lock = asyncio.Lock()


async def get_session() -> aiohttp.ClientSession:
    """Retorna uma sessão aiohttp reutilizável para o loop atual."""
    global _session
    if _session is None or _session.closed:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        headers = {"User-Agent": USER_AGENT}
        _session = aiohttp.ClientSession(timeout=timeout, headers=headers)
    return _session


async def close_session() -> None:
    """Fecha a sessão HTTP global se estiver aberta."""
    global _session
    if _session is not None and not _session.closed:
        await _session.close()
        _session = None


async def _make_api_request(params: dict) -> dict:
    """Executa uma requisição GET à API da Wikipédia com retry e backoff.

    Args:
        params: Dicionário de parâmetros de query string.

    Returns:
        Dicionário JSON retornado pela API.

    Raises:
        aiohttp.ClientError | asyncio.TimeoutError: Após esgotar todas as tentativas.
    """
    session = await get_session()
    req_params = dict(params)
    req_params["format"] = "json"

    last_exception: Optional[Exception] = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            async with _request_lock:
                await asyncio.sleep(POLITE_DELAY)
            async with session.get(API_URL, params=req_params) as response:
                if response.status in (429, 500, 502, 503):
                    if attempt < MAX_RETRIES:
                        retry_after = response.headers.get("Retry-After")
                        if retry_after and retry_after.isdigit():
                            delay = int(retry_after)
                        else:
                            base_delay = (
                                RETRY_DELAYS[attempt]
                                if attempt < len(RETRY_DELAYS)
                                else RETRY_DELAYS[-1]
                            )
                            # Para 429, aumenta ligeiramente o tempo de espera para aliviar o rate-limiting da Wikimedia
                            delay = base_delay * 2 if response.status == 429 else base_delay

                        logger.warning(
                            "HTTP %d recebido da API. Tentativa %d/%d. Aguardando %ds...",
                            response.status,
                            attempt + 1,
                            MAX_RETRIES,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        response.raise_for_status()

                response.raise_for_status()
                return await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_exception = e
            if attempt < MAX_RETRIES:
                delay = (
                    RETRY_DELAYS[attempt]
                    if attempt < len(RETRY_DELAYS)
                    else RETRY_DELAYS[-1]
                )
                logger.warning(
                    "Erro de rede (%s) na tentativa %d/%d. Aguardando %ds...",
                    type(e).__name__,
                    attempt + 1,
                    MAX_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                raise e

    if last_exception:
        raise last_exception
    raise RuntimeError("Falha desconhecida ao realizar requisição HTTP.")


async def get_outlinks_batch(titles: list[str], sem: asyncio.Semaphore) -> dict[str, list[str]]:
    """Obtém outlinks para múltiplos artigos da Wikipédia em lote.

    Agrupa requisições de 50 em 50 títulos (limite da API).

    Args:
        titles: Lista de títulos.
        sem:    Semáforo para limitar concorrência das chunks.

    Returns:
        Dicionário mapeando {título: [lista_de_outlinks]}.
    """
    outlinks = {t: [] for t in titles}
    chunks = [titles[i : i + 50] for i in range(0, len(titles), 50)]
    total_chunks = len(chunks)
    completed_chunks = 0

    async def fetch_chunk(chunk: list[str]) -> None:
        nonlocal completed_chunks
        async with sem:
            params: dict[str, str | int] = {
                "action": "query",
                "prop": "links",
                "titles": "|".join(chunk),
                "plnamespace": 0,
                "pllimit": 500,
            }
            while True:
                data = await _make_api_request(params)
                pages = data.get("query", {}).get("pages", {})
                for page in pages.values():
                    title = page.get("title", "")
                    if title in outlinks:
                        for link in page.get("links", []):
                            if link.get("ns") == 0:
                                outlinks[title].append(link.get("title", ""))
                cont = data.get("continue")
                if cont and isinstance(cont, dict):
                    params.update(cont)
                else:
                    break
        completed_chunks += 1
        if completed_chunks % max(1, total_chunks // 4) == 0 or completed_chunks == total_chunks:
            logger.debug(f"  [Outlinks] Chunks processados: {completed_chunks}/{total_chunks}")

    if chunks:
        await asyncio.gather(*[fetch_chunk(c) for c in chunks])

    return outlinks


async def get_backlinks_batch(titles: list[str], sem: asyncio.Semaphore) -> dict[str, list[str]]:
    """Obtém backlinks para múltiplos artigos da Wikipédia em lote.

    Agrupa requisições de 50 em 50 títulos (limite da API).

    Args:
        titles: Lista de títulos de destino.
        sem:    Semáforo para limitar concorrência das chunks.

    Returns:
        Dicionário mapeando {título: [lista_de_backlinks]}.
    """
    backlinks = {t: [] for t in titles}
    chunks = [titles[i : i + 50] for i in range(0, len(titles), 50)]
    total_chunks = len(chunks)
    completed_chunks = 0

    async def fetch_chunk(chunk: list[str]) -> None:
        nonlocal completed_chunks
        async with sem:
            params: dict[str, str | int] = {
                "action": "query",
                "prop": "linkshere",
                "titles": "|".join(chunk),
                "lhnamespace": 0,
                "lhlimit": MAX_BACKLINKS,
            }
            data = await _make_api_request(params)
            pages = data.get("query", {}).get("pages", {})
            for page in pages.values():
                title = page.get("title", "")
                if title in backlinks:
                    for link in page.get("linkshere", []):
                        if link.get("ns") == 0 or "ns" not in link:
                            backlinks[title].append(link.get("title", ""))
        completed_chunks += 1
        if completed_chunks % max(1, total_chunks // 4) == 0 or completed_chunks == total_chunks:
            logger.debug(f"  [Backlinks] Chunks processados: {completed_chunks}/{total_chunks}")

    if chunks:
        await asyncio.gather(*[fetch_chunk(c) for c in chunks])

    return backlinks
