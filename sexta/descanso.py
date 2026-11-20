# Tela de descanso da Sexta-Feira. Criado em 16/11/2026, de madrugada, a pedido do usuário:
# "uma espécie de protagonista da tela", um holograma "simpático e tecnológico" criado por ela,
# com a hora, os avisos e os prazos. Primeiro passo da ideia do painel sci-fi.
#
# 16/11, versão 2 (pedido do usuário): visual da referência que ele mandou (moldura com cantoneiras,
# relógio fino com régua dos segundos, cartões com selos, anel de dias), fundo animado no clima da
# Discagem Rápida do Opera GX (fitas de luz, estrelas, colunas de letras caindo) e uma BARRA para
# mandar pedidos à Sexta do chat sem abrir o Obsidian.
#
# Dois jeitos de aparecer (quem decide é a mascote, mascote.py):
#   - fundo: automático, ATRÁS de todas as janelas, no monitor dela, depois de alguns minutos sem o
#     mouse passar por lá. Só aparece onde não tem janela por cima. Um clique na barra traz para a frente.
#   - frente: um clique no reator do peito dela. Fica por cima de tudo naquele monitor, com a barra pronta.
# A barra entrega o texto na conversa do Claudian que está aberta (em fila: se a Sexta do chat estiver
# ocupada, ela recebe quando terminar). Se não der, o recado vira uma nota na pasta Entrada.
# Lê só a nota Avisos.md. Nada sai do PC. Finanças ficam de fora por enquanto.

import base64, ctypes, datetime, math, pathlib, random, re, shutil, subprocess, threading, time
import sys as _sys, pathlib as _pl  # 16/11: com "-P" o Python não procura na pasta do arquivo; sem isto, nada abria
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg
try:   # 16/11 (OpenJarvis): o registro nunca guarda CPF, telefone, cartão, chave ou senha
    from seguranca import mascarar as _mascarar
except Exception:
    _mascarar = lambda s: s

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath,
                           QPalette, QPen, QPixmap, QPolygonF, QRadialGradient, QBrush)
from PySide6.QtWidgets import QLineEdit, QWidget

CORTEX = cfg.PASTA
NOTA = cfg.nota("avisos")
ENTRADA = cfg.nota("entrada")
RE_ITEM = re.compile(r"^\s*-\s*\[( |x|X)\]\s*(\d{4}-\d{2}-\d{2})\s*[·|—-]\s*(.+?)\s*$")
DIAS_PARADA = 2
LOG = pathlib.Path.home() / ".sexta-voz" / "log.txt"

CIANO = QColor("#7ff3ff")
AZUL = QColor("#2fb6e8")
AMBAR = QColor("#f2bd6b")
CORAL = QColor("#ff8a6b")
TEXTO = QColor("#eaf6ff")
SUAVE = QColor("#9fb9d0")
TITULO = QColor("#6fd6f2")

DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]
LETRAS = "abcdefghijklmnopqrstuvxyz0123456789□□"

F_TITULO = ("Bahnschrift", "Segoe UI")
F_TEXTO = ("Segoe UI Variable Text", "Segoe UI")
F_RELOGIO = ("Segoe UI Variable Display Light", "Segoe UI Light", "Segoe UI")


def log(msg):
    try:
        msg = _mascarar(str(msg))
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%d/%m %H:%M:%S')} [descanso] {msg}\n")
    except Exception:
        pass


def fonte(tam, peso=QFont.Normal, nomes=F_TEXTO, espaco=0.0):
    f = QFont(nomes[0])
    f.setFamilies(list(nomes))
    f.setPixelSize(max(6, int(tam)))
    f.setWeight(peso)
    if espaco:
        f.setLetterSpacing(QFont.AbsoluteSpacing, espaco)
    return f


def cor(c, a):
    c = QColor(c)
    c.setAlpha(max(0, min(255, int(a))))
    return c


def ler_avisos():
    """[(tipo, data, assunto, passo)] dos itens ainda abertos da nota de avisos."""
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
            texto = m.group(3)
            assunto, _, passo = texto.partition("→")
            itens.append((tipo, d, assunto.strip(), passo.strip()))
    return itens


# ---------------------------------------------------------------- entregar o pedido ao chat
def _obsidian(js):
    exe = shutil.which("obsidian")
    if not exe:
        return None
    try:
        r = subprocess.run([exe, f"vault={cfg.NOME_COFRE}", "eval", f"code={js}"], capture_output=True, text=True,
                           encoding="utf-8", errors="ignore", timeout=20, creationflags=0x08000000)
    except Exception as e:
        log(f"linha de comando do Obsidian falhou: {type(e).__name__}")
        return None
    achados = re.findall(r"^=>\s*(.*)$", r.stdout or "", re.M)
    return achados[-1].strip() if achados else ""


def entregar_ao_chat(texto):
    """Põe o pedido na fila da conversa aberta do Claudian. Devolve "ok", "fila" ou None (falhou)."""
    b64 = base64.b64encode(texto.encode("utf-8")).decode("ascii")   # só letras: nada quebra a linha de comando
    js = ("(()=>{try{const m=app.plugins.plugins['realclaudian'].sessionMessaging;"
          "const id=m.getActiveSessionId();if(!id)return 'SEM_CONVERSA';"
          f"const t=new TextDecoder().decode(Uint8Array.from(atob('{b64}'),c=>c.charCodeAt(0)));"
          "window.__sextaTela='enviando';"
          "m.sendAsUser(id,{text:t}).then(()=>{window.__sextaTela='ok'})"
          ".catch(e=>{window.__sextaTela='erro '+(e&&e.message)});"
          "return 'PEDIDO'}catch(e){return 'ERRO '+e.message}})()")
    r = _obsidian(js)
    if r != "PEDIDO":
        log(f"barra: o chat não aceitou ({(r or 'sem resposta')[:60]})")
        return None
    for _ in range(10):
        time.sleep(0.6)
        s = _obsidian("String(window.__sextaTela||'')") or ""
        if s.startswith("ok"):
            return "ok"
        if s.startswith("erro"):
            log(f"barra: erro ao entregar ({s[:60]})")
            return None
    return "fila"


def guardar_na_entrada(texto):
    ENTRADA.mkdir(parents=True, exist_ok=True)
    agora = datetime.datetime.now()
    arq = ENTRADA / f"Recado da tela de descanso - {agora:%Y-%m-%d %H%M%S}.md"
    arq.write_text(f"Recado digitado pelo {cfg.NOME} na tela de descanso em {agora:%d/%m/%Y às %H:%M} "
                   f"(não deu para entregar direto no chat):\n\n> {texto}\n", encoding="utf-8")


