# Teste funcional ponta a ponta

Este conjunto demonstra uma sequência de operações sobre três registros. Os arquivos de entrada
ficam em `post` e devem ser processados na ordem do prefixo numérico.

## Sequencia

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
├── post/              # entrada dos descritores JSON
├── get/               # área legada mantida no snapshot
├── store/             # área legada, não usada pelo pipeline atual
├── temp/              # área temporária reservada
└── trash/             # arquivos rejeitados e mídias órfãs
```

O `config.json` usa caminhos absolutos sob `/mnt/share01`, o destino Linux do bind mount no
container. O diretório `temp` fica disponível para operações temporárias, mas o contrato atual do
pipeline não possui `temp_path` nem uma etapa que o utilize explicitamente.

## Execução com Podman

A partir da raiz do repositório no host Linux:

```bash
sudo bash containers/scarab-deploy.sh install \
	--environment test \
	--instance scarab-test \
	--service-user "$(id -un)" \
	--source "$PWD"

scarab-deploy update --instance scarab-test
scarab-deploy test --instance scarab-test
```

O instalador copia a configuração para `/etc/scarab-test/config`, as fixtures para
`/srv/scarab-test/fixtures` e usa `/srv/scarab-test/share01` e `share02` como runtime. Dentro do
container, entrada e lixeira ficam em `/mnt/share01`; mídia fica em `/mnt/share02/media`.

O comando `test` recria o estado descartável, envia as fixtures e valida `clientes_docs` e
`carga_historico`. Os snapshots permanecem inalterados no checkout.

Em um host Linux remoto, use `scarab-deploy test --instance scarab-test`. O aceite em um banco novo
é entrada e lixeira vazias, dois registros finais (`REG-001` e `REG-003`) e seis linhas `SUCESSO`
em `carga_historico`.

O passo a passo completo está no
[runbook de implantação remota](https://github.com/InovaFiscaliza/Scarab/wiki/Podman-Compose-Servidor-Remoto).
