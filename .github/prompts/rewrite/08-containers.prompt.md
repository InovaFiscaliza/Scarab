---
description: "Módulo 08 da reescrita Scarab: containers/Containerfile.app, Containerfile.db, podman-compose.yml"
agent: rewrite-builder
---
Implemente o **Módulo 08 (Containers)** da reescrita do Scarab.

## Leitura obrigatória antes de codificar
- [PLAN.md](../../../docs/rewrite/PLAN.md) — seção 3 (árvore alvo)
- [CONTRACTS.md](../../../docs/rewrite/CONTRACTS.md) — seções 1 (config, para variáveis de
  ambiente/volumes) e 4 (segurança — segredos nunca em texto puro na imagem)
- `pyproject.toml` e `src/main.py` já implementados — confirme o comando exato de entrada
  (argumentos esperados por `main.py`) antes de escrever o `CMD`/`ENTRYPOINT`
- `db/init.sql`, `db/procedures.sql` já implementados

## Entregáveis
- `containers/Containerfile.app`
- `containers/Containerfile.db`
- `containers/podman-compose.yml`

## Requisitos específicos

1. `Containerfile.app` (multi-stage):
   - Estágio `builder`: imagem `python:3.13-slim`, copia o binário `uv` (
     `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/`), copia `pyproject.toml` +
     `uv.lock`, roda `uv sync --frozen --no-dev` para criar `.venv`.
   - Estágio final: imagem `python:3.13-slim`, copia `.venv` + `src/` + `config/` do estágio
     anterior, define `ENV PATH="/app/.venv/bin:$PATH"`, cria e usa um usuário não-root,
     `WORKDIR /app`, `CMD` executando `src/main.py` com o argumento de diretório de config
     esperado (confirme o contrato real de `src/main.py` antes de fixar o comando).
2. `Containerfile.db`:
   - `FROM postgres:16-alpine` (ou tag estável equivalente).
   - Copie `db/init.sql` e `db/procedures.sql` para `/docker-entrypoint-initdb.d/` com nomes
     numerados para garantir ordem de execução (ex.: `01-init.sql`, `02-procedures.sql`), já que
     o Postgres executa os scripts desse diretório em ordem alfabética.
3. `podman-compose.yml`:
   - Serviço `db`: build a partir de `Containerfile.db`, volume nomeado para `PGDATA`,
     variáveis `POSTGRES_DB`/`POSTGRES_USER`/`POSTGRES_PASSWORD` vindas de `env_file: .env`
     (nunca hardcoded), `healthcheck` com `pg_isready`.
   - Serviço `app`: build a partir de `Containerfile.app`, `depends_on: db` com
     `condition: service_healthy`, `env_file: .env`, volumes montando pastas do host
     correspondentes aos `repositories[].path` locais definidos em `config/default_config.json`
     (entrada, mídia local, lixeira) — mapeie pelo menos um exemplo de cada papel
     (`input`/`storage_media`) mais a pasta de lixeira, `restart: unless-stopped`.
   - Nenhum segredo deve aparecer em texto puro no `podman-compose.yml` — sempre via `env_file`
     ou `secrets:`.

## Validação
- `get_errors` (quando aplicável a YAML/Containerfile).
- Se o `podman` (ou `podman-compose`) estiver disponível no ambiente, rode
  `podman compose -f containers/podman-compose.yml config` para validar a sintaxe; caso não
  esteja disponível, relate isso no resumo em vez de tentar contornar.

## Ao terminar
Atualize `/memories/repo/rewrite-plan.md` marcando o Módulo 08 como concluído e liste as tags de
imagem base escolhidas e quaisquer suposições sobre nomes de pastas montadas.
