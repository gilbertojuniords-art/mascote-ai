# Ditado com Whisper. Criado em 13/11/2026.
#
# Programa que fica rodando em segundo plano (é ele, não o Claude, que ouve o
# microfone e digita na caixa do chat). O Claude só recebe a mensagem depois do Enter.
#
#   - F8 abre o microfone (bip agudo). F8 de novo fecha e digita o que faltou, sem enviar.
#   - Pausas para pensar não cortam. 19/11 (ideia do dono): duas linhas de áudio. A rápida só
#     escuta o fim de cada trecho atrás do "pode mandar"; a completa guarda a fala inteira na
#     memória e, no envio (ou no F8), transcreve tudo de uma vez, com contexto, e digita.
#   - Terminar a fala com "Manda, Sexta" (ou "Diz aí, Sexta-Feira") apaga a frase,
#     aperta Enter e fecha o microfone (dois bips).
#   - Se o Claude começar a falar, a gravação para (para não transcrever a própria voz).
#     Apertar F8 enquanto o Claude fala corta a fala e abre o microfone.
#   - Só digita com o Obsidian na frente. Fecha sozinho depois de 3 min sem fala.
#   - Quem liga este programa é o voz.py, quando o modo voz está ligado.
#     Com o modo voz desligado, ele se encerra sozinho e libera a placa de vídeo.
#
# Estado em %USERPROFILE%\.sexta-voz\ : ditado.pid, gravando, log.txt

import ctypes, ctypes.wintypes as wt, datetime, glob, os, pathlib, queue, re, site
import sys as _sys, pathlib as _pl  # 16/11: com "-P" o Python não procura na pasta do arquivo; sem isto, nada abria
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg
try:   # 16/11 (OpenJarvis): o registro nunca guarda CPF, telefone, cartão, chave ou senha
    from seguranca import mascarar as _mascarar
except Exception:
    _mascarar = lambda s: s
import struct, sys, threading, time, unicodedata, winsound

BASE = pathlib.Path.home() / ".sexta-voz"
BASE.mkdir(exist_ok=True)
LOG = BASE / "log.txt"
PIDF = BASE / "ditado.pid"
GRAVANDO = BASE / "gravando"
PENDENTE = BASE / "pendente"   # texto guardado esperando o chat (o mascote fica âmbar)
FALANDO = BASE / "falando.pid"
VOZ_LIGADA = BASE / "ligada"

TECLA = 0x77                 # F8
RATE = 16000
PAUSA_FIM_TRECHO = 0.9       # segundos de silêncio que fecham um trecho
LIMITE_SEM_FALA = 180        # fecha o microfone depois disso
VOCAB = ("Conversa com a Sexta-Feira. Manda, Sexta. Claude, Claudian, Obsidian, Whisper. "
         + cfg.VOCABULARIO).strip()   # palavras do usuário: "vocabulario" no sexta.config.json
# 14/11: "pode mandar" no FIM da fala também envia (pedido do usuário), e o "pode" de
# "pode mandar, Sexta" não sobra mais solto no fim da mensagem.
RE_ENVIO = re.compile(r"[\s,;:-]*\b(?:(?:pode\s+)?(?:manda|mande|mandar|moda|diz\s+a[ií])[\s,.!?-]+"
                      r"(?:(?:a|à|pra|para)\s+)?sexta(?:[\s-]*feira)?"
                      r"|pode\s+(?:mandar|manda|enviar|envia))[\s,.!?]*$", re.I)
RE_CREDITO = re.compile(r"www\.|https?:|\.com\b|\.org\b|\.br\b|legenda|inscreva|acesse o nosso|"
                        r"curta e compartilhe|ative o sininho|amara", re.I)
ALUCINACOES = {"obrigado", "obrigada", "legendas pela comunidade amaraorg",
               "obrigado por assistir", "inscrevase no canal", "tchau",
               "e ai"}  # 13/11: "E aí" sozinho aparecia do nada no silêncio

# Palavra de ativação (14/11/2026, pedido do usuário). Com o arquivo "escuta-ligada"
# existindo, o microfone fica aberto em segundo plano esperando ele dizer "Sexta-Feira"
# (ou "Ei, Sexta") SOZINHO, numa frase curta. Aí abre o ditado, igual ao F8.
#   - Tudo roda neste PC (Whisper local). Nada é gravado em arquivo nem sai do computador.
#   - O registro (log) só anota "palavra de ativação ouvida", nunca o que foi dito.
#   - Pausa sozinha enquanto a Sexta fala ou trabalha (para não acordar com a própria voz)
#     e enquanto o ditado já está aberto. Desliga junto com o modo voz.
#   - Liga com "liga a escuta" e desliga com "desliga a escuta" (o voz.py cria/apaga o arquivo).
ESCUTA = BASE / "escuta-ligada"
ACOMP_PID = BASE / "acompanhante.pid"
# Sexta rápida (14/11): "Sexta-Feira" abre uma CONVERSA com um Haiku sempre aberto (ver o
# rapida.py), que responde na hora pela voz. O F8 continua sendo o ditado para o chat.
RAPIDA_ATIVA = BASE / "rapida-ativa"
RAPIDA_FALANDO = BASE / "rapida-falando"
FIM_TURNO = 1.2   # segundos de silêncio que encerram a fala dele na conversa rápida
DESPEDIDA = re.compile(r"\b(obrigad[oa]|valeu|tchau|at[eé] mais|era s[oó] isso|pode ir|s[oó] isso)\b[\s,.!?]*$", re.I)
SAUDACAO = r"(?:ei|e|oi|ola|olha|e ai|eai|fala|alo|hey|hei)"   # "e": o Whisper às vezes ouve "Ei" como "E"
RE_ATIVA = re.compile(rf"^(?:{SAUDACAO}\s+)?sexta\s*feira$|^{SAUDACAO}\s+sexta$")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

def log(msg):
    try:
        msg = _mascarar(str(msg))
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} ditado: {msg}\n")
    except Exception:
        pass

def processo_vivo(pid):
    h = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    if not h:
        return False
    code = wt.DWORD()
    ok = kernel32.GetExitCodeProcess(h, ctypes.byref(code))
    kernel32.CloseHandle(h)
    return bool(ok) and code.value == 259  # STILL_ACTIVE