class Campo(QLineEdit):
    """A caixa de texto da barra. Enter envia, Esc fecha a tela de descanso."""
    def __init__(self, dono):
        super().__init__(dono)
        self.dono = dono
        self.setFrame(False)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QLineEdit{background:transparent;border:none;color:#eaf6ff;"
                           "selection-background-color:#2fb6e8;}")
        pal = self.palette()
        pal.setColor(QPalette.PlaceholderText, QColor(143, 185, 210, 150))
        self.setPalette(pal)
        self.setPlaceholderText("Fale com a Sexta…")
        self.setMaxLength(2000)
        self.hide()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.dono.ao_clicar()
            return
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.dono.enviar()
            return
        super().keyPressEvent(e)


def coberta_por_janela(meu):
    """17/11 (otimização): no fundo, se uma janela maximizada ou em tela cheia cobre o monitor dela,
    ninguém vê a tela de descanso, então ela não precisa se desenhar. Olha só o retângulo da janela da
    frente (nunca o título). Falhou? Diz que não está coberta, e ela desenha como antes."""
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        u.GetForegroundWindow.restype = ctypes.c_void_p
        u.MonitorFromWindow.restype = ctypes.c_void_p
        u.MonitorFromWindow.argtypes = (ctypes.c_void_p, wintypes.DWORD)
        u.IsZoomed.argtypes = (ctypes.c_void_p,)
        u.GetWindowRect.argtypes = (ctypes.c_void_p, ctypes.POINTER(wintypes.RECT))
        u.GetMonitorInfoW.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
        fg = u.GetForegroundWindow()
        if not fg or fg == meu:
            return False
        mon = u.MonitorFromWindow(meu, 2)
        if u.MonitorFromWindow(fg, 2) != mon:
            return False
        if u.IsZoomed(fg):
            return True

        class MI(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
        mi = MI()
        mi.cb = ctypes.sizeof(MI)
        r = wintypes.RECT()
        if not u.GetMonitorInfoW(mon, ctypes.byref(mi)) or not u.GetWindowRect(fg, ctypes.byref(r)):
            return False
        m = mi.rcMonitor
        return r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom
    except Exception:
        return False


class TelaDescanso(QWidget):
    def __init__(self, ao_clicar, onde_ela, mascote=None):
        """ao_clicar(): a mascote fecha · onde_ela(): ponto global do peito dela (ou None) · mascote: ela."""
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle("Sexta-Feira · tela de descanso")
        self.ao_clicar, self.onde_ela, self.m = ao_clicar, onde_ela, mascote
        self.frente = False
        self.t_ini = 0.0
        self.saindo = None
        self.urgentes, self.proximos = [], []
        self.prox_leitura = 0.0
        self.campo = Campo(self)
        self.status = None                 # (texto, cor, até quando)
        self.envio = None                  # resultado vindo da thread de envio
        self.enviando = False
        self.cache_fundo = None
        self.cache_relogio = None
        rng = random.Random(7)
        self.rng = rng
        self.estrelas = [(rng.random(), rng.random(), rng.uniform(0.5, 1.5), rng.uniform(0.4, 1.6),
                          rng.uniform(0, 6.28)) for _ in range(170)]
        self.colunas = []
        xs = ([rng.uniform(0.938, 0.995) for _ in range(7)] + [rng.uniform(0.005, 0.06) for _ in range(3)]
              + [rng.uniform(0.1, 0.9) for _ in range(7)])
        for i, x in enumerate(xs):
            n = rng.randint(8, 18)
            self.colunas.append({"x": x, "v": rng.uniform(22, 60), "off": rng.uniform(0, 900), "n": n,
                                 "a": 70 if i < 10 else 26, "c": [rng.choice(LETRAS) for _ in range(n)]})
        self.particulas = [(rng.random(), rng.uniform(-0.9, 0.9), rng.uniform(0.06, 0.16), rng.uniform(1, 2.4))
                           for _ in range(34)]
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tique)

    # ------------------------------------------------------------ geometria
    def moldura_r(self):
        w, h = self.width(), self.height()
        return QRectF(w * 0.295, h * 0.105, w * 0.637, h * 0.74)

    def barra_r(self):
        w, h = self.width(), self.height()
        R = self.moldura_r()
        bw = R.width() * 0.70
        return QRectF(R.center().x() - bw / 2, h * 0.872, bw, h * 0.056)

    def botao_r(self):
        b = self.barra_r()
        d = b.height() * 0.72
        return QRectF(b.right() - d - b.height() * 0.14, b.center().y() - d / 2, d, d)

    def resizeEvent(self, e):
        b = self.barra_r()
        esq = b.left() + b.height() * 1.05
        self.campo.setGeometry(int(esq), int(b.top() + 2), int(self.botao_r().left() - esq - 10), int(b.height() - 4))
        self.campo.setFont(fonte(b.height() * 0.36))
        self.cache_fundo = self.cache_relogio = None

    # ------------------------------------------------------------ abrir e fechar
    def aberta(self):
        return self.isVisible() and self.saindo is None

    def mostrar(self, geo, frente):
        # atrás das janelas SEM o "StaysOnBottom" do Qt: ele joga a janela para baixo até do papel
        # de parede, e ela some (visto no teste de 16/11). O fundo é feito em ficar_no_fundo().
        # Na frente ela aceita o teclado (para a barra); no fundo, não rouba o foco de ninguém.
        flags = (Qt.FramelessWindowHint | Qt.Tool
                 | (Qt.WindowStaysOnTopHint if frente else Qt.WindowDoesNotAcceptFocus))
        estava = self.isVisible() and self.saindo is None
        if not self.isVisible() or frente != self.frente:
            self.setWindowFlags(flags)
            self.setAttribute(Qt.WA_ShowWithoutActivating, not frente)
        self.frente, self.saindo = frente, None
        self.setGeometry(geo)
        if not estava:
            self.t_ini = time.time()
        if not frente:
            self.campo.hide()
        self.ler()
        self.show()
        if frente:
            self.raise_()
        else:
            self.ficar_no_fundo()
        self.prox_fundo = time.time() + 3
        self.timer.start(40 if frente else 66)

    def ficar_no_fundo(self):
        """Coloca a janela logo acima da área de trabalho (papel de parede) e abaixo de todas as outras."""
        try:
            u = ctypes.windll.user32
            u.FindWindowW.restype = ctypes.c_void_p
            u.GetWindow.restype = ctypes.c_void_p
            meu = ctypes.c_void_p(int(self.winId()))
            prog = u.FindWindowW("Progman", None)
            if not prog:
                return
            acima = u.GetWindow(ctypes.c_void_p(prog), 3)      # GW_HWNDPREV: a janela logo acima do desktop
            if not acima or acima == meu.value:
                return
            u.SetWindowPos(meu, ctypes.c_void_p(acima), 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0010)
        except Exception:
            pass

    def focar_campo(self):
        self.campo.show()
        self.activateWindow()
        try:
            ctypes.windll.user32.SetForegroundWindow(ctypes.c_void_p(int(self.winId())))
        except Exception:
            pass
        self.campo.setFocus(Qt.OtherFocusReason)

    def esconder(self):
        if self.isVisible() and self.saindo is None:
            self.saindo = time.time()
            self.campo.clearFocus()
            self.campo.hide()

    def tique(self):
        agora = time.time()
        if self.saindo is not None and agora - self.saindo > 0.45:
            self.hide()
            self.timer.stop()
            self.saindo = None
            return
        if agora > self.prox_leitura:
            self.ler()
        if not self.frente and agora > getattr(self, "prox_fundo", 0):
            self.prox_fundo = agora + 3
            self.ficar_no_fundo()        # se algo a puxou para cima, volta para o fundo
        if self.frente and self.saindo is None and not self.campo.isVisible() and agora - self.t_ini > 0.9:
            self.focar_campo()           # o holograma terminou de aparecer: a barra fica pronta
        if self.envio is not None:
            res, self.envio = self.envio, None
            self.enviando = False
            if res == "ok":
                self.status = ("Entregue. A Sexta do chat já recebeu.", CIANO, agora + 7)
            elif res == "fila":
                self.status = ("Na fila: a Sexta do chat recebe assim que terminar.", CIANO, agora + 7)
            elif res == "entrada":
                self.status = ("O chat não respondeu. Guardei o recado na pasta Entrada.", AMBAR, agora + 9)
            else:
                self.status = ("Não consegui entregar nem guardar. O texto voltou para a barra.", CORAL, agora + 9)
            volta = getattr(self, "_devolver", None)
            if res == "falhou" and volta and not self.campo.text():
                self.campo.setText(volta)
            self._devolver = None
            if res in ("ok", "fila") and self.m is not None:
                self.m.lanca_t = agora    # ela "arremessa" o pedido, como faz com a Sexta rápida
        if not self.frente:              # 17/11 (otimização): coberta no fundo, não se desenha
            if agora > getattr(self, "prox_cob", 0):
                self.prox_cob = agora + 1
                self.coberta = coberta_por_janela(int(self.winId()))
            if getattr(self, "coberta", False):
                return
        for c in self.colunas:           # as letras que caem trocam de vez em quando
            if self.rng.random() < 0.08:
                c["c"][self.rng.randrange(c["n"])] = self.rng.choice(LETRAS)
        self.redesenhar()

    def redesenhar(self):
        self.update()       # a central de comando troca isto para não redesenhar o texto da nota à toa

    def mousePressEvent(self, e):
        pt = e.position()
        if self.barra_r().adjusted(-6, -6, 6, 6).contains(pt):
            if not self.frente:
                if self.m is not None:
                    self.m.abrir_descanso("frente")   # traz para a frente; a barra fica pronta logo depois
                return
            if self.botao_r().contains(pt):
                self.enviar()
            else:
                self.focar_campo()
            return
        self.ao_clicar()

    # ------------------------------------------------------------ enviar pedido
    def enviar(self):
        texto = " ".join(self.campo.text().split())
        if not texto or self.enviando:
            return
        self.enviando = True
        self.campo.clear()
        self.status = ("Enviando para a Sexta do chat…", SUAVE, time.time() + 30)
        pedido = f"(Pedido pela tela de descanso) {texto}"

        def trabalho():
            res = None
            try:
                res = entregar_ao_chat(pedido)
            except Exception as e:
                log(f"barra: erro {type(e).__name__}")
            if res is None:
                try:
                    guardar_na_entrada(texto)
                    res = "entrada"
                except Exception as e:
                    log(f"barra: não consegui guardar na Entrada ({type(e).__name__})")
                    res = "falhou"
                    self._devolver = texto
            log(f"barra: pedido {res}")      # (o texto do pedido não vai para o registro)
            self.envio = res
        threading.Thread(target=trabalho, daemon=True).start()

    # ------------------------------------------------------------ dados
    def ler(self):
        self.prox_leitura = time.time() + 20
        hoje = datetime.date.today()
        urg, prox = [], []
        for tipo, d, assunto, passo in ler_avisos():
            if tipo == "prazo":
                falta = (d - hoje).days
                if falta < 0:
                    urg.append((0, d, "VENCEU", CORAL, assunto, passo))
                elif falta == 0:
                    urg.append((1, d, "HOJE", AMBAR, assunto, passo))
                elif falta == 1:
                    urg.append((2, d, "AMANHÃ", CIANO, assunto, passo))
                else:
                    chip = f"EM {falta} DIAS" if falta <= 14 else d.strftime("%d/%m")
                    prox.append((falta, d, chip, CIANO, assunto, passo))
            else:
                dias = (hoje - d).days
                if dias >= DIAS_PARADA:
                    urg.append((3 + 1 / (dias + 1), d, f"PARADO {dias} DIAS", CIANO, assunto, passo))
        urg.sort(key=lambda x: (x[0], x[1]))
        prox.sort(key=lambda x: x[0])
        self.urgentes, self.proximos = urg, prox

    def frases(self):
        """[(parte em negrito, resto)]"""
        h = datetime.datetime.now().hour
        oi = f"Bom dia, {cfg.NOME}." if 5 <= h < 12 else f"Boa tarde, {cfg.NOME}." if 12 <= h < 18 else f"Boa noite, {cfg.NOME}."
        vencidos = sum(1 for u in self.urgentes if u[2] == "VENCEU")
        hoje = sum(1 for u in self.urgentes if u[2] == "HOJE")
        lista = []
        if vencidos:
            lista.append((oi, f"Tem {vencidos} coisa{'s' if vencidos > 1 else ''} vencida. Quando der, a gente olha junto."))
        elif hoje:
            lista.append((oi, f"Hoje tem {hoje} prazo{'s' if hoje > 1 else ''}. Estou de olho."))
        else:
            lista.append((oi, "Nada pegando fogo por aqui."))
        lista.append(("", "Estou cuidando dos seus prazos enquanto você descansa."))
        lista.append(("Pode falar comigo:", "é só escrever na barra aqui embaixo."))
        if h >= 23 or h < 5:
            lista.append(("", "Já é tarde. Dormir também é produtividade."))
        if self.proximos:
            lista.append(("Próximo prazo:", f"{self.proximos[0][4]}."))
        return lista

    # ------------------------------------------------------------ desenho
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        agora = time.time()
        t = agora - self.t_ini
        w, h = self.width(), self.height()
        sai = 1.0 if self.saindo is None else max(0.0, 1 - (agora - self.saindo) / 0.45)

        p.drawPixmap(0, 0, self.fundo_base(w, h))
        kf = min(1.0, t / 0.6) * sai
        p.setOpacity(kf)
        self.estrelas_(p, w, h, agora)
        self.ondas(p, w, h, agora)
        self.letras(p, w, h, agora)

        R = self.moldura_r()
        k = min(1.0, t / 0.9)
        k = k * k * (3 - 2 * k)
        pisca = 0.8 + 0.2 * math.sin(t * 47) if t < 0.6 else 1.0
        op = k * pisca * sai

        p.setOpacity(1.0)
        self.feixe(p, R, w, h, agora, op)

        if t > 1.6:
            # depois de aparecer, o painel quase não muda: vai de uma imagem pronta (refeita a cada
            # minuto ou quando os avisos mudam) e só a régua, a frase e os losangos são desenhados ao vivo.
            p.setOpacity(op)
            orig, pix = self.pix_painel(R, t)
            p.drawPixmap(orig, pix)
            self.vivo(p, R, agora, t)
        else:
            p.save()
            p.setClipRect(QRectF(0, 0, w, R.top() + (R.height() + 40) * k))
            p.setOpacity(op)
            self.moldura(p, R, agora)
            self.relogio(p, R, t)
            self.vivo(p, R, agora, t)
            self.cartoes(p, R, t)
            p.restore()

        if k < 1:
            yk = R.top() + (R.height() + 40) * k
            p.setOpacity(sai)
            p.setPen(QPen(QColor(160, 250, 255, int(200 * (1 - k))), 2))
            p.drawLine(QPointF(R.left() - 10, yk), QPointF(R.right() + 10, yk))

        p.setOpacity(op)
        self.cabecalho(p, R, agora)
        kb = max(0.0, min(1.0, (t - 0.6) / 0.4)) * sai
        p.setOpacity(kb)
        self.barra(p, agora)
        self.rodape(p, w, h, agora)
        p.end()

    def pix_painel(self, R, t):
        chave = (round(R.width()), round(R.height()), datetime.datetime.now().strftime("%H:%M"),
                 repr(self.urgentes), repr(self.proximos))
        c = getattr(self, "cache_painel", None)
        if c is not None and c[0] == chave:
            return c[1], c[2]
        m = 14
        orig = QPointF(R.left() - m, R.top() - m)
        dpr = self.devicePixelRatioF()
        pix = QPixmap(int((R.width() + 2 * m) * dpr), int((R.height() + 2 * m) * dpr))
        pix.setDevicePixelRatio(dpr)
        pix.fill(Qt.transparent)
        q = QPainter(pix)
        q.setRenderHint(QPainter.Antialiasing)
        q.setRenderHint(QPainter.TextAntialiasing)
        q.translate(-orig.x(), -orig.y())
        self.moldura(q, R, 0.0, losangos=False)
        self.relogio(q, R, 99.0)
        self.cartoes(q, R, 99.0)
        q.end()
        self.cache_painel = (chave, orig, pix)
        return orig, pix

    # --- fundo animado (clima da Discagem Rápida do Opera GX)
    def fundo_base(self, w, h):
        if self.cache_fundo is not None and self.cache_fundo[0] == (w, h):
            return self.cache_fundo[1]
        dpr = self.devicePixelRatioF()
        pix = QPixmap(int(w * dpr), int(h * dpr))
        pix.setDevicePixelRatio(dpr)
        q = QPainter(pix)
        g = QRadialGradient(QPointF(w * 0.55, h * 0.45), max(w, h) * 0.85)
        g.setColorAt(0, QColor(13, 31, 60))
        g.setColorAt(0.55, QColor(6, 15, 33))
        g.setColorAt(1, QColor(2, 5, 13))
        q.fillRect(QRectF(0, 0, w, h), QBrush(g))
        g2 = QRadialGradient(QPointF(w * 0.9, h * 0.85), w * 0.45)
        g2.setColorAt(0, QColor(30, 80, 200, 40))
        g2.setColorAt(1, QColor(30, 80, 200, 0))
        q.fillRect(QRectF(0, 0, w, h), QBrush(g2))
        q.end()
        self.cache_fundo = ((w, h), pix)
        return pix

    def estrelas_(self, p, w, h, agora):
        p.setPen(Qt.NoPen)
        for x, y, r, vel, fase in self.estrelas:
            a = 40 + 110 * (0.5 + 0.5 * math.sin(agora * vel + fase))
            xx = (x * w - agora * 3 * vel) % w
            p.setBrush(QColor(170, 215, 255, int(a)))
            p.drawEllipse(QPointF(xx, y * h), r, r)

    def ondas(self, p, w, h, agora):
        """Um feixe de fitas de luz cruzando a tela, que se torcem devagar (meia resolução, ~15 qps)."""
        c = getattr(self, "cache_ondas", None)
        if c is None or c[0] != (w, h) or agora - c[1] > 0.066:
            from PySide6.QtGui import QImage
            img = QImage(int(w * 0.5), int(h * 0.5), QImage.Format_ARGB32_Premultiplied)
            img.fill(Qt.transparent)
            q = QPainter(img)
            q.setRenderHint(QPainter.Antialiasing)
            q.scale(0.5, 0.5)
            self.ondas_(q, w, h, agora)
            q.end()
            self.cache_ondas = c = ((w, h), agora, img)
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(QRectF(0, 0, w, h), c[2])
        p.restore()

    def ondas_(self, p, w, h, agora):
        N, passos = 24, 52
        t = agora
        p.setBrush(Qt.NoBrush)
        meio = None
        for i in range(N):
            u = i / (N - 1)
            path = QPainterPath()
            pts = []
            for j in range(passos + 1):
                xf = j / passos
                x = -0.05 * w + xf * 1.1 * w
                abre = (u - 0.5) * h * (0.16 + 0.10 * math.sin(xf * 3.1 + t * 0.21))
                y = (h * (0.98 - 0.62 * xf) + h * 0.09 * math.sin(xf * 2.6 + t * 0.23 + 0.6)
                     + h * 0.04 * math.sin(xf * 6.3 - t * 0.37 + u * 2.2)
                     + abre * math.cos(xf * 2.2 - t * 0.18 + 1.0))
                pts.append((x, y))
                if j == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            if i == N // 2:
                meio = pts
            perto = 1 - abs(u - 0.5) * 2
            c = QColor(int(30 + 70 * u), int(95 + 120 * u), 255, int(30 + 90 * perto))
            p.setPen(QPen(c, 1.8))
            p.drawPath(path)
        # um cometa de luz correndo pela fita do meio
        if meio:
            cab = (agora * 0.10) % 1.4
            n = len(meio) - 1
            for j in range(n):
                xf = j / n
                d = cab - xf
                if 0 <= d < 0.16:
                    a = 1 - d / 0.16
                    p.setPen(QPen(QColor(150, 240, 255, int(200 * a)), 2.2 * a + 0.6, Qt.SolidLine, Qt.RoundCap))
                    p.drawLine(QPointF(*meio[j]), QPointF(*meio[j + 1]))

    def letras(self, p, w, h, agora):
        lh = max(11, h * 0.019)
        f = fonte(lh * 0.85, QFont.Normal, ("Consolas", "Cascadia Mono"))
        p.setFont(f)
        for c in self.colunas:
            n = c["n"]
            total = h + n * lh
            cab = (agora * c["v"] + c["off"]) % total
            x = c["x"] * w
            topo = cab - n * lh
            # a coluna inteira num texto só (a cabeça embaixo), com um degradê do transparente ao azul
            g = QLinearGradient(0, topo, 0, cab)
            g.setColorAt(0, QColor(90, 170, 255, 0))
            g.setColorAt(1, QColor(90, 170, 255, int(c["a"])))
            p.setPen(QPen(QBrush(g), 1))
            p.drawText(QRectF(x, topo - lh * 0.75, lh * 2, n * lh), Qt.AlignLeft | Qt.AlignTop,
                       chr(10).join(reversed(c["c"][1:])))
            p.setPen(QColor(200, 250, 255, int(min(255, c["a"] * 2.2))))
            p.drawText(QPointF(x, cab), c["c"][0])

    # --- o feixe do peito dela e a plataforma
    def feixe(self, p, R, w, h, agora, op):
        peito = self.onde_ela() if self.onde_ela else None
        if peito is None or op <= 0:
            return
        lx, ly = peito.x() - self.x(), peito.y() - self.y()
        if not (0 <= lx <= w and 0 <= ly <= h and lx < R.left()):
            return
        # plataforma holográfica embaixo dos pés dela
        if self.m is not None:
            try:
                vx, vy, cw, ch = self.m.caixa()
                px, py = vx + cw / 2 - self.x(), vy + ch - self.y()
                rx = cw * 0.75
                gp = QRadialGradient(QPointF(px, py), rx)
                gp.setColorAt(0, QColor(127, 243, 255, int(70 * op)))
                gp.setColorAt(1, QColor(127, 243, 255, 0))
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(gp))
                p.drawEllipse(QPointF(px, py), rx, rx * 0.22)
                p.setBrush(Qt.NoBrush)
                for i, (f, a, est) in enumerate(((0.55, 150, Qt.SolidLine), (0.8, 90, Qt.DashLine), (1.0, 50, Qt.SolidLine))):
                    pul = 1 + 0.03 * math.sin(agora * 2 + i)
                    p.setPen(QPen(QColor(127, 243, 255, int(a * op)), 1.4, est))
                    p.drawEllipse(QPointF(px, py), rx * f * pul, rx * f * 0.22 * pul)
            except Exception:
                pass
        topo, base = QPointF(R.left(), R.top() + R.height() * 0.03), QPointF(R.left(), R.bottom() - R.height() * 0.03)
        gf = QLinearGradient(QPointF(lx, ly), QPointF(R.left(), ly))
        gf.setColorAt(0, QColor(150, 245, 255, int(130 * op)))
        gf.setColorAt(0.35, QColor(127, 243, 255, int(55 * op)))
        gf.setColorAt(1, QColor(127, 243, 255, int(10 * op)))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(gf))
        p.drawPolygon(QPolygonF([QPointF(lx, ly), topo, base]))
        p.setPen(QPen(QColor(127, 243, 255, int(55 * op)), 1))
        p.drawLine(QPointF(lx, ly), topo)
        p.drawLine(QPointF(lx, ly), base)
        # partículas de luz viajando do peito para o painel
        p.setPen(Qt.NoPen)
        for fase, lado, vel, r in self.particulas:
            s = (agora * vel + fase) % 1.0
            x = lx + (R.left() - lx) * s
            yc = ly + ((topo.y() + base.y()) / 2 - ly) * s
            meia = (base.y() - topo.y()) / 2 * s
            y = yc + lado * meia
            a = math.sin(s * math.pi)
            p.setBrush(QColor(200, 250, 255, int(170 * a * op)))
            p.drawEllipse(QPointF(x, y), r * (0.6 + s), r * (0.6 + s))

    # --- a moldura
    def moldura(self, p, R, agora, losangos=True):
        RW, RH = R.width(), R.height()
        raio = RH * 0.035
        fundo = QLinearGradient(0, R.top(), 0, R.bottom())
        fundo.setColorAt(0, QColor(15, 36, 70, 212))
        fundo.setColorAt(1, QColor(8, 22, 48, 228))
        p.setBrush(QBrush(fundo))
        p.setPen(QPen(QColor(120, 220, 255, 55), 1))
        p.drawRoundedRect(R, raio, raio)
        # grade levíssima por dentro
        p.save()
        caminho = QPainterPath()
        caminho.addRoundedRect(R, raio, raio)
        p.setClipPath(caminho, Qt.IntersectClip)
        p.setPen(QPen(QColor(127, 243, 255, 7), 1))
        passo = RH / 16
        x = R.left()
        while x < R.right():
            p.drawLine(QPointF(x, R.top()), QPointF(x, R.bottom()))
            x += passo
        y = R.top()
        while y < R.bottom():
            p.drawLine(QPointF(R.left(), y), QPointF(R.right(), y))
            y += passo
        p.restore()
        # as cantoneiras grossas, com brilho
        L, Lv = RW * 0.075, RH * 0.11
        r = raio
        for brilho, larg in ((40, 9), (80, 5.5), (255, 3)):
            p.setPen(QPen(cor(CIANO, brilho), larg, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            for (x, y, dx, dy) in ((R.left(), R.top(), 1, 1), (R.right(), R.top(), -1, 1),
                                   (R.left(), R.bottom(), 1, -1), (R.right(), R.bottom(), -1, -1)):
                c = QPainterPath()
                c.moveTo(x, y + dy * Lv)
                c.lineTo(x, y + dy * r)
                c.quadTo(x, y, x + dx * r, y)
                c.lineTo(x + dx * L, y)
                p.drawPath(c)
        # barras no meio de cima e de baixo
        cx = R.center().x()
        for y in (R.top(), R.bottom()):
            p.setPen(QPen(CIANO, 3, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(cx - RW * 0.08, y), QPointF(cx + RW * 0.08, y))
            p.setPen(QPen(cor(CIANO, 140), 2, Qt.SolidLine, Qt.RoundCap))
            for s in (-1, 1):
                p.drawLine(QPointF(cx + s * RW * 0.098, y), QPointF(cx + s * RW * 0.108, y))
        # pontinhos nos cantos de dentro
        p.setPen(Qt.NoPen)
        p.setBrush(cor(CIANO, 120))
        for x, y in ((R.left() + RW * 0.018, R.top() + RH * 0.025), (R.right() - RW * 0.018, R.top() + RH * 0.025),
                     (R.left() + RW * 0.018, R.bottom() - RH * 0.025), (R.right() - RW * 0.018, R.bottom() - RH * 0.025)):
            p.drawEllipse(QPointF(x, y), 2.4, 2.4)
        # réguas nas laterais e os losangos no meio das bordas
        p.setPen(QPen(cor(CIANO, 60), 1))
        for i in range(9):
            y = R.top() + RH * (0.38 + i * 0.03)
            for x0, x1 in ((R.left() + RW * 0.012, R.left() + RW * 0.024), (R.right() - RW * 0.024, R.right() - RW * 0.012)):
                p.drawLine(QPointF(x0, y), QPointF(x1, y))
        if losangos:
            self.losangos(p, R, agora)

    def losangos(self, p, R, agora):
        p.setPen(Qt.NoPen)
        a = 0.6 + 0.4 * math.sin(agora * 1.8)
        p.setBrush(cor(CIANO, 160 + 90 * a))
        for x in (R.left(), R.right()):
            y = R.center().y()
            d = 6
            p.drawPolygon(QPolygonF([QPointF(x, y - d), QPointF(x + d, y), QPointF(x, y + d), QPointF(x - d, y)]))

    def cabecalho(self, p, R, agora):
        h = self.height()
        tam = h * 0.022
        caixa = QRectF(R.left(), R.top() - h * 0.058, R.width(), h * 0.04)
        p.setFont(fonte(tam, QFont.DemiBold, F_TITULO, tam * 0.22))
        p.setPen(TITULO)
        p.drawText(caixa, Qt.AlignLeft | Qt.AlignVCenter, "SEXTA-FEIRA · TELA DE DESCANSO")
        fm = QFontMetrics(p.font())
        larg = fm.horizontalAdvance("ONLINE")
        p.drawText(caixa, Qt.AlignRight | Qt.AlignVCenter, "ONLINE")
        a = 0.5 + 0.5 * math.sin(agora * 2.4)
        p.setPen(Qt.NoPen)
        p.setBrush(cor(CIANO, 60 * a))
        cx = R.right() - larg - tam * 0.9
        p.drawEllipse(QPointF(cx, caixa.center().y()), tam * 0.42, tam * 0.42)
        p.setBrush(cor(CIANO, 170 + 85 * a))
        p.drawEllipse(QPointF(cx, caixa.center().y()), tam * 0.24, tam * 0.24)

    # --- relógio, régua dos segundos, data e frase
    def pix_relogio(self, hora, tam):
        chave = (hora, int(tam))
        if self.cache_relogio is not None and self.cache_relogio[0] == chave:
            return self.cache_relogio[1]
        f = fonte(tam, QFont.Normal, F_RELOGIO)
        fm = QFontMetrics(f)
        larg, alt = fm.horizontalAdvance(hora) + 40, fm.height() + 20
        dpr = self.devicePixelRatioF()
        pix = QPixmap(int(larg * dpr), int(alt * dpr))
        pix.setDevicePixelRatio(dpr)
        pix.fill(Qt.transparent)
        q = QPainter(pix)
        q.setRenderHint(QPainter.Antialiasing)
        q.setRenderHint(QPainter.TextAntialiasing)
        q.setFont(f)
        caixa = QRectF(0, 0, larg, alt)
        for d, a in ((6, 10), (4, 18), (2, 34)):
            q.setPen(QColor(127, 243, 255, a))
            for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d), (d * .7, d * .7), (-d * .7, -d * .7)):
                q.drawText(caixa.translated(dx, dy), Qt.AlignCenter, hora)
        q.setPen(QColor(246, 252, 255))
        q.drawText(caixa, Qt.AlignCenter, hora)
        q.end()
        self.cache_relogio = (chave, pix, fm.horizontalAdvance(hora))
        return pix

    def relogio(self, p, R, t):
        RW, RH = R.width(), R.height()
        agora = datetime.datetime.now()
        hora = agora.strftime("%H:%M")
        pix = self.pix_relogio(hora, RH * 0.27)
        larg_txt = self.cache_relogio[2]
        dpr = pix.devicePixelRatio()
        pw, ph = pix.width() / dpr, pix.height() / dpr
        cy = R.top() + RH * 0.155
        p.drawPixmap(QPointF(R.center().x() - pw / 2, cy - ph / 2), pix)
        # os marcadores dos lados do relógio
        meio = R.top() + RH * 0.15
        for s in (-1, 1):
            xc = R.center().x() + s * (larg_txt / 2 + RW * 0.055)
            p.setPen(QPen(cor(CIANO, 160), 1.4))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(xc, meio), 6, 6)
            p.setPen(Qt.NoPen)
            p.setBrush(CIANO)
            p.drawEllipse(QPointF(xc, meio), 2.2, 2.2)
            gl = QLinearGradient(QPointF(xc, meio), QPointF(xc + s * RW * 0.14, meio))
            gl.setColorAt(0, cor(CIANO, 150))
            gl.setColorAt(1, cor(CIANO, 0))
            p.setPen(QPen(QBrush(gl), 1.2))
            p.drawLine(QPointF(xc + s * 12, meio), QPointF(xc + s * RW * 0.14, meio))
        # a data por extenso
        data = f"{DIAS[agora.weekday()]}, {agora.day} de {MESES[agora.month - 1]}"
        p.setFont(fonte(RH * 0.05, QFont.Medium))
        p.setPen(QColor(218, 234, 248))
        p.drawText(QRectF(R.left(), R.top() + RH * 0.325, RW, RH * 0.075), Qt.AlignCenter, data)

    def vivo(self, p, R, agora_t, t):
        """O que mexe o tempo todo no painel: a régua dos segundos, a frase e os losangos."""
        RW, RH = R.width(), R.height()
        agora = datetime.datetime.now()
        self.pix_relogio(agora.strftime("%H:%M"), RH * 0.27)
        larg_txt = self.cache_relogio[2]
        self.losangos(p, R, agora_t)
        # a régua dos segundos
        y = R.top() + RH * 0.30
        larg = larg_txt * 0.98
        x0 = R.center().x() - larg / 2
        seg = (agora.second + agora.microsecond / 1e6) / 60
        p.setPen(QPen(cor(CIANO, 50), 1))
        p.drawLine(QPointF(x0, y), QPointF(x0 + larg, y))
        for i in range(41):
            x = x0 + larg * i / 40
            alto = RH * (0.016 if i % 5 == 0 else 0.008)
            p.setPen(QPen(cor(CIANO, 110 if x <= x0 + larg * seg else 45), 1))
            p.drawLine(QPointF(x, y - alto / 2), QPointF(x, y + alto / 2))
        p.setPen(QPen(CIANO, 3, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(x0, y), QPointF(x0 + larg * seg, y))
        p.setPen(Qt.NoPen)
        p.setBrush(cor(CIANO, 70))
        p.drawEllipse(QPointF(x0 + larg * seg, y), 9, 9)
        p.setBrush(QColor(235, 255, 255))
        p.drawEllipse(QPointF(x0 + larg * seg, y), 4.5, 4.5)
        # a frase dela (troca a cada 12 s, com um fade): negrito + resto
        lista = self.frases()
        ciclo = 12.0
        i = int(t // ciclo) % len(lista)
        fase = (t % ciclo) / ciclo
        a = min(1.0, fase / 0.08, (1 - fase) / 0.08)
        negrito, resto = lista[i]
        fb = fonte(RH * 0.043, QFont.Bold)
        fr = fonte(RH * 0.043, QFont.Normal)
        wb = QFontMetrics(fb).horizontalAdvance(negrito + " ") if negrito else 0
        wr = QFontMetrics(fr).horizontalAdvance(resto)
        x = R.center().x() - (wb + wr) / 2
        caixa_y = QRectF(0, R.top() + RH * 0.405, 0, RH * 0.06)
        base = p.opacity()
        p.setOpacity(base * a)
        if negrito:
            p.setFont(fb)
            p.setPen(QColor(250, 253, 255))
            p.drawText(QRectF(x, caixa_y.top(), wb + 4, caixa_y.height()), Qt.AlignLeft | Qt.AlignVCenter, negrito)
        p.setFont(fr)
        p.setPen(QColor(178, 202, 222))
        p.drawText(QRectF(x + wb, caixa_y.top(), wr + 4, caixa_y.height()), Qt.AlignLeft | Qt.AlignVCenter, resto)
        p.setOpacity(base)

    # --- os cartões
    def cartoes(self, p, R, t):
        RW, RH = R.width(), R.height()
        topo, base = R.top() + RH * 0.505, R.top() + RH * 0.945
        c1 = QRectF(R.left() + RW * 0.052, topo, RW * 0.50, base - topo)
        c2 = QRectF(c1.right() + RW * 0.022, topo, R.right() - RW * 0.052 - c1.right() - RW * 0.022, base - topo)
        self.cartao_lista(p, c1, "HOJE E O QUE ESTÁ PARADO", self.urgentes, "Nada urgente. Respira.", t, 0.0)
        self.cartao_prazos(p, c2, t, 0.25)

    def caixa_cartao(self, p, r, titulo, t, atraso):
        k = max(0.0, min(1.0, (t - 0.5 - atraso) / 0.5))   # cada cartão entra um pouquinho depois
        if k <= 0:
            return None, 0
        r = r.translated(0, (1 - k) * 18)
        u = r.height() / 330
        fundo = QLinearGradient(0, r.top(), 0, r.bottom())
        fundo.setColorAt(0, QColor(32, 52, 88, 150))
        fundo.setColorAt(1, QColor(20, 36, 66, 140))
        p.setBrush(QBrush(fundo))
        p.setPen(QPen(QColor(130, 190, 240, 55), 1.2))
        p.drawRoundedRect(r, 22 * u, 22 * u)
        p.setFont(fonte(19 * u, QFont.DemiBold, F_TITULO, 19 * u * 0.14))
        p.setPen(TITULO)
        p.drawText(QRectF(r.left() + 31 * u, r.top() + 24 * u, r.width() - 50 * u, 30 * u),
                   Qt.AlignLeft | Qt.AlignVCenter, titulo)
        return r, k

    def chip(self, p, x, y, u, texto, c):
        p.setFont(fonte(18 * u, QFont.DemiBold, F_TITULO, 18 * u * 0.08))
        fm = QFontMetrics(p.font())
        cr = QRectF(x, y, fm.horizontalAdvance(texto) + 28 * u, 34 * u)
        p.setBrush(cor(c, 34))
        p.setPen(QPen(cor(c, 120), 1.2))
        p.drawRoundedRect(cr, cr.height() / 2, cr.height() / 2)
        p.setPen(c)
        p.drawText(cr, Qt.AlignCenter, texto)
        return cr

    def cartao_lista(self, p, r, titulo, itens, vazio, t, atraso):
        base = p.opacity()
        r, k = self.caixa_cartao(p, r, titulo, t, atraso)
        if r is None:
            return
        p.setOpacity(base * k)
        u = r.height() / 330
        x = r.left() + 31 * u
        larg = r.width() - 62 * u
        y = r.top() + 69 * u
        bloco = 145 * u
        if not itens:
            p.setFont(fonte(22 * u))
            p.setPen(SUAVE)
            p.drawText(QRectF(x, y, larg, 40 * u), Qt.AlignLeft | Qt.AlignVCenter, vazio)
        cabem = max(1, int((r.bottom() - 16 * u - y) // bloco) + (1 if (r.bottom() - y) % bloco > 105 * u else 0))
        mostrados = itens[:cabem] if len(itens) <= cabem else itens[:cabem - 1]
        for n, (_, _, chip, c, assunto, passo) in enumerate(mostrados):
            if n:
                p.setPen(QPen(QColor(130, 190, 240, 40), 1))
                p.drawLine(QPointF(x, y - 19 * u), QPointF(x + larg, y - 19 * u))
            self.chip(p, x, y, u, chip, c)
            p.setFont(fonte(23 * u, QFont.Medium))
            fm = QFontMetrics(p.font())
            p.setPen(TEXTO)
            p.drawText(QRectF(x, y + 44 * u, larg, 32 * u), Qt.AlignLeft | Qt.AlignVCenter,
                       fm.elidedText(assunto, Qt.ElideRight, int(larg)))
            if passo:
                p.setFont(fonte(19 * u))
                fm = QFontMetrics(p.font())
                p.setPen(SUAVE)
                p.drawText(QRectF(x, y + 80 * u, larg, 28 * u), Qt.AlignLeft | Qt.AlignVCenter,
                           fm.elidedText("→ " + passo, Qt.ElideRight, int(larg)))
            y += bloco
        if len(itens) > len(mostrados):
            p.setFont(fonte(18 * u))
            p.setPen(SUAVE)
            p.drawText(QRectF(x, y - 10 * u, larg, 28 * u), Qt.AlignLeft | Qt.AlignVCenter,
                       f"+ {len(itens) - len(mostrados)} na nota de avisos")
        p.setOpacity(base)

    def cartao_prazos(self, p, r, t, atraso):
        base = p.opacity()
        r, k = self.caixa_cartao(p, r, "PRÓXIMOS PRAZOS", t, atraso)
        if r is None:
            return
        p.setOpacity(base * k)
        u = r.height() / 330
        x = r.left() + 31 * u
        larg = r.width() - 62 * u
        y = r.top() + 69 * u
        if not self.proximos:
            p.setFont(fonte(22 * u))
            p.setPen(SUAVE)
            p.drawText(QRectF(x, y, larg, 40 * u), Qt.AlignLeft | Qt.AlignVCenter, "Nenhum prazo marcado à frente.")
            p.setOpacity(base)
            return
        falta, _, chip, c, assunto, passo = self.proximos[0]
        self.chip(p, x, y, u, chip, c)
        p.setFont(fonte(23 * u, QFont.Medium))
        p.setPen(TEXTO)
        p.drawText(QRectF(x, y + 42 * u, larg, 66 * u), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, assunto)
        # o anel dos dias que faltam
        rr = 44 * u
        cx, cy = x + rr + 4 * u, r.top() + 245 * u
        p.setPen(QPen(cor(CIANO, 45), 2))
        for i in range(48):
            ang = i / 48 * math.tau
            p.drawLine(QPointF(cx + math.cos(ang) * (rr - 3 * u), cy + math.sin(ang) * (rr - 3 * u)),
                       QPointF(cx + math.cos(ang) * (rr + 3 * u), cy + math.sin(ang) * (rr + 3 * u)))
        frac = max(0.06, min(1.0, 1 - falta / 30))
        p.setPen(QPen(CIANO, 5 * u, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(cx - rr, cy - rr, 2 * rr, 2 * rr), 90 * 16, int(-frac * 360 * 16))
        p.setFont(fonte(44 * u, QFont.Normal, F_RELOGIO))
        p.setPen(QColor(246, 252, 255))
        p.drawText(QRectF(cx - rr, cy - rr, 2 * rr, 2 * rr), Qt.AlignCenter, str(falta))
        p.setFont(fonte(23 * u))
        p.setPen(TEXTO)
        resto = "dia restante" if falta == 1 else "dias restantes"
        p.drawText(QRectF(cx + rr + 22 * u, cy - 20 * u, larg - 2 * rr - 26 * u, 40 * u), Qt.AlignLeft | Qt.AlignVCenter, resto)
        if len(self.proximos) > 1:
            p.setFont(fonte(17 * u))
            p.setPen(SUAVE)
            seg = self.proximos[1]
            fm = QFontMetrics(p.font())
            p.drawText(QRectF(cx + rr + 22 * u, cy + 18 * u, larg - 2 * rr - 26 * u, 28 * u), Qt.AlignLeft | Qt.AlignVCenter,
                       fm.elidedText(f"depois: {seg[4]} ({seg[2].lower()})", Qt.ElideRight, int(larg - 2 * rr - 26 * u)))
        p.setOpacity(base)

    # --- a barra de pedidos e o rodapé
    def barra(self, p, agora):
        b = self.barra_r()
        foco = self.campo.hasFocus()
        rr = b.height() * 0.32
        fundo = QLinearGradient(0, b.top(), 0, b.bottom())
        fundo.setColorAt(0, QColor(16, 36, 70, 236))
        fundo.setColorAt(1, QColor(9, 24, 50, 240))
        if foco:
            pul = 0.5 + 0.5 * math.sin(agora * 2.2)
            for d, a in ((7, 18), (4, 36)):
                p.setPen(QPen(cor(CIANO, a + 20 * pul), d))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(b, rr, rr)
        p.setBrush(QBrush(fundo))
        p.setPen(QPen(cor(CIANO, 170 if foco else 80), 1.4))
        p.drawRoundedRect(b, rr, rr)
        # o ícone dela (um mini reator) à esquerda
        cx, cy, r = b.left() + b.height() * 0.55, b.center().y(), b.height() * 0.2
        p.setPen(QPen(cor(CIANO, 190), 1.6))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)
        gi = QRadialGradient(QPointF(cx, cy), r * 0.7)
        gi.setColorAt(0, QColor(220, 255, 255))
        gi.setColorAt(1, cor(CIANO, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(gi))
        p.drawEllipse(QPointF(cx, cy), r * 0.7, r * 0.7)
        # o texto de convite quando a caixa ainda não está ativa (no modo de fundo)
        if self.campo.isHidden():
            p.setFont(fonte(b.height() * 0.36))
            p.setPen(QColor(143, 185, 210, 160))
            esq = b.left() + b.height() * 1.05
            p.drawText(QRectF(esq, b.top(), b.width() - (esq - b.left()) - b.height(), b.height()),
                       Qt.AlignLeft | Qt.AlignVCenter, "Clique aqui para falar com a Sexta…")
        # o botão de enviar
        br = self.botao_r()
        tem = bool(self.campo.text().strip()) and not self.enviando
        p.setPen(Qt.NoPen)
        p.setBrush(cor(CIANO, 210 if tem else 60))
        p.drawEllipse(br)
        s = br.width() * 0.22
        c = br.center()
        if self.enviando:
            p.setPen(QPen(QColor(8, 22, 48), 2.2, Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(c.x() - s, c.y() - s, 2 * s, 2 * s), int(-agora * 360 * 16) % (360 * 16), 270 * 16)
        else:
            p.setBrush(QColor(8, 22, 48) if tem else cor(CIANO, 200))
            p.drawPolygon(QPolygonF([QPointF(c.x() - s * 0.8, c.y() - s), QPointF(c.x() + s * 1.1, c.y()),
                                     QPointF(c.x() - s * 0.8, c.y() + s), QPointF(c.x() - s * 0.35, c.y())]))

    def rodape(self, p, w, h, agora):
        caixa = QRectF(0, h * 0.934, w, h * 0.03)
        R = self.moldura_r()
        caixa = QRectF(R.left(), caixa.top(), R.width(), caixa.height())
        if self.status and agora < self.status[2]:
            p.setFont(fonte(h * 0.017, QFont.Medium))
            p.setPen(self.status[1])
            p.drawText(caixa, Qt.AlignCenter, self.status[0])
            return
        tam = h * 0.0155
        p.setFont(fonte(tam, QFont.Normal, F_TEXTO, tam * 0.12))
        p.setPen(QColor(150, 180, 205, 150))
        dica = ("Enter envia para a Sexta do chat  ·  Esc ou clique fora da barra para voltar" if self.frente
                else "clique em qualquer lugar para voltar  ·  clique na barra para falar com a Sexta")
        p.drawText(caixa, Qt.AlignCenter, dica)
