"""
test_client.py
==============
Testes unitários para o cliente HTTP assíncrono (src.wiki_client).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import asyncio
import aiohttp
import pytest

from src.config import MAX_BACKLINKS
from src.wiki_client import (
    _make_api_request,
    close_session,
    get_backlinks_batch,
    get_outlinks_batch,
)


@pytest.fixture(autouse=True)
async def cleanup_session():
    yield
    await close_session()


async def test_get_outlinks_batch_pagination():
    """Verifica se get_outlinks_batch consome páginas subsequentes quando a API retorna 'continue'."""
    page1_resp = {
        "query": {
            "pages": {
                "1": {
                    "title": "Banana",
                    "links": [
                        {"ns": 0, "title": "Fruta"},
                        {"ns": 0, "title": "Planta"},
                    ],
                }
            }
        },
        "continue": {"plcontinue": "1|0|Torta", "continue": "||"},
    }
    page2_resp = {
        "query": {
            "pages": {
                "1": {"title": "Banana", "links": [{"ns": 0, "title": "Torta"}]}
            }
        }
    }

    mock_make_req = AsyncMock(side_effect=[page1_resp, page2_resp])
    sem = asyncio.Semaphore(1)

    with patch("src.wiki_client._make_api_request", mock_make_req):
        outlinks = await get_outlinks_batch(["Banana"], sem)

    assert outlinks["Banana"] == ["Fruta", "Planta", "Torta"]
    assert mock_make_req.call_count == 2


async def test_get_outlinks_batch_namespace_filtering():
    """Verifica se links fora do namespace 0 são descartados."""
    api_resp = {
        "query": {
            "pages": {
                "1": {
                    "title": "Artigo",
                    "links": [
                        {"ns": 0, "title": "ArtigoValido"},
                        {"ns": 14, "title": "Categoria:Frutas"},
                        {"ns": 0, "title": "OutroValido"},
                    ],
                }
            }
        }
    }

    sem = asyncio.Semaphore(1)
    with patch(
        "src.wiki_client._make_api_request", AsyncMock(return_value=api_resp)
    ):
        outlinks = await get_outlinks_batch(["Artigo"], sem)

    assert outlinks["Artigo"] == ["ArtigoValido", "OutroValido"]


async def test_get_backlinks_batch_limit_and_no_pagination():
    """Verifica se get_backlinks_batch passa lhlimit correto e faz apenas 1 requisição por chunk."""
    api_resp = {
        "query": {
            "pages": {
                "1": {
                    "title": "Destino",
                    "linkshere": [
                        {"ns": 0, "title": "Origem1"},
                        {"ns": 0, "title": "Origem2"},
                    ]
                }
            }
        }
    }

    mock_make_req = AsyncMock(return_value=api_resp)
    sem = asyncio.Semaphore(1)

    with patch("src.wiki_client._make_api_request", mock_make_req):
        backlinks = await get_backlinks_batch(["Destino"], sem)

    assert backlinks["Destino"] == ["Origem1", "Origem2"]
    assert mock_make_req.call_count == 1
    call_args = mock_make_req.call_args[0][0]
    assert call_args["lhlimit"] == MAX_BACKLINKS
    assert call_args["prop"] == "linkshere"


async def test_make_api_request_retry_success():
    """Verifica se _make_api_request faz retry em erro HTTP 429 e sucede em seguida."""
    mock_resp_429 = MagicMock()
    mock_resp_429.status = 429
    mock_resp_429.raise_for_status = MagicMock()

    mock_resp_200 = MagicMock()
    mock_resp_200.status = 200
    mock_resp_200.raise_for_status = MagicMock()
    mock_resp_200.json = AsyncMock(return_value={"result": "ok"})

    ctx_429 = MagicMock()
    ctx_429.__aenter__ = AsyncMock(return_value=mock_resp_429)
    ctx_429.__aexit__ = AsyncMock(return_value=None)

    ctx_200 = MagicMock()
    ctx_200.__aenter__ = AsyncMock(return_value=mock_resp_200)
    ctx_200.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get.side_effect = [ctx_429, ctx_200]

    with (
        patch("src.wiki_client.get_session", AsyncMock(return_value=mock_session)),
        patch("asyncio.sleep", AsyncMock()),
    ):
        res = await _make_api_request({"action": "query"})

    assert res == {"result": "ok"}
    assert mock_session.get.call_count == 2


async def test_make_api_request_retry_exhausted():
    """Verifica se _make_api_request lança exceção após esgotar retries."""
    mock_resp_500 = MagicMock()
    mock_resp_500.status = 500
    mock_resp_500.raise_for_status.side_effect = aiohttp.ClientResponseError(
        request_info=MagicMock(), history=(), status=500, message="Internal Error"
    )

    ctx_500 = MagicMock()
    ctx_500.__aenter__ = AsyncMock(return_value=mock_resp_500)
    ctx_500.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get.return_value = ctx_500

    with (
        patch("src.wiki_client.get_session", AsyncMock(return_value=mock_session)),
        patch("asyncio.sleep", AsyncMock()),
    ):
        with pytest.raises(aiohttp.ClientResponseError):
            await _make_api_request({"action": "query"})
