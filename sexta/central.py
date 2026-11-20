# Central de comando da Sexta-Feira (tela 1). Criado em 16/11/2026, de madrugada, a pedido do usuário:
# "Pode ser a tela principal [...] os apps, e as minhas notas do obsidian e só. não vamos estender demais
# isso [...] seria basicamente conferir somente pra leitura, por enquanto, e ai vc mantem o design da tela
# de bloqueio, com as letras meio em luz neon".
#
# Mesmo visual e mesmo fundo animado da tela de descanso (descanso.py): esta janela é uma "filha" dela.
#   - APLICATIVOS: seis blocos com ícones em neon. Um clique abre o programa e a central se recolhe.
#   - NOTAS: busca pelo nome, notas fixas e recentes do cofre.
#   - LEITURA: a nota escolhida aparece formatada, SÓ PARA LER (nada é alterado). Links [[...]] abrem a
#     outra nota aqui mesmo.
#   - A barra de falar com a Sexta continua embaixo, igual à da tela de descanso.
# Só aparece quando o usuário pede (menu da mascote ou comando). Lê as notas no PC; nada sai do PC.

import datetime, importlib.util, math, os, pathlib, re, threading, time, unicodedata, urllib.parse, webbrowser
import sys as _sys, pathlib as _pl  # 16/11: com "-P" o Python não procura na pasta do arquivo; sem isto, nada abria
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg

from PySide6.QtCore import Qt, QPointF, QRectF, QUrl
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPalette,
                           QPen, QPixmap, QPolygonF, QBrush, QRegion, QTextBlockFormat, QTextCursor)
from PySide6.QtWidgets import QLineEdit, QTextBrowser, QFrame

_spec = importlib.util.spec_from_file_location("descanso_base", pathlib.Path(__file__).with_name("descanso.py"))
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)
fonte, cor, CIANO, TEXTO, SUAVE, TITULO = D.fonte, D.cor, D.CIANO, D.TEXTO, D.SUAVE, D.TITULO

COFRE = cfg.COFRE
INICIO = cfg.RAIZ_NOTAS
CORTEX = cfg.PASTA
# (nome, ícone, o que abrir): vem do sexta.config.json ("apps"). Atalho, endereço ou programa.
APPS = cfg.APPS

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


def nome_bonito(p):
    n = p.stem if isinstance(p, pathlib.Path) else str(p)
    return n[4:] if n.startswith("(C) ") else n


def quando(mtime):
    d = datetime.date.fromtimestamp(mtime)
    hoje = datetime.date.today()
    if d == hoje:
        return "hoje"
    if (hoje - d).days == 1:
        return "ontem"
    return d.strftime("%d/%m")


def preparar_markdown(txt):
    """Traduz o jeito Obsidian de escrever para o Markdown comum que o leitor entende."""
    if txt.startswith("---"):
        fim = txt.find("\n---", 3)
        if fim != -1:
            txt = txt[fim + 4:].lstrip("\n")
    txt = re.sub(r"%%.*?%%", "", txt, flags=re.S)                         # comentários (roteiros de voz etc.)
    txt = re.sub(r"!\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", lambda m: f"*[anexo: {m.group(1)}]*", txt)

    def link(m):
        alvo, rot = m.group(1), m.group(2) or m.group(1)
        alvo = alvo.split("#")[0]
        return f"[{rot.split('/')[-1]}](nota:{urllib.parse.quote(alvo)})"
    txt = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", link, txt)
    txt = re.sub(r"^(\s*>\s*)\[!(\w+)\][+-]?\s*(.*)$",
                 lambda m: f"{m.group(1)}**{m.group(3) or m.group(2).capitalize()}**", txt, flags=re.M)
    txt = re.sub(r"==(.+?)==", r"**\1**", txt)
    return txt


def colorir(doc):
    """Dá a cara neon ao texto: títulos e links em ciano, código em azul-claro."""
    b = doc.begin()
    while b.isValid():
        nivel = b.blockFormat().headingLevel()
        bf = QTextBlockFormat()                       # linhas mais arejadas, como num leitor de verdade
        bf.setLineHeight(128, 1)                      # 1 = ProportionalHeight
        bf.setBottomMargin(9 if not nivel else 4)
        if nivel:
            bf.setTopMargin(14)
        cb = QTextCursor(b)
        cb.mergeBlockFormat(bf)
        it = b.begin()
        while not it.atEnd():
            f = it.fragment()
            if f.isValid():
                cf = f.charFormat()
                mudou = False
                if nivel:
                    cf.setForeground(QColor("#7ff3ff") if nivel <= 2 else QColor("#a8ecff"))
                    mudou = True
                if cf.isAnchor():
                    cf.setForeground(QColor("#7ff3ff"))
                    cf.setFontUnderline(False)
                    mudou = True
                if cf.fontFixedPitch():
                    cf.setForeground(QColor("#bfefff"))
                    cf.setBackground(QColor(20, 50, 90, 200))
                    mudou = True
                if mudou:
                    c = QTextCursor(doc)
                    c.setPosition(f.position())
                    c.setPosition(f.position() + f.length(), QTextCursor.KeepAnchor)
                    c.setCharFormat(cf)
            it += 1
        b = b.next()


