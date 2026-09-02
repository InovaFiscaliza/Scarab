<details>
    <summary>Índice</summary>
    <ol>
        <li><a href="#visão-geral">Visão Geral</a></li>
        <li><a href="#arquitetura">Arquitetura</a></li>
        <li><a href="#estrutura-do-repositório">Estrutura do Repositório</a></li>
        <li><a href="#como-funciona-o-processamento">Como Funciona o Processamento</a></li>
        <li><a href="#pré-requisitos">Pré-requisitos</a></li>
        <li><a href="#como-rodar-localmente">Como Rodar Localmente</a></li>
        <li><a href="#estrutura-do-podman-compose">Estrutura do Podman Compose</a></li>
        <li><a href="#implantação-remota-e-testes">Implantação Remota e Testes</a></li>
        <li><a href="#visão-geral-da-configuração">Visão Geral da Configuração</a></li>
        <li><a href="#licença-e-contribuição">Licença e Contribuição</a></li>
    </ol>
</details>

## Visão geral

<div>
    <picture>
        <source media="(prefers-color-scheme: dark)" srcset="./docs/images/scarab_glyph_white.svg">
        <img align="left" width="100" height="100"
             src="./docs/images/scarab_glyph.svg"
             alt="Scarab glyph">
    </picture>
</div>

O Scarab é um serviço de ingestão e persistência de documentos e metadados. A nova arquitetura
substitui a saída em arquivos por um armazenamento centralizado em PostgreSQL: o serviço recebe
descritores JSON (com ou sem mídia), valida e normaliza o payload, calcula um identificador
determinístico (UUIDv5) e delega a persistência a funções armazenadas no banco. Mídias são
armazenadas em repositórios configuráveis (local ou SharePoint) e vinculadas ao registro no banco.

O objetivo é tornar a ingestão robusta, audítável e compatível com orquestração via containers
(Podman), mantendo políticas de segurança para segredos, limpeza de arquivos órfãos e proteção
contra path traversal e injeção SQL.

<div> <a href="#visão-geral" title="De volta ao topo da página"> <picture> <source media="(prefers-color-scheme: dark)" srcset="./docs/images/up-arrow_white.svg"> <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="De volta ao topo da página" alt="De volta ao topo da página"> </picture> </a> <br><br> </div>

## Arquitetura

Diagrama de alto nível do fluxo de dados:

```mermaid
---
config:
    'theme': 'base'
    'themeVariables':
      'primaryColor': '#9090ff'
      'secondaryColor': '#808080'
      'primaryTextColor': '#eeeeee'
      'primaryBorderColor': '#ffffff'
      'lineColor': '#808080'
---
flowchart LR
    A[Front-end / Usuário] -->|deposita arquivos| B[Repositório input\nlocal ou SharePoint]
    B --> C{main.py: loop de varredura}
    C -->|classifica arquivo| D{JSON descritor\nou mídia?}
    D -->|mídia sem JSON par| F{órfã há mais de\norphaned_media_hours?}
    F -->|não| B
    F -->|sim| G["/trash"]
    D -->|JSON| E[pipeline.py: valida\n+ gera UUIDv5]
    E --> H[database.py: chama\nprocessar_operacao_json]
    H --> I[(PostgreSQL\nclientes_docs + carga_historico)]
    H -->|sucesso| J[move mídia -> storage_media\nremove JSON do disco]
    H -->|erro| G
    J --> K[Repositório storage_media\nlocal ou SharePoint]
```

Principais componentes:
- `src/main.py`: loop principal e tratamento de sinais.
- `src/pipeline.py`: validação, cálculo de UUIDv5 e orquestração por carga.
- `src/database.py`: conexão com PostgreSQL e chamada à função `processar_operacao_json`.
- `src/storage_manager.py`: abstração de repositórios (local / SharePoint) e sanitização de nomes.
- `db/`: scripts SQL com `clientes_docs`, `carga_historico` e `processar_operacao_json`.

