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
├── get/               # saída de mídias associadas
├── store/             # área legada, não usada pelo pipeline atual
├── temp/              # área temporária reservada
└── trash/             # arquivos rejeitados e mídias órfãs
```

O `config.json` usa caminhos relativos à raiz do repositório. O diretório `temp` fica disponível
para operações temporárias, mas o contrato atual do pipeline não possui `temp_path` nem uma etapa
que o utilize explicitamente.

## Execução com Podman

A partir da raiz do repositorio:

```powershell
Copy-Item examples/sandbox/config.json config/config.json
podman compose -f containers/podman-compose.yml up --build
```

O compose monta `examples/sandbox` no mesmo caminho dentro do container. Como os nomes possuem
prefixo numérico, os descritores são listados na ordem da sequência e processados pelo daemon.

Para consultar o resultado, use o PostgreSQL do serviço `db` e verifique `clientes_docs` e
`carga_historico`. Ao final, remova os arquivos de entrada processados e o override local se
quiser retornar a configuração padrão:

```powershell
Remove-Item examples/sandbox/post/*.json
Remove-Item config/config.json
```
