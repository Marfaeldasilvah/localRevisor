# Segurança

## Modelo de ameaça

O `localRevisor` foi desenhado para **uso pessoal, em `localhost`**. Ele não tem
login, contas ou isolamento entre usuários. Não o exponha na internet nem em uma
rede compartilhada sem colocar autenticação e HTTPS na frente.

## O que já existe

- CSRF em todos os POSTs.
- Limite de upload (`LOCALREVISOR_MAX_UPLOAD_BYTES`, 20 MB por padrão).
- Validação do conteúdo do arquivo por magic bytes, não só pela extensão.
- `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` e CSP.
- Chave da API fora do banco, em `.env` com permissão 600 ou variável de ambiente.
- Docker publicando apenas em `127.0.0.1`.

## O que não existe

- Autenticação/autorização.
- Criptografia em repouso do banco/uploads.
- Proteção contra um usuário local mal-intencionado com acesso ao disco.
- Sanitização de conteúdo gerado por IA além do escape automático do Jinja.

## Reportar

Abra uma issue privada ou fale com o mantenedor. Não inclua chaves, redações de
alunos ou dados pessoais no relato.
