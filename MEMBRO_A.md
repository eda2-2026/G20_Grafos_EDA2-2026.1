# Guia do Membro A — Wikirace

Este documento descreve **tudo** o que o Membro A precisa implementar para integrar a sua parte ao código já entregue pelo Membro B.

O Membro B entregou:
- `src/wikirace_engine.py` — Motor de Busca Bidirecional (BFS) completo e testado.
- `src/visualizer.py` — Renderizador HTML interativo (networkx + pyvis).
- `tests/` — 24 testes unitários prontos (rodam offline via mock).
- `requirements.txt` — Todas as dependências já declaradas.

Seu trabalho consiste em criar os arquivos listados abaixo. O motor de busca **já importa** as suas funções pelo caminho exato — basta implementar os contratos descritos.

---

## Tasks

- [ ] **Fase 0 — Setup**
  - [ ] Fazer `git pull` / `git fetch` na branch `fase-2` para ter o código do Membro B
  - [ ] Criar e ativar o ambiente virtual: `python -m venv venv && venv\Scripts\activate`
  - [ ] Instalar dependências: `pip install -r requirements.txt`
  - [ ] Verificar que os 24 testes do Membro B passam: `pytest tests/ -v`

- [ ] **Fase 1 — `src/config.py`**
  - [ ] Criar o arquivo com as constantes globais do projeto
  - [ ] Definir `API_URL = "https://pt.wikipedia.org/w/api.php"`
  - [ ] Definir `USER_AGENT` com identificação do projeto (ex: `"Wikirace-EDA2/1.0 (email@unb.br)"`)
  - [ ] Definir `REQUEST_TIMEOUT = 10` (segundos)
  - [ ] Definir `MAX_RETRIES = 3`
  - [ ] Definir `RETRY_DELAYS = [1, 2, 4]` (espera exponencial em segundos)
  - [ ] Definir `MAX_BACKLINKS = 500` (limite de backlinks por artigo)
  - [ ] Definir `SEMAPHORE_LIMIT = 20` (já usado no engine — manter consistente)

- [ ] **Fase 2 — `src/models.py`**
  - [ ] Criar o dataclass `Node` com exatamente esta assinatura:
    ```python
    from dataclasses import dataclass

    @dataclass
    class Node:
        title: str
        parent: str | None
        depth: int
    ```
  > O Membro B importa este contrato em `wikirace_engine.py`. Não altere os nomes dos campos.

- [ ] **Fase 3 — `src/wiki_client.py`** *(arquivo principal do Membro A)*
  - [ ] Criar uma `aiohttp.ClientSession` reutilizável com `User-Agent` e timeout configurados via `config.py`
  - [ ] Implementar `async def get_outlinks(title: str) -> list[str]`
    - [ ] Chamar a MediaWiki API com `action=query&prop=links&plnamespace=0`
    - [ ] Tratar paginação via campo `continue` na resposta JSON (loop até não haver mais páginas)
    - [ ] Normalizar os títulos recebidos (usar o campo `title` de cada link)
    - [ ] Retornar apenas artigos do namespace 0 (já filtrado via `plnamespace=0`)
    - [ ] Aplicar retry automático com espera exponencial em erros 429, 500, 502, 503
    - [ ] Aplicar timeout via `aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)`
  - [ ] Implementar `async def get_backlinks(title: str) -> list[str]`
    - [ ] Chamar a MediaWiki API com `action=query&list=backlinks&blnamespace=0`
    - [ ] **Sem paginação** — usar o parâmetro `bllimit=MAX_BACKLINKS` e parar na primeira página
    - [ ] Normalizar e retornar os títulos recebidos
    - [ ] Aplicar o mesmo retry e timeout de `get_outlinks`

  > **Contrato obrigatório**: as assinaturas devem ser exatamente:
  > ```python
  > async def get_outlinks(title: str) -> list[str]: ...
  > async def get_backlinks(title: str) -> list[str]: ...
  > ```
  > O `wikirace_engine.py` faz `from src.wiki_client import get_backlinks, get_outlinks`. Qualquer mudança de nome quebrará a integração.

- [ ] **Fase 4 — `tests/test_client.py`**
  - [ ] Testar `get_outlinks` com resposta mockada da API (sem requisição real)
    - [ ] Verifica que a paginação funciona: quando a API retorna `continue`, a função busca a próxima página
    - [ ] Verifica que artigos de outros namespaces são descartados
    - [ ] Verifica o comportamento no retry: status 429 → espera → nova tentativa
    - [ ] Verifica que após `MAX_RETRIES` falhas consecutivas, uma exceção é levantada
  - [ ] Testar `get_backlinks` com resposta mockada
    - [ ] Verifica que NÃO há paginação (apenas a primeira página é consumida)
    - [ ] Verifica o limite de `MAX_BACKLINKS` na query

