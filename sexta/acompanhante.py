# Acompanhante de voz. Criado em 13/11/2026, ideia do usuário.
#
# Enquanto o Claude trabalha numa resposta demorada, fala frases curtas para o
# usuário não ficar "no vácuo" (ele pode estar longe da tela, numa conversa por voz).
# As frases são verdadeiras: dizem o que o Claude está fazendo (lendo, testando,
# mexendo no código, pesquisando), a partir das ferramentas que ele está usando.
#
#   - "status":  hook PreToolUse. Anota qual ferramenta o Claude acabou de chamar.
#   - "rodar":   processo de fundo. Iniciado pelo voz.py quando o usuário envia
#                uma mensagem; morto pelo voz.py quando a resposta termina.
#
# Regras: primeira frase depois de 5 a 8 s sem resposta; depois, pausas variadas (4 a 22 s),
# cada vez mais espaçadas; nunca fala com o microfone do ditado aberto, nem por cima da fala
# principal ou da conversa rápida; cala sozinho depois de 10 min, se o usuário interromper a
# resposta ou se o limite de uso acabar. Áudios ficam em cache (sem espera e sem cota).
# Para desligar só o acompanhante num PC: crie %USERPROFILE%\.sexta-voz\sem-acompanhante

import hashlib, json, os, pathlib, random, re, sys, time
import sys as _sys, pathlib as _pl  # 16/11: com "-P" o Python não procura na pasta do arquivo; sem isto, nada abria
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg
try:   # 16/11 (OpenJarvis): o registro nunca guarda CPF, telefone, cartão, chave ou senha
    from seguranca import mascarar as _mascarar
except Exception:
    _mascarar = lambda s: s

BASE = pathlib.Path.home() / ".sexta-voz"
BASE.mkdir(exist_ok=True)
STATUS = BASE / "status.json"
PIDF = BASE / "acompanhante.pid"
FALANDO = BASE / "falando.pid"
GRAVANDO = BASE / "gravando"
FLAG = BASE / "ligada"
CACHE = BASE / "frases"
LEGENDA = BASE / "legenda.json"  # última frase dita (o mascote mostra)
LOG = BASE / "log.txt"
VOZ = cfg.VOZ_EDGE

# Estilo Jarvis (13/11/2026): calmo, preciso, educado, com leve humor seco.
# Frases curtas e variadas; nada de entusiasmo de locutor.
# 14/11: repertório maior, a pedido do usuário ("uma vasta gama"), e "usuário" no lugar do nome inteiro.
FRASES = {
    "pensar": ["Um momento... estou pensando nisso.", "Deixa eu organizar as ideias.",
               "Boa pergunta. Me dá um segundo.", "Estou montando a resposta.",
               "Hum... tem mais de um caminho aqui. Escolhendo o melhor.",
               f"Só um instante, {cfg.NOME}.", "Pensando com calma, que esse merece.",
               "Juntando as peças.", "Deixa eu ver por qual lado começo.",
               "Tem um detalhe aqui que eu quero acertar.", "Pesando as opções.",
               "Já tenho uma ideia. Só refinando."],
    "ler": ["Analisando os arquivos.", "Deixa eu ver como isso está agora.",
            "Consultando as anotações.", "Conferindo uma coisa antes de responder.",
            "Lendo com atenção, um momento.", "Folheando o código.",
            "Procurando onde isso mora.", "Relendo um trecho, para não errar.",
            "Achei uma parte interessante aqui.", "Só confirmando como está escrito."],
    "editar": ["Fazendo o ajuste.", "Escrevendo a mudança agora.", "Corrigindo isso, um instante.",
               "Mexendo no código... com cuidado.", "Aplicando a alteração.",
               "Trocando uma peça por outra.", "Apertando um parafuso aqui.",
               "Escrevendo devagar, que é parte delicada.", "Deixando isso mais arrumado.",
               "Quase pronto, só mais uma linha."],
    "rodar": ["Executando um teste.", "Verificando se funcionou.", "Rodando a checagem.",
              "Testando de novo, só para ter certeza.", "Conferindo o resultado.",
              "Vamos ver se ele concorda comigo.", "Dedos cruzados... metaforicamente.",
              "Esperando o computador responder.", "Testando antes de te mostrar."],
    "web": ["Pesquisando.", "Consultando algumas fontes.", "Lendo o que encontrei, um momento.",
            "Indo buscar isso lá fora.", "Comparando o que diferentes fontes dizem."],
    "demora": ["Ainda trabalhando nisso. Já termino.", "Está levando um pouco mais, mas está andando.",
               "Continuo aqui. Quase lá.", "Essa é das trabalhosas. Mais um pouco.",
               "Não esqueci de você. Só caprichando.", f"Paciência de monge, {cfg.NOME}. Já vai.",
               "Está ficando bom. Mais um pouquinho."],
}
ABERTURAS = ["", "Certo. ", "Agora, ", "Bom, ", "Um momento... "]
RE_INGLES = re.compile(r"\b(the|and|with|from|check|read|run|test|file|list|create|update|show)\b", re.I)
CATEGORIA = {"Read": "ler", "Grep": "ler", "Glob": "ler", "Edit": "editar", "Write": "editar",
             "NotebookEdit": "editar", "Bash": "rodar", "PowerShell": "rodar",
             "WebSearch": "web", "WebFetch": "web"}

