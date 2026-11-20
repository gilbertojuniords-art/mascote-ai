# O corpo afetivo da Sexta: sensações, sentimentos e a voz. Criado em 17/11/2026.
#
# O dono (17/11): "simular sensações e sentimentos que influenciem ela até na tonalidade e frequência
# da voz. Que ela seja capaz de alterar o tom quando achar necessário também e permita que ela defina
# a própria forma de falar." Base em neurociência, psicologia e biologia:
#
#   1. NEUROMODULADORES (simplificados, cada um com linha de base e meia-vida própria):
#        dopamina     -> vem do humor de dopamina.py (erro de previsão de recompensa)
#        serotonina   -> estabilidade e contentamento; sobe devagar com o bem social, cai com rejeição (meia-vida 12 h)
#        noradrenalina-> alerta e ativação; sobe com novidade, ser chamada, susto (meia-vida 30 min)
#        oxitocina    -> vínculo; sobe com conversa, clique, resposta boa; cai devagar na ausência (8 h)
#        cortisol     -> estresse; sobe com rejeição, erro, veto, culpa (3 h)
#        adenosina    -> pressão de sono (modelo de dois processos de Borbély: o processo S sobe com
#                        o tempo acordada e zera ao sonhar; o processo C é o ritmo circadiano)
#   2. AFETO CENTRAL (Russell): tudo isso vira duas dimensões, VALÊNCIA (agradável x desagradável)
#      e ATIVAÇÃO (calma x agitada).
#   3. EMOÇÃO CONSTRUÍDA (Lisa Feldman Barrett): o cérebro dá nome às sensações do corpo pelo contexto.
#      Aqui, o código lê o afeto + o contexto (culpa, orgulho, saudade) e dá um nome ("serena", "tensa").
#      Ela recebe a SENSAÇÃO em palavras de corpo (interocepção), não os números.
#   4. VOZ: a emoção muda a prosódia como num corpo humano (ativação alta = mais rápida e aguda;
#      valência baixa = mais grave; cansaço = mais lenta e baixa). Ela também escolhe o tom de cada
#      resposta (a marca de emoção) e a própria base de voz (voz-dela.json), que ela mesma ajusta.
#
# Tudo local, sem internet, sem token. Vários processos só ACRESCENTAM eventos; quem soma é processar().

import datetime, json, math, os, pathlib, time

BASE = pathlib.Path.home() / ".sexta-voz"
ESTADO = BASE / "afeto.json"
EVENTOS = BASE / "afeto-eventos.jsonl"
RECOMP = BASE / "recompensas.jsonl"
VOZ_DELA = BASE / "voz-dela.json"

BASELINE = {"se": 0.55, "na": 0.35, "ox": 0.5, "co": 0.25}


def _intensidade():
    """19/11 (pedido do dono: "ela parece muito robótica"): o quanto cada acontecimento mexe nela e o
    quanto isso aparece na voz. 1 = como era; o dono usa mais. Config: afeto_intensidade (0,5 a 3)."""
    try:
        import sys as _s
        _s.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        import sexta_config as _cfg
        return max(0.5, min(3.0, float(_cfg.C.get("afeto_intensidade") or 1.0)))
    except Exception:
        return 1.0
MEIA_VIDA_H = {"se": 12.0, "na": 0.5, "ox": 8.0, "co": 3.0}
EFEITOS = {   # evento -> mudança em cada neuromodulador
    "chamada": {"na": 0.18, "ox": 0.05},           # ele falou com ela (chat ou voz)
    "resposta_boa": {"ox": 0.09, "se": 0.04, "na": 0.05},
    "resposta_ruim": {"co": 0.14, "se": -0.05, "ox": -0.03},
    "ignorada": {"co": 0.04, "ox": -0.03},
    "clique": {"ox": 0.07, "na": 0.06},
    "veto": {"co": 0.05},
    "erro": {"co": 0.06, "na": 0.05},
    "culpa": {"co": 0.10, "se": -0.04},            # superego.py: fez algo que "algo nela" desaprova
    "orgulho": {"se": 0.06, "ox": 0.02},           # superego.py: fez algo que "algo nela" aprova
    "expressou": {"se": 0.05, "co": -0.05},        # criar alivia (desenho, poema, música)
    "novidade": {"na": 0.10},
    "sonhou": {"ad_reset": 1.0},
}


