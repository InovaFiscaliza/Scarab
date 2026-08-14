# Contratos Técnicos — Reescrita Scarab (Arquitetura PostgreSQL/Podman)

> **Este documento é a fonte única de verdade** para nomes, assinaturas, esquemas e regras de
> segurança usados por todos os módulos da nova arquitetura. Qualquer agente que implemente um
> módulo deve seguir estritamente estas definições. Divergências ou lacunas devem ser reportadas
> como "suposição/assunção" no relatório final do módulo — nunca decididas silenciosamente.
>
> Ver também: [PLAN.md](./PLAN.md) para visão geral, mapeamento conceitual e ordem de construção.

---

## 1. Esquema de configuração

### 1.1 Arquivo `config/default_config.json` (exemplo de referência)

```json
{
  "name": "scarab",
  "check_period_seconds": 10,
  "maximum_errors_before_exit": 5,
  "uuid_namespace": "38d60acc-fe97-5757-be97-834773f507f2",
  "business_key_field": "",
  "media_reference_json_path": "midia.arquivo",
  "null_string_values": ["", "NA", "N/A", "null", "None"],
  "repositories": [
    { "name": "local_inbound", "type": "local", "path": "/app/data/inbound", "role": "input" },
    { "name": "sharepoint_media", "type": "sharepoint", "path": "/sites/Dev/Docs", "role": "storage_media" }
  ],
  "prazos": {
    "orphaned_media_hours": 24,
    "trash_cleanup_days": 7
  },
  "trash_path": "/app/data/trash",
  "max_file_size_bytes": 52428800,
  "database": {
    "host": "localhost",
    "port": 5432,
    "dbname": "scarab",
    "user": "scarab_app",
    "password_env": "SCARAB_DB_PASSWORD",
    "sslmode": "prefer",
    "min_pool_size": 1,
    "max_pool_size": 5
  },
  "sharepoint": null,
  "log": {
    "level": "DEBUG",
    "screen_output": true,
    "file_output": false,
    "file_path": [],
    "format": ["%(asctime)s", "%(module)s: %(funcName)s:%(lineno)d", "%(name)s[%(process)d]", "%(levelname)s", "%(message)s"],
    "separator": " | "
  }
}
```

**Regra de segredos:** `database.password_env` e `sharepoint.client_secret_env` guardam o **nome**
de uma variável de ambiente, nunca o segredo em si (ver §4). `config/config.json` (gitignored)
pode sobrescrever qualquer campo acima; campos ausentes herdam do default via merge raso por seção.

**`business_key_field` em branco (`""`, valor padrão):** não existe chave de negócio fixa
pré-definida. Quando este campo estiver em branco, `pipeline.py` calcula o UUIDv5 a partir de
**todo o conteúdo de dados do payload**, excluindo os campos de controle listados em
`CONTROL_FIELDS` (§6) — nunca a partir de um campo específico. Quando `business_key_field` for
preenchido (ex.: `"cpf"` ou `"email"`), o comportamento alternativo (campo único, limpo) é usado.
Ver §3.4 e §6 para o algoritmo exato.

### 1.2 Tabela de campos

| Campo | Tipo | Herdado do Scarab atual? | Descrição |
|---|---|---|---|
| `name` | `str` | sim (`name`) | Nome da instância, usado em logs |
| `check_period_seconds` | `int` | sim (`check period in seconds`) | Intervalo do loop principal |
| `maximum_errors_before_exit` | `int` | sim | Erros consecutivos antes de encerrar |
| `uuid_namespace` | `str` (UUID) | novo | Namespace fixo para `uuid.uuid5()` — ver §6 |
| `business_key_field` | `str` | novo | Chave de negócio; **padrão `""`** (em branco) = usa todo o payload (exceto `CONTROL_FIELDS`) para o hash; se preenchido (ex.: `"cpf"`), usa só esse campo, limpo |
| `media_reference_json_path` | `str` | novo | Caminho "dot notation" dentro do JSON para o nome do arquivo de mídia |
| `null_string_values` | `list[str]` | sim | Strings tratadas como nulas ao limpar a chave de negócio |
| `repositories` | `list[RepositoryConfig]` | generaliza `folders.post`/`folders.get` | Repositórios de entrada/armazenamento de mídia |
| `prazos.orphaned_media_hours` | `int` | novo (inspirado em `clean period in hours`) | Tempo de espera por descritor JSON antes de mover mídia órfã para `/trash` |
| `prazos.trash_cleanup_days` | `int` | generaliza `clean period in hours` | Idade máxima de arquivos compactados em `/trash` |
| `trash_path` | `str` | novo | Diretório local usado para arquivos rejeitados e mídias órfãs |
| `max_file_size_bytes` | `int` | novo | Limite aplicado antes de carregar JSON/mídia em memória |
| `database.*` | — | novo | Conexão PostgreSQL (psycopg3) |
| `sharepoint` | `SharePointConfig \| None` | novo | Credenciais Client Credentials para repositórios `type: "sharepoint"` |
| `log.*` | — | sim, mesma filosofia | Nível, saída tela/arquivo, formato |