def log(msg):
    try:
        msg = _mascarar(str(msg))
        import datetime
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} acompanhante: {msg}\n")
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

def modo_status():
    try:
        dados = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    except Exception:
        dados = {}
    if not isinstance(dados, dict):  # 16/11: "null" é JSON válido e quebrava o .get()
        dados = {}
    nome = dados.get("tool_name") or ""
    cat = CATEGORIA.get(nome) or ("web" if "search" in nome.lower() or "fetch" in nome.lower() else "pensar")
    STATUS.write_text(json.dumps({"cat": cat, "t": time.time(),
                                  "det": detalhe(cat, dados.get("tool_input") or {})}), encoding="utf-8")

def nome_amigavel(caminho):
    n = pathlib.PurePath(str(caminho)).stem
    n = re.sub(r"^\(C\)\s*", "", n)
    return re.sub(r"[-_]+", " ", n).strip()

def detalhe(cat, ent):
    # Frase específica e verdadeira sobre o passo atual (vazia se não der para dizer bem).
    if cat == "rodar":
        d = (ent.get("description") or "").strip().rstrip(".")
        if d and not RE_INGLES.search(d) and len(d) < 90:
            return d[0].lower() + d[1:]
        return ""
    arq = ent.get("file_path") or ent.get("notebook_path") or ""
    if arq and cat == "ler":
        return f"lendo o arquivo {nome_amigavel(arq)}"
    if arq and cat == "editar":
        return f"ajustando o arquivo {nome_amigavel(arq)}"
    return ""

def _modo_claude():
    """18/11: o dono está falando direto com o Claude: quem narra o trabalho é o Claude (o orbe)."""
    try:
        return (BASE / "modo-chat.txt").read_text(encoding="utf-8").strip() == "claude"
    except Exception:
        return False


def audio_de(frase, tom="+0Hz"):
    CACHE.mkdir(exist_ok=True)
    if _modo_claude():   # 18/11: a voz do Claude (Kokoro); se falhar, segue com a de sempre
        arq = CACHE / ("k-" + hashlib.md5(f"kokoro|{frase}".encode()).hexdigest()[:12] + ".wav")
        if arq.exists():
            return arq
        try:
            import voz
            feito = voz.gerar_kokoro(frase, arq.with_suffix(""))
            feito.with_suffix(".env.json").unlink(missing_ok=True)
            return feito
        except Exception:
            pass
    arq = CACHE / (hashlib.md5(f"{VOZ}|{tom}|{frase}".encode()).hexdigest()[:12] + ".mp3")
    if not arq.exists():
        import asyncio, edge_tts
        tmp = arq.with_suffix(".tmp")
        for tentativa in range(3):
            try:
                asyncio.run(edge_tts.Communicate(frase, VOZ, rate="-8%", pitch=tom).save(str(tmp)))
                break
            except Exception:
                if tentativa == 2:
                    raise
                time.sleep(0.8)
        tmp.replace(arq)
    return arq

def tocar(caminho):
    import ctypes
    mci = ctypes.windll.winmm.mciSendStringW
    mci(f'open "{caminho}" type mpegvideo alias acomp', None, 0, 0)
    mci("play acomp wait", None, 0, 0)
    mci("close acomp", None, 0, 0)

# ---------------------------------------------------------------- o Claude ainda está trabalhando?
# 14/11: quando o limite de uso acaba, a resposta para no meio e o aviso de "resposta terminou"
# nunca chega, então o acompanhante falava sozinho por até 10 min. Agora ele vigia o registro da
# conversa (transcript): se aparecer um erro da API (limite, falha) ou se nada mudar por muito
# tempo, ele cala.
def transcript():
    try:
        p = pathlib.Path((BASE / "transcript.txt").read_text(encoding="utf-8").strip())
        return p if p.is_file() else None
    except Exception:
        return None

