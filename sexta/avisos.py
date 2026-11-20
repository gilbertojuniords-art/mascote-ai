# Avisos da Sexta. Criado em 15/11/2026, pedido do usuário.
#
# De vez em quando, a mascote lembra o usuário de um prazo chegando ou de uma pendência parada.
# Os avisos vêm de UMA nota só: Avisos.md (o usuário e o Claude editam).
#
# Segurança (exigência do usuário: "segura e que rode somente na minha máquina"):
#   - SEM INTERNET e SEM TOKEN: só usa a biblioteca padrão do Python. Nada de Haiku, nada de API.
#     A voz fala só frases genéricas ("usuário, um lembrete rápido"), com áudio gerado UMA vez
#     e guardado no PC (modo "preparar"). O assunto do aviso aparece só no balão da mascote.
#     Se o áudio não estiver guardado, o aviso sai calado (nunca vai buscar na internet).
#   - Só roda com o modo voz ligado e a mascote aberta; não começa com o Windows.
#   - Lê só a nota de avisos. O registro anota só o tipo do aviso, nunca o texto.
#   - Para desligar: crie %USERPROFILE%\.sexta-voz\sem-avisos (ou diga "desliga os avisos").
#
# Regras: das 8h às 22h; no máximo 4 avisos por dia, com pelo menos 2 h entre eles; o mesmo
# item no máximo uma vez por dia; nunca por cima do ditado, da fala, da Sexta rápida ou
# enquanto o Claude trabalha.
#   Prazo: avisa na véspera, no dia e enquanto estiver vencido sem marcar [x].
#   Parada: avisa quando está parada há 2 dias ou mais.

import datetime, hashlib, json, os, pathlib, random, re, sys, time
import sys as _sys, pathlib as _pl  # 16/11: com "-P" o Python não procura na pasta do arquivo; sem isto, nada abria
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg
try:   # 16/11 (OpenJarvis): o registro nunca guarda CPF, telefone, cartão, chave ou senha
    from seguranca import mascarar as _mascarar
except Exception:
    _mascarar = lambda s: s

