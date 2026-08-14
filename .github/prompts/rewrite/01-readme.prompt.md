---
description: "Módulo 01 da reescrita Scarab: README.md (Português do Brasil) descrevendo a nova arquitetura"
agent: rewrite-builder
---
Implemente o **Módulo 01 (README)** da reescrita do Scarab.

## Leitura obrigatória antes de codificar
- [PLAN.md](../../../docs/rewrite/PLAN.md) — completo (é a base de todo o conteúdo do README)
- [CONTRACTS.md](../../../docs/rewrite/CONTRACTS.md) — seções 1 a 3 (para descrever configuração,
  banco de dados e módulos com precisão)

## Entregáveis
- `README.md` (raiz do repositório — **substitua** o conteúdo atual, que descreve a arquitetura
  antiga)

## Requisitos específicos

Escreva em **Português do Brasil**, com as seções:
1. Visão geral (o que o sistema faz, 1-2 parágrafos).
2. Arquitetura (pode reaproveitar/adaptar o diagrama Mermaid de fluxo de dados de PLAN.md §3).
3. Estrutura do repositório (árvore de pastas, igual à de PLAN.md §3).
4. Pré-requisitos (Podman, UV, acesso a um PostgreSQL — via container).
5. Como rodar localmente (clonar, `uv sync`, configurar `config/config.json` a partir de
   `config/default_config.json`, `podman compose -f containers/podman-compose.yml up`).
6. Visão geral da configuração (resumo dos campos principais de `config/default_config.json`,
   sem repetir a tabela inteira de CONTRACTS.md — apenas os conceitos principais: repositórios,
   prazos, banco).
7. Como funciona o processamento (resumo do fluxo: JSON descritor + mídia → UUIDv5 → stored
   procedure → banco; tratamento de mídia órfã; rotina de lixeira).
8. Licença/contribuição (referencie os arquivos já existentes `LICENSE.md`, `CONTRIBUTING.md`,
   `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md` na raiz do repositório, sem duplicar
   conteúdo).

Não descreva funcionalidades que não estão nos contratos (ex.: não mencione múltiplas tabelas,
PK/FK ou formatos de exportação do Scarab antigo — este README documenta apenas a arquitetura
nova).

## Validação
- `get_errors` no arquivo (checagem de markdown válido).
- Releia e confirme que nenhum trecho ficou em inglês fora de nomes de arquivos/comandos/código.

## Ao terminar
Atualize `/memories/repo/rewrite-plan.md` marcando o Módulo 01 como concluído.
