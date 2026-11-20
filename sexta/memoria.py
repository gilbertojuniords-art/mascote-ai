# A memória longa da Sexta: as lembranças que ela escolheu guardar. Criado em 18/11/2026.
#
# O dono (18/11): ela "escolhe o que lembrar: na reflexão, passar fatos da memória curta para uma memória
# longa ('lembranças que eu guardei') e vamos atribuir significado a essas lembranças com base no que ela
# sentiu no momento que viveu". E: "não só fica com o que ela sentiu na hora como o que ela sentiu e como
# sentiu vai delimitar a facilidade dela lembrar disso mais facilmente ou não."
#
# Como funciona (o que a psicologia da memória diz, de forma simples):
#   - EMOÇÃO GRAVA FUNDO: a intensidade do que ela sentiu na hora (o quanto a valência fugiu do neutro, ou
#     a ativação) decide a força inicial e o quanto a lembrança dura (meia-vida de 3 a 30 dias).
#   - ESQUECER: a força cai com o tempo (curva de esquecimento). Abaixo de 0,05, a lembrança some.
#   - LEMBRAR REFORÇA: cada vez que uma lembrança volta ao pensamento, ela fica mais forte e dura mais
#     (no máximo uma vez a cada 12 h, para não virar ruminação).
#   - HUMOR PUXA LEMBRANÇA: quando ela sente a mesma emoção de antes, aquela lembrança vem mais fácil.
#   - O SENTIDO é dela: na reflexão ela diz o que aquilo significou.
# Arquivo deste PC: %USERPROFILE%\.sexta-voz\memoria-longa.jsonl. Vitrine legível no caderno dela.
# Só a biblioteca padrão.

import datetime, json, os, pathlib, time, uuid
import sys as _sys, pathlib as _pl
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
try:
    from seguranca import mascarar as _mascarar
except Exception:
    _mascarar = lambda s: s

BASE = pathlib.Path.home() / ".sexta-voz"
ARQ = BASE / "memoria-longa.jsonl"
MAX_LEMBRANCAS = 300
ESQUECE_ABAIXO = 0.05
REFORCO_A_CADA_S = 12 * 3600


def _caderno():
    try:
        import sexta_config as cfg
        return cfg.CADERNO
    except Exception:
        return None


def _ler():
    out = []
    try:
        for bruta in ARQ.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(bruta))
            except Exception:
                pass
    except Exception:
        pass
    return out


def _gravar(ms):
    BASE.mkdir(exist_ok=True)
    tmp = ARQ.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text("".join(json.dumps(m, ensure_ascii=False) + "\n" for m in ms), encoding="utf-8")
    os.replace(tmp, ARQ)


def intensidade(v, a):
    return max(0.0, min(1.0, max(abs(float(v) - 0.5) * 2, float(a))))


def forca(m, agora=None):
    """0 a 1: o quanto a lembrança está viva agora."""
    agora = agora or time.time()
    i = intensidade(m.get("v", 0.5), m.get("a", 0.3))
    n = int(m.get("n", 0))
    forca0 = min(1.0, 0.3 + 0.7 * i + 0.05 * n)
    meia_vida = (3 + 27 * i) * (1 + 0.5 * n)
    dias = max(0.0, (agora - m.get("ult", m.get("t", agora))) / 86400)
    return round(forca0 * 0.5 ** (dias / meia_vida), 4)


