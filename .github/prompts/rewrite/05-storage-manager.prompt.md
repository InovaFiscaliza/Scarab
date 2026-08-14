---
description: "Módulo 05 da reescrita Scarab: src/storage_manager.py (backends local e SharePoint)"
agent: rewrite-builder
---
Implemente o **Módulo 05 (Storage Manager)** da reescrita do Scarab.

## Leitura obrigatória antes de codificar
- [CONTRACTS.md](../../../docs/rewrite/CONTRACTS.md) — seções 3.3 (contrato do módulo) e 4
  (segurança — sanitização de nome de arquivo é **obrigatória** aqui)
- `src/config_loader.py` já implementado (Módulo 02) — leia o arquivo real para casar os nomes de
  `RepositoryConfig`/`SharePointConfig` exatamente como foram implementados

## Entregáveis
- `src/storage_manager.py`
- `tests/test_storage_manager.py` (suíte pytest aprovada — use `tmp_path`/mocks para o backend
  local e um mock/fake para o backend SharePoint, sem credenciais reais; cubra especialmente a
  sanitização de nome de arquivo/path traversal, que é um requisito de segurança obrigatório)

## Requisitos específicos

1. Defina o `Protocol` `StorageBackend` e duas implementações privadas: `_LocalBackend`
   (usa `pathlib`/`shutil`) e `_SharePointBackend` (usa `office365-rest-python-client`,
   autenticação Client Credentials via `ClientContext(site_url).with_credentials(
   ClientCredential(client_id, client_secret))`).
2. A classe pública `StorageManager` seleciona o backend correto por `RepositoryConfig.type` e
   expõe exatamente os métodos de CONTRACTS.md §3.3.
3. **Sanitização obrigatória** (dentro de `StorageManager`, antes de delegar ao backend): para
   qualquer `filename` recebido, aplique `os.path.basename()` e, para backends locais, resolva o
   caminho final e confirme que permanece dentro do diretório raiz configurado do repositório
   (`Path(...).resolve()` + `is_relative_to`). Se a validação falhar, levante uma exceção
   específica e clara (ex.: `InvalidFilenameError`) em vez de prosseguir — quem chama
   (`pipeline.py`) decide tratar isso como arquivo inválido.
4. `compress_trash(trash_path)`: compacta os arquivos atualmente soltos em `trash_path` em um
   único arquivo (`zip` ou `tar.gz`, à sua escolha, documente qual no docstring) nomeado com
   timestamp, e remove os arquivos originais após compactar com sucesso.
5. `purge_old_trash_archives(trash_path, older_than_days)`: remove arquivos compactados cuja
   idade (data de modificação) exceda `older_than_days`.
6. `file_age_hours`: calcula a idade do arquivo em horas (`(now - mtime)`, ou, para SharePoint,
   usando os metadados do item remoto).
7. Erros de rede/autenticação do SharePoint não devem derrubar o processo — capture e relate de
   forma que o chamador possa decidir (log + exceção específica, não uma falha silenciosa).

## Validação
- `get_errors` no arquivo.
- `uv run python -c "import src.storage_manager"` para checar importação limpa (o backend
  SharePoint não precisa de credenciais reais só para importar o módulo).

## Ao terminar
Atualize `/memories/repo/rewrite-plan.md` marcando o Módulo 05 como concluído e liste suposições
(ex.: formato de compressão escolhido para a lixeira).
