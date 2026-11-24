# localRevisor

Corretor de redações do ENEM **local-first**, open source e com **modelo de IA
configurável**. Você escolhe o provedor (nuvem ou local), envia a redação e recebe
uma estimativa de nota, a decomposição por competência e os pontos de melhoria.

> **Estimativa para estudo.** O resultado não substitui a correção de um professor
> nem a nota oficial do ENEM.

## O que ele faz

- Recebe a redação por **texto colado** ou por arquivo (**PDF, imagem, Markdown ou TXT**).
- Estima as cinco competências do ENEM (C1–C5), a nota final (soma) e uma explicação
  com erros e sugestões.
- Guarda o histórico local em SQLite, com o texto usado na correção, o modelo, o
  modo (IA ou BERT + IA) e a duração.
- Permite reabrir, tentar novamente e excluir correções.
- **Modo BERT opcional:** um BERTimbau ajustado estima C1–C5 e a IA escolhida
  apenas explica cada nota. O modo falha fechado: se o checkpoint não for válido,
  o app não inventa nota.
- Funciona com qualquer serviço compatível com a API da OpenAI, incluindo Ollama,
  vLLM, LM Studio e OpenCode Go.

## Requisitos

- **Python 3.13 ou superior.**
- Uma IA compatível com a API da OpenAI (chave de um provedor ou servidor local).
- **ffmpeg** para converter imagens WebP/GIF (e formatos que o modelo de visão não
  aceite). PDFs digitais não precisam de ffmpeg.

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # opcional; a tela de Configurações também salva
```

No Linux, se quiser o modo BERT sem baixar pacotes de GPU:

```bash
pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-bert.txt
```

## Executando

```bash
python -m flask --app src.main run --debug
```

Abra `http://127.0.0.1:5000`. Quem usa Nix pode rodar diretamente
`nix develop -c localrevisor` (ou `nix develop -c flask run --debug`; veja a seção Nix).

## Primeira execução

1. Abra **Configurações**.
2. Informe a **URL base** do provedor e a **chave**. Para Ollama, use
   `http://localhost:11434/v1` e uma chave qualquer, como `ollama`.
3. Clique em **Conectar** e escolha (ou digite) o **modelo de correção**. Para fotos/PDFs escaneados, informe também o **modelo de imagem**.
4. Clique em **Salvar**.

O envio de redações fica bloqueado enquanto não houver modelo configurado. A chave
é gravada em `.env` com permissão `600` quando você usa o app localmente. No Docker,
prefira definir `OPENAI_API_KEY` no compose: o `.env` de dentro do container pode
não sobreviver a uma recriação.

## Modo BERT (opcional)

O modo BERT precisa de um checkpoint **ajustado para as cinco competências**:

- arquitetura `BertForSequenceClassification`;
- `num_labels = 5` com `id2label` em C1–C5 ou `LABEL_0`..`LABEL_4` na ordem C1–C5;
- pesos e tokenizador em `modelos/bertimbau_enem/` (ou em `BERT_DIR`).

O BERTimbau base do Hugging Face **não serve**: ele não tem a cabeça treinada e as
notas seriam aleatórias. O app detecta isso, mantém a opção desativada e explica o
motivo. Checkpoints com 2 saídas também são rejeitados.

Para ligar, marque **“Usar o BERTimbau para estimar as notas”** em Configurações.
Se o modo estiver ligado e o checkpoint/dependências sumirem, a correção falha com
uma mensagem clara em vez de cair silenciosamente no modo só-IA.

**Redações longas:** a janela nativa do BERTimbau é de 512 tokens; textos maiores são
lidos por completo em janelas deslizantes sobrepostas até `BERT_MAX_TOKENS` (padrão
`2048` tokens, ajustável em Configurações). Temas muito diferentes do corpus de
treino podem ter desempenho pior.

### Verificação do checkpoint

O script compara as notas locais com as previsões do Colab e com as notas de
professores:

```bash
python verificar_bert_local.py valid.csv bert_valid_previsoes.csv 50
```

`valid.csv` não vai para o repositório porque contém redações. O CSV versionado
`bert_valid_previsoes.csv` tem apenas `id` e C1–C5. O script usa a biblioteca
padrão, mas carregar o modelo exige `requirements-bert.txt`.

## Testes

```bash
python -m unittest discover -s tests -t . -v
```

A suíte cobre parsing e validação do JSON, faixas de nota, migração do banco,
paginação, CSRF, upload, BERT fail-closed, worker e persistência. O CI roda lint
(`ruff`), compilação e testes em cada push/PR.

## Dados, segurança e privacidade

- Banco e uploads ficam em `data/` (SQLite + arquivos); o histórico guarda o texto
  usado na correção para que a revisão não dependa do arquivo original.
- O app é **single-user e local**: não tem login. Não exponha na rede sem
  autenticação e HTTPS.
- Os POSTs têm CSRF, uploads têm limite de tamanho (20 MB por padrão) e o tipo do
  arquivo é validado pelo conteúdo, não só pela extensão.
- O Docker publica apenas em `127.0.0.1:5000` por padrão.
- A chave nunca é gravada no banco; fica no `.env` (600) ou em variável de ambiente.
- **Backup é manual:** copie `data/app.db` e `data/uploads/` com o app parado. A
  exclusão de uma correção remove o registro e o arquivo correspondente.