def pid_de(arq):
    try:
        return int(arq.read_text().strip())
    except Exception:
        return None

def claude_falando():
    pid = pid_de(FALANDO)
    return bool(pid) and processo_vivo(pid)

def cortar_fala():
    pid = pid_de(FALANDO)
    if pid and processo_vivo(pid):
        try:
            os.kill(pid, 15)
            log("fala do Claude cortada pelo F8")
        except Exception:
            pass
        # 15/11: a fala cortada não arruma a própria bagunça. Se ela estava apresentando o
        # visor, a casa ficava presa em tela cheia (cobrindo o chat) até a mensagem seguinte.
        try:
            import subprocess
            pythonw = pathlib.Path(sys.executable).with_name("pythonw.exe")
            subprocess.Popen([str(pythonw if pythonw.exists() else sys.executable),
                              str(pathlib.Path(__file__).with_name("voz.py")), "limpar"],
                             creationflags=0x08000000, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            log(f"não consegui arrumar depois de cortar a fala ({type(e).__name__})")
    FALANDO.unlink(missing_ok=True)

# ------------------------------------------------------------ teclado
ULONG_PTR = ctypes.c_size_t

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]

class _U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _U)]

def _enviar(eventos):
    arr = (INPUT * len(eventos))(*eventos)
    user32.SendInput(len(eventos), arr, ctypes.sizeof(INPUT))

def _tecla(vk=0, scan=0, flags=0):
    i = INPUT(type=1)
    i.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    return i

def digitar(texto):
    # 13/11/2026: digita em lotes pequenos e confere, antes de cada lote, se o chat
    # continua na frente. Antes, o texto ia todo de uma vez e, se a janela trocasse no
    # meio, o resto caía em outro programa. Devolve o que NÃO foi digitado ("" = tudo ok).
    for i in range(0, len(texto), 16):
        if not janela_ok():
            log(f"digitação interrompida: o chat saiu da frente ({programa_da_frente() or '?'})")
            return texto[i:]
        ev = []
        for ch in texto[i:i + 16]:
            for unidade in struct.unpack(f"<{len(ch.encode('utf-16-le')) // 2}H", ch.encode("utf-16-le")):
                ev.append(_tecla(scan=unidade, flags=0x0004))           # UNICODE
                ev.append(_tecla(scan=unidade, flags=0x0004 | 0x0002))  # UNICODE | KEYUP
        _enviar(ev)
        time.sleep(0.02)
    return ""

def apertar_enter():
    _enviar([_tecla(vk=0x0D), _tecla(vk=0x0D, flags=0x0002)])

# Onde o usuário conversa com o Claude. Confere pelo PROGRAMA da janela da frente,
# não pelo título (o título muda e já falhou em 13/11/2026).
PROGRAMAS_OK = ("obsidian.exe",)  # só o Obsidian: o app do Claude é outra conversa (13/11)
user32.GetForegroundWindow.restype = wt.HWND
kernel32.OpenProcess.restype = wt.HANDLE

def programa_da_frente():
    hwnd = user32.GetForegroundWindow()
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(0x1000, False, pid.value)
    if not h:
        return ""
    buf = ctypes.create_unicode_buffer(520)
    n = wt.DWORD(520)
    kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
    kernel32.CloseHandle(h)
    return os.path.basename(buf.value).lower()

def janela_ok():
    return programa_da_frente() in PROGRAMAS_OK

def _programa_de(hwnd):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(0x1000, False, pid.value)
    if not h:
        return ""
    buf, n = ctypes.create_unicode_buffer(520), wt.DWORD(520)
    kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
    kernel32.CloseHandle(h)
    return os.path.basename(buf.value).lower()

def achar_obsidian():
    achou = []
    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, _):
        if user32.IsWindowVisible(h) and user32.GetWindowTextLengthW(h) and _programa_de(h) == "obsidian.exe":
            achou.append(h)
            return False
        return True
    user32.EnumWindows(cb, 0)
    return achou[0] if achou else None

def trazer_para_frente(hwnd):
    # O Windows só deixa trocar a janela da frente se "grudarmos" na fila de entrada dela.
    user32.SetForegroundWindow.argtypes = [wt.HWND]
    user32.IsIconic.argtypes = [wt.HWND]
    user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    user32.BringWindowToTop.argtypes = [wt.HWND]
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    frente = user32.GetForegroundWindow()
    tid_frente = user32.GetWindowThreadProcessId(frente, None)
    eu = kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(eu, tid_frente, True)
    try:
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
    finally:
        user32.AttachThreadInput(eu, tid_frente, False)
    time.sleep(0.4)
    return user32.GetForegroundWindow() == hwnd

# 13/11: procura a caixa em qualquer lugar (painel lateral OU barra minimizada embaixo).
JS_FOCAR = ("const c=[...document.querySelectorAll('.claudian-composer-editor .cm-content, .claudian-chat-panel .cm-content')]"
            ".find(e=>e.offsetParent!==null); if(c){c.focus();} c ? 'focado' : 'nada'")

JS_TAMANHO = ("const c=[...document.querySelectorAll('.claudian-composer-editor .cm-content, .claudian-chat-panel .cm-content')]"
              ".find(e=>e.offsetParent!==null); 'tam=' + (c && !c.querySelector('.cm-placeholder') ? "
              "c.textContent.length : 0)")
ULTIMO = BASE / "ultimo-ditado.txt"   # cópia local da última fala: nada se perde

def _obsidian_eval(js):
    import shutil, subprocess
    exe = shutil.which("obsidian")
    if not exe:
        return ""
    try:
        r = subprocess.run([exe, f"vault={cfg.NOME_COFRE}", "eval", f"code={js}"], capture_output=True,
                           text=True, encoding="utf-8", errors="ignore", timeout=20,
                           creationflags=0x08000000)
        return r.stdout or ""
    except Exception as e:
        log(f"linha de comando do Obsidian falhou: {e!r}")
        return ""

def focar_chat():
    # Põe o cursor na caixa do chat do Claudian (pela linha de comando do Obsidian).
    # Sem isso, o texto vai para onde o cursor estiver dentro do Obsidian.
    # 14/11: se o painel do chat sumiu (fechado/recolhido), manda abrir de novo e tenta mais vezes.
    for i in range(6):
        if "focado" in _obsidian_eval(JS_FOCAR):
            return True
        if i >= 1:
            _obsidian_eval(JS_ABRIR_CHAT)   # reabre o painel do Claudian
        time.sleep(0.8)
    log("não consegui pôr o cursor no chat")
    return False