class Busca(QLineEdit):
    def __init__(self, dono):
        super().__init__(dono)
        self.dono = dono
        self.setFrame(False)
        self.setStyleSheet("QLineEdit{background:transparent;border:none;color:#eaf6ff;"
                           "selection-background-color:#2fb6e8;}")
        pal = self.palette()
        pal.setColor(QPalette.PlaceholderText, QColor(143, 185, 210, 150))
        self.setPalette(pal)
        self.setPlaceholderText("Buscar nota pelo nome…")
        self.textChanged.connect(lambda _: setattr(dono, "lista_off", 0))
        self.hide()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.dono.ao_clicar()
            return
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            itens = [i for i in self.dono.itens_lista() if i[0] == "nota"]
            if itens:
                self.dono.abrir_nota(itens[0][1])
            return
        if e.key() == Qt.Key_Down:
            self.dono.leitor.setFocus()
            return
        super().keyPressEvent(e)


class Leitor(QTextBrowser):
    def __init__(self, dono):
        super().__init__(dono)
        self.dono = dono
        self.setFrameShape(QFrame.NoFrame)
        self.setOpenLinks(False)
        self.setReadOnly(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.viewport().setAutoFillBackground(False)
        self.setStyleSheet(
            "QTextBrowser{background:transparent;border:none;color:#d9e9f7;selection-background-color:#2fb6e8;}"
            "QScrollBar:vertical{background:transparent;width:8px;margin:4px 0;}"
            "QScrollBar::handle:vertical{background:rgba(127,243,255,90);border-radius:4px;min-height:30px;}"
            "QScrollBar::handle:vertical:hover{background:rgba(127,243,255,170);}"
            "QScrollBar::add-line,QScrollBar::sub-line{height:0;}"
            "QScrollBar::add-page,QScrollBar::sub-page{background:transparent;}")
        self.anchorClicked.connect(self.clicou)
        self.hide()

    def clicou(self, url):
        if url.scheme() == "nota":
            self.dono.abrir_por_nome(urllib.parse.unquote(url.path() or url.toString()[5:]))
        elif url.scheme() in ("http", "https"):
            webbrowser.open(url.toString())

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.dono.ao_clicar()
            return
        super().keyPressEvent(e)


class CentralComando(D.TelaDescanso):
    def __init__(self, ao_fechar, mascote=None):
        super().__init__(ao_fechar, None, mascote)
        self.setWindowTitle("Sexta-Feira · central de comando")
        self.setMouseTracking(True)
        self.mouse = QPointF(-1, -1)
        self.busca = Busca(self)
        self.leitor = Leitor(self)
        self.indice, self.indice_t, self.indexando = [], 0.0, False
        self.nota = None              # (caminho, mtime)
        self.lista_off = 0
        self.cache_quadro = None
        self.clique_app = None        # (índice, hora) para o brilho do clique

    # ------------------------------------------------------------ geometria
    def s(self):
        return self.height() / 864

    def moldura_r(self):
        w, h = self.width(), self.height()
        return QRectF(w * 0.05, h * 0.105, w * 0.90, h * 0.74)

    def barra_r(self):
        w, h = self.width(), self.height()
        R = self.moldura_r()
        bw = min(R.width() * 0.5, w * 0.48)
        return QRectF(R.center().x() - bw / 2, h * 0.872, bw, h * 0.056)

    def areas(self):
        R = self.moldura_r()
        pad = R.width() * 0.028
        gap = R.width() * 0.018
        lw = R.width() * 0.36
        x0, y0, y1 = R.left() + pad, R.top() + pad * 1.05, R.bottom() - pad * 1.05
        apps = QRectF(x0, y0, lw, (y1 - y0) * 0.40)
        notas = QRectF(x0, apps.bottom() + gap, lw, y1 - apps.bottom() - gap)
        leitura = QRectF(apps.right() + gap, y0, R.right() - pad - apps.right() - gap, y1 - y0)
        return apps, notas, leitura

    def blocos_apps(self):
        apps, _, _ = self.areas()
        s = self.s()
        topo = apps.top() + 50 * s
        gx, gy = 14 * s, 14 * s
        larg = (apps.width() - 2 * 22 * s - 2 * gx) / 3
        alt = (apps.bottom() - 20 * s - topo - gy) / 2
        r = []
        for i in range(len(APPS)):
            c, l = i % 3, i // 3
            r.append(QRectF(apps.left() + 22 * s + c * (larg + gx), topo + l * (alt + gy), larg, alt))
        return r

    def caixa_busca(self):
        _, notas, _ = self.areas()
        s = self.s()
        return QRectF(notas.left() + 22 * s, notas.top() + 50 * s, notas.width() - 44 * s, 36 * s)

    def area_lista(self):
        _, notas, _ = self.areas()
        b = self.caixa_busca()
        s = self.s()
        return QRectF(b.left(), b.bottom() + 12 * s, b.width(), notas.bottom() - 14 * s - b.bottom() - 12 * s)

    def area_texto(self):
        _, _, leitura = self.areas()
        s = self.s()
        return QRectF(leitura.left() + 30 * s, leitura.top() + 122 * s, leitura.width() - 46 * s,
                      leitura.height() - 122 * s - 18 * s)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        s = self.s()
        b = self.caixa_busca()
        self.busca.setGeometry(int(b.left() + 38 * s), int(b.top() + 2), int(b.width() - 48 * s), int(b.height() - 4))
        self.busca.setFont(fonte(15 * s))
        t = self.area_texto()
        self.leitor.setGeometry(int(t.left()), int(t.top()), int(t.width()), int(t.height()))
        self.leitor.setFont(fonte(15.5 * s))
        self.cache_quadro = None

    # ------------------------------------------------------------ abrir e fechar
    def mostrar(self, geo, frente=True):
        estava = self.aberta()
        super().mostrar(geo, True)
        self.timer.start(50)          # 20 quadros por segundo bastam aqui
        if not estava:
            self.busca.clear()
            self.lista_off = 0
        self.indexar()

    def esconder(self):
        super().esconder()
        self.busca.hide()
        self.leitor.hide()
        self.leitor.clear()
        self.nota = None          # fechou: a nota some da tela (ninguém vê depois)

    def tique(self):
        if (self.saindo is None and self.isVisible() and self.campo.isHidden()
                and time.time() - self.t_ini > 0.9):
            self.campo.show()
            self.busca.show()
            if self.nota:
                self.leitor.show()
            self.activateWindow()
            try:
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(ctypes.c_void_p(int(self.winId())))
            except Exception:
                pass
            self.busca.setFocus(Qt.OtherFocusReason)
        super().tique()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.ao_clicar()
            return
        super().keyPressEvent(e)

    def redesenhar(self):
        # O texto da nota fica parado: redesenha tudo menos ele (o fundo atrás do cartão quase não aparece).
        if self.leitor.isVisible() and self.saindo is None and time.time() - self.t_ini > 1.0:
            self.update(QRegion(self.rect()).subtracted(QRegion(self.leitor.geometry())))
        else:
            self.update()

    # ------------------------------------------------------------ notas
    def indexar(self):
        if self.indexando or time.time() - self.indice_t < 120:
            return
        self.indexando = True

        def trabalho():
            lista = []
            try:
                for raiz, pastas, arqs in os.walk(INICIO):
                    pastas[:] = [p for p in pastas if not p.startswith(".") and p != "Processados"]
                    for a in arqs:
                        if a.lower().endswith(".md"):
                            p = pathlib.Path(raiz) / a
                            try:
                                lista.append((p, p.stat().st_mtime, sem_acento(p.stem)))
                            except OSError:
                                pass
            except Exception as e:
                D.log(f"central: erro ao listar as notas ({type(e).__name__})")
            self.indice, self.indice_t, self.indexando = lista, time.time(), False
        threading.Thread(target=trabalho, daemon=True).start()

    def fixas(self):
        # guardadas por 30 s: conferir arquivo no Google Drive a cada quadro pesava (~7 ms cada)
        c = getattr(self, "cache_fixas", None)
        if c and time.time() - c[0] < 30 and c[2] == len(self.indice):
            return c[1]
        r = self._fixas()
        self.cache_fixas = (time.time(), r, len(self.indice))
        return r

    def _fixas(self):
        # o diário mais recente: qualquer nota AAAA-MM-DD dentro da pasta do diário
        hoje = datetime.date.today()
        rot_d, diario = "Diário de hoje", COFRE / "-sem-diario-"
        diarios = [i for i in self.indice if cfg.PASTA_DIARIO in i[0].parts and re.match(r"\d{4}-\d{2}-\d{2}$", i[0].stem)]
        if diarios:
            diario = max(diarios, key=lambda i: i[0].stem)[0]
            if diario.stem != f"{hoje:%Y-%m-%d}":
                rot_d = f"Último diário ({diario.stem[8:10]}/{diario.stem[5:7]})"
        r = [("Avisos", cfg.nota("avisos")), ("Onde paramos", cfg.nota("onde_paramos")), (rot_d, diario)]
        metas = [i[0] for i in self.indice if i[0].name == "METAS.md"]
        if metas:
            r.append(("Metas", metas[0]))
        return [(rot, p) for rot, p in r if p.exists()]

    def itens_lista(self):
        """[(tipo, caminho|rótulo, rótulo, à direita)] na ordem em que aparecem."""
        q = sem_acento(self.busca.text().strip())
        if q:
            achados = [i for i in self.indice if q in i[2]]
            achados.sort(key=lambda i: (not i[2].startswith(q), -i[1]))
            r = [("secao", "RESULTADOS", f"{len(achados)}", "")]
            r += [("nota", p, nome_bonito(p), quando(m)) for p, m, _ in achados[:60]]
            if not achados:
                r.append(("vazio", None, "Nenhuma nota com esse nome.", ""))
            return r
        r = [("secao", "FIXAS", "", "")]
        r += [("nota", p, rot, "") for rot, p in self.fixas()]
        r.append(("secao", "RECENTES", "", ""))
        rec = sorted(self.indice, key=lambda i: -i[1])[:14]
        r += [("nota", p, nome_bonito(p), quando(m)) for p, m, _ in rec]
        if not self.indice:
            r.append(("vazio", None, "Lendo o cofre…" if self.indexando else "Nenhuma nota encontrada.", ""))
        return r

    def linhas_lista(self):
        """[(retângulo, item)] já com a rolagem."""
        s = self.s()
        A = self.area_lista()
        y = A.top() - self.lista_off
        r = []
        for it in self.itens_lista():
            alt = (28 if it[0] == "secao" else 31) * s
            r.append((QRectF(A.left(), y, A.width(), alt), it))
            y += alt
        self.lista_total = y + self.lista_off - A.top()
        return r

    def abrir_nota(self, p):
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")[:250000]
            self.nota = (p, p.stat().st_mtime)
        except Exception as e:
            D.log(f"central: não consegui ler uma nota ({type(e).__name__})")
            return
        doc = self.leitor.document()
        doc.setDocumentMargin(4)
        self.leitor.setMarkdown(preparar_markdown(txt))
        colorir(doc)
        self.leitor.verticalScrollBar().setValue(0)
        if not self.campo.isHidden():
            self.leitor.show()

    def abrir_por_nome(self, nome):
        alvo = sem_acento(pathlib.PurePosixPath(nome).name.removesuffix(".md"))
        for p, _, chave in self.indice:
            if chave == alvo:
                self.abrir_nota(p)
                return

    # ------------------------------------------------------------ mouse
    def mouseMoveEvent(self, e):
        self.mouse = e.position()

    def leaveEvent(self, e):
        self.mouse = QPointF(-1, -1)

    def wheelEvent(self, e):
        if self.area_lista().contains(e.position()):
            A = self.area_lista()
            maximo = max(0, getattr(self, "lista_total", 0) - A.height())
            self.lista_off = max(0, min(maximo, self.lista_off - e.angleDelta().y() * 0.5))

    def mousePressEvent(self, e):
        pt = e.position()
        if self.barra_r().adjusted(-6, -6, 6, 6).contains(pt):
            super().mousePressEvent(e)
            return
        for i, r in enumerate(self.blocos_apps()):
            if r.contains(pt):
                self.abrir_app(i)
                return
        if self.area_lista().contains(pt):
            for r, it in self.linhas_lista():
                if it[0] == "nota" and r.contains(pt):
                    self.abrir_nota(it[1])
                    return
            return
        if self.caixa_busca().contains(pt):
            self.busca.setFocus()
            return
        if self.moldura_r().contains(pt):
            return
        self.ao_clicar()

    def abrir_app(self, i):
        nome, _, alvo = APPS[i]
        self.clique_app = (i, time.time())
        try:
            if alvo.startswith("http"):
                webbrowser.open(alvo)
            elif os.path.isabs(alvo) and not os.path.exists(alvo):
                raise FileNotFoundError
            else:
                os.startfile(alvo)
            D.log(f"central: abriu {nome}")
        except Exception as e:
            D.log(f"central: não consegui abrir {nome} ({type(e).__name__})")
            if nome == "Claude":
                webbrowser.open("https://claude.ai")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(350, self.ao_clicar)   # recolhe para o programa aparecer

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
        p.setOpacity(min(1.0, t / 0.6) * sai)
        self.estrelas_(p, w, h, agora)
        self.ondas(p, w, h, agora)
        self.letras(p, w, h, agora)

        R = self.moldura_r()
        k = min(1.0, t / 0.9)
        k = k * k * (3 - 2 * k)
        pisca = 0.8 + 0.2 * math.sin(t * 47) if t < 0.6 else 1.0
        op = k * pisca * sai

        p.save()
        p.setClipRect(QRectF(0, 0, w, R.top() + (R.height() + 40) * k))
        p.setOpacity(op)
        orig, pix = self.pix_quadro(R)
        p.drawPixmap(orig, pix)
        self.losangos(p, R, agora)
        self.apps_vivo(p, agora)
        self.notas_vivo(p)
        self.leitura_vivo(p)
        p.restore()

        if k < 1:
            yk = R.top() + (R.height() + 40) * k
            p.setOpacity(sai)
            p.setPen(QPen(QColor(160, 250, 255, int(200 * (1 - k))), 2))
            p.drawLine(QPointF(R.left() - 10, yk), QPointF(R.right() + 10, yk))

        p.setOpacity(op)
        self.cabecalho_c(p, R, agora)
        kb = max(0.0, min(1.0, (t - 0.6) / 0.4)) * sai
        p.setOpacity(kb)
        self.barra(p, agora)
        self.rodape_c(p, w, h, agora)
        p.end()

    def pix_quadro(self, R):
        """A moldura, os três cartões e os blocos dos apps (parados) numa imagem pronta."""
        chave = (round(R.width()), round(R.height()))
        if self.cache_quadro is not None and self.cache_quadro[0] == chave:
            return self.cache_quadro[1], self.cache_quadro[2]
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
        apps, notas, leitura = self.areas()
        self.cartao_c(q, apps, "APLICATIVOS")
        self.cartao_c(q, notas, "NOTAS")
        self.cartao_c(q, leitura, "LEITURA  ·  SÓ LEITURA")
        for i, r in enumerate(self.blocos_apps()):
            self.bloco_app(q, r, i, foco=0.0)
        # a caixa da busca
        b = self.caixa_busca()
        q.setBrush(QColor(8, 22, 46, 220))
        q.setPen(QPen(cor(CIANO, 70), 1.2))
        q.drawRoundedRect(b, b.height() / 2, b.height() / 2)
        s = self.s()
        cx, cy, rr = b.left() + 20 * s, b.center().y(), 6.5 * s
        q.setPen(QPen(cor(CIANO, 200), 1.6 * s, Qt.SolidLine, Qt.RoundCap))
        q.setBrush(Qt.NoBrush)
        q.drawEllipse(QPointF(cx - 1.5 * s, cy - 1.5 * s), rr, rr)
        q.drawLine(QPointF(cx + 3.3 * s, cy + 3.3 * s), QPointF(cx + 7.5 * s, cy + 7.5 * s))
        q.end()
        self.cache_quadro = (chave, orig, pix)
        return orig, pix

    def cartao_c(self, p, r, titulo):
        s = self.s()
        fundo = QLinearGradient(0, r.top(), 0, r.bottom())
        fundo.setColorAt(0, QColor(32, 52, 88, 150))
        fundo.setColorAt(1, QColor(20, 36, 66, 140))
        p.setBrush(QBrush(fundo))
        p.setPen(QPen(QColor(130, 190, 240, 55), 1.2))
        p.drawRoundedRect(r, 18 * s, 18 * s)
        p.setFont(fonte(13.5 * s, QFont.DemiBold, D.F_TITULO, 13.5 * s * 0.16))
        p.setPen(TITULO)
        p.drawText(QRectF(r.left() + 22 * s, r.top() + 14 * s, r.width() - 44 * s, 24 * s),
                   Qt.AlignLeft | Qt.AlignVCenter, titulo)

    # --- os blocos dos aplicativos
    def bloco_app(self, p, r, i, foco):
        s = self.s()
        nome, icone, _ = APPS[i]
        c = 14 * s                                      # o canto cortado, como na Discagem Rápida do Opera
        forma = QPolygonF([QPointF(r.left(), r.top()), QPointF(r.right(), r.top()),
                           QPointF(r.right(), r.bottom() - c), QPointF(r.right() - c, r.bottom()),
                           QPointF(r.left(), r.bottom())])
        g = QLinearGradient(0, r.top(), 0, r.bottom())
        g.setColorAt(0, QColor(18, 44, 82, int(170 + 60 * foco)))
        g.setColorAt(1, QColor(10, 26, 54, int(190 + 40 * foco)))
        if foco > 0:
            for d, a in ((8, 22), (4, 45)):
                p.setPen(QPen(cor(CIANO, a * foco), d, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.setBrush(Qt.NoBrush)
                p.drawPolygon(forma)
        p.setBrush(QBrush(g))
        p.setPen(QPen(cor(CIANO, 60 + 170 * foco), 1.3))
        p.drawPolygon(forma)
        # o ícone em neon
        tam = min(r.width(), r.height()) * 0.22
        centro = QPointF(r.center().x(), r.top() + r.height() * 0.42)
        self.icone(p, icone, centro, tam, 0.75 + 0.25 * foco)
        p.setFont(fonte(13.5 * s, QFont.Medium))
        p.setPen(QColor(235, 248, 255) if foco > 0.3 else QColor(205, 225, 242))
        p.drawText(QRectF(r.left() + 4, r.top() + r.height() * 0.70, r.width() - 8, r.height() * 0.22),
                   Qt.AlignCenter, nome)

    def icone(self, p, tipo, c, t, forca):
        x, y = c.x(), c.y()
        path = QPainterPath()
        if tipo == "opera":
            path.addEllipse(c, t * 0.82, t)
            path.addEllipse(c, t * 0.36, t * 0.78)
        elif tipo == "obsidian":
            pts = [(0, -1), (0.62, -0.38), (0.48, 0.72), (0, 1), (-0.6, 0.42), (-0.46, -0.5)]
            path.moveTo(x + pts[0][0] * t, y + pts[0][1] * t)
            for a, b in pts[1:] + pts[:1]:
                path.lineTo(x + a * t, y + b * t)
            path.moveTo(x, y - t)
            path.lineTo(x - 0.12 * t, y + 0.18 * t)
            path.lineTo(x, y + t)
            path.moveTo(x - 0.12 * t, y + 0.18 * t)
            path.lineTo(x + 0.48 * t, y + 0.72 * t)
        elif tipo == "pasta":
            path.moveTo(x - t, y - 0.62 * t)
            path.lineTo(x - 0.25 * t, y - 0.62 * t)
            path.lineTo(x - 0.05 * t, y - 0.38 * t)
            path.lineTo(x + t, y - 0.38 * t)
            path.lineTo(x + t, y + 0.72 * t)
            path.lineTo(x - t, y + 0.72 * t)
            path.closeSubpath()
            path.moveTo(x - t, y - 0.12 * t)
            path.lineTo(x + t, y - 0.12 * t)
        elif tipo == "spotify":
            path.addEllipse(c, t, t)
            for k, (lg, dy) in enumerate(((0.62, -0.28), (0.5, 0.06), (0.36, 0.36))):
                path.moveTo(x - lg * t, y + dy * t)
                path.quadTo(x, y + (dy - 0.2 + 0.03 * k) * t, x + lg * t, y + (dy + 0.06) * t)
        elif tipo == "painel":
            path.moveTo(x - t, y + 0.8 * t)
            path.lineTo(x + t, y + 0.8 * t)
            for k, alt in enumerate((0.55, 0.95, 1.35)):
                bx = x - 0.7 * t + k * 0.58 * t
                path.addRect(QRectF(bx, y + 0.8 * t - alt * t, 0.3 * t, alt * t))
            path.moveTo(x - 0.75 * t, y - 0.2 * t)
            path.lineTo(x - 0.15 * t, y - 0.55 * t)
            path.lineTo(x + 0.25 * t, y - 0.35 * t)
            path.lineTo(x + 0.9 * t, y - 0.95 * t)
        elif tipo == "claude":
            for k in range(10):
                a = k / 10 * math.tau + 0.2
                lg = t * (1.0 if k % 2 == 0 else 0.72)
                path.moveTo(x + math.cos(a) * t * 0.16, y + math.sin(a) * t * 0.16)
                path.lineTo(x + math.cos(a) * lg, y + math.sin(a) * lg)
        p.setBrush(Qt.NoBrush)
        for larg, a in ((7, 26), (3.6, 60), (1.8, 255)):
            p.setPen(QPen(cor(CIANO, a * forca), larg * self.s(), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)

    def apps_vivo(self, p, agora):
        for i, r in enumerate(self.blocos_apps()):
            foco = 1.0 if r.contains(self.mouse) else 0.0
            if self.clique_app and self.clique_app[0] == i and agora - self.clique_app[1] < 0.4:
                foco = 1.0
            if foco:
                self.bloco_app(p, r.translated(0, -2 * self.s()), i, foco)

    # --- a lista de notas
    def notas_vivo(self, p):
        s = self.s()
        A = self.area_lista()
        p.save()
        p.setClipRect(A.adjusted(-4, 0, 4, 0))
        atual = self.nota[0] if self.nota else None
        for r, (tipo, val, rot, dir_) in self.linhas_lista():
            if r.bottom() < A.top() or r.top() > A.bottom():
                continue
            if tipo == "secao":
                p.setFont(fonte(11.5 * s, QFont.DemiBold, D.F_TITULO, 11.5 * s * 0.18))
                p.setPen(cor(TITULO, 170))
                p.drawText(QRectF(r.left() + 4 * s, r.top() + 6 * s, r.width(), r.height() - 6 * s),
                           Qt.AlignLeft | Qt.AlignVCenter, val)
                if rot:
                    p.drawText(QRectF(r.left(), r.top() + 6 * s, r.width() - 6 * s, r.height() - 6 * s),
                               Qt.AlignRight | Qt.AlignVCenter, rot)
                continue
            if tipo == "vazio":
                p.setFont(fonte(13.5 * s))
                p.setPen(SUAVE)
                p.drawText(r.adjusted(8 * s, 0, 0, 0), Qt.AlignLeft | Qt.AlignVCenter, rot)
                continue
            sel = atual is not None and val == atual
            foco = r.contains(self.mouse)
            if sel or foco:
                p.setPen(Qt.NoPen)
                p.setBrush(cor(CIANO, 34 if sel else 18))
                p.drawRoundedRect(r.adjusted(0, 2 * s, 0, -2 * s), 8 * s, 8 * s)
            if sel:
                p.setBrush(CIANO)
                p.drawRoundedRect(QRectF(r.left(), r.top() + 7 * s, 3 * s, r.height() - 14 * s), 1.5 * s, 1.5 * s)
            cx, cy, d = r.left() + 14 * s, r.center().y(), 3.6 * s
            p.setPen(Qt.NoPen)
            p.setBrush(cor(CIANO, 230 if (sel or foco) else 120))
            p.drawPolygon(QPolygonF([QPointF(cx, cy - d), QPointF(cx + d, cy), QPointF(cx, cy + d), QPointF(cx - d, cy)]))
            p.setFont(fonte(11.5 * s))
            fm_d = QFontMetrics(p.font())
            wd = fm_d.horizontalAdvance(dir_) if dir_ else 0
            if dir_:
                p.setPen(cor(SUAVE, 170))
                p.drawText(QRectF(r.right() - wd - 10 * s, r.top(), wd + 4, r.height()), Qt.AlignRight | Qt.AlignVCenter, dir_)
            p.setFont(fonte(14 * s, QFont.Medium if sel else QFont.Normal))
            fm = QFontMetrics(p.font())
            area = r.width() - 30 * s - wd - 18 * s
            p.setPen(QColor(240, 252, 255) if (sel or foco) else QColor(205, 222, 238))
            p.drawText(QRectF(r.left() + 28 * s, r.top(), area, r.height()), Qt.AlignLeft | Qt.AlignVCenter,
                       fm.elidedText(rot, Qt.ElideRight, int(area)))
        p.restore()
        # a barrinha de rolagem da lista
        total = getattr(self, "lista_total", 0)
        if total > A.height():
            frac = A.height() / total
            y = A.top() + (A.height() - A.height() * frac) * (self.lista_off / max(1, total - A.height()))
            p.setPen(Qt.NoPen)
            p.setBrush(cor(CIANO, 90))
            p.drawRoundedRect(QRectF(A.right() + 6 * s, y, 3 * s, A.height() * frac), 1.5 * s, 1.5 * s)

    # --- a área de leitura
    def leitura_vivo(self, p):
        s = self.s()
        _, _, L = self.areas()
        x = L.left() + 30 * s
        larg = L.width() - 60 * s
        if not self.nota:
            c = QPointF(L.center().x(), L.center().y() - 26 * s)
            self.icone(p, "obsidian", c, 30 * s, 0.6)
            p.setFont(fonte(19 * s, QFont.Light, D.F_RELOGIO))
            p.setPen(QColor(220, 238, 250))
            p.drawText(QRectF(L.left(), c.y() + 44 * s, L.width(), 30 * s), Qt.AlignCenter, "Escolha uma nota para ler")
            p.setFont(fonte(13 * s))
            p.setPen(cor(SUAVE, 200))
            p.drawText(QRectF(L.left(), c.y() + 76 * s, L.width(), 24 * s), Qt.AlignCenter,
                       "Aqui é só leitura: nada do que aparece é alterado.")
            return
        caminho, mtime = self.nota
        titulo = nome_bonito(caminho)
        f = fonte(26 * s, QFont.Normal, D.F_RELOGIO)
        p.setFont(f)
        fm = QFontMetrics(f)
        titulo = fm.elidedText(titulo, Qt.ElideRight, int(larg))
        caixa = QRectF(x, L.top() + 44 * s, larg, 38 * s)
        for d, a in ((3, 22), (1.6, 45)):                 # o brilho neon do título
            p.setPen(cor(CIANO, a))
            for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d)):
                p.drawText(caixa.translated(dx, dy), Qt.AlignLeft | Qt.AlignVCenter, titulo)
        p.setPen(QColor(244, 252, 255))
        p.drawText(caixa, Qt.AlignLeft | Qt.AlignVCenter, titulo)
        try:
            rel = caminho.parent.relative_to(INICIO).as_posix().replace("/", "  ›  ")
        except ValueError:
            rel = ""
        p.setFont(fonte(12 * s))
        fm2 = QFontMetrics(p.font())
        info = f"{rel}   ·   editada {quando(mtime)}" if rel else f"editada {quando(mtime)}"
        p.setPen(cor(SUAVE, 200))
        p.drawText(QRectF(x, caixa.bottom() + 2 * s, larg, 22 * s), Qt.AlignLeft | Qt.AlignVCenter,
                   fm2.elidedText(info, Qt.ElideMiddle, int(larg)))
        gl = QLinearGradient(QPointF(x, 0), QPointF(x + larg, 0))
        gl.setColorAt(0, cor(CIANO, 150))
        gl.setColorAt(1, cor(CIANO, 0))
        p.setPen(QPen(QBrush(gl), 1.2))
        y = L.top() + 112 * s
        p.drawLine(QPointF(x, y), QPointF(x + larg, y))

    # --- cabeçalho e rodapé
    def cabecalho_c(self, p, R, agora):
        h = self.height()
        tam = h * 0.022
        caixa = QRectF(R.left(), R.top() - h * 0.058, R.width(), h * 0.04)
        p.setFont(fonte(tam, QFont.DemiBold, D.F_TITULO, tam * 0.22))
        p.setPen(TITULO)
        p.drawText(caixa, Qt.AlignLeft | Qt.AlignVCenter, "SEXTA-FEIRA · CENTRAL DE COMANDO")
        hora = datetime.datetime.now().strftime("%H:%M")
        fm = QFontMetrics(p.font())
        larg = fm.horizontalAdvance(hora)
        p.drawText(caixa, Qt.AlignRight | Qt.AlignVCenter, hora)
        a = 0.5 + 0.5 * math.sin(agora * 2.4)
        p.setPen(Qt.NoPen)
        cx = R.right() - larg - tam * 0.9
        p.setBrush(cor(CIANO, 60 * a))
        p.drawEllipse(QPointF(cx, caixa.center().y()), tam * 0.42, tam * 0.42)
        p.setBrush(cor(CIANO, 170 + 85 * a))
        p.drawEllipse(QPointF(cx, caixa.center().y()), tam * 0.24, tam * 0.24)

    def rodape_c(self, p, w, h, agora):
        R = self.moldura_r()
        caixa = QRectF(R.left(), h * 0.934, R.width(), h * 0.03)
        if self.status and agora < self.status[2]:
            p.setFont(fonte(h * 0.017, QFont.Medium))
            p.setPen(self.status[1])
            p.drawText(caixa, Qt.AlignCenter, self.status[0])
            return
        tam = h * 0.0155
        p.setFont(fonte(tam, QFont.Normal, D.F_TEXTO, tam * 0.12))
        p.setPen(QColor(150, 180, 205, 150))
        p.drawText(caixa, Qt.AlignCenter,
                   "Clique num app para abrir  ·  Enter na barra fala com a Sexta  ·  Esc ou clique fora para voltar")
