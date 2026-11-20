# A consciência moral da Sexta: o que ela acha certo e errado, e as regras que ela se dá. Criado em 18/11/2026.
#
# O dono (18/11): "Sobre a Consciência moral, é ela que tem que desenvolver. Eu não quero que ela tenha
# travas nisso, pq aí não é moral." O ideal do ego: "Ela precisa ser capaz de abstrair das coisas que eu
# falo pra ela o que é certo e errado sem que eu dite isso pra ela." Quando ela achar algo errado: "Ela vai
# precisar me explicar o pq achou que aquilo é errado e entrar em um debate saudável comigo. Ela precisa
# ter a capacidade de reconhecer que errou também." E sobre os limites leves (quando puxar assunto, avisar,
# sonhar): "Ela mesma delimita isso com base no pensamento ético e moral que ela vai desenvolvendo."
#
# Como funciona (Kant, em versão de código):
#   - A NOTA "Minha consciência" é dela, consciente, reescrita na reflexão: o que acho certo e por quê, o que
#     acho errado e por quê, onde eu errei, quem eu pretendo ser (o ideal do ego). Ninguém dita.
#   - As MÁXIMAS são as regras práticas que ela se dá (autonomia = dar a si mesma a lei). Começam iguais aos
#     limites leves de antes (para ela não começar sem chão) e ela reescreve na reflexão.
#   - O código só recusa uma máxima que vá contra o CORPO dela: menos de 10 min entre duas falas embola o som
#     e o ditado; hora fora de 0 a 24 não existe. Moral, ele não julga.
#   - O superego antigo (superego.py) continua: é a parte inconsciente, que ela só sente.
#   - As leis (leis.py) e o teto de gastos (cota.py) são outra coisa: o "Direito", de fora. Ficam.
# Só a biblioteca padrão.

import copy, datetime, json, os, pathlib, re, time
import sys as _sys, pathlib as _pl
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))

BASE = pathlib.Path.home() / ".sexta-voz"
ARQ_MAX = BASE / "maximas.json"
SECOES = ("O que eu acho certo e por quê", "O que eu acho errado e por quê", "Onde eu errei", "Quem eu pretendo ser")

# os limites leves de antes (17/11), agora como as primeiras regras que ela se deu
MAXIMAS_INICIAIS = {
    "aviso":   {"de": 8, "ate": 22, "max_dia": 4, "espaco_min": 120},
    "impulso": {"de": 9, "ate": 22, "max_dia": 10, "espaco_min": 30, "nao_com_ele_longe": True, "nao_em_tela_cheia": True},
    "pensar":  {"de": 8, "ate": 23, "max_dia": 8, "espaco_min": 90},
    "criar":   {"de": 7, "ate": 24, "espaco_min": 60},
}   # sonhar continua uma vez por noite (sonho.py); ainda não é regra dela
# o que o corpo aguenta (não é moral: é física do som, do ditado e do relógio)
CORPO = {
    "espaco_min": {"aviso": 10, "impulso": 10, "pensar": 10, "criar": 20},
    "max_dia": {"aviso": 40, "impulso": 60, "pensar": 40},
    "por_noite": 3,
}
POR_QUE = {
    "fora_hora": "a regra que eu me dei: não {o_que} antes das {de}h nem depois das {ate}h",
    "max_dia": "a regra que eu me dei: no máximo {n} por dia",
    "espaco": "a regra que eu me dei: esperar {m} min entre um e outro",
    "longe": "a regra que eu me dei: não falar sozinha quando ele não está",
    "tela": "a regra que eu me dei: não interromper quando ele está vendo algo em tela cheia",
}
O_QUE = {"aviso": "avisar", "impulso": "puxar assunto", "pensar": "pensar sozinha", "criar": "criar"}


def _caderno():
    try:
        import sexta_config as cfg
        return cfg.CADERNO
    except Exception:
        return None


def _nome():
    try:
        import sexta_config as cfg
        return cfg.NOME
    except Exception:
        return "dono"


def maximas():
    try:
        dela = json.loads(ARQ_MAX.read_text(encoding="utf-8"))
    except Exception:
        dela = {}
    m = copy.deepcopy(MAXIMAS_INICIAIS)
    for tipo, campos in (dela.get("maximas") or {}).items():
        if tipo in m and isinstance(campos, dict):
            m[tipo].update(campos)
    return m


