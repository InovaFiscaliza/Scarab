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

O sandbox não é usado pelo instalador. No laboratório remoto, ele pode ser publicado como um share
SMB da estação Windows e montado pelo host Linux sobre `/srv/<instância>`. Assim, `post`, `get` e
`trash` continuam chegando ao container como `/mnt/post`, `/mnt/get` e `/mnt/trash`, enquanto
`config.json` e `store` permanecem fora do container e são usados apenas pelo executor do cenário.

O diretório `examples/data`, que contém os arquivos `test_NN.tgz`, não deve ser confundido com
`examples/sandbox/store`. Este último guarda os descritores usados como fixtures. Em uma execução
manual, copie-os para `examples/sandbox/post`; `examples/src/exe.bat` faz essa transferência um
arquivo por vez e verifica o resultado no PostgreSQL após cada operação.

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

## Laboratório remoto com sandbox compartilhado

No Windows, restaure o cenário com as seis fixtures e publique apenas o sandbox. O segundo comando
exige um terminal elevado; ele concede acesso de alteração à conta informada, mas não lê nem
armazena sua senha:

```powershell
.\examples\src\rst.bat 1
.\examples\src\share-sandbox.bat `
    --share-name ScarabSandbox `
    --user "DOMINIO\usuario"
```

Instale a instância informando o IPv4 do host Linux no qual PostgreSQL deve aceitar conexões. O
bootstrap também aceita `--db-port` quando 5432 não estiver disponível:

```powershell
.\deploy\scarab-bootstrap.bat `
    --host ContainerHost `
    --branch rewrite/postgres-architecture `
    --instance scarab-test `
    --db-bind-address <IP-LAN-DO-HOST>
```

O host Linux precisa do pacote `cifs-utils`. O `install` copia o helper de
`deploy/mount-host-volumes.sh` para `/usr/local/sbin/mount-host-volumes`. Ele confirma a instalação
com `mount.cifs -V` e deixa cliente e servidor negociarem automaticamente o dialeto SMB. Execute-o
em um terminal SSH com TTY; ele solicitará a senha SMB diretamente no terminal e habilitará o
mount para os próximos boots:

```powershell
ssh -tt ContainerHost 'sudo /usr/local/sbin/mount-host-volumes --instance scarab-test --server <IP-DA-ESTACAO-WINDOWS> --share ScarabSandbox --username <usuario> --domain <DOMINIO> --service-user "$(id -un)" --confirm-mount scarab-test'
```

O serviço systemd do mount é `scarab-test-sandbox.service`; a credencial cifrada fica sob
`/etc/credstore.encrypted`, e somente o arquivo efêmero entregue pelo systemd aparece em `/run`.
Esse modo padrão exige systemd 250 ou mais recente e `systemd-creds`. Em RHEL 8 ou outro host com
systemd anterior, acrescente `--legacy`: a credencial ficará em
`/etc/scarab-test/.credentials/.cifs`, dentro de um diretório `0700` e arquivo `0600`, ambos de
`root`. O script recusa automaticamente o modo moderno incompatível e sugere esse fallback.
Restrinja SMB no firewall da estação ao host Linux confiável.

Depois do primeiro build, execute o cenário pela estação Windows. O reset só aceita uma instância
instalada como `test` e exige confirmação com o nome exato:

```powershell
ssh ContainerHost "scarab-deploy update --instance scarab-test"
.\examples\src\exe.bat `
    --host ContainerHost `
    --operation reset `
    --db-host <IP-LAN-DO-HOST> `
    --confirm-reset scarab-test
```

O executor apaga o banco e `post/get/trash`, aplica `sandbox/config.json`, inicia o stack e move os
seis JSON de `store` para `post` um por vez. Após cada arquivo, compara as contagens esperadas de
`clientes_docs`, histórico e sucessos; em caso de divergência, exibe as linhas recentes de
`carga_historico`. Também testa a porta TCP a partir do Windows. Se `psql.exe` e um `PGPASSFILE`
estiverem disponíveis, executa ainda a consulta diretamente pela porta publicada.

Por padrão, o cliente libpq procura `%APPDATA%\postgresql\pgpass.conf`. Provisione por um canal
seguro uma linha no formato `<host>:<porta>:scarab:scarab_app:<senha>` e defina `PGPASSFILE` caso
use outro caminho. O executor nunca lê, imprime ou transfere essa senha.

Operações não destrutivas podem ser encaminhadas pelo mesmo BAT:

```powershell
.\examples\src\exe.bat --host ContainerHost --operation status
.\examples\src\exe.bat --host ContainerHost --operation logs
```

Para preservar uma alteração do cenário, use `upt.bat`; para mantê-la como outro cenário, use
`add.bat`. Esses comandos alteram apenas os snapshots sob `examples/data`.