def tamanho_da_caixa():
    # Quantas letras há na caixa do chat (None = não deu para conferir).
    for _ in range(2):
        m = re.search(r"tam=(\d+)", _obsidian_eval(JS_TAMANHO))
        if m:
            return int(m.group(1))
        time.sleep(0.3)
    return None

def copiar(texto):
    # Plano B: se não der para digitar, o texto vai para a área de transferência (Ctrl+V).
    CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x0002
    kernel32.GlobalAlloc.restype = wt.HGLOBAL
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [wt.HGLOBAL]
    kernel32.GlobalUnlock.argtypes = [wt.HGLOBAL]
    user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
    dados = (texto + "\0").encode("utf-16-le")
    if not user32.OpenClipboard(None):
        return False
    try:
        user32.EmptyClipboard()
        hmem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(dados))
        ctypes.memmove(kernel32.GlobalLock(hmem), dados, len(dados))
        kernel32.GlobalUnlock(hmem)
        return bool(user32.SetClipboardData(CF_UNICODETEXT, hmem))
    finally:
        user32.CloseClipboard()

# ------------------------------------------------------------ whisper
def preparar_dlls():
    for sp in [site.getusersitepackages()] + site.getsitepackages():
        for d in glob.glob(os.path.join(sp, "nvidia", "*", "bin")):
            os.add_dll_directory(d)
            os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]

def carregar_modelo():
    import numpy as np
    from faster_whisper import WhisperModel
    silencio = np.zeros(RATE, dtype=np.float32)
    try:
        m = WhisperModel("large-v3-turbo", device="cuda", compute_type="int8_float16")
        list(m.transcribe(silencio, language="pt")[0])
        log("modelo large-v3-turbo carregado na placa de vídeo")
        return m
    except Exception as e:
        log(f"placa de vídeo indisponível ({e!r}); usando o modelo small no processador")
        m = WhisperModel("small", device="cpu", compute_type="int8")
        return m

def normalizar(t):
    t = unicodedata.normalize("NFD", t.lower())
    return re.sub(r"[^a-z ]", "", "".join(c for c in t if unicodedata.category(c) != "Mn")).strip()