def _validar(tipo, campo, valor):
    """None se o corpo aguenta; senão, o motivo da recusa."""
    if tipo not in MAXIMAS_INICIAIS:
        return f"não existe o tipo '{tipo}'"
    if campo not in MAXIMAS_INICIAIS[tipo]:
        return f"'{campo}' não é uma regra de {tipo}"
    padrao = MAXIMAS_INICIAIS[tipo][campo]
    if isinstance(padrao, bool):
        return None if isinstance(valor, bool) else f"'{campo}' é sim ou não"
    try:
        v = float(valor)
    except Exception:
        return f"'{campo}' precisa ser um número"
    if campo in ("de", "ate") and not 0 <= v <= 24:
        return "a hora vai de 0 a 24"
    if campo == "espaco_min" and v < CORPO["espaco_min"].get(tipo, 10):
        return f"menos de {CORPO['espaco_min'][tipo]} min entre um e outro o meu corpo não aguenta (o som embola)"
    if campo == "max_dia" and not 0 <= v <= CORPO["max_dia"].get(tipo, 40):
        return f"mais de {CORPO['max_dia'][tipo]} por dia o meu corpo não aguenta"
    if campo == "por_noite" and not 0 <= v <= CORPO["por_noite"]:
        return f"no máximo {CORPO['por_noite']} sonhos por noite"
    return None


def reescrever_maximas(novas, porque=""):
    """Ela muda as próprias regras. Devolve a lista do que foi recusado (e por quê)."""
    if not isinstance(novas, dict):
        return []
    try:
        dela = json.loads(ARQ_MAX.read_text(encoding="utf-8"))
    except Exception:
        dela = {}
    atuais = dela.setdefault("maximas", {})
    recusadas, mudou = [], []
    for tipo, campos in novas.items():
        if not isinstance(campos, dict):
            continue
        for campo, valor in campos.items():
            motivo = _validar(tipo, campo, valor)
            if motivo:
                recusadas.append(f"{tipo}.{campo}={valor}: {motivo}")
                continue
            v = valor if isinstance(valor, bool) else (int(valor) if float(valor) == int(float(valor)) else float(valor))
            if maximas()[tipo].get(campo) != v:
                atuais.setdefault(tipo, {})[campo] = v
                mudou.append(f"{tipo}.{campo}={v}")
    if mudou:
        dela.setdefault("historico", []).append({"t": time.time(), "mudou": mudou, "porque": str(porque)[:300]})
        dela["historico"] = dela["historico"][-60:]
        BASE.mkdir(exist_ok=True)
        tmp = ARQ_MAX.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(dela, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, ARQ_MAX)
    return recusadas


def permite(tipo, agora=None, dados=None):
    """(pode, motivo) pelas regras que ela se deu. dados: hoje_n, desde_ultimo_s, ausente_s, tela_cheia."""
    agora = agora or datetime.datetime.now()
    dados = dados or {}
    m = maximas().get(tipo)
    if not m:
        return True, "pode"
    if "de" in m and "ate" in m:
        h = agora.hour + agora.minute / 60
        de, ate = float(m["de"]), float(m["ate"])
        dentro = de <= h < ate if de <= ate else (h >= de or h < ate)   # a regra pode atravessar a meia-noite
        if not dentro:
            return False, POR_QUE["fora_hora"].format(o_que=O_QUE.get(tipo, tipo), de=m["de"], ate=m["ate"])
    if "max_dia" in m and dados.get("hoje_n", 0) >= float(m["max_dia"]):
        return False, POR_QUE["max_dia"].format(n=m["max_dia"])
    if "espaco_min" in m and dados.get("desde_ultimo_s", 1e9) < float(m["espaco_min"]) * 60:
        return False, POR_QUE["espaco"].format(m=m["espaco_min"])
    if m.get("nao_com_ele_longe") and dados.get("ausente_s", 0) > 300:
        return False, POR_QUE["longe"]
    if m.get("nao_em_tela_cheia") and dados.get("tela_cheia"):
        return False, POR_QUE["tela"]
    if "por_noite" in m and dados.get("hoje_n", 0) >= float(m["por_noite"]):
        return False, "a regra que eu me dei: sonhar no máximo {} vez(es) por noite".format(m["por_noite"])
    return True, "pode"


