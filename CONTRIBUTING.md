# Como contribuir

O `localRevisor` é um projeto local-first, single-user e em evolução. Contribuições
são bem-vindas, especialmente correções de bugs, testes e melhorias de acessibilidade.

## Antes de abrir um PR

1. Rode a suíte:

   ```bash
   python -m unittest discover -s tests -t . -v
   ```

2. Rode o lint (opcional, mas recomendado):

   ```bash
   ruff check src tests verificar_bert_local.py
   ```

3. Descreva o problema, a solução e como testou. Se mexer em notas/prompts, inclua
   um exemplo de antes/depois e deixe claro que é uma estimativa.

## Escopo

- O app é para uso pessoal/local; autenticação multiusuário e deploy público não
  fazem parte do escopo atual.
- Não envie dados reais de alunos, `.env`, `data/` nem checkpoints grandes.
- Mudanças de schema precisam de migração idempotente em `src/db.py` e teste em
  `tests/test_migration.py`.

## Licença

Ao contribuir, você concorda que a contribuição é licenciada sob a MIT, como o
restante do projeto.
