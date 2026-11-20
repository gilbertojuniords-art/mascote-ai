# Ações do Windows da Sexta (repertório v2). Criado em 15/11/2026 (noite), pedido do usuário:
# "passe para ela no repertório absolutamente todos os comandos que você sabe sobre o Windows. E aí
# ela eventualmente vai decidir qual usar [...] Para evitar que ela fique passando coisas básicas".
#
# Como funciona:
#   1. Frases claras ("aumenta o volume", "pausa a música") são entendidas AQUI, sem IA nenhuma.
#   2. O resto, a Sexta rápida (Haiku) entende pelo sentido e escolhe uma ação desta lista,
#      escrevendo a marca [ACAO nome | argumento]. Quem executa é este arquivo, não o Haiku.
#   3. Toda ação passa pelas Leis da Sexta (leis.py).
#
# Segurança: é uma LISTA FIXA. Nada de comando livre de CMD/PowerShell vindo do Haiku: um erro do
# ditado ("apaga" no lugar de "abre") ou um texto de site virando ordem não pode virar comando.
# Aqui só há ações de risco "livre" (abrir, mexer em janela, som, mídia). Fechar programa, desligar o
# PC, apagar, instalar, registro, senhas e firewall NÃO estão aqui. O registro anota só o nome da ação.
#
# Teste sem fazer nada: python "acoes.py" testar "aumenta o volume" "manda o opera pro outro monitor"

import ctypes, os, re, time, unicodedata, urllib.parse
import sys as _sys, pathlib as _pl  # 16/11: com "-P" o Python não procura na pasta do arquivo; sem isto, nada abria
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg
try:   # 16/11: registro encadeado das ações (só o nome da ação, nunca o argumento)
    from seguranca import auditar as _auditar
except Exception:
    _auditar = lambda *a, **k: None
from ctypes import wintypes

user32 = ctypes.windll.user32

def norm(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9 %.:/-]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()

# ------------------------------------------------------------------ teclas
VK = {"vol_mais": 0xAF, "vol_menos": 0xAE, "mudo": 0xAD, "play": 0xB3, "proxima": 0xB0,
      "anterior": 0xB1, "parar": 0xB2, "win": 0x5B, "shift": 0x10}

def _tecla(*vks):
    for v in vks:
        user32.keybd_event(v, 0, 0, 0)
    for v in reversed(vks):
        user32.keybd_event(v, 0, 2, 0)
    time.sleep(0.03)

# ------------------------------------------------------------------ janelas e monitores
class _RECT(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]

class _MONINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", _RECT), ("rcWork", _RECT), ("dwFlags", wintypes.DWORD)]

def monitores():
    """[(esquerda, topo, largura, altura, principal)], o principal primeiro, depois da esquerda para a direita."""
    out = []
    CB = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(_RECT), wintypes.LPARAM)
    def cb(h, hdc, r, lp):
        mi = _MONINFO(); mi.cbSize = ctypes.sizeof(_MONINFO)
        user32.GetMonitorInfoW(h, ctypes.byref(mi))
        w = mi.rcWork
        out.append((w.l, w.t, w.r - w.l, w.b - w.t, bool(mi.dwFlags & 1), h))
        return 1
    user32.EnumDisplayMonitors(None, None, CB(cb), 0)
    out.sort(key=lambda m: (not m[4], m[0]))
    return out

def _exe_da_janela(h):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    k = ctypes.windll.kernel32
    hp = k.OpenProcess(0x1000, False, pid.value)
    if not hp:
        return ""
    buf = ctypes.create_unicode_buffer(260); n = wintypes.DWORD(260)
    k.QueryFullProcessImageNameW(hp, 0, buf, ctypes.byref(n))
    k.CloseHandle(hp)
    return os.path.splitext(os.path.basename(buf.value))[0].lower()

def _janelas():
    """Janelas visíveis de verdade: [(handle, exe, título)]. O título fica só na memória, nunca no registro."""
    out = []
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(h, lp):
        if user32.IsWindowVisible(h) and user32.GetWindowTextLengthW(h) > 0 and not user32.GetWindow(h, 4):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(h, buf, 256)
            exe = _exe_da_janela(h)
            if exe not in ("pythonw", "python", "textinputhost", "applicationframehost", "shellexperiencehost"):
                out.append((h, exe, buf.value))
        return True
    user32.EnumWindows(CB(cb), 0)
    return out

