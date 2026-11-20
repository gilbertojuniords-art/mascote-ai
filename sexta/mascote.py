# Mascote da Sexta-Feira. Criado em 13/11/2026, ideia e referências do usuário.
# Versão 2 (Qt): fundo 100% transparente (só o robô aparece), não rouba o foco das
# outras janelas e tem "vontade própria": passeia pela tela, segue o mouse com os
# olhos, cochila quando nada acontece e acorda feliz.
#
# Expressões = estados da Sexta-Feira (lidos de %USERPROFILE%\.sexta-voz\):
#   espera · ouvindo · guardando (âmbar) · pensando · trabalhando (legenda) · falando
#   (+ cochilando e acordando, que são dela mesma)
# Mouse: arrastar = mudar de lugar · duplo clique = microfone (F8) · botão direito = menu.
# "Aprende" de um jeito simples: lembra onde o usuário costuma colocá-la e passeia
# mais por esses lugares. Memória em mascote.json. Nada sai do PC.

import ctypes, json, math, os, pathlib, random, sys, time
import sys as _sys, pathlib as _pl  # 16/11: com "-P" o Python não procura na pasta do arquivo; sem isto, nada abria
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg
try:   # 16/11 (OpenJarvis): o registro nunca guarda CPF, telefone, cartão, chave ou senha
    from seguranca import mascarar as _mascarar
except Exception:
    _mascarar = lambda s: s

try:   # 16/11: os movimentos que ela aprende (dados, não código) e a recompensa
    import movimentos as _movs
    import dopamina as _dopa
except Exception:
    _movs = _dopa = None
try:   # 17/11: a aparência que ela mesma escolhe (dado, não código)
    import aparencia as _apar
except Exception:
    _apar = None
try:   # 17/11: a memória curta (ego.py)
    import ego as _ego
except Exception:
    _ego = None

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import (QColor, QCursor, QFont, QGuiApplication, QLinearGradient, QPainter,
                           QPainterPath, QPen, QRadialGradient, QBrush, QPolygonF)
from PySide6.QtWidgets import QApplication, QMenu, QWidget

BASE = pathlib.Path.home() / ".sexta-voz"
BASE.mkdir(exist_ok=True)
FLAG = BASE / "ligada"
MEM = BASE / "mascote.json"
FECHADO = BASE / "mascote-fechado"
PIDF = BASE / "mascote.pid"
LOG = BASE / "log.txt"

W, H = 230, 250            # janela (transparente)
ESC = 0.78                 # escala do desenho (feito numa grade de 200 x 212)
OX, OY = (W - 200 * ESC) / 2, H - 212 * ESC - 2

# Profundidade (14/11/2026, ideia do usuário): ela chega perto da tela (fica maior) ou vai
# para o fundo (fica menor e mais apagadinha). A janela tem o tamanho máximo e ela é desenhada
# em escala dentro dela, com os PÉS sempre no mesmo ponto (o fundo da janela, no meio). Por isso
# a posição dela é guardada pelos pés, e não pelo canto da janela.
#   W x H = a "caixa" dela em tamanho normal (escala 1) · WM x HM = a janela de verdade
S_MIN, S_MAX = 0.62, 1.40
WM, HM = int(W * S_MAX) + 4, int(H * S_MAX) + 4
PROF_FALA = {"animada": 1.22, "feliz": 1.15, "neutra": 1.12, "pensativa": 1.06, "preocupada": 1.10}

# Profundidade v2 (16/11/2026, pedido do usuário: "um pequeno quadrado na tela até poder tomar a tela
# inteira"). A janela agora muda de tamanho junto com ela (antes tinha tamanho fixo, por isso o teto
# era 1,40). WM x HM continua sendo só a convenção da posição: os pés ficam em (px + WM/2, py + HM).
#   No dia a dia ela continua entre S_MIN e S_MAX. Os níveis grandes só vêm quando alguém pede
#   (menu, roda do mouse com Ctrl, demonstração ou o arquivo profundidade.json).
S_PISO = 0.30              # o menor tamanho possível (a "janelinha")
MARGEM = 14                # folga em volta dela na janela (braços para cima, balão)
NIVEIS = [                 # (nome, escala, legenda); "tela" é calculada pelo tamanho do monitor
    ("janelinha", 0.34, "Na minha janelinha"),
    ("fundo", 0.62, "Lá no fundo"),
    ("normal", 1.00, "Aqui"),
    ("perto", 1.40, "Pertinho"),
    ("close", 2.10, "Bem de perto"),
    ("tela", None, "Tela inteira"),
]
NIVEL_ESC = {n: e for n, e, _ in NIVEIS}
PIP_INI, PIP_FIM = 0.50, 0.38   # abaixo de 0,50 aparece o quadradinho; em 0,38 ele está inteiro
IMERSAO_INI = 1.55              # acima disso a tela vai escurecendo em volta dela
DEMO_PROF = [("janelinha", 3.2), ("fundo", 2.6), ("normal", 2.6), ("perto", 2.6),
             ("close", 3.0), ("tela", 4.2), ("close", 1.6), ("normal", 2.4)]

CIANO = QColor("#7ff3ff")
AZUL = QColor("#a77bff")   # 17/11: a cor de origem dela é o violeta (pedido do usuário); o nome AZUL ficou por história
AMBAR = QColor("#ffb020")
# 14/11: violeta = Sexta rápida (o Haiku); azul/ciano = Sexta do chat (o Opus no Claudian)
VIOLETA = QColor("#a77bff")
VIOLETA_LUZ = QColor("#c9a6ff")
BRANCO_LUZ = QColor("#ffffff")   # 17/11: na Sexta rápida as cores dela só clareiam (antes viravam violeta)
BRILHO = QColor("#c9a6ff")   # 17/11: antena e reator (a aparência dela pode trocar estas três cores)
AP = {"cabeca": 1.0, "olhos": 1.0, "antena": 1.0, "bracos": 1.0, "brilho": 1.0,
      "formato_olhos": "ovais", "acessorio": "nenhum",
      "cor_corpo": "#ffffff", "cor_visor": "#1b2a55", "esconder": [], "camadas": []}   # 17/11: sem limites, só o núcleo

def misturar(c1, c2, k):
    k = max(0.0, min(1.0, k))
    return QColor(int(c1.red() + (c2.red() - c1.red()) * k), int(c1.green() + (c2.green() - c1.green()) * k),
                  int(c1.blue() + (c2.blue() - c1.blue()) * k), int(c1.alpha() + (c2.alpha() - c1.alpha()) * k))
LEGENDA_PADRAO = {"ouvindo": "Ouvindo…", "guardando": "Guardando — volte ao chat",
                  "pensando": "Pensando…", "trabalhando": "Trabalhando…"}

# v3, passo 1 (13/11/2026): gestos ao falar. Cada gesto = (braço esq., braço dir.,
# inclinação da cabeça, subida do corpo). Ângulo positivo no braço esquerdo e negativo
# no direito = braço para fora. Acima de ~110 a mão some atrás da cabeça (braços curtos).
GESTOS = {
    "repouso":     (25, -25, 0, 0),
    "fala":        (36, -36, 0, 0),
    "abre":        (88, -88, 0, 0),     # mãos abertas, "veja bem"
    "explica_dir": (28, -104, 6, 0),    # explica com a mão direita
    "explica_esq": (104, -28, -6, 0),   # explica com a mão esquerda
    "ombros":      (50, -50, 4, -8),    # dá de ombros
    "inclina":     (32, -32, 11, 0),    # inclina a cabeça (o lado é sorteado)
    "conta":       (28, -98, 5, 0),     # conta nos dedos (aparecem 1, 2, 3 luzinhas)
    # Bloco 2: gestos que só acontecem quando o roteiro pede
    "sim":         (34, -34, 0, 0),     # faz que sim com a cabeça (duas vezes)
    "nao":         (58, -58, 0, 0),     # faz que não: o rosto vai de um lado para o outro
    "pisca":       (30, -72, 7, 0),     # piscadinha de um olho só (ironia)
    # 15/11 (ideias do usuário com o Gemini): comemora = braços para cima e um pulinho
    "comemora":    (128, -128, 0, -10),
}
PESOS_FALA = {"fala": 2, "abre": 2, "explica_dir": 2, "explica_esq": 2,
              "ombros": 1, "inclina": 2, "conta": 1}

# Poses de trabalho (14/11/2026, pedido do usuário): uma por atividade, com um objeto na mão.
#   (braço esq., braço dir., cabeça, subida) — mesmo formato dos GESTOS
POSES = {
    "editar": (16, -16, 3, 0),     # digitando no notebook
    "ler":    (25, -104, 5, 0),    # lupa na mão direita, perto do rosto
    "rodar":  (62, -30, -4, 0),    # prancheta na mão esquerda, marcando os testes
    "web":    (25, -92, -5, 0),    # globo girando acima da mão direita
    # 15/11 (o usuário reparou): a mão no queixo era desenhada A MAIS, com os dois braços
    # abaixados (três mãos). Agora o braço direito dobra para cima, por trás do corpo, e a mão
    # do queixo só aparece quando ele chega lá.
    "pensar": (25, 140, 7, 0),     # cabeça inclinada, braço direito dobrado, mão no queixo
}

# Bloco 2 (14/11/2026): emoção da resposta. Vem de uma marca no roteiro ({feliz}, {preocupada}...)
# e muda o rosto, o tamanho dos gestos, o ritmo e os gestos que ela prefere fazer sozinha.
#   amp = tamanho dos gestos · periodo = balanço do corpo (s) · batida = ritmo do braço · cab = cabeça
EMOCAO = {
    "neutra":     {"amp": 1.00, "periodo": 3.2, "batida": 5.5, "cab": 0, "pesos": {}},
    "feliz":      {"amp": 1.05, "periodo": 2.8, "batida": 6.0, "cab": 0, "pesos": {"abre": 3}},
    "animada":    {"amp": 1.18, "periodo": 2.0, "batida": 7.5, "cab": 0, "pesos": {"abre": 4, "explica_dir": 3, "explica_esq": 3, "fala": 1}},
    "pensativa":  {"amp": 0.85, "periodo": 4.0, "batida": 4.0, "cab": 5, "pesos": {"inclina": 4, "abre": 1, "ombros": 2}},
    "preocupada": {"amp": 0.72, "periodo": 4.4, "batida": 3.5, "cab": -3, "pesos": {"fala": 4, "abre": 1, "ombros": 0, "conta": 0}},
}

# 15/11 (pedido do usuário: "mostre todos os comportamentos novos e narre"): demonstração.
# O roteiro traz {mostra X}; enquanto a voz narra, ela faz o comportamento X.
#   nome: (estado que ela assume durante a demonstração, duração em s, legenda)
DEMOS = {
    "chamada":    ("ouvindo", 1.8, "Você me chamou"),
    "antena":     (None, 0.8, ""),
    "haiku":      ("pensando", 3.6, "Haiku pensando"),
    "opus":       ("pensando", 3.6, "Modelo grande pensando"),
    "trabalho":   ("trabalhando", 3.6, "Trabalhando"),
    "arremesso":  ("espera", 1.8, "Pensando com calma…"),
    "olha":       ("espera", 2.6, "Olhando para fora"),
    "painel":     ("espera", 3.4, "Conferindo o sistema"),
    "espreguica": ("espera", 2.2, "Espreguiçando"),
    "boceja":     ("espera", 1.9, "Bocejo"),
    "passeio":    ("espera", 4.6, "Passeando"),
    "esforco":    ("espera", 3.6, "PC pesado"),
}
DEMO_TEDIO = {"olha": "olha_longe", "painel": "holo", "espreguica": "espreguica", "boceja": "boceja"}

def carregar_casa():
    # Casa da Sexta (protótipo, 14/11/2026): o servidor local da página do visor.
    import importlib.util
    try:
        arq = pathlib.Path(__file__).with_name("casa.py")
        spec = importlib.util.spec_from_file_location("casa_sexta", arq)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        casa = mod.Casa(log)
        return casa if casa.iniciar() else None
    except Exception as e:
        log(f"casa não abriu: {e!r}")
        return None

def carregar_central(m):
    # 16/11: central de comando na tela 1 (central.py): apps e notas só para leitura.
    import importlib.util
    try:
        arq = pathlib.Path(__file__).with_name("central.py")
        spec = importlib.util.spec_from_file_location("central_sexta", arq)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.CentralComando(m.fechar_central, m)
    except Exception as e:
        log(f"central de comando não abriu: {e!r}")
        return None

def carregar_descanso(m):
    # 16/11: tela de descanso (descanso.py), o holograma dela com a hora, os avisos e os prazos.
    import importlib.util
    try:
        arq = pathlib.Path(__file__).with_name("descanso.py")
        spec = importlib.util.spec_from_file_location("descanso_sexta", arq)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.TelaDescanso(m.fechar_descanso, m.ponto_peito, m)   # 16/11: m = ela (barra, plataforma)
    except Exception as e:
        log(f"tela de descanso não abriu: {e!r}")
        return None

def log(msg):
    try:
        msg = _mascarar(str(msg))
        import datetime
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} mascote: {msg}\n")
    except Exception:
        pass

def vivo(arq):
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

class _FT(ctypes.Structure):
    _fields_ = [("lo", ctypes.c_ulong), ("hi", ctypes.c_ulong)]

def tempos_cpu():
    """15/11: tempo ocioso e total do processador (para ela sentir o PC pesado)."""
    i, k, u = _FT(), _FT(), _FT()
    ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u))
    v = lambda f: (f.hi << 32) | f.lo
    return v(i), v(k) + v(u)   # o tempo do kernel já inclui o ocioso

def ler_json(arq, maximo_s):
    try:
        d = json.loads(arq.read_text(encoding="utf-8"))
        return d if time.time() - d.get("t", 0) < maximo_s else None
    except Exception:
        return None

def satisfazer(nome):
    """15/11 (noite): conta ao vontades.py que uma vontade foi satisfeita (olhou o painel, cochilou)."""
    arq = BASE / "satisfeito.json"
    try:
        d = json.loads(arq.read_text(encoding="utf-8"))
    except Exception:
        d = {}
    d[nome] = time.time()
    try:
        arq.write_text(json.dumps(d), encoding="utf-8")
    except Exception:
        pass

class _RECT(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]

class _MONINFO(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("mon", _RECT), ("work", _RECT), ("flags", ctypes.c_ulong)]

def app_em_tela_cheia(meu_hwnd):
    """16/11: tem um programa em tela cheia (filme, série, jogo) no MESMO monitor que ela?
    Compara só o retângulo da janela da frente com o do monitor. Não lê título nem nome de nada."""
    try:
        u = ctypes.windll.user32
        u.GetForegroundWindow.restype = ctypes.c_void_p
        u.MonitorFromWindow.restype = ctypes.c_void_p
        fg = u.GetForegroundWindow()
        if not fg or fg == meu_hwnd:
            return False
        if fg in (u.GetShellWindow(), u.GetDesktopWindow()):
            return False
        cls = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(ctypes.c_void_p(fg), cls, 64)
        if cls.value in ("Progman", "WorkerW", "Shell_TrayWnd"):   # área de trabalho e barra de tarefas
            return False
        m_fg = u.MonitorFromWindow(ctypes.c_void_p(fg), 2)
        if m_fg != u.MonitorFromWindow(ctypes.c_void_p(meu_hwnd), 2):
            return False
        r, mi = _RECT(), _MONINFO()
        mi.cb = ctypes.sizeof(_MONINFO)
        u.GetWindowRect(ctypes.c_void_p(fg), ctypes.byref(r))
        u.GetMonitorInfoW(ctypes.c_void_p(m_fg), ctypes.byref(mi))
        return r.l <= mi.mon.l and r.t <= mi.mon.t and r.r >= mi.mon.r and r.b >= mi.mon.b
    except Exception:
        return False