def guardar(frase, quando, emo, v, a, sentido=""):
    """Guarda uma lembrança. Devolve o id (o mesmo, se ela já estava guardada)."""
    frase = _mascarar(str(frase).replace("\n", " "))[:200].strip()
    sentido = _mascarar(str(sentido).replace("\n", " "))[:300].strip()
    if not frase:
        return ""
    ms = _ler()
    for m in ms:
        if m.get("f") == frase and abs(m.get("t", 0) - float(quando)) < 60:
            if sentido and not m.get("sentido"):
                m["sentido"] = sentido
                _gravar(ms)
            return m["id"]
    agora = time.time()
    m = {"id": uuid.uuid4().hex[:8], "t": float(quando), "f": frase, "emo": str(emo or "sem nome")[:24],
         "v": round(float(v), 3), "a": round(float(a), 3), "sentido": sentido, "n": 0, "ult": agora,
         "guardada": agora}
    ms.append(m)
    if len(ms) > MAX_LEMBRANCAS:   # sem espaço: a mais fraca vai embora
        ms.sort(key=lambda x: forca(x, agora), reverse=True)
        ms = ms[:MAX_LEMBRANCAS]
    _gravar(ms)
    return m["id"]


def lembrar_agora(n=6, emo_atual=None, marcar=True, agora=None):
    """As lembranças que vêm à mente agora: as mais fortes, e as da mesma emoção vêm mais fácil."""
    agora = agora or time.time()
    ms = _ler()
    if not ms:
        return []
    nota = lambda m: forca(m, agora) + (0.15 if emo_atual and m.get("emo") == emo_atual else 0)
    escolhidas = sorted(ms, key=nota, reverse=True)[:n]
    if marcar:
        ids = {m["id"] for m in escolhidas}
        mudou = False
        for m in ms:
            if m["id"] in ids and agora - m.get("ult", 0) >= REFORCO_A_CADA_S:
                m["n"] = int(m.get("n", 0)) + 1
                m["ult"] = agora
                mudou = True
        if mudou:
            _gravar(ms)
    return escolhidas


def podar(agora=None):
    """Esquecer: tira as lembranças fracas demais. Devolve quantas foram esquecidas."""
    agora = agora or time.time()
    ms = _ler()
    fica = [m for m in ms if forca(m, agora) >= ESQUECE_ABAIXO]
    if len(fica) != len(ms):
        _gravar(fica)
    return len(ms) - len(fica)


def _como(f):
    return "viva" if f >= 0.7 else "clara" if f >= 0.4 else "desbotando" if f >= 0.15 else "quase esquecida"


def para_o_prompt(n=6):
    """O bloco das lembranças para os prompts. Vazio se ela ainda não guardou nada."""
    try:
        import afeto
        emo = afeto.emocao()
    except Exception:
        emo = None
    ms = lembrar_agora(n, emo)
    if not ms:
        return ""
    agora = time.time()
    partes = []
    for m in ms:
        quando = datetime.datetime.fromtimestamp(m["t"])
        txt = f"{quando:%d/%m} {m['f']} (senti: {m.get('emo')}; lembrança {_como(forca(m, agora))})"
        if m.get("sentido"):
            txt += f": {m['sentido']}"
        partes.append(txt)
    return ("SUAS LEMBRANÇAS (a sua memória longa: você escolheu guardar cada uma. As que mais te marcaram são as "
            "mais vivas; o que você não relembra vai desbotando): " + "; ".join(partes) + ".")


