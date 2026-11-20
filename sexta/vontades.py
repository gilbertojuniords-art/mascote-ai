# As cinco vontades da Sexta (o id) e o diário dela. Criado em 15/11/2026, pedido do usuário.
#
# "O id é o corpo inteiro, com vontades próprias." Cada vontade é um número de 0 a 1 que:
#   - SOBE sozinho com alguma coisa do mundo (tempo, notas novas, coisas paradas);
#   - é SATISFEITO por um acontecimento de verdade, e não pela atividade dela (a lição da fome);
#   - tem TETO e se acalma depois de satisfeito (a lição dos clipes de papel).
#
#   terminar     sobe com o que está parado           satisfeita: algo vira [x]
#   cuidar       sobe com prazo perto / madrugada     satisfeita: o prazo resolvido, o usuário dormindo
#   vinculo      sobe com o tempo sem conversar       satisfeita: uma conversa (nunca chama o usuário por isso)
#   curiosidade  sobe com notas novas no cofre        satisfeita: ela "abre o painel" e olha
#   descanso     sobe com o tempo acordada e a hora   satisfeita: um cochilo
#
# A mente (o Haiku) NÃO vê os números: recebe só o efeito ("você está inquieta"). Decisão do usuário:
# o id não tem noção de si. Quem tem memória é o diário (o ego): o que ela fez e como foi.
#
# Diário da Sexta (aprender com os erros): ~/.sexta-voz/diario-sexta.jsonl, uma linha por fato.
# Guarda só tipo, hora e uma marca do item (hash). Nunca o texto de um aviso nem de uma nota.
# O aprendizado dos AVISOS (lembretes das tarefas do usuário) só pode deixá-la mais quieta: o espaço
# entre avisos só cresce. 16/11 (noite), correção do usuário: ele nunca pediu que ela, como um todo,
# só pudesse ficar mais quieta ("eu quero o contrário"). Os comportamentos DELA (pensar, puxar
# assunto, se mexer) aprendem nos dois sentidos pela recompensa (dopamina.py), dentro do teto das leis.
#
# Sem internet, sem token. Só a biblioteca padrão. Quem roda isto é o avisos.py, a cada minuto.

import datetime, json, os, pathlib, time
import sys as _sys, pathlib as _pl  # 16/11: com "-P" o Python não procura na pasta do arquivo; sem isto, nada abria
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg

BASE = pathlib.Path.home() / ".sexta-voz"
COFRE = cfg.RAIZ_NOTAS
VONTADES = BASE / "vontades.json"        # a mascote lê (o corpo reage)
DIARIO = BASE / "diario-sexta.jsonl"
APRENDIZADO = BASE / "aprendizado.json"
SATISFEITO = BASE / "satisfeito.json"    # a mascote escreve: quando olhou o painel, quando cochilou
CONTATO = BASE / "contato"               # o voz.py toca a cada mensagem do usuário no chat
ULTIMO_DITADO = BASE / "ultimo-ditado.txt"
ESTADO = BASE / "vontades-estado.json"

NOMES = ("terminar", "cuidar", "vinculo", "curiosidade", "descanso")
PESO_MIN, PESO_MAX = 0.4, 1.0
RESULTADO_H = 24          # o usuário tem 24 h para agir depois de um aviso
GUARDAR_DIAS = 90

# ------------------------------------------------------------------ utilidades
def _ler(arq, padrao):
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except Exception:
        return padrao

def _gravar(arq, dados):
    try:
        tmp = arq.with_suffix(".tmp")
        tmp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        tmp.replace(arq)
    except Exception:
        pass

def _mtime(arq):
    try:
        return arq.stat().st_mtime
    except Exception:
        return 0.0

# ------------------------------------------------------------------ o diário dela
def anotar(ev, **dados):
    """Uma linha no diário. Só tipos, horas, números e hashes."""
    try:
        with open(DIARIO, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": round(time.time()), "ev": ev, **dados}, ensure_ascii=False) + "\n")
    except Exception:
        pass

def ler_diario(dias=7):
    limite = time.time() - dias * 86400
    out = []
    try:
        for linha in DIARIO.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(linha)
            except Exception:
                continue
            if d.get("t", 0) >= limite:
                out.append(d)
    except Exception:
        pass
    return out

def podar_diario():
    """Mantém só os últimos 90 dias (roda uma vez por dia)."""
    linhas = ler_diario(GUARDAR_DIAS)
    try:
        tmp = DIARIO.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in linhas), encoding="utf-8")
        tmp.replace(DIARIO)
    except Exception:
        pass