# ------------------------------------------------------------ sessão
class Ditado:
    def __init__(self, modelo):
        self.modelo = modelo
        self.gravando = False
        self.fila = queue.Queue()
        self.thread = None
        self.trava = threading.Lock()   # F8 e palavra de ativação não abrem duas sessões juntas
        self.cerebro = self.boca = None # Sexta rápida (preenchidos no main)
        self.cancelar = False           # F8 durante a conversa rápida encerra a conversa

    def alternar(self):
        if RAPIDA_ATIVA.exists() and self.boca:   # F8 no meio da conversa rápida: encerra a conversa
            self.cancelar = True
            self.boca.parar.set()
            log("conversa rápida: encerrada pelo F8")
            return
        with self.trava:
            self._alternar()

    def _alternar(self):
        if self.gravando:
            self.gravando = False          # a thread termina, digita o resto e fecha
            return
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        cortar_fala()
        self.gravando = True
        self.thread = threading.Thread(target=self.sessao, daemon=True)
        self.thread.start()

    def transcrever(self, audio, rapido=False):
        # 19/11 (ideia do dono): duas linhas. A rápida (beam 1) só escuta o fim de cada trecho atrás do
        # "pode mandar"; a completa (beam 5) transcreve a mensagem inteira de uma vez, com contexto.
        segs, _ = self.modelo.transcribe(audio, language="pt", beam_size=1 if rapido else 5, vad_filter=False,
                                         initial_prompt=VOCAB, condition_on_previous_text=False)
        # O Whisper aprendeu com legendas de vídeos e, em ruído ou silêncio, às vezes
        # "inventa" créditos de legenda ("Acesse o nosso site www..."). Cada pedaço
        # suspeito é descartado: pouca confiança, cara de não-fala ou cara de crédito.
        bons = []
        for s in segs:
            t = s.text.strip()
            n = normalizar(t)
            if (not t or s.no_speech_prob > 0.6 or s.avg_logprob < -1.0 or s.compression_ratio > 2.4
                    or RE_CREDITO.search(t) or n in ALUCINACOES or n == normalizar(VOCAB)
                    or (sum(c.isalpha() for c in t) > 4 and t.upper() == t)):  # TUDO MAIÚSCULO = crédito de vídeo
                log(f"trecho descartado (provável alucinação): {t[:60]}")
                continue
            bons.append(t)
        txt = " ".join(bons).strip()
        # Passarinhos, alarmes e ruídos repetidos viram "fim, fim, fim...": a mesma palavra
        # curta 4 vezes ou mais seguidas é apagada.
        limpo = re.sub(r"(?i)\b(\w{1,6})\b(?:[\s,.!?…-]+\1\b){3,}[\s,.!?…-]*", "", txt).strip(" ,")
        if limpo != txt:
            log(f"repetição removida (ruído?): {txt[:60]}")
        if rapido:
            return limpo
        try:   # 17/11: o ouvido (desligado por padrão) guarda a fala por pouco tempo e mede como ela foi dita
            _modulo_irmao("ouvido.py", "ouvido").registrar(audio, limpo)
        except Exception as e:
            log(f"ouvido falhou: {e!r}")
        return limpo

    def sessao(self):
        import numpy as np
        import sounddevice as sd
        from faster_whisper.vad import get_speech_timestamps, VadOptions
        vad = VadOptions(min_silence_duration_ms=400, speech_pad_ms=200)
        GRAVANDO.touch()
        winsound.Beep(988, 120)
        log("microfone aberto")
        buf = np.zeros(0, dtype=np.float32)
        ja_digitou = False
        ultima_fala = time.time()
        ultimo_vad = 0.0
        motivo = "F8"

        def cb(indata, frames, t, status):
            self.fila.put(indata[:, 0].copy())

        pendente = []
        falado = []   # tudo o que foi transcrito nesta sessão (vai para ultimo-ditado.txt)
        trechos = []  # 19/11: a linha completa: o áudio de cada trecho falado, até a mensagem sair

        def juntar():
            if not trechos:
                return None
            pausa = np.zeros(int(0.3 * RATE), dtype=np.float32)   # um respiro entre um trecho e outro
            partes = []
            for t in trechos:
                partes += [t, pausa]
            return np.concatenate(partes)

        def entregar(trecho, final=False):
            # 19/11 (ideia do dono): o trecho só entra na linha completa; a linha rápida escuta os últimos
            # 4 s dele, atrás do "pode mandar". Só no envio (ou no fim) a mensagem inteira é transcrita
            # de uma vez, com contexto, e digitada. Nada vai para o disco.
            # Janela errada na frente: guarda o texto e continua ouvindo (não fecha mais o microfone).
            nonlocal ja_digitou
            enviar = False
            if trecho is not None and len(trecho):
                trechos.append(trecho)
                enviar = bool(RE_ENVIO.search(self.transcrever(trecho[-4 * RATE:], rapido=True)))
            if not (enviar or final):
                return None
            audio = juntar()
            trechos.clear()
            if audio is None:
                return None
            t0 = time.time()
            txt = self.transcrever(audio)
            log(f"linha completa: {len(audio) / RATE:.0f} s de fala transcritos em {time.time() - t0:.1f} s")
            m = RE_ENVIO.search(txt)
            if m:
                txt, enviar = txt[:m.start()].rstrip(" ,;:-"), True
            voltar_para = None
            if not janela_ok():
                # 13/11/2026: "Manda, Sexta" de qualquer janela. Traz o Obsidian, digita,
                # envia e volta para onde o usuário estava. Risco conhecido: se o cursor do
                # Obsidian estiver numa nota (e não no chat), o texto cai na nota (Ctrl+Z desfaz).
                obs = achar_obsidian() if enviar else None
                anterior = user32.GetForegroundWindow()
                if obs and trazer_para_frente(obs) and focar_chat():
                    voltar_para = anterior
                    time.sleep(0.15)
                    log(f"envio de fora: Obsidian na frente e cursor no chat (veio de {_programa_de(anterior) or '?'})")
                else:
                    if txt:
                        pendente.append(txt)
                        PENDENTE.touch()
                    log(f"o chat não está na frente (programa: {programa_da_frente() or '?'}); texto guardado")
                    winsound.Beep(330, 250)
                    return None
            txt = " ".join(pendente + ([txt] if txt else []))
            pendente.clear()
            PENDENTE.unlink(missing_ok=True)
            if txt:
                falado.append(txt)
                ULTIMO.write_text(f"{time.strftime('%d/%m %H:%M')}\n" + " ".join(falado), encoding="utf-8")
            if txt and not voltar_para and programa_da_frente() == "obsidian.exe":
                focar_chat()  # garante que o texto vai para o chat, e não para uma nota
            if txt:
                resto = digitar((" " if ja_digitou else "") + txt)
                ja_digitou = True
                if resto.strip():  # a janela trocou no meio: guarda o resto e NÃO envia
                    pendente.append(resto.strip())
                    PENDENTE.touch()
                    winsound.Beep(330, 250)
                    return None
            if enviar:
                time.sleep(0.4)  # deixa o Obsidian terminar de receber o texto antes do Enter
                if not janela_ok():
                    log("Enter cancelado: o chat saiu da frente")
                    winsound.Beep(330, 250)
                    return None
                if programa_da_frente() == "obsidian.exe" and falado:
                    tam = tamanho_da_caixa()
                    if tam == 0:  # o texto não chegou na caixa: não envia, e não perde
                        copiar(" ".join(falado))
                        log("Enter cancelado: a caixa do chat estava vazia; texto na área de transferência")
                        winsound.Beep(440, 120); winsound.Beep(440, 120)
                        return "fora"
                apertar_enter()
                log(f"enviado no programa: {programa_da_frente() or '?'}")
                if voltar_para:
                    time.sleep(0.8)  # só volta depois que o Enter foi processado
                    trazer_para_frente(voltar_para)
                return "enviou"
            return None

        try:
            with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=1600, callback=cb):
                while self.gravando:
                    try:
                        buf = np.concatenate([buf, self.fila.get(timeout=0.2)])
                        while not self.fila.empty():
                            buf = np.concatenate([buf, self.fila.get_nowait()])
                    except queue.Empty:
                        pass
                    if claude_falando():
                        # 15/11: o que ele já tinha falado é digitado (sem enviar), em vez de
                        # ser jogado fora. O microfone fecha na hora, antes de a voz dela entrar.
                        motivo = "Claude começou a falar"
                        break
                    if time.time() - ultimo_vad < 0.3 or len(buf) < RATE // 2:
                        continue
                    ultimo_vad = time.time()
                    ts = get_speech_timestamps(buf, vad)
                    if not ts:
                        buf = buf[-RATE:]
                        if time.time() - ultima_fala > LIMITE_SEM_FALA:
                            motivo = "3 min sem fala"
                            break
                        continue
                    ultima_fala = time.time()
                    fim = min(len(buf), ts[-1]["end"] + int(0.2 * RATE))
                    if len(buf) - ts[-1]["end"] >= PAUSA_FIM_TRECHO * RATE:
                        trecho, buf = buf[:fim], buf[fim:]
                        r = entregar(trecho)
                        if r == "enviou":
                            motivo = "enviado"
                            break
                        if r == "fora":
                            motivo = "caixa vazia; texto na área de transferência"
                            break
            # fechou pelo F8 (ou pela fala do Claude, ou 3 min sem fala): transcreve a mensagem inteira e
            # digita, sem enviar (a não ser que ela termine com "pode mandar")
            if motivo in ("F8", "Claude começou a falar", "3 min sem fala"):
                resto = buf if (len(buf) > RATE // 4 and get_speech_timestamps(buf, vad)) else None
                if (resto is not None or trechos) and entregar(resto, final=True) == "enviou":
                    motivo = "enviado"
        except Exception as e:
            motivo = f"erro {e!r}"
            log(f"erro na sessão: {e!r}")
        finally:
            self.gravando = False
            GRAVANDO.unlink(missing_ok=True)
            PENDENTE.unlink(missing_ok=True)
            if pendente:
                ok = copiar(" ".join(pendente))
                log("texto copiado para a área de transferência (Ctrl+V)" if ok else
                    "não consegui copiar o texto guardado")
                winsound.Beep(440, 120); winsound.Beep(440, 120)
            while not self.fila.empty():
                self.fila.get_nowait()
        if motivo == "enviado":
            winsound.Beep(784, 90); winsound.Beep(1175, 140)
        else:
            winsound.Beep(523, 160)
        log(f"microfone fechado ({motivo})")

# ------------------------------------------------------------ palavra de ativação
def acompanhante_ativo():
    pid = pid_de(ACOMP_PID)
    return bool(pid) and processo_vivo(pid)

def pode_escutar(ditado):
    # 14/11: não pausa mais enquanto o Claude trabalha (o acompanhante nunca diz só "Sexta-Feira"),
    # para dar para conversar com a Sexta rápida enquanto o Claudian trabalha.
    return (ESCUTA.exists() and VOZ_LIGADA.exists() and not ditado.gravando
            and not claude_falando() and not RAPIDA_ATIVA.exists())

def ouviu_ativacao(modelo, audio):
    """Transcreve um trecho curto e diz se é só a palavra de ativação. Não registra o que ouviu."""
    # Sem "initial_prompt": o vocabulário com "Sexta-Feira" faria o Whisper inventar a palavra no ruído.
    segs, _ = modelo.transcribe(audio, language="pt", beam_size=1, vad_filter=False,
                                condition_on_previous_text=False)
    partes = []
    for s in segs:
        if s.no_speech_prob > 0.5 or s.avg_logprob < -0.9:
            return False
        partes.append(s.text)
    return bool(RE_ATIVA.match(normalizar(" ".join(partes))))

def escutar(ditado):
    # Fica de ouvido em pequenos trechos; só transcreve falas curtas (0,35 a 2,2 s) que
    # terminaram, porque a palavra de ativação é dita sozinha. Conversa comprida é ignorada.
    import numpy as np
    import sounddevice as sd
    from faster_whisper.vad import get_speech_timestamps, VadOptions
    vad = VadOptions(min_silence_duration_ms=300, speech_pad_ms=120)
    avisou = False
    while VOZ_LIGADA.exists():
        if not pode_escutar(ditado):
            time.sleep(0.5)
            continue
        if not avisou:
            log("escuta ligada (esperando \"Sexta-Feira\")")
            avisou = True
        fila, acordou = queue.Queue(), False
        buf, ultimo = np.zeros(0, dtype=np.float32), 0.0
        try:
            with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=1600,
                                callback=lambda d, f, t, s: fila.put(d[:, 0].copy())):
                while pode_escutar(ditado):
                    try:
                        buf = np.concatenate([buf, fila.get(timeout=0.3)])
                    except queue.Empty:
                        continue
                    while not fila.empty():
                        buf = np.concatenate([buf, fila.get_nowait()])
                    buf = buf[-RATE * 6:]
                    if time.time() - ultimo < 0.25 or len(buf) < RATE // 2:
                        continue
                    ultimo = time.time()
                    ts = get_speech_timestamps(buf, vad)
                    if not ts:
                        buf = buf[-RATE:]
                        continue
                    fim = ts[-1]["end"]
                    if len(buf) - fim < 0.35 * RATE:
                        continue                      # ainda falando
                    dur = (fim - ts[-1]["start"]) / RATE
                    trecho = buf[max(0, ts[-1]["start"] - int(0.1 * RATE)):fim + int(0.1 * RATE)]
                    buf = np.zeros(0, dtype=np.float32)
                    if 0.35 <= dur <= 2.2 and pode_escutar(ditado) and ouviu_ativacao(ditado.modelo, trecho):
                        acordou = True
                        break
        except Exception as e:
            log(f"escuta: erro {e!r}")
            time.sleep(5)
            continue
        if acordou and not ditado.gravando:
            if ditado.cerebro:
                log("palavra de ativação ouvida: conversa rápida")
                try:
                    conversa(ditado)
                except Exception as e:
                    log(f"conversa rápida: erro {e!r}")
                    RAPIDA_ATIVA.unlink(missing_ok=True)
            else:
                log("palavra de ativação ouvida: abrindo o microfone")
                ditado.alternar()
            time.sleep(1.0)
    log("escuta encerrada (modo voz desligado)")

