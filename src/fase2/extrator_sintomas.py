# -*- coding: utf-8 -*-
"""
CardioIA - Fase 2, Parte 1
Extração de sintomas em relatos de pacientes e sugestão de diagnóstico
com base num mapa de conhecimento (sintoma -> doença).

Entrada : dados/frases_sintomas.txt      (1 relato por linha)
          dados/mapa_conhecimento.csv    (Sintoma 1 | Sintoma 2 | Doença Associada)
Saída   : relatório no terminal + dados/saida_diagnosticos.csv

Isto é APOIO AO DIAGNÓSTICO, não diagnóstico. A sugestão é uma contagem de
expressões casadas, não um juízo clínico.

Uso: python extrator_sintomas.py
"""

import csv
import io
import os
import re
import sys
import unicodedata
from collections import defaultdict

# O console do Windows abre em cp1252 e engole os acentos na hora de imprimir:
# "Há dois dias" vira "H? dois dias". Os arquivos já são UTF-8 — quem quebra é
# só a saída do terminal, que é justamente o que aparece no vídeo da entrega.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
ARQ_FRASES = os.path.join(BASE, "dados", "frases_sintomas.txt")
ARQ_MAPA = os.path.join(BASE, "dados", "mapa_conhecimento.csv")
ARQ_SAIDA = os.path.join(BASE, "dados", "saida_diagnosticos.csv")

# "sem falta de ar", "não sinto enjoo" -> o sintoma foi NEGADO pelo paciente.
# A janela para em pontuação, para "não é bem dor, é um peso no estômago"
# não negar o "peso no estômago" que vem depois da vírgula.
NEGACAO = re.compile(r"\b(sem|nao|nem)\b[^.;,]{0,15}$")


def normaliza(texto):
    """minúsculas + sem acento, para casar 'coração' com 'coracao'."""
    texto = texto.lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def carrega_mapa(caminho):
    """Lê o CSV e devolve [(expressao_normalizada, expressao_original, doenca)]."""
    entradas = []
    with io.open(caminho, encoding="utf-8", newline="") as f:
        for linha in csv.DictReader(f):
            doenca = (linha.get("Doença Associada") or "").strip()
            if not doenca:
                continue
            for coluna in ("Sintoma 1", "Sintoma 2"):
                expr = (linha.get(coluna) or "").strip()
                if expr:
                    entradas.append((normaliza(expr), expr, doenca))
    return entradas


def analisa(frase, mapa):
    """Casa as expressões do mapa contra uma frase.

    Devolve (placar_por_doenca, sintomas_encontrados, sintomas_negados).
    O placar conta EXPRESSÕES DISTINTAS, não ocorrências: repetir a mesma
    palavra na frase não infla o diagnóstico.
    """
    frase_norm = normaliza(frase)
    achados = defaultdict(set)   # doença -> {expressões}
    encontrados, negados = set(), set()

    for expr_norm, expr_orig, doenca in mapa:
        pos = frase_norm.find(expr_norm)
        if pos == -1:
            continue
        # o paciente afirmou ou negou esse sintoma?
        if NEGACAO.search(frase_norm[max(0, pos - 25):pos]):
            negados.add(expr_orig)
            continue
        achados[doenca].add(expr_orig)
        encontrados.add(expr_orig)

    placar = {d: len(exprs) for d, exprs in achados.items()}
    return placar, sorted(encontrados), sorted(negados)


def decide(placar):
    """Devolve (diagnostico, pontos, empatados)."""
    if not placar:
        return "INDETERMINADO - nenhum sintoma do mapa foi reconhecido", 0, []
    topo = max(placar.values())
    empatados = sorted(d for d, p in placar.items() if p == topo)
    if len(empatados) > 1:
        return "EM ABERTO - empate entre " + " / ".join(empatados), topo, empatados
    return empatados[0], topo, []


def main():
    for caminho in (ARQ_FRASES, ARQ_MAPA):
        if not os.path.exists(caminho):
            sys.exit("Arquivo nao encontrado: %s" % caminho)

    mapa = carrega_mapa(ARQ_MAPA)
    doencas = sorted({d for _, _, d in mapa})
    with io.open(ARQ_FRASES, encoding="utf-8") as f:
        frases = [l.strip() for l in f if l.strip()]

    print("Mapa de conhecimento: %d expressoes, %d doencas" % (len(mapa), len(doencas)))
    print("Relatos lidos: %d\n" % len(frases))

    saida = []
    for i, frase in enumerate(frases, 1):
        placar, encontrados, negados = analisa(frase, mapa)
        diagnostico, pontos, _ = decide(placar)

        print("-" * 72)
        print("[%02d] %s" % (i, frase))
        print("     sintomas .....: %s" % (", ".join(encontrados) or "(nenhum)"))
        if negados:
            # o paciente disse que NAO tem - contar isso seria inventar sintoma
            print("     negados ......: %s  <- ignorados de proposito" % ", ".join(negados))
        print("     sugestao .....: %s  (%d expressoes)" % (diagnostico, pontos))
        if len(placar) > 1:
            outras = sorted(((p, d) for d, p in placar.items()), reverse=True)[1:]
            print("     concorrentes .: %s" % ", ".join("%s (%d)" % (d, p) for p, d in outras))

        saida.append({
            "id": i,
            "relato": frase,
            "sintomas_identificados": "; ".join(encontrados),
            "sintomas_negados": "; ".join(negados),
            "diagnostico_sugerido": diagnostico,
            "expressoes_casadas": pontos,
        })

    with io.open(ARQ_SAIDA, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(saida[0].keys()))
        w.writeheader()
        w.writerows(saida)

    print("-" * 72)
    sem_dx = sum(1 for r in saida if r["expressoes_casadas"] == 0)
    print("Resultado gravado em: %s" % os.path.relpath(ARQ_SAIDA, BASE))
    print("Relatos sem diagnostico sugerido: %d de %d" % (sem_dx, len(saida)))
    print("\nLembrete: apoio a decisao, nao diagnostico. Contagem de expressoes")
    print("nao e evidencia clinica - a conferencia e sempre humana.")


if __name__ == "__main__":
    main()
