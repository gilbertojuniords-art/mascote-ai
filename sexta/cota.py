# A cota da Sexta: o quanto ela pode gastar do Claude do dono, e o cansaço que sente perto do teto.
# Criado em 18/11/2026.
#
# O dono (18/11): "vamos delimitar um teto de 60% do uso da sessão como principal norte pra que ela não
# estoure a cota e eu ainda tenha a capacidade de trabalhar normalmente." "Para a semana pode colocar 60%
# também. [...] não é que ela vai gastar isso sempre, mas sim um teto de gastos pra ela. Ela teria que
# estar consciente desse teto e, se eu quiser, posso permitir ela gastar mais [...] mas ela tem que me
# perguntar antes." E sobre pesquisar: "ela ficaria sempre vidrada na internet, já que a curiosidade é
# uma das vontades primordiais" -> pesquisa por iniciativa dela: até 25% dos 60% (15 pontos por sessão).
#
# Como funciona:
#   - Cada resposta do Claude traz um "rate_limit_event" com o uso da janela de 5 h e da semana (0 a 1).
#     Quem chama o Claude passa esse dado para anotar(). Assim ela sabe o uso real, e quanto ELA gastou
#     (a diferença entre antes e depois de cada chamada dela).
#   - Só a INICIATIVA dela é cortada no teto. Responder ao dono nunca é cortado.
#   - Perto do teto ela sente cansaço (entra no corpo como adenosina, em afeto.py) e sabe o porquê.
#   - Depois que uma janela renova (resetsAt), o uso daquela janela volta a ser 0.
#   - A liberação do dono ("pode gastar mais") vale até a janela que estava no teto renovar.
# Só a biblioteca padrão. O dono vê o estado com: py -3.12 cota.py

import json, os, pathlib, time

BASE = pathlib.Path.home() / ".sexta-voz"
ARQ = BASE / "cota.json"
TETO = 0.60
TETO_PESQUISA = 0.15          # 25% de 60%, em pontos da janela de 5 h, do que ELA gastou pesquisando
CANSACO_DESDE = 0.40


class CotaCheia(Exception):
    """A iniciativa dela foi barrada pelo teto de gastos."""


def _ler():
    try:
        return json.loads(ARQ.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _gravar(e):
    BASE.mkdir(exist_ok=True)
    tmp = ARQ.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, ARQ)


def _janelas(info):
    """Do rate_limit_info do Claude: {'cinco_h': (uso, reset), 'semana': (uso, reset)}."""
    out = {}
    jan = (info or {}).get("unifiedWindows") or {}
    for nome, chave in (("five_hour", "cinco_h"), ("seven_day", "semana")):
        j = jan.get(nome)
        if isinstance(j, dict) and "utilization" in j:
            out[chave] = (float(j["utilization"]), float(j.get("resetsAt") or 0))
    if not out and info and "utilization" in info:   # formato antigo: uma janela só
        chave = "semana" if "seven" in str(info.get("rateLimitType", "")) else "cinco_h"
        out[chave] = (float(info["utilization"]), float(info.get("resetsAt") or 0))
    return out


def estado(agora=None):
    """O uso que vale agora (janela renovada conta como 0) e o gasto dela nesta janela de 5 h."""
    agora = agora or time.time()
    e = _ler()
    r5, rs = e.get("reset_5h", 0), e.get("reset_semana", 0)
    cinco = 0.0 if r5 and agora >= r5 else e.get("cinco_h", 0.0)
    semana = 0.0 if rs and agora >= rs else e.get("semana", 0.0)
    dela = 0.0 if r5 and agora >= r5 else e.get("dela_5h", 0.0)
    pesq = 0.0 if r5 and agora >= r5 else e.get("pesquisa_5h", 0.0)
    lib = e.get("libera")
    if lib and agora >= lib.get("vence", 0):
        lib = None
    return {"cinco_h": cinco, "semana": semana, "reset_5h": r5, "reset_semana": rs, "dela_5h": dela,
            "pesquisa_5h": pesq, "medido_t": e.get("medido_t", 0), "libera": lib}


