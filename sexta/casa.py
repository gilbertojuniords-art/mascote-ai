# Casa da Sexta-Feira — protótipo (14/11/2026, ideia do usuário).
#
# O visor vira a "casa" da mascote: uma página HTML aberta no navegador do Obsidian
# (Web viewer), servida pela própria mascote em http://127.0.0.1:47817 (só este PC enxerga;
# nada fica exposto na rede). A nota "Visor.md" continua sendo o ROTEIRO: o Claude
# escreve nela, e a casa é o PALCO que a mostra.
#
# Como a mascote "mora" lá:
#   - a página conta para a mascote onde está cada seção (POST /posicoes);
#   - a mascote conta para a página o que mostrar (GET /estado): quantas seções já foram
#     "montadas" e qual é a atual. Quando o visor muda num turno, a casa fica em obra e
#     cada seção aparece quando a Sexta fala dela.

import html, http.server, json, pathlib, re, threading, time
import sys as _sys, pathlib as _pl  # 16/11: com "-P" o Python não procura na pasta do arquivo; sem isto, nada abria
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg

PORTA = 47817
HOOKS = pathlib.Path(__file__).resolve().parent
VISOR = cfg.nota("visor")
PAGINA = HOOKS / "casa.html"
MERMAID = HOOKS / "mermaid.min.js"   # mermaid 11.17.2, baixado do jsDelivr em 14/11/2026

