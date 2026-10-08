# FIAP - Faculdade de Informática e Administração Paulista

<p align="center">
<a href= "https://www.fiap.com.br/"><img src="assets/logo-fiap.png" alt="FIAP - Faculdade de Informática e Admnistração Paulista" border="0" width=40% height=40%></a>
</p>

<br>

# CardioIA — plataforma de cardiologia inteligente

## Grupo 19 (Fase 1) · Grupo 44 (Fase 2) — integrante único

## 👨‍🎓 Integrantes:
- Roberto Almeida Alvares — RM568265

## 👩‍🏫 Professores:
### Tutor(a)
- <a href="https://www.linkedin.com/in/leonardoorabona/">Leonardo Ruiz Orabona</a>
### Coordenador(a)
- <a href="https://www.linkedin.com/in/andre-godoi-chiovato-83730228/">André Godoi Chiovato</a>

## 🎥 Vídeos de demonstração

| Fase | Vídeo (YouTube, não listado) |
|---|---|
| Fase 2 — Diagnóstico Automatizado | [youtu.be/rlHPc3Kz-tI](https://youtu.be/rlHPc3Kz-tI) |

## 📜 Descrição

O **CardioIA** simula um ecossistema de cardiologia inteligente: dados clínicos,
Machine Learning, Visão Computacional, IoT e agentes de IA para triagem,
diagnóstico, monitoramento e previsão. Cada fase do curso constrói uma parte, e
todas vivem neste repositório.

### Fase 1 — A Busca de Dados

Papel de **cientista de dados hospitalar**: levantar e organizar as bases que
alimentam as fases seguintes. Base numérica com **120 pacientes e 14 variáveis
clínicas**, sem valor faltante, a partir de dados reais da *Cleveland Clinic
Foundation* (UCI Heart Disease); dois textos para NLP; e 100 laudos de ECG
(*Khan & Hussain, Mendeley Data*, DOI 10.17632/gwbz3fsgp8.2, CC BY 4.0), que
ficam fora do git por volume. O relatório completo, com o critério de amostragem
e o enquadramento de governança, está em
[`document/fase1_relatorio.md`](document/fase1_relatorio.md). O estado exato do
repositório na entrega está preservado na tag
[`fase1-entrega`](https://github.com/RobertoAlvares/A-Busca-de-Dados-Preparando-o-Terreno-para-a-Intelig-ncia-Cardiol-gica/tree/fase1-entrega).

### Fase 2 — Diagnóstico Automatizado: IA no Estetoscópio Digital

Nesta fase o sistema começa a **ler linguagem natural** — relatos de pacientes
escritos como as pessoas realmente falam.

**Parte 1 — extração de sintomas por mapa de conhecimento.** Dez relatos
simulados; um mapa `sintoma → doença` em CSV liga expressões coloquiais ("aperto
no peito", "o sapato aperta", "falha uma batida") a sete hipóteses: Infarto,
Angina, Insuficiência Cardíaca, Arritmia, Crise Hipertensiva e duas causas não
cardíacas (musculoesquelética e ansiedade). O extrator conta **expressões
distintas**, não ocorrências, e tem duas regras que mudam o resultado:

- **Negação é tratada.** "sem falta de ar" não conta como sintoma presente —
  fica registrado como *negado* e é ignorado.
- **Empate não vira diagnóstico.** Duas hipóteses com a mesma contagem geram
  `EM ABERTO`, com as concorrentes listadas.

Resultado: 10 de 10 relatos com hipótese sugerida.

**Parte 2 — classificador de risco por TF-IDF.** Dataset de **100 frases**
rotuladas em "alto risco" / "baixo risco", balanceado (50/50), vetorizado com
TF-IDF e classificado com Scikit-learn. Três modelos comparados; o principal é
escolhido pela **maior média na validação cruzada**, e não pela acurácia de uma
única divisão, porque com 25 frases de teste uma divisão só é sorte demais.

| Modelo | Acurácia no teste | Validação cruzada (5×) |
|---|---|---|
| **Regressão Logística (unigramas)** — principal | 72,0% | 81,0% ± 11,6 |
| Regressão Logística (uni + bigramas) | 72,0% | 76,0% ± 12,8 |
| Árvore de Decisão (uni + bigramas) | 60,0% | 56,0% ± 3,7 |

Matriz de confusão do modelo principal no teste (25 frases):

| | previsto alto | previsto baixo |
|---|---|---|
| **real alto** | 12 | 1 |
| **real baixo** | 6 | 6 |

Além das métricas, o script imprime as frases que o modelo errou, os termos de
maior peso em cada direção e um **teste de estresse** com 10 frases fora do
dataset (negação, apresentação atípica, intensidade, vocabulário coloquial e
contexto) — 2 das 10 divergem do esperado. Tudo é gravado em
`src/fase2/dados/saida_classificador.csv` e `saida_teste_estresse.csv`.

**Critério de rotulagem do dataset.** As frases são **simuladas** e os rótulos
seguem a lógica de sinais de alarme usada em triagem: dor torácica em repouso ou
prolongada, irradiação para braço/mandíbula/costas, síncope, falta de ar em
repouso ou ao deitar, sinais neurológicos com pressão muito alta → alto risco;
sintoma leve, localizado, com causa aparente e autolimitado → baixo risco.
**Os rótulos não foram validados por profissional de saúde.** Servem a um
exercício acadêmico, não a uso clínico.

### 🧭 Análise de padrões e distorções

**O modelo aprendeu o estilo de quem escreveu as frases, não só os sintomas.**
Os termos que mais empurram para baixo risco são "quando" e "depois" — nenhum
dos dois é sintoma. No dataset, "quando" aparece em 19 frases de baixo risco e
em 3 de alto; "depois", em 15 contra 3, porque as frases leves explicam a causa
("depois da academia"). O efeito aparece no pior erro do modelo: o único
paciente grave liberado foi *"Fiquei sem ar de repente **depois** de uma viagem
longa de avião e a panturrilha está inchada"*.

**"Não" virou sinal de gravidade.** O termo aparece em 10 frases de alto risco
("não passa", "não melhora") e em 4 de baixo, e o modelo aprendeu a ler "não"
como alarme. Por isso erra "A pressão está controlada com o remédio e não
sinto nada diferente" e as duas frases do teste de estresse com "não … dor no peito". O
TF-IDF trata a frase como um conjunto de palavras sem ordem: não percebe que o
"não" nega o sintoma. A Parte 1 acerta esses casos porque trata a negação por
regra explícita.

**A acurácia esconde o tipo de erro.** As duas regressões logísticas acertam
72%, mas o modelo principal libera 1 paciente grave e dá 6 alarmes falsos,
enquanto o outro libera 3 graves. Numa triagem, o número que importa é o
recall de alto risco (0,923 no modelo principal), não a acurácia. Com só 100
frases rotuladas por uma pessoa e variação de ±11,6 pontos na validação
cruzada, esses resultados indicam padrões, não comprovam desempenho.

### O limite que este projeto assume

Os dois módulos são **apoio à decisão, não diagnóstico**, e os scripts dizem
isso ao usuário no fim de cada execução. Dado de saúde é **dado pessoal
sensível** (LGPD, Art. 5º, II); por isso todos os relatos e frases da Fase 2 são
simulados, e nenhum dado real de paciente entra no repositório público.

## 📁 Estrutura de pastas

Dentre os arquivos e pastas presentes na raiz do projeto, definem-se:

- <b>.github</b>: arquivos de configuração específicos do GitHub.

- <b>assets</b>: elementos não-estruturados deste repositório, como imagens.

- <b>config</b>: arquivos de configuração usados para definir parâmetros e ajustes do projeto.

- <b>document</b>: documentos do projeto.
  - `fase1_relatorio.md` — relatório completo da Fase 1.
  - `ai_project_document_fiap.md` — documento de projeto no modelo da FIAP.

- <b>scripts</b>: scripts auxiliares para tarefas específicas.

- <b>src</b>: todo o código-fonte e os dados do projeto, por fase.
  - `fase1/dados/` — base de pacientes (120) e base completa de referência (303).
  - `fase1/textos/` — textos para NLP (Harvey, 1628; SciELO, 2019).
  - `fase2/extrator_sintomas.py` — Parte 1: extração por mapa de conhecimento.
  - `fase2/classificador_risco.ipynb` — Parte 2 em notebook: TF-IDF, classificação e avaliação, com a saída executada.
  - `fase2/classificador_risco.py` — o mesmo classificador, para rodar no terminal.
  - `fase2/dados/` — relatos, mapa de conhecimento, dataset rotulado e saídas.

- <b>README.md</b>: arquivo que serve como guia e explicação geral sobre o projeto (o mesmo que você está lendo agora).

## 🔧 Como executar o código

**Pré-requisitos:** Python 3.8 ou superior.

```bash
git clone https://github.com/RobertoAlvares/A-Busca-de-Dados-Preparando-o-Terreno-para-a-Intelig-ncia-Cardiol-gica.git
cd A-Busca-de-Dados-Preparando-o-Terreno-para-a-Intelig-ncia-Cardiol-gica
pip install -r requirements.txt
```

**Fase 2, Parte 1** — só biblioteca padrão:

```bash
cd src/fase2
python extrator_sintomas.py
```

**Fase 2, Parte 2** — requer `scikit-learn` (instalado acima):

```bash
cd src/fase2
python classificador_risco.py
```

Os resultados são reprodutíveis: divisão de treino/teste, validação cruzada e
árvore de decisão usam semente fixa (42).

## 🗃 Histórico de lançamentos

* 0.2.0 - 05/10/2026
    * Fase 2 completa: extração de sintomas (Parte 1) e classificador de risco
      TF-IDF com três modelos, validação cruzada e teste de estresse (Parte 2).
    * Repositório reorganizado no template oficial da FIAP, um repositório para
      todas as fases.
* 0.1.0 - 02/09/2026
    * Fase 1 entregue: bases de pacientes, textos e imagens de ECG, com
      enquadramento de governança (tag `fase1-entrega`).

## 📋 Licença

<img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/cc.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/by.svg?ref=chooser-v1"><p xmlns:cc="http://creativecommons.org/ns#" xmlns:dct="http://purl.org/dc/terms/"><a property="dct:title" rel="cc:attributionURL" href="https://github.com/agodoi/template">MODELO GIT FIAP</a> por <a rel="cc:attributionURL dct:creator" property="cc:attributionName" href="https://fiap.com.br">Fiap</a> está licenciado sobre <a href="http://creativecommons.org/licenses/by/4.0/?ref=chooser-v1" target="_blank" rel="license noopener noreferrer" style="display:inline-block;">Attribution 4.0 International</a>.</p>