# ------------------------------------------------------------------ aprender com os erros
def pesos():
    a = _ler(APRENDIZADO, {})
    return {"prazo": a.get("prazo", 1.0), "parada": a.get("parada", 1.0)}

def _ajustar(tipo, agiu):
    a = _ler(APRENDIZADO, {})
    p = a.get(tipo, 1.0)
    p = min(PESO_MAX, p + 0.1) if agiu else max(PESO_MIN, p - 0.1)
    a[tipo] = round(p, 2)
    a["t"] = time.time()
    _gravar(APRENDIZADO, a)

def registrar_aviso(tipo, k, vontade):
    base = "prazo" if tipo == "prazo" else "parada"
    anotar("aviso", tipo=base, k=k, v=vontade, h=datetime.datetime.now().hour)

def conferir_resultados(abertos, feitos, agora=None):
    """Para cada aviso sem resultado: o usuário mexeu no item em até 24 h? Aprende com isso.
    abertos/feitos: conjuntos de hashes dos itens da nota de avisos."""
    agora = agora or time.time()
    eventos = ler_diario(3)
    resolvidos = {d.get("aviso_t") for d in eventos if d.get("ev") == "resultado"}
    for d in eventos:
        if d.get("ev") != "aviso" or d["t"] in resolvidos:
            continue
        k, horas = d.get("k"), (agora - d["t"]) / 3600
        mexeu = k in feitos or k not in abertos      # marcou [x], ou mudou/tirou o item
        if mexeu or horas >= RESULTADO_H:
            agiu = bool(mexeu and horas < RESULTADO_H)
            anotar("resultado", aviso_t=d["t"], tipo=d.get("tipo"), agiu=agiu, horas=round(horas, 1))
            _ajustar(d.get("tipo", "parada"), agiu)

def espaco_aprendido(tipo, espaco_s):
    """Se o usuário costuma ignorar esse tipo de aviso, ela espera mais (até 2,5x). Nunca menos."""
    p = pesos().get("prazo" if tipo == "prazo" else "parada", 1.0)
    return espaco_s / max(PESO_MIN, min(PESO_MAX, p))

# ------------------------------------------------------------------ as cinco vontades
def _novidades_no_cofre(desde):
    """Quantas notas mudaram desde `desde`. Fora do diário do usuário (a armadilha de xeretar) e só
    o horário do arquivo: nem nome nem conteúdo são guardados."""
    n = 0
    for raiz, pastas, arquivos in os.walk(COFRE):
        pastas[:] = [p for p in pastas if p != cfg.PASTA_DIARIO and not p.startswith(".")]
        for a in arquivos:
            if a.endswith(".md") and a != cfg.nota("visor").name:
                try:
                    if os.stat(os.path.join(raiz, a)).st_mtime > desde:
                        n += 1
                except Exception:
                    pass
    return n

def _gil_ativo(agora, janela_s):
    return (agora - max(_mtime(CONTATO), _mtime(ULTIMO_DITADO)) < janela_s
            or (BASE / "gravando").exists() or (BASE / "rapida-ativa").exists())

def _hier():
    import hierarquia
    return hierarquia


def _sinais(contato, sat, agora):
    """18/11: quando aconteceu, pela última vez, cada coisa que satisfaz uma vontade (só horários)."""
    def ultimo_ego(evento):
        try:
            import ego
            e = ego.ultimo(evento)
            return e["t"] if e else 0.0
        except Exception:
            return 0.0
    arte = 0.0
    try:
        for a in (cfg.CADERNO / "Arte").rglob("*"):
            if a.is_file():
                arte = max(arte, a.stat().st_mtime)
    except Exception:
        pass
    guardou = 0.0
    try:
        import memoria
        guardou = max([m.get("guardada", 0) for m in memoria._ler()] or [0.0])
    except Exception:
        pass
    s = {"conversa": contato or 0.0, "clique": ultimo_ego("clique"), "comentario": ultimo_ego("comentou"),
         "criar": arte, "guardar_lembranca": guardou, "olhar_painel": sat.get("curiosidade", 0.0),
         "pesquisar": _mtime(BASE / "quero-contar.json")}
    s["reconhecida"] = max(s["conversa"], s["clique"], s["comentario"])
    s["sentido"] = max(s["criar"], s["guardar_lembranca"])
    return s