# ---------------------------------------------------------------- nota -> HTML (simples)
def _inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    t = re.sub(r"\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    return t

def _fluxo(linhas):
    # Mermaid de verdade fica para depois: aqui viram caixinhas em sequência.
    rotulos = []
    for a, b, c in re.findall(r'\["([^"]*)"\]|\("([^"]*)"\)|\{"([^"]*)"\}', "\n".join(linhas)):
        r = (a or b or c).replace("<br/>", "\n").replace("<br>", "\n")
        rotulos.append("<br>".join(_inline(x) for x in r.split("\n")))
    if not rotulos:
        return "<pre>" + html.escape("\n".join(linhas)) + "</pre>"
    caixas = '<span class="seta">→</span>'.join(f'<span class="no">{r}</span>' for r in rotulos)
    return f'<div class="fluxo">{caixas}</div>'

def _tabela(linhas):
    def celulas(l):
        return [c.strip() for c in l.strip().strip("|").split("|")]
    cab, corpo = celulas(linhas[0]), [celulas(l) for l in linhas[2:]]
    h = "<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in cab) + "</tr></thead><tbody>"
    for row in corpo:
        h += "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>"
    return h + "</tbody></table>"

def _bloco(linhas):
    out, i, par = [], 0, []
    def fecha_par():
        if par:
            out.append("<p>" + "<br>".join(_inline(x) for x in par) + "</p>")
            par.clear()
    while i < len(linhas):
        l = linhas[i]
        s = l.strip()
        if s.startswith("```"):
            fecha_par()
            tipo, j = s[3:].strip(), i + 1
            while j < len(linhas) and not linhas[j].strip().startswith("```"):
                j += 1
            corpo = linhas[i + 1:j]
            if tipo == "mermaid":
                # diagrama de verdade (mermaid.js, servido daqui, sem internet); as caixinhas
                # ficam de reserva, caso o desenho falhe
                out.append('<div class="diagrama"><pre class="mermaid">' + html.escape("\n".join(corpo)) + "</pre>"
                           + '<div class="reserva">' + _fluxo(corpo) + "</div></div>")
            else:
                out.append("<pre>" + html.escape("\n".join(corpo)) + "</pre>")
            i = j + 1
            continue
        if s.startswith("|") and i + 1 < len(linhas) and re.match(r"^\|?\s*:?-{2,}", linhas[i + 1].strip()):
            fecha_par()
            j = i
            while j < len(linhas) and linhas[j].strip().startswith("|"):
                j += 1
            out.append(_tabela(linhas[i:j]))
            i = j
            continue
        m = re.match(r"^(\s*)(?:[-*]|(\d+)[.)])\s+(.*)$", l)
        if m:
            fecha_par()
            tag = "ol" if m.group(2) else "ul"
            itens, j = [], i
            while j < len(linhas):
                mm = re.match(r"^\s*(?:[-*]|\d+[.)])\s+(.*)$", linhas[j])
                if not mm:
                    break
                itens.append(f"<li>{_inline(mm.group(1))}</li>")
                j += 1
            out.append(f"<{tag}>{''.join(itens)}</{tag}>")
            i = j
            continue
        if s.startswith(">"):
            fecha_par()
            out.append(f"<blockquote>{_inline(s.lstrip('> '))}</blockquote>")
        elif s.startswith("### "):
            fecha_par()
            out.append(f"<h3>{_inline(s[4:])}</h3>")
        elif not s:
            fecha_par()
        else:
            par.append(s)
        i += 1
    fecha_par()
    return "".join(out)

def renderizar(md):
    md = re.sub(r"^---\n.*?\n---\n", "", md, flags=re.S)
    assunto = ""
    titulo, intro, secoes, atual = "", [], [], None
    for l in md.splitlines():
        if l.startswith("# ") and not titulo:
            titulo = l[2:].strip()
        elif l.startswith("## "):
            atual = {"titulo": l[3:].strip(), "linhas": []}
            secoes.append(atual)
        elif atual is None:
            intro.append(l)
        else:
            atual["linhas"].append(l)
    return {"titulo": _inline(titulo), "intro": _bloco(intro),
            "secoes": [{"titulo": _inline(s["titulo"]), "html": _bloco(s["linhas"])} for s in secoes]}

# ---------------------------------------------------------------- servidor local
class Casa:
    def __init__(self, log=print):
        self.log = log
        self.trava = threading.Lock()
        self.estado = {"revelado": 999, "atual": None, "fala": False, "emo": "neutra"}
        self.pos, self.pos_t = None, 0.0
        self._cache = (None, None)
        self.servidor = None

    def versao(self):
        try:
            return VISOR.stat().st_mtime
        except Exception:
            return 0.0

    def conteudo(self):
        v = self.versao()
        if self._cache[0] != v:
            try:
                dados = renderizar(VISOR.read_text(encoding="utf-8"))
            except Exception as e:
                dados = {"titulo": "Visor", "intro": f"<p>Não consegui ler o visor ({html.escape(repr(e))}).</p>", "secoes": []}
            dados["v"] = v
            self._cache = (v, dados)
        return self._cache[1]

    def posicoes(self, maximo_s=2.0):
        with self.trava:
            return self.pos if self.pos and time.time() - self.pos_t < maximo_s else None

    def mudar(self, **k):
        with self.trava:
            self.estado.update(k)

    def iniciar(self):
        casa = self

        class Atende(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _enviar(self, corpo, tipo="application/json; charset=utf-8"):
                b = corpo if isinstance(corpo, bytes) else corpo.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", tipo)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def _daqui(self):
                # 15/11: só atende quem chama pelo endereço do próprio PC. Fecha a brecha em
                # que um site aberto no navegador tenta ler o visor apontando um domínio para cá.
                host = (self.headers.get("Host") or "").split(":")[0].strip().lower()
                if host in ("127.0.0.1", "localhost"):
                    return True
                self.send_error(403)
                return False

            def do_GET(self):
                if not self._daqui():
                    return
                if self.path in ("/", "/index.html"):
                    self._enviar(PAGINA.read_bytes(), "text/html; charset=utf-8")
                elif self.path.startswith("/mermaid.js") and MERMAID.exists():
                    self._enviar(MERMAID.read_bytes(), "text/javascript; charset=utf-8")
                elif self.path.startswith("/conteudo"):
                    self._enviar(json.dumps(casa.conteudo()))
                elif self.path.startswith("/estado"):
                    with casa.trava:
                        e = dict(casa.estado)
                    e["v"] = casa.versao()
                    self._enviar(json.dumps(e))
                else:
                    self.send_error(404)

            def do_POST(self):
                if not self._daqui():
                    return
                if self.path.startswith("/posicoes"):
                    n = min(int(self.headers.get("Content-Length") or 0), 200_000)
                    try:
                        d = json.loads(self.rfile.read(n) or b"{}")
                        with casa.trava:
                            casa.pos, casa.pos_t = d, time.time()
                    except Exception:
                        pass
                    self._enviar("{}")
                else:
                    self.send_error(404)

        # no Windows, "reusar o endereço" deixa dois programas abrirem a mesma porta;
        # desligado, só uma casa existe por vez (um teste não "rouba" a casa da mascote)
        class Servidor(http.server.ThreadingHTTPServer):
            allow_reuse_address = False
        try:
            self.servidor = Servidor(("127.0.0.1", PORTA), Atende)
        except OSError as e:
            self.log(f"casa: não abriu a porta {PORTA} ({e!r})")
            return False
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        self.log(f"casa: aberta em http://127.0.0.1:{PORTA}")
        return True