O contrato técnico completo da configuração, dos módulos Python, do banco e das regras de
segurança está em [docs/architecture/CONTRACTS.md](docs/architecture/CONTRACTS.md).

<div> <a href="#visão-geral" title="De volta ao topo da página"> <picture> <source media="(prefers-color-scheme: dark)" srcset="./docs/images/up-arrow_white.svg"> <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="De volta ao topo da página" alt="De volta ao topo da página"> </picture> </a> <br><br> </div>

## Como funciona o processamento

Fluxo resumido:
1. O `main.py` varre repositórios `role == "input"` procurando novos arquivos.
2. Arquivos JSON são validados; o campo `operacao` deve existir e ser um dos literais suportados.
3. O `pipeline.py` resolve a fonte do `business key` (campo específico ou todo o payload limpo), aplica
   normalização (`clean_business_key`) e calcula `uuid.uuid5(namespace, source)`.
4. A aplicação chama `database.py` que executa a função SQL `processar_operacao_json(nome_arquivo, payload)`.
5. A função no banco realiza `UPSERT` / `DELETE` / remoção de propriedade conforme a `operacao`, e registra a execução em `carga_historico`.
6. Se houver mídia associada, após sucesso a mídia é movida para um repositório com `role == "storage_media"`.
7. Mídias sem JSON correspondente são mantidas por `orphaned_media_hours` e, após esse período, movidas para `/trash`.

Rotina de lixeira e manutenção: compactação periódica dos arquivos em `/trash` e remoção de arquivos mais antigos que `prazos.trash_cleanup_days`.

<div> <a href="#visão-geral" title="De volta ao topo da página"> <picture> <source media="(prefers-color-scheme: dark)" srcset="./docs/images/up-arrow_white.svg"> <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="De volta ao topo da página" alt="De volta ao topo da página"> </picture> </a> <br><br> </div>


## Estrutura do repositório

Árvore principal (resumida):

```mermaid
---
config:
    'theme': 'base'
    'themeVariables':
      'primaryColor': '#9090ff'
      'secondaryColor': '#808080'
      'primaryTextColor': '#eeeeee'
      'primaryBorderColor': '#ffffff'
      'lineColor': '#808080'
---
treeView-beta
    Scarab/
        deploy/
            Containerfile.app
            Containerfile.db
            lib/
                scarab-runtime.sh
            mount-host-volumes.sh ## configures persistent host volume mounts
            podman-compose.build.yml
            podman-compose.yml
            scarab-deploy.sh ## script used on container deployment (local)
            scarab-ops.sh ## script used for lifecycle and operational commands
            scarab-bootstrap.sh ## script used to bootstrap the environment from a linux system (remote)
            scarab-bootstrap.bat ## script used to bootstrap the environment from a Windows system (remote)
            scarab.env.example ## example environment file
        examples/ ## Sripts and resources for testing and experimentation
            /sandbox ## gitignored; local sandbox environment
            /src ## scripts to manage the sandbox environment
            /data ## archived test scenarios
        config/
            default_config.json ## default configuration file
            config.json ## gitignored; local overrides to default configuration
        db/
            init.sql
            provision-app-role.sh
            procedures.sql
        src/
            __init__.py ## marks the directory as a Python package
            main.py ## entry point of the application
            config_loader.py ## loads and parses the configuration files
            database.py ## database interaction layer
            storage_manager.py ## handles media storage operations
            pipeline.py ## orchestrates the processing pipeline
        tests/ ## python testing suite
        pyproject.toml ## Python project configuration file
        .gitignore
```

<div> <a href="#visão-geral" title="De volta ao topo da página"> <picture> <source media="(prefers-color-scheme: dark)" srcset="./docs/images/up-arrow_white.svg"> <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="De volta ao topo da página" alt="De volta ao topo da página"> </picture> </a> <br><br> </div>

