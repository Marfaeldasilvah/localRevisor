# Pipeline de ML do localRevisor

Esta pasta reúne tudo o que foi feito para **treinar e avaliar** os modelos que estimam as notas por competência (C1 a C5) das redações do Enem: carga e preparo dos dados, baselines, IAs generativas, BERTimbau, comparação e teste final. O aplicativo (pasta `src/`) fica separado e só usa o modelo treinado.

## Scripts

| Etapa | Arquivo | O que faz |
|---|---|---|
| Dados | `preparar_dados.py` | Lê o corpus Essay-BR e gera `dados/train.csv`, `valid.csv` e `test.csv` |
| Baselines | `baseline_atributos.py`, `atributos.py` | B0 (sempre a nota mais comum) e B1 (atributos manuais + regressão Ridge) |
| IAs generativas | `llm_zero_shot.py` | Corrige redações com qualquer IA compatível com a API da OpenAI (nuvem ou Ollama) |
| BERTimbau | `treinar_bert.py` | Treina o modelo final e o salva para o aplicativo |
| BERTimbau | `experimentos_bert.py` | Experimentos de temas novos e de sementes |
| Comparação | `comparar.py` | Compara os modelos na validação, com intervalos de confiança |
| Teste final | `avaliar_teste.py` | Avalia o teste. **Use uma única vez** |
| Apoio | `metricas.py`, `avaliacao.py`, `bert_treino.py`, `divisao.py` | Métricas, tabela de avaliação, treino e divisão por temas |

Rode todos os comandos **de dentro da pasta `ml/`**.

## Como reproduzir

1. **Ambiente** (Python 3.13 ou superior):

   ```
   pip install -r requirements-ml.txt
   ```

   Para treinar o BERT, instale também `pip install -r ../requirements-bert.txt` e use uma GPU (no Google Colab, o treino leva cerca de 6 minutos). Sem GPU o treino é muito lento.

2. **Corpus** (não vem junto com este projeto):

   ```
   git clone https://github.com/lplnufpi/essay-br corpus
   python preparar_dados.py --corpus corpus --saida dados
   ```

   O Essay-BR usa a licença MIT. O corpus só traz o **código numérico do tema** (0 a 85), sem o texto da proposta. Os textos das redações não devem ser publicados com este projeto.

3. **Baselines:**

   ```
   python baseline_atributos.py
   ```

4. **BERTimbau:**

   ```
   python treinar_bert.py --saida ../modelos/bertimbau_enem --teste dados/test.csv
   python experimentos_bert.py temas-novos
   python experimentos_bert.py sementes
   ```

   O `--teste` só grava as previsões do teste, sem avaliá-las.

5. **IAs generativas** (exemplo com o Ollama, no PowerShell):

   ```
   $env:LLM_MODEL="qwen3:8b"
   $env:ANCORAS="1"
   $env:N_REDACOES="200"
   python llm_zero_shot.py
   ```

   Para um serviço em nuvem, defina também `LLM_BASE_URL` e `LLM_API_KEY`. As IAs recebem só a redação (sem o tema). As respostas ficam em `resultados/*.jsonl` e **não devem ser publicadas**, porque trazem trechos das redações.

6. **Comparação e teste final:**

   ```
   python comparar.py
   python avaliar_teste.py
   ```

   O `avaliar_teste.py` usa o `resultados/bert_test_previsoes.csv`. Ele deve ser executado **uma única vez**, com o modelo já escolhido, para o resultado do teste não ser contaminado por decisões tomadas olhando para ele.

## Resultados guardados em `resultados/`

| Arquivo | Conteúdo |
|---|---|
| `bert_valid_previsoes.csv`, `bert_test_previsoes.csv` | Notas previstas pelo modelo final (só ids e notas) |
| `comparacao_teste.csv` | Resultado final no teste: B0, B1 e BERTimbau, com intervalos de confiança |
| `temas_novos_resultado.csv` | QWK em temas vistos e em temas novos (3 repetições) |
| `sementes_resultado.csv` | QWK com 3 sementes de treino |

Os demais arquivos (`comparacao_validacao_*.csv` e os `.jsonl` das IAs) são gerados pelos scripts e não são versionados.

## O que não vai para o Git

Acrescente ao `.gitignore` da raiz do projeto:

```
modelos/
ml/corpus/
ml/dados/
ml/resultados/*.jsonl
ml/resultados/comparacao_validacao_*.csv
```