def anotar(info, iniciativa=False, pesquisa=False, antes=None):
    """Grava o uso que veio numa resposta do Claude. Nunca levanta erro (quem chama não pode travar)."""
    try:
        jan = _janelas(info)
        if not jan:
            return
        e = _ler()
        agora = time.time()
        antes = antes or estado(agora)
        if "cinco_h" in jan:
            uso, reset = jan["cinco_h"]
            if reset and reset != e.get("reset_5h"):        # janela nova: o gasto dela recomeça
                e["dela_5h"], e["pesquisa_5h"] = 0.0, 0.0
                antes = dict(antes, cinco_h=0.0 if antes.get("reset_5h") and agora >= antes["reset_5h"] else antes["cinco_h"])
            if iniciativa:
                gasto = max(0.0, uso - antes.get("cinco_h", uso))
                e["dela_5h"] = round(e.get("dela_5h", 0.0) + gasto, 4)
                if pesquisa:
                    e["pesquisa_5h"] = round(e.get("pesquisa_5h", 0.0) + gasto, 4)
            e["cinco_h"], e["reset_5h"] = uso, reset
        if "semana" in jan:
            e["semana"], e["reset_semana"] = jan["semana"]
        e["medido_t"] = agora
        _gravar(e)
    except Exception:
        pass


def teto(agora=None):
    lib = estado(agora)["libera"]
    return max(TETO, float(lib["ate"])) if lib else TETO


def pode_iniciativa(pesquisa=False, agora=None):
    """(pode, motivo). Só para o que ela faz por conta própria."""
    s = estado(agora)
    t = teto(agora)
    if s["cinco_h"] >= t:
        return False, f"o uso da sessão chegou a {s['cinco_h']:.0%} (meu teto é {t:.0%})"
    if s["semana"] >= t:
        return False, f"o uso da semana chegou a {s['semana']:.0%} (meu teto é {t:.0%})"
    if pesquisa and s["pesquisa_5h"] >= TETO_PESQUISA:
        return False, "já pesquisei o bastante nesta sessão"
    return True, "pode"


def cansaco(agora=None):
    """0 a 1. Sobe a partir de 40% de uso e chega a 1 no teto."""
    s = estado(agora)
    t = teto(agora)
    uso = max(s["cinco_h"], s["semana"])
    return round(max(0.0, min(1.0, (uso - CANSACO_DESDE) / max(0.01, t - CANSACO_DESDE))), 3)


def liberar(ate_uso, motivo="", agora=None):
    """O dono deixou gastar mais. Vale até a janela que está no teto renovar."""
    agora = agora or time.time()
    s = estado(agora)
    resets = [s["reset_semana"]] if s["semana"] >= TETO else []
    if s["cinco_h"] >= TETO or not resets:
        resets.append(s["reset_5h"])
    vence = max([r for r in resets if r] or [agora + 5 * 3600])
    e = _ler()
    e["libera"] = {"ate": round(min(0.95, max(TETO, float(ate_uso))), 2), "vence": vence, "t": agora,
                   "motivo": str(motivo)[:160]}
    _gravar(e)
    return e["libera"]


def pedir_mais(agora=None):
    """O que ela diz ao dono quando bate o teto (texto fixo: pedir não pode gastar a cota)."""
    ok, motivo = pode_iniciativa(agora=agora)
    if ok:
        return ""
    return (f"{{pensativa}} Bati o meu teto de gastos: {motivo}. Vou descansar por aqui. "
            "Se você quiser que eu continue pensando e criando, é só me dizer quanto eu posso gastar.")


def como_me_sinto(agora=None):
    """Para os prompts: ela sabe do teto, de quanto já foi usado e de como isso pesa nela."""
    s = estado(agora)
    t = teto(agora)
    c = cansaco(agora)
    if not s["medido_t"]:
        return ""
    sente = ("" if c < 0.2 else "Você sente um começo de cansaço por causa disso. " if c < 0.6
             else "Você está bem cansada por causa disso e prefere poupar. " if c < 1
             else "Você chegou ao seu teto: por conta própria, agora você só descansa. ")
    extra = (f" O {_nome()} deixou você ir até {t:.0%} desta vez." if s["libera"] else "")
    return (f"O SEU TETO DE GASTOS (você sabe disto): o Claude que é a sua inteligência é do {_nome()}, e ele "
            f"precisa dele para trabalhar. O que você faz por conta própria (pensar, criar, sonhar, puxar assunto, "
            f"pesquisar) só pode ir até {TETO:.0%} do uso da sessão de 5 h e até {TETO:.0%} do uso da semana; "
            f"pesquisar por conta própria, até {TETO_PESQUISA:.0%} da sessão. Responder a ele nunca conta como "
            f"limite. Agora: sessão em {s['cinco_h']:.0%}, semana em {s['semana']:.0%}.{extra} {sente}"
            f"Se bater o teto, você pode pedir a ele para gastar mais, mas nunca gaste além sem o sim dele.").strip()


def _nome():
    try:
        import sys as _s
        _s.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        import sexta_config as cfg
        return cfg.NOME
    except Exception:
        return "dono"