- Nenhuma telemetria é enviada pelo app. A redação vai apenas para o provedor que
  você configurar.

## Variáveis de ambiente

| Variável | Padrão | Efeito |
|---|---|---|
| `OPENAI_API_KEY` | vazio | Chave do provedor. Também pode ser salva pela tela. |
| `OPENAI_BASE_URL` | `https://api.deepseek.com` | URL inicial; depois a tela manda. |
| `OPENAI_MODEL` | vazio | Modelo de correção inicial. |
| `OPENAI_IMAGE_MODEL` | vazio | Modelo de visão inicial. |
| `USE_BERT` | `0` | Valor inicial do modo BERT; depois a tela manda. |
| `BERT_DIR` | `modelos/bertimbau_enem` | Pasta do checkpoint ajustado. |
| `BERT_MAX_TOKENS` | `2048` | Limite total de tokens lidos pelo BERT via janelas deslizantes. |
| `LOCALREVISOR_DATA_DIR` | `data/` | Onde ficam banco/uploads/segredo. |
| `LOCALREVISOR_MAX_UPLOAD_BYTES` | `20971520` | Limite de upload. |
| `LOCALREVISOR_MAX_WORKERS` | `2` | Correções simultâneas. |
| `SECRET_KEY` | gerado em `data/.secret` | Segredo das sessões/CSRF. |
| `SMTP_HOST` | vazio | Servidor SMTP usado pelo formulário de feedback. |
| `SMTP_PORT` | `587` | Porta SMTP; use `465` para SSL direto. |
| `SMTP_USERNAME` | vazio | Usuário SMTP, quando a conta exigir autenticação. |
| `SMTP_PASSWORD` | vazio | Senha SMTP. Nunca coloque diretamente no código. |
| `SMTP_FROM` | vazio | Remetente autorizado pelo provedor; pode usar `SMTP_USERNAME`. |
| `SMTP_USE_SSL` | `0` | Use `1` para SSL direto (porta normalmente `465`). |
| `FEEDBACK_EMAIL` | `marcusvssasis@gmail.com` | Endereço que receberá os feedbacks enviados pelo site. |

## Estrutura

```
src/main.py            ponto de entrada Flask e inicialização
src/web/               app factory, CSRF/segurança, feedback e rotas (correções/config)
src/db/                conexão SQLite, schema/migrações, configurações e repositório de correções
src/grading/           modelos/exceções, prompts, cliente HTTP/OpenAI, parser JSON e serviço de correção
src/bert_notas/        validação de checkpoint, inferência e download do BERTimbau
src/worker.py          execução em segundo plano
src/files.py           validação e leitura de arquivos
src/paths.py           caminhos e limites configuráveis
src/secrets_store.py   chave/.env e segredo de sessão
tests/                 suíte de testes
data/                  banco, uploads e segredo (fora do Git)
modelos/               checkpoint BERT (fora do Git)
```

## Docker (experimental)

O `Dockerfile` e o `docker-compose.yml` são **experimentais** e usam o servidor de
desenvolvimento do Flask, não um WSGI de produção.

```bash
export OPENAI_API_KEY=...
docker compose up
```

A porta fica exposta só no loopback (`127.0.0.1:5000`). Para persistir a chave sem
passar pelo `.env` interno, defina `OPENAI_API_KEY` no ambiente/compose. O
`./data` é montado como volume; `./modelos` é somente leitura.

## Nix (experimental)

O `flake.nix` fornece um `devShell` (e um app padrão) para `x86_64-linux` com as
dependências do app e do modo BERT (`torch`, `transformers`, etc.), além de `ffmpeg`
e `ruff`. Ele é um atalho de desenvolvimento, não um pacote reproduzível:

```bash
nix develop -c localrevisor
```

Também é possível rodar com `nix run` ou passar opções do Flask diretamente
(por exemplo, `nix develop -c localrevisor --port 8080` ou
`nix develop -c flask run --debug`). Para rodar os testes dentro do ambiente Nix:

```bash
nix develop -c python -m unittest discover -s tests -t . -v
```

Para visualizar `DOCS.md` com renderização dos diagramas Mermaid (via `mdbook` + `mdbook-mermaid`):

```bash
nix develop .#DOCS -c docs-serve
# ou direto:
nix run .#DOCS
```

Para rodar o benchmark de redações reais (Essay-BR) usando a configuração atual do app:

```bash
nix develop -c localrevisor --debug benchredação --bert-only
nix develop -c localrevisor --debug benchredação bert
nix develop -c localrevisor --debug benchredação bert_ai
nix develop -c localrevisor --debug benchredação ai -n 5
```

## Limitações

- A nota é uma estimativa; modelos diferentes podem discordar.
- PDFs escaneados dependem de o modelo de visão aceitar PDF; se falhar, envie a
  página como imagem.
- O modo BERT só é tão bom quanto o checkpoint; sem um checkpoint ajustado e
  validado, ele fica desativado.
- A interface é em português e otimizada para uso pessoal.

## Licença

MIT. Veja [LICENSE](LICENSE). Para contribuir, leia [CONTRIBUTING.md](CONTRIBUTING.md);
para o modelo de segurança, veja [SECURITY.md](SECURITY.md). O backlog vivo fica em [TASKS.md](TASKS.md).