def _carregar_leis():
    # 15/11: as Leis da Sexta (Asimov) decidem se um aviso pode sair. Arquivo ao lado deste.
    import importlib.util
    spec = importlib.util.spec_from_file_location("leis", pathlib.Path(__file__).with_name("leis.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

leis = _carregar_leis()

def _carregar_vontades():
    # 15/11 (noite): as cinco vontades e o diário da Sexta. Arquivo ao lado deste.
    import importlib.util
    spec = importlib.util.spec_from_file_location("vontades", pathlib.Path(__file__).with_name("vontades.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

vontades = _carregar_vontades()

BASE = pathlib.Path.home() / ".sexta-voz"
NOTA = cfg.nota("avisos")
PIDF = BASE / "avisos.pid"
ESTADO = BASE / "avisos-estado.json"
AVISO = BASE / "aviso.json"          # a mascote lê: mostra o balão
CACHE = BASE / "frases"
LOG = BASE / "log.txt"
VOZ = cfg.VOZ_EDGE

HORA_INI, HORA_FIM = 8, 22
MAX_DIA = 4
ESPACO_S = 2 * 3600
DIAS_PARADA = 2
PRIMEIRA_ESPERA_S = 10 * 60          # depois de ligar, espera 10 min antes do primeiro aviso

# Frases genéricas: não dizem o assunto, de propósito (o assunto fica só na tela).
FRASES = {
    "prazo": [f"{cfg.NOME}, tem um prazo chegando. Deixei no balão.",
              f"Um lembrete de prazo, {cfg.NOME}. Está aqui em cima.",
              f"{cfg.NOME}, só para não escapar: um prazo. Dá uma olhada no balão."],
    "parada": [f"{cfg.NOME}, tem uma coisa parada há uns dias. Se quiser, eu preparo o primeiro passo. É só me chamar.",
               f"{cfg.NOME}, sem pressão... uma coisa está parada. Quer que eu prepare o começo? Me chama.",
               f"Uma pendência esperando por você, {cfg.NOME}. Eu posso preparar o primeiro passo, se quiser."],
    # vontade alta: a mesma oferta, com mais vontade (nunca com cobrança)
    "parada_forte": [f"{cfg.NOME}, de novo aquela coisa parada. Deixa eu te ajudar a começar? É só me chamar.",
                     f"Ainda está parada, {cfg.NOME}... e eu queria muito ver isso pronto. Me chama, que eu preparo o começo."],
    # a satisfação da vontade: algo virou [x]
    # 16/11: a mente dela (pensar.py) quer contar algo que pensou ou pesquisou. O assunto fica só no balão.
    "curiosidade": [f"{cfg.NOME}, pensei numa coisa. Se quiser saber, é só me chamar.",
                    f"Achei uma coisa interessante, {cfg.NOME}. Deixei no balão.",
                    f"{cfg.NOME}, quando tiver um minuto... queria te contar uma coisa."],
    "feito": [f"Isso, {cfg.NOME}! Uma coisa a menos.",
              "Terminou! Eu vi... e gostei.",
              "Feito. Riscado da lista."],
}

RE_ITEM = re.compile(r"^\s*-\s*\[( |x|X)\]\s*(\d{4}-\d{2}-\d{2})\s*[·|—-]\s*(.+?)\s*$")

def log(msg):
    try:
        msg = _mascarar(str(msg))
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} avisos: {msg}\n")
    except Exception:
        pass

def vivo(arq):
    import ctypes
    try:
        pid = int(arq.read_text().strip())
    except Exception:
        return False
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    code = ctypes.c_ulong()
    ok = k.GetExitCodeProcess(h, ctypes.byref(code))
    k.CloseHandle(h)
    return bool(ok) and code.value == 259

def ler_itens():
    """Lê a nota: [(tipo, data, texto)] dos itens ainda não marcados."""
    try:
        linhas = NOTA.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    tipo, itens = None, []
    for l in linhas:
        if l.startswith("## "):
            t = l[3:].strip().lower()
            tipo = "prazo" if t.startswith("prazo") else "parada" if t.startswith("parad") else None
            continue
        m = RE_ITEM.match(l)
        if tipo and m and m.group(1) == " ":
            try:
                d = datetime.date.fromisoformat(m.group(2))
            except ValueError:
                continue
            itens.append((tipo, d, m.group(3)))
    return itens

def ler_feitos():
    """15/11: {chave: texto} dos itens já marcados com [x] (é o que satisfaz a vontade)."""
    try:
        linhas = NOTA.read_text(encoding="utf-8").splitlines()
    except Exception:
        return {}
    tipo, feitos = None, {}
    for l in linhas:
        if l.startswith("## "):
            t = l[3:].strip().lower()
            tipo = "prazo" if t.startswith("prazo") else "parada" if t.startswith("parad") else None
            continue
        m = RE_ITEM.match(l)
        if tipo and m and m.group(1) in "xX":
            feitos[chave(m.group(3))] = m.group(3)
    return feitos

def separar_passo(texto):
    """"texto → próximo passo": a parte depois da seta é o que ela oferece produzir."""
    if "→" in texto:
        a, b = texto.split("→", 1)
        return a.strip(), b.strip()
    return texto.strip(), ""

# ------------------------------------------------------------------ 15/11: a vontade "ver terminado"
# A primeira vontade da Sexta (o id). Ela não sabe que tem: é só um número aqui.
#   - SOBE com o que está parado (mais dias, mais vontade) e com prazo chegando.
#   - É SATISFEITA quando algo vira [x], e não quando ela avisa (se satisfazer avisando seria
#     cumprir o objetivo ao pé da letra, a lição do vídeo sobre a IA e a fome).
#   - Tem TETO (1.0) e se acalma depois de uma conquista, como a fome depois de comer.
VONTADES = BASE / "vontades.json"

def vontade_terminar(itens, hoje, estado, agora):
    # 15/11 (noite): a conta passou para o vontades.py, junto com as outras quatro.
    # Fica aqui só para o modo "simular".
    v = 0.0
    for tipo, data, texto in itens:
        if tipo == "parada":
            v += min(max((hoje - data).days, 0), 7) / 7 * 0.5
        elif tipo == "prazo" and 0 <= (data - hoje).days <= 2:
            v += 0.4
    v = min(1.0, v)
    if agora - estado.get("comemorou_t", 0) < 6 * 3600:   # satisfeita: acalma por 6 h
        v *= 0.3
    return round(v, 2)

def devido(tipo, data, hoje):
    """Texto do balão se o item merece aviso hoje; senão None."""
    if tipo == "prazo":
        falta = (data - hoje).days
        if falta == 1:
            return "Amanhã: "
        if falta == 0:
            return "Hoje: "
        if falta < 0:
            return "Venceu: "
    elif tipo == "parada":
        dias = (hoje - data).days
        if dias >= DIAS_PARADA:
            return f"Parado há {dias} dias: "
    return None

def chave(texto):
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:10]   # o estado guarda só isto, não o texto

def carregar_estado(hoje):
    try:
        e = json.loads(ESTADO.read_text(encoding="utf-8"))
    except Exception:
        e = {}
    if e.get("dia") != hoje.isoformat():
        e = {"dia": hoje.isoformat(), "n": 0, "ultimo": e.get("ultimo", 0), "vistos": [],
             "feitos": e.get("feitos"), "comemorou_t": e.get("comemorou_t", 0)}
    return e

def ocupado():
    return ((BASE / "gravando").exists() or vivo(BASE / "falando.pid")
            or (BASE / "rapida-ativa").exists() or vivo(BASE / "acompanhante.pid"))

def audio_guardado(frase):
    arq = CACHE / (hashlib.md5(f"{VOZ}|+0Hz|{frase}".encode()).hexdigest()[:12] + ".mp3")
    return arq if arq.exists() else None

def tocar(caminho):
    import ctypes
    mci = ctypes.windll.winmm.mciSendStringW
    mci(f'open "{caminho}" type mpegvideo alias aviso', None, 0, 0)
    mci("play aviso wait", None, 0, 0)
    mci("close aviso", None, 0, 0)

def avisar(tipo, texto, gesto=None):
    frase = random.choice(FRASES[tipo])
    balao = texto if len(texto) <= 70 else texto[:67].rstrip() + "…"
    # 16/11 (usuário): com a voz desligada, o aviso continua, só no balão (sem som)
    audio = audio_guardado(frase) if (BASE / "ligada").exists() else None
    gid = time.time()   # a mascote faz o gesto uma vez por aviso
    AVISO.write_text(json.dumps({"txt": balao, "t": gid, "fala": bool(audio), "gesto": gesto, "gid": gid}),
                     encoding="utf-8")
    if audio:
        tocar(audio)
    AVISO.write_text(json.dumps({"txt": balao, "t": time.time(), "fala": False}), encoding="utf-8")

def um_ciclo(estado, agora):
    hoje = datetime.date.today()
    # 15/11 (noite): as cinco vontades e o diário vivem mesmo sem corpo e sem avisos
    itens = ler_itens()
    feitos = ler_feitos()
    try:
        vont = vontades.calcular(itens, hoje, agora, estado.get("comemorou_t", 0))
        vontades.conferir_resultados({chave(t) for _, _, t in itens}, set(feitos), agora)
    except Exception as e:
        vont = {"terminar": 0.0}
        log(f"vontades falharam: {type(e).__name__}")
    if not vivo(BASE / "mascote.pid"):   # sem corpo, não há como avisar (não é uma lei)
        return False
    # 15/11: a satisfação. Algo novo virou [x]? Ela comemora (se as leis deixarem).
    if estado.get("feitos") is None:          # primeira vez: só aprende o que já estava feito
        estado["feitos"] = list(feitos)
        ESTADO.write_text(json.dumps(estado), encoding="utf-8")
    novos = [k for k in feitos if k not in estado["feitos"]]
    if novos:
        ok, lei, motivo = leis.julgar({"tipo": "comemoracao"})
        if ok:
            avisar("feito", "Feito: " + separar_passo(feitos[novos[0]])[0], gesto="comemora")
            estado["feitos"] = list(feitos)
            estado["comemorou_t"] = time.time()
            ESTADO.write_text(json.dumps(estado), encoding="utf-8")
            vontades.anotar("comemorou", n=len(novos))
            log(f"vontade satisfeita: {len(novos)} item(ns) feito(s); comemorou")
            return True
    # a vontade, para a mascote e para o tom da fala
    vontade = vont.get("terminar", 0.0)
    # 15/11 (noite): primeiro escolhe o candidato, porque o espaço entre avisos agora depende
    # do que ela aprendeu sobre aquele tipo de aviso (se o usuário costuma ignorar, ela espera mais).
    candidatos = []
    for tipo, data, texto in itens:
        prefixo = devido(tipo, data, hoje)
        if prefixo and chave(texto) not in estado["vistos"]:
            assunto, passo = separar_passo(texto)
            balao = prefixo + assunto + (f" → {passo}" if passo else "")
            candidatos.append((0 if tipo == "prazo" else 1, data, tipo, balao, chave(texto)))
    # 16/11: se não há prazo para lembrar, ela pode oferecer o que pensou (quero-contar.json, do pensar.py).
    # Passa pelo mesmo juiz dos avisos: horário, limite do dia, intervalo e "não interromper".
    if not any(c[0] == 0 for c in candidatos):
        try:
            qc = json.loads((BASE / "quero-contar.json").read_text(encoding="utf-8"))
        except Exception:
            qc = {}
        if qc.get("teaser") and not qc.get("mostrado") and time.time() - qc.get("t", 0) < 2 * 86400:
            ok, lei, motivo = leis.julgar({"tipo": "aviso", "hoje_dados": estado["n"], "max_dia": MAX_DIA,
                                           "desde_ultimo_s": agora - estado["ultimo"], "espaco_s": ESPACO_S})
            if ok:
                avisar("curiosidade", qc["teaser"], gesto="inclina")
                qc["mostrado"] = time.time()
                (BASE / "quero-contar.json").write_text(json.dumps(qc, ensure_ascii=False), encoding="utf-8")
                estado["n"] += 1
                estado["ultimo"] = time.time()
                ESTADO.write_text(json.dumps(estado), encoding="utf-8")
                log(f"aviso dado (curiosidade), {estado['n']} de {MAX_DIA} hoje")
                return True
    if not candidatos:
        return False
    candidatos.sort()   # prazos primeiro, depois o mais antigo
    _, _, tipo, texto, k = candidatos[0]
    # 15/11: o horário, o limite do dia, o intervalo e o "não interromper" saíram daqui e viraram
    # a 1ª Lei; "desliga os avisos" e o modo quieto viraram a 2ª. Quem decide é o juiz das leis.
    ok, lei, motivo = leis.julgar({"tipo": "aviso", "hoje_dados": estado["n"], "max_dia": MAX_DIA,
                                   "desde_ultimo_s": agora - estado["ultimo"],
                                   "espaco_s": vontades.espaco_aprendido(tipo, ESPACO_S)})
    if not ok:
        if estado.get("ultimo_veto") != motivo:   # anota só quando o motivo muda (sem texto do aviso)
            estado["ultimo_veto"] = motivo
            ESTADO.write_text(json.dumps(estado), encoding="utf-8")
            log(f"veto ({'regra dela' if lei == 'dela' else lei + ' Lei'}): {motivo}")
        return False
    # o tom forte também aprende: se ela costuma ser ignorada, não sobe o tom
    if tipo == "parada" and vontade * vontades.pesos()["parada"] >= 0.7:
        tipo = "parada_forte"
    avisar(tipo, texto, gesto="inclina")
    estado["n"] += 1
    estado["ultimo"] = time.time()
    estado["vistos"].append(k)
    ESTADO.write_text(json.dumps(estado), encoding="utf-8")
    vontades.registrar_aviso(tipo, k, vontade)   # o diário dela: para saber depois se ajudou
    log(f"aviso dado ({tipo}, vontade {vontade}), {estado['n']} de {MAX_DIA} hoje")
    return True

def modo_rodar():
    if vivo(PIDF):   # 15/11 (noite): "sem avisos" não desliga mais as vontades; a 2ª Lei cala os avisos
        return
    PIDF.write_text(str(os.getpid()))
    inicio = time.time()
    log("ligado")
    # 16/11: roda enquanto a mascote não for fechada (antes parava junto com a voz)
    while not (BASE / "mascote-fechado").exists():
        time.sleep(60)
        agora = time.time()
        if agora - inicio < PRIMEIRA_ESPERA_S:
            try:   # as vontades não esperam: só os avisos
                e = carregar_estado(datetime.date.today())
                vontades.calcular(ler_itens(), datetime.date.today(), agora, e.get("comemorou_t", 0))
            except Exception as ex:
                log(f"vontades falharam: {type(ex).__name__}")
            continue
        try:
            um_ciclo(carregar_estado(datetime.date.today()), agora)
        except Exception as e:
            log(f"falhou: {type(e).__name__}")
    log("desligado")

def modo_preparar():
    """Gera os áudios das frases genéricas (a única vez que usa a internet, e sem dado pessoal)."""
    import asyncio, edge_tts
    CACHE.mkdir(exist_ok=True)
    for lista in FRASES.values():
        for frase in lista:
            arq = CACHE / (hashlib.md5(f"{VOZ}|+0Hz|{frase}".encode()).hexdigest()[:12] + ".mp3")
            for tentativa in range(4):
                if arq.exists():
                    break
                try:
                    tmp = arq.with_suffix(".tmp")
                    asyncio.run(edge_tts.Communicate(frase, VOZ, rate="-8%").save(str(tmp)))
                    tmp.replace(arq)
                except Exception:
                    if tentativa == 3:
                        raise
                    time.sleep(1.5 * (tentativa + 1))
    print("ok")

def modo_simular():
    """Mostra o que seria avisado hoje, sem falar nem gravar nada (para testar)."""
    hoje = datetime.date.today()
    itens = ler_itens()
    for tipo, data, texto in itens:
        p = devido(tipo, data, hoje)
        print(f"{tipo:6} {data}  {'AVISARIA: ' + p + texto if p else '(ainda não)'}")
    estado = carregar_estado(hoje)
    print(f"vontade 'ver terminado': {vontade_terminar(itens, hoje, estado, time.time())} (0 a 1)")
    print("as cinco vontades:", vontades.calcular(itens, hoje, time.time(), estado.get("comemorou_t", 0)))
    print(vontades.como_estou())
    print(f"itens feitos que ela conhece: {len(estado.get('feitos') or [])}; feitos na nota: {len(ler_feitos())}")

if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if modo == "rodar":
            modo_rodar()
        elif modo == "preparar":
            modo_preparar()
        elif modo == "simular":
            modo_simular()
        elif modo == "testar":  # espera tudo ficar quieto (até 5 min) e dá um aviso de teste
            fim, quieto = time.time() + 600, 0
            time.sleep(20)
            while time.time() < fim and quieto < 15:   # precisa de 15 s seguidos de silêncio
                quieto = 0 if ocupado() else quieto + 1
                time.sleep(1)
            if quieto >= 15:
                avisar("parada", "Teste do aviso: se você lê isto, funcionou")
                log("aviso de teste dado")
    except Exception as e:
        log(f"erro no modo {modo}: {type(e).__name__}")
    finally:
        if modo == "rodar":
            try:
                if PIDF.read_text().strip() == str(os.getpid()):
                    PIDF.unlink()
            except Exception:
                pass
    sys.exit(0)
