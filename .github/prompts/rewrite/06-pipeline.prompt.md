---
description: "Módulo 06 da reescrita Scarab: src/pipeline.py (UUIDv5, classificação de arquivos, orquestração)"
agent: rewrite-builder
---
Implemente o **Módulo 06 (Pipeline)** da reescrita do Scarab.

## Leitura obrigatória antes de codificar
- [CONTRACTS.md](../../../docs/rewrite/CONTRACTS.md) — seções 3.4 (contrato do módulo), 4
  (segurança) e 6 (constantes fixas — namespace UUID)
- `src/config_loader.py`, `src/database.py`, `src/storage_manager.py` já implementados — leia os
  três arquivos reais para casar exatamente com as assinaturas implementadas

## Entregáveis
- `src/pipeline.py`
- `tests/test_pipeline.py` (suíte pytest aprovada — use mocks/fakes para `StorageManager` e
  `Database`; cubra especialmente: hash com `business_key_field` preenchido, hash com
  `business_key_field == ""` usando o payload inteiro exceto `CONTROL_FIELDS`, e o tratamento de
  mídia órfã conforme `orphaned_media_hours`)

## Requisitos específicos

1. `CONTROL_FIELDS = frozenset({"operacao", "propriedade", "id"})` e
   `resolve_business_key_source(payload: dict, business_key_field: str) -> str`:
   - se `business_key_field == ""` (padrão): monte `{k: v for k, v in payload.items() if k not in
     CONTROL_FIELDS}` e serialize com `json.dumps(..., sort_keys=True, separators=(",", ":"),
     ensure_ascii=False)` — essa string determinística é a fonte do hash (não há chave de negócio
     fixa; todo o conteúdo de dados participa, exceto os campos de controle);
   - se `business_key_field` estiver preenchido (ex.: `"cpf"`): resolva o valor por dot-path no
     payload e aplique `clean_business_key`.
2. `clean_business_key(value: str, field_name: str) -> str`: se `field_name == "cpf"`, mantenha
   somente dígitos (`re.sub(r"\D", "", value)`); caso contrário, `value.strip().lower()`. Trate
   valores em `null_string_values` (da config) como ausentes/erro de validação, não como string
   vazia silenciosa.
3. `compute_uuid5(source: str, namespace: uuid.UUID) -> uuid.UUID`: `uuid.uuid5(namespace,
   source)`, onde `source` vem de `resolve_business_key_source`.
4. `IngestionPipeline.run_once()` deve, para cada repositório com `role == "input"`:
   - listar arquivos via `StorageManager.list_files`;
   - classificar cada arquivo como "JSON descritor" (extensão `.json`) ou "mídia" (demais
     extensões);
   - para JSON: ler e parsear; validar que contém `"operacao"` (um dos 4 valores válidos de
     CONTRACTS.md §6); se inválido, mover para `/trash` e registrar log de erro (sem lançar
     exceção não tratada);
   - calcular `id` via `resolve_business_key_source` + `compute_uuid5`, usando
     `config.uuid_namespace` e `config.business_key_field`; injetar esse `id` no payload antes de
     enviar ao banco;
   - resolver o nome do arquivo de mídia associado usando `media_reference_json_path` (ex.:
     `"midia.arquivo"`, resolvido por navegação de dicionário separada por ponto);
   - chamar `Database.call_processar_operacao_json`; em caso de sucesso, mover a mídia associada
     (se houver) para o repositório `storage_media` e apagar o JSON do disco de origem; em caso
     de erro, mover o JSON (e a mídia, se houver) para `/trash`;
   - para arquivos de mídia sem JSON descritor correspondente ainda presente na mesma pasta:
     verificar `file_age_hours`; se maior que `prazos.orphaned_media_hours`, mover para
     `/trash`; caso contrário, deixar para reavaliação no próximo ciclo.
4. `IngestionPipeline.run_trash_maintenance()`: chama `StorageManager.compress_trash` e depois
   `purge_old_trash_archives` com `prazos.trash_cleanup_days`.
5. Todas as exceções inesperadas dentro do processamento de **um** arquivo devem ser capturadas e
   logadas, permitindo que o loop continue com os demais arquivos do lote (não propague para
   `main.py` a menos que seja um erro de infraestrutura, ex.: `OSError` ao acessar pastas).
6. Nunca confie no nome do arquivo de mídia lido do JSON sem passar pela sanitização do
   `StorageManager` (não implemente sanitização própria aqui — delegue).

## Validação
- `get_errors` no arquivo.
- `uv run python -c "import src.pipeline"` para checar importação limpa.
- Se fizer sentido, escreva um pequeno teste manual local (não crie arquivos de teste formais a
  menos que a memória do repositório indique que testes automatizados foram aprovados).

## Ao terminar
Atualize `/memories/repo/rewrite-plan.md` marcando o Módulo 06 como concluído e liste suposições
(ex.: formato exato de navegação do `media_reference_json_path`).