- [ ] **Fase 5 — `main.py`** *(ponto de entrada da aplicação)*
  - [ ] Capturar `origem` e `destino` via argumentos de linha de comando (ex: `argparse`)
  - [ ] Configurar o módulo `logging` (nível `INFO` por padrão, `DEBUG` com flag `--verbose`)
  - [ ] Medir o tempo total da busca com `time.perf_counter()`
  - [ ] Chamar `await bidirectional_bfs(origem, destino)` do `wikirace_engine`
  - [ ] Exibir o caminho encontrado no terminal
  - [ ] Gerar os dois HTMLs do visualizador chamando:
    ```python
    from src.visualizer import render_path_only, render_exploration_tree
    render_path_only(path, parents_fwd, parents_bwd)
    render_exploration_tree(path, parents_fwd, parents_bwd)
    ```
  - [ ] Exibir quadro de estatísticas ao final:
    ```
    Tempo total:       X.XXs
    Nos visitados:     NNN
    Profundidade FWD:  N
    Profundidade BWD:  N
    Caminho (N passos): Origem → A → B → Destino
    ```

---

## Referencia da API da Wikipedia

Endpoint base: `https://pt.wikipedia.org/w/api.php`

**Outlinks de um artigo:**
```
GET ?action=query&prop=links&titles={TITULO}&plnamespace=0&pllimit=500&format=json
```
Quando a resposta tiver o campo `continue`, repita a requisição adicionando os parâmetros retornados nele.

**Backlinks de um artigo (sem paginação):**
```
GET ?action=query&list=backlinks&bltitle={TITULO}&blnamespace=0&bllimit=500&format=json
```

**Exemplo de resposta de outlinks:**
```json
{
  "query": {
    "pages": {
      "123": {
        "title": "Banana",
        "links": [
          { "ns": 0, "title": "Fruta" },
          { "ns": 0, "title": "Planta" }
        ]
      }
    }
  },
  "continue": { "plcontinue": "...", "continue": "..." }
}
```

---

## Estrutura final esperada do projeto

```
projeto/
├── requirements.txt          (pronto)
├── pytest.ini                (pronto)
├── main.py                   (Membro A — Fase 5)
│
├── src/
│   ├── __init__.py           (pronto)
│   ├── config.py             (Membro A — Fase 1)
│   ├── models.py             (Membro A — Fase 2)
│   ├── wiki_client.py        (Membro A — Fase 3)
│   ├── wikirace_engine.py    (pronto — Membro B)
│   └── visualizer.py         (pronto — Membro B)
│
└── tests/
    ├── __init__.py           (pronto)
    ├── conftest.py           (pronto)
    ├── test_client.py        (Membro A — Fase 4)
    ├── test_engine.py        (pronto — Membro B)
    ├── test_cache.py         (pronto — Membro B)
    └── test_path.py          (pronto — Membro B)
```

---

## Como validar a integracao

Após implementar os quatro arquivos (`config.py`, `models.py`, `wiki_client.py`, `main.py`), execute:

```powershell
# 1. Todos os 24 testes do Membro B devem continuar passando
pytest tests/test_engine.py tests/test_cache.py tests/test_path.py -v

# 2. Os testes do wiki_client (seus) devem passar
pytest tests/test_client.py -v

# 3. Teste de ponta a ponta no terminal
python main.py "Banana" "Física quântica"
```

O resultado esperado no terminal:
```
INFO  Iniciando Bidirectional BFS: 'Banana' -> 'Fisica quantica'
INFO  Intersecao encontrada no no: '...'
INFO  Caminho reconstruido (N passos): Banana -> ... -> Fisica quantica
INFO  Grafo salvo em: grafo_caminho.html
INFO  Grafo salvo em: grafo_exploracao.html

Tempo total:        X.XXs
Caminho (N passos): Banana -> ... -> Fisica quantica
```

---

## Observacoes importantes

1. **Nao altere as assinaturas de `get_outlinks` e `get_backlinks`** — o engine ja importa exatamente esses nomes de `src.wiki_client`.
2. **Nao altere `src/wikirace_engine.py` nem `src/visualizer.py`** — qualquer mudanca deve ser discutida com o Membro B antes.
3. **`pytest.ini` ja esta configurado** com `asyncio_mode = auto`. Seus testes async funcionarao sem nenhum decorator adicional.
4. **Os 24 testes do Membro B devem permanecer passando** apos a sua integracao — use-os como garantia de regressao.