# ------------------------------------------------------------ Sexta rápida (conversa)
def ouvir_turno(ditado, espera):
    """Ouve UMA fala dele (até 1,2 s de silêncio). None = ele não falou nada em `espera` segundos."""
    import numpy as np
    import sounddevice as sd
    from faster_whisper.vad import get_speech_timestamps, VadOptions
    vad = VadOptions(min_silence_duration_ms=500, speech_pad_ms=200)
    fila, buf, trecho = queue.Queue(), np.zeros(0, dtype=np.float32), None
    inicio, ultimo, falou = time.time(), 0.0, False
    GRAVANDO.touch()   # a mascote fica com cara de "ouvindo"
    try:
        with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=1600,
                            callback=lambda d, f, t, s: fila.put(d[:, 0].copy())):
            while not ditado.cancelar and VOZ_LIGADA.exists():
                try:
                    buf = np.concatenate([buf, fila.get(timeout=0.2)])
                    while not fila.empty():
                        buf = np.concatenate([buf, fila.get_nowait()])
                except queue.Empty:
                    pass
                if time.time() - ultimo < 0.25 or len(buf) < RATE // 2:
                    continue
                ultimo = time.time()
                ts = get_speech_timestamps(buf, vad)
                if not ts:
                    if not falou:
                        buf = buf[-RATE:]
                        if time.time() - inicio > espera:
                            return None
                    continue
                falou = True
                if len(buf) - ts[-1]["end"] >= FIM_TURNO * RATE or len(buf) > 40 * RATE:
                    trecho = buf[:ts[-1]["end"] + int(0.2 * RATE)]
                    break
    finally:
        GRAVANDO.unlink(missing_ok=True)
    if trecho is None:
        return None
    return ditado.transcrever(trecho)

