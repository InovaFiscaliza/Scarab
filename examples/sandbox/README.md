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

O sandbox não é montado no runtime. O `config.json` referencia os pontos de montagem independentes
`/mnt/post`, `/mnt/get` e `/mnt/trash`. No host, eles correspondem a
`/srv/<instância>/post`, `/srv/<instância>/get` e `/srv/<instância>/trash`.

## Execução com Podman

A partir da raiz do repositório no host Linux:

```bash
sudo bash deploy/scarab-deploy.sh install \
	--environment test \
	--instance scarab-test \
	--service-user "$(id -un)" \
	--source "$PWD"

scarab-deploy update --instance scarab-test
scarab-deploy test --instance scarab-test
```

O instalador configura `/etc/scarab-test/config`, extrai as seis fixtures de `test_01.tgz` para
`/srv/scarab-test/fixtures` e cria os diretórios de runtime `/srv/scarab-test/post`, `get` e
`trash`. Eles são montados diretamente no container como `/mnt/post`, `/mnt/get` e `/mnt/trash`.

O comando `test` limpa o banco e os três diretórios de runtime, inicia o stack e copia as fixtures
para `/srv/scarab-test/post`. Depois, valida `clientes_docs`, `carga_historico` e que a lixeira
permaneceu vazia. Os snapshots do checkout não são alterados por essa execução.

Em um host Linux remoto, use `scarab-deploy test --instance scarab-test`. O aceite é entrada e
lixeira vazias, dois registros finais (`REG-001` e `REG-003`) e seis linhas `SUCESSO` em
`carga_historico`. Como este cenário não possui mídia, não se espera conteúdo em `get`.

O passo a passo completo está no
[runbook de implantação remota](https://github.com/InovaFiscaliza/Scarab/wiki/Podman-Compose-Servidor-Remoto).