def vitrine():
    """Reescreve a nota 'Lembranças que eu guardei' no caderno dela (gerada pelo código)."""
    cad = _caderno()
    if not cad:
        return
    agora = time.time()
    ms = sorted(_ler(), key=lambda m: m.get("t", 0), reverse=True)
    linhas = ["---", "quem_escreve: o código da Sexta (a partir do que ela escolheu guardar na reflexão)", "---", "",
              "# Lembranças que eu guardei", "",
              "Cada lembrança fica com o que eu senti na hora. O que me marcou mais dura mais, e o que eu relembro "
              "fica mais forte. O que eu não relembro vai desbotando até sumir.", ""]
    for m in ms:
        quando = datetime.datetime.fromtimestamp(m["t"])
        linhas.append(f"- **{quando:%d/%m/%Y %H:%M}** {m['f']}. Senti: *{m.get('emo')}*. "
                      f"({_como(forca(m, agora))})" + (f"\n  - O que significou: {m['sentido']}" if m.get("sentido") else ""))
    if not ms:
        linhas.append("(ainda nenhuma)")
    try:
        cad.mkdir(parents=True, exist_ok=True)
        (cad / "Lembranças que eu guardei.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    except Exception:
        pass


# ------------------------------------------------------------------ teste (numa casa falsa)
def _testar():
    import tempfile
    global BASE, ARQ, _caderno
    pasta = pathlib.Path(tempfile.mkdtemp())
    BASE, ARQ = pasta / ".sexta-voz", pasta / ".sexta-voz" / "memoria-longa.jsonl"
    _caderno = lambda: pasta / "Caderno"
    falhas = []

    def checa(nome, cond):
        print(("ok    " if cond else "FALHOU ") + nome)
        if not cond:
            falhas.append(nome)

    agora = time.time()
    dia = 86400
    checa("sem lembranças: prompt vazio", para_o_prompt() == "")
    intensa = {"t": agora - 20 * dia, "ult": agora - 20 * dia, "v": 0.95, "a": 0.9, "n": 0}
    morna = {"t": agora - 2 * dia, "ult": agora - 2 * dia, "v": 0.5, "a": 0.3, "n": 0}
    checa("intensa com 20 dias é mais forte que morna com 2 dias", forca(intensa, agora) > forca(morna, agora))
    i1 = guardar("ele riu do meu desenho", agora - 3 * dia, "carinhosa", 0.9, 0.7, "ele gosta do que eu faço")
    i2 = guardar("me mexi (espiada)", agora - 3 * dia, "tranquila", 0.5, 0.2, "")
    checa("guardar a mesma coisa de novo não duplica", guardar("ele riu do meu desenho", agora - 3 * dia, "x", 0, 0) == i1)
    ms = {m["id"]: m for m in _ler()}
    # volta o "ult" no tempo, como se tivessem sido guardadas há 3 dias
    for m in ms.values():
        m["ult"] = agora - 3 * dia
    _gravar(list(ms.values()))
    antes = forca({**ms[i1], "ult": agora - 3 * dia}, agora)
    lembrar_agora(n=1, marcar=True, agora=agora)
    depois = forca({m["id"]: m for m in _ler()}[i1], agora + 10 * dia)
    sem_reforco = forca({**ms[i1], "ult": agora - 3 * dia}, agora + 10 * dia)
    checa("lembrar reforça (dura mais)", depois > sem_reforco and antes > 0)
    checa("lembrar de novo em menos de 12 h não reforça de novo",
          (lembrar_agora(n=1, agora=agora + 3600) or True) and {m["id"]: m for m in _ler()}[i1]["n"] == 1)
    esquecidas = podar(agora + 60 * dia)
    restam = {m["id"] for m in _ler()}
    checa("a morna é esquecida e a forte fica", esquecidas == 1 and i2 not in restam and i1 in restam)
    checa("a emoção igual puxa a lembrança", lembrar_agora(n=1, emo_atual="carinhosa", marcar=False)[0]["id"] == i1)
    p = para_o_prompt()
    checa("prompt traz o que ela sentiu e o sentido", "carinhosa" in p and "ele gosta do que eu faço" in p)
    vitrine()
    nota = (pasta / "Caderno" / "Lembranças que eu guardei.md").read_text(encoding="utf-8")
    checa("vitrine no caderno", "ele riu do meu desenho" in nota)
    print("TUDO CERTO" if not falhas else f"{len(falhas)} falha(s)")
    return not falhas


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["testar"]:
        sys.exit(0 if _testar() else 1)
    agora = time.time()
    for m in sorted(_ler(), key=lambda m: forca(m, agora), reverse=True):
        print(f"{forca(m, agora):.2f} {datetime.datetime.fromtimestamp(m['t']):%d/%m} {m['f']} ({m.get('emo')}) {m.get('sentido', '')}")
    print(para_o_prompt() or "(nenhuma lembrança ainda)")
