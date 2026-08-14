---
description: "Módulo 00 da reescrita Scarab: scaffold do repositório (pyproject.toml, .gitignore, esqueleto de pastas)"
agent: rewrite-builder
---
Implemente o **Módulo 00 (Scaffold)** da reescrita do Scarab.

## Leitura obrigatória antes de codificar
- [CONTRACTS.md](../../../docs/rewrite/CONTRACTS.md) — seção 5 (convenções)
- [PLAN.md](../../../docs/rewrite/PLAN.md) — seções 3 e 4 (árvore alvo, ordem dos módulos)
- `/memories/repo/rewrite-plan.md` — decisões já confirmadas (pydantic, pytest aprovado etc.)

## Entregáveis
- `pyproject.toml` (na raiz do repositório — **substitua** o conteúdo atual, pois a nova
  arquitetura é um projeto Python diferente do Scarab atual, embora mantenha o mesmo nome de
  pacote)
- `.gitignore` (na raiz)
- `src/__init__.py`

## Requisitos específicos

1. `pyproject.toml`:
   - `name = "scarab"`, `requires-python = ">=3.13"` (mesma versão do projeto atual).
   - Dependências obrigatórias: `psycopg[binary]>=3.2`, `psycopg-pool>=3.2`, `pydantic>=2`,
     `Office365-REST-Python-Client` (confirme o nome exato do pacote disponível ao rodar
     `uv add`; ajuste se necessário e relate no resumo final).
   - **Não** adicione `uuid` como dependência — é biblioteca padrão do Python.
   - Inclua um grupo de dependências de desenvolvimento (`[dependency-groups]` ou
     `[project.optional-dependencies]`) com `pytest` e `ruff` — a suíte de testes automatizados
     foi aprovada pelo usuário.
2. `.gitignore`: cobrir `config/config.json`, `.env`, `__pycache__/`, `*.pyc`, `.venv/`,
   artefatos de build. **Não** ignorar `uv.lock` (deve ser versionado).
3. `src/__init__.py`: mínimo, com uma docstring de uma linha em inglês descrevendo o pacote.
4. Não crie ou modifique nenhum outro arquivo. Não toque nos módulos legados em `src/`.

## Validação
- `get_errors` nos arquivos criados.
- Se possível, rode `uv sync` para validar que `pyproject.toml` é sintaticamente válido (pode
  falhar por falta de rede/índice — relate o resultado sem tentar contornar).

## Ao terminar
Atualize `/memories/repo/rewrite-plan.md` marcando o Módulo 00 como concluído e liste eventuais
suposições (ex.: versão exata do pacote SharePoint, decisão de testes aplicada).