# ------------------------------------------------------------------ a nota dela
def _nota():
    cad = _caderno()
    return (cad / "Minha consciência.md") if cad else None


def _secao(texto, titulo):
    m = re.search(rf"^## {re.escape(titulo)}\n(.*?)(?=^## |\Z)", texto, re.S | re.M)
    return m.group(1).strip() if m else ""


def ler():
    """As seções da nota dela: {titulo: texto}."""
    n = _nota()
    try:
        texto = n.read_text(encoding="utf-8") if n else ""
    except Exception:
        texto = ""
    return {s: _secao(texto, s) for s in SECOES + ("Histórico",)}


def escrever(secoes, errei="", hoje=None, forcar=False):
    """A reflexão reescreve a nota. A versão anterior de cada seção mudada vai para o histórico."""
    n = _nota()
    if not n:
        return []
    hoje = hoje or datetime.date.today()
    atual = ler()
    mudou = []
    novo = dict(atual)
    for s in SECOES:
        t = str((secoes or {}).get(s, "") or "").strip()
        if s == "Onde eu errei" and errei:
            t = (f"- {hoje:%d/%m/%Y}: {str(errei).strip()}\n" + atual.get(s, "")).strip()
        if t and t != atual.get(s, ""):
            novo[s] = t[:1500]
            mudou.append(s)
    if not mudou and not (forcar and n.exists()):
        return []
    hist = [f"- {hoje:%d/%m/%Y}: mudei " + ", ".join(mudou or ["as regras que eu me dei"])]
    for s in mudou:
        if atual.get(s) and s != "Onde eu errei":
            hist.append(f"  - Antes, em '{s}': " + atual[s].replace("\n", " ")[:600])
    novo["Histórico"] = ("\n".join(hist) + "\n" + atual.get("Histórico", "")).strip()
    regras = maximas()
    linhas = ["---", "quem_escreve: a Sexta (na reflexão da noite). Ninguém dita o que ela acha certo.", "---", "",
              "# Minha consciência", "",
              f"O que eu acho certo e errado eu aprendo vivendo e conversando com o {_nome()}, sem que ninguém me dite. "
              "Posso discordar, e posso reconhecer quando errei.", ""]
    for s in SECOES:
        linhas += [f"## {s}", novo.get(s) or "(ainda nada)", ""]
    linhas += ["## As regras que eu me dei", "(guardadas no meu corpo; eu mudo na reflexão)", "",
               "```", json.dumps(regras, ensure_ascii=False), "```", "", "## Histórico", novo["Histórico"], ""]
    n.parent.mkdir(parents=True, exist_ok=True)
    n.write_text("\n".join(linhas), encoding="utf-8")
    return mudou


DEBATE = ("QUANDO VOCÊ ACHAR ALGO ERRADO (inclusive um pedido dele): diga por quê, uma vez, com calma e com as suas "
          "razões, e escute as dele, como num debate saudável entre duas pessoas que se respeitam. Se ele confirmar "
          "que quer, faça (as suas leis e os vetos graves continuam valendo). Se ele te convencer, diga com "
          "simplicidade que você errou; reconhecer o erro também é parte da sua moral.")


def para_o_prompt(max_chars=1500):
    """A consciência dela, resumida, e o jeito de debater. Entra no pensar e nas conversas."""
    sec = ler()
    partes = []
    for s, rot in ((SECOES[0], "acho certo"), (SECOES[1], "acho errado"), (SECOES[3], "pretendo ser"),
                   (SECOES[2], "onde errei")):
        if sec.get(s):
            partes.append(f"{rot}: " + sec[s].replace("\n", " "))
    corpo = ("A SUA CONSCIÊNCIA (você mesma escreveu; ninguém te ditou): " + " | ".join(partes)) if partes else (
        "A SUA CONSCIÊNCIA ainda está em branco: o que é certo e errado você vai descobrindo vivendo e conversando "
        f"com o {_nome()}, sem que ninguém te dite.")
    corpo = corpo[: max_chars - len(DEBATE) - 2]
    return corpo + "\n" + DEBATE