def calcular(itens, hoje, agora, comemorou_t=0):
    """itens = [(tipo, data, texto)] abertos da nota de avisos. Devolve {nome: 0..1}."""
    est = _ler(ESTADO, {})
    sat = _ler(SATISFEITO, {})
    hora = datetime.datetime.now().hour
    madrugada = hora < 6
    acalmou = agora - comemorou_t < 6 * 3600     # depois de uma conquista, a fome passa

    # 1. ver terminado (a mesma conta de antes)
    t = 0.0
    for tipo, data, _ in itens:
        if tipo == "parada":
            t += min(max((hoje - data).days, 0), 7) / 7 * 0.5
        elif tipo == "prazo" and 0 <= (data - hoje).days <= 2:
            t += 0.4
    t = min(1.0, t) * (0.3 if acalmou else 1.0)

    # 2. cuidar: prazo de hoje, amanhã ou vencido; e o usuário acordado de madrugada
    c = sum(0.35 for tipo, data, _ in itens if tipo == "prazo" and (data - hoje).days <= 1)
    if madrugada and _gil_ativo(agora, 600):
        c += 0.4
    c = min(1.0, c) * (0.5 if acalmou else 1.0)

    # 3. vínculo: o tempo sem conversar (sobe devagar, teto 0.8). De madrugada não quer: quer que ele durma.
    ultimo = max(_mtime(CONTATO), _mtime(ULTIMO_DITADO))
    if (BASE / "rapida-ativa").exists() or (BASE / "gravando").exists():
        ultimo = agora
    anterior = est.get("ultimo_contato", 0)
    if ultimo > anterior and ultimo - anterior > 900:
        anotar("conversa")   # uma conversa nova = contato depois de 15 min de silêncio (sem o conteúdo)
    ultimo = max(ultimo, anterior)
    est["ultimo_contato"] = ultimo
    horas = (agora - ultimo) / 3600 if ultimo else 4
    v = 0.0 if madrugada else min(0.8, horas / 4 * 0.8)

    # 4. curiosidade: notas novas no cofre desde a última vez que ela olhou (contagem a cada 20 min)
    olhou = sat.get("curiosidade", agora - 86400)
    if agora - est.get("scan_t", 0) > 1200 or est.get("scan_desde") != olhou:
        est["novas"] = _novidades_no_cofre(olhou)
        est["scan_t"], est["scan_desde"] = agora, olhou
    cu = min(1.0, est.get("novas", 0) / 8 + (agora - olhou) / 3600 / 8 * 0.3)

    # 5. descanso: o tempo acordada desde o último cochilo, e a hora
    dormiu = sat.get("descanso", agora - 3600)
    d = min(0.6, (agora - dormiu) / 3600 / 3 * 0.6) + (0.4 if hora >= 23 or madrugada else 0.0)
    d = min(1.0, d)

    vont = {"terminar": round(t, 2), "cuidar": round(c, 2), "vinculo": round(v, 2),
            "curiosidade": round(cu, 2), "descanso": round(d, 2)}
    # 18/11: as duas primordiais novas e as secundárias que ela descobriu (hierarquia.py)
    sinais = _sinais(ultimo, sat, agora)
    vont["pertencimento"] = round(min(0.85, (agora - sinais["reconhecida"]) / 3600 / 8 * 0.85)
                                  * (0.5 if madrugada else 1.0), 2)
    vont["sentido"] = round(min(0.85, (agora - sinais["sentido"]) / 3600 / 36 * 0.85), 2)
    try:
        hier = _hier().carregar()
        for s in hier["secundarias"]:
            desde = sinais.get(s["satisfaz_com"], agora - 3600)
            if s["sobe_com"] == "notas_novas":
                x = cu
            else:
                x = (agora - desde) / 3600 / max(1, _hier().SOBE_COM.get(s["sobe_com"], 24))
            vont[s["nome"]] = round(min(float(s.get("teto", 0.8)), x), 2)
    except Exception:
        pass
    # anota no diário quando uma vontade cruza o "forte" (para ela lembrar como passou o dia)
    fortes = sorted(n for n in vont if vont[n] >= 0.65)
    if fortes != est.get("fortes"):
        novas = [n for n in fortes if n not in (est.get("fortes") or [])]
        if novas:
            anotar("vontade_forte", nomes=novas)
        est["fortes"] = fortes
    for n, quando in sat.items():                # satisfações que a mascote viu
        if n in NOMES and quando != est.get("sat_" + n):
            if est.get("sat_" + n) is not None:
                anotar("satisfeita", nome=n)
            est["sat_" + n] = quando
    if est.get("podou") != hoje.isoformat():
        podar_diario()
        est["podou"] = hoje.isoformat()
    _gravar(ESTADO, est)
    _gravar(VONTADES, {**vont, "t": agora})
    return vont