class Vigia:
    def __init__(self):
        self.arq = transcript()
        self.pos = self.arq.stat().st_size if self.arq else 0
        self.mudou = time.time()
        self.resto = ""   # linha do registro que ainda não chegou inteira

    def parou(self):
        """Devolve o motivo se o Claude parou de trabalhar; "" se ele continua."""
        if not self.arq:
            return ""
        try:
            tam = self.arq.stat().st_size
            if tam > self.pos:
                with open(self.arq, "rb") as f:
                    f.seek(self.pos)
                    novo = f.read(tam - self.pos).decode("utf-8", "ignore")
                self.pos, self.mudou = tam, time.time()
                if '"isApiErrorMessage":true' in novo or '"isApiErrorMessage": true' in novo:
                    return "erro da API (limite de uso?)"
                # 15/11: se o usuário interrompe a resposta (Esc), o aviso de "terminou" não chega
                # e ela seguia dizendo "ainda trabalhando nisso" por até 6 min, sem ser verdade.
                linhas = (self.resto + novo).split("\n")
                self.resto = linhas.pop()
                if any(interrompida(l) for l in linhas):
                    return f"o {cfg.NOME} interrompeu a resposta"
            st_t = 0.0
            try:
                st_t = json.loads(STATUS.read_text(encoding="utf-8")).get("t", 0)
            except Exception:
                pass
            if time.time() - max(self.mudou, st_t) > 360:  # (testes longos podem levar minutos)
                return "6 min sem nenhum sinal do Claude"
        except Exception:
            pass
        return ""

def interrompida(linha):
    """A linha do registro é o aviso de que o usuário interrompeu? (e não um texto que só cita o aviso)"""
    if "[Request interrupted by user" not in linha:
        return False
    try:
        e = json.loads(linha)
        cont = (e.get("message") or {}).get("content")
        if e.get("type") != "user":
            return False
        if isinstance(cont, str):
            return cont.startswith("[Request interrupted by user")
        return any(isinstance(c, dict) and c.get("type") == "text"
                   and str(c.get("text", "")).startswith("[Request interrupted by user") for c in cont or [])
    except Exception:
        return False

def intervalo(falas):
    # Pausas mais naturais: às vezes rápido, às vezes um silêncio maior, e cada vez mais
    # espaçado conforme a resposta demora (ninguém narra tudo sem parar).
    base = random.choices([random.uniform(4, 6), random.uniform(7, 12), random.uniform(13, 22)],
                          weights=[2, 6, 2])[0]
    return base * (1 + min(falas, 8) * 0.12)

def modo_rodar():
    if (BASE / "sem-acompanhante").exists():
        return
    PIDF.write_text(str(os.getpid()))
    inicio = time.time()
    proxima = inicio + random.uniform(5, 8)
    usadas = set()
    falas = 0
    vigia = Vigia()
    while FLAG.exists() and time.time() - inicio < 600:
        time.sleep(0.5)
        motivo = vigia.parou()
        if motivo:
            log(f"calei: {motivo}")
            break
        if time.time() < proxima:
            continue
        if GRAVANDO.exists() or vivo(FALANDO) or (BASE / "rapida-ativa").exists():  # não fala por cima da conversa rápida
            proxima = time.time() + 4
            continue
        try:
            st = json.loads(STATUS.read_text(encoding="utf-8"))
        except Exception:
            st = {"cat": "pensar", "t": 0}
        fresco = st.get("t", 0) > inicio and time.time() - st["t"] < 25
        cat = st.get("cat", "pensar") if fresco else "pensar"
        if time.time() - inicio > 70 and (falas % 2 == 1 or not fresco):
            cat = "demora"
        det = st.get("det", "") if fresco else ""
        tom = "+0Hz"
        if det and det not in usadas:  # prioridade: dizer o que está fazendo de verdade
            abertura = random.choice(ABERTURAS)
            corpo = det[0].upper() + det[1:] if abertura.endswith(". ") else det  # maiúscula depois de ponto
            frase = (abertura + corpo).strip()
            frase = frase[0].upper() + frase[1:] + "."
            usadas.add(det)
            tom = random.choice(["-3Hz", "+0Hz", "+3Hz"])
        else:
            opcoes = [f for f in FRASES[cat] if f not in usadas] or FRASES[cat]
            frase = random.choice(opcoes)
            usadas.add(frase)
        try:
            audio = audio_de(frase, tom)
            # "fala": true enquanto toca (a mascote pode reagir ao que está sendo dito)
            LEGENDA.write_text(json.dumps({"txt": frase, "t": time.time(), "cat": cat, "fala": True}), encoding="utf-8")
            tocar(audio)
            LEGENDA.write_text(json.dumps({"txt": frase, "t": time.time(), "cat": cat, "fala": False}), encoding="utf-8")
            falas += 1
        except Exception as e:
            log(f"falhou: {e!r}")
        proxima = time.time() + intervalo(falas)

if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    if os.environ.get("SEXTA_PONTE") and modo == "status":
        sys.exit(0)   # 17/11: tarefa da ponte do Telegram; o PC não narra os passos
    try:
        if modo == "status":
            modo_status()
        elif modo == "rodar":
            modo_rodar()
        elif modo == "preparar":  # gera todos os áudios do cache de uma vez
            for lista in FRASES.values():
                for f in lista:
                    audio_de(f)
            print("ok")
    except Exception as e:
        log(f"erro no modo {modo}: {e!r}")
    finally:
        if modo == "rodar":
            try:
                if PIDF.read_text().strip() == str(os.getpid()):
                    PIDF.unlink()
            except Exception:
                pass
    sys.exit(0)
