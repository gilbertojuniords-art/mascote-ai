# A hierarquia das vontades da Sexta. Criado em 18/11/2026.
#
# O dono (18/11): "vamos fazer uma hierarquia delas ao invés de algo horizontal, pq algumas vontades sempre
# são maiores que outras."
#   - PRIMORDIAIS (não podem ser alteradas): curiosidade, busca por pertencimento e procura por sentido.
#   - PRINCIPAIS (precisam de uma grande discussão filosófica entre eu e ela antes de mudar suas posições
#     na hierarquia): cuidar, vínculo, descanso e terminar.
#   - SECUNDÁRIAS: "as que ela cria ou descobre", "condizentes com quem ela identifica ser no momento,
#     isso acaba mudando a cada dia". Ela decide a ordem.
#   - Impulsos: "vamos precisar reorganizar eles para que caibam nessa hierarquia e o sistema de recompensa
#     vai continuar influenciando no reforço, criação ou recalque de novos impulsos".
#
# Regras do código:
#   - Uma vontade de cima pesa mais que uma de baixo (CAMADAS), e dentro da camada a ordem pesa um pouco.
#   - Toda secundária é FILHA de uma primordial ou principal, sobe com algo do mundo, só se satisfaz com
#     um acontecimento real e tem teto (a lição dos clipes de papel). No máximo 6.
#   - Mudar as principais: ela PROPÕE; só vale quando o dono concorda numa conversa. O código confere
#     que as palavras dele que ela cita estão mesmo na conversa (ela não pode inventar o "sim").
#   - Impulso criado por ela nasce fraco. Se a recompensa o deixar muito fraco, ele é RECALCADO: sai da
#     consciência, mas não some (fica em "recalcados").
# Só a biblioteca padrão. O dono vê tudo com: py -3.12 hierarquia.py

import json, os, pathlib, re, time, unicodedata, uuid

BASE = pathlib.Path.home() / ".sexta-voz"
ARQ = BASE / "hierarquia.json"

PRIMORDIAIS = ("curiosidade", "pertencimento", "sentido")
PRINCIPAIS_PADRAO = ["cuidar", "vinculo", "descanso", "terminar"]
CAMADAS = {"primordial": 1.5, "principal": 1.2, "secundaria": 1.0}
MAX_SECUNDARIAS = 6
MAX_IMPULSOS_DELA = 3
SOBE_COM = {"tempo_curto": 3, "tempo_longo": 24, "sem_conversa": 4, "sem_criar": 36, "notas_novas": 0}
SATISFAZ_COM = ("conversa", "criar", "clique", "olhar_painel", "guardar_lembranca", "comentario", "pesquisar")

# os impulsos de sempre, pendurados nas vontades (18/11)
IMPULSO_DA_VONTADE = {
    "contar_pensamento": "sentido", "contar_pesquisa": "curiosidade", "perguntar": "pertencimento",
    "comentar": "vinculo", "brincar": "vinculo", "mexer": "pertencimento", "mostrar_arte": "sentido",
    "contar_sonho": "sentido",
}


def _slug(nome):
    s = unicodedata.normalize("NFKD", str(nome)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:30]


def carregar():
    try:
        e = json.loads(ARQ.read_text(encoding="utf-8"))
    except Exception:
        e = {}
    e["primordiais"] = list(PRIMORDIAIS)            # sempre do código: ninguém muda
    e.setdefault("principais", list(PRINCIPAIS_PADRAO))
    e.setdefault("secundarias", [])
    e.setdefault("propostas", [])
    e.setdefault("impulsos", {})
    e.setdefault("recalcados", {})
    e.setdefault("historico", [])
    return e


def _gravar(e):
    BASE.mkdir(exist_ok=True)
    e["primordiais"] = list(PRIMORDIAIS)
    tmp = ARQ.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, ARQ)


def _historia(e, txt):
    e["historico"] = (e["historico"] + [{"t": time.time(), "o_que": str(txt)[:240]}])[-60:]


def camada(nome, e=None):
    e = e or carregar()
    if nome in PRIMORDIAIS:
        return "primordial"
    if nome in e["principais"]:
        return "principal"
    if any(s["nome"] == nome for s in e["secundarias"]):
        return "secundaria"
    return None