APELIDO_EXE = {"navegador": "opera", "chrome": "chrome", "google chrome": "chrome", "edge": "msedge",
               "explorador": "explorer", "explorador de arquivos": "explorer", "arquivos": "explorer",
               "obsidian": "obsidian", "cofre": "obsidian", "discord": "discord", "spotify": "spotify",
               "word": "winword", "excel": "excel", "powerpoint": "powerpnt", "bloco de notas": "notepad",
               "steam": "steamwebhelper", "whatsapp": "whatsapp", "capcut": "capcut", "vscode": "code",
               "vs code": "code", "visual studio code": "code"}

def achar_janela(alvo):
    """'opera', 'discord', 'esta janela'... Devolve o handle ou None."""
    a = norm(alvo)
    a = re.sub(r"^(?:a |o |do |da )?(?:janela|tela|programa|aplicativo|app)\s*(?:do |da |de )?", "", a).strip()
    if not a or a in ("esta", "essa", "atual", "da frente", "esta janela", "essa janela"):
        return user32.GetForegroundWindow()
    exe = APELIDO_EXE.get(a, a.split()[0])
    js = _janelas()
    for h, e, _ in js:
        if e == exe or e.startswith(exe):
            return h
    for h, e, t in js:   # pelo título (ex.: "youtube"), só na memória
        if a in norm(t):
            return h
    return None

def _mover(h, mon, maximizar=True):
    x, y, w, hh, _, _ = mon
    user32.ShowWindow(h, 9)   # restaura
    user32.SetWindowPos(h, None, x + 40, y + 40, int(w * 0.8), int(hh * 0.8), 0x0040)
    time.sleep(0.2)
    if maximizar:
        user32.ShowWindow(h, 3)
    user32.SetForegroundWindow(h)

def _monitor_da_janela(h, mons):
    m = user32.MonitorFromWindow(h, 2)
    for i, mon in enumerate(mons):
        if mon[5] == m:
            return i
    return 0

# ------------------------------------------------------------------ as ações
# Cada uma devolve a frase curta que ela fala. Erros viram frase, nunca exceção para fora.

def a_abrir(arg):
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location("rep", pathlib.Path(__file__).with_name("repertorio.py"))
    rep = importlib.util.module_from_spec(spec); spec.loader.exec_module(rep)
    r = rep.executar("abre " + arg)
    return r or f"Não achei {arg} no meu repertório, {cfg.NOME}."

def a_mover_monitor(arg):
    alvo, _, qual = (arg or "").partition("|")
    h = achar_janela(alvo)
    if not h:
        return f"Não achei essa janela aberta, {cfg.NOME}."
    mons = monitores()
    if len(mons) < 2:
        return "Só estou vendo um monitor ligado."
    q = norm(qual)
    if re.search(r"\b(1|um|primeiro|principal)\b", q):
        i = 0
    elif re.search(r"\b(2|dois|segundo)\b", q):
        i = 1
    elif re.search(r"\b(3|tres|terceiro)\b", q) and len(mons) > 2:
        i = 2
    else:   # "o outro monitor": o próximo
        i = (_monitor_da_janela(h, mons) + 1) % len(mons)
    _mover(h, mons[i])
    return "Pronto, mandei para o outro monitor." if not q else "Pronto."

def _janela_cmd(arg, cmd, frase):
    h = achar_janela(arg)
    if not h:
        return f"Não achei essa janela aberta, {cfg.NOME}."
    user32.ShowWindow(h, cmd)
    if cmd in (3, 9):
        user32.SetForegroundWindow(h)
    return frase

def a_maximizar(arg):  return _janela_cmd(arg, 3, "Maximizei.")
def a_minimizar(arg):  return _janela_cmd(arg, 6, "Minimizei.")
def a_restaurar(arg):  return _janela_cmd(arg, 9, "Pronto.")
def a_trazer(arg):     return _janela_cmd(arg, 9, "Está na frente.")

