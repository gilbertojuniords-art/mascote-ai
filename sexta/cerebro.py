# Cérebro de reserva da Sexta (sem internet). Criado em 16/11/2026.
#
# Ideia do usuário: "a Sexta sempre roda no Claude. A partir do momento que o computador fica sem
# internet, aí ela liga sozinha o segundo cérebro, que fica dentro da placa de vídeo. Informa isso.
# Mas a partir do momento que ela estiver online, ela não precisa usar o segundo cérebro, então
# pode simplesmente ficar desligado."
#
# Como funciona:
#   - online(): testa a internet (uma conexão rápida, sem mandar dado nenhum).
#   - Sem internet e com a escuta ligada, o ditado chama ligar(): abre o Ollama (servidor local,
#     só em 127.0.0.1, nada sai do PC) e carrega o modelo pequeno na placa de vídeo.
#   - A internet voltou: desligar() fecha o Ollama inteiro e a placa fica livre de novo.
#   - O Ollama NÃO começa com o Windows: só a Sexta liga, e só quando precisa.
#   - A placa tem pouca memória e o Whisper também mora nela. Se não couber, o próprio Ollama
#     põe parte do modelo no processador (fica mais lento, mas não quebra nada).
#
# Ideia do OpenJarvis (engine/multi.py): pedido nunca cai para a nuvem em silêncio. Aqui é o
# contrário e vale igual: quando ela troca de cérebro, ela avisa.

import json, os, pathlib, shutil, socket, subprocess, time, urllib.request
import sys as _sys, pathlib as _pl
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg

BASE = pathlib.Path.home() / ".sexta-voz"
PIDF = BASE / "cerebro-local.pid"
MODELO = cfg.C.get("cerebro_local") or "qwen3:4b-instruct-2507-q4_K_M"   # a versão direta (sem "pensar em voz alta")
URL = "http://127.0.0.1:11434"
_ONLINE = {"t": 0.0, "ok": True}


def online(cache_s=15):
    """True se há internet. Só abre uma conexão e fecha (não manda nada)."""
    if time.time() - _ONLINE["t"] < cache_s:
        return _ONLINE["ok"]
    ok = False
    for host in ("api.anthropic.com", "1.1.1.1"):
        try:
            socket.create_connection((host, 443), timeout=2.5).close()
            ok = True
            break
        except OSError:
            continue
    _ONLINE.update(t=time.time(), ok=ok)
    return ok


def exe():
    achado = shutil.which("ollama")
    if achado:
        return achado
    p = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    return str(p) if p.exists() else None


def instalado():
    return exe() is not None


def _get(caminho, timeout=1.5):
    with urllib.request.urlopen(URL + caminho, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def respondendo():
    try:
        _get("/api/version")
        return True
    except Exception:
        return False


def _vivo(pid):
    import ctypes
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, int(pid))
    if not h:
        return False
    code = ctypes.c_ulong()
    ok = k.GetExitCodeProcess(h, ctypes.byref(code))
    k.CloseHandle(h)
    return bool(ok) and code.value == 259


def ligado():
    """True se fomos NÓS que ligamos o Ollama e ele ainda está de pé."""
    try:
        return _vivo(PIDF.read_text().strip())
    except Exception:
        return False


def ligar(esperar_s=30):
    """Abre o servidor local (se ainda não estiver de pé). Devolve True quando ele responde."""
    if respondendo():
        return True
    e = exe()
    if not e:
        return False
    env = dict(os.environ, OLLAMA_HOST="127.0.0.1:11434", OLLAMA_KEEP_ALIVE="20m")
    BASE.mkdir(exist_ok=True)
    # 16/11: com a saída jogada no "nada" (DEVNULL) o servidor não subia. Ela vai para um arquivo,
    # que só anota os endereços chamados (nunca o texto da conversa) e recomeça a cada vez.
    saida = open(BASE / "cerebro-local.log", "w", encoding="utf-8")
    p = subprocess.Popen([e, "serve"], env=env, stdin=subprocess.DEVNULL, stdout=saida, stderr=saida,
                         creationflags=0x00000200 | 0x08000000, close_fds=True)
    saida.close()
    PIDF.write_text(str(p.pid))
    fim = time.time() + esperar_s
    while time.time() < fim:
        if respondendo():
            return True
        time.sleep(0.5)
    return False


