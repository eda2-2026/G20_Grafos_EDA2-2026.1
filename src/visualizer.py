"""
visualizer.py
=============
Renderizador de grafos interativos utilizando NetworkX e Pyvis.

Responsabilidades:
  - Receber o caminho vencedor e os mapas de visitação do wikirace_engine.
  - Gerar um arquivo HTML interativo com dois modos de exibição:

    Modo 1 — "Caminho Mínimo" (show_path_only=True):
      Exibe unicamente os nós que compõem o caminho mais curto encontrado.
      Visual limpo, ideal para apresentações.

    Modo 2 — "Árvore de Exploração" (show_path_only=False):
      Exibe TODOS os nós visitados pelas buscas FWD e BWD, destacando o
      caminho vencedor com cores vibrantes sobre o fundo de nós explorados.

Paleta de cores dos nós:
  - Verde   (#2ECC71): Origem
  - Vermelho (#E74C3C): Destino
  - Azul    (#3498DB): Nó de Interseção (onde as buscas se encontraram)
  - Amarelo (#F1C40F): Nós intermediários do Caminho Vencedor
  - Cinza   (#95A5A6): Nós visitados, mas não utilizados no caminho final

Dependências: networkx, pyvis
"""

import logging
import os
from typing import Optional

import networkx as nx
from pyvis.network import Network

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paleta de cores (centralizada para fácil alteração futura)
# ---------------------------------------------------------------------------
COLOR_ORIGIN: str = "#2ECC71"        # Verde
COLOR_DESTINATION: str = "#E74C3C"   # Vermelho
COLOR_INTERSECTION: str = "#3498DB"  # Azul
COLOR_PATH: str = "#F1C40F"          # Amarelo
COLOR_EXPLORED: str = "#95A5A6"      # Cinza
COLOR_EDGE_PATH: str = "#F39C12"     # Laranja — arestas do caminho vencedor
COLOR_EDGE_EXPLORED: str = "#BDC3C7" # Cinza claro — arestas de exploração

# Tamanhos dos nós
SIZE_ENDPOINTS: int = 35    # Origem e Destino
SIZE_INTERSECTION: int = 30 # Nó de interseção
SIZE_PATH: int = 25          # Nós intermediários do caminho
SIZE_EXPLORED: int = 15      # Nós apenas visitados


# ===========================================================================
# Funções de classificação de nós
# ===========================================================================

def _classify_nodes(
    path: list[str],
    parents_fwd: dict[str, Optional[str]],
    parents_bwd: dict[str, Optional[str]],
) -> dict[str, str]:
    """Classifica cada nó em uma categoria visual.

    A prioridade de classificação é:
      1. Origem / Destino
      2. Interseção (o ponto de encontro das buscas)
      3. Nós intermediários do caminho vencedor
      4. Nós explorados (visitados mas fora do caminho)

    Args:
        path:        Lista ordenada de títulos do caminho mais curto.
        parents_fwd: Mapa de pais do lado da origem (todos os nós FWD visitados).
        parents_bwd: Mapa de pais do lado do destino (todos os nós BWD visitados).

    Returns:
        Dicionário { título_do_nó → categoria } onde categoria é uma das
        strings: "origin", "destination", "intersection", "path", "explored".
    """
    if not path:
        return {}

    origin: str = path[0]
    destination: str = path[-1]

    # O nó de interseção é o último nó que pertence ao lado FWD dentro do caminho
    # (ou seja, path[i] ainda está em parents_fwd mas path[i+1] não está)
    intersection: Optional[str] = None
    for node in path[1:-1]:  # exclui origem e destino
        if node in parents_fwd and node in parents_bwd:
            intersection = node
            break

    classification: dict[str, str] = {}

    # Todos os nós explorados (base)
    for node in parents_fwd:
        classification[node] = "explored"
    for node in parents_bwd:
        classification[node] = "explored"

    # Sobrescreve com categorias de maior prioridade
    for node in path:
        classification[node] = "path"

    if intersection:
        classification[intersection] = "intersection"

    classification[origin] = "origin"
    classification[destination] = "destination"

    return classification


def _get_node_style(category: str) -> tuple[str, int, str]:
    """Retorna (cor, tamanho, label_shape) para cada categoria de nó.

    Args:
        category: Uma das strings de classificação definidas em _classify_nodes.

    Returns:
        Tupla (cor_hex, tamanho_int, forma_do_label).
    """
    styles: dict[str, tuple[str, int, str]] = {
        "origin":       (COLOR_ORIGIN,       SIZE_ENDPOINTS,    "star"),
        "destination":  (COLOR_DESTINATION,  SIZE_ENDPOINTS,    "star"),
        "intersection": (COLOR_INTERSECTION, SIZE_INTERSECTION, "diamond"),
        "path":         (COLOR_PATH,         SIZE_PATH,         "dot"),
        "explored":     (COLOR_EXPLORED,     SIZE_EXPLORED,     "dot"),
    }
    return styles.get(category, (COLOR_EXPLORED, SIZE_EXPLORED, "dot"))


