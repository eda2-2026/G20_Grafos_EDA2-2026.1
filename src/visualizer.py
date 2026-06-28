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

def _depths_from_parents(
    parents: dict[str, Optional[str]],
    root: str,
) -> dict[str, int]:
    """Calcula a profundidade de cada nó a partir de ``root`` usando o mapa de pais.

    Reconstrói as relações filho→pai em pai→filhos e executa uma BFS simples.

    Args:
        parents: Dict {filho: pai} gerado pelo BFS bidirecional.
        root:    Raíz da árvore (origem ou destino).

    Returns:
        Dict {título: profundidade_inteira}.
    """
    children: dict[str, list[str]] = {}
    for node, parent in parents.items():
        if parent is not None:
            children.setdefault(parent, []).append(node)
        children.setdefault(node, [])

    depths: dict[str, int] = {root: 0}
    queue: list[str] = [root]
    while queue:
        node = queue.pop(0)
        for child in children.get(node, []):
            if child not in depths:
                depths[child] = depths[node] + 1
                queue.append(child)
    return depths


def _build_networkx_graph(
    path: list[str],
    parents_fwd: dict[str, Optional[str]],
    parents_bwd: dict[str, Optional[str]],
    show_path_only: bool,
    max_display_depth: int = 1,
) -> tuple[nx.DiGraph, dict[str, str]]:
    """Constrói o grafo NetworkX a partir das estruturas do motor de busca.

    Args:
        path:              Caminho mais curto encontrado pelo BFS bidirecional.
        parents_fwd:       Mapa de pais FWD (origem → ...).
        parents_bwd:       Mapa de pais BWD (destino → ...).
        show_path_only:    Se True, inclui apenas os nós do caminho vencedor.
                           Se False, inclui os nós visitados até ``max_display_depth``.
        max_display_depth: Profundidade máxima exibida na árvore de exploração.
                           Nós mais distantes são omitidos para reduzir o tamanho
                           do HTML. Nós do caminho vencedor são sempre mantidos.

    Returns:
        Tupla (grafo_direcionado, mapa_de_classificacao).
    """
    G = nx.DiGraph()
    classification = _classify_nodes(path, parents_fwd, parents_bwd)
    path_set: set[str] = set(path)

    if show_path_only:
        # --- Modo 1: apenas o caminho mínimo ---
        for node in path:
            cat = classification.get(node, "path")
            color, size, shape = _get_node_style(cat)
            G.add_node(node, color=color, size=size, shape=shape, title=node)

        for i in range(len(path) - 1):
            G.add_edge(path[i], path[i + 1], color=COLOR_EDGE_PATH, width=4)

    else:
        # --- Modo 2: árvore de exploração com corte por profundidade ---

        depth_fwd = _depths_from_parents(parents_fwd, path[0])
        depth_bwd = _depths_from_parents(parents_bwd, path[-1])

        def _within_depth(node: str) -> bool:
            """Retorna True se o nó está dentro da profundidade máxima exibida."""
            return (
                node in path_set
                or depth_fwd.get(node, 9999) <= max_display_depth
                or depth_bwd.get(node, 9999) <= max_display_depth
            )

        # Adiciona nós FWD dentro do limite
        for node in parents_fwd:
            if _within_depth(node):
                cat = classification.get(node, "explored")
                color, size, shape = _get_node_style(cat)
                G.add_node(node, color=color, size=size, shape=shape, title=node)

        # Adiciona nós BWD dentro do limite
        for node in parents_bwd:
            if _within_depth(node) and node not in G:
                cat = classification.get(node, "explored")
                color, size, shape = _get_node_style(cat)
                G.add_node(node, color=color, size=size, shape=shape, title=node)

        # Arestas da árvore FWD (pai → filho)
        for child, parent in parents_fwd.items():
            if parent is not None and child in G and parent in G:
                is_path_edge = (child in path_set and parent in path_set)
                edge_color = COLOR_EDGE_PATH if is_path_edge else COLOR_EDGE_EXPLORED
                edge_width = 4 if is_path_edge else 1
                G.add_edge(parent, child, color=edge_color, width=edge_width)

        # Arestas da árvore BWD (sentido real: child → parent)
        for child, parent in parents_bwd.items():
            if parent is not None and child in G and parent in G:
                is_path_edge = (child in path_set and parent in path_set)
                edge_color = COLOR_EDGE_PATH if is_path_edge else COLOR_EDGE_EXPLORED
                edge_width = 4 if is_path_edge else 1
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

        omitted = (len(parents_fwd) + len(parents_bwd)) - len(G.nodes)
        if omitted > 0:
            logger.info(
                "Profundidade máxima exibida: %d — %d nós omitidos (além do limite).",
                max_display_depth,
                omitted,
            )

    return G, classification


