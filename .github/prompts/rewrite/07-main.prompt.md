---
description: "Módulo 07 da reescrita Scarab: src/main.py (loop principal, sinais, ponto de entrada)"
agent: rewrite-builder
---
Implemente o **Módulo 07 (Main)** da reescrita do Scarab.

## Leitura obrigatória antes de codificar
- [CONTRACTS.md](../../../docs/rewrite/CONTRACTS.md) — seção 3.5 (contrato do módulo)
- [PLAN.md](../../../docs/rewrite/PLAN.md) — seção 2 (mapeamento, última linha — padrão de sinais
  do `legacy/src/scarab.py` legado)
- `legacy/src/scarab.py` (legado) — **somente leitura**, para reaproveitar o padrão de
  `signal.signal`/loop/contagem de erros; não copie literalmente, adapte para os novos módulos
- `src/config_loader.py`, `src/database.py`, `src/storage_manager.py`, `src/pipeline.py` já
  implementados — leia os arquivos reais para casar exatamente com as assinaturas implementadas

## Entregáveis
- `src/main.py`
- `src/__init__.py` (crie somente se ainda não existir do Módulo 00; não sobrescreva se já
  existir)
- `tests/test_main.py` (opcional — o loop é majoritariamente I/O e sinais, difícil de testar de
  forma unitária; só crie se conseguir isolar uma parte testável, ex.: a lógica de contagem de
  erros consecutivos)

## Requisitos específicos

1. Handlers para `SIGINT`, `SIGTERM`, `SIGBREAK` que sinalizam uma flag global `keep_running =
   False` para parada graciosa (mesmo espírito do `sigint_handler` em `legacy/src/scarab.py`
   legado).
2. `main(config_dir: str) -> None`:
   - carrega config via `config_loader.get_config(config_dir)`;
   - inicializa logging (nível/formato conforme `config.log`);
   - instancia `StorageManager`, `Database`, `IngestionPipeline`;
   - loop principal: enquanto `keep_running`, chama `pipeline.run_once()`, trata erros contando
     falhas consecutivas contra `config.maximum_errors_before_exit` (mesmo padrão do legado:
     `FileNotFoundError`/`OSError` tratados separadamente de exceções genéricas), executa
     `pipeline.run_trash_maintenance()` periodicamente (ex.: a cada N ciclos ou verificando um
     timestamp da última execução — decida e documente a estratégia escolhida), e
     `time.sleep(config.check_period_seconds)` entre ciclos;
   - ao sair do loop (flag `keep_running == False` ou erros excedidos), chama `db.close()` e
     loga uma mensagem final de encerramento.
3. Bloco `if __name__ == "__main__":` validando `sys.argv` (espera o caminho do diretório de
   config como argumento único) e chamando `main(config_dir)`, com mensagem de uso em caso de
   argumento ausente/incorreto (mesmo padrão do `legacy/src/scarab.py` legado).
4. Não implemente lógica de negócio aqui — tudo que for classificação/validação/persistência já
   está em `pipeline.py`/`database.py`/`storage_manager.py`. `main.py` apenas orquestra o ciclo de
   vida do processo.

## Validação
- `get_errors` no arquivo.
- `uv run python -c "import src.main"` para checar importação limpa.

## Ao terminar
Atualize `/memories/repo/rewrite-plan.md` marcando o Módulo 07 como concluído. Neste ponto, todos
os módulos Python (`src/`) estão implementados — sinalize isso claramente no resumo, pois os
módulos 08/09 (containers/CI) dependem deste marco.