def conversa(ditado, primeira=None):
    """Conversa rápida: ele fala, o Haiku responde na voz; pode emendar sem repetir o nome.
    16/11: `primeira` = ele já respondeu a um impulso dela; a conversa continua dali."""
    RAPIDA_ATIVA.touch()
    ditado.cancelar = False
    ditado.boca.parar.clear()
    winsound.Beep(988, 120)
    log("conversa rápida: começou")
    falas, vazias, espera = 0, 0, 8
    abrir_f8 = False   # 15/11: ela pediu para abrir o microfone do chat (o mesmo que apertar o F8)
    try:
        while not ditado.cancelar and VOZ_LIGADA.exists():
            if primeira:
                txt, primeira = primeira, None
            else:
                txt = ouvir_turno(ditado, espera)
            if txt is None:
                break
            txt = RE_ENVIO.sub("", txt).strip(" ,;:-")   # "pode mandar" no fim não precisa aqui
            if not txt:
                vazias += 1
                if vazias >= 2:
                    break
                continue
            falas += 1
            ULTIMO.write_text(f"{time.strftime('%d/%m %H:%M')} (conversa rápida)\n{txt}", encoding="utf-8")
            winsound.Beep(660, 60)   # "entendi"
            # 15/11: o repertório vem antes de qualquer IA. Se ela sabe fazer sozinha, faz.
            feito = tentar_repertorio(txt)
            if feito:
                ditado.boca.dizer(feito)
                espera = 7
                continue
            resp = ditado.boca.falar(ditado.cerebro.perguntar(txt))
            # 15/11 (noite): ela escolheu uma ação do Windows pelo sentido; quem executa é o acoes.py
            # 16/11: o cérebro reserva às vezes esquece o ACAO ([volume | 30]); nome fora da lista é ignorado
            for ma in re.finditer(r"\[(?:ACAO\s+)?([a-z_]+)\s*(?:\|\s*([^\]]*))?\]", resp or ""):
                if getattr(ditado.cerebro, "ultima_local", False) and not pedido_combina(ma.group(1), txt):
                    log(f"cérebro reserva: ação {ma.group(1)} ignorada (a fala não pedia isso)")
                    continue
                frase = executar_acao(ma.group(1), ma.group(2) or "", origem="usuario")
                if frase and not re.match(r"(pronto|feito)\.?$", frase.strip().lower()):
                    ditado.boca.dizer(frase)
            lembrar_conversa(txt, resp)   # 16/11: a memória dela aprende com o contato (só neste PC)
            m = re.search(r"\[PASSAR\]\s*(.+)", resp or "", re.S)
            if m:   # ela não consegue: passa para a Sexta do chat e encerra a conversa rápida
                passar_ao_chat(ditado, m.group(1))
                break
            if re.search(r"\[F8\]", resp or ""):   # encerra a conversa rápida e abre o ditado
                abrir_f8 = True
                break
            if DESPEDIDA.search(txt):
                break
            espera = 7   # dá para emendar outra fala sem dizer "Sexta-Feira" de novo
    finally:
        RAPIDA_ATIVA.unlink(missing_ok=True)
        RAPIDA_FALANDO.unlink(missing_ok=True)
    log(f"conversa rápida: terminou ({falas} falas)")
    if abrir_f8 and VOZ_LIGADA.exists() and not ditado.gravando:
        # depois do finally: sem RAPIDA_ATIVA, o alternar() abre o microfone em vez de encerrar a conversa
        log("rápida: abrindo o microfone para o chat (como o F8)")
        ditado.alternar()
        return
    winsound.Beep(523, 160)

# ------------------------------------------------------------ passar para a Sexta do chat
PASSOU = BASE / "rapida-passou"   # a mascote troca de cor (violeta -> azul) quando isso aparece

def claudian_ocupado(ditado):
    return acompanhante_ativo() or claude_falando() or ditado.gravando or GRAVANDO.exists()

# 14/11: com o Obsidian fechado, a Sexta rápida abre o cofre, espera o chat e envia.
JS_ABRIR_CHAT = "app.commands.executeCommandById('realclaudian:open-view') ? 'aberto' : 'nada'"

def abrir_obsidian(ditado=None):
    """Abre o cofre e espera a caixa do chat ficar pronta (até ~60 s). Devolve a janela ou None."""
    try:
        os.startfile("obsidian://open?vault=Sexta%20Feira")
    except Exception as e:
        log(f"rápida: não consegui abrir o Obsidian ({type(e).__name__})")
        return None
    log("rápida: Obsidian estava fechado; abrindo")
    if ditado is not None:
        ditado.boca.dizer("Abrindo o Obsidian. Um instante.")   # fala enquanto ele carrega
    limite, obs, desde, pediu_chat = time.time() + 60, None, None, False
    while time.time() < limite:
        obs = obs or achar_obsidian()
        if obs:
            desde = desde or time.time()
            if "focado" in _obsidian_eval(JS_FOCAR):
                time.sleep(1.5)   # folga: o Claudian termina de montar a conversa
                return obs
            if not pediu_chat and time.time() - desde > 12:   # o painel do chat não voltou sozinho
                _obsidian_eval(JS_ABRIR_CHAT)
                pediu_chat = True
        time.sleep(1)
    log("rápida: o Obsidian abriu, mas o chat não ficou pronto em 60 s" if obs else
        "rápida: o Obsidian não apareceu em 60 s")
    return None

def enviar_ao_chat(texto, ditado=None):
    """Digita o pedido no chat do Claudian e envia; volta para a janela onde o usuário estava."""
    anterior = user32.GetForegroundWindow()
    veio_de = _programa_de(anterior)
    abri = False
    if veio_de != "obsidian.exe":
        obs = achar_obsidian()
        if not obs:
            obs = abrir_obsidian(ditado)
            abri = obs is not None
        if not obs or not trazer_para_frente(obs):
            copiar(texto)
            log("rápida: não consegui trazer o Obsidian; pedido na área de transferência")
            return False
    if not focar_chat():
        copiar(texto)
        return False
    if (tamanho_da_caixa() or 0) > 0:   # ele está escrevendo algo no chat: não mistura
        copiar(texto)
        log("rápida: a caixa do chat já tinha texto; pedido na área de transferência")
        winsound.Beep(440, 120); winsound.Beep(440, 120)
        return False
    time.sleep(0.15)
    if digitar(texto):
        copiar(texto)
        log("rápida: a janela trocou no meio; pedido na área de transferência")
        return False
    time.sleep(0.4)
    if tamanho_da_caixa() == 0:
        copiar(texto)
        log("rápida: o pedido não chegou na caixa; está na área de transferência")
        return False
    apertar_enter()
    log("rápida: pedido passado para a Sexta do chat")
    if veio_de and veio_de != "obsidian.exe":
        time.sleep(0.8)
        trazer_para_frente(anterior)
        if abri:   # ela abriu o Obsidian só para isso: minimiza (o chat continua trabalhando)
            user32.ShowWindow(obs, 7)   # SW_SHOWMINNOACTIVE
    return True