# ===========================================================================
# Construção do grafo NetworkX
# ===========================================================================

def _build_networkx_graph(
    path: list[str],
    parents_fwd: dict[str, Optional[str]],
    parents_bwd: dict[str, Optional[str]],
    show_path_only: bool,
) -> tuple[nx.DiGraph, dict[str, str]]:
    """Constrói o grafo NetworkX a partir das estruturas do motor de busca.

    Args:
        path:           Caminho mais curto encontrado pelo BFS bidirecional.
        parents_fwd:    Mapa de pais FWD (origem → ...).
        parents_bwd:    Mapa de pais BWD (destino → ...).
        show_path_only: Se True, inclui apenas os nós do caminho vencedor.
                        Se False, inclui todos os nós visitados.

    Returns:
        Tupla (grafo_direcionado, mapa_de_classificacao).
    """
    G = nx.DiGraph()
    classification = _classify_nodes(path, parents_fwd, parents_bwd)

    if show_path_only:
        # --- Modo 1: apenas o caminho mínimo ---
        for node in path:
            cat = classification.get(node, "path")
            color, size, shape = _get_node_style(cat)
            G.add_node(node, color=color, size=size, shape=shape, title=node)

        for i in range(len(path) - 1):
            G.add_edge(path[i], path[i + 1], color=COLOR_EDGE_PATH, width=4)

    else:
        # --- Modo 2: árvore de exploração completa ---

        # Adiciona todos os nós FWD visitados
        for node in parents_fwd:
            cat = classification.get(node, "explored")
            color, size, shape = _get_node_style(cat)
            G.add_node(node, color=color, size=size, shape=shape, title=node)

        # Adiciona todos os nós BWD visitados
        for node in parents_bwd:
            if node not in G:
                cat = classification.get(node, "explored")
                color, size, shape = _get_node_style(cat)
                G.add_node(node, color=color, size=size, shape=shape, title=node)

        # Arestas da árvore FWD (pai → filho)
        for child, parent in parents_fwd.items():
            if parent is not None and child in G and parent in G:
                is_path_edge = (child in path and parent in path)
                edge_color = COLOR_EDGE_PATH if is_path_edge else COLOR_EDGE_EXPLORED
                edge_width = 4 if is_path_edge else 1
                G.add_edge(parent, child, color=edge_color, width=edge_width)

        # Arestas da árvore BWD (pai → filho, lembrando que BWD anda "ao contrário")
        # No mapa BWD, o "pai" é o nó que veio depois na direção do destino.
        # Portanto, a aresta real é: child → parent (BWD inverte a direção).
        for child, parent in parents_bwd.items():
            if parent is not None and child in G and parent in G:
                is_path_edge = (child in path and parent in path)
                edge_color = COLOR_EDGE_PATH if is_path_edge else COLOR_EDGE_EXPLORED
                edge_width = 4 if is_path_edge else 1
                # Aresta no sentido real do grafo: child aponta para parent
                if not G.has_edge(child, parent):
                    G.add_edge(child, parent, color=edge_color, width=edge_width)

        # Garante que as arestas do caminho mínimo estejam com a cor correta
        for i in range(len(path) - 1):
            src, dst = path[i], path[i + 1]
            if G.has_edge(src, dst):
                G[src][dst]["color"] = COLOR_EDGE_PATH
                G[src][dst]["width"] = 4
            else:
                G.add_edge(src, dst, color=COLOR_EDGE_PATH, width=4)

    return G, classification


# ===========================================================================
# Renderização com Pyvis
# ===========================================================================

def _build_pyvis_network(
    G: nx.DiGraph,
    title: str,
    height: str = "750px",
    width: str = "100%",
    bgcolor: str = "#1a1a2e",
    font_color: str = "#FFFFFF",
) -> Network:
    """Converte o grafo NetworkX em uma rede Pyvis configurada.

    Args:
        G:          Grafo NetworkX com atributos de cor e tamanho.
        title:      Título exibido no HTML gerado.
        height:     Altura do canvas Pyvis.
        width:      Largura do canvas Pyvis.
        bgcolor:    Cor de fundo (padrão: azul escuro).
        font_color: Cor da fonte dos labels.

    Returns:
        Objeto Network do Pyvis pronto para ser exportado.
    """
    net = Network(
        height=height,
        width=width,
        bgcolor=bgcolor,
        font_color=font_color,
        directed=True,
        notebook=False,
    )

    # Configura física da simulação para um layout mais legível
    net.set_options("""
    {
      "physics": {
        "enabled": true,
        "barnesHut": {
          "gravitationalConstant": -8000,
          "centralGravity": 0.3,
          "springLength": 120,
          "springConstant": 0.04,
          "damping": 0.09,
          "avoidOverlap": 0.5
        },
        "stabilization": {
          "iterations": 200
        }
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 200,
        "zoomView": true,
        "dragView": true
      },
      "edges": {
        "arrows": {
          "to": { "enabled": true, "scaleFactor": 0.8 }
        },
        "smooth": {
          "type": "curvedCW",
          "roundness": 0.2
        }
      }
    }
    """)

    # Transfere nós do NetworkX para o Pyvis
    for node, attrs in G.nodes(data=True):
        net.add_node(
            node,
            label=node,
            color=attrs.get("color", COLOR_EXPLORED),
            size=attrs.get("size", SIZE_EXPLORED),
            shape=attrs.get("shape", "dot"),
            title=f"<b>{attrs.get('title', node)}</b>",
            font={"size": 12, "color": font_color},
        )

    # Transfere arestas do NetworkX para o Pyvis
    for src, dst, attrs in G.edges(data=True):
        net.add_edge(
            src,
            dst,
            color=attrs.get("color", COLOR_EDGE_EXPLORED),
            width=attrs.get("width", 1),
            title=f"{src} → {dst}",
        )

    return net


