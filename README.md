# G20 Grafos EDA2 (Wikirace)

Projeto academico da disciplina de Estruturas de Dados 2. Trata-se de um explorador de grafos que encontra o caminho mais curto de cliques entre dois artigos da Wikipedia.

## Sobre o Projeto

O algoritmo simula o famoso jogo "Wikirace", partindo de um artigo de origem e buscando alcancar um artigo de destino clicando apenas nos links internos. O projeto utiliza a MediaWiki API para buscar as relacoes entre os artigos em tempo real.

Devido ao alto fator de ramificacao da Wikipedia (onde um unico artigo pode conter centenas de links), o projeto resolve o problema de explosao combinatoria utilizando o algoritmo de Busca Bidirecional em Largura (Bidirectional BFS).

## Arquitetura

O projeto esta modularizado em responsabilidades estritas:

* config.py: Centraliza variaveis de ambiente, URLs da API, limites de concorrencia e politicas de timeout e retry.
* models.py: Contem as estruturas de dados (dataclasses) utilizadas, como os Nos do grafo.
* wiki_client.py: Modulo puramente de rede. Lida com chamadas HTTP assincronas para a Wikipedia, limites de paginacao e tratamento de falhas.
* wikirace_engine.py: O motor logico. Implementa o BFS Bidirecional, semaforos de concorrencia, deteccao de intersecao e camadas de cache para outlinks e backlinks.
* visualizer.py: Exportador do grafo. Recebe a arvore percorrida e o caminho vencedor para renderizar um documento HTML interativo usando Pyvis.

## Dependencias

* Python 3.10+
* aiohttp (Requisicoes assincronas e controle de conexao)
* networkx (Estruturacao do grafo)
* pyvis (Visualizacao web do grafo)
* pytest (Suite de testes unitarios)

## Execucao (Desenvolvimento)

(Instrucoes a serem adicionadas apos a conclusao da implementacao da CLI).

1. Clone o repositorio.
2. Crie um ambiente virtual: `python -m venv venv`
3. Ative o ambiente virtual e instale as dependencias: `pip install -r requirements.txt`
4. Execute o modulo principal (A fazer).
