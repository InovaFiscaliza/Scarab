---
description: "Módulo 03 da reescrita Scarab: db/init.sql e db/procedures.sql"
agent: rewrite-builder
---
Implemente o **Módulo 03 (Esquema de Banco de Dados)** da reescrita do Scarab.

## Leitura obrigatória antes de codificar
- [CONTRACTS.md](../../../docs/rewrite/CONTRACTS.md) — seção 2 (esquema completo) e seção 4
  (segurança, especialmente o item sobre privilégio mínimo do usuário de banco)

## Entregáveis
- `db/init.sql`
- `db/procedures.sql`

## Requisitos específicos

1. `init.sql`:
   - `CREATE EXTENSION IF NOT EXISTS "uuid-ossp";`
   - Tabela `clientes_docs` exatamente como CONTRACTS.md §2.1 (`id UUID PRIMARY KEY`,
     `dados JSONB NOT NULL`, `criado_em`, `atualizado_em`).
   - Índice `GIN` sobre `dados`.
   - Tabela `carga_historico` exatamente como CONTRACTS.md §2.2 — **sem** `FOREIGN KEY` em
     `cliente_id` (leia o aviso em CONTRACTS.md §2.2 antes de implementar; isso é intencional).
   - Índices em `status` e `timestamp_processamento`.
   - Ao final, inclua (comentado, como exemplo/documentação, não necessariamente executado) um
     bloco `GRANT` mostrando o privilégio mínimo esperado para o usuário da aplicação
     (`EXECUTE` na função + `SELECT/INSERT/UPDATE/DELETE` nas duas tabelas, sem superusuário).
2. `procedures.sql`:
   - Função `processar_operacao_json(p_nome_arquivo TEXT, p_payload JSONB) RETURNS TABLE
     (status TEXT, mensagem TEXT, id UUID)`, cobrindo as 4 operações (`INSERT`, `UPDATE`,
     `DELETE_REGISTRO`, `REMOVER_PROPRIEDADE`) conforme CONTRACTS.md §2.3. Pode partir do
     rascunho de referência ali presente, mas revise e corrija eventuais problemas antes de
     finalizar (não copie cegamente).
   - Garanta que erros sejam capturados (`EXCEPTION WHEN OTHERS`) e sempre gravados em
     `carga_historico` com `status = 'ERRO'` e `mensagem_erro = SQLERRM`, sem interromper a
     função com uma exceção não tratada.
   - `INSERT`/`UPDATE`: usar `ON CONFLICT (id) DO UPDATE` com o operador `||` para mesclar
     `dados` sem apagar chaves existentes.
   - `REMOVER_PROPRIEDADE`: exigir campo `"propriedade"` no payload; usar o operador `-` do
     JSONB.

## Validação
- Não há banco disponível nesta fase (container ainda não existe) — valide a sintaxe SQL
  manualmente, com atenção especial a: ponto e vírgula ao final de cada statement, tipos de
  dados corretos, uso correto de `$$` para o corpo da função `plpgsql`.
- Rode `get_errors` nos dois arquivos (cobre problemas óbvios de sintaxe se houver suporte de
  linguagem ativo).

## Ao terminar
Atualize `/memories/repo/rewrite-plan.md` marcando o Módulo 03 como concluído e liste qualquer
ajuste feito em relação ao rascunho de CONTRACTS.md §2.3.