def a_lado(arg):
    alvo, _, lado = (arg or "").partition("|")
    h = achar_janela(alvo)
    if not h:
        return f"Não achei essa janela aberta, {cfg.NOME}."
    mons = monitores()
    x, y, w, hh, _, _ = mons[_monitor_da_janela(h, mons)]
    user32.ShowWindow(h, 9)
    esq = "esq" in norm(lado)
    user32.SetWindowPos(h, None, x if esq else x + w // 2, y, w // 2, hh, 0x0040)
    user32.SetForegroundWindow(h)
    return "Coloquei na metade " + ("esquerda." if esq else "direita.")

def a_area_de_trabalho(arg):
    _tecla(VK["win"], ord("D"))
    return "Mostrando a área de trabalho."

def a_volume(arg):
    a = norm(arg)
    m = re.search(r"(\d{1,3})", a)
    if m:
        alvo = max(0, min(100, int(m.group(1))))
        for _ in range(50):
            _tecla(VK["vol_menos"])
        for _ in range(alvo // 2):
            _tecla(VK["vol_mais"])
        return f"Volume em {alvo} por cento."
    if re.search(r"mud|silenc|desmut|tira o mudo", a):
        _tecla(VK["mudo"])
        return "Pronto."
    passos = 5 if re.search(r"pouco|pouquinho", a) else 10
    if re.search(r"baix|diminu|menos|abaix", a):
        for _ in range(passos):
            _tecla(VK["vol_menos"])
        return "Baixei."
    if not re.search(r"aument|sobe|subi|mais|alto", a):   # sem direção clara: pergunta, não chuta
        return f"Aumento ou baixo, {cfg.NOME}?"
    for _ in range(passos):
        _tecla(VK["vol_mais"])
    return "Aumentei."

def a_midia(arg):
    a = norm(arg)
    if re.search(r"proxim|pula|avanc", a):
        _tecla(VK["proxima"]); return "Próxima."
    if re.search(r"anterior|volta", a):
        _tecla(VK["anterior"]); return "Voltei uma."
    _tecla(VK["play"])
    return "Pronto."

def a_captura(arg):
    _tecla(VK["win"], VK["shift"], ord("S"))
    return "Pode recortar a tela."

def a_bloquear(arg):
    user32.LockWorkStation()
    return "Tela bloqueada."

CONFIG = {"bluetooth": "bluetooth", "wifi": "network-wifi", "wi-fi": "network-wifi", "rede": "network",
          "internet": "network", "som": "sound", "audio": "sound", "microfone": "sound", "tela": "display",
          "monitor": "display", "resolucao": "display", "atualizacoes": "windowsupdate",
          "windows update": "windowsupdate", "aplicativos": "appsfeatures", "programas": "appsfeatures",
          "personalizacao": "personalization", "papel de parede": "personalization-background",
          "notificacoes": "notifications", "energia": "powersleep", "bateria": "batterysaver",
          "impressora": "printers", "mouse": "mousetouchpad", "teclado": "typing", "data": "dateandtime",
          "hora": "dateandtime", "armazenamento": "storagesense", "disco": "storagesense"}

def a_configuracoes(arg):
    a = norm(arg)
    pagina = next((v for k, v in CONFIG.items() if k in a), "")
    os.startfile("ms-settings:" + pagina)
    return "Abrindo as configurações."

SITES = {"limite": "https://claude.ai/settings/usage", "uso do claude": "https://claude.ai/settings/usage",
         "youtube": "https://www.youtube.com", "gmail": "https://mail.google.com", "e-mail": "https://mail.google.com",
         "google": "https://www.google.com", "drive": "https://drive.google.com", "github": "https://github.com",
         "chatgpt": "https://chatgpt.com", "claude": "https://claude.ai", "whatsapp": "https://web.whatsapp.com",
         "netflix": "https://www.netflix.com", "mapas": "https://maps.google.com", "tradutor": "https://translate.google.com"}

def a_site(arg):
    a = norm(arg)
    # só endereço simples (19/11: com busca no fim, ex. netflix.com/search?q=phantom). Vem antes da
    # lista de sites, senão "netflix.com/search?q=..." abriria só a página inicial.
    end = re.sub(r"^https?://", "", (arg or "").strip().lower())   # o norm tira o ? e o =
    if re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+(/[a-z0-9._/-]*)?(\?[a-z0-9._=&%+-]*)?", end):
        os.startfile("https://" + end)
        return "Abrindo o site."
    for k, url in SITES.items():
        if k in a:
            os.startfile(url)
            return "Abrindo a página do limite." if k in ("limite", "uso do claude") else f"Abrindo o {k}."
    return f"Não entendi o endereço, {cfg.NOME}."

def a_pesquisar(arg):
    q = (arg or "").strip()
    if not q:
        return f"Pesquisar o quê, {cfg.NOME}?"
    os.startfile("https://www.google.com/search?q=" + urllib.parse.quote(q))
    return "Pesquisando."

def a_youtube(arg):
    q = (arg or "").strip()
    os.startfile("https://www.youtube.com/results?search_query=" + urllib.parse.quote(q) if q else "https://www.youtube.com")
    return "Abrindo no YouTube."

# nome: (função, o que o Haiku lê)
def a_ver(arg):
    """17/11: a visão, jeito 2 (visao.py olhar). Roda em outro processo: a foto precisa do PySide6."""
    import subprocess
    exe = _sys.executable.replace("pythonw.exe", "python.exe")
    r = subprocess.run([exe, "-X", "utf8", str(_pl.Path(__file__).with_name("visao.py")), "olhar"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=120,
                       creationflags=0x08000000)
    frase = re.sub(r"\{[^{}]{1,24}\}", "", (r.stdout or "").strip()).strip()
    return frase or "Não consegui ver a tela agora."

ACOES = {
    "abrir":          (a_abrir, "abrir pasta ou programa do repertório (arg: o nome, ex. discord, downloads)"),
    "mover_monitor":  (a_mover_monitor, "mandar uma janela para outro monitor (arg: programa | qual monitor, ex. opera | segundo; sem monitor = o outro)"),
    "maximizar":      (a_maximizar, "maximizar uma janela (arg: programa, ou vazio para a janela da frente)"),
    "minimizar":      (a_minimizar, "minimizar uma janela (arg: programa, ou vazio)"),
    "restaurar":      (a_restaurar, "tirar uma janela do maximizado (arg: programa)"),
    "trazer":         (a_trazer, "trazer uma janela para a frente (arg: programa)"),
    "lado":           (a_lado, "pôr uma janela na metade da tela (arg: programa | esquerda ou direita)"),
    "area_de_trabalho": (a_area_de_trabalho, "minimizar tudo e mostrar a área de trabalho"),
    "volume":         (a_volume, "volume do PC (arg: SEMPRE com a direção: aumentar, baixar, aumentar um pouco, baixar um pouco, mudo, ou um número de 0 a 100)"),
    "midia":          (a_midia, "música ou vídeo (arg: pausar, tocar, próxima, anterior)"),
    "captura":        (a_captura, "recortar ou tirar print da tela"),
    "bloquear":       (a_bloquear, "bloquear o PC"),
    "configuracoes":  (a_configuracoes, "abrir uma página das configurações do Windows (arg: bluetooth, wifi, som, tela, atualizações, aplicativos, energia, impressora...)"),
    "site":           (a_site, "abrir um site (arg: youtube, gmail, drive, github, whatsapp, mapas, limite do claude (a página de uso/limite)... ou um endereço)"),
    "pesquisar":      (a_pesquisar, f"pesquisar no Google (arg: o que pesquisar, com as palavras do {cfg.NOME})"),
    "youtube":        (a_youtube, "procurar um vídeo no YouTube (arg: o que procurar)"),
    "ver":            (a_ver, "olhar a tela dele agora e comentar o que você vê (só quando ele PEDIR: 'olha minha tela', 'o que você está vendo')"),
}

def lista_para_haiku():
    return "; ".join(f"{n} ({d})" for n, (_, d) in ACOES.items())

def executar(nome, arg="", julgar=None, log=None, origem="usuario"):
    # 16/11: origem = de onde veio o pedido (seguranca.py). Só "usuario" vira ação; a lei confere.
    nome = (nome or "").strip().lower()
    if nome not in ACOES:
        return None
    if julgar:
        ok, lei, motivo = julgar({"tipo": "acao", "risco": "livre", "origem": origem})
        if not ok:
            _auditar("ação recusada", acao=nome, lei=lei)
            return f"Agora não posso, {cfg.NOME}. {motivo.capitalize()}."
    try:
        frase = ACOES[nome][0]((arg or "").strip())
        if log:
            log(f"ação do Windows: {nome} (sem IA)")
        _auditar("ação feita", acao=nome)
        return frase
    except Exception as e:
        if log:
            log(f"ação do Windows: {nome} falhou ({type(e).__name__})")
        return "Tentei, mas o Windows não deixou."

# ------------------------------------------------------------------ 16/11: a trava do cérebro reserva
# O modelo pequeno (sem internet) às vezes pendura uma ação numa resposta que não pedia nada.
# Por isso, quando quem escolheu a ação foi ele, ela só acontece se as PALAVRAS do usuário pedirem
# aquilo. (O Haiku não passa por esta trava: ele erra muito menos e a lei já confere a origem.)
PISTAS = {
    "abrir": r"\b(abr[ea]|abrir|abre)\b", "mover_monitor": r"\b(monitor|tela)\b",
    "maximizar": r"\bmaximiz", "minimizar": r"\bminimiz", "restaurar": r"\b(restaur|desmaximiz)",
    "trazer": r"\b(traz|trazer|frente)\b", "lado": r"\b(lado|metade|esquerda|direita)\b",
    "area_de_trabalho": r"\b(area de trabalho|minimiza tudo|limpa a tela)\b",
    "volume": r"\b(volume|som|mudo|muta|silencia|desmuta)\b",
    "midia": r"\b(musica|video|pausa|pausar|play|toca|tocar|proxima|anterior|faixa|continua)\b",
    "captura": r"\b(print|captura|recort)", "bloquear": r"\b(bloque|trava)",
    "configuracoes": r"\b(configurac|bluetooth|wi ?fi|impressora)", "site": r"\b(site|abre|abrir|entra)\b",
    "pesquisar": r"\b(pesquis|procur|busc|google)", "youtube": r"\byoutube\b",
    "ver": r"\b(olha|olhe|olhar|olhada|ve|veja|vendo|enxerga)\b",
}

def pedido_combina(nome, fala):
    """True se as palavras do usuário pedem a ação `nome` (trava do cérebro reserva)."""
    padrao = PISTAS.get((nome or "").strip().lower())
    return bool(padrao and re.search(padrao, norm(fala)))

# ------------------------------------------------------------------ frases claras, sem IA
LOCAL = [
    (r"^(?:aumenta|sobe|aumentar|subir)(?: (?:um pouco|um pouquinho))? (?:o )?(?:volume|som)(?: (?:um pouco|um pouquinho))?$", "volume", lambda m, t: "aumentar " + t),
    (r"^(?:abaixa|baixa|diminui|abaixar|baixar|diminuir)(?: (?:um pouco|um pouquinho))? (?:o )?(?:volume|som)(?: (?:um pouco|um pouquinho))?$", "volume", lambda m, t: "baixar " + t),
    (r"^(?:volume|som) (?:em|no|pra|para) (\d{1,3})(?: por cento| %)?$", "volume", lambda m, t: m.group(1)),
    (r"^(?:muta|silencia|tira o som|desmuta|tira o mudo|mudo)$", "volume", lambda m, t: "mudo"),
    (r"^(?:pausa|pausar|despausa|continua|da play|play|solta)(?: (?:a |o )?(?:musica|video|som))?$", "midia", lambda m, t: "play"),
    (r"^(?:proxima|pula|passa)(?: (?:a )?(?:musica|faixa))?$", "midia", lambda m, t: "proxima"),
    (r"^(?:volta|musica anterior|anterior)(?: (?:a )?(?:musica|faixa))?$", "midia", lambda m, t: "anterior"),
    (r"^(?:minimiza tudo|mostra a area de trabalho|limpa a tela)$", "area_de_trabalho", lambda m, t: ""),
    (r"^(?:bloqueia|trava) (?:o pc|o computador|a tela)$", "bloquear", lambda m, t: ""),
    (r"^(?:tira (?:um )?print|captura (?:de )?tela|recorta a tela|print da tela)$", "captura", lambda m, t: ""),
    (r"^(?:manda|joga|passa|coloca|bota|move|leva) (?:o |a )?(.+?) (?:pro|para o|pra|no|ao) (?:outro|segundo|primeiro|outra) (?:monitor|tela)$",
     "mover_monitor", lambda m, t: m.group(1) + " | " + ("primeiro" if "primeiro" in t else ("segundo" if "segundo" in t else ""))),
    (r"^maximiza (?:o |a )?(.+)$", "maximizar", lambda m, t: m.group(1)),
    (r"^minimiza (?:o |a )?(.+)$", "minimizar", lambda m, t: m.group(1)),
    (r"^(?:pesquisa|procura|busca|pesquise) (?:no google )?(?:por )?(.+?)(?: no google)?$", "pesquisar", lambda m, t: m.group(1)),
    # 17/11: a visão, jeito 2
    (r"^(?:olha|olhe|ve|veja|da uma olhada|de uma olhada)(?: (?:na|a|em|para|pra))? (?:minha |a |essa |esta )?tela(?: (?:aqui|ai))?$", "ver", lambda m, t: ""),
    (r"^(?:o que (?:voce )?(?:esta|ta) vendo|o que voce ve|da uma olhada aqui|de uma olhada aqui|olha isso aqui|olha isso)$", "ver", lambda m, t: ""),
]

def entender_local(fala):
    t = norm(fala)
    t = re.sub(r"^(?:ei )?sexta(?:[- ]?feira)?\s+", "", t.replace(",", " ")).strip()
    t = re.sub(r"\s+(?:pra mim|por favor|ai)$", "", t).strip(" .")
    if len(t.split()) > 12:
        return None
    for padrao, nome, arg in LOCAL:
        m = re.match(padrao, t)
        if m:
            return nome, arg(m, t)
    return None

if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["testar"]:
        for f in sys.argv[2:]:
            print(f"{f!r:50} -> {entender_local(f)}")
    elif sys.argv[1:2] == ["monitores"]:
        print([m[:5] for m in monitores()])