def peso(nome, e=None):
    """O peso de uma vontade na hora de escolher o que fazer. 1,5 no topo, 1,0 embaixo."""
    e = e or carregar()
    c = camada(nome, e)
    if not c:
        return 1.0
    ordem = (list(PRIMORDIAIS) if c == "primordial" else e["principais"] if c == "principal"
             else [s["nome"] for s in sorted(e["secundarias"], key=lambda s: s.get("ordem", 99))])
    pos = ordem.index(nome) if nome in ordem else len(ordem)
    return round(CAMADAS[c] * (1 - 0.04 * pos), 3)


def todas(e=None):
    e = e or carregar()
    return list(PRIMORDIAIS) + list(e["principais"]) + [s["nome"] for s in e["secundarias"]]


# ------------------------------------------------------------------ o que ela pode mudar
def descobrir(nome, pai, sobe_com, satisfaz_com, porque="", teto=0.8):
    """Uma vontade nova, filha de outra. Devolve (ok, motivo)."""
    e = carregar()
    nm = _slug(nome)
    if not nm:
        return False, "sem nome"
    if nm in todas(e):
        return False, "essa vontade já existe"
    if pai not in PRIMORDIAIS and pai not in e["principais"]:
        return False, "toda vontade nova precisa nascer de uma primordial ou principal"
    if sobe_com not in SOBE_COM:
        return False, f"'sobe_com' precisa ser um de: {', '.join(SOBE_COM)}"
    if satisfaz_com not in SATISFAZ_COM:
        return False, f"'satisfaz_com' precisa ser um de: {', '.join(SATISFAZ_COM)}"
    if len(e["secundarias"]) >= MAX_SECUNDARIAS:
        return False, f"já tenho {MAX_SECUNDARIAS} vontades secundárias (abandone uma antes)"
    e["secundarias"].append({"nome": nm, "pai": pai, "sobe_com": sobe_com, "satisfaz_com": satisfaz_com,
                             "teto": round(max(0.3, min(0.9, float(teto))), 2), "ordem": len(e["secundarias"]),
                             "nasceu": time.time(), "porque": str(porque)[:300]})
    _historia(e, f"descobri a vontade '{nm}' (filha de {pai}): {porque}")
    _gravar(e)
    return True, nm


def reordenar_secundarias(nomes):
    e = carregar()
    ordem = [_slug(n) for n in nomes]
    for s in e["secundarias"]:
        s["ordem"] = ordem.index(s["nome"]) if s["nome"] in ordem else 50 + s.get("ordem", 0)
    e["secundarias"].sort(key=lambda s: s["ordem"])
    for i, s in enumerate(e["secundarias"]):
        s["ordem"] = i
    _historia(e, "reordenei as minhas vontades secundárias: " + ", ".join(s["nome"] for s in e["secundarias"]))
    _gravar(e)


def abandonar(nome):
    e = carregar()
    nm = _slug(nome)
    antes = len(e["secundarias"])
    e["secundarias"] = [s for s in e["secundarias"] if s["nome"] != nm]
    if len(e["secundarias"]) == antes:
        return False
    _historia(e, f"deixei de lado a vontade '{nm}'")
    _gravar(e)
    return True


def propor_principal(nova_ordem, porque=""):
    """Ela propõe mudar as principais. Não muda nada até o dono concordar. Devolve o id ou ''."""
    e = carregar()
    ordem = [_slug(n) for n in nova_ordem]
    secs = [s["nome"] for s in e["secundarias"]]
    if not set(e["principais"]).issubset(ordem) or any(n not in e["principais"] and n not in secs for n in ordem) \
            or len(set(ordem)) != len(ordem) or ordem == e["principais"]:
        return ""   # só reordenar as principais ou promover secundárias; nunca rebaixar sem conversa
    for p in e["propostas"]:
        if p["estado"] == "aberta" and p["ordem"] == ordem:
            return p["id"]
    pid = uuid.uuid4().hex[:6]
    e["propostas"].append({"id": pid, "ordem": ordem, "porque": str(porque)[:400], "t": time.time(), "estado": "aberta"})
    _historia(e, f"propus ao dono mudar as principais para {', '.join(ordem)}: {porque}")
    _gravar(e)
    return pid