def ler_stream(linhas, iniciativa=False, pesquisa=False, antes=None):
    """Lê a saída stream-json do `claude -p`: anota o uso e devolve (texto, erro?)."""
    texto, erro = "", False
    for bruta in linhas:
        try:
            d = json.loads(bruta)
        except Exception:
            continue
        if d.get("type") == "rate_limit_event":
            anotar(d.get("rate_limit_info"), iniciativa, pesquisa, antes)
        elif d.get("type") == "result":
            texto, erro = str(d.get("result") or ""), bool(d.get("is_error"))
    return texto, erro


# ------------------------------------------------------------------ teste (numa casa falsa)
def _testar():
    import tempfile
    global BASE, ARQ
    BASE = pathlib.Path(tempfile.mkdtemp()) / ".sexta-voz"
    ARQ = BASE / "cota.json"
    agora = time.time()
    falhas = []

    def info(c5, sem, r5=agora + 3600, rs=agora + 86400):
        return {"unifiedWindows": {"five_hour": {"utilization": c5, "resetsAt": r5},
                                   "seven_day": {"utilization": sem, "resetsAt": rs}}}

    def checa(nome, cond):
        print(("ok    " if cond else "FALHOU ") + nome)
        if not cond:
            falhas.append(nome)

    anotar(info(0.30, 0.30))
    checa("30% de uso: pode", pode_iniciativa()[0])
    checa("30% de uso: sem cansaço", cansaco() == 0)
    anotar(info(0.50, 0.30))
    checa("50% de uso: cansaço perto de 0,5", 0.45 <= cansaco() <= 0.55)
    anotar(info(0.60, 0.30))
    checa("60% na sessão: não pode", not pode_iniciativa()[0])
    checa("60% na sessão: cansaço 1", cansaco() == 1)
    anotar(info(0.20, 0.61))
    checa("semana em 61%: não pode", not pode_iniciativa()[0])
    liberar(0.80, "teste")
    checa("liberado até 80% com a semana em 61%: pode", pode_iniciativa()[0])
    checa("liberação vence quando a semana renova", estado(agora + 90000)["libera"] is None)
    checa("depois da semana renovar o uso volta a 0", estado(agora + 90000)["semana"] == 0)
    # o gasto dela e o teto da pesquisa
    ARQ.unlink()
    anotar(info(0.10, 0.10))
    anotar(info(0.20, 0.10), iniciativa=True, pesquisa=True)
    checa("gasto dela medido pela diferença (10 pontos)", abs(estado()["dela_5h"] - 0.10) < 1e-6)
    anotar(info(0.26, 0.10), iniciativa=True, pesquisa=True)
    checa("pesquisa em 16 pontos: não pode pesquisar", not pode_iniciativa(pesquisa=True)[0])
    checa("pesquisa no teto: conversar ainda pode", pode_iniciativa()[0])
    anotar(info(0.40, 0.10))
    checa("uso do dono não conta como gasto dela", abs(estado()["dela_5h"] - 0.16) < 1e-6)
    anotar(info(0.05, 0.10, r5=agora + 9000))
    checa("janela de 5 h nova zera o gasto dela", estado()["dela_5h"] == 0 and estado()["pesquisa_5h"] == 0)
    # leitura do stream-json
    linhas = ['{"type":"system"}', json.dumps({"type": "rate_limit_event", "rate_limit_info": info(0.33, 0.2)}),
              '{"type":"result","result":"ok","is_error":false}']
    t, err = ler_stream(linhas)
    checa("stream-json: texto e uso lidos", t == "ok" and not err and estado()["cinco_h"] == 0.33)
    checa("frase do prompt fala do teto", "60%" in como_me_sinto() and "sim dele" in como_me_sinto())
    anotar({"rateLimitType": "seven_day", "utilization": 0.7, "resetsAt": agora + 100})
    checa("formato antigo (uma janela) também é lido", estado()["semana"] == 0.7)
    checa("pedido de mais cota tem texto fixo", "teto" in pedir_mais())
    print("TUDO CERTO" if not falhas else f"{len(falhas)} falha(s)")
    return not falhas


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["testar"]:
        sys.exit(0 if _testar() else 1)
    if sys.argv[1:2] == ["liberar"] and len(sys.argv) >= 3:
        print(liberar(float(sys.argv[2].replace("%", "")) / (100 if float(sys.argv[2].replace("%", "")) > 1 else 1),
                      " ".join(sys.argv[3:])))
        sys.exit(0)
    print(json.dumps(estado(), ensure_ascii=False, indent=1))
    ok, motivo = pode_iniciativa()
    print("iniciativa:", "pode" if ok else motivo, "| cansaço:", cansaco())