# ===========================================================================
# Renderização com Pyvis
# ===========================================================================

def _compute_positions(
    G: nx.DiGraph,
    path: list[str],
    show_path_only: bool,
) -> dict[str, tuple[float, float]]:
    """Calcula as posições dos nós usando algoritmos do NetworkX."""
    if show_path_only or len(G.nodes) <= 3:
        n = len(path)
        if n == 0:
            return {}
        positions = {}
        for i, node in enumerate(path):
            positions[node] = (i / max(n - 1, 1) * 2 - 1, 0.0)
        return positions

    fixed_pos = {node: ((i / max(len(path) - 1, 1)) * 0.4 - 0.2, 0.0) for i, node in enumerate(path)}
    pos = nx.spring_layout(
        G,
        pos=fixed_pos,
        fixed=list(fixed_pos.keys()),
        seed=42,
        k=0.3,
        iterations=80,
    )
    return {node: (float(x), float(y)) for node, (x, y) in pos.items()}


def _build_pyvis_network(
    G: nx.DiGraph,
    positions: dict[str, tuple[float, float]],
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

    # Física desabilitada: posições são pré-computadas no Python (nx.spring_layout).
    # Com centenas de nós, o simulador vis.js nunca converge — os nós oscilam
    # indefinidamente. Pré-computar e fixar as coordenadas elimina o problema.
    net.set_options("""
    {
      "physics": {
        "enabled": false
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

    # Transfere nós do NetworkX para o Pyvis com posições fixas
    SCALE = 1500  # escala em pixels para o canvas vis.js
    for node, attrs in G.nodes(data=True):
        x, y = positions.get(node, (0.0, 0.0))
        net.add_node(
            node,
            label=node,
            color=attrs.get("color", COLOR_EXPLORED),
            size=attrs.get("size", SIZE_EXPLORED),
            shape=attrs.get("shape", "dot"),
            title=f"<b>{attrs.get('title', node)}</b>",
            font={"size": 12, "color": font_color},
            x=x * SCALE,
            y=y * SCALE,
            physics=False,  # fixa o nó na posição calculada
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
# Pós-processamento do HTML gerado
# ===========================================================================

def _compute_layout(
    G: nx.DiGraph,
    path: list[str],
    show_path_only: bool,
) -> dict[str, tuple[float, float]]:
    """Calcula as posições dos nós usando algoritmos do NetworkX.

    Para o Modo 1 (caminho mínimo): posiciona os nós linearmente da
    esquerda para a direita, em uma linha reta simples.

    Para o Modo 2 (árvore de exploração): usa spring_layout (Fruchterman-
    Reingold). Os nós do caminho são fixados no centro para atraírem os
    explorados ao redor, produzindo um layout mais legível.

    Args:
        G:              Grafo NetworkX já construído.
        path:           Nós do caminho vencedor (para ancoragem no spring_layout).
        show_path_only: Define qual algoritmo de layout usar.

    Returns:
        Dicionário { título_do_nó → (x, y) } com coordenadas normalizadas.
    """
    if show_path_only or len(G.nodes) <= 3:
        # Layout linear simples para o caminho mínimo
        n = len(path)
        if n == 0:
            return {}
        positions = {}
        for i, node in enumerate(path):
            positions[node] = (i / max(n - 1, 1) * 2 - 1, 0.0)
        return positions

    # Layout radial sem dependência de scipy.
    # Nós são colocados em anéis concêntricos conforme profundidade BFS da origem.
    # Nós do caminho ficam fixados no centro; explorados formam anéis ao redor.
    import math

    path_set = set(path)

    # BFS simples para calcular profundidade de cada nó a partir da origem
    depth_map: dict[str, int] = {}
    queue: list[tuple[str, int]] = [(path[0], 0)]
    while queue:
        node, d = queue.pop(0)
        if node in depth_map:
            continue
        depth_map[node] = d
        for nb in G.successors(node):
            if nb not in depth_map:
                queue.append((nb, d + 1))
    # Nós não alcançados pela BFS da origem (lado BWD apenas) recebem profundidade máxima+1
    max_depth = max(depth_map.values(), default=0)
    for node in G.nodes:
        if node not in depth_map:
            depth_map[node] = max_depth + 1

    # Agrupa nós por profundidade
    rings: dict[int, list[str]] = {}
    for node in G.nodes:
        d = depth_map[node]
        rings.setdefault(d, []).append(node)

    positions: dict[str, tuple[float, float]] = {}

    # Fixa nós do caminho em linha horizontal no centro (profundidade 0)
    n_path = len(path)
    for i, node in enumerate(path):
        positions[node] = ((i / max(n_path - 1, 1)) * 0.5 - 0.25, 0.0)

    # Distribui demais nós em anéis conforme profundidade
    for depth, nodes_at_depth in sorted(rings.items()):
        radius = depth * 0.3 + 0.5
        other_nodes = [n for n in nodes_at_depth if n not in path_set]
        n = len(other_nodes)
        for j, node in enumerate(other_nodes):
            angle = 2 * math.pi * j / max(n, 1)
            positions[node] = (radius * math.cos(angle), radius * math.sin(angle))

    return positions


# ===========================================================================
# Funções públicas da API do visualizador
# ===========================================================================

def render_path(
    path: list[str],
    parents_fwd: dict[str, Optional[str]],
    parents_bwd: dict[str, Optional[str]],
    output_file: str = "grafo.html",
    show_path_only: bool = False,
    max_display_depth: int = 1,
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
        path, parents_fwd, parents_bwd, show_path_only, max_display_depth
    )

    positions = _compute_layout(G, path, show_path_only)
    net = _build_pyvis_network(G, positions=positions, title=html_title)

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
    max_display_depth: int = 1,
) -> str:
    """Atalho para o Modo 'Árvore de Exploração'.

    Exibe os nós visitados pelas buscas FWD e BWD até ``max_display_depth``
    passos de distância da origem ou do destino. Nós do caminho vencedor
    são sempre incluídos. O padrão (1) exibe apenas os vizinhos imediatos,
    que já é suficiente para visualizar a busca bidirecional na maioria dos casos.

    Args:
        path:              Lista de títulos do caminho mais curto.
        parents_fwd:       Mapa de pais FWD (todos os nós visitados pela busca FWD).
        parents_bwd:       Mapa de pais BWD (todos os nós visitados pela busca BWD).
        output_file:       Arquivo HTML de saída.
        max_display_depth: Profundidade máxima de nós exibidos (padrão: 1).
                           Aumente para 2 ou mais para ver camadas mais profundas
                           (aviso: o HTML pode ficar muito grande).

    Returns:
        Caminho absoluto do arquivo HTML gerado.
    """
    return render_path(
        path=path,
        parents_fwd=parents_fwd,
        parents_bwd=parents_bwd,
        output_file=output_file,
        show_path_only=False,
        max_display_depth=max_display_depth,
    )