def estado_externo():
    if (BASE / "gravando").exists():
        return ("guardando" if (BASE / "pendente").exists() else "ouvindo"), ""
    # Sexta rápida (conversa com o Haiku): falando, ou pensando na resposta
    if (BASE / "rapida-falando").exists():
        return "falando", ""
    if (BASE / "rapida-ativa").exists():
        return "pensando", ""
    if vivo(BASE / "falando.pid"):
        # Bloco 2: só "fala" quando a voz já começou (progresso.json existe). Antes disso o
        # áudio ainda está sendo preparado, e ela mexia a boca uns 5 s sem som.
        if (BASE / "progresso.json").exists():
            return "falando", ""
        return "pensando", "Preparando a fala…"
    if vivo(BASE / "acompanhante.pid"):
        leg = (ler_json(BASE / "legenda.json", 12) or {}).get("txt", "")
        st = ler_json(BASE / "status.json", 20)
        if st and st.get("cat") not in (None, "pensar"):
            return "trabalhando", leg
        return "pensando", leg
    # 15/11: avisos da Sexta (avisos.py). Fala uma frase genérica e mostra o assunto no balão.
    av = ler_json(BASE / "aviso.json", 30)
    if av and av.get("txt"):
        return ("falando" if av.get("fala") else "espera"), av["txt"]
    return "espera", ""

