# CardioIA — Batimentos de Dados: Mapeando o Coração Moderno

**FIAP · Inteligência Artificial · 2º Ano · Turma 2TIAOR · 2026/2**
**Aluno:** Roberto Almeida Alvares (RM568265) · **Grupo:** 19

Primeira fase do projeto **CardioIA**, uma plataforma digital que simula um
ecossistema de cardiologia inteligente, integrando dados clínicos, Machine
Learning, Visão Computacional, IoT e agentes de IA para triagem,
diagnóstico, monitoramento e previsão médica.

Nesta fase, o papel assumido é o de **cientista de dados hospitalar**:
levantar, organizar e entender os dados que vão alimentar os módulos
inteligentes das próximas fases do projeto — sempre com atenção à
governança dos dados envolvidos.

---

## 1. Construção da base de dados de pacientes

A base numérica reúne informações clínicas reais de pacientes cardíacos:
idade, sexo, pressão arterial em repouso, colesterol sérico, glicemia de
jejum, resultado de eletrocardiograma em repouso, frequência cardíaca
máxima atingida, presença de angina induzida por exercício, entre outras
variáveis, totalizando **14 campos clínicos por paciente**.

**Origem dos dados:** são dados reais, não simulados. Vêm da *Cleveland
Clinic Foundation* e do *V.A. Medical Center* (Long Beach), coletados por
Robert Detrano, M.D., e disponibilizados publicamente pelo UCI Machine
Learning Repository. Escolhi dado real em vez de simulado por um motivo
prático: as próximas fases do projeto (diagnóstico automatizado,
previsão de eventos cardíacos) vão precisar de relação clínica de
verdade entre as variáveis, e não faria sentido trocar a base depois.

**Processo de preparação:** o arquivo original (303 pacientes) veio sem
cabeçalho e com 6 valores clínicos faltantes, marcados como `?`. Essas
linhas foram descartadas por princípio de qualidade de dado — melhor não
ter a informação do que preencher um valor clínico arbitrário. Em
seguida, foi aplicado um critério de seleção determinístico: percorrer o
dataset e manter a primeira ocorrência de cada combinação de valor em
todas as variáveis categóricas (sexo, tipo de dor no peito, resultado de
ECG, presença de angina, inclinação do segmento ST, número de vasos
afetados, tipo de talassemia e severidade do diagnóstico), garantindo que
**nenhuma variação clínica relevante ficasse de fora** mesmo com uma base
mais enxuta. O resultado final tem **120 pacientes**, com as 5
severidades de diagnóstico (de ausência de doença a grau 4) todas
representadas — evitando viés por classe ausente.

**Dicionário de variáveis** — as mais relevantes clinicamente, e por quê
importam para um projeto de IA em cardiologia:

| Variável | Nome | Domínio | Relevância clínica |
|---|---|---|---|
| `age` | idade | anos | fator de risco não modificável para doença cardiovascular |
| `sex` | sexo | 1=masc, 0=fem | apresentação clínica difere entre sexos |
| `cp` | tipo de dor no peito | 1-4 | triagem de risco de isquemia miocárdica |
| `trestbps` | pressão arterial em repouso | mmHg | hipertensão crônica gera sobrecarga cardíaca — um dos fatores de risco mais associados a mortalidade cardiovascular |
| `chol` | colesterol sérico | mg/dl | marcador de formação de placa nas coronárias — outro fator de risco central |
| `fbs` | glicemia de jejum >120 | 1=sim, 0=não | indica diabetes, comorbidade de alto risco |
| `restecg` | ECG em repouso | 0-2 | detecta alteração elétrica de sobrecarga |
| `thalach` | freq. cardíaca máxima | bpm | central pro monitoramento contínuo via wearable nas próximas fases |
| `exang` | angina induzida por esforço | 1=sim, 0=não | indicador direto de insuficiência de fluxo coronário |
| `oldpeak` | depressão do segmento ST | mm | forte marcador de isquemia |
| `slope` | inclinação do ST no pico | 1-3 | risco isquêmico associado à morfologia |
| `ca` | nº de vasos afetados | 0-3 | obstrução coronária visualizada por fluoroscopia |
| `thal` | talassemia | 3, 6, 7 | diferencia tecido infartado de tecido isquêmico viável |
| `num` | severidade do diagnóstico | 0-4 | **variável-alvo** — sem ela não há como treinar nenhum classificador de risco nas próximas fases |

**Arquivo:** [`heart_disease_cardioia_final.csv`](./heart_disease_cardioia_final.csv)
(120 linhas, 14 colunas, sem valores faltantes). Dataset de origem
completo, para referência: [`heart_disease_cleveland.csv`](./heart_disease_cleveland.csv)
(303 linhas).

---

## 2. Coleta de dados de fontes públicas

Além dos dados numéricos, a base foi complementada com conteúdo textual e
visual de fontes públicas e verificáveis — nenhum dado foi gerado
artificialmente.

### Textos (`docs/`)