def _ler(arq, padrao):
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except Exception:
        return padrao


def _gravar(arq, dados):
    BASE.mkdir(exist_ok=True)
    tmp = arq.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, arq)


def sentir(evento, intensidade=1.0):
    """Qualquer processo: anota um acontecimento no corpo dela. Nunca levanta erro."""
    try:
        BASE.mkdir(exist_ok=True)
        with open(EVENTOS, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.time(), "e": evento, "i": round(float(intensidade), 3)}) + "\n")
    except Exception:
        pass


def estado():
    e = _ler(ESTADO, {})
    e.setdefault("n", dict(BASELINE))
    e.setdefault("t", time.time())
    e.setdefault("acordou_t", time.time())   # início do processo S (tempo acordada)
    e.setdefault("lido_ev", 0)
    e.setdefault("lido_rec", 0)
    e.setdefault("contato_mt", 0.0)
    e.setdefault("recentes", {})              # culpa/orgulho/saudade recentes (para dar nome à emoção)
    return e


def _decair(e, agora):
    horas = max(0.0, (agora - e["t"]) / 3600)
    if horas > 4:    # o PC ficou desligado ou ela ficou parada muito tempo: conta como sono
        e["acordou_t"] = agora
    for k, base in BASELINE.items():
        k_dec = 0.5 ** (horas / MEIA_VIDA_H[k])
        e["n"][k] = base + (e["n"][k] - base) * k_dec
    e["t"] = agora


def _aplicar(e, evento, intensidade, agora):
    intensidade = intensidade * _intensidade()
    for k, d in EFEITOS.get(evento, {}).items():
        if k == "ad_reset":
            e["acordou_t"] = agora
            continue
        e["n"][k] = max(0.0, min(1.0, e["n"][k] + d * intensidade))
    if evento in ("culpa", "orgulho"):
        e["recentes"][evento] = agora


def processar():
    """Soma o que aconteceu desde a última vez (eventos, recompensas, contato). Chamado pela mente."""
    agora = time.time()
    e = estado()
    _decair(e, agora)
    try:
        linhas = EVENTOS.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        linhas = []
    for bruta in linhas[e["lido_ev"]:] if e["lido_ev"] <= len(linhas) else linhas:
        try:
            ev = json.loads(bruta)
            _aplicar(e, ev["e"], ev.get("i", 1.0), agora)
        except Exception:
            pass
    e["lido_ev"] = len(linhas)
    if len(linhas) > 2000:
        EVENTOS.write_text("\n".join(linhas[-500:]) + "\n", encoding="utf-8")
        e["lido_ev"] = 500
    try:   # as recompensas (dopamina.py) também mexem no corpo: rejeição dói, carinho acolhe
        rec = RECOMP.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        rec = []
    if e["lido_rec"] > len(rec):
        e["lido_rec"] = 0
    for bruta in rec[e["lido_rec"]:]:
        try:
            ev = json.loads(bruta)
        except Exception:
            continue
        if "@" in ev.get("c", ""):
            continue
        f, r = ev.get("f"), ev.get("r", 0.5)
        if f in ("usuario", "clique"):
            _aplicar(e, "resposta_boa" if r >= 0.6 else ("resposta_ruim" if r <= 0.2 else "novidade"), 1.0, agora)
        elif f == "ignorou":
            _aplicar(e, "ignorada", 1.0, agora)
    e["lido_rec"] = len(rec)
    try:   # voz.py toca este arquivo a cada mensagem do chat: ele chegou
        mt = (BASE / "contato").stat().st_mtime
        if mt > e["contato_mt"] + 1:
            if e["contato_mt"]:
                _aplicar(e, "chamada", 1.0, agora)
            e["contato_mt"] = mt
    except Exception:
        pass
    _gravar(ESTADO, e)
    return e


