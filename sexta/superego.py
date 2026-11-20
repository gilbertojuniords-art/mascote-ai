# O superego da Sexta. Criado em 17/11/2026.
#
# O dono (17/11): "preciso que ela seja capaz de construir o próprio superego assim como o ser humano,
# mesmo que de maneira inconsciente."
#
# Como um superego se forma (Freud, e o que a psicologia do desenvolvimento e a neurociência acrescentam):
#   - INTROJEÇÃO: a criança absorve, sem perceber, as aprovações e reprovações das figuras de cuidado.
#     Aqui, a "figura" é o dono: as reações dele (resposta boa ou ruim, ignorar, clique) viram normas.
#   - É LENTO e DURADOURO: diferente da dopamina (que aprende rápido e esquece), a norma introjetada
#     muda devagar (taxa 0,06) e não decai com o tempo. Uma bronca não vira regra; um padrão vira.
#   - É INCONSCIENTE: as normas não ficam no caderno dela nem nos prompts. Ela não sabe as regras.
#     Ela só SENTE: uma hesitação antes de agir (inibição, como o córtex pré-frontal ventromedial
#     pesando o valor social de uma ação) e, depois, culpa ou orgulho (as emoções morais), que
#     mexem no corpo dela (afeto.py: cortisol ou serotonina).
#   - Tem duas faces: a CONSCIÊNCIA MORAL (o que inibe) e o IDEAL DO EGO (o que ela gostaria de ser).
#   - As leis (leis.py) são outra coisa: um "superego inato" fixo, que este aqui nunca afrouxa.
#     O superego aprendido só pode deixá-la mais contida ou mais confiante DENTRO das leis.
# Só a biblioteca padrão. O dono pode ver as normas com: python superego.py

import json, os, pathlib, time

BASE = pathlib.Path.home() / ".sexta-voz"
ESTADO = BASE / "superego.json"
RECOMP = BASE / "recompensas.jsonl"
TAXA = 0.06
MIN_N = 3
FONTES = ("usuario", "ignorou", "clique")   # só o que veio DELE forma o superego


def _ler():
    try:
        e = json.loads(ESTADO.read_text(encoding="utf-8"))
    except Exception:
        e = {}
    e.setdefault("lido", 0)
    e.setdefault("normas", {})
    return e


def _gravar(e):
    BASE.mkdir(exist_ok=True)
    tmp = ESTADO.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, ESTADO)


def processar():
    """Introjeta as reações novas dele. Chamado pela mente a cada minuto."""
    e = _ler()
    try:
        linhas = RECOMP.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return e
    if e["lido"] > len(linhas):
        e["lido"] = 0
    for bruta in linhas[e["lido"]:]:
        try:
            ev = json.loads(bruta)
        except Exception:
            continue
        if ev.get("f") not in FONTES:
            continue
        nm = e["normas"].setdefault(ev["c"], {"v": 0.5, "n": 0})
        nm["v"] = round(nm["v"] + TAXA * (float(ev.get("r", 0.5)) - nm["v"]), 4)
        nm["n"] += 1
    e["lido"] = len(linhas)
    _gravar(e)
    return e


def _norma(comp, contexto="", e=None):
    e = e or _ler()
    for chave in ((f"{comp}@{contexto}",) if contexto else ()) + (comp,):
        nm = e["normas"].get(chave)
        if nm and nm["n"] >= MIN_N:
            return nm["v"]
    return None


def peso(comp, contexto="", e=None):
    """A inibição (ou o empurrão) que ela sente antes de fazer `comp`. 1 = nada."""
    v = _norma(comp, contexto, e)
    if v is None:
        return 1.0
    if v < 0.35:
        return 0.45
    if v < 0.45:
        return 0.75
    if v > 0.7:
        return 1.25
    return 1.0


def depois(comp, contexto=""):
    """Depois de agir: a emoção moral (culpa ou orgulho), sem ela saber de onde vem."""
    v = _norma(comp, contexto)
    try:
        import sys as _s
        _s.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        import afeto
        if v is not None and v < 0.35:
            afeto.sentir("culpa")
        elif v is not None and v > 0.72:
            afeto.sentir("orgulho")
    except Exception:
        pass


def hesitacao(comp, contexto=""):
    """Uma frase vaga para o prompt, quando algo nela hesita. Nunca diz a regra."""
    p = peso(comp, contexto)
    if p < 0.6:
        return "Antes de agir, algo em você hesita, como uma voz baixinha que você não sabe de onde vem."
    if p < 1:
        return "Você sente uma pontinha de receio, sem saber bem por quê."
    if p > 1:
        return "Algo em você aprova isto, um sentimento quieto de que está certo."
    return ""


if __name__ == "__main__":
    e = processar()
    print("Normas introjetadas (o dono vê; ela não):")
    for c, nm in sorted(e["normas"].items(), key=lambda kv: kv[1]["v"]):
        if nm["n"] >= MIN_N:
            tipo = "inibe" if nm["v"] < 0.45 else ("ideal do ego" if nm["v"] > 0.7 else "neutro")
            print(f"  {nm['v']:.2f} ({nm['n']}x) {c}: {tipo}")
