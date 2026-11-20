# Repertório da Sexta. Criado em 15/11/2026, pedido do usuário.
#
# O que ela faz SOZINHA, sem Claude, sem internet e sem IA nenhuma: hoje, abrir pastas e programas.
# "Eu dependo muito do Claude para, por exemplo, abrir uma pasta, abrir um programa" (o usuário).
#
#   - O catálogo é uma nota do cofre: Repertório.md (o usuário edita).
#     Os programas do Menu Iniciar entram sozinhos, menos ferramentas de sistema e desinstaladores.
#   - Toda ação passa pelas Leis da Sexta (leis.py). Abrir é risco "livre".
#   - Só entende frases curtas que COMEÇAM com "abre/abra/abrir". "Abre o chat" fica de fora
#     (é a marca [F8] da Sexta rápida). O que não bate com o catálogo volta para o Haiku, como antes.
#   - O registro anota só "abriu pasta" ou "abriu programa", nunca o nome (regra de privacidade).
#
# Teste sem abrir nada: python "repertorio.py" testar "abre a pasta de downloads"

import difflib, os, pathlib, re, unicodedata
import sys as _sys, pathlib as _pl  # 16/11: com "-P" o Python não procura na pasta do arquivo; sem isto, nada abria
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg
try:   # 16/11: registro encadeado (seguranca.py)
    from seguranca import auditar as _auditar
except Exception:
    _auditar = lambda *a, **k: None

COFRE = cfg.COFRE
NOTA = cfg.nota("repertorio")
MENUS = [pathlib.Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
         pathlib.Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Microsoft/Windows/Start Menu/Programs"]

# Ferramentas de sistema e afins ficam FORA do repertório automático (segurança e menos confusão).
FORA = re.compile(r"desinstal|uninstall|registry|regedit|command prompt|powershell|\bcmd\b|recovery|disk cleanup|"
                  r"computer management|administrative|event viewer|services|print management|odbc|memory diag|"
                  r"performance monitor|system config|task scheduler|windows tools|security|defender|firewall|"
                  r"avast|developer|verifier|debuggable|documentation|manual|release notes|ajuda|module docs|"
                  r"telemetria|o que ha de novo|^sexta.feira|readme|license|licen[cs]a|website|help", re.I)
RESERVADO = {"chat", "o chat", "microfone", "o microfone", "f8"}   # é da Sexta rápida ([F8])
VERBO = re.compile(r"^(?:sexta(?: feira)?\s+)?(?:abre|abra|abrir|abri|abre ai|abra pra mim|abre pra mim)\s+(?P<resto>.+)$")
GENERICO = {"microsoft", "windows", "google", "python", "git", "the"}


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


PASTAS_DO_WINDOWS = {   # o lugar de verdade muda de PC para PC (o Windows diz onde fica)
    "{Downloads}": "{374DE290-123F-4565-9164-39C4925E467B}",
    "{Desktop}": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
    "{Documentos}": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
}


def _pasta_do_windows(guid):
    import ctypes, uuid
    from ctypes import wintypes
    g = uuid.UUID(guid)
    buf = (ctypes.c_byte * 16).from_buffer_copy(g.bytes_le)
    p = ctypes.c_wchar_p()
    if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(buf), 0, None, ctypes.byref(p)) != 0:
        return None
    s = p.value
    ctypes.windll.ole32.CoTaskMemFree(p)
    return s


def resolver(caminho):
    for marca, guid in PASTAS_DO_WINDOWS.items():
        if marca in caminho:
            real = _pasta_do_windows(guid)
            if real:
                caminho = caminho.replace(marca, real)
    return os.path.expandvars(caminho)


def _tabela(texto, titulo):
    """Linhas 'apelidos | caminho' da seção ## titulo da nota."""
    parte = re.split(r"^## ", texto, flags=re.M)
    sec = next((p for p in parte if p.lower().startswith(titulo)), "")
    linhas = []
    for l in sec.splitlines():
        cel = [c.strip() for c in l.strip().strip("|").split("|")]
        if len(cel) == 2 and cel[0] and not cel[0].startswith("-") and cel[0].lower() != "apelidos":
            linhas.append(([a.strip() for a in cel[0].split(",") if a.strip()], cel[1]))
    return linhas


