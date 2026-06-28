"""
main.py
=======
Ponto de entrada da aplicação Wikirace.

Interface de linha de comando (CLI) para executar o algoritmo Bidirectional BFS
entre dois artigos da Wikipédia em português, gerando os grafos interativos
e exibindo relatórios de estatísticas no terminal.
"""

import argparse
import asyncio
import logging
import sys
import time
from typing import Optional

from src.visualizer import render_exploration_tree, render_path_only
from src.wiki_client import close_session
from src.wikirace_engine import bidirectional_bfs


def parse_arguments() -> argparse.Namespace:
    """Configura e analisa os argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Wikirace — Encontre o caminho mais curto entre dois artigos da Wikipédia."
    )
    parser.add_argument(
        "origem",
        type=str,
        help="Título do artigo de origem (ex: 'Banana')",
    )
    parser.add_argument(
        "destino",
        type=str,
        help="Título do artigo de destino (ex: 'Física quântica')",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Habilita modo de log detalhado (DEBUG)",
    )
    return parser.parse_args()


def setup_logging(verbose: bool) -> None:
    """Configura a formatação e nível de log da aplicação."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def calculate_depths(
    path: list[str],
    parents_fwd: dict[str, Optional[str]],
    parents_bwd: dict[str, Optional[str]],
) -> tuple[int, int]:
    """Calcula as profundidades atingidas nos lados FWD e BWD para o caminho encontrado."""
    if not path:
        return 0, 0

    # Encontra o nó de interseção no caminho
    meeting_index = 0
    for idx, node in enumerate(path):
        if node in parents_fwd and node in parents_bwd:
            meeting_index = idx
            break

    depth_fwd = meeting_index
    depth_bwd = len(path) - 1 - meeting_index
    return depth_fwd, depth_bwd


async def async_main() -> None:
    """Função principal assíncrona."""
    args = parse_arguments()
    setup_logging(args.verbose)

    origem = args.origem.strip()
    destino = args.destino.strip()

    start_time = time.perf_counter()

    try:
        path, parents_fwd, parents_bwd = await bidirectional_bfs(origem, destino)
    except ValueError as e:
        print(f"\n[ERRO] {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await close_session()

    # Reconfigura o encoding de saída para UTF-8 no Windows
    if sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass

    elapsed_time = time.perf_counter() - start_time

    path_html = None
    tree_html = None
    if path:
        path_html = render_path_only(path, parents_fwd, parents_bwd)
        tree_html = render_exploration_tree(path, parents_fwd, parents_bwd)

    # Cálculo das estatísticas finais
    total_nodes = len(set(parents_fwd.keys()) | set(parents_bwd.keys()))
    depth_fwd, depth_bwd = calculate_depths(path, parents_fwd, parents_bwd)
    passos = len(path) - 1 if path else 0
    caminho_str = " -> ".join(path) if path else "Nenhum caminho encontrado"

    print("\n" + "=" * 60)
    print("                RESUMO DO WIKIRACE")
    print("=" * 60)
    print(f"Tempo total:       {elapsed_time:.2f}s")
    print(f"Nós visitados:     {total_nodes}")
    print(f"Profundidade FWD:  {depth_fwd}")
    print(f"Profundidade BWD:  {depth_bwd}")
    print(f"Caminho ({passos} passos): {caminho_str}")
    if path_html and tree_html:
        path_uri = f"file:///{path_html.replace('\\', '/')}"
        tree_uri = f"file:///{tree_html.replace('\\', '/')}"
        print("-" * 60)
        print("Grafos HTML gerados (Ctrl+Clique para abrir):")
        print(f"  • Caminho Mínimo: {path_uri}")
        print(f"  • Exploração:     {tree_uri}")
    print("=" * 60 + "\n")


def main() -> None:
    """Ponto de entrada síncrono."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