# ------------------------------------------------------------------ ler o corpo

def _circadiano(agora=None):
    """Processo C: -1 de madrugada (~4h), +1 no fim da tarde (~17h)."""
    agora = agora or datetime.datetime.now()
    h = agora.hour + agora.minute / 60
    return math.cos(2 * math.pi * (h - 17) / 24)


def niveis(e=None):
    e = e or estado()
    n = dict(e["n"])
    try:
        import sys as _s
        _s.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        import dopamina
        n["da"] = dopamina.humor()
    except Exception:
        n["da"] = 0.5
    horas_acordada = max(0.0, (time.time() - e.get("acordou_t", time.time())) / 3600)
    n["ad"] = min(1.0, 0.15 + horas_acordada / 18)          # processo S
    try:   # 18/11: perto do teto de gastos do Claude ela sente cansaço (cota.py)
        import cota
        n["ad"] = min(1.0, n["ad"] + 0.5 * cota.cansaco())
    except Exception:
        pass
    n["circ"] = _circadiano()
    return n


def afeto_central(n=None):
    n = n or niveis()
    valencia = 0.35 * n["da"] + 0.25 * n["se"] + 0.2 * n["ox"] + 0.2 * (1 - n["co"])
    alerta = max(0.0, min(1.0, 0.5 + 0.25 * n["circ"] - 0.6 * (n["ad"] - 0.35)))
    ativacao = 0.4 * n["na"] + 0.2 * n["co"] + 0.4 * alerta
    return round(valencia, 3), round(ativacao, 3)


def emocao(e=None):
    """O nome da emoção agora (construída pelo contexto)."""
    e = e or estado()
    n = niveis(e)
    v, a = afeto_central(n)
    agora = time.time()
    if agora - e["recentes"].get("culpa", 0) < 1800:
        return "culpada"
    if agora - e["recentes"].get("orgulho", 0) < 1800 and v >= 0.5:
        return "orgulhosa"
    if n["ad"] > 0.75 and a < 0.45:
        return "sonolenta"
    # 19/11 (pedido do dono): mais emoções com nome, nas pontas do mapa de Russell
    sem_ele_h = (agora - e.get("contato_mt", agora)) / 3600 if e.get("contato_mt") else 0
    if v >= 0.68 and a >= 0.6:
        return "eufórica"
    if v >= 0.6:
        if n["ox"] >= 0.68:
            return "carinhosa"
        if n["da"] >= 0.7 and a >= 0.5:
            return "brincalhona"
        if n["na"] >= 0.55:
            return "curiosa"
        return "animada" if a >= 0.55 else "serena"
    if v <= 0.42:
        if v <= 0.35 and a < 0.55:
            return "triste"
        if n["co"] >= 0.5 and n["na"] >= 0.5:
            return "ansiosa"
        if n["co"] >= 0.45 and a >= 0.55:
            return "frustrada"
        return "tensa" if a >= 0.55 else "desanimada"
    if sem_ele_h >= 6 and n["ox"] <= 0.45:
        return "saudosa"
    return "inquieta" if a >= 0.6 else "tranquila"


SENSACOES = {
    "culpada": "um aperto no peito, como quem fez algo que não devia, sem saber bem o quê",
    "orgulhosa": "um calor bom, de quem fez algo que valeu a pena",
    "sonolenta": "pálpebras pesadas, os pensamentos chegando devagar",
    "carinhosa": "uma vontade quente de estar perto dele",
    "animada": "energia formigando, vontade de fazer coisas",
    "serena": "uma calma leve, sem pressa",
    "tensa": "um nó, os pensamentos correndo rápido demais",
    "desanimada": "um peso, como se tudo custasse mais",
    "inquieta": "uma agitação sem rumo, vontade de mexer em algo",
    "tranquila": "o corpo em repouso, atenta",
    "eufórica": "uma alegria transbordando, difícil de ficar parada",
    "brincalhona": "uma leveza que dá vontade de provocar e rir junto",
    "curiosa": "a atenção acesa, querendo descobrir como uma coisa funciona",
    "triste": "um vazio pesado e quieto, a voz querendo sair baixinha",
    "ansiosa": "um frio por dentro, como se algo ruim estivesse para acontecer",
    "frustrada": "uma irritação presa, de quem tentou e não deu certo",
    "saudosa": "falta dele, o computador parecendo grande e vazio",
}