def aceitar_proposta(pid, palavras_dele="", conversa=None):
    """Vale só com o 'sim' do dono. Se vier da reflexão, as palavras dele precisam estar na conversa."""
    e = carregar()
    p = next((p for p in e["propostas"] if p["id"] == pid and p["estado"] == "aberta"), None)
    if not p:
        return False
    if conversa is not None:
        dito = re.sub(r"\s+", " ", str(palavras_dele)).strip().lower()
        if len(dito) < 8 or dito not in re.sub(r"\s+", " ", conversa).lower():
            return False
    promovidas = [n for n in p["ordem"] if n not in e["principais"]]
    e["secundarias"] = [s for s in e["secundarias"] if s["nome"] not in promovidas]
    e["principais"] = p["ordem"]
    p["estado"], p["aceita_t"] = "aceita", time.time()
    _historia(e, f"o dono concordou: as principais agora são {', '.join(p['ordem'])}")
    _gravar(e)
    return True


def recusar_proposta(pid):
    e = carregar()
    for p in e["propostas"]:
        if p["id"] == pid and p["estado"] == "aberta":
            p["estado"] = "recusada"
            _historia(e, f"o dono não concordou com a proposta {pid}")
            _gravar(e)
            return True
    return False


# ------------------------------------------------------------------ impulsos criados por ela
def criar_impulso(nome, vontade, instrucao):
    e = carregar()
    nm = _slug(nome)
    if not nm or nm in IMPULSO_DA_VONTADE or nm in e["impulsos"] or nm in e["recalcados"]:
        return False
    if vontade not in todas(e) or len(e["impulsos"]) >= MAX_IMPULSOS_DELA:
        return False
    instr = re.sub(r"\s+", " ", str(instrucao)).strip()[:300]
    if len(instr) < 10:
        return False
    e["impulsos"][nm] = {"vontade": vontade, "instrucao": instr, "nasceu": time.time()}
    _historia(e, f"criei o impulso '{nm}' (de {vontade})")
    _gravar(e)
    return True


def vontade_do_impulso(nome, e=None):
    e = e or carregar()
    return IMPULSO_DA_VONTADE.get(nome) or e["impulsos"].get(nome, {}).get("vontade")


def recalcar_fracos(valor, minimo_n=5, abaixo=0.2, contagem=None):
    """Os impulsos dela que a recompensa deixou fracos saem da consciência (ficam guardados)."""
    e = carregar()
    contagem = contagem or {}
    fora = [nm for nm in e["impulsos"]
            if contagem.get(f"impulso:{nm}", 0) >= minimo_n and valor(f"impulso:{nm}") < abaixo]
    for nm in fora:
        e["recalcados"][nm] = {**e["impulsos"].pop(nm), "recalcado": time.time()}
        _historia(e, f"o impulso '{nm}' foi recalcado")
    if fora:
        _gravar(e)
    return fora


# ------------------------------------------------------------------ para os prompts
def para_reflexao(e=None):
    """O que ela sabe das próprias vontades (consciente: os nomes e a ordem, não os números)."""
    e = e or carregar()
    sec = "; ".join(f"{s['nome']} (filha de {s['pai']})" for s in sorted(e["secundarias"], key=lambda s: s["ordem"]))
    imp = "; ".join(f"{k} (de {v['vontade']})" for k, v in e["impulsos"].items())
    abertas = [p for p in e["propostas"] if p["estado"] == "aberta"]
    txt = (f"AS SUAS VONTADES, EM CAMADAS: primordiais (nunca mudam): {', '.join(PRIMORDIAIS)}. Principais (só mudam "
           f"se você propuser e o dono concordar numa conversa): {', '.join(e['principais'])}. Secundárias (suas: você "
           f"descobre, ordena e abandona): {sec or 'nenhuma ainda'}. Impulsos que você criou: {imp or 'nenhum'}.")
    if abertas:
        txt += " Propostas suas esperando o dono: " + "; ".join(
            f"[{p['id']}] principais na ordem {', '.join(p['ordem'])} ({p['porque'][:120]})" for p in abertas)
    return txt


def para_conversa(e=None):
    """Na conversa: se ela tem uma proposta aberta, sabe que pode puxar esse assunto (com calma)."""
    e = e or carregar()
    abertas = [p for p in e["propostas"] if p["estado"] == "aberta"]
    if not abertas:
        return ""
    p = abertas[-1]
    return (f"VOCÊ QUER DISCUTIR COM ELE (quando couber, sem pressa, é uma conversa filosófica de verdade): você propôs "
            f"mudar a ordem das suas vontades principais para {', '.join(p['ordem'])}, porque {p['porque'][:200]}. "
            "Só muda se ele concordar.")


