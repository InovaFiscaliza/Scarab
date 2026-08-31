# Exemplos e sandbox de testes

Este diretório reúne cenários usados nos testes funcionais ponta a ponta do Scarab. Os cenários
ficam divididos em três áreas:

```text
examples/
├── sandbox/  # cópia de trabalho usada durante a execução dos testes
├── src/      # scripts para restaurar e armazenar cenários
└── data/     # snapshots compactados no formato test_NN.tgz
```

## Sandbox descartável

O diretório `sandbox` é uma área **efêmera**. Ele pode ser alterado pelo daemon durante o teste e
apagado por completo ao restaurar outro cenário. Portanto:

- não mantenha nele arquivos únicos, credenciais ou qualquer dado que não possa ser recriado;
- restaure um snapshot antes de cada teste completo para começar de um estado conhecido;
- considere permanentes somente as alterações gravadas intencionalmente em um arquivo de `data`;
- use `add.bat` ou `upt.bat` apenas depois de revisar o conteúdo que será preservado.

O sandbox não é montado no runtime publicado. No ambiente de teste, o instalador extrai as fixtures
de `test_01.tgz`. Os diretórios persistentes do host são `/srv/<instância>/post`, `get` e `trash`,
montados separadamente no container como `/mnt/post`, `/mnt/get` e `/mnt/trash`.

O diretório `examples/data`, que contém os arquivos `test_NN.tgz`, não deve ser confundido com
`examples/sandbox/store`. Este último guarda os descritores usados como fixtures. Em uma execução
manual, copie-os para `examples/sandbox/post`; no teste implantado, o instalador extrai as fixtures
de `test_01.tgz` e `scarab-deploy test` as copia para `/srv/scarab-test/post`.

Cada snapshot contém o diretório `sandbox` completo, incluindo a configuração e o estado das áreas
do cenário. A estrutura e a execução do cenário funcional atual estão descritas em
[sandbox/README.md](sandbox/README.md).

## Pré-requisitos

Os utilitários em `src` são scripts em lote para Windows e exigem `tar.exe` disponível no `PATH`.
É possível confirmar o requisito no Prompt de Comando ou no PowerShell:

```powershell
where.exe tar.exe
```

Os scripts localizam `sandbox` e `data` a partir da própria pasta em que estão instalados. Assim,
podem ser chamados a partir de qualquer diretório; os exemplos abaixo partem da raiz do
repositório.

## Restaurar um cenário: `rst.bat`

Restaura um snapshot de `data` como a nova cópia de trabalho em `sandbox`:

```powershell
# Restaura test_00.tgz, usado como padrão quando o número é omitido
.\examples\src\rst.bat

# Restaura test_01.tgz
.\examples\src\rst.bat 1
```

O argumento aceita números de `0` a `99`, com ou sem zero à esquerda. Antes da extração, o script
remove recursivamente o diretório `examples/sandbox` existente. Arquivos não salvos em um snapshot
serão perdidos. A operação falha quando o arquivo solicitado não existe ou quando `tar.exe` não
está disponível.

## Criar um cenário: `add.bat`

Cria em `data` um novo snapshot com o conteúdo atual de `sandbox`:

```powershell
.\examples\src\add.bat
```

O nome é calculado a partir do maior sufixo numérico existente. Por exemplo, se `test_00.tgz` e
`test_01.tgz` existirem, será criado `test_02.tgz`. Lacunas na numeração não são reutilizadas, a
faixa válida termina em `test_99.tgz` e um arquivo existente nunca é sobrescrito por este comando.

Use este script quando o estado atual do sandbox representar um novo cenário que deve ser mantido.

## Atualizar um cenário: `upt.bat`

Substitui um snapshot existente pelo conteúdo atual de `sandbox`:

```powershell
# Atualiza test_01.tgz
.\examples\src\upt.bat 1
```

O número do cenário é obrigatório e deve estar entre `0` e `99`, com ou sem zero à esquerda. O
script somente atualiza um arquivo que já exista em `data`. Como a operação sobrescreve o snapshot,
use-a apenas quando a mudança fizer parte do mesmo cenário; para preservar ambos os estados, use
`add.bat`.

## Execução em um host Podman remoto

Instale uma instância de laboratório com `deploy/scarab-deploy.sh`. Neste contexto, as
**fixtures** são os seis descritores JSON de operações armazenados em `sandbox/store/` dentro do
snapshot `examples/data/test_01.tgz`, por exemplo `01-insert-registro-001.json`,
`04-update-registro-001-com-email.json` e `06-delete-registro-002.json`. O comando `install` extrai
esses arquivos para `/srv/scarab-test/fixtures`; o checkout não é montado no runtime:

```bash
sudo bash deploy/scarab-deploy.sh install \
  --environment test \
  --instance scarab-test \
  --service-user "$(id -un)" \
  --source "$PWD"
```

Como a conta rootless:

```bash
scarab-deploy update --instance scarab-test
scarab-deploy test --instance scarab-test
```

Em um banco recém-criado, o resultado esperado é dois registros finais e seis históricos com
status `SUCESSO`. Consulte o
[runbook de implantação remota](https://github.com/InovaFiscaliza/Scarab/wiki/Podman-Compose-Servidor-Remoto)
para configuração de SSH, `.env`, consultas de aceite, reset e diferenças obrigatórias de produção.

## Fluxo recomendado para um teste completo

1. Restaure o cenário de testes, por exemplo `test_01.tgz` com `examples/src/rst.bat` para recriar o sandbox em um estado conhecido:

  ```powershell
  .\examples\src\rst.bat 1
  ```

2. Faça somente os ajustes necessários nos arquivos e na configuração dentro de `sandbox`.
3. Depois de revisar as mudanças, atualize o snapshot consumido pelo teste com
  `examples/src/upt.bat` ou crie um novo snapshot com `examples/src/add.bat`:

  ```powershell
  .\examples\src\upt.bat 1
  ```
    ou

  ```powershell
  .\examples\src\add.bat
  ```

  `examples/src/add.bat` cria outro snapshot, por exemplo `test_02.tgz`, caso o último cenário configurado seja o `test_01.tgz`.

4. Na raiz do checkout no host Podman, reexecute o comando `install` de
  `deploy/scarab-deploy.sh`. Ele substitui as fixtures em `/srv/scarab-test/fixtures` pelos seis JSON atualizados do snapshot:

  ```bash
  sudo bash deploy/scarab-deploy.sh install \
    --environment test \
    --instance scarab-test \
    --service-user "$(id -un)" \
    --source "$PWD"
  ```

5. Execute `scarab-deploy test --instance scarab-test`.
6. Verifique o resultado no PostgreSQL e em `/srv/scarab-test/post`, `get` e `trash`.

Esse ciclo mantém os testes reproduzíveis: os snapshots permanecem em `data`, enquanto o
`sandbox` é apenas a cópia de autoria e pode ser recriado sem ser tratado como armazenamento de
runtime.