### 1.3 Estrutura de um repositório

```json
{ "name": "str (único)", "type": "local | sharepoint", "path": "str", "role": "input | storage_media" }
```

- `role: "input"`: pastas monitoradas para novos arquivos (JSON descritores + mídias), equivalente
  a `folders.post` no Scarab atual.
- `role: "storage_media"`: destino final de mídias após processamento bem-sucedido do JSON
  associado, equivalente a `folders.get`.
- Pode haver múltiplos repositórios de cada papel (lista), assim como o Scarab atual suporta
  múltiplas pastas `post` e múltiplas pastas `get` por padrão.

---

## 2. Esquema do banco de dados

### 2.1 Tabela `clientes_docs`

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `UUID` | Chave primária. Calculada em Python via UUIDv5 (§6), nunca gerada pelo banco. |
| `dados` | `JSONB NOT NULL` | Conteúdo consolidado do JSON recebido (sem a chave `"operacao"`). |
| `criado_em` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Auditoria. |
| `atualizado_em` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Atualizada a cada `UPDATE`/`UPSERT`. |

Índice recomendado: `GIN` sobre `dados` para permitir consultas por chave dentro do JSONB.

### 2.2 Tabela `carga_historico`

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `BIGSERIAL` | Chave primária auto-incremental. |
| `nome_original_arquivo` | `TEXT NOT NULL` | Nome do arquivo JSON recebido. |
| `conteudo_json_bruto` | `JSONB NOT NULL` | Payload bruto recebido (incluindo `"operacao"`). |
| `timestamp_processamento` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |
| `status` | `TEXT NOT NULL CHECK (status IN ('SUCESSO','ERRO'))` | |
| `mensagem_erro` | `TEXT` | `NULL` quando `status = 'SUCESSO'`. |
| `cliente_id` | `UUID` | **Sem `FOREIGN KEY`** — ver aviso abaixo. |

> ⚠️ **Não adicionar `REFERENCES clientes_docs(id)` em `cliente_id`.** Em `DELETE_REGISTRO`, o
> registro em `clientes_docs` é removido *antes* do log em `carga_historico` ser gravado dentro da
> mesma função; uma FK quebraria essa gravação. Mantenha `cliente_id` como `UUID` solto.

### 2.3 Função `processar_operacao_json`

Assinatura (função, não procedure, para simplificar a chamada via psycopg3 com `SELECT`):

```sql
CREATE OR REPLACE FUNCTION processar_operacao_json(
    p_nome_arquivo TEXT,
    p_payload JSONB
)
RETURNS TABLE (status TEXT, mensagem TEXT, id UUID)
LANGUAGE plpgsql
AS $$ ... $$;
```

Regras de negócio (chave raiz `"operacao"` do payload):

| Valor de `operacao` | Comportamento |
|---|---|
| `INSERT` / `UPDATE` | `UPSERT` em `clientes_docs`: `ON CONFLICT (id) DO UPDATE SET dados = clientes_docs.dados \|\| EXCLUDED.dados, atualizado_em = now()`. O operador `\|\|` mescla sem apagar chaves existentes. |
| `DELETE_REGISTRO` | `DELETE FROM clientes_docs WHERE id = v_id`. |
| `REMOVER_PROPRIEDADE` | Requer campo adicional `"propriedade"` no payload (nome da chave a remover). Usa o operador `-`: `UPDATE clientes_docs SET dados = dados - v_propriedade WHERE id = v_id`. |

Em **todos** os casos, a função grava uma linha em `carga_historico` (status `SUCESSO` ou `ERRO`,
usando um bloco `EXCEPTION WHEN OTHERS` — que em PL/pgSQL cria um *savepoint* implícito, permitindo
registrar o erro sem perder a transação externa). A função sempre retorna `(status, mensagem, id)`
para que `database.py` saiba o resultado sem consulta adicional.

Referência de implementação (rascunho a refinar no Módulo 03, não copiar literalmente sem revisão):

