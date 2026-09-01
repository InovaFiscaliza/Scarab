# Teste funcional ponta a ponta

Este diretório é a cópia de trabalho dos cenários compactados em `examples/data`. O snapshot
`test_00.tgz` representa um baseline vazio; `test_01.tgz` contém, em `store`, seis descritores que
demonstram uma sequência de operações sobre três registros.

## Sequência

1. `01` e `02`: criam os registros `REG-001` e `REG-002`, com `codigo`, `nome` e `cidade`.
2. `03`: cria `REG-003` acrescentando o campo `email`.
3. `04` e `05`: atualizam `REG-001` e `REG-002`, acrescentando `email` por UPSERT.
4. `06`: remove `REG-002`.

O campo `codigo` é usado como chave de negócio para que os `UPDATE` encontrem os registros
criados pelos `INSERT`. Isso é necessário porque o valor padrão vazio de `business_key_field`
calcula o UUIDv5 a partir de todo o payload; nesse modo, adicionar um campo produziria outro ID.

## Estrutura

```text
sandbox/
├── config.json       # override usado pelo teste
├── post/              # estado da entrada preservado no cenário
├── get/               # estado da saída preservado no cenário
├── store/             # fixtures mantidas para execução do teste funcional
└── trash/             # estado de rejeitados e mídias órfãs
```

No laboratório remoto, o sandbox pode ser compartilhado pela estação Windows e montado sobre
`/srv/<instância>` no host Linux. Assim, `post`, `get` e `trash` correspondem diretamente a
`/mnt/post`, `/mnt/get` e `/mnt/trash` no container. `config.json` e `store` não são montados no
container; o executor usa ambos pela camada de host.

## Execução com Podman

A partir da raiz do repositório no host Linux:

```bash
sudo bash deploy/scarab-deploy.sh install \
	--environment test \
	--instance scarab-test \
	--service-user "$(id -un)" \
	--db-bind-address <IP-LAN-DO-HOST> \
	--source "$PWD"

scarab-deploy update --instance scarab-test
```

O instalador não lê este diretório. Use `share-sandbox.bat` no Windows e o comando instalado
`/usr/local/sbin/mount-host-volumes` no host Linux para sobrepor `/srv/scarab-test` com o share. A
senha SMB é lida no terminal Linux. O padrão usa credencial criptografada do systemd; em RHEL 8,
`--legacy` usa um arquivo oculto `0600` dentro de `/etc/scarab-test/.credentials`, protegido com
modo `0700`.

Na estação Windows, execute:

```powershell
.\examples\src\exe.bat `
    --host ContainerHost `
    --operation reset `
    --db-host <IP-LAN-DO-HOST> `
    --confirm-reset scarab-test
```

O executor recusa produção, limpa o banco e as três áreas, aplica este `config.json` e envia cada
fixture de `store` separadamente. O aceite é entrada, saída e lixeira vazias, dois registros finais
(`REG-001` e `REG-003`) e seis linhas `SUCESSO` em `carga_historico`. Como este cenário não possui
mídia, não se espera conteúdo em `get`.

O passo a passo completo está no
[runbook de implantação remota](https://github.com/InovaFiscaliza/Scarab/wiki/Podman-Compose-Servidor-Remoto).
