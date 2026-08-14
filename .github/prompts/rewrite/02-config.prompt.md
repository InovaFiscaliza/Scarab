---
description: "Módulo 02 da reescrita Scarab: config/default_config.json e src/config_loader.py"
agent: rewrite-builder
---
Implemente o **Módulo 02 (Configuração)** da reescrita do Scarab.

## Leitura obrigatória antes de codificar
- [CONTRACTS.md](../../../docs/rewrite/CONTRACTS.md) — seções 1 (esquema de configuração), 3.1
  (contrato do módulo), 4 (segurança) e 5 (convenções)
- `/memories/repo/rewrite-plan.md` — decisões confirmadas relevantes a este módulo

## Entregáveis
- `config/default_config.json`
- `src/config_loader.py`
- `tests/test_config_loader.py` (suíte pytest aprovada — cubra ao menos: merge default+override,
  validação de `type`/`role` inválidos, leitura de segredo via variável de ambiente, e o caso
  `business_key_field == ""`)

## Requisitos específicos

1. `default_config.json` deve seguir **exatamente** o esquema de CONTRACTS.md §1.1, incluindo
   `repositories`, `prazos`, `database` (com `password_env`, nunca uma senha literal),
   `sharepoint: null` por padrão, `log`, `check_period_seconds`, `maximum_errors_before_exit`,
   `uuid_namespace` (use o literal `"38d60acc-fe97-5757-be97-834773f507f2"`, não recalcule),
   `business_key_field` (use `""`, string vazia, como padrão — não preencha com `"cpf"` nem
   qualquer outro valor), `media_reference_json_path`, `null_string_values`.
2. `config_loader.py` deve expor as classes imutáveis descritas em CONTRACTS.md §3.1
   (`RepositoryConfig`, `DeadlinesConfig`, `DatabaseConfig`, `SharePointConfig`, `LogConfig`,
   `AppConfig`), usando **pydantic** (`BaseModel` com `model_config = ConfigDict(frozen=True)`) —
   decisão já confirmada pelo usuário, não use `dataclasses`.
3. Reaproveite o padrão de docstring por atributo já usado em `legacy/src/config_handler.py`
   (docstring literal logo abaixo de cada atributo) para integração com o hover do VS Code (essa
   convenção do Pyright/Pylance funciona igual em campos pydantic). Não copie código do módulo
   legado — apenas o padrão estilístico.
4. Implemente merge/fallback: carregar `default_config.json`; se `config/config.json` existir
   (`Path.exists()`), sobrepor por seção (chaves ausentes no override herdam do default). Merge
   raso é suficiente (nível de seção, não precisa recursão profunda além de um nível).
5. `DatabaseConfig.password` e `SharePointConfig.client_secret` devem ser propriedades
   (`@property`) que leem `os.environ[self.password_env]` / `os.environ[self.client_secret_env]`
   sob demanda — nunca armazenar o segredo em texto puro no objeto de config. Levantar um erro
   claro (não um `KeyError` genérico) se a variável de ambiente não estiver definida.
6. Exponha um singleton via `get_config(config_dir: str | None = None) -> AppConfig`, cacheado
   (ex.: `functools.lru_cache(maxsize=1)`).
7. Valide o campo `type` de cada repositório (`"local"` ou `"sharepoint"`) e `role`
   (`"input"` ou `"storage_media"`) na carga, levantando erro descritivo em caso de valor
   inválido — mesmo espírito de validação do `config_handler.py` legado.

## Validação
- `get_errors` nos arquivos criados.
- Se o ambiente `uv` já tiver sido inicializado pelo Módulo 00, rode
  `uv run python -c "from src.config_loader import get_config; print(get_config('config'))"`
  (ajuste o caminho conforme a implementação) e relate o resultado.

## Ao terminar
Atualize `/memories/repo/rewrite-plan.md` marcando o Módulo 02 como concluído e liste suposições
(ex.: nomes exatos de variáveis de ambiente escolhidos, valor padrão de `business_key_field`).