```sql
CREATE OR REPLACE FUNCTION processar_operacao_json(
    p_nome_arquivo TEXT,
    p_payload JSONB
)
RETURNS TABLE (status TEXT, mensagem TEXT, id UUID)
LANGUAGE plpgsql
AS $$
DECLARE
    v_operacao TEXT := p_payload->>'operacao';
    v_id UUID := (p_payload->>'id')::UUID;
    v_propriedade TEXT;
BEGIN
    IF v_operacao IS NULL OR v_id IS NULL THEN
        RAISE EXCEPTION 'payload sem "operacao" ou "id"';
    END IF;

    CASE v_operacao
        WHEN 'INSERT', 'UPDATE' THEN
            INSERT INTO clientes_docs (id, dados)
            VALUES (v_id, (p_payload - 'operacao'))
            ON CONFLICT (id) DO UPDATE
                SET dados = clientes_docs.dados || EXCLUDED.dados,
                    atualizado_em = now();
        WHEN 'DELETE_REGISTRO' THEN
            DELETE FROM clientes_docs WHERE id = v_id;
        WHEN 'REMOVER_PROPRIEDADE' THEN
            v_propriedade := p_payload->>'propriedade';
            IF v_propriedade IS NULL THEN
                RAISE EXCEPTION 'REMOVER_PROPRIEDADE requer o campo "propriedade"';
            END IF;
            UPDATE clientes_docs
                SET dados = dados - v_propriedade, atualizado_em = now()
                WHERE id = v_id;
        ELSE
            RAISE EXCEPTION 'operacao desconhecida: %', v_operacao;
    END CASE;

    INSERT INTO carga_historico (nome_original_arquivo, conteudo_json_bruto, status, cliente_id)
    VALUES (p_nome_arquivo, p_payload, 'SUCESSO', v_id);

    RETURN QUERY SELECT 'SUCESSO'::TEXT, NULL::TEXT, v_id;
EXCEPTION WHEN OTHERS THEN
    INSERT INTO carga_historico (nome_original_arquivo, conteudo_json_bruto, status, mensagem_erro, cliente_id)
    VALUES (p_nome_arquivo, p_payload, 'ERRO', SQLERRM, v_id);

    RETURN QUERY SELECT 'ERRO'::TEXT, SQLERRM::TEXT, v_id;
END;
$$;
```

---

## 3. Contratos dos módulos Python

> Assinaturas obrigatórias. Implementações internas ficam a critério do módulo, mas nomes públicos,
> tipos e comportamento devem corresponder exatamente ao descrito aqui, para que módulos construídos
> isoladamente (por agentes diferentes) se integrem sem retrabalho.

### 3.1 `src/config_loader.py`

**Decisão confirmada: `pydantic` (não `dataclasses`).**

```python
from pydantic import BaseModel, ConfigDict
from typing import Literal

RepositoryType = Literal["local", "sharepoint"]
RepositoryRole = Literal["input", "storage_media"]

class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)

class RepositoryConfig(_Frozen):
    name: str
    type: RepositoryType
    path: str
    role: RepositoryRole

class DeadlinesConfig(_Frozen):  # "prazos"
    orphaned_media_hours: int
    trash_cleanup_days: int

class DatabaseConfig(_Frozen):
    host: str
    port: int
    dbname: str
    user: str
    password_env: str
    sslmode: str
    min_pool_size: int
    max_pool_size: int
    # property `password` reads os.environ[self.password_env] on demand (never stored/cached in plain text)

class SharePointConfig(_Frozen):
    tenant_id: str
    client_id: str
    client_secret_env: str
    site_url: str
    # property `client_secret` reads os.environ[self.client_secret_env]

class LogConfig(_Frozen):
    level: str
    screen_output: bool
    file_output: bool
    file_path: list[str]
    format: list[str]
    separator: str

class AppConfig(_Frozen):
    name: str
    check_period_seconds: int
    maximum_errors_before_exit: int
    uuid_namespace: str
    business_key_field: str  # "" (default) = hash the whole payload; otherwise a single field name
    media_reference_json_path: str
    null_string_values: list[str]
    repositories: list[RepositoryConfig]
    prazos: DeadlinesConfig
    database: DatabaseConfig
    sharepoint: SharePointConfig | None
    log: LogConfig
    trash_path: str
    max_file_size_bytes: int

def load_config(config_dir: str) -> AppConfig: ...
def get_config(config_dir: str | None = None) -> AppConfig: ...  # cached singleton (functools.lru_cache ou equivalente)
```