class Mascote(QWidget):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle("Sexta-Feira")
        self.resize(WM, HM)
        self.mem = self.carregar()
        self.espelho_t, self.no_espelho = time.time(), False   # 18/11: o espelho (espelho.py)
        # 18/11: o orbe (o Claude falando direto com o dono). 0 = ela, 1 = o orbe.
        self.orbe_k, self.orbe_quer, self.env, self.env_suave = 0.0, False, None, 0.0
        rnd = random.Random(18)
        self.orbe_part = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(0, 1), rnd.uniform(-1, 1),
                           rnd.uniform(0, 2 * math.pi), rnd.random()) for _ in range(220)]
        # profundidade: escala atual, a do passeio e a preferência dele (roda do mouse)
        self.prof = self.prof_alvo = self.prof_passeio = 1.0
        self.prof_base = float(self.mem.get("prof", 1.0))
        tela = QGuiApplication.primaryScreen().availableGeometry()
        if "pes" in self.mem:
            fx, fy = self.mem["pes"]
        else:  # memória antiga: guardava o canto da janela de 230 x 250
            x, y = self.mem.get("x", tela.right() - W - 20), self.mem.get("y", tela.bottom() - H)
            fx, fy = x + W / 2, y + H
        self.px, self.py = float(fx - WM / 2), float(fy - HM)
        # profundidade v2: nível pedido (menu/demonstração/arquivo), escuridão da imersão,
        # quadradinho da janelinha, para onde os pés vão e de onde ela saiu
        self.forcado = None        # (escala alvo, até quando; None = sem prazo)
        self.demo_prof = None      # [(nível, fim), ...] da demonstração de profundidade
        self.imersao = 0.0         # 0 = normal · 1 = tela toda escura em volta dela
        self.pes_alvo = None       # (fx, fy) para onde os pés estão indo (níveis grandes e a volta)
        self.pes_antes = None      # onde ela estava antes de crescer (para voltar)
        self.tela_cheia_fora = False   # um filme/série em tela cheia no monitor dela
        self.prof_pedido_t = time.time()   # ignora pedidos antigos do profundidade.json
        self.leg_prof, self.leg_prof_ate = "", 0.0
        self.geo_atual = None
        # 16/11: tela de descanso (o holograma dela) e o clique no reator do peito
        self.descanso = carregar_descanso(self)
        self.central = carregar_central(self)   # 16/11: central de comando (tela 1)
        self.descanso_modo = None          # None · "fundo" (automática, atrás das janelas) · "frente"
        self.uso_tela_t = time.time()      # última vez que o mouse passou pela tela dela
        self.prox_raise = 0.0
        self.toque = None                  # (posição, hora, foi no peito?) do último clique
        self.toque_id = 0
        self.aplicar_janela()
        self.estado, self.legenda = "espera", ""
        self.t0 = time.time()
        self.ultima_atividade = time.time()
        self.dormindo = False
        self.feliz_ate = 0.0
        self.proximo_pisco = time.time() + 3
        self.pisco_ate = 0.0
        self.alvo = None
        self.proximo_passeio = time.time() + random.uniform(6, 12)
        self.vont, self.prox_vont = {}, 0.0   # 15/11 (noite): as cinco vontades (o id), lidas a cada 5 s
        # 16/11: os movimentos dela. Recarrega quando o arquivo muda (ela aprende à noite).
        self.movs, self.movs_mtime, self.mov, self.mov_ini = {}, 0.0, None, 0.0
        self.mov_pedido_t = 0.0
        self.ap_mtime, self.ap_mudou_t, self.ap_mudou = None, 0.0, []   # 17/11: a aparência dela
        self.camadas_r = []
        self.prox_mov_solto = time.time() + random.uniform(180, 420)
        self.olhar = QPointF(0, 0)
        self.inclinacao = 0.0
        self.arrastando = None
        self.tick = 0
        self.apres = None          # retângulo do visor quando ela está apresentando
        self.apres_inicio = 0.0
        self.alvo_apres = None
        self.lado = 1              # 1 = aponta para a direita, -1 = para a esquerda
        self.ponta = None
        # gestos: valores atuais (suavizados) e o gesto escolhido
        self.g_esq, self.g_dir, self.g_cab, self.g_sobe = 25.0, -25.0, 0.0, 0.0
        self.gesto, self.gesto_inicio, self.proximo_gesto = "repouso", 0.0, 0.0
        self.lado_inclina = 1
        self.fatia_vista = None
        # Bloco 2: o que a voz conta sobre a fala (emoção, gesto pedido, seção do visor)
        self.prog = {}             # último progresso.json lido inteiro
        self.emo = "neutra"
        self.gid_visto = 0         # número do último gesto pedido pelo roteiro que ela já fez
        self.marcado_ate = 0.0     # até quando o gesto pedido fica (o sorteio não o atropela)
        self.som = False           # o áudio está tocando agora?
        # Poses de trabalho (14/11): o que eu estou fazendo (status.json) e se o acompanhante
        # está falando agora (legenda.json, "fala": true)
        self.cat = "pensar"
        self.acomp_fala = False
        self.acomp_t = 0.0         # quando o acompanhante começou a falar (para o gestinho)
        # Casa da Sexta (protótipo): o que já foi "montado" e o que já foi apresentado
        self.casa = carregar_casa()
        self.casa_apresentado = None   # versão do visor que ela já apresentou
        self.revelado = 999
        self.novo_desde = None
        # fluidez: 60 quadros por segundo com relógio preciso; tudo se move pelo tempo
        # que passou (dt), e não por quadro, então não engasga quando um quadro atrasa.
        self.ultimo_quadro = time.time()
        self.prox_leitura = 0.0
        self.vel = 0.0             # velocidade do passeio (acelera e freia)
        # 15/11 (ideias do usuário com o Gemini; norte: a EVE do Wall-E)
        self.rapida = False
        self.passou_ant = False
        self.pulo_t = self.antena_t = self.lanca_t = -99.0   # pulinho ao ser chamada, antena piscando, arremesso
        self.prep_t, self.chegada_t, self.chegada_dir, self.dir_mov = -99.0, -99.0, 0.0, 0.0
        self.agacha = self.balanco = 0.0
        self.tedio, self.tedio_t, self.tedio_fim = None, 0.0, 0.0   # o que ela faz sozinha quando está à toa
        self.prox_tedio = time.time() + random.uniform(20, 35)
        self.olhar_lado = 1
        self.cpu_ant, self.cpu_alta, self.esforco, self.prox_cpu = None, 0, False, 0.0
        self.demo, self.demo_fim, self.did_visto = None, 0.0, 0   # demonstração em andamento
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.passo)
        self.timer.start(16)

    # ---------------------------------------------------------------- memória
    def carregar(self):
        try:
            return json.loads(MEM.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def salvar(self):
        try:
            MEM.write_text(json.dumps(self.mem), encoding="utf-8")
        except Exception:
            pass

    def lembrar_lugar(self):
        c = self.centro()
        chave = f"{int(c.x()) // 200},{int(c.y()) // 200}"
        lugares = self.mem.setdefault("lugares", {})
        lugares[chave] = lugares.get(chave, 0) + 1
        self.mem["pes"] = [round(self.px + WM / 2), round(self.py + HM)]
        self.mem.pop("x", None); self.mem.pop("y", None)
        self.salvar()

    # ---------------------------------------------------------------- profundidade (geometria)
    def caixa(self, s=None):
        """Onde ela aparece de fato na tela (canto e tamanho), na escala s."""
        s = self.prof if s is None else s
        return self.px + (WM - W * s) / 2, self.py + HM - H * s, W * s, H * s

    @staticmethod
    def janela_para(vx, vy, s):
        """O inverso: para ela aparecer com o canto em (vx, vy) na escala s, onde fica a janela."""
        return vx - (WM - W * s) / 2, vy - (HM - H * s)

    def centro(self):
        vx, vy, w, h = self.caixa()
        return QPointF(vx + w / 2, vy + h / 2)

    # ---------------------------------------------------------------- profundidade v2 (16/11)
    def pes(self):
        return self.px + WM / 2, self.py + HM

    def por_pes(self, fx, fy):
        self.px, self.py = fx - WM / 2, fy - HM

    def tela_dos_pes(self):
        fx, fy = self.pes()
        s = QGuiApplication.screenAt(QPointF(fx, fy - 5).toPoint()) or QGuiApplication.screenAt(
            self.centro().toPoint()) or QGuiApplication.primaryScreen()
        return s.geometry()

    def escala_tela(self):
        g = self.tela_dos_pes()
        return max(1.5, min(g.height() * 0.86 / H, g.width() * 0.8 / W))

    def aplicar_janela(self):
        """A janela acompanha o tamanho dela. Com a imersão, cobre o monitor inteiro."""
        s = self.prof
        if self.imersao > 0.003:
            g = self.tela_dos_pes()
            x, y, w, h = g.x(), g.y(), g.width(), g.height()
        else:
            fx, fy = self.pes()
            # tamanho em degraus de 16 px: menos redimensionamentos enquanto ela cresce ou encolhe
            w = math.ceil((W * s + 2 * MARGEM) / 16) * 16
            h = math.ceil((H * s + 2 * MARGEM) / 16) * 16
            x, y = round(fx - w / 2), round(fy - H * s - MARGEM)
        if self.geo_atual != (x, y, w, h):
            self.geo_atual = (x, y, w, h)
            self.setGeometry(x, y, w, h)

    def caixa_na_janela(self):
        """Canto da caixa dela (escala s) em coordenadas da própria janela, com a fração de pixel."""
        fx, fy = self.pes()
        s = self.prof
        gx, gy = (self.geo_atual or (self.x(), self.y()))[:2]
        return fx - W * s / 2 - gx, fy - H * s - gy

    def pedir_nivel(self, nome, dur=None, legenda=True):
        """Leva ela até um nível de profundidade. dur=None: fica até pedirem outro (ou "normal")."""
        agora = time.time()
        if nome == "normal" and dur is None:
            self.forcado = None
        else:
            esc = self.escala_tela() if nome == "tela" else NIVEL_ESC.get(nome, 1.0)
            self.forcado = (esc, None if dur is None else agora + dur)
            if esc > S_MAX and self.pes_antes is None:
                self.pes_antes = self.pes()
        if legenda:
            self.leg_prof = dict((n, l) for n, _, l in NIVEIS).get(nome, "")
            self.leg_prof_ate = agora + 2.2
        self.ultima_atividade = agora
        if self.dormindo and nome != "janelinha":
            self.acordar()
        log(f"profundidade: {nome}")

    def iniciar_demo_prof(self):
        agora, seq = time.time(), []
        for nome, dur in DEMO_PROF:
            agora += dur
            seq.append((nome, agora))
        self.demo_prof = seq
        self.alvo = None
        self.pedir_nivel(seq[0][0], dur=DEMO_PROF[0][1] + 1)
        log("demonstração da profundidade")

    def sair_imersao(self):
        self.demo_prof = None
        self.forcado = None
        self.leg_prof_ate = 0.0

    # ---------------------------------------------------------------- tela de descanso (16/11)
    def tela_dela(self):
        """A tela da tela de descanso: a que ficou guardada (quando o usuário a arrasta para um monitor)
        ou, de começo, a segunda tela."""
        telas = QGuiApplication.screens()
        nome = self.mem.get("tela_descanso")
        for t in telas:
            if t.name() == nome:
                return t
        outras = [t for t in telas if t != QGuiApplication.primaryScreen()]
        return outras[0] if outras else QGuiApplication.primaryScreen()

    def ponto_peito(self):
        vx, vy, w, h = self.caixa()
        s = self.prof
        return QPointF(vx + s * (OX + 100 * ESC), vy + s * (OY + 156 * ESC))

    def abrir_descanso(self, modo):
        if not self.descanso:
            return
        tela = self.tela_dela()
        self.descanso.mostrar(tela.geometry(), modo == "frente")
        self.descanso_modo = modo
        if modo == "frente":
            # ela vai para o canto esquerdo da tela dela, do lado do holograma que está projetando
            g, ga = tela.geometry(), tela.availableGeometry()
            self.alvo = None
            self.forcado = (1.15, None)
            self.pes_alvo = (g.left() + g.width() * 0.15, ga.bottom() - 8)
            self.raise_()
            self.antena_t = time.time()
        log(f"tela de descanso: {modo}")

    def abrir_central(self):
        if self.central:
            self.central.mostrar(QGuiApplication.primaryScreen().geometry(), True)
            log("central de comando: aberta")

    def fechar_central(self):
        if self.central and self.central.aberta():
            self.central.esconder()
            log("central de comando: fechada")

    def fechar_descanso(self):
        if not self.descanso:
            return
        self.descanso.esconder()
        if self.descanso_modo == "frente":
            self.forcado = None
            self.pes_alvo = None
        self.descanso_modo = None
        self.uso_tela_t = time.time()
        log("tela de descanso: fechada")

    def alternar_descanso(self):
        if self.descanso_modo == "frente" and self.descanso and self.descanso.aberta():
            self.fechar_descanso()
        else:
            self.abrir_descanso("frente")

    def atualizar_descanso(self, agora):
        if not self.descanso:
            return
        tela = self.tela_dela()
        if tela.geometry().contains(QCursor.pos()) and self.descanso_modo != "frente":
            self.uso_tela_t = agora
        if self.descanso_modo and not self.descanso.isVisible():
            self.descanso_modo = None
        # 17/11, bug visto pelo usuário: ela abria a tela de descanso ao ser chamada ou ao responder
        # (conversa por voz não mexe no mouse, então o relógio de 3 min corria). Ocupada conta como uso;
        # o fundo some quando ela trabalha, e qualquer tela de descanso some quando ela apresenta (palco).
        if self.estado != "espera" or self.rapida or (BASE / "palco").exists():
            self.uso_tela_t = agora
            if self.descanso_modo == "fundo" or (self.descanso_modo and (BASE / "palco").exists()):
                self.fechar_descanso()
                return
        auto = self.mem.get("descanso_auto", True)
        espera = self.mem.get("descanso_min", 3) * 60
        if not self.descanso_modo and auto and agora - self.uso_tela_t > espera:
            self.abrir_descanso("fundo")
        elif self.descanso_modo == "fundo" and not auto:
            self.fechar_descanso()
        if self.descanso_modo == "frente" and agora > self.prox_raise:
            self.prox_raise = agora + 2
            self.raise_()          # ela sempre na frente do holograma dela

    def atualizar_profundidade(self, agora):
        """Lê pedidos de fora (profundidade.json), anda a demonstração e vê se há filme em tela cheia."""
        esp = ler_json(BASE / "espelho-pedido.json", 60)   # 18/11: ela quer se ver (só a janela dela)
        if esp and esp.get("t", 0) > self.espelho_t:
            self.espelho_t = esp["t"]
            self.tirar_foto_do_espelho()
        ped = ler_json(BASE / "profundidade.json", 60)
        if ped and ped.get("t", 0) > self.prof_pedido_t:
            self.prof_pedido_t = ped["t"]
            nome = ped.get("nivel")
            cmd = ped.get("descanso")   # 16/11: {"descanso": "fundo" | "frente" | "fechar"}
            if cmd in ("fundo", "frente"):
                self.abrir_descanso(cmd)
            elif cmd == "fechar":
                self.fechar_descanso()
            cen = ped.get("central")    # 16/11: {"central": "abrir" | "fechar"}
            if cen == "abrir":
                self.abrir_central()
            elif cen == "fechar":
                self.fechar_central()
            if nome is None:
                pass
            elif nome == "demo" and ped.get("respeitar") and self.tela_cheia_fora:
                self.demo_espera = True     # tem filme em tela cheia: mostra quando ele sair
            elif nome == "demo":
                self.iniciar_demo_prof()
            elif nome in NIVEL_ESC:
                self.demo_prof = None
                self.pedir_nivel(nome, ped.get("dur"))
        if getattr(self, "demo_espera", False) and not self.tela_cheia_fora and self.estado == "espera":
            self.demo_espera = False
            self.iniciar_demo_prof()
        if self.demo_prof:
            while self.demo_prof and agora >= self.demo_prof[0][1]:
                self.demo_prof.pop(0)
                if self.demo_prof:
                    nome, fim = self.demo_prof[0]
                    self.pedir_nivel(nome, dur=fim - agora + 1)
            if not self.demo_prof:
                self.demo_prof = None
                self.forcado = None
        if self.forcado and self.forcado[1] is not None and agora > self.forcado[1] and not self.demo_prof:
            self.forcado = None

    # ---------------------------------------------------------------- comportamento
    def tela_atual(self):
        c = self.centro().toPoint()
        s = QGuiApplication.screenAt(c) or QGuiApplication.primaryScreen()
        return s.availableGeometry()

    def sortear_prof(self):
        # a cada passeio ela escolhe uma distância: quase sempre perto do normal, às vezes
        # bem no fundo, às vezes bem pertinho
        return random.choices((0.68, 0.8, 0.9, 1.0, 1.12, 1.28), (1, 2, 2, 4, 2, 1))[0]

    def escolher_passeio(self):
        geo = self.tela_atual()
        if random.random() < 0.08 and len(QGuiApplication.screens()) > 1:  # às vezes visita a outra tela
            geo = random.choice(QGuiApplication.screens()).availableGeometry()
        lugares = self.mem.get("lugares", {})
        if lugares and random.random() < 0.5:  # prefere os lugares onde o usuário a coloca
            chave = random.choices(list(lugares), weights=list(lugares.values()))[0]
            cx, cy = (int(v) * 200 + 100 for v in chave.split(","))
            x, y = cx - W / 2 + random.uniform(-80, 80), cy - H / 2 + random.uniform(-60, 60)
        elif random.random() < 0.25 + 0.45 * self.vont.get("vinculo", 0):  # vínculo: chega perto do mouse (de você)
            m = QCursor.pos()
            x, y = m.x() - W / 2 + random.choice([-170, 170]), m.y() - H / 2
        else:  # passeia pela parte de baixo da tela, como quem anda no chão
            x = random.uniform(geo.left(), geo.right() - W)
            y = geo.bottom() - H + random.uniform(-40, 0)
        # profundidade: o alvo é o lugar dos PÉS; no fundo, os pés ficam um pouco mais
        # para cima (perspectiva: o que está longe fica mais perto do horizonte)
        s = max(S_MIN, min(S_MAX, self.sortear_prof() * self.prof_base))
        fx, fy = x + W / 2, y + H - max(0.0, 1 - s) * 90
        fx = max(geo.left() + W * s / 2, min(geo.right() - W * s / 2, fx))
        fy = max(geo.top() + H * s, min(geo.bottom(), fy))
        self.prof_passeio = s
        self.alvo = (fx - WM / 2, fy - HM)

    def passo(self):
        agora = time.time()
        f = min(0.1, agora - self.ultimo_quadro) * 30   # quantos "quadros de 30 fps" passaram
        self.ultimo_quadro = agora
        def suave(k):  # o mesmo amortecimento de antes, independente do fps
            return 1 - (1 - k) ** f
        self.tick += 1
        alvo_k = 1.0 if self.orbe_quer else 0.0   # 18/11: ~0,9 s de transição
        if self.orbe_k != alvo_k:
            passo_k = (f / 30) / 0.9
            self.orbe_k = (min(alvo_k, self.orbe_k + passo_k) if alvo_k > self.orbe_k
                           else max(alvo_k, self.orbe_k - passo_k))
        if agora >= self.prox_leitura:  # ~0,3 s (0,15 s enquanto fala, para os gestos caírem na hora)
            self.prox_leitura = agora + (0.15 if self.estado == "falando" else 0.3)
            # 16/11 (usuário): desligar a voz só cala a fala. Ela some só com "fecha o mascote".
            if FECHADO.exists():
                QApplication.quit()
                return
            novo = estado_externo()
            if novo[0] != "espera" or novo[1]:   # 15/11: um aviso no balão também a acorda
                self.ultima_atividade = agora
                if self.dormindo:
                    self.acordar()
                if novo[1] and novo[1] != self.legenda and novo[0] == "espera":
                    self.antena_t = agora          # antena pisca: "tenho uma coisa para você"
            if novo[0] == "ouvindo" and self.estado == "espera":
                self.pulo_t = self.antena_t = agora   # chamada: dá um pulinho e a antena pisca
            self.estado, self.legenda = novo
            # Sexta rápida: cor violeta durante a conversa; ao passar para o chat, volta ao azul
            self.rapida = (BASE / "rapida-ativa").exists()
            try:
                passou = time.time() - float((BASE / "rapida-passou").read_text()) < 3.0
            except Exception:
                passou = False
            if passou:
                # 19/11 (pedido do dono): sem a luz que voava da mão para o chat. Ela é uma só:
                # não manda o pedido para ninguém, fica onde está e pensa com calma.
                self.rapida, self.legenda = False, "Pensando com calma…"
                self.ultima_atividade = agora
            self.passou_ant = passou
            if agora >= self.prox_vont:               # 15/11 (noite): o id. Ela sente, não sabe.
                self.prox_vont = agora + 5
                self.vont = ler_json(BASE / "vontades.json", 600) or {}
                self.atualizar_movimentos(agora)
                self.atualizar_aparencia(agora)
            if agora >= self.prox_cpu:                # o PC está pesado? (a cada 2 s)
                self.prox_cpu = agora + 2
                try:
                    oc, tot = tempos_cpu()
                    if self.cpu_ant and tot > self.cpu_ant[1]:
                        uso = 1 - (oc - self.cpu_ant[0]) / (tot - self.cpu_ant[1])
                        self.cpu_alta = self.cpu_alta + 1 if uso > 0.85 else (0 if uso < 0.7 else self.cpu_alta)
                        self.esforco = self.cpu_alta >= 3
                    self.cpu_ant = (oc, tot)
                except Exception:
                    self.esforco = False
                # 16/11: filme/série em tela cheia no monitor dela? Então ela se recolhe na janelinha.
                self.tela_cheia_fora = app_em_tela_cheia(int(self.winId()))
                try:   # 16/11: as leis do impulso não deixam ela puxar assunto no meio de um filme ou jogo
                    if self.tela_cheia_fora:
                        (BASE / "tela-cheia").touch()
                    else:
                        (BASE / "tela-cheia").unlink(missing_ok=True)
                except Exception:
                    pass
            # Bloco 2: lê o que a voz publicou. Se o arquivo falhar numa leitura, vale o último.
            if self.estado == "falando":
                if (BASE / "rapida-falando").exists():   # 15/11: a Sexta rápida também tem corpo
                    self.prog = ler_json(BASE / "rapida-falando", 120) or self.prog
                else:
                    self.prog = ler_json(BASE / "progresso.json", 600) or self.prog
                self.emo = self.prog.get("emo") if self.prog.get("emo") in EMOCAO else "neutra"
                self.som = bool(self.prog.get("som", True))
            else:
                self.prog, self.emo, self.som = {}, "neutra", False
            try:   # 18/11: o orbe aparece quando o Claude trabalha ou fala com o dono (modo Claude)
                modo_claude = (BASE / "modo-chat.txt").read_text(encoding="utf-8").strip() == "claude"
            except Exception:
                modo_claude = False
            prog_f = ler_json(BASE / "progresso.json", 600) or {}
            fala_claude = vivo(BASE / "falando.pid") and bool(prog_f.get("orbe"))
            rapida_on = (BASE / "rapida-falando").exists() or (BASE / "rapida-ativa").exists()
            self.orbe_quer = bool(fala_claude or (modo_claude and self.estado in ("pensando", "trabalhando"))) \
                and not rapida_on
            self.env = ler_json(BASE / "envelope.json", 120) if self.orbe_quer else None
            # poses de trabalho: qual atividade e se o acompanhante está falando
            if self.estado in ("trabalhando", "pensando"):
                st = ler_json(BASE / "status.json", 20) or {}
                self.cat = st.get("cat") if self.estado == "trabalhando" and st.get("cat") in POSES else "pensar"
                leg = ler_json(BASE / "legenda.json", 15) or {}
                fala = bool(leg.get("fala"))
                if fala and not self.acomp_fala:
                    self.acomp_t = agora
                    self.antena_t = agora             # "achei uma coisa": a antena pisca duas vezes
                self.acomp_fala = fala
            else:
                self.cat, self.acomp_fala = "pensar", False
            self.atualizar_apresentacao()
            self.atualizar_casa(agora)
            self.atualizar_gesto(agora)
            self.atualizar_demo(agora)      # por último: troca o estado só para o desenho
            self.atualizar_profundidade(agora)
            self.atualizar_descanso(agora)
        # gestos: os ângulos andam suavemente até o alvo do gesto atual
        ge, gd, gc, gs = GESTOS.get(self.gesto, GESTOS["repouso"])
        if self.demo and DEMOS[self.demo][0]:   # demonstrando: braços em repouso, sem gesto de fala
            ge, gd, gc, gs = GESTOS["repouso"]
        if self.estado in ("trabalhando", "pensando") and not self.dormindo:
            ge, gd, gc, gs = POSES[self.cat]          # a pose da atividade
            if self.acomp_fala:                       # o acompanhante fala: ela levanta a cabeça
                gc = 0                                # e faz um gestinho com a mão livre
                if self.cat == "pensar":
                    gd = -25                          # tira a mão do queixo para falar
                if agora - self.acomp_t < 1.6:
                    ge = max(ge, 70) if self.cat != "rodar" else ge
                    gd = min(gd, -70) if self.cat == "rodar" else gd
        if self.estado == "espera" and not self.dormindo:
            if self.tedio == "espreguica":
                ge, gd, gc, gs = 130, -130, 0, -7
            elif self.esforco:                         # PC pesado: encolhe, braços colados
                ge, gd, gc, gs = 12, -12, 0, 3
        if agora - self.lanca_t < 0.9:                 # arremesso: levanta o braço e joga
            gd = -105 if agora - self.lanca_t < 0.35 else -45
        if self.gesto == "inclina":
            gc *= self.lado_inclina
        if self.gesto == "ombros" and agora - self.gesto_inicio > 0.6:
            gs = 0  # o ombro sobe e desce rápido
        if self.estado == "falando":  # Bloco 2: a emoção muda o tamanho do gesto e a cabeça
            emo = EMOCAO[self.emo]
            ge = min(108.0, 25 + (ge - 25) * emo["amp"])
            gd = max(-108.0, -25 + (gd + 25) * emo["amp"])
            gc += emo["cab"]
            if self.gesto == "comemora":               # braços para cima de verdade (passa do limite dos outros gestos)
                ge, gd = 128.0, -128.0
        if self.mov and not self.dormindo:   # 16/11: um movimento dela manda no corpo enquanto dura
            pose = _movs.pose_em(self.movs[self.mov], agora - self.mov_ini) if self.mov in self.movs else None
            if pose is None:
                self.mov = None
            else:
                ge, gd = pose.get("esq", 25.0), pose.get("dir", -25.0)
                gc, gs = pose.get("cab", 0.0), pose.get("sobe", 0.0)
        if self.apres:
            gc += 4 * self.lado  # apresentando: cabeça levemente virada para o visor
        k = suave(0.16)
        self.g_esq += (ge - self.g_esq) * k
        self.g_dir += (gd - self.g_dir) * k
        self.g_cab += (gc - self.g_cab) * suave(0.12)
        self.g_sobe += (gs - self.g_sobe) * suave(0.25)
        # cochilo: 2,5 min sem nada acontecendo
        mouse = QCursor.pos()
        centro = self.centro()
        dist = math.hypot(mouse.x() - centro.x(), mouse.y() - centro.y())
        # profundidade: chega mais perto para falar e para ouvir, volta para a distância
        # do passeio quando fica à toa, e se afasta um pouco para cochilar
        if self.dormindo:
            # 16/11: depois de um tempinho dormindo, ela se recolhe na janelinha
            alvo_p = NIVEL_ESC["janelinha"] if agora - getattr(self, "dormiu_t", agora) > 45 else 0.9
        elif self.estado == "falando":
            alvo_p = 1.06 if self.apres else PROF_FALA.get(self.emo, 1.12)
        elif self.estado in ("ouvindo", "guardando"):
            alvo_p = 1.12
        elif self.estado in ("pensando", "trabalhando"):
            alvo_p = 1.0
        else:
            alvo_p = self.prof_passeio
        if self.estado != "espera" or self.dormindo:
            alvo_p *= self.prof_base   # (o passeio já vem com a preferência aplicada)
        if self.tela_cheia_fora and not self.apres:
            # 16/11: você está vendo um filme/série em tela cheia: ela não atrapalha
            alvo_p = min(alvo_p, 0.62 if self.estado == "falando" else NIVEL_ESC["janelinha"])
        self.prof_alvo = max(S_PISO, min(S_MAX, alvo_p))
        if self.demo:                 # demonstrando: fica no tamanho em que está
            self.prof_alvo = self.prof
        if self.forcado and not self.apres:   # nível pedido (menu, demonstração, arquivo)
            self.prof_alvo = self.forcado[0]
        if not self.arrastando:
            # 16/11: o zoom anda em escala logarítmica (de 0,34 a 3 parece uma viagem só, sem
            # disparar no começo), e mais rápido quando é um nível pedido
            rapido = self.forcado or self.prof > S_MAX + 0.02 or self.prof < S_MIN - 0.02
            lp = math.log(self.prof)
            self.prof = math.exp(lp + (math.log(self.prof_alvo) - lp) * suave(0.065 if rapido else 0.035))
        # imersão: acima de 1,55 a tela escurece em volta dela, até ficar toda escura na "tela"
        topo = self.escala_tela()
        k_im = max(0.0, min(1.0, (self.prof - IMERSAO_INI) / max(0.1, topo * 0.97 - IMERSAO_INI)))
        self.imersao = k_im * k_im * (3 - 2 * k_im)
        # os pés: nos níveis grandes ela vai para o meio da tela; depois volta para onde estava
        g = self.tela_dos_pes()
        if self.forcado and not self.apres and self.forcado[0] >= topo * 0.95:
            self.pes_alvo = (g.center().x(), g.bottom() - g.height() * 0.035)
        elif not self.forcado and self.pes_antes and self.prof < S_MAX + 0.15:
            self.pes_alvo, self.pes_antes = self.pes_antes, None
        if self.prof > S_MAX and not self.arrastando:   # grande: não deixa sair da tela
            fx, fy = self.pes()
            s = self.prof
            fx = max(g.left() + W * s / 2, min(g.right() - W * s / 2, fx)) if g.width() > W * s else g.center().x()
            fy = max(g.top() + H * s, min(g.bottom(), fy))
            self.por_pes(fx, fy)
        if self.pes_alvo and not self.arrastando:
            fx, fy = self.pes()
            dx, dy = self.pes_alvo[0] - fx, self.pes_alvo[1] - fy
            if math.hypot(dx, dy) < 1:
                if not self.forcado:
                    self.pes_alvo = None
            else:
                k = suave(0.08)
                self.por_pes(fx + dx * k, fy + dy * k)
        sono = 90 if time.localtime().tm_hour < 5 else 150   # de madrugada ela cochila antes
        if self.vont.get("descanso", 0) >= 0.65:              # com sono, cochila mais cedo
            sono = min(sono, 70)
        if self.estado == "espera" and not self.dormindo and agora - self.ultima_atividade > sono:
            self.dormindo = True
            self.dormiu_t = agora
            self.alvo = None
            satisfazer("descanso")
        if self.dormindo and dist < 110:
            self.acordar()
        # piscar
        if agora > self.proximo_pisco:
            self.pisco_ate = agora + 0.14
            self.proximo_pisco = agora + random.uniform(2.5, 6)
        # olhos seguem o mouse
        vx, vy, _, _ = self.caixa()
        cab = QPointF(centro.x(), vy + (OY + 84 * ESC) * self.prof)
        dx, dy = mouse.x() - cab.x(), mouse.y() - cab.y()
        d = math.hypot(dx, dy) or 1
        k = min(4.0, d / 60)
        alvo_olhar = QPointF(dx / d * k, dy / d * k * 0.7)
        if self.tedio == "olha_longe":   # olha para fora da tela, como quem vê o outro monitor
            alvo_olhar = QPointF(4.5 * self.olhar_lado, -1.2)
        elif self.tedio == "holo":       # lê o painelzinho dela
            alvo_olhar = QPointF(4.0, -1.5)
        if self.apres:  # apresentando: olha para o visor
            alvo_olhar = QPointF(4.0 * self.lado, -0.5)
            if self.alvo_apres and not self.arrastando:
                ax, ay = self.alvo_apres
                vx, vy = ax - self.px, ay - self.py
                dd = math.hypot(vx, vy)
                if dd > 0.5:  # voa rápido e freia suave ao chegar
                    passo_px = min(dd, max(0.6, min(6.0, dd * 0.09)) * f)
                    self.px += vx / dd * passo_px
                    self.py += vy / dd * passo_px
                    self.aplicar_janela()
        ko = suave(0.2)
        self.olhar = QPointF(self.olhar.x() + (alvo_olhar.x() - self.olhar.x()) * ko,
                             self.olhar.y() + (alvo_olhar.y() - self.olhar.y()) * ko)
        # passeio: só em espera, acordada, sem estar sendo arrastada e sem "fica quieta"
        livre = (self.estado == "espera" and not self.dormindo and not self.arrastando
                 and not self.forcado and self.pes_alvo is None
                 and (not self.mem.get("quieta") or self.demo == "passeio"))
        # vida própria: parada e à toa, de vez em quando ela faz alguma coisinha
        # (vale também no "fica quietinha": ela não passeia, mas continua viva)
        parada = self.estado == "espera" and not self.dormindo and not self.arrastando
        if not parada or self.alvo is not None or self.esforco:
            self.tedio = None
            if not parada:
                self.prox_tedio = max(self.prox_tedio, agora + 15)
        elif self.tedio and agora > self.tedio_fim:
            self.tedio, self.prox_tedio = None, agora + random.uniform(14, 30)
        elif not self.tedio and agora > self.prox_tedio and agora - self.ultima_atividade > 20:
            madrugada = time.localtime().tm_hour < 5
            boceja = 3 if madrugada else (2 if agora - self.ultima_atividade > 80 else 0)
            # 15/11 (noite): curiosa, abre o painel mais vezes; cansada, boceja mais
            cur, desc = self.vont.get("curiosidade", 0), self.vont.get("descanso", 0)
            if desc >= 0.5:
                boceja += 3
            opcoes = {"olha_longe": 3, "holo": 3 + 6 * cur, "espreguica": 1 + desc, "boceja": boceja}
            self.tedio = random.choices(list(opcoes), list(opcoes.values()))[0]
            if self.tedio == "holo":
                satisfazer("curiosidade")       # olhou o painel: a curiosidade se acalma
            self.tedio_fim = agora + {"olha_longe": 2.6, "holo": 3.4, "espreguica": 1.8, "boceja": 1.9}[self.tedio]
            self.tedio_t, self.olhar_lado = agora, random.choice((-1, 1))
            # 16/11 (usuário): de vez em quando, por vontade própria, ela chega pertinho da tela e fica
            # fazendo a coisinha dela ali (lendo o painel, olhando em volta, espreguiçando), depois volta.
            # Mais vezes quando o vínculo ou a curiosidade estão altos. Nunca com filme em tela cheia.
            chance = 0.18 + 0.25 * max(self.vont.get("vinculo", 0), cur)
            if (not self.tela_cheia_fora and not self.forcado and not self.demo_prof
                    and self.tedio in ("holo", "olha_longe") and random.random() < chance):
                dur = random.uniform(6.0, 9.0)
                self.tedio_fim = agora + dur
                if self.pes_antes is None:
                    self.pes_antes = self.pes()
                self.forcado = (random.choice((1.45, 1.5, 1.55)), agora + dur)
                log(f"chegou perto da tela por vontade própria ({self.tedio})")
        if livre and self.alvo is None and not self.tedio and agora > self.proximo_passeio:
            self.escolher_passeio()
            self.prep_t = agora            # antecipação: antes de sair, ela se prepara
        if not livre:
            self.alvo = None
            self.proximo_passeio = agora + random.uniform(8, 15)
        alvo_incl = 0.0
        if self.alvo:
            ax, ay = self.alvo
            vx, vy = ax - self.px, ay - self.py
            dd = math.hypot(vx, vy)
            if dd < 1:
                self.alvo = None
                self.vel = 0.0
                # inquieta (coisa parada, ou preocupada com você): passeia mais vezes
                inquieta = self.vont.get("cuidar", 0) >= 0.6 or self.vont.get("terminar", 0) >= 0.7
                self.proximo_passeio = agora + (random.uniform(4, 9) if inquieta else random.uniform(10, 25))
                self.chegada_t, self.chegada_dir = agora, self.dir_mov   # freada com balanço
            elif agora - self.prep_t < 0.35:   # inclina para trás e agacha um tiquinho antes de ir
                alvo_incl = -max(-1.0, min(1.0, vx / dd)) * 7
            else:
                # acelera na saída e freia na chegada (antes era velocidade fixa, com tranco)
                alvo_v = 0.4 + 2.4 * min(1.0, dd / 70)          # px por quadro de 30 fps (~80 px/s)
                alvo_v *= 1 + self.orbe_k                       # 18/11: o orbe é bem mais rápido
                self.vel += (alvo_v - self.vel) * suave(0.07)
                passo_px = min(dd, self.vel * f)
                self.px += vx / dd * passo_px
                self.py += vy / dd * passo_px
                self.aplicar_janela()
                alvo_incl = max(-10, min(10, vx / dd * 9)) * min(1.0, self.vel / 1.5)
                self.dir_mov = max(-1.0, min(1.0, vx / dd))
        else:
            self.vel = 0.0
        self.inclinacao += (alvo_incl - self.inclinacao) * suave(0.1)
        kc = agora - self.chegada_t
        self.balanco = self.chegada_dir * 8 * math.exp(-4.5 * kc) * math.sin(kc * 11) if kc < 1.3 else 0.0
        agacha = 3.0 if (self.alvo and agora - self.prep_t < 0.35) else 0.0
        self.agacha += (agacha - self.agacha) * suave(0.3)
        # clareia suave (~1 s) quando a Sexta rápida está ativa (1); a cor continua a dela
        self.tom = getattr(self, "tom", 0.0) + ((1.0 if getattr(self, "rapida", False) else 0.0) - getattr(self, "tom", 0.0)) * suave(0.09)
        self.aplicar_janela()   # profundidade v2: a janela acompanha o tamanho e a posição dela
        self.update()

    def tocar_movimento(self, nome, agora, origem):
        if nome not in self.movs:
            return
        self.mov, self.mov_ini = nome, agora
        try:
            (BASE / "ultimo-movimento.json").write_text(json.dumps({"nome": nome, "t": time.time(), "origem": origem}),
                                                       encoding="utf-8")
        except Exception:
            pass
        log(f"movimento: {nome} ({origem})")
        if _ego is not None and origem != "gesto":
            _ego.lembrar("mexeu", movimento=nome)

    def atualizar_aparencia(self, agora):
        """17/11: recarrega a aparência quando o arquivo muda (ela escolhe à noite). Ausente = o visual de sempre."""
        global CIANO, AZUL, BRILHO
        if _apar is None:
            return
        try:
            mt = _apar.ARQ.stat().st_mtime if _apar.ARQ.exists() else 0.0
        except Exception:
            return
        if mt == self.ap_mtime:
            return
        antes = dict(AP, cor_principal=AZUL.name(), cor_brilho=BRILHO.name(), cor_olhos=CIANO.name())
        ap = _apar.carregar()
        CIANO, AZUL, BRILHO = QColor(ap["cor_olhos"]), QColor(ap["cor_principal"]), QColor(ap["cor_brilho"])
        AP.update({k: ap[k] for k in AP})
        self.camadas_r = []   # 17/11: os desenhos SVG que ela põe sobre si
        try:
            from PySide6.QtSvg import QSvgRenderer
            from PySide6.QtCore import QByteArray
            for c in AP["camadas"]:
                r = QSvgRenderer(QByteArray(c["svg"].encode("utf-8")))
                if r.isValid():
                    self.camadas_r.append((c, r))
        except Exception as e:
            log(f"camadas: não desenhou ({type(e).__name__})")
        if self.ap_mtime is not None:   # mudou com ela acordada: guarda para o carinho do clique
            self.ap_mudou = _apar.diferencas(antes, ap)
            self.ap_mudou_t = agora
            log(f"aparência nova: {', '.join(self.ap_mudou) or 'nada'}")
        self.ap_mtime = mt

    def atualizar_movimentos(self, agora):
        """16/11: recarrega a biblioteca, atende pedidos (impulso) e às vezes se mexe sozinha."""
        if _movs is None:
            return
        arq = _movs.ARQ
        try:
            mt = arq.stat().st_mtime
            if mt != self.movs_mtime:
                self.movs, self.movs_mtime = _movs.carregar(), mt
                log(f"movimentos carregados: {len(self.movs)}")
        except Exception:
            pass
        pedido = ler_json(BASE / "movimento.json", 30) or {}
        if pedido.get("nome") in self.movs and pedido.get("t", 0) > self.mov_pedido_t:
            self.mov_pedido_t = pedido["t"]
            self.tocar_movimento(pedido["nome"], agora, "impulso")
            return
        # sozinha: parada, acordada, sem filme em tela cheia. Quanto mais ela gosta, mais vezes.
        if (self.estado == "espera" and not self.dormindo and not self.tela_cheia_fora and not self.mov
                and not self.demo and self.movs and agora > self.prox_mov_solto):
            try:
                nome = _dopa.escolher({f"mov:{n}": 1.0 for n in self.movs})[4:]
                fator = _dopa.fator_frequencia("mov:")
            except Exception:
                nome, fator = random.choice(list(self.movs)), 1.0
            self.tocar_movimento(nome, agora, "sozinha")
            self.prox_mov_solto = agora + random.uniform(240, 600) * fator

    def encerrar_demo(self):
        if self.demo == "esforco":
            self.esforco = self.cpu_alta >= 3
        if self.demo in DEMO_TEDIO:
            self.tedio = None
        if self.demo == "passeio":
            self.alvo = None
        self.demo = None

    def iniciar_demo(self, nome, agora):
        self.encerrar_demo()
        self.demo, self.demo_fim = nome, agora + DEMOS[nome][1]
        if nome == "chamada":
            self.pulo_t = self.antena_t = agora
        elif nome == "antena":
            self.antena_t = agora
        elif nome == "arremesso":
            self.lanca_t = agora
        elif nome in DEMO_TEDIO:
            self.tedio, self.tedio_t, self.tedio_fim = DEMO_TEDIO[nome], agora, self.demo_fim
            self.olhar_lado = random.choice((-1, 1))
        elif nome == "passeio":       # um passinho curto para o lado que tiver mais espaço
            geo = self.tela_atual()
            lado = 1 if self.px + WM / 2 < geo.center().x() else -1
            self.alvo, self.prep_t, self.prof_passeio = (self.px + lado * 170, self.py), agora, self.prof
        log(f"demonstração: {nome}")

    def atualizar_demo(self, agora):
        # Só vale enquanto a voz fala: o estado de verdade continua sendo "falando"; aqui eu troco
        # o estado só até a próxima leitura, para o desenho e os movimentos serem os do comportamento.
        falando = self.estado == "falando"
        if not falando:
            self.did_visto = 0
        else:
            did = self.prog.get("did", 0)
            if did != self.did_visto:
                self.did_visto = did
                if self.prog.get("demo") in DEMOS:
                    self.iniciar_demo(self.prog["demo"], agora)
                elif self.prog.get("demo") in self.movs:   # 16/11: um movimento que ela aprendeu
                    self.tocar_movimento(self.prog["demo"], agora, "fala")
        if not self.demo:
            return
        if not falando or agora > self.demo_fim:
            self.encerrar_demo()
            return
        est, _, leg = DEMOS[self.demo]
        if est:
            self.estado, self.legenda = est, leg
        if self.demo == "haiku":
            self.rapida = True
        elif self.demo == "trabalho":
            self.cat = "editar"
        elif self.demo == "esforco":
            self.esforco = True
        if self.demo != "passeio":
            self.proximo_passeio = max(self.proximo_passeio, agora + 6)

    def atualizar_gesto(self, agora):
        # Falando: troca de gesto a cada frase nova (fatia da fala) ou, no máximo, a cada ~3 s.
        if self.estado != "falando" or self.dormindo:
            self.gesto, self.fatia_vista = "repouso", None
            self.gid_visto, self.marcado_ate = 0, 0.0
            return
        prog = self.prog
        # 15/11: o aviso da Sexta pode pedir um gesto (comemora quando algo ficou pronto)
        av = ler_json(BASE / "aviso.json", 30) or {}
        if av.get("fala") and av.get("gesto") in GESTOS and av.get("gid") != getattr(self, "aviso_gid", None):
            self.aviso_gid = av.get("gid")
            self.trocar_gesto(av["gesto"], agora)
            self.marcado_ate = agora + 2.4
            return
        # Bloco 2: "frase" conta as frases de verdade (antes só existia a fatia do áudio,
        # e com a voz Kore a fala inteira eram só duas fatias).
        fatia = prog.get("frase", prog.get("i"))
        nova_frase = fatia is not None and fatia != self.fatia_vista
        gid, pedido = prog.get("gid", 0), prog.get("gesto")
        if pedido and gid != self.gid_visto:  # o roteiro pediu um gesto para esta frase
            self.gid_visto = gid
            if pedido == "explica" or (pedido == "aponta" and not self.apres):
                pedido = random.choice(("explica_dir", "explica_esq"))
            if pedido in GESTOS:
                self.trocar_gesto(pedido, agora)
                self.marcado_ate = agora + 1.8          # a próxima frase não o atropela
                self.proximo_gesto = agora + 3.2
        elif self.gesto == "repouso":  # começou a falar: abre as mãos (ou só fala, se preocupada)
            self.trocar_gesto("fala" if self.emo == "preocupada" else "abre", agora)
        elif agora > self.marcado_ate and (nova_frase or agora > self.proximo_gesto):
            pesos = {**PESOS_FALA, **EMOCAO[self.emo]["pesos"]}
            opcoes = [g for g in pesos if g != self.gesto and pesos[g] > 0]
            self.trocar_gesto(random.choices(opcoes, [pesos[g] for g in opcoes])[0], agora)
        self.fatia_vista = fatia

    def trocar_gesto(self, gesto, agora):
        self.gesto, self.gesto_inicio = gesto, agora
        self.proximo_gesto = agora + random.uniform(2.2, 3.6)
        if gesto == "inclina":
            self.lado_inclina = random.choice((-1, 1))

    def atualizar_casa(self, agora):
        # Casa da Sexta: quando o visor muda num turno, a casa fica "em obra" e cada seção
        # aparece quando ela fala dela. Fora disso, tudo fica à mostra.
        if not self.casa:
            return
        v = self.casa.versao()
        try:
            turno = float((BASE / "turno.t").read_text())
        except Exception:
            turno = 0.0
        novo = v > turno and v != self.casa_apresentado
        if self.apres:
            prog = self.prog
            nsec = len(self.casa.conteudo().get("secoes", [])) or 1
            sec = prog.get("sec")
            if not prog:                       # áudio ainda sendo preparado
                r = 0
            elif prog.get("secs"):             # o roteiro marca as seções: monta na marca
                r = sec or 0
            else:                              # sem marcas: monta conforme as frases passam
                r = math.ceil((prog.get("frase", 0) + 1) / max(1, prog.get("nf", 1)) * nsec)
            self.revelado = r if self.revelado >= 999 else max(self.revelado, r)
            self.casa_visto = v
            self.casa.mudar(revelado=self.revelado, atual=sec or (self.revelado or None),
                            fala=bool(self.som), emo=self.emo)
            return
        if getattr(self, "casa_visto", None) is not None:   # a apresentação acabou
            self.casa_apresentado, self.casa_visto = self.casa_visto, None
            novo = False
        if novo and self.estado != "espera":   # o Claude ainda está trabalhando: casa em obra
            self.novo_desde = self.novo_desde or agora
            self.revelado = 0
        elif novo and self.novo_desde and agora - self.novo_desde < 45:
            self.revelado = 0                  # esperando a fala começar
        else:
            if novo:                           # turno sem fala: mostra tudo
                self.casa_apresentado = v
            self.novo_desde, self.revelado = None, 999
        self.casa.mudar(revelado=self.revelado, atual=None, fala=False, emo=self.emo)

    def atualizar_apresentacao(self):
        # Enquanto eu falo de algo que está no visor, ela vai até ele e desce apontando o conteúdo.
        # Bloco 2: ela já vai até o visor enquanto o áudio é preparado (chega antes de falar).
        fala_ativa = (self.estado == "falando" or vivo(BASE / "falando.pid")) and not self.rapida
        rect = ler_json(BASE / "apresentar.json", 600) if fala_ativa else None
        if not rect:
            self.apres = self.alvo_apres = None
            return
        if rect.get("casa"):
            # Casa da Sexta: a página conta onde está cada seção; somo à posição da página na tela.
            pos = self.casa.posicoes() if self.casa else None
            if pos:
                rect = dict(rect)
                secs = pos.get("secoes") or []
                rect["cx"] = rect["x"] + (secs[0]["x"] if secs else pos.get("x", 0))
                rect["cw"] = pos.get("w", rect["w"])
                rect["secoes"] = [rect["y"] + s["y"] for s in secs]
        if self.apres is None:
            self.apres_inicio = time.time()
        self.apres = rect
        prog = self.prog or {"i": 0, "n": 1}
        # desce conforme as frases passam (antes era por fatia do áudio: na Kore, só dois degraus)
        if prog.get("nf"):
            frac = (prog.get("frase", 0) + 0.5) / max(1, prog["nf"])
        else:
            frac = (prog.get("i", 0) + 0.5) / max(1, prog.get("n", 1))
        geo = self.tela_atual()
        for s in QGuiApplication.screens():
            if s.geometry().contains(int(rect["x"] + 20), int(rect["y"] + 20)):
                geo = s.availableGeometry()
        # profundidade: a conta é feita na escala em que ela vai estar ao chegar (s)
        s = self.prof_alvo
        y = rect["y"] + rect["h"] * (0.12 + 0.7 * frac) - (OY + 150 * ESC) * s
        # Bloco 2: se o roteiro disse a seção ({seção 2}), a mão para na altura daquele título
        secoes, sec = rect.get("secoes") or [], prog.get("sec")
        if rect.get("casa") and not sec and self.revelado and self.revelado < 999:
            sec = self.revelado                 # na casa, sem marca: aponta a seção que acabou de montar
        if isinstance(sec, int) and 1 <= sec <= len(secoes):
            ys = secoes[sec - 1]
            if rect["y"] <= ys <= rect["y"] + rect["h"]:  # só se o título estiver visível (sem rolar)
                y = ys - (OY + 146 * ESC) * s
        # v3: encosta a ponta da mão na borda do TEXTO do visor (não na borda da janela).
        cx, cw = rect.get("cx", rect["x"]), rect.get("cw", rect["w"])
        ponta_dir, ponta_esq = (OX + 158 * ESC) * s, (OX + 42 * ESC) * s   # onde fica a mão, dentro da caixa dela
        x_esq = cx - ponta_dir + 4             # do lado esquerdo do texto, apontando para a direita
        if x_esq >= geo.left():
            self.lado, x = 1, x_esq
        else:                                   # sem espaço: fica do lado direito, apontando para a esquerda
            self.lado, x = -1, cx + cw - ponta_esq - 4
        x = max(geo.left(), min(geo.right() - W * s, x))
        y = max(geo.top(), min(geo.bottom() - H * s, y))
        self.alvo_apres = self.janela_para(x, y, s)

    def acordar(self):
        self.dormindo = False
        self.feliz_ate = time.time() + 1.6
        self.ultima_atividade = time.time()

    # ---------------------------------------------------------------- mouse
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            # imersão: clicar fora dela (no escuro) devolve a tela
            if self.imersao > 0.05:
                bx, by = self.caixa_na_janela()
                s = self.prof
                q = e.position()
                if not (bx <= q.x() <= bx + W * s and by <= q.y() <= by + H * s):
                    self.sair_imersao()
                    return
            g = e.globalPosition()
            # 16/11: um clique no reator do peito abre/fecha a tela de descanso na frente
            bx, by = self.caixa_na_janela()
            s = self.prof
            q = e.position()
            cx, cy = bx + s * (OX + 100 * ESC), by + s * (OY + 156 * ESC)
            no_peito = math.hypot(q.x() - cx, q.y() - cy) <= max(12.0, 24 * ESC * s)
            self.toque = (QPointF(g), time.time(), no_peito)
            self.arrastando = QPointF(g.x() - self.px, g.y() - self.py)
            self.alvo = self.pes_alvo = None
            self.pes_antes = None if self.forcado is None else self.pes_antes
            self.ultima_atividade = time.time()
            if self.dormindo:
                self.acordar()
            self.recompensa_do_clique()

    def recompensa_do_clique(self):
        """16/11: ele clicou nela logo depois de um movimento ou de ela puxar assunto: carinho."""
        if _dopa is None:
            return
        agora = time.time()
        um = ler_json(BASE / "ultimo-movimento.json", 12) or {}
        if um.get("nome") and agora - um.get("t", 0) < 12 and not um.get("premiado"):
            _dopa.registrar(f"mov:{um['nome']}", 0.85, "clique")
            um["premiado"] = True
            (BASE / "ultimo-movimento.json").write_text(json.dumps(um), encoding="utf-8")
        imp = ler_json(BASE / "impulso.json", 90) or {}
        if imp.get("estado") in ("falado", "balao") and not imp.get("premiado") and agora - imp.get("t_feito", 0) < 90:
            _dopa.registrar(imp.get("comp", "impulso:comentar"), 0.8, "clique", imp.get("ctx", ""))
            if _ego is not None:
                _ego.lembrar("clique")
            imp["premiado"] = True
            (BASE / "impulso.json").write_text(json.dumps(imp, ensure_ascii=False), encoding="utf-8")
        if self.ap_mudou and agora - self.ap_mudou_t < 600:   # 17/11: clicou nela logo depois de ela mudar o visual
            for campo in self.ap_mudou[:3]:
                _dopa.registrar(f"aparencia:{campo}", 0.85, "clique")
            self.ap_mudou = []

    def mouseMoveEvent(self, e):
        if self.arrastando is not None:
            g = e.globalPosition()
            self.px, self.py = g.x() - self.arrastando.x(), g.y() - self.arrastando.y()
            self.aplicar_janela()

    def mouseReleaseEvent(self, e):
        if self.arrastando is not None:
            self.arrastando = None
            self.lembrar_lugar()
            self.proximo_passeio = time.time() + random.uniform(20, 40)
            if self.toque:
                p0, t0, no_peito = self.toque
                g = e.globalPosition()
                andou = math.hypot(g.x() - p0.x(), g.y() - p0.y())
                if andou < 6 and time.time() - t0 < 0.45 and no_peito:
                    # espera um tiquinho: se virar duplo clique (microfone), não abre a tela
                    self.toque_id += 1
                    meu = self.toque_id
                    QTimer.singleShot(300, lambda: self.alternar_descanso() if meu == self.toque_id else None)
                elif andou >= 6:
                    # arrastou para um monitor: aquele vira a tela dela (a da tela de descanso)
                    fx, fy = self.pes()
                    t = QGuiApplication.screenAt(QPointF(fx, fy - 10).toPoint())
                    if t and t.name() != self.mem.get("tela_descanso"):
                        self.mem["tela_descanso"] = t.name()
                        self.salvar()
                        log("tela de descanso mudou de monitor")
            self.toque = None

    def mouseDoubleClickEvent(self, e):
        self.toque_id += 1   # duplo clique é o microfone: cancela o clique no peito
        u = ctypes.windll.user32
        u.keybd_event(0x77, 0, 0, 0)
        u.keybd_event(0x77, 0, 2, 0)

    def mudar_prof_base(self, fator):
        # a preferência dele de distância (multiplica todas as outras); fica salva
        self.prof_base = 1.0 if fator is None else max(0.75, min(1.25, self.prof_base * fator))
        self.prof_passeio = 1.0
        self.mem["prof"] = round(self.prof_base, 3)
        self.salvar()

    def wheelEvent(self, e):
        d = e.angleDelta().y()
        if d and e.modifiers() & Qt.ControlModifier:
            # 16/11: Ctrl + roda = sobe ou desce um nível de profundidade inteiro
            nomes = [n for n, _, _ in NIVEIS]
            esc = [self.escala_tela() if x is None else x for _, x, _ in NIVEIS]
            atual = min(range(len(esc)), key=lambda i: abs(math.log(esc[i]) - math.log(self.prof_alvo)))
            novo = max(0, min(len(nomes) - 1, atual + (1 if d > 0 else -1)))
            self.demo_prof = None
            self.pedir_nivel(nomes[novo], None if nomes[novo] != "normal" else None)
        elif d:
            self.mudar_prof_base(1.06 if d > 0 else 1 / 1.06)

    def contextMenuEvent(self, e):
        menu = QMenu()
        quieta = self.mem.get("quieta")
        a1 = menu.addAction("Pode passear" if quieta else "Fica quietinha aqui")
        a2 = menu.addAction("Microfone (F8)")
        # profundidade: a roda do mouse em cima dela faz o mesmo
        perto = menu.addAction("Chega mais perto")
        longe = menu.addAction("Vai mais para o fundo")
        normal = menu.addAction("Distância normal")
        # 16/11: os níveis de profundidade, da janelinha à tela inteira
        sub = menu.addMenu("Profundidade")
        acoes_nivel = {sub.addAction(l): n for n, _, l in NIVEIS}
        sub.addSeparator()
        mostrar = sub.addAction("Mostrar todos os níveis")
        # 16/11: tela de descanso
        sub2 = menu.addMenu("Tela de descanso")
        agora_d = sub2.addAction("Fechar a tela de descanso" if self.descanso_modo else "Abrir agora (na frente)")
        auto_on = self.mem.get("descanso_auto", True)
        auto_a = sub2.addAction(("✓ " if auto_on else "") + "Automática (atrás das janelas)")
        mins = {sub2.addAction(("✓ " if self.mem.get("descanso_min", 3) == m else "") + f"Depois de {m} min sem usar a tela"): m
                for m in (2, 3, 5, 10)}
        central_a = menu.addAction("Fechar a central de comando" if (self.central and self.central.aberta())
                                   else "Central de comando (tela 1)")
        a3 = menu.addAction("Fechar  (para voltar: \"abre o mascote\")")
        r = menu.exec(e.globalPos())
        if r in acoes_nivel:
            self.demo_prof = None
            self.pedir_nivel(acoes_nivel[r])
            return
        if r == mostrar:
            self.iniciar_demo_prof()
            return
        if r == central_a:
            self.fechar_central() if (self.central and self.central.aberta()) else self.abrir_central()
            return
        if r == agora_d:
            self.fechar_descanso() if self.descanso_modo else self.abrir_descanso("frente")
            return
        if r == auto_a:
            self.mem["descanso_auto"] = not auto_on
            self.salvar()
            return
        if r in mins:
            self.mem["descanso_min"] = mins[r]
            self.salvar()
            return
        if r in (perto, longe, normal):
            self.mudar_prof_base({perto: 1.12, longe: 1 / 1.12, normal: None}[r])
            return
        if r == a1:
            self.mem["quieta"] = not quieta
            self.lembrar_lugar()
        elif r == a2:
            self.mouseDoubleClickEvent(e)
        elif r == a3:
            FECHADO.touch()
            log(f"fechado pelo {cfg.NOME}")
            QApplication.quit()

    # ---------------------------------------------------------------- desenho
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # fluidez: a janela só anda de 1 em 1 pixel; a fração que sobra é aplicada no
        # desenho. Assim, ao frear devagar, ela desliza em vez de dar "soquinhos".
        # profundidade v2: a caixa normal (W x H) é desenhada em escala, com os pés no lugar
        # certo. A fração de pixel já vem na conta (caixa_na_janela), então ela continua deslizando.
        s = self.prof
        bx, by = self.caixa_na_janela()
        if self.imersao > 0.003:
            # imersão: o resto da tela escurece, com uma luz suave atrás dela
            im = self.imersao
            c = QPointF(bx + W * s / 2, by + H * s * 0.55)
            raio = max(self.width(), self.height()) * 0.75
            g = QRadialGradient(c, raio)
            g.setColorAt(0.0, QColor(20, 60, 90, int(70 * im)))
            g.setColorAt(0.35, QColor(8, 16, 34, int(170 * im)))
            g.setColorAt(1.0, QColor(2, 5, 12, int(232 * im)))
            p.fillRect(self.rect(), QBrush(g))
            if im > 0.5:   # a dica de como sair, bem discreta, no rodapé
                p.setOpacity((im - 0.5) * 2 * 0.55)
                p.setPen(QColor("#9fdcf0"))
                p.setFont(QFont("Segoe UI", 9))
                p.drawText(QRectF(0, self.height() - 34, self.width(), 24), Qt.AlignCenter,
                           "clique fora de mim para voltar")
                p.setOpacity(1.0)
        p.translate(bx, by)
        p.scale(s, s)
        # janelinha: abaixo de 0,50 ela aparece dentro de um quadradinho, como quem foi para o quarto dela
        k_pip = max(0.0, min(1.0, (PIP_INI - s) / (PIP_INI - PIP_FIM)))
        if k_pip > 0:
            r = QRectF(6, 10, W - 12, H - 12)
            fundo = QLinearGradient(0, r.top(), 0, r.bottom())
            fundo.setColorAt(0, QColor(14, 30, 58, int(225 * k_pip)))
            fundo.setColorAt(1, QColor(6, 14, 30, int(235 * k_pip)))
            p.setPen(QPen(QColor(127, 243, 255, int(210 * k_pip)), 2.4 / s))
            p.setBrush(QBrush(fundo))
            p.drawRoundedRect(r, 26, 26)
            p.setPen(Qt.NoPen)   # três luzinhas no alto, como uma janelinha de verdade
            for i, cor in enumerate((QColor(255, 120, 120), QColor(255, 200, 90), QColor(120, 230, 140))):
                cor.setAlpha(int(200 * k_pip))
                p.setBrush(cor)
                p.drawEllipse(QPointF(r.left() + 20 + i * 15, r.top() + 15), 4.5, 4.5)
        if s < 1:   # longe, ela fica um pouco mais apagada; dentro da janelinha, volta a ficar nítida
            base = 0.7 + 0.3 * max(0.0, min(1.0, (s - S_MIN) / (1 - S_MIN)))
            p.setOpacity(base + (1 - base) * k_pip)
        t = time.time() - self.t0
        estado = self.estado
        periodo = 1.5 if estado == "trabalhando" else 3.2
        if estado == "pensando":  # 15/11: o Haiku pensa ágil; o Opus pensa devagar, concentrado
            periodo = 2.3 if self.rapida else 4.2
        if estado == "falando":  # Bloco 2: animada balança mais rápido, preocupada mais devagar
            periodo = EMOCAO[self.emo]["periodo"] * (0.8 if self.rapida else 1.0)
        fase = math.sin(t * 2 * math.pi / periodo)
        flut = (0 if self.dormindo else fase * 6) + self.g_sobe + self.agacha
        kp = time.time() - self.pulo_t
        if kp < 0.45:  # pulinho de "pois não?"
            flut -= 16 * math.sin(math.pi * kp / 0.45)
        if self.esforco and estado == "espera" and not self.dormindo:  # PC pesado: treme de leve
            p.translate(math.sin(t * 57) * 0.9, math.sin(t * 43) * 0.5)
        if self.alvo and self.vel > 0.3:  # passinhos: quica de leve enquanto anda
            flut -= abs(math.sin(t * 8.5)) * 3.5 * min(1.0, self.vel / 2)
        # sombra
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, int(55 - fase * 15)))
        sx = 40 * ESC * (0.9 - fase * 0.1)
        if "sombra" not in AP["esconder"]:
            p.drawEllipse(QPointF(W / 2, H - 6), sx, 5)
        # legenda (balão acima da cabeça)
        leg = self.legenda or LEGENDA_PADRAO.get(estado, "")
        if self.dormindo or self.no_espelho:   # 18/11: no espelho, sem o balão (pode ter assunto dele)
            leg = ""
        if not self.legenda and time.time() < self.leg_prof_ate:   # o nome do nível, por 2 s
            leg = self.leg_prof
        if leg:
            self.desenhar_balao(p, leg)
        k_orbe = self.orbe_k
        if k_orbe < 1:
            p.save()
            if k_orbe > 0:   # 18/11: ela se desfaz enquanto o orbe nasce
                p.setOpacity(p.opacity() * (1 - k_orbe) ** 1.6)
            p.translate(OX, OY + flut)
            p.scale(ESC, ESC)
            p.translate(100, 120)
            p.rotate(self.inclinacao + self.balanco)
            p.translate(-100, -120)
            self.desenhar_robo(p, t, estado)
            p.restore()
        if k_orbe > 0:
            p.save()
            self.desenhar_orbe(p, t, k_orbe, flut)
            p.restore()
        p.end()

    def _volume_agora(self, t):
        """O volume da fala do Claude agora (0 a 1), pelo envelope que a voz gravou; senão, uma respiração."""
        env = self.env
        alvo = 0.18 + 0.1 * math.sin(t * 2.6)
        if env and env.get("v"):
            i = int((time.time() - env.get("t0", 0)) / max(0.01, env.get("passo", 0.05)))
            if 0 <= i < len(env["v"]):
                alvo = float(env["v"][i])
        self.env_suave += (alvo - self.env_suave) * 0.35
        return self.env_suave

    def desenhar_orbe(self, p, t, k, flut):
        """18/11: o corpo do Claude. Linhas de fluxo pontilhadas numa esfera que gira (violeta, azul e
        rosa), anéis ciano de varredura e um halo que pulsa no volume da voz. Na transição, as partículas
        saem do corpo dela, giram e viram a esfera (e o contrário no fim)."""
        e = k * k * (3 - 2 * k)                       # suaviza a transição
        vol = self._volume_agora(t)
        cx, cy = OX + 100 * ESC, OY + 108 * ESC + flut * 0.4
        R = 58 * ESC * (0.55 + 0.45 * e) * (1 + 0.12 * vol)
        tilt, rot = 0.42, t * 0.9
        a_orbe = max(0.0, min(1.0, (k - 0.3) / 0.7))
        p.setPen(Qt.NoPen)
        halo = QRadialGradient(QPointF(cx, cy), R * 1.9)
        halo.setColorAt(0.0, QColor(90, 120, 255, int((70 + 90 * vol) * a_orbe)))
        halo.setColorAt(0.5, QColor(70, 60, 220, int((40 + 50 * vol) * a_orbe)))
        halo.setColorAt(1.0, QColor(20, 10, 60, 0))
        p.setBrush(QBrush(halo))
        p.drawEllipse(QPointF(cx, cy), R * 1.9, R * 1.9)
        nucleo = QRadialGradient(QPointF(cx - R * 0.2, cy - R * 0.25), R)
        nucleo.setColorAt(0.0, QColor(40, 40, 120, int(150 * a_orbe)))
        nucleo.setColorAt(1.0, QColor(8, 6, 40, int(200 * a_orbe)))
        p.setBrush(QBrush(nucleo))
        p.drawEllipse(QPointF(cx, cy), R, R)
        if a_orbe > 0:   # as linhas de fluxo pontilhadas (referência 1)
            cores = (QColor(150, 110, 255), QColor(80, 130, 255), QColor(255, 120, 210), QColor(120, 90, 255))
            n_lin, n_pt = 14, 72
            ct, st_ = math.cos(tilt), math.sin(tilt)
            for j in range(n_lin):
                base = -1.35 + 2.7 * (j + 0.5) / n_lin
                cor = QColor(cores[j % len(cores)])
                for i in range(n_pt):
                    th = i / n_pt * 2 * math.pi + rot
                    ph = base + 0.17 * math.sin(2 * th + t * 1.3 + j * 0.55)
                    x, y, z = math.cos(ph) * math.cos(th), math.sin(ph), math.cos(ph) * math.sin(th)
                    y, z = y * ct - z * st_, y * st_ + z * ct
                    frente = (z + 1) / 2
                    cor.setAlpha(int((25 + 215 * frente ** 1.5) * a_orbe * (0.7 + 0.3 * vol)))
                    p.setBrush(cor)
                    r = 0.45 + 0.85 * frente
                    p.drawEllipse(QPointF(cx + R * x, cy - R * y), r, r)
        ciano = QColor(80, 240, 255, int(220 * a_orbe))   # os anéis de varredura (referência 2)
        for n, (raio, larg, vel, abertura) in enumerate(((1.28, 2.2, 1.1, 200), (1.42, 1.4, -0.7, 120),
                                                          (1.18, 1.0, 1.8, 70))):
            pen = QPen(ciano, larg)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.save()
            p.translate(cx, cy)
            p.rotate(-25 + n * 35)
            p.scale(1.0, 0.42 + 0.1 * n)
            rr = R * raio
            p.drawArc(QRectF(-rr, -rr, 2 * rr, 2 * rr), int((t * vel * 57 + n * 90) * 16), int(abertura * e * 16))
            p.restore()
        p.setPen(QPen(QColor(80, 240, 255, int(200 * a_orbe)), 1.6))   # o anelzinho de mira
        p.setBrush(Qt.NoBrush)
        mx, my = cx - R * 0.95, cy - R * 0.8
        p.drawEllipse(QPointF(mx, my), 6 * ESC, 6 * ESC)
        p.drawArc(QRectF(mx - 10 * ESC, my - 10 * ESC, 20 * ESC, 20 * ESC), int(t * 300) % 5760, 140 * 16)
        if 0 < k < 1:   # as partículas da transição: saem do corpo dela e giram até a esfera
            p.setPen(Qt.NoPen)
            brilho = math.sin(math.pi * k)
            for th, u, ph, gira, tom in self.orbe_part:
                bx = cx + math.cos(th) * 62 * ESC * math.sqrt(u)
                by = cy + 8 * ESC + math.sin(th) * 85 * ESC * math.sqrt(u)
                ox = cx + R * math.cos(ph * 1.2) * math.cos(gira)
                oy = cy - R * math.sin(ph * 1.2)
                x, y = bx + (ox - bx) * e, by + (oy - by) * e
                ang = (1 - e) * e * 4 * 2.4 * (1 if tom > 0.5 else -1)
                dx, dy = x - cx, y - cy
                x, y = cx + dx * math.cos(ang) - dy * math.sin(ang), cy + dx * math.sin(ang) + dy * math.cos(ang)
                cor = QColor(90, 240, 255) if tom > 0.6 else QColor(160, 120, 255)
                cor.setAlpha(int(230 * brilho))
                p.setBrush(cor)
                p.drawEllipse(QPointF(x, y), 1.5, 1.5)

    def tirar_foto_do_espelho(self):
        """18/11: uma foto SÓ da janela dela (nunca da tela), sem o balão de fala."""
        try:
            self.no_espelho = True
            foto = self.grab()
            tmp = BASE / "espelho.tmp.png"
            foto.save(str(tmp), "PNG")
            os.replace(tmp, BASE / "espelho.png")
        except Exception:
            pass
        finally:
            self.no_espelho = False
            self.update()

    def desenhar_balao(self, p, texto):
        p.setFont(QFont("Segoe UI", 8))
        fm = p.fontMetrics()
        largura = min(W - 10, fm.horizontalAdvance(texto) + 18)
        linhas = 1 if fm.horizontalAdvance(texto) + 18 <= W - 10 else 2
        altura = 20 if linhas == 1 else 34
        r = QRectF((W - largura) / 2, max(2, OY - altura + 8), largura, altura)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(12, 22, 44, 215))
        p.drawRoundedRect(r, 9, 9)
        p.setPen(QColor("#e8f7ff"))
        p.drawText(r.adjusted(7, 2, -7, -2), Qt.AlignCenter | Qt.TextWordWrap, texto)

    def brilho(self, p, centro, raio, cor, intensidade=1.0):
        intensidade = min(1.6, intensidade * AP["brilho"])
        g = QRadialGradient(centro, raio * 2.4)
        c1 = QColor(cor); c1.setAlpha(min(255, int(150 * intensidade)))
        c2 = QColor(cor); c2.setAlpha(0)
        g.setColorAt(0, c1); g.setColorAt(1, c2)
        p.setPen(Qt.NoPen); p.setBrush(QBrush(g))
        p.drawEllipse(centro, raio * 2.4, raio * 2.4)
        p.setBrush(cor)
        p.drawEllipse(centro, raio, raio)

    def traco(self, p, caminho, largura=4.5, cor=None):
        cor = cor or CIANO
        brilho = QColor(cor); brilho.setAlpha(70)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(brilho, largura + 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(caminho)
        p.setPen(QPen(cor, largura, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(caminho)

    def desenhar_robo(self, p, t, estado):
        ambar = estado == "guardando"
        tom = getattr(self, "tom", 0.0)
        cor_fone = AMBAR if ambar else misturar(AZUL, BRANCO_LUZ, 0.3 * tom)
        branco = QLinearGradient(0, 30, 0, 190)
        corpo_c = QColor(AP["cor_corpo"])   # 17/11: a cor do corpo que ela escolher
        branco.setColorAt(0, corpo_c); branco.setColorAt(1, corpo_c.darker(116))
        borda = QPen(corpo_c.darker(128), 1.2)
        esc = AP["esconder"]
        self.desenhar_camadas(p, "atras")

        # Bloco 2: "sim" = a cabeça desce e sobe duas vezes; "não" = balança de um lado para o outro
        tg = time.time() - self.gesto_inicio
        self.cab_dy = self.cab_rot = self.rosto_dx = 0.0
        if estado == "falando" and self.gesto == "sim" and tg < 1.1:
            self.cab_dy = 8 * max(0.0, math.sin(2 * math.pi * tg / 0.55))
        elif estado == "falando" and self.gesto == "nao" and tg < 1.26:
            vai = math.sin(2 * math.pi * tg / 0.42) * min(1.0, (1.26 - tg) * 4)
            self.cab_rot, self.rosto_dx = vai * 4, vai * 9

        def cabeca():  # a cabeça inclina sozinha, girando em volta do pescoço
            p.translate(100, 134 + self.cab_dy); p.rotate(self.g_cab + self.cab_rot)
            p.scale(AP["cabeca"], AP["cabeca"]); p.translate(-100, -134)

        p.save(); cabeca()
        # ondas dos fones (ouvindo/guardando)
        if estado in ("ouvindo", "guardando"):
            for i, (r0, desloc) in enumerate(((14, 0.0), (24, 0.35))):
                a = (math.sin((t - desloc) * 2 * math.pi / 1.4) + 1) / 2
                c = QColor(cor_fone if ambar else misturar(CIANO, BRANCO_LUZ, 0.3 * getattr(self, "tom", 0.0))); c.setAlpha(int(220 * a))
                p.setPen(QPen(c, 3, Qt.SolidLine, Qt.RoundCap)); p.setBrush(Qt.NoBrush)
                for lado in (-1, 1):
                    cx = 100 + lado * (64 + r0)
                    path = QPainterPath(QPointF(cx, 72)); path.quadTo(QPointF(cx + lado * 9, 88), QPointF(cx, 104))
                    p.drawPath(path)
        # pensando: três pontinhos
        if estado == "pensando":
            for i, (x, y, r) in enumerate(((146, 22, 4), (158, 14, 4.5), (172, 8, 5))):
                a = (math.sin(t * 5 - i * 0.9) + 1) / 2
                c = QColor(CIANO); c.setAlpha(int(70 + 185 * a))
                p.setPen(Qt.NoPen); p.setBrush(c); p.drawEllipse(QPointF(x, y), r, r)
        # antena
        p.setPen(QPen(QColor("#cfe0ee"), 4, Qt.SolidLine, Qt.RoundCap) if "antena" not in esc else Qt.NoPen)
        ka = AP["antena"]
        topo = 40 - 13 * ka              # 17/11: a antena do tamanho que ela escolher
        p.drawLine(QPointF(100, 40), QPointF(100, topo))
        # 15/11: ocupada = a antena pulsa rápido e forte; o Opus pensando pulsa devagar e fundo
        raio_ant = 5.5
        if estado == "trabalhando":
            pulso, raio_ant = 0.6 + 0.4 * (math.sin(t * 11) + 1) / 2, 6.5
        elif estado == "pensando":
            pulso = 0.55 + 0.45 * (math.sin(t * (8 if self.rapida else 3)) + 1) / 2
        else:
            pulso = 1.0
        cor_ant = misturar(BRILHO, BRANCO_LUZ, 0.3 * tom)
        bola = QPointF(100, topo - 4)
        if "antena" in esc:
            pass
        elif AP["acessorio"] == "estrela_antena":
            self.desenhar_estrela(p, bola, raio_ant * 1.7, cor_ant, pulso)
        else:
            self.brilho(p, bola, raio_ant, cor_ant, pulso)
        fl = time.time() - self.antena_t
        if fl < 0.7 and int(fl / 0.175) % 2 == 0 and "antena" not in esc:   # duas piscadas fortes ("achei!")
            self.brilho(p, bola, 8.5, misturar(cor_ant, QColor("#ffffff"), 0.5), 1.0)
        # arco do fone
        path = QPainterPath(QPointF(36, 84)); path.quadTo(QPointF(36, 30), QPointF(100, 30))
        path.quadTo(QPointF(164, 30), QPointF(164, 84))
        p.setPen(QPen(cor_fone, 6)); p.setBrush(Qt.NoBrush)
        if "fones" not in esc:
            p.drawPath(path)
        if AP["acessorio"] == "laco" and "antena" not in esc:   # 17/11: na frente do arco, logo abaixo da bolinha da antena
            self.desenhar_laco(p, QPointF(100, topo + 3))
        p.restore()
        # braços e corpo
        p.setPen(Qt.NoPen); p.setBrush(QBrush(branco))
        aceno = math.sin(t * 9) * 18 if time.time() < self.feliz_ate else 0
        # gestos: o braço que está gesticulando "marca o ritmo" da fala com um balanço pequeno
        falando = estado == "falando"
        batida = math.sin(t * EMOCAO[self.emo]["batida"] * (1.25 if self.rapida else 1.0)) * 5 * EMOCAO[self.emo]["amp"] if falando and self.som else 0
        ang_esq = self.g_esq + aceno + (batida if self.g_esq > 50 else 0)
        ang_dir = self.g_dir - (batida if self.g_dir < -50 else 0)
        if self.apres:  # apontando para o visor (com um leve balanço, como quem explica)
            gesto = math.sin(t * 2.2) * 6
            if self.lado > 0:
                ang_dir = -100 + gesto
            else:
                ang_esq = 100 + gesto
        maos = []
        for (sx, sy), ang in (((70, 150), ang_esq), ((130, 150), ang_dir)):
            kb = AP["bracos"]
            if "bracos" not in esc:
                p.save(); p.translate(sx, sy); p.rotate(ang); p.drawEllipse(QPointF(0, 14 * kb), 9 * kb, 15 * kb); p.restore()
            a = math.radians(ang)
            maos.append((QPointF(sx - 27 * kb * math.sin(a), sy + 27 * kb * math.cos(a)), abs(ang)))
        # mãos acesas enquanto gesticula (luz suave na ponta do braço levantado)
        if falando and not self.dormindo:
            for c, abertura in maos:
                if abertura > 55:
                    self.brilho(p, c, 3.2, QColor("#9ff7ff"), min(1.0, (abertura - 55) / 40) * 0.75)
            p.setPen(Qt.NoPen); p.setBrush(QBrush(branco))
        # contar nos dedos: 1, 2, 3 luzinhas acendendo ao lado da mão direita levantada
        if falando and self.gesto == "conta" and abs(ang_dir) > 85:
            c = maos[1][0]
            n = min(3, int((time.time() - self.gesto_inicio - 0.4) / 0.55) + 1)
            for i in range(max(0, n)):
                self.brilho(p, QPointF(c.x() + 13 + i * 11, c.y() - 6), 3.0, QColor("#7ff3ff"), 0.9)
            p.setPen(Qt.NoPen); p.setBrush(QBrush(branco))
        self.ponta = None
        if self.apres:
            sx, ang = ((130, 150), ang_dir) if self.lado > 0 else ((70, 150), ang_esq)
            a = math.radians(ang)
            self.ponta = QPointF(sx[0] - 29 * math.sin(a), sx[1] + 29 * math.cos(a))
        if "corpo" not in esc:
            p.setPen(borda); p.drawRoundedRect(QRectF(70, 130, 60, 58), 28, 28)
        # reator no peito
        vel = 0.5 if estado == "falando" else 2.6
        inten = 0.6 + 0.4 * (math.sin(t * 2 * math.pi / vel) + 1) / 2
        if "reator" not in esc and "corpo" not in esc:
            self.brilho(p, QPointF(100, 156), 7, AMBAR if ambar else misturar(BRILHO, BRANCO_LUZ, 0.3 * tom), inten)
        tgc = time.time() - self.gesto_inicio
        if falando and self.gesto == "comemora" and tgc < 1.6:   # pulso de luz acolhedor saindo do peito
            for atraso in (0.0, 0.5):
                k = (tgc - atraso) / 1.1
                if 0 < k < 1:
                    c = QColor("#9ff7ff"); c.setAlpha(int(200 * (1 - k)))
                    p.setBrush(Qt.NoBrush); p.setPen(QPen(c, 3))
                    p.drawEllipse(QPointF(100, 156), 8 + 60 * k, 8 + 60 * k)
            p.setPen(Qt.NoPen); p.setBrush(QBrush(branco))
        self.desenhar_camadas(p, "corpo")
        # cabeça
        p.save(); cabeca()
        p.setPen(borda); p.setBrush(QBrush(branco))
        p.drawRoundedRect(QRectF(38, 36, 124, 100), 46, 46)
        for cx in ((36, 164) if "fones" not in esc else ()):
            p.setPen(Qt.NoPen); p.setBrush(cor_fone); p.drawEllipse(QPointF(cx, 88), 15, 15)
            p.setBrush(QColor("#e9f7ff")); p.drawEllipse(QPointF(cx, 88), 7, 7)
        # visor
        visor = QLinearGradient(0, 52, 0, 122)
        cv = QColor(AP["cor_visor"])   # 17/11: o fundo do rosto que ela escolher
        visor.setColorAt(0, cv); visor.setColorAt(1, cv.darker(260))
        p.setPen(Qt.NoPen); p.setBrush(QBrush(visor))
        p.drawRoundedRect(QRectF(52, 52, 96, 70), 32, 32)
        p.save(); p.translate(self.rosto_dx, 0)  # no "não", o rosto desliza dentro do visor
        self.desenhar_rosto(p, t, estado)
        p.restore()
        if AP["acessorio"] == "oculos":
            self.desenhar_oculos(p)
        elif AP["acessorio"] == "flor":
            self.desenhar_flor(p, QPointF(150, 44), t)
        self.desenhar_camadas(p, "cabeca")
        p.restore()
        if AP["acessorio"] == "cachecol":
            self.desenhar_cachecol(p, t)
        # 15/11: o pedido vira uma bolinha de luz que sai voando para o chat
        kl = time.time() - self.lanca_t
        if 0.3 < kl < 1.3:
            k = (kl - 0.3) / 1.0
            c0 = maos[1][0]
            for i in range(4):   # bolinha + rastro
                kk = max(0.0, k - i * 0.05)
                pos = QPointF(c0.x() + 170 * kk, c0.y() - 210 * kk + 60 * kk * kk)
                self.brilho(p, pos, 5.0 - i, QColor("#7ff3ff"), (1 - k) * (1 - i * 0.22))
        if self.tedio == "holo" and not self.dormindo:
            self.desenhar_holo(p, t)
        if self.esforco and estado == "espera" and not self.dormindo:   # "fumacinha" azul subindo
            for i in range(3):
                k = ((t * 0.7) + i / 3) % 1
                c = QColor("#7ff3ff"); c.setAlpha(int(150 * (1 - k)))
                p.setPen(Qt.NoPen); p.setBrush(c)
                p.drawEllipse(QPointF(150 + 6 * math.sin(t * 3 + i), 40 - 34 * k), 2.5 + 3 * k, 2.5 + 3 * k)
        # objeto da atividade (notebook, lupa, prancheta, globo, mão no queixo)
        if estado in ("trabalhando", "pensando") and not self.dormindo:
            self.desenhar_ferramenta(p, t, maos)
        if self.apres and self.ponta:
            self.desenhar_apontar(p, t)
        self.desenhar_camadas(p, "frente")
        if self.dormindo:
            p.setPen(QColor(200, 235, 255, 200)); p.setFont(QFont("Segoe UI", 13, QFont.Bold))
            sobe = (t * 12) % 24
            p.drawText(QPointF(150, 40 - sobe), "z"); p.setFont(QFont("Segoe UI", 10, QFont.Bold))
            p.drawText(QPointF(162, 26 - sobe * 0.6), "z")

    # ---------------------------------------------------------------- 17/11: acessórios que ela escolhe
    def desenhar_estrela(self, p, c, r, cor, intensidade=1.0, halo=True):
        if halo:
            self.brilho(p, c, r * 0.45, cor, intensidade * 0.8)
        pontas = ((0, -1), (1, 0), (0, 1), (-1, 0))
        path = QPainterPath(QPointF(c.x(), c.y() - r))
        for i in range(4):
            dx, dy = pontas[i]
            nx, ny = pontas[(i + 1) % 4]
            path.quadTo(QPointF(c.x() + (dx + nx) * r * 0.18, c.y() + (dy + ny) * r * 0.18),
                        QPointF(c.x() + nx * r, c.y() + ny * r))
        p.setPen(Qt.NoPen); p.setBrush(cor); p.drawPath(path)

    def desenhar_camadas(self, p, onde):
        """17/11: os desenhos SVG que ela mesma fez e pôs sobre si (aparencia.py: dado validado)."""
        for c, r in self.camadas_r:
            if c["onde"] != onde:
                continue
            p.save()
            p.setOpacity(p.opacity() * c["opacidade"])
            p.translate(c["x"] + c["largura"] / 2, c["y"] + c["altura"] / 2)
            p.rotate(c["girar"])
            r.render(p, QRectF(-c["largura"] / 2, -c["altura"] / 2, c["largura"], c["altura"]))
            p.restore()

    def desenhar_laco(self, p, c):
        p.setPen(QPen(QColor("#e0609f"), 1.2)); p.setBrush(QColor("#ff8fc8"))
        for lado in (-1, 1):
            p.drawPolygon(QPolygonF([c, QPointF(c.x() + lado * 15, c.y() - 8), QPointF(c.x() + lado * 15, c.y() + 8)]))
        p.setBrush(QColor("#ffd1e8")); p.drawEllipse(c, 3.2, 3.2)

    def desenhar_oculos(self, p):
        p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor("#e8f2fa"), 2.6))
        for cx in (80, 120):
            p.drawEllipse(QPointF(cx, 85), 15, 14)
        p.drawLine(QPointF(95, 83), QPointF(105, 83))
        p.setPen(Qt.NoPen); p.setBrush(QColor(255, 255, 255, 70))
        for cx in (74, 114):
            p.drawEllipse(QPointF(cx, 79), 3.5, 2.2)

    def desenhar_flor(self, p, c, t):
        p.setPen(Qt.NoPen)
        gira = t * 8
        for i in range(5):
            a = math.radians(gira + i * 72)
            p.setBrush(QColor("#ffb3d9")); p.drawEllipse(QPointF(c.x() + 7 * math.cos(a), c.y() + 7 * math.sin(a)), 5.2, 5.2)
        p.setBrush(QColor("#ffd34d")); p.drawEllipse(c, 4, 4)

    def desenhar_cachecol(self, p, t):
        p.setPen(Qt.NoPen); p.setBrush(QColor("#ff7a7a"))
        p.drawRoundedRect(QRectF(68, 128, 64, 13), 6, 6)
        bal = math.sin(t * 2.2) * 2.5
        p.drawPolygon(QPolygonF([QPointF(108, 136), QPointF(120, 136), QPointF(123 + bal, 166), QPointF(110 + bal, 166)]))
        p.setPen(QPen(QColor("#d95454"), 2))
        for y in (156, 161):
            p.drawLine(QPointF(111 + bal, y), QPointF(122 + bal, y))

    def desenhar_ferramenta(self, p, t, maos):
        # Poses de trabalho (14/11). "maos" = posição da mão esquerda e da direita.
        cat = self.cat
        md, me = maos[1][0], maos[0][0]
        luz = QColor(CIANO)
        if cat == "editar":  # notebook (o de antes), com teclinhas piscando
            p.setPen(Qt.NoPen); p.setBrush(QColor("#9fb2c4"))
            p.drawRoundedRect(QRectF(66, 150, 68, 28), 4, 4)
            p.setBrush(QColor("#0b1530")); p.drawRoundedRect(QRectF(72, 155, 56, 18), 2, 2)
            p.setPen(QPen(luz, 2.5, Qt.SolidLine, Qt.RoundCap))
            n = int(t * 6) % 4
            for i in range(3):
                largura = 18 + ((i + n) % 3) * 9
                p.drawLine(QPointF(78, 159 + i * 5), QPointF(78 + largura, 159 + i * 5))
            p.setPen(Qt.NoPen); p.setBrush(QColor("#c8d6e3"))
            p.drawPolygon(QPolygonF([QPointF(60, 196), QPointF(140, 196), QPointF(132, 178), QPointF(68, 178)]))
            if not self.acomp_fala and int(t * 7) % 2:   # as mãos "batem" nas teclas
                for x in (82, 118):
                    self.brilho(p, QPointF(x + math.sin(t * 13 + x) * 3, 187), 1.8, QColor("#9ff7ff"), 0.7)
        elif cat == "ler":   # lupa: cabo na mão direita, lente perto do rosto, brilho passeando
            c = QPointF(md.x() - 6, md.y() - 30 + math.sin(t * 1.6) * 3)
            p.setPen(QPen(QColor("#8aa4c0"), 5, Qt.SolidLine, Qt.RoundCap)); p.drawLine(md, c + QPointF(4, 15))
            vidro = QColor(CIANO); vidro.setAlpha(55)
            p.setPen(QPen(QColor("#d6e6f2"), 4.5)); p.setBrush(vidro); p.drawEllipse(c, 17, 17)
            reflexo = QPainterPath(QPointF(c.x() - 10, c.y() - 2)); reflexo.quadTo(QPointF(c.x() - 9, c.y() - 11), QPointF(c.x(), c.y() - 12))
            self.traco(p, reflexo, 2.0, QColor("#ffffff"))
        elif cat == "rodar":  # prancheta na mão esquerda; os "ok" vão aparecendo
            p.save(); p.translate(me.x() - 4, me.y() - 30); p.rotate(-8)
            p.setPen(Qt.NoPen); p.setBrush(QColor("#c9a46a")); p.drawRoundedRect(QRectF(-14, 0, 30, 38), 3, 3)
            p.setBrush(QColor("#f4f8fb")); p.drawRect(QRectF(-11, 5, 24, 30))
            p.setBrush(QColor("#8aa4c0")); p.drawRoundedRect(QRectF(-5, -3, 12, 6), 2, 2)
            feitos = int(t * 1.2) % 4
            for i in range(3):
                y = 11 + i * 8
                p.setPen(QPen(QColor("#b5c7d6"), 2)); p.drawLine(QPointF(-1, y), QPointF(10, y))
                if i < feitos:
                    ok = QPainterPath(QPointF(-8, y)); ok.lineTo(QPointF(-6, y + 2.5)); ok.lineTo(QPointF(-2, y - 3))
                    p.setPen(QPen(QColor("#2fbf71"), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); p.setBrush(Qt.NoBrush)
                    p.drawPath(ok)
            p.restore()
        elif cat == "web":    # globo de luz girando acima da mão direita
            c = QPointF(md.x() + 2, md.y() - 24 + math.sin(t * 2) * 2)
            self.brilho(p, c, 15, QColor(47, 182, 232, 120), 0.5)
            p.setBrush(Qt.NoBrush); p.setPen(QPen(luz, 1.8))
            p.drawEllipse(c, 15, 15)
            p.drawLine(QPointF(c.x() - 15, c.y()), QPointF(c.x() + 15, c.y()))
            for k in range(3):   # meridianos que giram
                w = abs(math.cos(t * 1.8 + k * math.pi / 3)) * 15
                p.drawEllipse(c, w, 15)
        elif cat == "pensar" and not self.acomp_fala and self.g_dir > 105:   # mão no queixo (por cima do rosto)
            bate = math.sin(t * 3) * 1.2 if int(t / 2.5) % 2 else 0   # "tamborila" de vez em quando
            p.setPen(QPen(QColor("#9fb8cc"), 1.6)); p.setBrush(QColor("#f4f9fd"))
            p.drawEllipse(QPointF(116, 131 + bate), 11, 8)
            p.setPen(QPen(QColor("#b9cddd"), 1.2))
            for dx in (-4, 1, 6):   # dedinhos
                p.drawLine(QPointF(116 + dx, 125 + bate), QPointF(116 + dx, 129 + bate))

    def desenhar_holo(self, p, t):
        # 15/11: painelzinho holográfico ao lado da cabeça; ela "confere o sistema" e fecha
        k = time.time() - self.tedio_t
        dur = self.tedio_fim - self.tedio_t
        abre = min(1.0, k / 0.3, max(0.0, (dur - k) / 0.3))
        if abre <= 0:
            return
        r = QRectF(184, 50, 40 * abre, 46 * abre)
        fundo = QColor("#7ff3ff"); fundo.setAlpha(int(45 * abre))
        p.setPen(QPen(QColor(127, 243, 255, int(200 * abre)), 1.4)); p.setBrush(fundo)
        p.drawRoundedRect(r, 4, 4)
        if abre > 0.8:
            p.setPen(QPen(QColor(127, 243, 255, 190), 2, Qt.SolidLine, Qt.RoundCap))
            rola = (t * 9) % 9
            for i in range(5):
                y = 58 + i * 9 - rola
                if 54 < y < 92:
                    p.drawLine(QPointF(189, y), QPointF(189 + 8 + ((i * 7) % 4) * 6, y))

    def desenhar_apontar(self, p, t):
        # Luz saindo da mão em direção ao visor + "abertura" (moldura que cresce) no começo.
        c = self.ponta
        lado = self.lado
        fim_x = c.x() + lado * 140
        feixe = QLinearGradient(c, QPointF(fim_x, c.y()))
        f1 = QColor(CIANO); f1.setAlpha(110); f2 = QColor(CIANO); f2.setAlpha(0)
        feixe.setColorAt(0, f1); feixe.setColorAt(1, f2)
        abre = 18 + 6 * math.sin(t * 3)
        p.setPen(Qt.NoPen); p.setBrush(QBrush(feixe))
        p.drawPolygon(QPolygonF([c, QPointF(fim_x, c.y() - abre * 2.2), QPointF(fim_x, c.y() + abre * 2.2)]))
        self.brilho(p, c, 4.5, QColor("#9ff7ff"), 0.6 + 0.4 * (math.sin(t * 8) + 1) / 2)
        idade = time.time() - self.apres_inicio
        if idade < 1.2:  # animação de "abrir o visor"
            k = idade / 1.2
            cor = QColor(CIANO); cor.setAlpha(int(230 * (1 - k)))
            p.setBrush(Qt.NoBrush); p.setPen(QPen(cor, 2.5))
            larg, alt = 20 + 90 * k, 14 + 60 * k
            x0 = c.x() + (8 if lado > 0 else -8 - larg)
            p.drawRoundedRect(QRectF(x0, c.y() - alt / 2, larg, alt), 6, 6)

    def desenhar_rosto(self, p, t, estado):
        ox, oy = self.olhar.x(), self.olhar.y()
        piscando = time.time() < self.pisco_ate
        feliz = time.time() < self.feliz_ate
        def olhos_ovais(rx, ry, y=84, dx=0.0):
            k, forma = AP["olhos"], AP["formato_olhos"]   # 17/11: o tamanho e o formato que ela escolher
            rx, ry = rx * k, ry * k
            if forma == "redondos":
                rx = ry = (rx + ry) / 2
            for cx in (80, 120):
                c = QPointF(cx + ox + dx, y + oy)
                altura = ry * (0.12 if piscando else 1)
                g = QRadialGradient(c, ry * 2.2)
                c1 = QColor(CIANO); c1.setAlpha(120); c2 = QColor(CIANO); c2.setAlpha(0)
                g.setColorAt(0, c1); g.setColorAt(1, c2)
                p.setPen(Qt.NoPen); p.setBrush(QBrush(g)); p.drawEllipse(c, rx * 2, ry * 1.8)
                p.setBrush(CIANO)
                if piscando or forma in ("ovais", "redondos"):
                    p.drawEllipse(c, rx, altura)
                elif forma == "meia_lua":     # metade de cima, como quem sorri com os olhos
                    path = QPainterPath(QPointF(c.x() - rx * 1.1, c.y() + ry * 0.35))
                    path.cubicTo(QPointF(c.x() - rx * 1.1, c.y() - ry * 1.1), QPointF(c.x() + rx * 1.1, c.y() - ry * 1.1),
                                 QPointF(c.x() + rx * 1.1, c.y() + ry * 0.35))
                    path.closeSubpath(); p.drawPath(path)
                elif forma == "losango":
                    p.drawPolygon(QPolygonF([QPointF(c.x(), c.y() - ry), QPointF(c.x() + rx, c.y()),
                                             QPointF(c.x(), c.y() + ry), QPointF(c.x() - rx, c.y())]))
                elif forma == "estrela":
                    self.desenhar_estrela(p, c, ry * 1.1, CIANO, 1.0, halo=False)
        def olhos_sorrindo(abre=1.0, so=(80, 120)):
            for cx in so:
                path = QPainterPath(QPointF(cx - 9 * abre, 88))
                path.quadTo(QPointF(cx, 88 - 14 * abre), QPointF(cx + 9 * abre, 88))
                self.traco(p, path)
        # Bloco 2: o rosto de quem fala depende da emoção da resposta
        emo = self.emo if estado == "falando" else None
        tg = time.time() - self.gesto_inicio
        if self.dormindo:
            for cx in (80, 120):
                path = QPainterPath(QPointF(cx - 8, 86)); path.lineTo(QPointF(cx + 8, 86))
                self.traco(p, path, 4)
        elif emo and self.gesto == "pisca" and 0.25 < tg < 1.0:  # piscadinha: um olho fecha, o outro sorri
            path = QPainterPath(QPointF(111, 85)); path.lineTo(QPointF(129, 85))
            self.traco(p, path, 4.5)
            olhos_sorrindo(so=(80,))
        elif emo and self.gesto == "comemora" and tg < 2.2:   # sorriso enorme
            olhos_sorrindo(1.35)
        elif estado == "espera" and self.tedio == "boceja":   # olhos quase fechando
            for cx in (80, 120):
                path = QPainterPath(QPointF(cx - 8, 86)); path.quadTo(QPointF(cx, 91), QPointF(cx + 8, 86))
                self.traco(p, path, 3.5)
        elif estado == "espera" and self.esforco:           # esforço: > <
            for a, b, c in (((72, 77), (86, 84), (72, 91)), ((128, 77), (114, 84), (128, 91))):
                path = QPainterPath(QPointF(*a)); path.lineTo(QPointF(*b)); path.lineTo(QPointF(*c))
                self.traco(p, path)
        elif estado == "pensando" and self.rapida:          # o Haiku processando: olhos estreitos
            olhos_ovais(7.5, 5)
        elif emo == "neutra":            # olhos abertos, atentos
            olhos_ovais(7, 10)
        elif emo == "pensativa":         # olhos menores, olhando para cima e para o lado
            olhos_ovais(6, 8, y=77, dx=3)
        elif emo == "preocupada":        # olhos abertos + sobrancelhas caídas para fora
            olhos_ovais(7, 9, y=87)
            for a, b in (((70, 73), (88, 67)), ((130, 73), (112, 67))):
                path = QPainterPath(QPointF(a[0] + ox, a[1] + oy)); path.lineTo(QPointF(b[0] + ox, b[1] + oy))
                self.traco(p, path, 3.5)
        elif emo == "animada":           # sorriso maior + duas faíscas piscando
            olhos_sorrindo(1.15)
            for i, (x, y) in enumerate(((62, 66), (139, 63))):
                r = 2.2 + 3.2 * (math.sin(t * 6 + i * 2.1) + 1) / 2
                path = QPainterPath(QPointF(x - r, y)); path.lineTo(QPointF(x + r, y))
                path.moveTo(QPointF(x, y - r)); path.lineTo(QPointF(x, y + r))
                self.traco(p, path, 2.2)
        elif estado == "falando" or feliz:
            olhos_sorrindo()
        elif estado in ("trabalhando", "pensando") and self.acomp_fala:
            olhos_ovais(7, 10)            # o acompanhante fala: ela olha para você
        elif estado == "trabalhando" and self.cat == "ler":
            olhos_ovais(7.5, 10.5, y=82, dx=4)    # olhando pela lupa
        elif estado == "trabalhando" and self.cat == "rodar":
            olhos_ovais(6.5, 9, y=88, dx=-4)      # olhando a prancheta
        elif estado == "trabalhando" and self.cat == "web":
            olhos_ovais(6.5, 9, y=77, dx=4)       # olhando o globo
        elif estado == "trabalhando":
            for a, b, c in (((72, 77), (86, 84), (72, 91)), ((128, 77), (114, 84), (128, 91))):
                path = QPainterPath(QPointF(*a)); path.lineTo(QPointF(*b)); path.lineTo(QPointF(*c))
                self.traco(p, path)
        elif estado == "pensando":
            olhos_ovais(6, 8, y=76, dx=3)
        elif estado in ("ouvindo", "guardando"):
            olhos_ovais(8.5, 12, y=83)
        else:
            olhos_ovais(7, 10)
        # boca
        if estado == "falando" and self.som:  # a boca só mexe com o som tocando
            p.setPen(Qt.NoPen); p.setBrush(CIANO)
            alto = {"animada": 15, "preocupada": 8, "pensativa": 9}.get(self.emo, 12)
            for i, x in enumerate((87, 93, 99, 105, 111)):
                h = 6 + alto * (math.sin(t * 14 + i * 1.3) + 1) / 2
                p.drawRoundedRect(QRectF(x, 106 - h / 2, 4, h), 2, 2)
        elif estado in ("trabalhando", "pensando") and self.acomp_fala:  # fala do acompanhante
            p.setPen(Qt.NoPen); p.setBrush(CIANO)
            for i, x in enumerate((90, 96, 102, 108)):
                h = 4 + 8 * (math.sin(t * 13 + i * 1.4) + 1) / 2
                p.drawRoundedRect(QRectF(x, 106 - h / 2, 3.5, h), 1.75, 1.75)
        elif self.dormindo:
            pass
        elif estado == "espera" and self.tedio == "boceja":   # bocejo: boca em "O" que abre e fecha
            k = (time.time() - self.tedio_t) / 1.9
            h = 2 + 9 * math.sin(math.pi * max(0.0, min(1.0, k)))
            p.setPen(Qt.NoPen); p.setBrush(CIANO); p.drawEllipse(QPointF(100, 107), 5, h / 1.6)
        elif estado == "espera" and self.esforco:             # esforço: boca apertada
            path = QPainterPath(QPointF(93, 106)); path.lineTo(QPointF(107, 106))
            self.traco(p, path, 3.5)
        elif estado in ("espera", "ouvindo") or feliz:
            path = QPainterPath(QPointF(92, 104)); path.quadTo(QPointF(100, 111), QPointF(108, 104))
            self.traco(p, path, 3.5)
        else:
            path = QPainterPath(QPointF(93, 106)); path.lineTo(QPointF(107, 106))
            self.traco(p, path, 3.5)

def main():
    if vivo(PIDF) and PIDF.read_text().strip() != str(os.getpid()):
        return
    PIDF.write_text(str(os.getpid()))
    app = QApplication(sys.argv)
    m = Mascote()
    m.show()
    log("aberto (v4.3, tela de descanso)")
    app.exec()
    if PIDF.exists() and PIDF.read_text().strip() == str(os.getpid()):
        PIDF.unlink(missing_ok=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"erro fatal: {e!r}")
