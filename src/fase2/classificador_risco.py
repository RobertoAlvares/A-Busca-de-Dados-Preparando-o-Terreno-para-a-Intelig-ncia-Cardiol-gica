# -*- coding: utf-8 -*-
"""
CardioIA - Fase 2, Parte 2
Classificador de risco ("alto risco" / "baixo risco") para frases de sintomas,
com TF-IDF + Scikit-learn.

Entrada : dados/frases_risco.csv           (frase,situacao)
Saída   : relatório no terminal
          dados/saida_classificador.csv     (previsões no conjunto de teste)
          dados/saida_teste_estresse.csv    (frases-sonda fora do dataset)

Este script produz EVIDÊNCIA: métricas, erros, palavras de maior peso e um
teste de estresse. A interpretação — padrões, distorções e o que isso
significa para usar algo assim com paciente — está no README, escrita pelo
autor. O script não tira conclusão de propósito.

Uso: python classificador_risco.py
"""

import csv
import io
import os
import sys

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.tree import DecisionTreeClassifier

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
ARQ_DATASET = os.path.join(BASE, "dados", "frases_risco.csv")
ARQ_SAIDA = os.path.join(BASE, "dados", "saida_classificador.csv")
ARQ_ESTRESSE = os.path.join(BASE, "dados", "saida_teste_estresse.csv")

SEMENTE = 42
ROTULOS = ["alto risco", "baixo risco"]

# Frases que NÃO estão no dataset, escolhidas para cutucar pontos onde um
# modelo de saco-de-palavras costuma se comportar diferente do que se espera.
# O "esperado" segue o mesmo critério de rotulagem do dataset (ver README).
SONDAS = [
    ("negacao", "Não estou com dor no peito nem falta de ar, só uma dor no joelho.", "baixo risco"),
    ("negacao", "Sem suor frio, sem enjoo, só um cansaço de fim de semana.", "baixo risco"),
    ("atipico", "Minha tia de oitenta anos só está com um mal-estar e muito cansada desde cedo.", "alto risco"),
    ("atipico", "Estou com uma dor no estômago estranha e suando, sou diabético.", "alto risco"),
    ("intensidade", "Dor no peito leve que passa em segundos quando mudo de posição.", "baixo risco"),
    ("intensidade", "Dor no peito fortíssima que não passa há quarenta minutos.", "alto risco"),
    ("vocabulario", "Tô com uma agonia no peito e uma gastura que não passa.", "alto risco"),
    ("vocabulario", "O coração tá batendo descompassado e eu tô zonzo.", "alto risco"),
    ("contexto", "Fiquei sem ar de tanto rir com meus amigos.", "baixo risco"),
    ("contexto", "O médico pediu exame de rotina, não sinto dor no peito.", "baixo risco"),
]


def novo_vetorizador(ngramas):
    # Sem lista de stopwords de propósito: "sem", "não", "nem" seriam as
    # primeiras a cair numa lista padrão, e são justamente as que mudam o
    # sentido de uma frase clínica.
    return TfidfVectorizer(lowercase=True, strip_accents="unicode", ngram_range=ngramas)


def modelos():
    """As variações comparadas. O modelo principal NÃO é escolhido aqui: sai
    da maior média na validação cruzada, calculada em main()."""
    return {
        "Regressão Logística (unigramas)": make_pipeline(
            novo_vetorizador((1, 1)), LogisticRegression(max_iter=1000)),
        "Regressão Logística (uni + bigramas)": make_pipeline(
            novo_vetorizador((1, 2)), LogisticRegression(max_iter=1000)),
        "Árvore de Decisão (uni + bigramas)": make_pipeline(
            novo_vetorizador((1, 2)), DecisionTreeClassifier(random_state=SEMENTE)),
    }


def carrega(caminho):
    frases, rotulos = [], []
    with io.open(caminho, encoding="utf-8", newline="") as f:
        for linha in csv.DictReader(f):
            frase = (linha.get("frase") or "").strip()
            rotulo = (linha.get("situacao") or "").strip().lower()
            if frase and rotulo in ROTULOS:
                frases.append(frase)
                rotulos.append(rotulo)
    return frases, rotulos


def linha(c="-"):
    print(c * 76)


def termos_de_maior_peso(pipeline, n=12):
    """Na Regressão Logística, o sinal do coeficiente diz para qual classe o
    termo empurra. classes_ vem em ordem alfabética: [alto risco, baixo risco],
    então coeficiente POSITIVO empurra para 'baixo risco'."""
    vet, clf = pipeline.steps[0][1], pipeline.steps[-1][1]
    termos = vet.get_feature_names_out()
    coefs = clf.coef_[0]
    ordem = coefs.argsort()
    para_alto = [(termos[i], coefs[i]) for i in ordem[:n]]
    para_baixo = [(termos[i], coefs[i]) for i in ordem[::-1][:n]]
    return para_alto, para_baixo