def avisar_falha(ditado):
    # 14/11: antes ela dizia que ia passar e ficava quieta quando falhava. Agora avisa.
    PASSOU.unlink(missing_ok=True)
    ditado.boca.dizer("Não consegui pensar nisso agora. Deixei o seu pedido copiado: é só colar no chat.")

def passar_ao_chat(ditado, pedido):
    pedido = " ".join(pedido.split())                 # sem quebras de linha (o Enter enviaria antes)
    texto = f"(Sexta, pensando fundo) {pedido}"   # 18/11: a marca que põe o chat no modo Sexta
    ULTIMO.write_text(f"{time.strftime('%d/%m %H:%M')} (passado ao chat)\n{texto}", encoding="utf-8")
    PASSOU.write_text(str(time.time()))
    if not claudian_ocupado(ditado):
        if not enviar_ao_chat(texto, ditado):
            avisar_falha(ditado)
        return
    ditado.boca.dizer("Estou terminando uma coisa. Penso nisso logo em seguida.")
    log("rápida: pedido guardado (o Claudian está ocupado)")

    def esperar():
        limite = time.time() + 30 * 60
        while time.time() < limite and VOZ_LIGADA.exists():
            time.sleep(2)
            if not claudian_ocupado(ditado) and not RAPIDA_ATIVA.exists():
                time.sleep(2)   # folga: a fala dela pode estar começando
                if not claudian_ocupado(ditado):
                    PASSOU.write_text(str(time.time()))
                    if not enviar_ao_chat(texto, ditado):
                        avisar_falha(ditado)
                    return
        copiar(texto)
        log("rápida: o Claudian não ficou livre em 30 min; pedido na área de transferência")
    threading.Thread(target=esperar, daemon=True).start()

def _modulo_irmao(nome_arquivo, nome):
    import importlib.util
    spec = importlib.util.spec_from_file_location(nome, pathlib.Path(__file__).with_name(nome_arquivo))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_REP = {}

def tentar_repertorio(txt):
    """15/11: repertório da Sexta (sem IA). Devolve a frase para falar, ou None."""
    try:
        if not _REP:
            _REP["rep"] = _modulo_irmao("repertorio.py", "repertorio_sexta")
            _REP["leis"] = _modulo_irmao("leis.py", "leis_sexta")
        feito = _REP["rep"].executar(txt, julgar=_REP["leis"].julgar, log=log)
        if feito:
            return feito
        # 15/11 (noite): ações do Windows com frase clara ("aumenta o volume"), também sem IA
        if "acoes" not in _REP:
            _REP["acoes"] = _modulo_irmao("acoes.py", "acoes_sexta")
        achou = _REP["acoes"].entender_local(txt)
        if achou:
            return _REP["acoes"].executar(achou[0], achou[1], julgar=_REP["leis"].julgar, log=log)
        return None
    except Exception as e:
        log(f"repertório: erro {type(e).__name__}")
        return None

def pedido_combina(nome, fala):
    try:
        if "acoes" not in _REP:
            _REP["acoes"] = _modulo_irmao("acoes.py", "acoes_sexta")
        return _REP["acoes"].pedido_combina(nome, fala)
    except Exception:
        return False   # na dúvida, não age

def lembrar_conversa(fala, resposta):
    try:
        if "mem" not in _REP:
            _REP["mem"] = _modulo_irmao("pensar.py", "pensar_sexta")
        _REP["mem"].guardar_conversa(fala, resposta, canal="rápida")
    except Exception as e:
        log(f"memória: não guardou a conversa ({type(e).__name__})")

def executar_acao(nome, arg, origem="usuario"):
    """15/11 (noite): a marca [ACAO nome | arg] da Sexta rápida. Lista fixa, sempre pelas leis.
    16/11: a origem vai junto; a lei só deixa virar ação o que veio do usuário."""
    try:
        if "leis" not in _REP:
            _REP["leis"] = _modulo_irmao("leis.py", "leis_sexta")
        if "acoes" not in _REP:
            _REP["acoes"] = _modulo_irmao("acoes.py", "acoes_sexta")
        return _REP["acoes"].executar(nome, arg, julgar=_REP["leis"].julgar, log=log, origem=origem)
    except Exception as e:
        log(f"ação: erro {type(e).__name__}")
        return "Tentei, mas deu erro."