def programas_do_menu():
    progs = {}
    for base in MENUS:
        try:
            for lnk in base.rglob("*.lnk"):
                nome = lnk.stem
                if not FORA.search(norm(nome)) and not FORA.search(nome):
                    progs.setdefault(nome, str(lnk))
        except Exception:
            pass
    return progs


def catalogo():
    """[(apelido_normalizado, tipo, alvo, nome_falado)]"""
    itens = []
    try:
        texto = NOTA.read_text(encoding="utf-8")
    except Exception:
        texto = ""
    for apelidos, caminho in _tabela(texto, "pastas"):
        alvo = resolver(caminho)
        for a in apelidos:
            itens.append((norm(a), "pasta", alvo, apelidos[0]))
    menu = programas_do_menu()
    for apelidos, caminho in _tabela(texto, "programas"):
        alvo = menu.get(caminho, resolver(caminho))   # pode apontar para um nome do Menu Iniciar
        for a in apelidos:
            itens.append((norm(a), "programa", alvo, apelidos[0]))
    primeiras = {}
    for nome in menu:
        p = norm(nome).split()
        if p and p[0] not in GENERICO and len(p[0]) >= 3:
            primeiras[p[0]] = primeiras.get(p[0], 0) + 1
    for nome, lnk in menu.items():
        n = norm(nome)
        itens.append((n, "programa", lnk, nome))
        p = n.split()
        if len(p) > 1 and primeiras.get(p[0]) == 1:   # "discord" para "Discord", só se não for ambíguo
            itens.append((p[0], "programa", lnk, nome))
    return itens


def entender(fala):
    """Devolve (tipo, alvo, nome) se a fala é um pedido do repertório; senão None."""
    t = norm(fala)
    if len(t.split()) > 9:
        return None
    m = VERBO.match(t)
    if not m:
        return None
    resto = m.group("resto")
    if resto in RESERVADO or resto.endswith(" chat"):
        return None
    quer_pasta = bool(re.match(r"(?:a |as )?pastas?\b", resto))
    quer_prog = bool(re.match(r"(?:o |os )?(?:programa|aplicativo|app)s?\b", resto))
    resto = re.sub(r"^(?:a |o |as |os )?(?:pastas?|programas?|aplicativos?|apps?)\s*", "", resto)
    resto = re.sub(r"^(?:a |o |as |os |de |da |do |das |dos )+", "", resto).strip()
    resto = re.sub(r"\s+(?:pra mim|por favor|ai)$", "", resto).strip()
    if not resto or resto in RESERVADO:
        return None
    melhor, nota = None, 0.0
    for apelido, tipo, alvo, nome in catalogo():
        if (quer_pasta and tipo != "pasta") or (quer_prog and tipo != "programa"):
            continue
        if apelido == resto:
            s = 1.0
        elif len(resto) >= 4 and (resto in apelido.split() or apelido in resto.split()):
            s = 0.9
        else:
            s = difflib.SequenceMatcher(None, resto, apelido).ratio()
        if s > nota:
            melhor, nota = (tipo, alvo, nome), s
    return melhor if nota >= 0.82 else None


def executar(fala, julgar=None, log=None, origem="usuario"):
    """Tenta fazer o pedido. Devolve a frase que ela fala, ou None (não é do repertório).
    16/11: origem = de onde veio o pedido; só "usuario" passa pela lei (seguranca.py)."""
    achou = entender(fala)
    if not achou:
        return None
    tipo, alvo, nome = achou
    if julgar:
        ok, lei, motivo = julgar({"tipo": "acao", "risco": "livre", "origem": origem})
        if not ok:
            _auditar("abrir recusado", tipo=tipo, lei=lei)
            return f"Agora não posso, {cfg.NOME}. {motivo.capitalize()}."
    if tipo == "pasta" and not os.path.isdir(alvo):
        return f"Não achei a pasta {nome} no lugar de sempre, {cfg.NOME}."
    try:
        os.startfile(alvo)
    except Exception:
        if log:
            log(f"repertório: falhou ao abrir {tipo}")
        return f"Tentei abrir {nome}, mas o Windows não deixou."
    if log:
        log(f"repertório: abriu {tipo} (sem IA)")
    _auditar("abriu", tipo=tipo)   # só o tipo (pasta/programa), nunca o nome
    return f"Abrindo {'a pasta ' if tipo == 'pasta' else ''}{nome}."


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["testar"]:
        for fala in sys.argv[2:]:
            print(f"{fala!r:45} -> {entender(fala)}")
