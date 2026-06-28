"""
models.py
=========
Modelos de dados utilizados pelo Wikirace.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Node:
    """Representa um nó da busca no grafo da Wikipédia.

    Attributes:
        title:  Título do artigo da Wikipédia.
        parent: Título do artigo pai no caminho de exploração.
        depth:  Profundidade do nó na árvore de busca.
    """
    title: str
    parent: Optional[str]
    depth: int