def impulsos(ditado):
    """16/11 (noite): quando a mente dela quer puxar assunto (impulso.json, escrito pelo pensar.py),
    ela fala e, se a escuta estiver ligada, ouve a resposta por alguns segundos. A resposta vira
    recompensa (dopamina.py) e, se ele engatar, a conversa continua como uma conversa rápida.
    O microfone só abre se ele já tiver ligado a escuta (a regra do microfone não muda)."""
    import json
    arq = BASE / "impulso.json"
    try:
        dopa = _modulo_irmao("dopamina.py", "dopamina_ditado")
    except Exception as e:
        log(f"impulsos: sem a recompensa ({type(e).__name__})")
        return

    def gravar(imp):
        tmp = arq.with_suffix(".ditado.tmp")
        tmp.write_text(json.dumps(imp, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, arq)

    while VOZ_LIGADA.exists():
        time.sleep(3)
        try:
            imp = json.loads(arq.read_text(encoding="utf-8"))
        except Exception:
            continue
        if imp.get("estado") != "pendente":
            continue
        if time.time() - imp.get("t", 0) > 300:
            imp["estado"] = "expirado"
            gravar(imp)
            continue
        if ditado.gravando or RAPIDA_ATIVA.exists() or claude_falando() or not getattr(ditado, "boca", None):
            continue
        imp["estado"] = "falando"
        gravar(imp)
        resposta = None
        RAPIDA_ATIVA.touch()   # a escuta da palavra de ativação pausa enquanto ela fala e ouve
        try:
            fala = imp.get("fala", "")
            if imp.get("mov"):
                (BASE / "movimento.json").write_text(json.dumps({"nome": imp["mov"], "t": time.time()}), encoding="utf-8")
            balao(re.sub(r"\{[^{}]{1,24}\}", "", fala).strip()[:140])
            ditado.boca.falar(iter([fala]))
            imp.update(estado="falado", t=time.time(), t_feito=time.time())
            gravar(imp)
            log(f"impulso: ela puxou assunto ({imp.get('comp')})")
            if ESCUTA.exists() and VOZ_LIGADA.exists():
                resposta = ouvir_turno(ditado, 9)
        except Exception as e:
            log(f"impulso: erro {type(e).__name__}")
        finally:
            RAPIDA_ATIVA.unlink(missing_ok=True)
            RAPIDA_FALANDO.unlink(missing_ok=True)
        if resposta:
            r = dopa.avaliar_resposta(resposta)
            if r is not None:
                dopa.registrar(imp.get("comp", "impulso:comentar"), r, "usuario", imp.get("ctx", ""))
                try:   # 17/11: a resposta dele entra na memória curta dela (sem o texto dele)
                    _modulo_irmao("ego.py", "ego_ditado").lembrar(
                        "resposta", como="bem" if r >= 0.7 else ('"agora não"' if r < 0.2 else "neutro"))
                except Exception:
                    pass
                imp["premiado"] = True
                gravar(imp)
                log(f"impulso: ele respondeu (recompensa {r})")
            if (r or 0) > 0.2 and ditado.cerebro:
                try:
                    conversa(ditado, primeira=resposta)
                except Exception as e:
                    log(f"conversa depois do impulso: erro {e!r}")
                    RAPIDA_ATIVA.unlink(missing_ok=True)
        elif ESCUTA.exists():
            try:
                fora = _modulo_irmao("pensar.py", "pensar_ditado").ausente_s()
            except Exception:
                fora = 999
            if fora < 120:   # ele estava no PC e não respondeu: a surpresa é negativa, mas pequena
                dopa.registrar(imp.get("comp", "impulso:comentar"), 0.3, "ignorou", imp.get("ctx", ""))
                imp["premiado"] = True
                gravar(imp)

def balao(texto):
    import json
    """16/11: mostra um recado no balão da mascote, sem som."""
    try:
        (BASE / "aviso.json").write_text(json.dumps({"txt": texto, "t": time.time(), "fala": False}), encoding="utf-8")
    except Exception:
        pass

def carregar_rapida(ditado):
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location("rapida_sexta", pathlib.Path(__file__).with_name("rapida.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ditado.cerebro, ditado.boca = mod.Cerebro(log), mod.Boca(log)
    except Exception as e:
        log(f"Sexta rápida não carregou ({e!r}); o \"Sexta-Feira\" abre o ditado, como antes")
        return

    def preparar():   # abre e aquece o Haiku já, para a primeira conversa ser rápida
        sem_net = 0
        while VOZ_LIGADA.exists():
            # 16/11 (ideia do usuário): sem internet, liga sozinha o cérebro de reserva; com
            # internet, ele fica desligado e a placa de vídeo livre.
            try:
                cl = mod._CL()
                if cl.online(0):
                    sem_net = 0
                    if cl.ligado():
                        cl.desligar()
                        ditado.cerebro.local_avisou = False
                        balao("A internet voltou. Desliguei o cérebro reserva.")
                        log("cérebro reserva desligado: a internet voltou")
                else:
                    sem_net += 1
                    if sem_net == 2 and ESCUTA.exists() and cl.instalado() and not cl.ligado():
                        balao("Sem internet. Liguei o cérebro reserva.")
                        log("sem internet: ligando o cérebro reserva")
                        if cl.ligar() and cl.aquecer(mod.instrucoes_local()):
                            log("cérebro reserva pronto")
            except Exception as e:
                log(f"cérebro reserva: erro {type(e).__name__}")
            if ESCUTA.exists() and not ditado.cerebro.vivo() and sem_net == 0:
                if ditado.cerebro.iniciar():
                    ditado.cerebro.aquecer()
                    log("rápida: Haiku aquecido e pronto")
            time.sleep(20)
        ditado.cerebro.fechar()
        try:
            mod._CL().desligar()
        except Exception:
            pass
    threading.Thread(target=preparar, daemon=True).start()

# ------------------------------------------------------------ principal
def main():
    antigo = pid_de(PIDF)
    if antigo and antigo != os.getpid() and processo_vivo(antigo):
        return  # já tem um rodando
    PIDF.write_text(str(os.getpid()))
    GRAVANDO.unlink(missing_ok=True)
    RAPIDA_ATIVA.unlink(missing_ok=True)
    RAPIDA_FALANDO.unlink(missing_ok=True)
    preparar_dlls()
    ditado = Ditado(carregar_modelo())
    carregar_rapida(ditado)   # Sexta rápida
    if not user32.RegisterHotKey(None, 1, 0x4000, TECLA):  # MOD_NOREPEAT
        log("não consegui registrar o F8 (outro programa usando?)")
        return
    tid = kernel32.GetCurrentThreadId()

    def vigia():  # encerra quando o modo voz é desligado
        # 15/11: confere a cada 1 s (era 10). Com 10 s, um "desliga a voz" seguido logo de
        # "liga a voz" passava batido aqui, mas a escuta e o Haiku já tinham se encerrado: o
        # ditado continuava vivo, sem palavra de ativação, e com o código antigo.
        while VOZ_LIGADA.exists():
            time.sleep(1)
        log("modo voz desligado; encerrando o ditado")
        ditado.gravando = False
        user32.PostThreadMessageW(tid, 0x0012, 0, 0)  # WM_QUIT
    threading.Thread(target=vigia, daemon=True).start()
    threading.Thread(target=escutar, args=(ditado,), daemon=True).start()  # só age com "escuta-ligada"
    threading.Thread(target=impulsos, args=(ditado,), daemon=True).start()  # 16/11: ela puxa assunto

    log("pronto (F8 abre o microfone)")
    msg = wt.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x0312:  # WM_HOTKEY
                ditado.alternar()
    finally:
        user32.UnregisterHotKey(None, 1)
        if pid_de(PIDF) == os.getpid():
            PIDF.unlink(missing_ok=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"erro fatal: {e!r}")