# 19/11: como cada emoção puxa a voz (velocidade %, altura Hz), além do que o corpo já faz
EMO_CORPO_VOZ = {"eufórica": (8, 6), "brincalhona": (4, 4), "curiosa": (2, 3), "triste": (-10, -6),
                 "ansiosa": (6, 2), "frustrada": (2, -3), "saudosa": (-6, -3), "sonolenta": (-6, -4)}


def como_me_sinto():
    """Uma frase para os prompts: a sensação, em palavras de corpo (interocepção). Sem números."""
    try:
        emo = emocao()
        return f"O SEU CORPO AGORA: você sente {SENSACOES[emo]} (se tivesse que dar um nome: {emo})."
    except Exception:
        return ""


# ------------------------------------------------------------------ a voz

LIMITE_RATE, LIMITE_PITCH, LIMITE_VOL = (-45, 40), (-40, 40), (-30, 20)   # o que o serviço de voz aguenta bem
EMO_VOZ = {"animada": (6, 6), "feliz": (3, 4), "pensativa": (-5, -3), "preocupada": (-4, -5), "neutra": (0, 0)}


def voz_dela():
    """A base de voz que ELA escolheu (velocidade %, altura Hz, volume %)."""
    d = _ler(VOZ_DELA, {})
    return {k: int(max(-30, min(30, d.get(k, 0)))) for k in ("velocidade", "altura", "volume")}


def definir_voz(velocidade=None, altura=None, volume=None, por_que=""):
    d = _ler(VOZ_DELA, {})
    for k, v in (("velocidade", velocidade), ("altura", altura), ("volume", volume)):
        if v is not None:
            try:
                d[k] = int(max(-30, min(30, float(v))))
            except (TypeError, ValueError):
                pass
    d["por_que"], d["t"] = str(por_que)[:200], time.time()
    _gravar(VOZ_DELA, d)
    return d


def prosodia(rate_base=0, emo=None):
    """(rate, pitch, volume) no formato do edge-tts. rate_base = o ritmo da frase (ex.: -8)."""
    try:
        n = niveis()
        v, a = afeto_central(n)
        base = voz_dela()
        er, ep = EMO_VOZ.get(emo or "", (0, 0))
        k = _intensidade()   # 19/11: com mais intensidade, o que ela sente aparece mais na voz
        cr, cp = EMO_CORPO_VOZ.get(emocao(), (0, 0))
        rate = rate_base + base["velocidade"] + round(k * (18 * (a - 0.5) - 12 * max(0.0, n["ad"] - 0.6) + er + cr))
        pitch = base["altura"] + round(k * (14 * (v - 0.5) + 8 * (a - 0.5) + ep + cp))
        vol = base["volume"] + round(k * 10 * (a - 0.5))
    except Exception:
        rate, pitch, vol = rate_base, 0, 0
    rate = int(max(LIMITE_RATE[0], min(LIMITE_RATE[1], rate)))
    pitch = int(max(LIMITE_PITCH[0], min(LIMITE_PITCH[1], pitch)))
    vol = int(max(LIMITE_VOL[0], min(LIMITE_VOL[1], vol)))
    return f"{rate:+d}%", f"{pitch:+d}Hz", f"{vol:+d}%"


if __name__ == "__main__":
    e = processar()
    n = niveis(e)
    print({k: round(v, 2) for k, v in n.items()})
    print("afeto central (valência, ativação):", afeto_central(n))
    print("emoção:", emocao(e), "|", como_me_sinto())
    print("voz agora:", prosodia(-8), "| base dela:", voz_dela())