Dois textos sobre saúde cardiovascular, de naturezas complementares:

- **`harvey_1628_motion_of_heart.txt`** — obra clássica de William
  Harvey (1628), que descreveu pela primeira vez a circulação sanguínea.
  Texto histórico-fundacional da cardiologia, disponível integralmente
  via Projeto Gutenberg (domínio público).
- **`scielo_fatores_risco_cardiovascular_2019.txt`** — síntese de artigo
  científico sobre fatores de risco cardiovascular em países de língua
  portuguesa (dados do estudo Global Burden of Disease 2019), publicado
  em periódico científico brasileiro de acesso aberto.

**Aplicação em NLP:** esses textos são material de entrada natural para
tarefas de Processamento de Linguagem Natural nas próximas fases do
projeto — extração de sintomas e fatores de risco mencionados em texto
livre, classificação de tópicos (ex: prevenção x tratamento x
epidemiologia) e, no caso do texto científico, análise de relações entre
fatores de risco e desfechos, que pode alimentar o assistente virtual
cardiológico previsto para fases futuras. Nenhum dos dois textos contém
dado pessoal de paciente identificável — são conteúdo científico e
histórico já publicado.

### Imagens (link externo, ver seção 4)

100 imagens reais de laudos de eletrocardiograma (ECG) de 12 derivações,
de pacientes com infarto do miocárdio, no formato usado em ambiente
hospitalar (traçados I, II, III, aVR, aVL, aVF, V1-V6 + tira de ritmo).

**Aplicação em Visão Computacional:** esse tipo de imagem é o material
de entrada típico para detecção de padrões (identificação automática de
elevação ou depressão do segmento ST), reconhecimento de anomalias de
ritmo e, futuramente, classificação automática de gravidade — tarefas
centrais da fase de diagnóstico por Visão Computacional do CardioIA.

---

## 3. Governança de dados e IA

Dado de saúde é dado pessoal sensível pela LGPD (Lei 13.709/2018). Os
dados usados aqui já vêm de fontes públicas tratadas pelos autores
originais — sem nome, sem identificador de paciente. Mesmo assim, tratei
a base pensando em proteção de dado sensível por dois motivos: primeiro,
porque é a prática certa mesmo com dado já anonimizado; segundo, porque
as próximas fases do projeto vão envolver coleta de dado real de
paciente (wearable, assistente virtual), e aí esse cuidado deixa de ser
opcional.

**Pontos aplicados nesta fase:**

- **Base legal considerada** para o cenário de uso futuro do projeto:
  tratamento de dado de saúde exclusivamente por profissionais e serviços
  de saúde, para fins de tutela da saúde — a hipótese legal mais aderente
  a uma plataforma de apoio a diagnóstico cardiológico.
- **Anonimização tem limite:** dado anonimizado sai do escopo principal
  da lei, mas isso não é definitivo. Se der pra reverter com esforço
  razoável — por exemplo, cruzando uma combinação rara de variáveis
  clínicas com outra fonte — volta a ser dado pessoal. Por isso reduzi o
  dataset numérico para o menor volume necessário: menos dado circulando
  é menos risco, mesmo sendo um dataset de pesquisa pública.
- **Qualidade do dado como princípio de governança**, não só de boa
  prática técnica: os registros com valor clínico faltante foram
  descartados em vez de preenchidos artificialmente, porque dado
  impreciso em contexto de saúde tem potencial de dano direto se um
  modelo futuro aprender em cima dele.
- **Próximo passo de governança**, a considerar já a partir da Fase 2:
  qualquer coleta de dado real de paciente deve vir acompanhada de um
  relatório de avaliação de impacto à proteção de dados antes da
  implementação — não depois.

---

## 4. Links públicos

Todos os arquivos preparados nesta fase (incluindo o volume completo de
imagens, não versionado neste repositório por tamanho) estão disponíveis
publicamente para consulta e correção:

**Google Drive (pasta completa — dataset, textos e 100 imagens de ECG):**
https://drive.google.com/drive/folders/16hSIALtvht82R25h1ht2KRYX3H7_Gubf?usp=sharing

Fonte das imagens de ECG: *ECG Images dataset of Cardiac Patients*, Ali
Haider Khan & Muzammil Hussain, Ch. Pervaiz Elahi Institute of Cardiology
Multan / University of Management and Technology Lahore, Mendeley Data,
DOI 10.17632/gwbz3fsgp8.2, licença CC BY 4.0.

---

## Estrutura do repositório

```
.
├── README.md
├── heart_disease_cardioia_final.csv   # base final (120 pacientes, 14 variáveis)
├── heart_disease_cleveland.csv        # dataset de origem completo (303 pacientes)
└── docs/
    ├── harvey_1628_motion_of_heart.txt
    └── scielo_fatores_risco_cardiovascular_2019.txt
```

As 100 imagens de ECG não estão versionadas neste repositório (volume
grande de arquivos binários) — estão disponíveis no link do Google Drive
acima, como orienta o enunciado da atividade.
