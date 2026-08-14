-- =============================================================================
-- Scarab — Função de persistência (Módulo 03)
-- Referência: docs/rewrite/CONTRACTS.md §2.3
--
-- Ponto de entrada ÚNICO da aplicação para escrita em clientes_docs.
-- Depende das tabelas criadas por db/init.sql.
-- =============================================================================

CREATE OR REPLACE FUNCTION processar_operacao_json(
    p_nome_arquivo TEXT,
    p_payload      JSONB
)
RETURNS TABLE (status TEXT, mensagem TEXT, id UUID)
LANGUAGE plpgsql
-- SECURITY INVOKER (padrão) + search_path fixo: evita sequestro de resolução de
-- nomes por schemas temporários ou de terceiros.
SET search_path = public, pg_temp
AS $$
DECLARE
    -- As variáveis NÃO são inicializadas aqui de propósito: um erro na seção
    -- DECLARE (ex.: "id" com UUID malformado) NÃO é capturado pelo bloco
    -- EXCEPTION deste mesmo bloco — ele escaparia da função sem gravar
    -- carga_historico. Toda extração/cast acontece dentro do BEGIN.
    v_operacao    TEXT;
    v_id          UUID;
    v_propriedade TEXT;
    v_linhas      INTEGER;
BEGIN
    IF p_payload IS NULL OR jsonb_typeof(p_payload) <> 'object' THEN
        RAISE EXCEPTION 'payload ausente ou nao e um objeto JSON';
    END IF;

    v_operacao := p_payload ->> 'operacao';
    v_id       := (p_payload ->> 'id')::UUID;

    IF v_operacao IS NULL OR v_id IS NULL THEN
        RAISE EXCEPTION 'payload sem "operacao" ou "id"';
    END IF;

    CASE v_operacao
        WHEN 'INSERT', 'UPDATE' THEN
            -- O conflito é resolvido pelo nome da constraint, e não por
            -- `ON CONFLICT (id)`, para evitar ambiguidade com o parametro de
            -- saida `id` desta funcao.
            INSERT INTO clientes_docs (id, dados)
            VALUES (v_id, p_payload - 'operacao'::TEXT)
            ON CONFLICT ON CONSTRAINT clientes_docs_pkey DO UPDATE
                SET dados         = clientes_docs.dados || EXCLUDED.dados,
                    atualizado_em = now();

        WHEN 'DELETE_REGISTRO' THEN
            DELETE FROM clientes_docs
                WHERE clientes_docs.id = v_id;

            GET DIAGNOSTICS v_linhas = ROW_COUNT;
            IF v_linhas = 0 THEN
                RAISE EXCEPTION 'DELETE_REGISTRO: registro nao encontrado (id=%)', v_id;
            END IF;

        WHEN 'REMOVER_PROPRIEDADE' THEN
            v_propriedade := p_payload ->> 'propriedade';
            IF v_propriedade IS NULL OR v_propriedade = '' THEN
                RAISE EXCEPTION 'REMOVER_PROPRIEDADE requer o campo "propriedade"';
            END IF;

            UPDATE clientes_docs
                SET dados         = clientes_docs.dados - v_propriedade,
                    atualizado_em = now()
                WHERE clientes_docs.id = v_id;

            GET DIAGNOSTICS v_linhas = ROW_COUNT;
            IF v_linhas = 0 THEN
                RAISE EXCEPTION 'REMOVER_PROPRIEDADE: registro nao encontrado (id=%)', v_id;
            END IF;

        ELSE
            RAISE EXCEPTION 'operacao desconhecida: %', v_operacao;
    END CASE;

    INSERT INTO carga_historico (
        nome_original_arquivo, conteudo_json_bruto, status, mensagem_erro, cliente_id
    )
    VALUES (
        COALESCE(p_nome_arquivo, '<desconhecido>'), p_payload, 'SUCESSO', NULL, v_id
    );

    RETURN QUERY SELECT 'SUCESSO'::TEXT, NULL::TEXT, v_id;

EXCEPTION WHEN OTHERS THEN
    -- Um bloco com clausula EXCEPTION abre uma subtransacao implicita: ao
    -- entrar aqui, tudo que foi feito acima ja foi desfeito e a transacao
    -- externa continua utilizavel, portanto este INSERT e valido e persiste.
    -- COALESCE protege contra NOT NULL quando o proprio payload/nome e nulo,
    -- caso em que o handler falharia e a excecao escaparia da funcao.
    INSERT INTO carga_historico (
        nome_original_arquivo, conteudo_json_bruto, status, mensagem_erro, cliente_id
    )
    VALUES (
        COALESCE(p_nome_arquivo, '<desconhecido>'),
        COALESCE(p_payload, 'null'::JSONB),
        'ERRO',
        SQLERRM,
        v_id
    );

    RETURN QUERY SELECT 'ERRO'::TEXT, SQLERRM::TEXT, v_id;
END;
$$;

COMMENT ON FUNCTION processar_operacao_json(TEXT, JSONB) IS
    'Aplica a operacao declarada no payload (INSERT/UPDATE/DELETE_REGISTRO/REMOVER_PROPRIEDADE), '
    'registra o resultado em carga_historico e retorna (status, mensagem, id).';
