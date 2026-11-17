# Task list

## Concluído nesta rodada (P0)

- [x] Resultado completo na revisão: nota, C1–C5, texto/transcrição, explicação, erros e metadados.
- [x] Persistência estruturada (`scores`, `source_text`, `score_mode`, modelo, provedor, prompt, duração, tokens) com migração idempotente.
- [x] Ciclo de vida do job: recuperação após reinício, `pending` global, retry protegido, limite de concorrência e WAL/busy_timeout.
- [x] Histórico paginado e filtrável por status.
- [x] Contrato de IA robusto: JSON mode com fallback, validação de faixa, reparo único, temperature 0, timeout, defesa de prompt e aviso de citação não encontrada.
- [x] BERT fail-closed: exige 5 saídas/id2label coerente, não cai silenciosamente no modo só-IA e tem script de verificação sem pandas.
- [x] Configuração/chave: sem hash no banco, `.env` atômico 600, remover chave, aviso de Docker, primeira execução bloqueada até configurar.
- [x] Segurança local: CSRF, limite de upload, validação por magic bytes, UTF-8, permissões 700 no diretório de dados, headers e loopback no compose.
- [x] Documentação e governança: README, deck alinhado, `LICENSE` MIT, `.env.example`, `CONTRIBUTING`, `SECURITY` e CI.
- [x] Testes: parsing, banco/migração, upload, CSRF, worker, BERT, chave, rotas e headers (65 testes).

## Próximo (P1)

- [ ] App factory (`create_app`) e injeção de configuração para testes multi-instância.
- [ ] Observabilidade local: logs estruturados, tempo/tokens/custo por correção e endpoint de saúde.
- [ ] Registro de capacidades por modelo (texto, visão, JSON, contexto) e remoção da heurística `deepseek`/`VISION_MODEL`.
- [ ] PDF escaneado: renderizar páginas em imagem ou usar input de arquivo do provedor, com limite de páginas.
- [ ] Golden set anonimizado para regressão de nota/prompt.
- [ ] Testes de integração com um provedor falso HTTP (não só mock de classe).

## Fora do escopo atual

- Multiusuário/login/deploy público.
- Modo professor/calibração/anotações.
- Exportação/backup como feature (o backup é manual e documentado).
- Outros exames/idiomas/LMS.
- Reescrita de UI/SPA/dark mode.
- Treino/re-treino do BERT.
- Analytics/telemetria/pagamentos.
- Endurecimento de produção do Docker/Nix (seguem experimentais).