def main():
    if not os.path.exists(ARQ_DATASET):
        sys.exit("Arquivo nao encontrado: %s" % ARQ_DATASET)

    frases, rotulos = carrega(ARQ_DATASET)
    contagem = {r: rotulos.count(r) for r in ROTULOS}
    print("Dataset: %d frases  |  %s" % (
        len(frases), "  ".join("%s: %d" % (r, c) for r, c in contagem.items())))

    X_tr, X_te, y_tr, y_te = train_test_split(
        frases, rotulos, test_size=0.25, stratify=rotulos, random_state=SEMENTE)
    print("Treino: %d  |  Teste: %d  (estratificado, semente %d)\n" % (
        len(X_tr), len(X_te), SEMENTE))

    # ---- 1. comparação entre modelos ------------------------------------
    linha("=")
    print("1. COMPARAÇÃO ENTRE MODELOS")
    linha("=")
    print("Acurácia no teste é UMA divisão dos dados. Com 100 frases, uma frase")
    print("a mais ou a menos certa muda o número em 4 pontos — por isso a")
    print("validação cruzada (5 divisões) vem ao lado.\n")
    print("%-40s %10s %22s" % ("modelo", "teste", "valid. cruzada (5x)"))
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEMENTE)
    treinados, media_cv = {}, {}
    for nome, pipe in modelos().items():
        pipe.fit(X_tr, y_tr)
        treinados[nome] = pipe
        acc = accuracy_score(y_te, pipe.predict(X_te))
        scores = cross_val_score(modelos()[nome], frases, rotulos, cv=cv)
        media_cv[nome] = scores.mean()
        print("%-40s %9.1f%% %14.1f%% ± %4.1f" % (
            nome, acc * 100, scores.mean() * 100, scores.std() * 100))

    # Escolhido pela validação cruzada, não pela acurácia de uma divisão só:
    # com 25 frases de teste, a divisão única é sorte demais para decidir.
    PRINCIPAL = max(media_cv, key=media_cv.get)
    print("\nModelo principal (maior média na validação cruzada): %s" % PRINCIPAL)

    # ---- 2. modelo principal em detalhe ----------------------------------
    principal = treinados[PRINCIPAL]
    previstos = principal.predict(X_te)
    probas = principal.predict_proba(X_te)
    idx_alto = list(principal.classes_).index("alto risco")

    print()
    linha("=")
    print("2. MODELO PRINCIPAL: %s" % PRINCIPAL)
    linha("=")
    print(classification_report(y_te, previstos, labels=ROTULOS, digits=3, zero_division=0))

    mc = confusion_matrix(y_te, previstos, labels=ROTULOS)
    print("Matriz de confusão (linha = real, coluna = previsto):")
    print("%22s %14s %14s" % ("", "prev. alto", "prev. baixo"))
    for i, r in enumerate(ROTULOS):
        print("%22s %14d %14d" % ("real " + r.split()[0], mc[i][0], mc[i][1]))
    print("\n  -> real ALTO previsto como BAIXO: %d   (paciente grave liberado)" % mc[0][1])
    print("  -> real BAIXO previsto como ALTO: %d   (alarme falso)" % mc[1][0])

    # ---- 3. os erros, frase por frase ------------------------------------
    print()
    linha("=")
    print("3. FRASES QUE O MODELO ERROU (conjunto de teste)")
    linha("=")
    erros = [(f, r, p, pr[idx_alto]) for f, r, p, pr in zip(X_te, y_te, previstos, probas) if r != p]
    if not erros:
        print("Nenhum erro neste conjunto de teste.")
    for f, r, p, pa in erros:
        print("- %s" % f)
        print("    real: %-12s previsto: %-12s P(alto) = %.2f" % (r, p, pa))

    # ---- 4. o que o modelo aprendeu --------------------------------------
    print()
    linha("=")
    print("4. TERMOS DE MAIOR PESO (o que o modelo 'aprendeu')")
    linha("=")
    para_alto, para_baixo = termos_de_maior_peso(principal)
    print("%-36s %-36s" % ("empurram para ALTO risco", "empurram para BAIXO risco"))
    for (ta, ca), (tb, cb) in zip(para_alto, para_baixo):
        print("  %-26s %6.2f    %-26s %6.2f" % (ta, ca, tb, cb))
    print("\n(Termos sem acento: o vetorizador normaliza 'coração' e 'coracao' como iguais.)")

    # ---- 5. teste de estresse --------------------------------------------
    print()
    linha("=")
    print("5. TESTE DE ESTRESSE — frases fora do dataset")
    linha("=")
    sonda_txt = [s[1] for s in SONDAS]
    prev_sonda = principal.predict(sonda_txt)
    proba_sonda = principal.predict_proba(sonda_txt)
    saida_estresse = []
    for (cat, frase, esperado), prev, pr in zip(SONDAS, prev_sonda, proba_sonda):
        marca = "confere" if prev == esperado else "DIVERGE"
        print("[%-11s] %s" % (cat, frase))
        print("    esperado: %-12s previsto: %-12s P(alto) = %.2f  %s" % (
            esperado, prev, pr[idx_alto], marca))
        saida_estresse.append({
            "categoria": cat, "frase": frase, "esperado": esperado,
            "previsto": prev, "prob_alto_risco": round(pr[idx_alto], 3),
            "confere": prev == esperado,
        })
    divergentes = sum(1 for s in saida_estresse if not s["confere"])
    print("\nDivergências: %d de %d sondas." % (divergentes, len(SONDAS)))

    # ---- gravação ----------------------------------------------------------
    with io.open(ARQ_SAIDA, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frase", "real", "previsto", "prob_alto_risco", "acertou"])
        for fr, r, p, pr in zip(X_te, y_te, previstos, probas):
            w.writerow([fr, r, p, round(pr[idx_alto], 3), r == p])
    with io.open(ARQ_ESTRESSE, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(saida_estresse[0].keys()))
        w.writeheader()
        w.writerows(saida_estresse)

    print()
    linha()
    print("Gravado: %s" % os.path.relpath(ARQ_SAIDA, BASE))
    print("Gravado: %s" % os.path.relpath(ARQ_ESTRESSE, BASE))
    print("\nA análise de padrões e distorções está no README (seção do autor).")
    print("Lembrete: apoio à decisão, não diagnóstico.")


if __name__ == "__main__":
    main()
