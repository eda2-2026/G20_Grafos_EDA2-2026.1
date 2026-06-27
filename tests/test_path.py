"""
test_path.py
============
Testes da reconstrução do caminho final (função _reconstruct_path).

Responsabilidade desta função:
  Recebe o nó de interseção + dois mapas de pais (FWD e BWD) e devolve
  a lista de títulos na ordem correta: Origem → ... → Interseção → ... → Destino.

Cenários cobertos:
  1. Reconstrução correta do caminho simples (4 nós, interseção em "B").
  2. Ordem dos nós: o primeiro deve ser a origem e o último o destino.
  3. Sem duplicatas: o nó de interseção aparece exatamente uma vez.
  4. Caminho de comprimento mínimo (2 nós — vizinhos diretos).
  5. Caminho mais longo (5 nós).
  6. Nó de interseção é a própria origem (meeting_node == origin).
  7. Nó de interseção é o próprio destino (meeting_node == destination).
"""

import pytest
from src.wikirace_engine import _reconstruct_path


# ---------------------------------------------------------------------------
# Cenário base: Origem → A → B (interseção) → Destino
# ---------------------------------------------------------------------------

def test_reconstruct_simple_path(
    parents_fwd_fixture, parents_bwd_fixture, expected_path
):
    """A reconstrução do cenário padrão deve retornar exatamente o caminho ótimo."""
    path = _reconstruct_path(
        meeting_node="B",
        parents_fwd=parents_fwd_fixture,
        parents_bwd=parents_bwd_fixture,
        origin="Origem",
        destination="Destino",
    )
    assert path == expected_path, f"Esperado {expected_path}, obtido {path}"


def test_path_starts_with_origin(parents_fwd_fixture, parents_bwd_fixture):
    """O primeiro elemento deve sempre ser a origem."""
    path = _reconstruct_path(
        meeting_node="B",
        parents_fwd=parents_fwd_fixture,
        parents_bwd=parents_bwd_fixture,
        origin="Origem",
        destination="Destino",
    )
    assert path[0] == "Origem"


def test_path_ends_with_destination(parents_fwd_fixture, parents_bwd_fixture):
    """O último elemento deve sempre ser o destino."""
    path = _reconstruct_path(
        meeting_node="B",
        parents_fwd=parents_fwd_fixture,
        parents_bwd=parents_bwd_fixture,
        origin="Origem",
        destination="Destino",
    )
    assert path[-1] == "Destino"


def test_intersection_node_appears_exactly_once(
    parents_fwd_fixture, parents_bwd_fixture
):
    """O nó de interseção 'B' deve aparecer exatamente uma vez no caminho."""
    path = _reconstruct_path(
        meeting_node="B",
        parents_fwd=parents_fwd_fixture,
        parents_bwd=parents_bwd_fixture,
        origin="Origem",
        destination="Destino",
    )
    assert path.count("B") == 1, (
        f"'B' deveria aparecer exatamente 1 vez, apareceu {path.count('B')} em {path}"
    )


def test_no_duplicate_nodes(parents_fwd_fixture, parents_bwd_fixture):
    """Nenhum nó deve aparecer mais de uma vez no caminho reconstruído."""
    path = _reconstruct_path(
        meeting_node="B",
        parents_fwd=parents_fwd_fixture,
        parents_bwd=parents_bwd_fixture,
        origin="Origem",
        destination="Destino",
    )
    assert len(path) == len(set(path)), (
        f"Há duplicatas no caminho: {path}"
    )


# ---------------------------------------------------------------------------
# Caminho de comprimento 1 (vizinhos diretos — sem nós intermediários)
# ---------------------------------------------------------------------------

def test_reconstruct_direct_neighbors():
    """Vizinhos diretos: interseção é o destino, caminho tem 2 nós."""
    # FWD: Origem → Destino em um passo
    parents_fwd = {"Origem": None, "Destino": "Origem"}
    # BWD: apenas o destino (raiz da busca reversa)
    parents_bwd = {"Destino": None}

    path = _reconstruct_path(
        meeting_node="Destino",
        parents_fwd=parents_fwd,
        parents_bwd=parents_bwd,
        origin="Origem",
        destination="Destino",
    )
    assert path == ["Origem", "Destino"], f"Obtido: {path}"


# ---------------------------------------------------------------------------
# Caminho mais longo (5 nós)
# ---------------------------------------------------------------------------

def test_reconstruct_longer_path():
    """Caminho Origem→A→B→C (interseção)→D→Destino deve ter 6 nós."""
    parents_fwd = {
        "Origem": None,
        "A":      "Origem",
        "B":      "A",
        "C":      "B",
    }
    parents_bwd = {
        "Destino": None,
        "D":       "Destino",
        "C":       "D",
    }

    path = _reconstruct_path(
        meeting_node="C",
        parents_fwd=parents_fwd,
        parents_bwd=parents_bwd,
        origin="Origem",
        destination="Destino",
    )

    assert path[0] == "Origem",   f"Deveria iniciar em Origem, obtido: {path}"
    assert path[-1] == "Destino", f"Deveria terminar em Destino, obtido: {path}"
    assert "C" in path,           f"Nó de interseção 'C' deveria estar no caminho"
    assert len(path) == 6,        f"Caminho deveria ter 6 nós, obtido {len(path)}: {path}"
    assert path == ["Origem", "A", "B", "C", "D", "Destino"]


# ---------------------------------------------------------------------------
# Casos extremos: interseção é a própria origem ou o próprio destino
# ---------------------------------------------------------------------------

def test_meeting_node_is_origin():
    """Se a interseção for a origem, o caminho parte dela diretamente para o destino."""
    parents_fwd = {"Origem": None}
    parents_bwd = {
        "Destino": None,
        "A":       "Destino",
        "Origem":  "A",
    }

    path = _reconstruct_path(
        meeting_node="Origem",
        parents_fwd=parents_fwd,
        parents_bwd=parents_bwd,
        origin="Origem",
        destination="Destino",
    )

    assert path[0] == "Origem"
    assert path[-1] == "Destino"
    assert "Origem" not in path[1:], (
        f"'Origem' não deveria aparecer no meio do caminho: {path}"
    )


def test_meeting_node_is_destination():
    """Se a interseção for o destino, o caminho é puramente FWD até ele."""
    parents_fwd = {
        "Origem":  None,
        "A":       "Origem",
        "Destino": "A",
    }
    parents_bwd = {"Destino": None}

    path = _reconstruct_path(
        meeting_node="Destino",
        parents_fwd=parents_fwd,
        parents_bwd=parents_bwd,
        origin="Origem",
        destination="Destino",
    )

    assert path == ["Origem", "A", "Destino"], f"Obtido: {path}"


# ---------------------------------------------------------------------------
# Verificação da ordem interna dos nós
# ---------------------------------------------------------------------------

def test_path_order_is_correct():
    """Os nós devem estar na ordem topológica correta (sem inversões)."""
    parents_fwd = {
        "Origem": None,
        "A":      "Origem",
        "B":      "A",
    }
    parents_bwd = {
        "Destino": None,
        "C":       "Destino",
        "B":       "C",
    }

    path = _reconstruct_path(
        meeting_node="B",
        parents_fwd=parents_fwd,
        parents_bwd=parents_bwd,
        origin="Origem",
        destination="Destino",
    )

    # A ordem esperada é exatamente esta — sem inversões
    assert path == ["Origem", "A", "B", "C", "Destino"], (
        f"Ordem incorreta: {path}"
    )
