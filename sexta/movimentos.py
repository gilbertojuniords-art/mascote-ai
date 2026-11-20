# Os movimentos da Sexta: o corpo que ela mesma aprende a mexer. Criado em 16/11/2026.
#
# O usuário: "Ela tem que aprender a se mexer também, do jeito que ela quiser [...] ela teria que
# ser capaz de alterar o próprio código e fazer o upload, pelo menos o código de movimentos [...]
# As outras partes, que seriam referentes ao código bruto, ela não deveria fazer."
#
# Decisão de segurança: um movimento é DADO, não programa. É uma lista de poses com tempo, no
# mesmo formato dos gestos da mascote: (braço esquerdo, braço direito, cabeça, subida). Ela pode
# inventar quantos quiser, do jeito que quiser, mas nunca escreve algo que o computador execute.
# Quem toca o movimento é a mascote (código fixo), e tudo passa por validar() antes:
#   - só os campos conhecidos, números dentro dos limites do desenho (nada de braço atravessando o corpo);
#   - de 1 a 10 poses, cada uma de 0,12 a 2 s, no total até 8 s, repetindo no máximo 3 vezes.
#
# O arquivo movimentos.json mora no repositório (sexta/movimentos.json). À noite, a mente
# (pensar.py) cria ou ajusta um movimento, valida, faz commit SÓ desse arquivo, sobe para o GitHub,
# baixa a versão nova e instala no cofre. A mascote recarrega sozinha quando o arquivo muda.

import json, pathlib, re

AQUI = pathlib.Path(__file__).resolve().parent
ARQ = AQUI / "movimentos.json"

LIMITES = {             # (mínimo, máximo) de cada parte do corpo, em graus ou pixels do desenho
    "esq": (0.0, 135.0),     # braço esquerdo: 25 = repouso, 90 = aberto, 128 = para cima
    "dir": (-135.0, 0.0),    # braço direito (espelhado): -25 = repouso, -90 = aberto, -128 = para cima
    "cab": (-15.0, 15.0),    # cabeça inclinada (negativo = para um lado, positivo = para o outro)
    "sobe": (-14.0, 6.0),    # corpo: negativo = pula/sobe, positivo = agacha
}
DUR = (0.12, 2.0)
MAX_POSES, MAX_TOTAL_S, MAX_REPETIR = 10, 8.0, 3
RE_NOME = re.compile(r"^[a-z][a-z0-9_]{2,23}$")


def vocabulario():
    """Texto para a IA: o que dá para mexer e os limites."""
    return ("Cada pose tem: dur (segundos, 0.12 a 2), esq (braço esquerdo, 0 a 135; 25 = repouso, 90 = aberto, "
            "128 = para cima), dir (braço direito espelhado, -135 a 0; -25 = repouso, -90 = aberto, -128 = para cima), "
            "cab (cabeça, -15 a 15; inclina para um lado ou outro), sobe (corpo, -14 a 6; negativo = pula, positivo = "
            "agacha). Entre uma pose e outra o corpo vai suavemente. Até 10 poses, no total até 8 s, repetir de 1 a 3.")


def validar(nome, mov):
    """Devolve (ok, movimento limpo ou motivo). Corta o que passar dos limites; recusa o que não fizer sentido."""
    nome = (nome or "").strip().lower()
    if not RE_NOME.match(nome):
        return False, "nome inválido (minúsculas, números e _; 3 a 24 letras)"
    if not isinstance(mov, dict):
        return False, "não é um movimento"
    poses = mov.get("poses")
    if not isinstance(poses, list) or not 1 <= len(poses) <= MAX_POSES:
        return False, f"precisa de 1 a {MAX_POSES} poses"
    limpas, total = [], 0.0
    for p in poses:
        if not isinstance(p, dict):
            return False, "pose inválida"
        limpa = {"dur": round(min(DUR[1], max(DUR[0], float(p.get("dur", 0.4)))), 2)}
        for campo, (lo, hi) in LIMITES.items():
            v = p.get(campo)
            if v is not None:
                limpa[campo] = round(min(hi, max(lo, float(v))), 1)
        total += limpa["dur"]
        limpas.append(limpa)
    repetir = int(min(MAX_REPETIR, max(1, int(mov.get("repetir", 1)))))
    if total * repetir > MAX_TOTAL_S:
        return False, f"longo demais ({total * repetir:.1f} s; o máximo é {MAX_TOTAL_S:.0f} s)"
    desc = re.sub(r"[\r\n\[\]{}]", " ", str(mov.get("descricao", "")))[:140].strip()
    return True, {"descricao": desc, "poses": limpas, "repetir": repetir,
                  "criado": str(mov.get("criado", ""))[:10], "por": "sexta" if mov.get("por") == "sexta" else "base"}


def carregar(arq=None):
    """{nome: movimento} já validado. O que estiver inválido no arquivo é ignorado."""
    try:
        dados = json.loads(pathlib.Path(arq or ARQ).read_text(encoding="utf-8"))
    except Exception:
        return {}
    saida = {}
    for nome, mov in (dados.get("movimentos") or {}).items():
        ok, limpo = validar(nome, mov)
        if ok:
            saida[nome] = limpo
    return saida


def gravar(movs, arq=None):
    dados = {"_leia": "Movimentos da Sexta. 'base' = vieram com ela; 'sexta' = ela criou. Ver movimentos.py.",
             "movimentos": {n: movs[n] for n in sorted(movs)}}
    pathlib.Path(arq or ARQ).write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def lista_para_ia(movs=None):
    movs = carregar() if movs is None else movs
    return "; ".join(f"{n} ({m['descricao']})" for n, m in movs.items()) or "nenhum ainda"


def pose_em(mov, t):
    """A pose-alvo do movimento no instante t (s desde o começo), ou None se acabou."""
    ciclo = sum(p["dur"] for p in mov["poses"])
    if t >= ciclo * mov["repetir"]:
        return None
    t %= ciclo
    for p in mov["poses"]:
        if t < p["dur"]:
            return p
        t -= p["dur"]
    return mov["poses"][-1]