Reaproveitar o padrão já usado em `legacy/src/config_handler.py` (legado): **docstring literal
logo abaixo de cada atributo**, para que o VS Code exiba a descrição no hover — essa convenção do
Pyright/Pylance funciona da mesma forma em campos de `pydantic.BaseModel`, não é exclusiva de
`dataclass`.

### 3.2 `src/database.py`

```python
from dataclasses import dataclass
from typing import Literal
import uuid

@dataclass(frozen=True)
class ProcessResult:
    status: Literal["SUCESSO", "ERRO"]
    message: str | None
    client_id: uuid.UUID | None

class Database:
    def __init__(self, config: DatabaseConfig) -> None: ...
    def call_processar_operacao_json(self, filename: str, payload: dict) -> ProcessResult: ...
    def health_check(self) -> bool: ...
    def close(self) -> None: ...
```

Chamada obrigatoriamente parametrizada (nunca concatenar/format string com dados do payload):

```python
from psycopg.types.json import Jsonb
cur.execute(
    "SELECT status, mensagem, id FROM processar_operacao_json(%s, %s)",
    (filename, Jsonb(payload)),
)
row = cur.fetchone()
```

### 3.3 `src/storage_manager.py`

```python
from typing import Protocol

class StorageBackend(Protocol):
    def list_files(self, path: str) -> list[str]: ...
    def read_file(self, path: str, filename: str) -> bytes: ...
    def write_file(self, path: str, filename: str, content: bytes) -> None: ...
    def delete_file(self, path: str, filename: str) -> None: ...
    def file_age_hours(self, path: str, filename: str) -> float: ...
    def file_size_bytes(self, path: str, filename: str) -> int: ...

class StorageManager:
    def __init__(self, repositories: list[RepositoryConfig], sharepoint: SharePointConfig | None) -> None: ...
    def list_files(self, repository_name: str) -> list[str]: ...
    def read_file(self, repository_name: str, filename: str) -> bytes: ...
    def write_file(self, repository_name: str, filename: str, content: bytes) -> None: ...
    def delete_file(self, repository_name: str, filename: str) -> None: ...
    def move_to_trash(self, repository_name: str, filename: str, trash_path: str) -> None: ...
    def file_age_hours(self, repository_name: str, filename: str) -> float: ...
    def file_size_bytes(self, repository_name: str, filename: str) -> int: ...
    def validate_filename(self, repository_name: str, filename: str) -> str: ...
    def compress_trash(self, trash_path: str) -> None: ...
    def purge_old_trash_archives(self, trash_path: str, older_than_days: int) -> None: ...
```

Duas implementações internas de `StorageBackend` (`_LocalBackend`, `_SharePointBackend`),
selecionadas por `RepositoryConfig.type`. **A sanitização de nome de arquivo (§4) deve acontecer
dentro de `StorageManager`**, não nos módulos que o chamam.

### 3.4 `src/pipeline.py`

```python
import uuid

CONTROL_FIELDS: frozenset[str] = frozenset({"operacao", "propriedade", "id"})
"""Root JSON keys that are never part of the business content used to compute the UUIDv5."""

def clean_business_key(value: str, field_name: str) -> str: ...
    # field_name == "cpf" -> mantém somente dígitos
    # demais campos (ex.: "email") -> strip() + lower()

def resolve_business_key_source(payload: dict, business_key_field: str) -> str: ...
    # business_key_field == "" (padrão): serializa {k: v for k, v in payload.items()
    #   if k not in CONTROL_FIELDS} com json.dumps(..., sort_keys=True, separators=(",", ":"),
    #   ensure_ascii=False) -> string determinística usada como fonte do hash.
    # business_key_field != "": resolve o campo por dot-path no payload e aplica
    #   clean_business_key(valor, business_key_field).

def compute_uuid5(source: str, namespace: uuid.UUID) -> uuid.UUID: ...
    # uuid.uuid5(namespace, source)

class IngestionPipeline:
    def __init__(
        self,
        config: AppConfig,
        storage: StorageManager,
        db: Database,
        trash_path: str | None = None,
        max_file_size_bytes: int | None = None,
    ) -> None: ...
    def run_once(self) -> None: ...              # um ciclo completo de varredura/processamento
    def run_trash_maintenance(self) -> None: ...  # compactação + purga da lixeira
```

### 3.5 `src/main.py`

```python
def main(config_dir: str) -> None: ...

if __name__ == "__main__":
    ...  # valida argv, chama main(config_dir)
```

