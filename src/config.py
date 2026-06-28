"""
config.py
=========
Constantes globais de configuração do Wikirace.
"""

# Endpoint oficial da API da Wikipédia em português
API_URL = "https://pt.wikipedia.org/w/api.php"

# Identificação do projeto nas requisições HTTP (boas práticas da Wikimedia)
USER_AGENT = "Wikirace-EDA2/1.0 (equipeG20@unb.br)"

# Timeout padrão por requisição HTTP (em segundos)
REQUEST_TIMEOUT = 10

# Configurações de retry com esperas exponenciais
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]

# Limite máximo de backlinks por artigo (evita estouro de memória)
MAX_BACKLINKS = 500

# Limite de conexões simultâneas (utilizado pelo motor de busca)
# Reduzido de 20 para 5 para evitar bloqueios severos (HTTP 429) da Wikimedia.
SEMAPHORE_LIMIT = 5

# Atraso fixo (em segundos) antes de cada requisição para "esfriar" o tráfego
POLITE_DELAY = 0.05

