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
)

logger = logging.getLogger(__name__)

_session: Optional[aiohttp.ClientSession] = None


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


async def get_outlinks(title: str) -> list[str]:
    """Obtém todos os links de saída (outlinks) de um artigo da Wikipédia.

    Lida automaticamente com paginação caso o artigo possua mais de 500 links.
    Retorna apenas links para artigos do namespace 0 (artigos principais).

    Args:
        title: Título do artigo.

    Returns:
        Lista de títulos dos artigos para os quais este artigo aponta.
    """
    outlinks: list[str] = []
    params: dict[str, str | int] = {
        "action": "query",
        "prop": "links",
        "titles": title,
        "plnamespace": 0,
        "pllimit": 500,
    }

    while True:
        data = await _make_api_request(params)
        pages = data.get("query", {}).get("pages", {})

        for page in pages.values():
            for link in page.get("links", []):
                if link.get("ns") == 0:
                    outlinks.append(link.get("title", ""))

        cont = data.get("continue")
        if cont and isinstance(cont, dict):
            params.update(cont)
        else:
            break

    return outlinks


async def get_backlinks(title: str) -> list[str]:
    """Obtém os links de entrada (backlinks) para um artigo da Wikipédia.

    Não realiza paginação, respeitando o limite máximo de MAX_BACKLINKS.

    Args:
        title: Título do artigo de destino.

    Returns:
        Lista de títulos dos artigos que apontam para este artigo.
    """
    params: dict[str, str | int] = {
        "action": "query",
        "list": "backlinks",
        "bltitle": title,
        "blnamespace": 0,
        "bllimit": MAX_BACKLINKS,
    }

    data = await _make_api_request(params)
    backlinks_data = data.get("query", {}).get("backlinks", [])

    return [
        bl.get("title", "")
        for bl in backlinks_data
        if bl.get("ns") == 0 or "ns" not in bl
    ]
