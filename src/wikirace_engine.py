"""
wikirace_engine.py
==================
Motor de Busca Bidirecional em Largura (Bidirectional BFS) Assíncrono.

Responsabilidades:
  - Expandir os nós da fronteira de forma concorrente via asyncio.gather +
    asyncio.Semaphore para respeitar os limites de rede.
  - Manter dois caches isolados (outlinks / backlinks) para evitar chamadas
    duplicadas à API na mesma execução.
  - Detectar a interseção entre os dois lados da busca e reconstruir o
    caminho completo (Origem → Interseção → Destino).

Contrato com o Membro A (wiki_client.py):
  - async def get_outlinks(title: str) -> list[str]
  - async def get_backlinks(title: str) -> list[str]

Contrato com o Membro A (models.py):
  - @dataclass class Node: title: str, parent: str | None, depth: int
"""

import asyncio
import logging
from collections import deque
from typing import Optional

# ---------------------------------------------------------------------------
# Importações do Membro A — serão substituídas pelos módulos reais quando
# o wiki_client.py estiver pronto. Durante os testes, estas funções são
# "mockadas" via unittest.mock.patch.
# ---------------------------------------------------------------------------
from src.wiki_client import get_backlinks_batch, get_outlinks_batch
from src.config import SEMAPHORE_LIMIT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes de configuração local do motor.
# Podem ser sobrescritas via src/config.py quando o Membro A finalizar.
# ---------------------------------------------------------------------------
_DEFAULT_CONCURRENCY: int = SEMAPHORE_LIMIT   # Conexões simultâneas máximas
_MAX_DEPTH: int = 6              # Profundidade máxima de cada lado da busca


# ===========================================================================
# Funções auxiliares de cache
# ===========================================================================

async def _fetch_outlinks_cached_batch(
    titles: list[str],
    cache: dict[str, list[str]],
    sem: asyncio.Semaphore,
) -> None:
    """Retorna os links de saída para múltiplos títulos em lote e popula o cache."""
    to_fetch = [t for t in titles if t not in cache]
    if to_fetch:
        logger.debug("Cache MISS outlinks: %d nós. Buscando em lote...", len(to_fetch))
        results = await get_outlinks_batch(to_fetch, sem)
        cache.update(results)
    else:
        logger.debug("Cache HIT outlinks para todos %d nós deste nível.", len(titles))


async def _fetch_backlinks_cached_batch(
    titles: list[str],
    cache: dict[str, list[str]],
    sem: asyncio.Semaphore,
) -> None:
    """Retorna os links de entrada para múltiplos títulos em lote e popula o cache."""
    to_fetch = [t for t in titles if t not in cache]
    if to_fetch:
        logger.debug("Cache MISS backlinks: %d nós. Buscando em lote...", len(to_fetch))
        results = await get_backlinks_batch(to_fetch, sem)
        cache.update(results)
    else:
        logger.debug("Cache HIT backlinks para todos %d nós deste nível.", len(titles))


# ===========================================================================
# Expansão de nível (fronteira completa de um lado da busca)
# ===========================================================================


async def _expand_level_with_parents(
    frontier: deque[str],
    visited: dict[str, Optional[str]],
    fetch_batch_fn,
    cache: dict[str, list[str]],
    sem: asyncio.Semaphore,
) -> None:
    """Expande todos os nós do nível atual utilizando requisições em lote.

    Esta versão é usada durante a busca real pois o mapa de pais precisa ser
    preenchido para que a reconstrução de caminho funcione.
    """
    current_level: list[str] = list(frontier)
    frontier.clear()

    # Dispara a busca em lote, que popula o dicionário 'cache' in-place
    await fetch_batch_fn(current_level, cache, sem)

    # Processa os resultados diretamente do cache
    for parent_title in current_level:
        neighbors = cache.get(parent_title, [])
        for neighbor in neighbors:
            if neighbor not in visited:
                visited[neighbor] = parent_title   # registra o pai real
                frontier.append(neighbor)


# ===========================================================================
# Reconstrução do caminho
# ===========================================================================

def _reconstruct_path(
    meeting_node: str,
    parents_fwd: dict[str, Optional[str]],
    parents_bwd: dict[str, Optional[str]],
    origin: str,
    destination: str,
) -> list[str]:
    """Reconstrói o caminho completo a partir dos mapas de pais.

    O Bidirectional BFS mantém dois mapas de pais:
      - parents_fwd: construído a partir da origem (outlinks).
      - parents_bwd: construído a partir do destino (backlinks).

    O caminho final é: Origem → ... → meeting_node → ... → Destino.

    Args:
        meeting_node:  Nó onde as duas buscas se encontraram.
        parents_fwd:   Mapa de pais do lado da origem.
        parents_bwd:   Mapa de pais do lado do destino.
        origin:        Título da página de origem.
        destination:   Título da página de destino.

    Returns:
        Lista ordenada de títulos representando o caminho mais curto.
    """
    # --- Metade dianteira: meeting_node → origem (percorrendo ao contrário) ---
    path_forward: list[str] = []
    node: Optional[str] = meeting_node
    while node is not None:
        path_forward.append(node)
        node = parents_fwd.get(node)

    path_forward.reverse()  # agora está: origem → ... → meeting_node

    # --- Metade traseira: meeting_node → destino (direto) ---
    path_backward: list[str] = []
    node = parents_bwd.get(meeting_node)  # não duplicar o meeting_node
    while node is not None:
        path_backward.append(node)
        node = parents_bwd.get(node)

    # Combina as duas metades
    full_path = path_forward + path_backward

    logger.info(
        "Caminho reconstruído (%d passos): %s",
        len(full_path) - 1,
        " → ".join(full_path),
    )
    return full_path


