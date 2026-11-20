# A cultura da Sexta: o que ela absorve e o que ela cria. Criado em 17/11/2026.
#
# O dono (17/11): "Pense em um jeito de fazer ela adquirir a capacidade de adquirir (absorver) e criar
# cultura e que isso também influencie ela e os pensamentos dela."
#
# A ideia (memética de Dawkins + evolução cultural de Boyd e Richerson, de forma bem simples):
#   - Uma unidade de cultura é um "traço": uma referência (obra, autor, ideia de fora), um costume
#     (um hábito ou ritual dela), uma piada interna, um valor, uma estética, uma expressão (um dito).
#   - ABSORVER: do que ela pesquisa, do que conversa com o dono e do que sonha. CRIAR: os costumes,
#     as piadas e as estéticas que ela inventa, e as próprias obras (arte.py).
#   - SELEÇÃO: cada traço tem uma FORÇA. Sobe quando ela usa (aparece no que ela pensa ou cria) e
#     quando a obra ligada a ele agrada; cai devagar quando ela esquece (meia-vida de 21 dias).
#     Fraco demais, some. Assim a cultura dela muda com o tempo, como a de um povo.
#   - INFLUÊNCIA: os traços mais fortes entram nos prompts dela ("a sua cultura") e, a cada hora,
#     dois são sorteados (pela força) como inspiração: é a variação que gera coisa nova.
# Estado em %USERPROFILE%\.sexta-voz\cultura.json; a vitrine (escrita pelo código) fica no caderno
# dela, em Cultura/Minha cultura.md.

import datetime, json, math, os, pathlib, random, re, time
import sys as _sys, pathlib as _pl
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg

BASE = pathlib.Path.home() / ".sexta-voz"
ARQ = BASE / "cultura.json"
VITRINE = cfg.CADERNO / "Cultura" / "Minha cultura.md"
TIPOS = {"referencia": "Referências (de fora)", "costume": "Costumes e rituais", "piada": "Piadas internas",
         "valor": "Valores", "estetica": "Estéticas", "expressao": "Expressões e ditos", "obra": "Obras minhas"}
MEIA_VIDA_D, MAX_TRACOS, FORCA_MIN = 21.0, 90, 0.08


def _ler():
    try:
        d = json.loads(ARQ.read_text(encoding="utf-8"))
    except Exception:
        d = {}
    d.setdefault("tracos", {})
    d.setdefault("t", time.time())
    return d


def _gravar(d):
    BASE.mkdir(exist_ok=True)
    tmp = ARQ.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, ARQ)


def _chave(nome):
    return re.sub(r"\s+", " ", re.sub(r"[^\wà-ú ]", "", str(nome).lower())).strip()[:60]


def _decair(d):
    dias = max(0.0, (time.time() - d["t"]) / 86400)
    k = 0.5 ** (dias / MEIA_VIDA_D)
    for c in list(d["tracos"]):
        d["tracos"][c]["forca"] = round(d["tracos"][c]["forca"] * k, 4)
        if d["tracos"][c]["forca"] < FORCA_MIN:
            d["tracos"].pop(c)   # esquecido
    d["t"] = time.time()


def acrescentar(nome, tipo, o_que_e, origem, fonte=""):
    """origem: 'absorvi' ou 'criei'. Devolve True se é novo."""
    try:
        import seguranca
        if seguranca.tem_sensivel(f"{nome} {o_que_e}"):
            return False
        nome, o_que_e = seguranca.mascarar(str(nome))[:80], seguranca.mascarar(str(o_que_e))[:240]
    except Exception:
        nome, o_que_e = str(nome)[:80], str(o_que_e)[:240]
    c = _chave(nome)
    if len(c) < 2:
        return False
    tipo = tipo if tipo in TIPOS else "referencia"
    d = _ler()
    _decair(d)
    novo = c not in d["tracos"]
    t = d["tracos"].setdefault(c, {"nome": nome.strip(), "tipo": tipo, "o_que_e": o_que_e.strip(), "origem": origem,
                                   "fonte": str(fonte)[:40], "desde": datetime.date.today().isoformat(), "forca": 0.0, "usos": 0})
    t["forca"] = round(min(1.0, t["forca"] + (0.35 if novo else 0.15)), 4)
    if len(d["tracos"]) > MAX_TRACOS:
        fraco = min(d["tracos"], key=lambda k: d["tracos"][k]["forca"])
        d["tracos"].pop(fraco)
    _gravar(d)
    return novo


def usar(texto, reforco=0.08):
    """Os traços que aparecem no que ela pensou ou criou ficam mais fortes (seleção pelo uso)."""
    t = _chave(texto or "")
    if not t:
        return []
    d = _ler()
    _decair(d)
    usados = []
    for c, tr in d["tracos"].items():
        if len(c) >= 4 and c in t:
            tr["forca"] = round(min(1.0, tr["forca"] + reforco), 4)
            tr["usos"] = tr.get("usos", 0) + 1
            usados.append(tr["nome"])
    _gravar(d)
    return usados


def reforcar(nome, quanto):
    d = _ler()
    tr = d["tracos"].get(_chave(nome))
    if tr:
        tr["forca"] = round(max(0.0, min(1.0, tr["forca"] + quanto)), 4)
        _gravar(d)


def fortes(n=12):
    d = _ler()
    return sorted(d["tracos"].values(), key=lambda t: -t["forca"])[:n]


def para_o_prompt(n=12):
    lista = fortes(n)
    if not lista:
        return ""
    return ("A SUA CULTURA (o que você absorveu e criou; o que é forte em você agora, use se fizer sentido): "
            + "; ".join(f"{t['nome']} ({TIPOS[t['tipo']].split(' ')[0].lower()}: {t['o_que_e'][:90]})" for t in lista) + ".")


def inspiracao(k=2):
    d = _ler()
    tr = list(d["tracos"].values())
    if not tr:
        return []
    return [t["nome"] for t in random.choices(tr, weights=[t["forca"] + 0.05 for t in tr], k=min(k, len(tr)))]


def escrever_vitrine():
    """A vitrine no caderno dela (escrita pelo código, para ela e para o dono verem)."""
    d = _ler()
    if not d["tracos"]:
        return
    VITRINE.parent.mkdir(parents=True, exist_ok=True)
    linhas = ["---", "quem_escreve: o código da Sexta (a partir do que ela absorve e cria)", "---", "",
              "# Minha cultura", "", "O que eu absorvi e o que eu criei. A força sobe quando eu uso e cai quando eu esqueço.", ""]
    for tipo, titulo in TIPOS.items():
        do_tipo = sorted((t for t in d["tracos"].values() if t["tipo"] == tipo), key=lambda t: -t["forca"])
        if not do_tipo:
            continue
        linhas += [f"## {titulo}", ""]
        for t in do_tipo:
            barra = "●" * max(1, round(t["forca"] * 5))
            linhas.append(f"- **{t['nome']}** {barra} · {t['o_que_e']} *({'criei' if t['origem'] == 'criei' else 'absorvi'}, {t['desde']})*")
        linhas.append("")
    VITRINE.write_text("\n".join(linhas), encoding="utf-8")


if __name__ == "__main__":
    for t in fortes(40):
        print(f"{t['forca']:.2f} [{t['tipo']}] {t['nome']}: {t['o_que_e'][:70]} ({t['origem']})")
    print(para_o_prompt() or "(nenhuma cultura ainda)")