Deve seguir o mesmo padrão de `legacy/src/scarab.py` (legado): handlers para `SIGINT`, `SIGTERM`,
`SIGBREAK`, flag global `keep_running`, contagem de erros consecutivos com
`maximum_errors_before_exit`, `time.sleep(config.check_period_seconds)` entre ciclos, encerramento
gracioso chamando `db.close()`.

---

## 4. Segurança obrigatória (OWASP Top 10)

1. **Injeção de SQL:** todas as chamadas usam parâmetros ligados (`%s` + tupla), nunca
   concatenação/f-string com dados do payload ou nomes de arquivo.
2. **Path traversal / escrita arbitrária:** o nome do arquivo de mídia é lido de **dentro do JSON**
   recebido (não confiável). Antes de qualquer leitura/escrita/exclusão em disco:
   - aplicar `os.path.basename()` para descartar qualquer componente de diretório;
   - resolver o caminho final (`Path(...).resolve()`) e confirmar que permanece **dentro** do
     diretório raiz do repositório configurado (`Path.is_relative_to`);
   - se a validação falhar, tratar como arquivo inválido (mover para `/trash`, registrar erro) —
     nunca lançar exceção não tratada que derrube o loop principal.
3. **Segredos:** `database.password_env` / `sharepoint.client_secret_env` apontam para variáveis de
   ambiente. Segredos nunca são lidos de `config.json`, nunca logados, nunca hardcoded. `.gitignore`
   deve cobrir `config/config.json` e `.env`.
4. **Validação de entrada:** antes de processar, confirmar que o JSON tem `"operacao"` (um dos 4
   valores válidos) e o campo `business_key_field` presente e não vazio. Caso contrário, mover para
   `/trash` sem chamar o banco.
5. **Negação de serviço:** aplicar um limite de tamanho de arquivo configurável antes de ler
   JSON/mídia para memória.
6. **Privilégio mínimo no banco:** o usuário `database.user` deve ter apenas `EXECUTE` na função e
   acesso às duas tabelas — nunca superusuário. Documentar isso com `GRANT` de exemplo comentado em
   `db/init.sql`.
7. **TLS:** conexões SharePoint sempre via HTTPS (padrão da biblioteca), sem desabilitar verificação
   de certificado. `database.sslmode` não deve ser `disable` em ambientes que não sejam de
   desenvolvimento local.
8. **Logs:** não logar o conteúdo completo de `dados`/JSONB (pode conter CPF/e-mail) em nível
   `INFO`; reservar payloads completos para `DEBUG`.

---

## 5. Convenções de código

- **Python:** identificadores, docstrings e comentários em **inglês**; PEP 8; *type hints* em 100%
  das assinaturas públicas; docstrings estilo Google/Sphinx; padrão de docstring literal por
  atributo (ver §3.1) idêntico ao já usado no projeto atual.
- **SQL:** nomes de tabelas/colunas/função mantidos em **português**, exatamente como especificados
  pelo usuário (`clientes_docs`, `carga_historico`, `processar_operacao_json`, `operacao`,
  `DELETE_REGISTRO`, `REMOVER_PROPRIEDADE`, `propriedade`) — não traduzir.
- **Markdown (README, docs de arquitetura):** **Português do Brasil**.
- Nenhum módulo deve alterar arquivos fora do seu escopo declarado (ver prompt de cada módulo em
  `.github/prompts/rewrite/`).

---

## 6. Constantes fixas

- **Namespace UUID:** `38d60acc-fe97-5757-be97-834773f507f2`, calculado uma única vez com
  `uuid.uuid5(uuid.NAMESPACE_DNS, "scarab.inovafiscaliza.gov.br")` e gravado como literal em
  `config/default_config.json` (`uuid_namespace`). **Não recalcular em runtime** — deve ser lido do
  config e convertido com `uuid.UUID(config.uuid_namespace)`.
- **Prazos padrão:** `orphaned_media_hours = 24`, `trash_cleanup_days = 7` (mesmos valores do
  exemplo do enunciado original).
- **Operações válidas:** `INSERT`, `UPDATE`, `DELETE_REGISTRO`, `REMOVER_PROPRIEDADE` (exatamente
  estes literais, maiúsculos).
- **`business_key_field` padrão:** string vazia (`""`). Não há campo de negócio fixo — cada
  instalação decide via config. Quando vazio, o hash é calculado sobre todo o conteúdo do
  payload, exceto `CONTROL_FIELDS`.
- **`CONTROL_FIELDS`:** `{"operacao", "propriedade", "id"}` — chaves de controle sempre excluídas
  do cálculo do UUIDv5 quando `business_key_field == ""`.