## Pré-requisitos

### Desenvolvimento local

- Git para obter e versionar o código;
- Python 3.13 ou superior;
- [UV](https://docs.astral.sh/uv/) para instalar as dependências com
    `uv sync --extra dev` e executar lint e testes;
- acesso a um PostgreSQL externo somente para executar o daemon fora do stack. No stack completo,
    [deploy/podman-compose.yml](deploy/podman-compose.yml) provisiona o próprio serviço de banco;
- Podman e um provider de `podman compose` são opcionais no desenvolvimento Python e necessários
    apenas para construir imagens ou exercitar o stack completo.

### Execução do stack

No host de execução:

- Linux com Bash e utilitários básicos do sistema;
- Podman 4 ou superior e um provider de `podman compose`, como `podman-compose` 1.x;
- uma conta de serviço não-root com Podman rootless, subuids e subgids configurados;
- acesso administrativo por `root` ou `sudo` durante a instalação; os comandos de ciclo de vida
    são executados posteriormente pela conta de serviço;
- acesso aos registries das imagens e, ao usar o bootstrap, ao GitHub;
- Git para o bootstrap e para builds locais a partir de uma branch. Sem `--branch`, o bootstrap
    também requer um entre `curl`, `python3` ou `wget` para resolver a release mais recente. Essas
    ferramentas não são necessárias durante a execução com imagens imutáveis já instaladas.

Python e UV não são exigidos pelo runtime da aplicação, e um PostgreSQL externo também não é
necessário: as imagens contêm o runtime e
[deploy/podman-compose.yml](deploy/podman-compose.yml) provisiona o serviço de banco.

<div> <a href="#visão-geral" title="De volta ao topo da página"> <picture> <source media="(prefers-color-scheme: dark)" srcset="./docs/images/up-arrow_white.svg"> <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="De volta ao topo da página" alt="De volta ao topo da página"> </picture> </a> <br><br> </div>

## Como rodar localmente

1. Clone o repositório:

```powershell
git clone <repo> && cd Scarab
```

2. Instale dependências de desenvolvimento com UV:

```powershell
uv sync --extra dev
```

3. Para executar somente o daemon fora de containers, crie um override e ajuste o banco para um
    PostgreSQL acessível pela estação:

```powershell
New-Item -ItemType Directory -Force config | Out-Null
Copy-Item config/default_config.json config/config.json
# editar config/config.json, inclusive database.host
$env:SCARAB_DB_PASSWORD = "<senha-local>"
```

4. Execute ciclos de inspeção com UV:

```powershell
uv run python -m src.main config
```

O stack completo deve ser instalado em um host Linux com `scarab-deploy`, conforme a seção
[Implantação remota e testes](#implantação-remota-e-testes). O Compose de runtime exige caminhos
FHS provisionados e não deve ser iniciado diretamente do checkout.

<div> <a href="#visão-geral" title="De volta ao topo da página"> <picture> <source media="(prefers-color-scheme: dark)" srcset="./docs/images/up-arrow_white.svg"> <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="De volta ao topo da página" alt="De volta ao topo da página"> </picture> </a> <br><br> </div>

## Estrutura do Podman Compose

O runtime usa [deploy/podman-compose.yml](deploy/podman-compose.yml) em todos os ambientes.
Esse arquivo não contém build nem caminhos do checkout. O override
[deploy/podman-compose.build.yml](deploy/podman-compose.build.yml) acrescenta build somente
no laboratório. [deploy/scarab-deploy.sh](deploy/scarab-deploy.sh) limita-se a `install` e
`update`; [deploy/scarab-ops.sh](deploy/scarab-ops.sh) concentra ciclo de vida, diagnóstico e
backup, usando a biblioteca compartilhada em `deploy/lib`. O instalador também copia
[deploy/mount-host-volumes.sh](deploy/mount-host-volumes.sh) para
`/usr/local/sbin/mount-host-volumes`, auxiliando a configuração dos volumes no host.

No host, cada instância segue a hierarquia Linux:

| Host | Finalidade | Container |
|---|---|---|
| `/etc/<instância>/config` | Configuração somente leitura | `/etc/scarab` |
| `/var/lib/<instância>/postgresql` | Estado do PostgreSQL | `/var/lib/postgresql/data` |
| `/srv/<instância>/post` | Entrada depositada pelos usuários | `/mnt/post` |
| `/srv/<instância>/get` | Resultados e arquivos acessíveis aos usuários | `/mnt/get` |
| `/srv/<instância>/trash` | Arquivos rejeitados e mídias órfãs | `/mnt/trash` |
| `/var/log/<instância>` | Logs em arquivo opcionais | `/var/log/scarab` |
| `/var/backups/<instância>` | Backups lógicos no host | não montado |

Antes de atualizar uma instalação que ainda use o layout numérico anterior, pare o stack, mova a
entrada, a saída e a lixeira para os três diretórios acima e ajuste qualquer `config.json` local.
O instalador preserva overrides e não move dados automaticamente entre filesystems.

O código e as dependências são imutáveis na imagem em `/opt/scarab`. Nenhum diretório do checkout
é montado em runtime.

### Serviço `db`

O PostgreSQL usa bind mount persistente sob `/var/lib/<instância>` e publica a porta 5432 do
container no endereço IPv4 e porta do host definidos por `--db-bind-address` e `--db-port`. Se
`--db-bind-address` for omitido, um único IPv4 unicast não loopback atribuído ao host é detectado
automaticamente; múltiplos endereços exigem a opção. A
imagem executa schema, procedures e criação idempotente do papel `scarab_app` na primeira
inicialização. O instalador reaplica senha e grants mínimos em updates. Restrinja o endereço e o
firewall à rede administrativa; wildcard, loopback, multicast e endereços não atribuídos ao host
são recusados. O Compose não configura firewall nem TLS para clientes externos.

### Serviço `app`

O app executa como usuário não-root com filesystem raiz somente leitura, `/tmp` em `tmpfs`, sem
capabilities e com `no-new-privileges`. Os serviços usam rede interna e `database.host: "db"`.
`keep-id` permite escrita nos diretórios montados pelo proprietário rootless do host sem
permissões globais.

<div> <a href="#visão-geral" title="De volta ao topo da página"> <picture> <source media="(prefers-color-scheme: dark)" srcset="./docs/images/up-arrow_white.svg"> <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="De volta ao topo da página" alt="De volta ao topo da página"> </picture> </a> <br><br> </div>

## Implantação remota e testes

O fluxo remoto recomendado mantém checkout, build, containers e bind mounts no host Linux. A
estação de trabalho acessa esse host por SSH; não é necessário instalar Podman localmente para usar
as tarefas incluídas em [.vscode/tasks.json](.vscode/tasks.json).

### Bootstrap automatizado

#### Execução direta no host Linux

O script `deploy/scarab-bootstrap.sh` é executado no host Linux. Sem `--branch`, ele resolve a
release mais recente publicada no GitHub e clona sua tag em um diretório temporário sob o `HOME` da
conta de serviço. Para validar acesso sudo, Podman rootless, Compose, GitHub e os arquivos da versão
sem instalar, use `--check`:

```bash
bash deploy/scarab-bootstrap.sh \
    --branch rewrite/postgres-architecture \
    --instance scarab-test \
    --db-bind-address <IP-LAN-DO-HOST> \
    --check
```

Remova `--check` para instalar. A opção `--branch` seleciona explicitamente uma branch em vez da
última release. Se `--instance` for omitido, o bootstrap também omite esse argumento ao chamar
`scarab-deploy`, cujo padrão é `scarab`. Enquanto uma release que contenha o novo deployment não
estiver publicada, use a branch; releases antigas são recusadas quando não contêm os artefatos
necessários.

#### Execução remota pela estação Windows

Na estação Windows são necessários PowerShell, os clientes OpenSSH `ssh.exe` e `scp.exe` e acesso
SSH por chave ao host Linux. O passo a passo para gerar e proteger a chave, configurar o alias SSH
e conceder privilégio administrativo via `sudo`, sem habilitar login direto de `root`, está na
[Wiki: Acesso SSH por chave e sudo remoto](https://github.com/InovaFiscaliza/Scarab/wiki/Acesso-SSH-por-Chave-e-Sudo).

Mantenha `deploy/scarab-bootstrap.bat` e `deploy/scarab-bootstrap.sh` no mesmo diretório. O `.bat`
verifica o OpenSSH, envia o `.sh` e executa no host Linux o mesmo fluxo descrito acima:

```powershell
.\deploy\scarab-bootstrap.bat `
    --host ContainerHost `
    --branch rewrite/postgres-architecture `
    --instance scarab-test `
    --db-bind-address <IP-LAN-DO-HOST> `
    --check
```

Podman não precisa ser instalado no Windows; ele executa no host Linux. Python e UV também não são
requisitos da estação para usar o bootstrap. O SSH deve funcionar por chave, e o `sudo` remoto pode
solicitar a senha no terminal.

Em builds locais de teste, o checkout é preservado porque os próximos updates ainda precisam dele.
Com imagens imutáveis, o diretório temporário é removido. Se a instância já existir, `install`
valida ambiente e proprietário, atualiza os artefatos instalados e executa
`scarab-deploy update` como a conta rootless.

Depois de configurar o SSH, instale uma instância de teste no host:

```bash
sudo bash deploy/scarab-deploy.sh install \
    --environment test \
    --instance scarab-test \
    --service-user "$(id -un)" \
    --db-bind-address <IP-LAN-DO-HOST> \
    --source "$PWD"

scarab-deploy update --instance scarab-test
scarab-ops validate --instance scarab-test
```

O instalador exige um host com systemd/logind, habilita `linger` para a conta rootless, recarrega o
gerenciador de usuário e habilita `scarab-test.service` para o boot. O comando `update` inicia o
stack e deixa essa unidade ativa, de modo que o systemd também execute o encerramento ordenado do
Compose no shutdown. Verifique a ativação com:

```bash
loginctl show-user "$(id -un)" -p Linger
systemctl --user is-enabled scarab-test.service
systemctl --user is-active scarab-test.service
```

No runtime, banco e aplicação usam `restart: unless-stopped`. No boot, a unidade chama
`scarab-ops`, inicia o banco, aguarda o healthcheck, reaplica o papel da aplicação, executa uma
consulta `SELECT 1`, confirma a publicação configurada da porta e então valida o app. Uma partida
que falhar é repetida após 15 segundos, respeitando o limite de cinco partidas em uma janela de
cinco minutos.

O laboratório usa `/etc/scarab-test`, `/var/lib/scarab-test`, `/srv/scarab-test` e
`/var/backups/scarab-test`, exatamente como produção usa os caminhos sem `-test`. Somente o
desenvolvimento constrói imagens do checkout; runtime nunca monta o source. Para homologação com
paridade completa, forneça ao instalador os mesmos digests de imagem que serão promovidos para
produção.

Também é possível executar **Tasks: Run Task** no VS Code:

- `Scarab remoto: verificar acesso` valida SSH, Podman, Compose e o checkout;
- `Scarab remoto: sincronizar alteracoes locais` envia arquivos modificados sem copiar `.env` ou
    `config/config.json`;
- `Scarab remoto: testes unitarios Linux` executa a suíte em um container descartável;
- `Scarab remoto: validar Compose`, `subir e reconstruir`, `teste funcional`, `status`, `logs`,
    `backup do banco` e `parar` operam a instância instalada.

As tarefas operacionais usam `scarab-ops`. O teste funcional usa `examples/src/exe.bat`: ele exige
o sandbox compartilhado e montado, confirma explicitamente o reset, aplica o override do sandbox e
envia os seis arquivos de `store` um por vez. Cada etapa compara as contagens no PostgreSQL e
informa as linhas recentes de auditoria em caso de divergência. Produção usa imagens imutáveis de
registry, conta rootless dedicada, segredos provisionados e filesystems permanentes, mas conserva
a mesma topologia.

O procedimento completo, incluindo bootstrap seguro, comandos de validação, reset do laboratório
e matriz de diferenças para produção, está na
[Wiki: Podman Compose em servidor remoto](https://github.com/InovaFiscaliza/Scarab/wiki/Podman-Compose-Servidor-Remoto).

<div> <a href="#visão-geral" title="De volta ao topo da página"> <picture> <source media="(prefers-color-scheme: dark)" srcset="./docs/images/up-arrow_white.svg"> <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="De volta ao topo da página" alt="De volta ao topo da página"> </picture> </a> <br><br> </div>

## Visão geral da configuração

O arquivo `config/default_config.json` concentra os parâmetros principais:
- `repositories`: lista de repositórios com `type` (`local` | `sharepoint`) e `role` (`input` | `storage_media`).
- `prazos`: `orphaned_media_hours` (horas para considerar mídia órfã) e `trash_cleanup_days` (idade para compactação/purge).
- `trash_path`: diretório local da lixeira para arquivos rejeitados e mídias órfãs.
- `max_file_size_bytes`: limite verificado antes de carregar descritores ou mídias em memória.
- `database`: parâmetros de conexão (host, port, dbname, user) e `password_env` (nome da variável de ambiente que guarda a senha).
- `uuid_namespace`: UUID literal usado como namespace para `uuid.uuid5()` (não recalculado em runtime).
- `business_key_field`: se vazio (`""`), o UUIDv5 é calculado a partir de todo o payload (excluindo campos de controle); se preenchido, o campo indicado é usado como fonte limpa para o hash.

O `config/config.json` (gitignored) pode sobrescrever qualquer campo do default por seção.

<div> <a href="#visão-geral" title="De volta ao topo da página"> <picture> <source media="(prefers-color-scheme: dark)" srcset="./docs/images/up-arrow_white.svg"> <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="De volta ao topo da página" alt="De volta ao topo da página"> </picture> </a> <br><br> </div>

## Itens a fazer / melhorias

- [ ] Implementar funções base
- [ ] Wiki de conexão ao banco usando dbeaver
- [x] Separar instalação/atualização, operações e execução funcional remota, com acesso PostgreSQL configurável
- [ ] Implementar módulo de conversão de arquivos de entrada e injestão de dados para compatibilidade
- [ ] Implementar API REST usando PostgREST
- Implementar API para upload de mídia via HTTP usando [https://tus.io/](https://tus.io/)

<div> <a href="#visão-geral" title="De volta ao topo da página"> <picture> <source media="(prefers-color-scheme: dark)" srcset="./docs/images/up-arrow_white.svg"> <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="De volta ao topo da página" alt="De volta ao topo da página"> </picture> </a> <br><br> </div>

## Licença e contribuição

Este repositório mantém os arquivos de política e contribuição na raiz. Consulte:

- [LICENSE.md](LICENSE.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [SECURITY.md](SECURITY.md)
- [SUPPORT.md](SUPPORT.md)

Por favor, siga as diretrizes de contribuição e o código de conduta ao enviar PRs.

<div> <a href="#visão-geral" title="De volta ao topo da página"> <picture> <source media="(prefers-color-scheme: dark)" srcset="./docs/images/up-arrow_white.svg"> <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="De volta ao topo da página" alt="De volta ao topo da página"> </picture> </a> <br><br> </div>
