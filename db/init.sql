-- =============================================================================
-- Scarab — Esquema de banco de dados (Módulo 03)
-- Referência: docs/rewrite/CONTRACTS.md §2.1, §2.2 e §4 (item 6)
--
-- Este script é idempotente: pode ser executado mais de uma vez sem erro.
-- É montado no contêiner PostgreSQL em /docker-entrypoint-initdb.d/ (Módulo 08).
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- -----------------------------------------------------------------------------
-- Tabela clientes_docs — documento consolidado por entidade de negócio
-- -----------------------------------------------------------------------------
-- O `id` é sempre um UUIDv5 calculado em Python (ver CONTRACTS.md §6); o banco
-- nunca gera identificadores. A constraint de chave primária recebe nome
-- explícito porque a função processar_operacao_json usa
-- `ON CONFLICT ON CONSTRAINT clientes_docs_pkey` (evita ambiguidade entre a
-- coluna `id` e o parâmetro de saída `id` da função).
CREATE TABLE IF NOT EXISTS clientes_docs (
    id             UUID        NOT NULL,
    dados          JSONB       NOT NULL,
    criado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT clientes_docs_pkey PRIMARY KEY (id)
);

COMMENT ON TABLE clientes_docs IS
    'Documento JSONB consolidado por entidade de negócio, identificado por UUIDv5 calculado na aplicação.';
COMMENT ON COLUMN clientes_docs.dados IS
    'Conteúdo do JSON recebido sem a chave de controle "operacao".';

-- Consultas por chave/valor dentro do JSONB (operadores @>, ?, ?&, ?|).
CREATE INDEX IF NOT EXISTS idx_clientes_docs_dados_gin
    ON clientes_docs USING GIN (dados);

-- -----------------------------------------------------------------------------
-- Tabela carga_historico — trilha de auditoria de cada arquivo processado
-- -----------------------------------------------------------------------------
-- ATENÇÃO: `cliente_id` NÃO tem FOREIGN KEY para clientes_docs(id), e isso é
-- intencional (CONTRACTS.md §2.2). Na operação DELETE_REGISTRO o registro de
-- clientes_docs é removido ANTES do log ser gravado, dentro da mesma chamada de
-- função; uma FK inviabilizaria essa gravação.
CREATE TABLE IF NOT EXISTS carga_historico (
    id                      BIGSERIAL   NOT NULL,
    nome_original_arquivo   TEXT        NOT NULL,
    conteudo_json_bruto     JSONB       NOT NULL,
    timestamp_processamento TIMESTAMPTZ NOT NULL DEFAULT now(),
    status                  TEXT        NOT NULL,
    mensagem_erro           TEXT,
    cliente_id              UUID,
    CONSTRAINT carga_historico_pkey PRIMARY KEY (id),
    CONSTRAINT carga_historico_status_check CHECK (status IN ('SUCESSO', 'ERRO'))
);

COMMENT ON TABLE carga_historico IS
    'Trilha de auditoria: uma linha por arquivo JSON processado, com sucesso ou erro.';
COMMENT ON COLUMN carga_historico.cliente_id IS
    'UUID do documento afetado. Sem FOREIGN KEY por design (ver docs/rewrite/CONTRACTS.md §2.2).';

CREATE INDEX IF NOT EXISTS idx_carga_historico_status
    ON carga_historico (status);

CREATE INDEX IF NOT EXISTS idx_carga_historico_timestamp
    ON carga_historico (timestamp_processamento DESC);

-- =============================================================================
-- Privilégio mínimo do usuário da aplicação (CONTRACTS.md §4, item 6)
--
-- O bloco abaixo está COMENTADO de propósito: serve como documentação do
-- privilégio esperado. Execute-o manualmente (ou via script de provisionamento)
-- após criar o papel da aplicação. O usuário da aplicação NUNCA deve ser
-- superusuário nem dono das tabelas.
--
-- A senha nunca deve ser escrita neste arquivo: use uma variável psql
-- (`psql -v senha="$SCARAB_DB_PASSWORD" -f init.sql`) ou o comando \password.
--
--   CREATE ROLE scarab_app LOGIN PASSWORD :'senha';
--
--   GRANT CONNECT ON DATABASE scarab TO scarab_app;
--   GRANT USAGE   ON SCHEMA public   TO scarab_app;
--
--   GRANT SELECT, INSERT, UPDATE, DELETE ON clientes_docs   TO scarab_app;
--   GRANT SELECT, INSERT, UPDATE, DELETE ON carga_historico TO scarab_app;
--
--   -- Necessário para o BIGSERIAL de carga_historico.id.
--   GRANT USAGE, SELECT ON SEQUENCE carga_historico_id_seq TO scarab_app;
--
--   -- Único ponto de entrada usado pela aplicação em produção.
--   GRANT EXECUTE ON FUNCTION processar_operacao_json(TEXT, JSONB) TO scarab_app;
--
--   -- Nada de DDL nem de acesso a objetos futuros criados por outros papéis.
--   REVOKE CREATE ON SCHEMA public FROM scarab_app;
-- =============================================================================