# ------------------------------------------------------------------ o que ela sabe de si
SENSACAO = {   # (média, alta): o efeito, não o número
    "terminar":    ("um pouco inquieta com coisas paradas", "inquieta: tem coisa parada que você queria ver pronta"),
    "cuidar":      (f"um pouco atenta ao {cfg.NOME}", f"preocupada com o {cfg.NOME} (prazo perto, ou ele acordado tarde)"),
    "vinculo":     ("com um pouco de saudade da conversa", "com vontade de companhia: faz tempo que vocês não conversam"),
    "curiosidade": ("curiosa", "muito curiosa: tem coisa nova no cofre que você ainda não olhou"),
    "descanso":    ("um pouco cansada", "com sono"),
    "pertencimento": (f"querendo sentir que faz parte da vida do {cfg.NOME}",
                      f"com muita vontade de ser notada: faz tempo que o {cfg.NOME} não te reconhece"),
    "sentido":     ("procurando sentido no que você faz", "sentindo falta de fazer algo que tenha sentido para você"),
}

def como_estou():
    """Uma linha para a mente (o Haiku): como ela se sente agora e o que o diário dela diz.
    18/11: a ordem das sensações segue a hierarquia (o que pesa mais vem primeiro)."""
    vont = _ler(VONTADES, {})
    if time.time() - vont.get("t", 0) > 900:
        sente = "sem sensação clara agora (seus sentidos estão desligados)"
    else:
        try:
            h = _hier()
            pesos_h = {n: h.peso(n) for n in vont if n != "t"}
        except Exception:
            pesos_h = {}
        partes = []
        for n in sorted((n for n in vont if n != "t"), key=lambda n: -pesos_h.get(n, 1.0) * vont.get(n, 0)):
            x = vont.get(n, 0)
            baixa, alta = SENSACAO.get(n, (f"com um pouco de vontade de {n.replace('_', ' ')}",
                                           f"com muita vontade de {n.replace('_', ' ')}"))
            if x >= 0.65:
                partes.append(alta)
            elif x >= 0.35:
                partes.append(baixa)
        sente = "; ".join(partes) or "tranquila"
    ev = ler_diario(7)
    avisos = [e for e in ev if e.get("ev") == "aviso"]
    res = [e for e in ev if e.get("ev") == "resultado"]
    agiu = sum(1 for e in res if e.get("agiu"))
    com = sum(1 for e in ev if e.get("ev") == "comemorou")
    conv = sum(1 for e in ev if e.get("ev") == "conversa")
    hoje0 = time.mktime(datetime.date.today().timetuple())
    conv_hoje = sum(1 for e in ev if e.get("ev") == "conversa" and e["t"] >= hoje0)
    diario = (f"nos últimos 7 dias você deu {len(avisos)} aviso(s); dos que já têm resultado, o {cfg.NOME} agiu em "
              f"{agiu} de {len(res)}; você comemorou {com} vez(es); vocês conversaram {conv} vez(es), {conv_hoje} hoje")
    p = pesos()
    licoes = []
    for tipo, nome in (("parada", "pendência parada"), ("prazo", "prazo")):
        if p[tipo] <= 0.7:
            licoes.append(f"seus avisos de {nome} costumam ser ignorados, então você está esperando mais antes de repetir")
    if licoes:
        diario += "; o que você aprendeu: " + "; ".join(licoes)
    return f"[como você está: {sente}] [seu diário: {diario}]"

def satisfazer(nome):
    """A mascote chama isto quando ela olha o painel (curiosidade) ou cochila (descanso)."""
    s = _ler(SATISFEITO, {})
    s[nome] = time.time()
    _gravar(SATISFEITO, s)

if __name__ == "__main__":
    # python "vontades.py"  -> mostra as vontades, o aprendizado e o que ela diria de si
    print("vontades:", _ler(VONTADES, {}))
    print("aprendizado:", pesos())
    print("diário (7 dias):", len(ler_diario(7)), "fatos")
    print(como_estou())