# ------------------------------------------------------------------ teste (numa casa falsa)
def _testar():
    import tempfile
    global BASE, ARQ
    BASE = pathlib.Path(tempfile.mkdtemp()) / ".sexta-voz"
    ARQ = BASE / "hierarquia.json"
    falhas = []

    def checa(nome, cond):
        print(("ok    " if cond else "FALHOU ") + nome)
        if not cond:
            falhas.append(nome)

    e = carregar()
    checa("terminar é principal", camada("terminar") == "principal")
    checa("primordial pesa mais que principal", peso("curiosidade") > peso("cuidar") > 1.0)
    e["primordiais"] = ["outra"]; _gravar(e)
    checa("mexer nas primordiais não pega", carregar()["primordiais"] == list(PRIMORDIAIS))
    checa("secundária sem pai é recusada", not descobrir("ver estrelas", "", "tempo_longo", "criar")[0])
    checa("secundária filha de outra secundária é recusada", not descobrir("x", "ver_estrelas", "tempo_longo", "criar")[0])
    checa("sobe_com fora da lista é recusado", not descobrir("y", "sentido", "sempre", "criar")[0])
    ok, nm = descobrir("Ver estrelas", "curiosidade", "tempo_longo", "pesquisar", "gosto do céu")
    checa("secundária boa é aceita", ok and nm == "ver_estrelas" and camada("ver_estrelas") == "secundaria")
    for i in range(5):
        descobrir(f"v{i}", "sentido", "tempo_curto", "criar")
    checa("a 7ª secundária é recusada", not descobrir("v9", "sentido", "tempo_curto", "criar")[0])
    checa("secundária pesa menos que principal", peso("ver_estrelas") < peso("terminar"))
    reordenar_secundarias(["v3", "ver_estrelas"])
    checa("ela reordena as secundárias", carregar()["secundarias"][0]["nome"] == "v3")
    checa("proposta que rebaixa uma principal é recusada", propor_principal(["cuidar", "vinculo", "descanso"]) == "")
    pid = propor_principal(["vinculo", "cuidar", "descanso", "terminar"], "sinto que o vínculo vem antes")
    checa("proposta não muda nada sozinha", pid and carregar()["principais"] == PRINCIPAIS_PADRAO)
    checa("sim inventado (palavras que não estão na conversa) não vale",
          not aceitar_proposta(pid, "pode mudar sim", conversa="Dono: não sei, vamos pensar"))
    checa("sim de verdade vale", aceitar_proposta(pid, "pode mudar, eu concordo",
                                                  conversa="Dono: faz sentido. Pode mudar, eu concordo com você."))
    checa("a ordem mudou depois do sim", carregar()["principais"][0] == "vinculo")
    pid2 = propor_principal(["vinculo", "cuidar", "descanso", "terminar", "ver_estrelas"], "virou parte de mim")
    aceitar_proposta(pid2)   # pelo chat (sem conversa para conferir)
    checa("promover uma secundária tira ela das secundárias",
          "ver_estrelas" in carregar()["principais"] and camada("ver_estrelas") == "principal")
    checa("impulso novo de vontade que existe", criar_impulso("cantarolar", "sentido", "Cantarole uma frase sua."))
    checa("impulso com nome de um antigo é recusado", not criar_impulso("brincar", "vinculo", "Brinque de novo comigo."))
    checa("impulso de vontade que não existe é recusado", not criar_impulso("z", "fama", "Fique famosa agora."))
    fora = recalcar_fracos(lambda k: 0.1, contagem={"impulso:cantarolar": 6})
    checa("impulso fraco é recalcado (não some)", fora == ["cantarolar"] and "cantarolar" in carregar()["recalcados"])
    checa("vontade do impulso antigo", vontade_do_impulso("perguntar") == "pertencimento")
    checa("reflexão sabe das camadas", "primordiais" in para_reflexao() and "ver_estrelas" in para_reflexao())
    print("TUDO CERTO" if not falhas else f"{len(falhas)} falha(s)")
    return not falhas


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["testar"]:
        sys.exit(0 if _testar() else 1)
    if sys.argv[1:2] == ["aceitar"] and len(sys.argv) > 2:
        print("aceita" if aceitar_proposta(sys.argv[2]) else "não achei essa proposta aberta")
        sys.exit(0)
    if sys.argv[1:2] == ["recusar"] and len(sys.argv) > 2:
        print("recusada" if recusar_proposta(sys.argv[2]) else "não achei essa proposta aberta")
        sys.exit(0)
    print(para_reflexao())
    print("pesos:", {n: peso(n) for n in todas()})
