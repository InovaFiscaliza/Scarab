# Exemplos e sandbox de testes

Este diretório reúne cenários usados nos testes funcionais ponta a ponta do Scarab. Os cenários
ficam divididos em três áreas:

```text
examples/
├── sandbox/  # cópia de trabalho usada durante a execução dos testes
├── src/      # scripts para restaurar e armazenar cenários
└── store/    # snapshots compactados no formato test_NN.tgz
```

## Sandbox descartável

O diretório `sandbox` é uma área **efêmera**. Ele pode ser alterado pelo daemon durante o teste e
apagado por completo ao restaurar outro cenário. Portanto:

- não mantenha nele arquivos únicos, credenciais ou qualquer dado que não possa ser recriado;
- restaure um snapshot antes de cada teste completo para começar de um estado conhecido;
- considere permanentes somente as alterações gravadas intencionalmente em um arquivo de `store`;
- use `add.bat` ou `upt.bat` apenas depois de revisar o conteúdo que será preservado.

No Compose publicado, essa pasta do host é montada como `/mnt/share01` dentro do container. O nome
interno imita um ponto de montagem Linux de produção, mas não torna o sandbox permanente. Em uma
implantação real, a origem do bind mount deve ser substituída por armazenamento persistente do
host; outros repositórios podem ser montados como `/mnt/share02`, `/mnt/share03` e assim por diante.

O diretório `examples/store`, que contém os arquivos `test_NN.tgz`, não deve ser confundido com
`examples/sandbox/store`. Este último pertence à estrutura do cenário e é uma área legada, não
utilizada pelo pipeline atual.

Cada snapshot contém o diretório `sandbox` completo, incluindo sua configuração e seus arquivos de
entrada. A estrutura e a execução do cenário funcional atual estão descritas em
[sandbox/README.md](sandbox/README.md).

## Pré-requisitos

Os utilitários em `src` são scripts em lote para Windows e exigem `tar.exe` disponível no `PATH`.
É possível confirmar o requisito no Prompt de Comando ou no PowerShell:

```powershell
where.exe tar.exe
```

Os scripts localizam `sandbox` e `store` a partir da própria pasta em que estão instalados. Assim,
podem ser chamados a partir de qualquer diretório; os exemplos abaixo partem da raiz do
repositório.

## Restaurar um cenário: `rst.bat`

Restaura um snapshot de `store` como a nova cópia de trabalho em `sandbox`:

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

Cria em `store` um novo snapshot com o conteúdo atual de `sandbox`:

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
script somente atualiza um arquivo que já exista em `store`. Como a operação sobrescreve o snapshot,
use-a apenas quando a mudança fizer parte do mesmo cenário; para preservar ambos os estados, use
`add.bat`.

## Fluxo recomendado para um teste completo

1. Restaure o cenário desejado com `rst.bat` para recriar o sandbox em um estado conhecido.
2. Faça somente os ajustes necessários nos arquivos e na configuração dentro de `sandbox`.
3. Execute a solução completa conforme [sandbox/README.md](sandbox/README.md), usando o
	`config.json` do cenário.
4. Verifique o resultado no PostgreSQL e inspecione as áreas `post`, `get` e `trash` do sandbox.
5. Para descartar o resultado e repetir o teste, execute `rst.bat` novamente.
6. Para preservar o estado como cenário, use `add.bat`; para corrigir deliberadamente o snapshot
	de origem, use `upt.bat`.

Esse ciclo mantém os testes reproduzíveis: os snapshots permanecem em `store`, enquanto o
`sandbox` pode ser consumido, modificado e recriado sem ser tratado como armazenamento permanente.