# ===========================================================================
# Ponto de entrada principal
# ===========================================================================

async def bidirectional_bfs(
    origin: str,
    destination: str,
    concurrency: int = _DEFAULT_CONCURRENCY,
    max_depth: int = _MAX_DEPTH,
) -> tuple[list[str], dict[str, Optional[str]], dict[str, Optional[str]]]:
    """Executa o Bidirectional BFS Assíncrono entre dois artigos da Wikipedia.

    A busca alterna entre expandir um nível a partir da origem (usando
    outlinks) e um nível a partir do destino (usando backlinks limitados).
    Pára assim que qualquer nó for descoberto por **ambos** os lados.

    Args:
        origin:      Título do artigo de partida (ex: "Banana").
        destination: Título do artigo de chegada (ex: "Física quântica").
        concurrency: Número máximo de requisições HTTP simultâneas.
        max_depth:   Profundidade máxima de exploração por lado. Evita
                     buscas infinitas caso os artigos sejam muito distantes.

    Returns:
        Uma tupla com três elementos:
          [0] path        — Lista de títulos do caminho mais curto encontrado.
                            Lista vazia se não houver caminho dentro do limite.
          [1] parents_fwd — Mapa de pais do lado da origem (para visualização).
          [2] parents_bwd — Mapa de pais do lado do destino (para visualização).

    Raises:
        ValueError: Se origin e destination forem iguais.
    """
    if origin == destination:
        raise ValueError(
            f"Origem e destino são iguais: '{origin}'. "
            "Não há caminho a percorrer."
        )

    logger.info("Iniciando Bidirectional BFS: '%s' → '%s'", origin, destination)

    # --- Estruturas de controle ---
    sem = asyncio.Semaphore(concurrency)

    # Caches isolados: nunca misturam outlinks com backlinks
    cache_outlinks: dict[str, list[str]] = {}
    cache_backlinks: dict[str, list[str]] = {}

    # Mapas de pais: { título_do_nó → título_do_pai, ou None para a raiz }
    parents_fwd: dict[str, Optional[str]] = {origin: None}
    parents_bwd: dict[str, Optional[str]] = {destination: None}

    # Filas de fronteira
    frontier_fwd: deque[str] = deque([origin])
    frontier_bwd: deque[str] = deque([destination])

    # --- Caso trivial: origem e destino são vizinhos diretos ---
    if destination in parents_fwd:
        return [origin, destination], parents_fwd, parents_bwd

    depth_fwd: int = 0
    depth_bwd: int = 0

    # --- Loop principal ---
    while frontier_fwd or frontier_bwd:

        # ---- Expandir lado da origem (outlinks) ----
        if frontier_fwd and depth_fwd < max_depth:
            logger.debug(
                "Expandindo lado FWD — profundidade %d, fronteira: %d nós",
                depth_fwd, len(frontier_fwd),
            )
            await _expand_level_with_parents(
                frontier_fwd, parents_fwd,
                _fetch_outlinks_cached_batch, cache_outlinks, sem,
            )
            depth_fwd += 1

            # Verifica interseção após expansão do lado FWD
            for node in parents_fwd:
                if node in parents_bwd:
                    logger.info("Interseção encontrada no nó: '%s'", node)
                    path = _reconstruct_path(
                        node, parents_fwd, parents_bwd, origin, destination
                    )
                    return path, parents_fwd, parents_bwd

        # ---- Expandir lado do destino (backlinks) ----
        if frontier_bwd and depth_bwd < max_depth:
            logger.debug(
                "Expandindo lado BWD — profundidade %d, fronteira: %d nós",
                depth_bwd, len(frontier_bwd),
            )
            await _expand_level_with_parents(
                frontier_bwd, parents_bwd,
                _fetch_backlinks_cached_batch, cache_backlinks, sem,
            )
            depth_bwd += 1

            # Verifica interseção após expansão do lado BWD
            for node in parents_bwd:
                if node in parents_fwd:
                    logger.info("Interseção encontrada no nó: '%s'", node)
                    path = _reconstruct_path(
                        node, parents_fwd, parents_bwd, origin, destination
                    )
                    return path, parents_fwd, parents_bwd

        # Sem fronteira ativa: grafo desconexo dentro do limite de profundidade
        if not frontier_fwd and not frontier_bwd:
            break

    logger.warning(
        "Nenhum caminho encontrado entre '%s' e '%s' "
        "dentro do limite de profundidade %d.",
        origin, destination, max_depth,
    )
    return [], parents_fwd, parents_bwd


# ===========================================================================
# Estatísticas de execução (opcional — consumidas pelo main.py do Membro A)
# ===========================================================================

def get_cache_stats(
    cache_outlinks: dict[str, list[str]],
    cache_backlinks: dict[str, list[str]],
) -> dict[str, int]:
    """Retorna um resumo das entradas armazenadas nos caches.

    Args:
        cache_outlinks:  Cache de outlinks da última execução.
        cache_backlinks: Cache de backlinks da última execução.

    Returns:
        Dicionário com contadores de entradas em cada cache.
    """
    return {
        "outlinks_cached": len(cache_outlinks),
        "backlinks_cached": len(cache_backlinks),
        "total_cached": len(cache_outlinks) + len(cache_backlinks),
    }