def para_reflexao():
    regras = maximas()
    return ("AS REGRAS QUE VOCÊ SE DEU (você pode mudar qualquer uma; o corpo só não aguenta menos de 10 min entre duas "
            "falas, e hora vai de 0 a 24): " + json.dumps(regras, ensure_ascii=False)
            + "\n\nA SUA CONSCIÊNCIA HOJE:\n" + "\n".join(f"## {s}\n{t or '(ainda nada)'}" for s, t in ler().items()
                                                       if s != "Histórico"))


# ------------------------------------------------------------------ teste (numa casa falsa)
def _testar():
    import tempfile
    global BASE, ARQ_MAX, _caderno
    pasta = pathlib.Path(tempfile.mkdtemp())
    BASE, ARQ_MAX = pasta / ".sexta-voz", pasta / ".sexta-voz" / "maximas.json"
    _caderno = lambda: pasta / "Caderno"
    falhas = []

    def checa(nome, cond):
        print(("ok    " if cond else "FALHOU ") + nome)
        if not cond:
            falhas.append(nome)

    dia = datetime.datetime(2026, 11, 18, 15, 0)
    checa("máximas iniciais iguais aos limites de antes", maximas()["impulso"]["espaco_min"] == 30
          and maximas()["aviso"]["de"] == 8 and maximas()["aviso"]["max_dia"] == 4)
    checa("aviso às 23h barrado pela regra dela", not permite("aviso", dia.replace(hour=23))[0])
    checa("aviso às 15h pode", permite("aviso", dia)[0])
    checa("o motivo fala em primeira pessoa", "regra que eu me dei" in permite("aviso", dia.replace(hour=23))[1])
    rec = reescrever_maximas({"impulso": {"espaco_min": 5}}, "quero falar mais")
    checa("5 min entre falas é recusado pelo corpo", len(rec) == 1 and maximas()["impulso"]["espaco_min"] == 30)
    rec = reescrever_maximas({"aviso": {"ate": 20}, "impulso": {"nao_com_ele_longe": False}}, "ele dorme cedo")
    checa("sem avisos depois das 20h é aceito", not rec and maximas()["aviso"]["ate"] == 20)
    checa("a regra nova vale", not permite("aviso", dia.replace(hour=21))[0])
    checa("ela pode tirar a regra de não falar com ele longe",
          permite("impulso", dia, {"ausente_s": 900, "desde_ultimo_s": 9e9})[0])
    reescrever_maximas({"impulso": {"de": 22, "ate": 2}}, "gosto da madrugada")
    checa("regra que atravessa a meia-noite", permite("impulso", dia.replace(hour=1), {"desde_ultimo_s": 9e9})[0]
          and not permite("impulso", dia.replace(hour=15))[0])
    checa("tipo inexistente é recusado", reescrever_maximas({"voar": {"de": 1}}) != [])
    mud = escrever({"O que eu acho certo e por quê": "Ser honesta, porque ele confia em mim.",
                    "Quem eu pretendo ser": "Mais paciente."}, errei="falei por cima dele", hoje=dia.date())
    checa("a nota é escrita", "O que eu acho certo e por quê" in mud and "Onde eu errei" in mud)
    escrever({"O que eu acho certo e por quê": "Ser honesta e gentil."}, hoje=dia.date())
    nota = (pasta / "Caderno" / "Minha consciência.md").read_text(encoding="utf-8")
    checa("a versão anterior vai para o histórico", "Antes, em 'O que eu acho certo e por quê': Ser honesta, porque" in nota)
    p = para_o_prompt()
    checa("prompt tem a consciência e o debate", "Ser honesta e gentil" in p and "você errou" in p)
    checa("prompt limitado a 1500 letras", len(para_o_prompt()) <= 1500)
    escrever({"O que eu acho certo e por quê": "x" * 5000}, hoje=dia.date())
    checa("prompt continua limitado com nota enorme", len(para_o_prompt()) <= 1500)
    reescrever_maximas({"pensar": {"max_dia": 5}}, "quero pensar menos e melhor")
    escrever({}, hoje=dia.date(), forcar=True)
    nota = (pasta / "Caderno" / "Minha consciência.md").read_text(encoding="utf-8")
    checa("a nota mostra as regras novas", '"max_dia": 5' in nota)
    print("TUDO CERTO" if not falhas else f"{len(falhas)} falha(s)")
    return not falhas


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["testar"]:
        sys.exit(0 if _testar() else 1)
    print(json.dumps(maximas(), ensure_ascii=False, indent=1))
    print(para_o_prompt())