# ===========================================================================
# Funções públicas da API do visualizador
# ===========================================================================

def render_path(
    path: list[str],
    parents_fwd: dict[str, Optional[str]],
    parents_bwd: dict[str, Optional[str]],
    output_file: str = "grafo.html",
    show_path_only: bool = False,
) -> str:
    """Gera o arquivo HTML interativo do grafo Wikirace.

    Esta é a função principal do módulo, consumida pelo main.py ou
    diretamente após uma execução do wikirace_engine.

    Args:
        path:           Lista de títulos representando o caminho mais curto.
                        Ex: ["Banana", "Fruta", "Biologia", "Física Quântica"].
        parents_fwd:    Mapa de pais do lado da origem (retornado pelo engine).
        parents_bwd:    Mapa de pais do lado do destino (retornado pelo engine).
        output_file:    Caminho do arquivo HTML de saída.
        show_path_only: Se True → Modo "Caminho Mínimo".
                        Se False → Modo "Árvore de Exploração" (padrão).

    Returns:
        Caminho absoluto do arquivo HTML gerado.

    Raises:
        ValueError: Se o caminho fornecido for vazio.
    """
    if not path:
        raise ValueError(
            "O caminho está vazio. Execute o wikirace_engine antes de visualizar."
        )

    origin: str = path[0]
    destination: str = path[-1]
    mode_label: str = "Caminho Mínimo" if show_path_only else "Árvore de Exploração"

    html_title = (
        f"Wikirace: {origin} → {destination} "
        f"[{mode_label} | {len(path) - 1} passos]"
    )

    logger.info(
        "Gerando visualização '%s' com %d nós no caminho e %d nós explorados.",
        mode_label,
        len(path),
        len(parents_fwd) + len(parents_bwd),
    )

    G, _classification = _build_networkx_graph(
        path, parents_fwd, parents_bwd, show_path_only
    )

    net = _build_pyvis_network(G, title=html_title)

    # Persiste o HTML
    abs_output = os.path.abspath(output_file)
    net.write_html(abs_output)

    logger.info("Grafo salvo em: %s", abs_output)
    return abs_output


def render_path_only(
    path: list[str],
    parents_fwd: dict[str, Optional[str]],
    parents_bwd: dict[str, Optional[str]],
    output_file: str = "grafo_caminho.html",
) -> str:
    """Atalho para o Modo 'Caminho Mínimo'.

    Exibe apenas a rota vencedora, sem os nós secundários explorados.
    Ideal para relatórios ou apresentações.

    Args:
        path:        Lista de títulos do caminho mais curto.
        parents_fwd: Mapa de pais FWD (necessário para classificação de cores).
        parents_bwd: Mapa de pais BWD (necessário para classificação de cores).
        output_file: Arquivo HTML de saída.

    Returns:
        Caminho absoluto do arquivo HTML gerado.
    """
    return render_path(
        path=path,
        parents_fwd=parents_fwd,
        parents_bwd=parents_bwd,
        output_file=output_file,
        show_path_only=True,
    )


def render_exploration_tree(
    path: list[str],
    parents_fwd: dict[str, Optional[str]],
    parents_bwd: dict[str, Optional[str]],
    output_file: str = "grafo_exploracao.html",
) -> str:
    """Atalho para o Modo 'Árvore de Exploração'.

    Exibe todos os nós visitados pelas buscas FWD e BWD, com o caminho
    vencedor destacado em cores vibrantes sobre o fundo cinza dos explorados.

    Args:
        path:        Lista de títulos do caminho mais curto.
        parents_fwd: Mapa de pais FWD (todos os nós visitados pela busca FWD).
        parents_bwd: Mapa de pais BWD (todos os nós visitados pela busca BWD).
        output_file: Arquivo HTML de saída.

    Returns:
        Caminho absoluto do arquivo HTML gerado.
    """
    return render_path(
        path=path,
        parents_fwd=parents_fwd,
        parents_bwd=parents_bwd,
        output_file=output_file,
        show_path_only=False,
    )