def aquecer(sistema=None):
    """Carrega o modelo na memória já, para a primeira resposta não demorar.
    16/11: com as instruções, ele já as lê agora (fica guardado) e a 1ª resposta cai de ~20 s para ~5 s."""
    try:
        if sistema:
            corpo = {"model": MODELO, "stream": False, "think": False, "keep_alive": "20m",
                     "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": "ok"}],
                     "options": {"num_ctx": 4096, "num_predict": 1}}
            caminho = "/api/chat"
        else:
            corpo, caminho = {"model": MODELO, "prompt": "", "keep_alive": "20m"}, "/api/generate"
        req = urllib.request.Request(URL + caminho, data=json.dumps(corpo).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=180).read()
        return True
    except Exception:
        return False


def desligar():
    """Fecha o Ollama que nós abrimos (e os filhos dele). A placa de vídeo fica livre."""
    try:
        pid = PIDF.read_text().strip()
    except Exception:
        return False
    if _vivo(pid):
        subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, creationflags=0x08000000)
    PIDF.unlink(missing_ok=True)
    return True


def conversar(sistema, mensagens, max_tokens=320, temperatura=0.6):
    """Manda a conversa para o modelo local e devolve os pedaços da resposta conforme chegam.
    mensagens = [{"role": "user"|"assistant", "content": "..."}]. Nada sai do PC."""
    corpo = {"model": MODELO, "stream": True, "think": False, "keep_alive": "20m",
             "messages": [{"role": "system", "content": sistema}] + list(mensagens),
             "options": {"num_ctx": 4096, "temperature": temperatura, "num_predict": max_tokens}}
    req = urllib.request.Request(URL + "/api/chat", data=json.dumps(corpo).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    pensando = False   # alguns modelos ainda escrevem <think>...</think>: isso não é falado
    buf = ""
    with urllib.request.urlopen(req, timeout=180) as r:
        for linha in r:
            try:
                d = json.loads(linha.decode("utf-8"))
            except Exception:
                continue
            buf += (d.get("message") or {}).get("content", "")
            while True:
                if pensando:
                    i = buf.find("</think>")
                    if i < 0:
                        buf = buf[-8:]
                        break
                    buf, pensando = buf[i + 8:], False
                    continue
                i = buf.find("<think>")
                if i >= 0:
                    if i:
                        yield buf[:i]
                    buf, pensando = buf[i + 7:], True
                    continue
                corte = len(buf) - 7 if "<" in buf[-7:] else len(buf)   # pode ser o começo de "<think>"
                if corte > 0:
                    yield buf[:corte]
                    buf = buf[corte:]
                break
            if d.get("done"):
                break
    if buf and not pensando:
        yield buf


def responder(sistema, texto, max_tokens=320):
    """Atalho: uma pergunta, a resposta inteira."""
    return "".join(conversar(sistema, [{"role": "user", "content": texto}], max_tokens=max_tokens)).strip()


if __name__ == "__main__":
    import sys
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    if modo == "teste":
        print("online:", online(0), "| instalado:", instalado(), "| modelo:", MODELO)
        if ligar():
            t = time.time()
            print(responder("Você é a Sexta-Feira. Responda em português do Brasil, em uma ou duas frases.",
                            " ".join(sys.argv[2:]) or "Oi, Sexta. Tudo bem?"))
            print(f"({time.time() - t:.1f} s)")
    elif modo == "desligar":
        print("desligado" if desligar() else "não estava ligado por nós")
