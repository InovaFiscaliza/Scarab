---
description: "Módulo 04 da reescrita Scarab: src/database.py (psycopg3, chamada da stored function)"
agent: rewrite-builder
---
Implemente o **Módulo 04 (Banco de Dados)** da reescrita do Scarab.

## Leitura obrigatória antes de codificar
- [CONTRACTS.md](../../../docs/rewrite/CONTRACTS.md) — seções 2.3 (função SQL), 3.2 (contrato do
  módulo) e 4 (segurança — SQL parametrizado é obrigatório)
- `src/config_loader.py` já implementado (Módulo 02) — leia o arquivo real para casar os nomes de
  `DatabaseConfig` exatamente como foram implementados

## Entregáveis
- `src/database.py`
- `tests/test_database.py` (suíte pytest aprovada — use mocks/fakes para `psycopg`, sem exigir um
  PostgreSQL real; cubra ao menos: parametrização correta da chamada SQL, mapeamento de
  `ProcessResult`, e `health_check()`/erros de conexão tratados sem propagar exceção crua)

## Requisitos específicos

1. Implemente `ProcessResult` (dataclass congelada) e a classe `Database`, exatamente com a
   interface pública descrita em CONTRACTS.md §3.2.
2. Use `psycopg` (v3) com um `psycopg_pool.ConnectionPool` (ou `ConnectionPool` equivalente),
   configurado com `min_pool_size`/`max_pool_size` de `DatabaseConfig`.
3. `call_processar_operacao_json`: chame a função com parâmetros ligados
   (`SELECT status, mensagem, id FROM processar_operacao_json(%s, %s)`), envolvendo o payload
   com `psycopg.types.json.Jsonb(payload)`. **Nunca** monte a query com f-string/concatenação
   contendo dados do payload ou do nome do arquivo.
4. `health_check()`: uma consulta simples (`SELECT 1`) que retorna `True`/`False` sem lançar
   exceção para o chamador.
5. `close()`: fecha o pool de conexões de forma limpa.
6. Trate exceções de conexão/banco (`psycopg.Error`) de forma explícita, convertendo em um
   `ProcessResult(status="ERRO", ...)` quando fizer sentido, em vez de propagar exceções cruas
   para o chamador (o pipeline deve poder continuar processando outros arquivos mesmo se um
   falhar).
7. Não logue o conteúdo completo do payload em nível `INFO` (pode conter CPF/e-mail) — reserve
   isso para `DEBUG`, conforme CONTRACTS.md §4.

## Validação
- `get_errors` no arquivo.
- Não é possível testar contra um banco real nesta fase (container ainda não existe) — valide ao
  menos que o módulo importa sem erro (`uv run python -c "import src.database"`), e relate no
  resumo que testes de integração reais ficam para a fase de validação final (pós Módulo 08).

## Ao terminar
Atualize `/memories/repo/rewrite-plan.md` marcando o Módulo 04 como concluído.
