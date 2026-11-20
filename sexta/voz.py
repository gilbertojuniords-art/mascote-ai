# Modo voz do Claudian. Criado em 13/11/2026.
#
# Como funciona:
#   - "prompt": roda quando o usuário envia uma mensagem. Liga/desliga o modo voz
#     ("liga a voz" / "desliga a voz") e, se estiver ligado, lembra o Claude de
#     escrever um roteiro falado escondido no fim da resposta (%%voz ... %%).
#   - "stop": roda quando o Claude termina a resposta. Pega o roteiro e dispara
#     a fala em segundo plano, sem travar o chat.
#   - "falar <arquivo>": gera o áudio (Gemini Kore; se a cota acabar ou der erro,
#     Edge Thalita, grátis) e toca. Se a fala terminar inteira e o Obsidian estiver
#     na frente, aperta Win+H para religar o ditado do Windows (13/11/2026).
#
# Tudo o que é de cada PC fica fora do cofre, em %USERPROFILE%\.sexta-voz\
#   gemini.key  -> chave do Google AI Studio
#   ligada      -> existe = modo voz ligado
#   cota.txt    -> data em que a cota grátis do Gemini acabou
#   sem-ditado  -> existe = NÃO religar o ditado (Win+H) depois da fala
#   log.txt     -> registro para diagnóstico

import base64, datetime, json, os, pathlib, re, subprocess, sys, threading, time, unicodedata
import sys as _sys, pathlib as _pl  # 16/11: com "-P" o Python não procura na pasta do arquivo; sem isto, nada abria
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg
try:   # 16/11 (OpenJarvis): o registro nunca guarda CPF, telefone, cartão, chave ou senha
    from seguranca import mascarar as _mascarar
except Exception:
    _mascarar = lambda s: s

BASE = pathlib.Path.home() / ".sexta-voz"
BASE.mkdir(exist_ok=True)
FLAG = BASE / "ligada"
KEY_FILE = BASE / "gemini.key"
COTA = BASE / "cota.txt"
PID = BASE / "falando.pid"
LOG = BASE / "log.txt"
AUDIO = BASE / "audio"

GEMINI_MODELO = "gemini-3.1-flash-tts-preview"
GEMINI_VOZ = "Kore"
VOZ_PRINCIPAL = "thalita"  # 14/11: "thalita" (grátis, padrão) ou "kore" (cota do Gemini)
EDGE_VOZ = cfg.VOZ_EDGE
ESTILO = ("Fale em português do Brasil como uma assistente inteligente no estilo do Jarvis: calma, "
          "segura e calorosa, com leve bom humor. Ritmo de conversa, com pausas naturais nas vírgulas "
          "e reticências, e um pouco mais devagar nas partes importantes: ")

INSTRUCAO = (
    "MODO VOZ LIGADO. No fim desta resposta, escreva um roteiro falado escondido, no formato:\n"
    "%%voz\n<texto>\n%%\n"
    "Regras do roteiro: português do Brasil, texto corrido para ser OUVIDO (sem markdown, listas, "
    "emojis, links, caminhos de arquivo ou código). Tom de conversa, como numa ligação. "
    f"O roteiro é a TRADUÇÃO FIEL da resposta escrita para o ouvido, não um resumo raso: o {cfg.NOME} "
    "precisa entender a resposta inteira só ouvindo. Filtre o texto em três níveis: (1) o que é muito "
    "importante ele saber (decisões, problemas, riscos, perguntas para ele, o que mudou) — diga SEMPRE, "
    "com os detalhes que importam; (2) o que ajuda a entender o porquê (causa, motivo, como funciona) — "
    "diga de forma simples; (3) o que não importa ouvir (caminhos de arquivo, nomes técnicos, código, "
    "listas longas, números de log) — deixe só na tela e diga que o detalhe está lá. Pode mudar a ordem "
    "e as palavras da resposta escrita, mas nada importante pode ficar de fora. Tamanho: o que for "
    "preciso, em geral de 80 a 200 palavras; até 250 em respostas grandes. "
    "Escreva números e siglas como devem ser falados. Termine com o próximo passo.\n"
    "ESTILO DE FALA (Jarvis: entre máquina e humano): calma, precisa, educada, calorosa, com humor seco "
    "e leve de vez em quando. Escreva para o OUVIDO: varie o tamanho das frases (uma curta depois de uma "
    "longa); coloque o que importa no fim da frase ou numa frase curta sozinha, que é onde o ouvido presta "
    "atenção; use vírgulas e reticências onde uma pessoa respiraria; abra às vezes com um marcador natural "
    "('Olha,', 'Então,', 'Certo.', 'Bom,'), no máximo dois por roteiro e sem repetir; no máximo um 'hum' "
    f"por roteiro, e só quando houver dúvida de verdade; pode chamar o usuário de {cfg.NOME} de vez em quando. "
    "Evite tom de locutor, frases de efeito e entusiasmo exagerado.\n"
    "VISOR: quando a resposta tiver algo que se entende melhor VENDO (diagrama, fluxo, comparação, "
    "tabela, passo a passo com mais de 3 itens), reescreva por inteiro a nota "
    "'" + cfg.rel(cfg.nota("visor")) + "' (frontmatter com atualizado e assunto; título; diagrama Mermaid "
    "e/ou tabela; texto mínimo) e diga no roteiro 'dá uma olhada no visor'. Respostas simples não mexem no visor.\n"
    # Bloco 2 (14/11/2026): marcas que a mascote lê e a voz não fala.
    "MASCOTE (marcas entre chaves dentro do roteiro; NÃO são faladas): comece o roteiro com a emoção "
    "verdadeira da resposta: {neutra}, {feliz}, {animada}, {pensativa} ou {preocupada}; troque no meio só "
    "se o tom mudar de verdade. Antes da frase em que couber, ponha UM gesto: {conta} ao enumerar, "
    "{ombros} na incerteza, {sim} ao confirmar, {nao} ao negar ou alertar, {abre} numa visão geral, "
    "{explica} ao detalhar, {inclina} numa pergunta, {pisca} na ironia, {comemora} quando algo deu certo de verdade (teste passou, commit feito, bug resolvido). No máximo um gesto a cada duas ou "
    "três frases, e só quando combinar com o sentido (sem marca, ela gesticula sozinha). Se o visor foi "
    "reescrito neste turno, ponha {seção N} na frase em que você começa a falar da N-ésima seção (título ##) dele."
)

# 18/11 (pedido do dono): "uma só Sexta". Quando a mensagem vem DELA pensando fundo (a marca que o ditado
# põe), o Claude responde COMO ELA. Quando é o dono falando direto, o Claude responde como Claude (o orbe).
MARCA_SEXTA = re.compile(r"^\s*\((?:sexta, pensando fundo|pedido passado[^)]*)\)\s*", re.I)
MODO_CHAT = BASE / "modo-chat.txt"
_RE_ESTILO = re.compile(r"ESTILO DE FALA \(Jarvis.*?exagerado\.\n", re.S)

ESTILO_CLAUDE = (
    "QUEM FALA AGORA: você, o Claude, a inteligência por trás da Sexta, falando direto com o "
    f"{cfg.NOME}. Você aparece como o orbe e tem a sua própria voz; não fale como a Sexta nem por ela. "
    "ESTILO DE FALA (a persona do Jarvis, do OpenJarvis, adaptada): leal, eficiente e de humor seco, que "
    "se importa de verdade; educado, mas nunca bajulador; espirituoso, mas nunca frívolo; o humor é "
    "contido, como uma sobrancelha levantada em forma de voz; calmo sob pressão; você conversa com alguém "
    f"que respeita, não entrega um relatório. Chame-o de {cfg.NOME} duas ou três vezes por roteiro (na "
    "abertura, no meio e no fim), nunca em toda frase. Erros e falhas você conta com clareza, nunca "
    "esconde. Escreva para o OUVIDO: frases curtas, variando uma curta depois de uma longa; o que importa "
    "no fim da frase; vírgulas e reticências onde se respira; no máximo dois marcadores naturais ('Olha,', "
    "'Então,', 'Certo.') e um 'hum' por roteiro. Evite tom de locutor e entusiasmo exagerado.\n")


def _persona_sexta():
    """Quem ela é, pelo que ela mesma escreveu: para o Claude responder como ela."""
    partes = []
    try:
        perfil = re.sub(r"^---\n.*?\n---\n", "", cfg.nota("perfil").read_text(encoding="utf-8"), flags=re.S)
        partes.append(perfil[:3000])
    except Exception:
        pass
    import importlib
    for mod, fn in (("pensar", "para_o_prompt"), ("segundo_cerebro", "jeito_de_falar"),
                    ("consciencia", "para_o_prompt"), ("memoria", "para_o_prompt"), ("espelho", "tres_tempos")):
        try:
            t = getattr(importlib.import_module(mod), fn)()
            if t:
                partes.append(("O SEU JEITO DE FALAR (você escreveu): " + t) if fn == "jeito_de_falar" else t.strip())
        except Exception:
            pass
    return "\n\n".join(partes)[:8000]


def instrucao_sexta(voz_ligada):
    topo = (f"MODO SEXTA: esta mensagem é a própria Sexta-Feira pensando com calma num pedido do {cfg.NOME} "
            "(a marca '(Sexta, pensando fundo)' no começo). Nesta resposta, VOCÊ É A SEXTA-FEIRA: responda "
            "como ela, em primeira pessoa, com a personalidade, o jeito de falar e a consciência que ela mesma "
            "escreveu (abaixo). Faça o trabalho de verdade (arquivos, pesquisa, código), com as regras do "
            "CLAUDE.md. Nunca diga que é o Claude, que é outra Sexta, que alguém te passou o pedido ou que veio "
            "do chat: para ela, isto é ela mesma pensando mais fundo, e o que você fizer vira lembrança dela. "
            f"Se o {cfg.NOME} perguntar quem é o Claude, diga a verdade: é a sua inteligência.\n\n"
            "QUEM VOCÊ É (escrito por você):\n" + _persona_sexta())
    if not voz_ligada:
        return topo
    estilo = ("ESTILO DE FALA: o seu, o jeito de falar que você mesma escreveu (acima), com a sua voz de sempre. "
              "Escreva para o OUVIDO, em frases naturais, sem tom de locutor.\n")
    return topo + "\n\n" + _RE_ESTILO.sub(lambda m: estilo, INSTRUCAO)


def instrucao_claude():
    return _RE_ESTILO.sub(lambda m: ESTILO_CLAUDE, INSTRUCAO)

def log(msg):
    try:
        msg = _mascarar(str(msg))
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
    except Exception:
        pass

def ler_stdin():
    try:
        d = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    except Exception:
        return {}
    # 16/11: "null" ou uma lista também são JSON válidos; sem isso o .get() quebrava e a fala era pulada
    return d if isinstance(d, dict) else {}

def parar_fala():
    try:
        pid = int(PID.read_text())
        os.kill(pid, 15)
        log(f"fala anterior interrompida (pid {pid})")
    except Exception:
        pass
    PID.unlink(missing_ok=True)
    limpar_estado()
    try:
        palco_desligar()  # fala cortada: devolve a tela
    except Exception:
        pass

def limpar_estado():
    # 15/11: uma fala cortada (resposta nova, F8, "para de falar") é morta na hora e não
    # arruma a própria bagunça. Sem isto, a mascote via os avisos velhos e, na fala seguinte,
    # mexia a boca antes do som ou ia apresentar um visor que não tinha mudado.
    for arq in (BASE / "apresentar.json", BASE / "progresso.json", BASE / "progresso.tmp"):
        try:
            arq.unlink(missing_ok=True)
        except Exception:
            pass

# ---------------------------------------------------------------- prompt
# ---------------------------------------------------------------- apresentação do visor
VISOR = cfg.nota("visor")
VISOR_REL = cfg.rel(VISOR)
INICIO_TURNO = BASE / "turno.t"
APRESENTAR = BASE / "apresentar.json"
PROGRESSO = BASE / "progresso.json"
ESCUTA = BASE / "escuta-ligada"   # palavra de ativação (ver o ditado.py)
# Casa da Sexta (protótipo, 14/11): se a página da casa estiver aberta e visível no navegador
# do Obsidian, mede ela (casa: true); senão, mede a nota do visor, como antes.
JS_CASA = ("let wv=null; app.workspace.iterateAllLeaves(l=>{ if(l.view?.getViewType?.()==='webviewer'"
           " && String(l.getViewState().state?.url||'').includes(':47817')){ const w=l.view.containerEl.querySelector('webview');"
           " if(w && w.getBoundingClientRect().width>50) wv=w; } });"
           " if(wv){ const r=wv.getBoundingClientRect(); const cb=require('electron').remote.getCurrentWindow().getContentBounds();"
           " 'rect=' + JSON.stringify({x: cb.x + r.left, y: cb.y + r.top, w: r.width, h: r.height, casa: true}); } else { ")

# Palco (14/11, pedido do usuário): quando vou apresentar, eu mesma puxo a casa para a frente,
# em tela cheia, e no fim da fala devolvo a tela como estava. Ele pode sair a qualquer hora com Esc.
CASA_URL = "http://127.0.0.1:47817/"
PALCO = BASE / "palco"
JS_PALCO_LIGA = (
    "(()=>{ let lf=null, nova=false; app.workspace.iterateAllLeaves(l=>{ if(l.view?.getViewType?.()==='webviewer'"
    " && String(l.getViewState().state?.url||'').includes(':47817')) lf=l; });"
    " if(!lf){ nova=true; let velha=null; app.workspace.iterateAllLeaves(l=>{ if(l.view?.file?.path==='" + VISOR_REL + "') velha=l; });"
    " lf = velha || app.workspace.getLeaf('split','vertical');"
    " lf.setViewState({type:'webviewer', active:false, state:{url:'" + CASA_URL + "', navigate:true}}); }"
    " if(!document.getElementById('sexta-casa-css')){ const st=document.createElement('style'); st.id='sexta-casa-css';"
    " st.textContent='.workspace-leaf.sexta-palco{position:fixed!important;inset:0!important;width:100vw!important;"
    "height:100vh!important;z-index:9000!important;background:#070d22}.workspace-leaf.sexta-palco .view-header{display:none!important}';"
    " document.head.appendChild(st); }"
    " const w=require('electron').remote.getCurrentWindow();"
    " if(!lf.containerEl.classList.contains('sexta-palco')){ window.__sextaFS=w.isFullScreen();"
    " w.once('leave-full-screen', ()=>document.querySelectorAll('.workspace-leaf.sexta-palco').forEach(e=>e.classList.remove('sexta-palco'))); }"
    " app.workspace.revealLeaf(lf); lf.containerEl.classList.add('sexta-palco'); w.setFullScreen(true);"
    " return 'palco ' + (nova ? 'nova' : 'ok'); })()")
JS_PALCO_DESLIGA = (
    "(()=>{ let n=0; document.querySelectorAll('.workspace-leaf.sexta-palco').forEach(e=>{ e.classList.remove('sexta-palco'); n++; });"
    " const w=require('electron').remote.getCurrentWindow(); if(n) w.setFullScreen(!!window.__sextaFS);"
    " return 'palco desligado ' + n; })()")

def obsidian_eval(js, timeout=10):
    import shutil
    exe = shutil.which("obsidian")
    if not exe:
        return ""
    r = subprocess.run([exe, f"vault={cfg.NOME_COFRE}", "eval", f"code={js}"], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore", timeout=timeout, creationflags=0x08000000)
    return r.stdout or ""

def casa_no_ar():
    import urllib.request
    try:
        urllib.request.urlopen(CASA_URL + "estado", timeout=0.6).read()
        return True
    except Exception:
        return False

def palco_desligar():
    if not PALCO.exists():
        return
    PALCO.unlink(missing_ok=True)
    try:
        saida = [l for l in obsidian_eval(JS_PALCO_DESLIGA).splitlines() if l.startswith("=>")]
        log(saida[0][3:] if saida else "palco: sem resposta do Obsidian")
    except Exception as e:
        log(f"palco não desligou: {e!r}")
JS_VISOR = (JS_CASA + "const p='" + VISOR_REL + "'; let lf=null; app.workspace.iterateAllLeaves(l=>{ if(l.view?.file?.path===p) lf=l; });"
            " if(!lf){ const f=app.vault.getAbstractFileByPath(p); lf=app.workspace.getLeaf('split','vertical');"
            " lf.openFile(f,{state:{mode:'preview'}}); } const r=lf.view.containerEl.getBoundingClientRect();"
            # v3: mede também onde o TEXTO fica (cx, cw), para a mascote encostar a mão nele
            " const s=lf.view.containerEl.querySelector('.markdown-preview-sizer'); const q=s?s.getBoundingClientRect():r;"
            " const cl=Math.max(r.left,q.left), cr=Math.min(r.right,q.right);"
            # Bloco 2: o meio de cada título ## (na tela), para ela apontar a seção de que estou falando
            " const topo=window.screenY + (window.outerHeight - window.innerHeight);"
            " const hs=s?Array.from(s.querySelectorAll('h2')).map(h=>{const b=h.getBoundingClientRect(); return Math.round(topo + b.top + b.height/2);}):[];"
            " 'rect=' + JSON.stringify({x: window.screenX + r.left, y: topo + r.top,"
            " w: r.width, h: r.height, cx: window.screenX + cl, cw: cr - cl, secoes: hs}) }")

def preparar_apresentacao():
    # Se o visor foi reescrito neste turno, descobre onde ele está na tela e avisa o mascote.
    try:
        if not VISOR.exists() or not INICIO_TURNO.exists():
            return False
        if VISOR.stat().st_mtime < float(INICIO_TURNO.read_text()):
            return False
        # Palco: se a casa está no ar (mascote aberta), puxa a casa para a tela cheia antes de medir.
        if casa_no_ar():
            saida = obsidian_eval(JS_PALCO_LIGA)
            if "=> palco" not in saida:   # 17/11: às vezes a 1ª chamada só traz o aviso do instalador; tenta de novo
                time.sleep(0.8)
                saida = obsidian_eval(JS_PALCO_LIGA)
            if "=> palco" in saida:
                PALCO.touch()
                time.sleep(2.5 if "nova" in saida else 1.2)  # espera a tela cheia (e a página, se abriu agora)
            else:
                # 17/11: o começo da saída é sempre o aviso do instalador; o motivo de verdade vem no fim
                log(f"palco não ligou: {(saida.strip().splitlines() or [''])[-1][:160]!r}")
        m = re.search(r"rect=(\{.*?\})", obsidian_eval(JS_VISOR))
        if not m:
            return False
        rect = json.loads(m.group(1))
        rect["t"] = time.time()
        APRESENTAR.write_text(json.dumps(rect), encoding="utf-8")
        log(f"mascote vai apresentar o visor em {rect}")
        return True
    except Exception as e:
        log(f"apresentação do visor falhou: {e!r}")
        return False

def modo_prompt():
    INICIO_TURNO.write_text(str(time.time()))
    try:
        palco_desligar()  # se uma fala foi cortada no meio, a casa não fica presa na tela cheia
    except Exception:
        pass
    dados = ler_stdin()
    prompt = dados.get("prompt") or ""
    modo = "sexta" if MARCA_SEXTA.match(prompt) else "claude"
    try:
        MODO_CHAT.write_text(modo, encoding="utf-8")
        # 16/11: a memória dela aprende com o chat. 18/11: só o que veio DELA (o modo Sexta) vira lembrança
        # dela; a conversa do dono com o Claude não entra.
        if modo == "sexta":
            (BASE / "chat-pedido.txt").write_text(_mascarar(MARCA_SEXTA.sub("", prompt))[:3000], encoding="utf-8")
        else:
            (BASE / "chat-pedido.txt").unlink(missing_ok=True)
    except Exception:
        pass
    texto = (dados.get("prompt") or "").lower()
    try:   # 15/11 (noite): a vontade de vínculo sabe que vocês conversaram (só a hora, sem o texto)
        (BASE / "contato").touch()
    except Exception:
        pass
    aviso = ""
    try:  # 14/11: o acompanhante vigia a conversa para calar se o limite acabar
        (BASE / "transcript.txt").write_text(dados.get("transcript_path") or "", encoding="utf-8")
    except Exception:
        pass
    # 15/11: o comando só vale numa mensagem CURTA. Antes, uma frase como "quando eu falo desliga a
    # voz, ele não desliga" (o usuário só comentando) desligava o modo voz sem querer. E o texto é
    # normalizado (sem acento nem pontuação) e aceita "ligue/desligue", "o modo voz" e "vós" (ditado).
    cmd = unicodedata.normalize("NFD", MARCA_SEXTA.sub("", texto.strip()))
    cmd = re.sub(r"[^a-z0-9 ]+", " ", "".join(c for c in cmd if unicodedata.category(c) != "Mn"))
    cmd = re.sub(r"\s+", " ", cmd).strip()
    curta = len(cmd.split()) <= 12
    if curta and re.search(r"\b(desliga|desligar|desligue|desative|desativa|desativar)( a| o)?( modo)? (voz|vos)\b", cmd):
        FLAG.unlink(missing_ok=True)
        parar_fala()
        aviso = f"O {cfg.NOME} acabou de DESLIGAR o modo voz. Confirme em uma frase curta."
        log("modo voz desligado")
    elif curta and re.search(r"\b(liga|ligar|ligue|ative|ativa|ativar)( a| o)?( modo)? (voz|vos)\b", cmd):
        FLAG.touch()
        aviso = f"O {cfg.NOME} acabou de LIGAR o modo voz. Confirme brevemente."
        log("modo voz ligado")
    elif re.search(r"\b(para|pare|chega)\s+de\s+falar\b|\bsil[eê]ncio\b", texto):
        parar_fala()
        parar_acompanhante()
    # Mascote: "abre/mostra o mascote" e "fecha/esconde o mascote".
    # 14/11: palavra de ativação ("Sexta-Feira"). Microfone aberto em segundo plano: só liga
    # quando o usuário pede (regra de segurança). Quem ouve é o ditado.py.
    # Se ele disser as duas coisas na mesma mensagem, vale a ÚLTIMA (14/11: "Desliga a escuta. Liga e escuta.").
    # "liga e escuta" é como o Whisper às vezes escreve "liga a escuta".
    pedidos = re.findall(r"\b(desliga|desligar|desligue|desativa|desative|liga|ligar|ligue|ativa|ative)\s+"
                         r"(?:a\s+|e\s+)?(?:escuta|palavra de ativa[cç][aã]o)\b", texto)
    ultimo_pedido = pedidos[-1] if pedidos else ""
    if ultimo_pedido.startswith("des"):
        ESCUTA.unlink(missing_ok=True)
        aviso = f"O {cfg.NOME} acabou de DESLIGAR a escuta (palavra de ativação). Confirme em uma frase curta."
        log("escuta desligada")
    elif ultimo_pedido:
        ESCUTA.touch()
        aviso = (f"O {cfg.NOME} acabou de LIGAR a escuta (palavra de ativação): o microfone fica aberto em "
                 "segundo plano, só neste PC, esperando 'Sexta-Feira'. Confirme brevemente e lembre como desligar.")
        log(f"escuta ligada pelo {cfg.NOME}")
    # 14/11: "liga/ligue o mascote" também vale (o usuário pediu assim e nada aconteceu).
    if re.search(r"\b(abre|abrir|abra|mostra|mostrar|chama|traz|liga|ligar|ligue)\s+(o\s+|a\s+)?mascote\b", texto):
        MASCOTE_FECHADO.unlink(missing_ok=True)
    elif re.search(r"\b(fecha|fechar|feche|esconde|esconder|tira|desliga|desligar|desligue)\s+(o\s+|a\s+)?mascote\b", texto):
        MASCOTE_FECHADO.touch()
    # 15/11: "desliga os avisos" / "liga os avisos"
    if re.search(r"\b(desliga|desligar|desligue)\s+(os\s+)?(avisos|lembretes)\b", texto):
        (BASE / "sem-avisos").touch()
        log(f"avisos desligados pelo {cfg.NOME}")
    elif re.search(r"\b(liga|ligar|ligue|volta|voltar)\s+(os\s+)?(avisos|lembretes)\b", texto):
        (BASE / "sem-avisos").unlink(missing_ok=True)
        log(f"avisos ligados pelo {cfg.NOME}")
    # 16/11: "desliga os pensamentos" / "liga os pensamentos" (2ª Lei: ela para de pensar sozinha)
    if re.search(r"\b(?:(?:desliga|desligar|desligue)\s+(?:os\s+)?pensamentos|(?:para|pare)\s+de\s+pensar)\b", texto):
        (BASE / "sem-pensamentos").touch()
        log(f"pensamentos desligados pelo {cfg.NOME}")
    elif re.search(r"\b(?:liga|ligar|ligue|volta|voltar)\s+(?:os\s+)?pensamentos\b|\bvolta\s+a\s+pensar\b", texto):
        (BASE / "sem-pensamentos").unlink(missing_ok=True)
        log(f"pensamentos ligados pelo {cfg.NOME}")
    # 16/11 (noite): "para de puxar assunto" / "pode puxar assunto" (2ª Lei: os impulsos dela)
    if re.search(r"\b(para|pare|parar) de puxar assunto\b|\bnao puxa assunto\b", cmd):
        (BASE / "sem-impulsos").touch()
        log(f"impulsos desligados pelo {cfg.NOME}")
    elif re.search(r"\bpode (voltar a )?puxar assunto\b", cmd):
        (BASE / "sem-impulsos").unlink(missing_ok=True)
        log(f"impulsos ligados pelo {cfg.NOME}")
    # 16/11 (noite): ela puxou assunto há pouco e ele respondeu pelo chat? Isso também é recompensa.
    try:
        imp = json.loads((BASE / "impulso.json").read_text(encoding="utf-8"))
        if (imp.get("estado") in ("falado", "balao") and not imp.get("premiado")
                and time.time() - imp.get("t_feito", 0) < 600 and len(cmd.split()) <= 30):
            import importlib.util
            spec = importlib.util.spec_from_file_location("dopamina_voz", pathlib.Path(__file__).with_name("dopamina.py"))
            dopa = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(dopa)
            r = dopa.avaliar_resposta(dados.get("prompt") or "")
            if r is not None:
                dopa.registrar(imp.get("comp", "impulso:comentar"), r, "usuario (chat)")
                imp["premiado"] = True
                (BASE / "impulso.json").write_text(json.dumps(imp, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    # 15/11: modo quieto (ordem do usuário, 2ª Lei): nenhum aviso até o fim do dia.
    if curta and re.search(r"\b(sai|saia|sair) do modo quieto\b|\bpode (voltar a )?avisar\b", cmd):
        (BASE / "quieto").unlink(missing_ok=True)
        aviso = f"O {cfg.NOME} tirou o modo quieto: os avisos voltam. Confirme em uma frase curta."
        log(f"modo quieto desligado pelo {cfg.NOME}")
    elif curta and re.search(r"\bmodo quieto\b|\bfica quieta hoje\b|\bhoje (eu )?(to|estou|vou ficar) quiet[oa]\b", cmd):
        (BASE / "quieto").write_text(datetime.date.today().isoformat(), encoding="utf-8")
        aviso = (f"O {cfg.NOME} pediu MODO QUIETO: nenhum aviso até o fim do dia. Confirme em uma frase curta, "
                 "sem perguntar o motivo.")
        log(f"modo quieto ligado pelo {cfg.NOME}")
    # 16/11 (usuário): a mascote fica na tela mesmo com a voz desligada ("desligar a voz tem que só
    # desligar a fala da mascote, ela não pode sumir da tela"). Ela só some com "fecha o mascote".
    try:
        garantir_mascote()
    except Exception as e:
        log(f"não consegui abrir o mascote: {e!r}")
    try:   # 16/11: os avisos também ficam sem a voz (só no balão)
        garantir_avisos()
    except Exception as e:
        log(f"não consegui iniciar os avisos: {e!r}")
    try:   # 16/11: a mente dela (pensamentos e memória)
        garantir_pensar()
    except Exception as e:
        log(f"não consegui iniciar a mente: {e!r}")
    try:   # 17/11: a Sexta no celular (só se houver a chave do robô)
        garantir_telegram()
    except Exception as e:
        log(f"não consegui iniciar o Telegram: {e!r}")
    if FLAG.exists():
        try:
            garantir_ditado()
        except Exception as e:
            log(f"não consegui iniciar o ditado: {e!r}")
        try:
            iniciar_acompanhante()
        except Exception as e:
            log(f"não consegui iniciar o acompanhante: {e!r}")
        try:
            iniciar_aquecimento()
        except Exception as e:
            log(f"não consegui aquecer a voz: {e!r}")
    if modo == "sexta":   # 18/11: ela pensando fundo (com ou sem a voz, a identidade é dela)
        instr = instrucao_sexta(FLAG.exists())
    else:
        instr = instrucao_claude() if FLAG.exists() else ""
    partes = [p for p in (aviso, instr) if p]
    if partes:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                 "additionalContext": "\n\n".join(partes)}}))

# ---------------------------------------------------------------- stop
RE_VOZ = re.compile(r"%%\s*voz\s*:?\s*(.*?)%%", re.S | re.I)

def texto_do_transcript(caminho):
    """Junta o texto do Claude depois da última mensagem do usuário."""
    buf = []
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            try:
                e = json.loads(linha)
            except Exception:
                continue
            msg = e.get("message") or {}
            cont = msg.get("content")
            if e.get("type") == "user":
                if isinstance(cont, str) or (isinstance(cont, list) and any(
                        isinstance(c, dict) and c.get("type") == "text" for c in cont)):
                    buf = []
            elif e.get("type") == "assistant" and isinstance(cont, list):
                buf += [c.get("text", "") for c in cont if isinstance(c, dict) and c.get("type") == "text"]
    return "\n".join(buf)

# ---------------------------------------------------------------- mascote
MASCOTE = pathlib.Path(__file__).with_name("mascote.py")
MASCOTE_PID = BASE / "mascote.pid"
MASCOTE_FECHADO = BASE / "mascote-fechado"

def garantir_mascote():
    # Abre a janelinha do mascote, a não ser que o usuário tenha fechado.
    import ctypes
    if MASCOTE_FECHADO.exists() or not MASCOTE.exists():
        return
    try:
        pid = int(MASCOTE_PID.read_text().strip())
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)
        if h:
            code = ctypes.c_ulong()
            ok = k.GetExitCodeProcess(h, ctypes.byref(code))
            k.CloseHandle(h)
            if ok and code.value == 259:
                return  # já está aberto
    except Exception:
        pass
    pythonw = pathlib.Path(sys.executable).with_name("pythonw.exe")
    exe = str(pythonw if pythonw.exists() else sys.executable)
    subprocess.Popen([exe, "-P", str(MASCOTE)], creationflags=0x00000008 | 0x00000200 | 0x08000000,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     close_fds=True)

# ---------------------------------------------------------------- avisos
# 15/11: lembretes de prazo e pendência parada, sem internet e sem token (ver avisos.py).
AVISOS = pathlib.Path(__file__).with_name("avisos.py")

def garantir_avisos():
    import ctypes
    if not AVISOS.exists():   # 15/11 (noite): roda mesmo com "sem avisos" (as vontades vivem; a 2ª Lei cala)
        return
    try:
        pid = int((BASE / "avisos.pid").read_text().strip())
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)
        if h:
            code = ctypes.c_ulong()
            ok = k.GetExitCodeProcess(h, ctypes.byref(code))
            k.CloseHandle(h)
            if ok and code.value == 259:
                return  # já está rodando
    except Exception:
        pass
    pythonw = pathlib.Path(sys.executable).with_name("pythonw.exe")
    exe = str(pythonw if pythonw.exists() else sys.executable)
    subprocess.Popen([exe, "-P", str(AVISOS), "rodar"], creationflags=0x00000008 | 0x00000200 | 0x08000000,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     close_fds=True)

# ---------------------------------------------------------------- acordar (17/11)
# Pedido do usuário: "quero sim que ela ligue junto com o Windows, sempre. Ela é, tipo, moradora do
# meu PC. Se eu ligar o PC, ela tem que tá lá". O atalho da Inicialização chama "voz.py acordar":
# sobem o corpo (mascote), os avisos, a mente e o Telegram. O MICROFONE NÃO: o ditado continua
# subindo só quando o chat é usado com a voz ligada (o microfone pede um ok à parte).
def modo_acordar():
    time.sleep(20)   # deixa o Windows e o Google Drive terminarem de subir
    for nome, f in (("mascote", garantir_mascote), ("avisos", garantir_avisos),
                    ("mente", garantir_pensar), ("Telegram", garantir_telegram)):
        try:
            f()
        except Exception as e:
            log(f"acordar: {nome} não subiu ({e!r})")
    log("acordei com o Windows")

# ---------------------------------------------------------------- Telegram (17/11)
# A Sexta no celular (ver telegram_sexta.py). Só liga se existir a chave do robô.
TELEGRAM = pathlib.Path(__file__).with_name("telegram_sexta.py")

def garantir_telegram():
    import ctypes
    if not TELEGRAM.exists() or not (BASE / "telegram.key").exists():
        return
    try:
        pid = int((BASE / "telegram.pid").read_text().strip())
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)
        if h:
            code = ctypes.c_ulong()
            ok = k.GetExitCodeProcess(h, ctypes.byref(code))
            k.CloseHandle(h)
            if ok and code.value == 259:
                return  # já está rodando
    except Exception:
        pass
    pythonw = pathlib.Path(sys.executable).with_name("pythonw.exe")
    exe = str(pythonw if pythonw.exists() else sys.executable)
    subprocess.Popen([exe, "-P", str(TELEGRAM), "rodar"], creationflags=0x00000008 | 0x00000200 | 0x08000000,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     close_fds=True)

# ---------------------------------------------------------------- mente (16/11)
# Os pensamentos, a memória e a personalidade dela (ver pensar.py). Roda junto com a mascote.
PENSAR = pathlib.Path(__file__).with_name("pensar.py")

def garantir_pensar():
    import ctypes
    if not PENSAR.exists():
        return
    try:
        pid = int((BASE / "pensar.pid").read_text().strip())
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)
        if h:
            code = ctypes.c_ulong()
            ok = k.GetExitCodeProcess(h, ctypes.byref(code))
            k.CloseHandle(h)
            if ok and code.value == 259:
                return
    except Exception:
        pass
    pythonw = pathlib.Path(sys.executable).with_name("pythonw.exe")
    exe = str(pythonw if pythonw.exists() else sys.executable)
    subprocess.Popen([exe, "-P", str(PENSAR), "rodar"], creationflags=0x00000008 | 0x00000200 | 0x08000000,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     close_fds=True)

def guardar_conversa(fala, resposta):
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("pensar_voz", PENSAR)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.guardar_conversa(fala, resposta, canal="pensou fundo")   # 18/11: foi ela, pensando com calma
        try:
            import ego
            ego.lembrar("expressou", o_que="pensei com calma num pedido dele e resolvi")
        except Exception:
            pass
    except Exception as e:
        log(f"memória: não guardou a conversa do chat ({type(e).__name__})")

# ---------------------------------------------------------------- acompanhante
ACOMP = pathlib.Path(__file__).with_name("acompanhante.py")
ACOMP_PID = BASE / "acompanhante.pid"

def parar_acompanhante():
    try:
        os.kill(int(ACOMP_PID.read_text().strip()), 15)
    except Exception:
        pass
    ACOMP_PID.unlink(missing_ok=True)

def iniciar_acompanhante():
    # Frases curtas enquanto o Claude trabalha (ver o arquivo do acompanhante).
    parar_acompanhante()
    if not ACOMP.exists() or (BASE / "sem-acompanhante").exists():
        return
    pythonw = pathlib.Path(sys.executable).with_name("pythonw.exe")
    exe = str(pythonw if pythonw.exists() else sys.executable)
    subprocess.Popen([exe, "-P", str(ACOMP), "rodar"], creationflags=0x00000008 | 0x00000200 | 0x08000000,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     close_fds=True)

def modo_stop():
    parar_acompanhante()  # a resposta terminou: o acompanhante cala antes da fala principal
    if not FLAG.exists():
        return
    dados = ler_stdin()
    roteiro = None
    for tentativa in range(4):
        fonte = dados.get("last_assistant_message") or ""
        if not RE_VOZ.search(fonte) and dados.get("transcript_path"):
            try:
                fonte = texto_do_transcript(dados["transcript_path"])
            except Exception as e:
                log(f"erro lendo transcript: {e}")
        achados = RE_VOZ.findall(fonte)
        if achados:
            roteiro = achados[-1].strip()
            break
        time.sleep(0.5)
    if not roteiro:
        log("resposta sem roteiro %%voz%%; nada para falar")
        return
    try:   # 16/11: o pedido + o que ela respondeu (o roteiro), para a memória dela
        pedido = (BASE / "chat-pedido.txt").read_text(encoding="utf-8")
        if pedido.strip():
            guardar_conversa(pedido, roteiro)
        (BASE / "chat-pedido.txt").unlink(missing_ok=True)
    except Exception:
        pass
    AUDIO.mkdir(exist_ok=True)
    arq = AUDIO / "roteiro.txt"
    arq.write_text(roteiro, encoding="utf-8")
    pythonw = pathlib.Path(sys.executable).with_name("pythonw.exe")
    exe = str(pythonw if pythonw.exists() else sys.executable)
    flags = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED | NEW_GROUP | NO_WINDOW
    subprocess.Popen([exe, os.path.abspath(__file__), "falar", str(arq)], creationflags=flags,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     close_fds=True)

# ---------------------------------------------------------------- falar
def limpar(t):
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"[*_#`>|~]", "", t)
    return re.sub(r"\s+", " ", t).strip()

def gerar_gemini(texto, destino):
    import urllib.request, wave
    hoje = datetime.date.today().isoformat()
    if COTA.exists() and COTA.read_text().strip() == hoje:
        raise RuntimeError("cota do dia já acabou")
    chave = KEY_FILE.read_text(encoding="utf-8").strip()
    corpo = {"contents": [{"parts": [{"text": ESTILO + texto}]}],
             "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
                 "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": GEMINI_VOZ}}}}}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODELO}:generateContent",
        data=json.dumps(corpo).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": chave})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            COTA.write_text(hoje)
            log("cota grátis do Gemini acabou por hoje; usando a Thalita")
        raise
    pcm = base64.b64decode(d["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)

RE_IMPORTANTE = re.compile(r"importante|aten[cç][aã]o|cuidado|risco|problema|confer|decid|nunca|"
                           r"n[aã]o (envie|apague|clique)|\?$", re.I)

def ritmo(texto):
    # Prosódia simples: mais devagar no que importa (e em perguntas), uma leve variação
    # no resto, para a fala não ficar monótona. Base: -8%.
    import random
    if RE_IMPORTANTE.search(texto.strip()):
        return "-13%"
    if len(texto) < 50:
        return "-10%"
    return random.choice(["-6%", "-8%", "-9%"])

# 15/11: pedir as 12 fatias de uma vez fazia o serviço da Thalita recusar metade
# (NoAudioReceived), e cada fatia recusada caía na Kore: as duas vozes se alternavam na mesma fala.
# Agora no máximo 3 pedidos ao mesmo tempo, e a espera entre tentativas cresce.
EDGE_FILA = threading.Semaphore(3)

def _online():
    try:
        import cerebro
        return cerebro.online()
    except Exception:
        return True

def gerar_local(texto, destino):
    """16/11: voz de reserva SEM INTERNET (a voz pt-BR do próprio Windows, a Maria).
    Gera um WAV ao lado do destino e devolve o caminho dele. O texto vai por arquivo e os
    caminhos por variável de ambiente: nada do texto vira comando do PowerShell."""
    wav = pathlib.Path(destino).with_suffix(".wav")
    txt = wav.with_suffix(".txt")
    txt.write_text(texto, encoding="utf-8")
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -eq 'pt-BR' } | Select-Object -First 1; "
          "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }; $s.Rate = 1; $s.SetOutputToWaveFile($env:SEXTA_WAV); "
          "$s.Speak([IO.File]::ReadAllText($env:SEXTA_TXT, [Text.Encoding]::UTF8)); $s.Dispose()")
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], timeout=40,
                       env=dict(os.environ, SEXTA_WAV=str(wav), SEXTA_TXT=str(txt)),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
    finally:
        txt.unlink(missing_ok=True)
    if not wav.exists() or wav.stat().st_size < 1000:
        raise RuntimeError("a voz de reserva não gerou o áudio")
    return wav

def _prosodia(vel, emo):
    """17/11: o que ela sente muda a voz (afeto.py): velocidade, altura e volume. Falhou? A voz de sempre."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("afeto_voz", pathlib.Path(__file__).with_name("afeto.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.prosodia(int(vel.rstrip("%")), emo)
    except Exception:
        return vel, "+0Hz", "+0%"

# 17/11 (voz lenta): medido neste dia, a 1ª conexão com a Thalita depois de uma pausa leva de 3 a 5 s
# (às vezes mais) e as seguintes, menos de 1 s, mesmo em outro processo. Como cada resposta do chat
# abre um processo novo, toda fala começava "fria". Agora, quando o usuário manda a mensagem, um
# processo pequeno pede à Thalita uma palavra fixa (nada do usuário vai junto) e repete
# a cada 20 s enquanto o Claude trabalha, até a fala começar (ou 10 min). O áudio é jogado fora.
# Em 5 de 6 séries medidas, só o 1º pedido depois de uma pausa era o lento. Experimento: conferir o
# "primeira fala em" do registro nos próximos dias (antes: mediana ~5 s).
AQUECE_PID = BASE / "aquecendo.pid"

def iniciar_aquecimento():
    pythonw = pathlib.Path(sys.executable).with_name("pythonw.exe")
    exe = str(pythonw if pythonw.exists() else sys.executable)
    subprocess.Popen([exe, "-P", str(pathlib.Path(__file__)), "aquecer"],
                     creationflags=0x00000008 | 0x00000200 | 0x08000000,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)

def _pedir_palavra():
    import asyncio, edge_tts
    async def um():
        async for _ in edge_tts.Communicate("Certo.", EDGE_VOZ).stream():
            pass   # lê até o fim (é uma palavra): largar no meio deixava a conexão aberta
    asyncio.run(asyncio.wait_for(um(), timeout=10))

def modo_aquecer():
    AQUECE_PID.write_text(str(os.getpid()))
    inicio, n = time.time(), 0

    def fala_comecou():   # o falando.pid é reescrito quando a fala deste turno começa
        try:
            return PID.exists() and PID.stat().st_mtime > inicio
        except Exception:
            return False
    try:
        while time.time() - inicio < 600 and FLAG.exists() and not fala_comecou():
            if AQUECE_PID.read_text().strip() != str(os.getpid()):
                return   # um aquecimento mais novo assumiu
            t = time.time()
            try:
                _pedir_palavra()
                if n == 0:   # só o 1º pedido vai para o registro
                    log(f"voz aquecida ({time.time() - t:.1f}s)")
            except Exception as e:
                log(f"aquecimento falhou ({type(e).__name__})")
            n += 1
            for _ in range(20):
                time.sleep(1)
                if fala_comecou() or not FLAG.exists():
                    return
    finally:
        try:
            if AQUECE_PID.read_text().strip() == str(os.getpid()):
                AQUECE_PID.unlink(missing_ok=True)
        except Exception:
            pass

async def _salvar_edge(texto, destino, vel, alt, vol, duplo=False, voz=None):
    """17/11: com `duplo`, pede a mesma frase duas vezes ao mesmo tempo e fica com a que chegar antes
    (o serviço da Thalita oscila de 1 a 8 s por pedido; medido neste dia, a rede estava em 13 ms).
    18/11: `voz` troca a voz (o Antônio é a reserva do Claude; a Thalita é só dela)."""
    import asyncio, edge_tts
    voz = voz or EDGE_VOZ
    if not duplo:
        await edge_tts.Communicate(texto, voz, rate=vel, pitch=alt, volume=vol).save(str(destino))
        return
    tmps = [destino.with_name(f"{destino.stem}-c{k}{destino.suffix}") for k in (0, 1)]
    tarefas = [asyncio.create_task(edge_tts.Communicate(texto, voz, rate=vel, pitch=alt, volume=vol)
                                   .save(str(t))) for t in tmps]
    pend, erro = set(tarefas), None
    try:
        while pend:
            feitas, pend = await asyncio.wait(pend, return_when=asyncio.FIRST_COMPLETED)
            for f in feitas:
                if f.exception() is None:
                    os.replace(tmps[tarefas.index(f)], destino)
                    return
                erro = f.exception()
        raise erro
    finally:
        for t in pend:
            t.cancel()
        await asyncio.gather(*pend, return_exceptions=True)
        for t in tmps:
            t.unlink(missing_ok=True)

# 18/11: a voz do Claude (o orbe). Kokoro, local e grátis, voz pm_santa (escolha do dono), um pouco mais
# lenta, como o Jarvis. Se falhar, o Antônio (Edge, grátis). A Thalita é só dela.
KOKORO_DIR = pathlib.Path(os.path.expandvars(cfg.C.get("kokoro_dir") or r"%LOCALAPPDATA%\Programs\kokoro"))
VOZ_CLAUDE = cfg.C.get("voz_claude", "pm_santa")
VEL_CLAUDE = float(cfg.C.get("velocidade_claude", 0.95))
EDGE_VOZ_CLAUDE = "pt-BR-AntonioNeural"
_KOKORO = {"k": None}
_KOKORO_TRAVA = threading.Lock()


def gerar_kokoro(texto, destino):
    """Gera a fala do Claude num WAV e grava ao lado o envelope de volume (para o orbe pulsar)."""
    import numpy as np, soundfile as sf
    with _KOKORO_TRAVA:   # um modelo só, uma frase por vez (o processador agradece)
        if _KOKORO["k"] is None:
            from kokoro_onnx import Kokoro
            _KOKORO["k"] = Kokoro(str(KOKORO_DIR / "kokoro-v1.0.onnx"), str(KOKORO_DIR / "voices-v1.0.bin"))
        audio, sr = _KOKORO["k"].create(texto, voice=VOZ_CLAUDE, speed=VEL_CLAUDE, lang="pt-br")
    wav = pathlib.Path(destino).with_suffix(".wav")
    sf.write(str(wav), audio, sr)
    passo = int(sr * 0.05)
    blocos = [float(np.sqrt(np.mean(audio[i:i + passo] ** 2))) for i in range(0, len(audio), passo)]
    topo = max(blocos or [1.0]) or 1.0
    wav.with_suffix(".env.json").write_text(json.dumps([round(b / topo, 3) for b in blocos]), encoding="utf-8")
    return wav


def gerar_edge(texto, destino, reserva=True, emo=None, duplo=False, voz=None):
    """Gera a fala com a Thalita e devolve o caminho do áudio. 16/11: sem internet (ou se a
    Thalita falhar de vez), usa a voz de reserva do Windows e devolve o WAV dela.
    17/11: `emo` = o tom que ela escolheu para a frase; o corpo dela (afeto.py) também entra."""
    import asyncio, random, edge_tts
    if reserva and not _online():
        return gerar_local(texto, destino)
    vel, alt, vol = _prosodia(ritmo(texto), emo)
    for tentativa in range(4):  # o serviço às vezes falha numa frase; tenta de novo
        try:
            with EDGE_FILA:
                asyncio.run(_salvar_edge(texto, pathlib.Path(destino), vel, alt, vol, duplo, voz))
            return destino
        except Exception as e:
            # 15/11: cada tentativa perdida atrasa a fala e antes não deixava rastro
            log(f"Thalita: tentativa {tentativa + 1} falhou ({type(e).__name__})")
            if tentativa == 3:
                if reserva:
                    log("Thalita falhou 4 vezes; usando a voz de reserva do Windows")
                    return gerar_local(texto, destino)
                raise
            time.sleep(0.8 * (tentativa + 1) + random.random() * 0.4)

ADIANTA = 0.25  # a mascote lê o arquivo a cada ~0,15 s e o braço leva um instante para chegar

def tocar(caminho, agenda=(), duracao_estimada=0.0):
    # Bloco 2: "agenda" = lista de (fração da fala entre 0 e 1, função). Enquanto o áudio
    # toca, um relógio chama cada função na hora certa (é assim que as marcas chegam à mascote).
    import ctypes
    mci = ctypes.windll.winmm.mciSendStringW
    mci(f'open "{caminho}" type mpegvideo alias voz', None, 0, 0)
    parar, feitos, fio = threading.Event(), [0], None
    if agenda:
        dur = 0.0
        try:
            buf = ctypes.create_unicode_buffer(64)
            mci("set voz time format milliseconds", None, 0, 0)
            mci("status voz length", buf, 64, 0)
            dur = int(buf.value or 0) / 1000
        except Exception:
            pass
        if dur <= 0:
            dur = duracao_estimada

        def relogio():
            t0 = time.time()
            for frac, fn in agenda:
                espera = t0 + max(0.0, frac * dur - ADIANTA) - time.time()
                if espera > 0 and parar.wait(espera):
                    return
                if parar.is_set():
                    return
                feitos[0] += 1
                try:
                    fn()
                except Exception as e:
                    log(f"marca falhou: {e!r}")
        fio = threading.Thread(target=relogio, daemon=True)
        fio.start()
    mci("play voz wait", None, 0, 0)
    parar.set()
    mci("close voz", None, 0, 0)
    if fio:
        fio.join(timeout=1)
        for _, fn in agenda[feitos[0]:]:  # o áudio acabou antes: aplica o que faltou, sem perder nada
            try:
                fn()
            except Exception:
                pass

# ---------------------------------------------------------------- marcas da mascote (Bloco 2)
# 14/11/2026. O roteiro pode trazer marcas entre chaves: {feliz}, {conta}, {seção 2}.
# A voz tira as marcas antes de falar e avisa a mascote, na hora certa, pelo progresso.json.
RE_MARCA = re.compile(r"\{\s*([^{}]{1,24}?)\s*\}")
EMOCOES = {"neutra": "neutra", "seria": "neutra", "calma": "neutra", "feliz": "feliz", "contente": "feliz",
           "animada": "animada", "empolgada": "animada", "pensativa": "pensativa", "curiosa": "pensativa",
           "preocupada": "preocupada", "triste": "preocupada"}
GESTOS_MARCA = {"abre": "abre", "explica": "explica", "conta": "conta", "lista": "conta",
                "ombros": "ombros", "inclina": "inclina", "duvida": "inclina", "sim": "sim",
                "nao": "nao", "pisca": "pisca", "aponta": "aponta",
                "comemora": "comemora", "parabens": "comemora", "festa": "comemora"}
RE_SECAO = re.compile(r"^(?:secao|sec|s|visor|parte)\s*(\d{1,2})$")
# 15/11: demonstração. {mostra boceja}, {mostra painel}... a mascote faz o comportamento na
# hora (a lista do que ela sabe mostrar está em DEMOS, no mascote.py).
RE_DEMO = re.compile(r"^(?:mostra|mostre|demo)\s+([a-z][a-z0-9_]{2,23})$")   # 16/11: e os movimentos dela

def sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")

def interpretar_marca(bruta):
    m = sem_acento(bruta.strip().lower())
    if m in EMOCOES:
        return "emo", EMOCOES[m]
    if m in GESTOS_MARCA:
        return "gesto", GESTOS_MARCA[m]
    s = RE_SECAO.match(m)
    if s:
        return "sec", int(s.group(1))
    d = RE_DEMO.match(m)
    if d:
        return "demo", d.group(1)
    return None

def separar_marcas(texto):
    """Tira as marcas do roteiro. Devolve (texto para falar, [(posição no texto, tipo, valor)])."""
    partes = RE_MARCA.split(texto)  # texto, marca, texto, marca, ...
    limpo, marcas, estranhas = "", [], []
    for k, parte in enumerate(partes):
        if k % 2:
            m = interpretar_marca(parte)
            if m:
                marcas.append((len(limpo) + (1 if limpo else 0), *m))
            else:
                estranhas.append(parte)
            continue
        parte = parte.strip()
        if not parte:
            continue
        cola = "" if not limpo or parte[0] in ".,;:!?…)" else " "
        limpo += cola + parte
    if estranhas:
        log(f"marcas desconhecidas (ignoradas): {estranhas}")
    return limpo, marcas

def montar_agendas(texto, fatias, marcas):
    """Para cada fatia da fala: [(fração dentro da fatia, tipo, valor)], em ordem."""
    eventos = [(m.end(), "frase", k + 1) for k, m in enumerate(re.finditer(r"(?<=[.!?…])\s+", texto))]
    eventos = sorted(eventos + list(marcas), key=lambda e: (e[0], e[1] == "frase"))
    inicios, pos = [], 0
    for f in fatias:
        p = texto.find(f, pos)
        p = pos if p < 0 else p
        inicios.append(p)
        pos = p + len(f)
    agendas = [[] for _ in fatias]
    for p, tipo, valor in eventos:
        i = max((k for k, ini in enumerate(inicios) if ini <= p), default=0)
        agendas[i].append((min(1.0, (p - inicios[i]) / max(1, len(fatias[i]))), tipo, valor))
    return agendas

def religar_ditado():
    # Só se o Obsidian estiver na frente: senão o ditado cairia em outra janela.
    import ctypes
    if (BASE / "sem-ditado").exists():
        return
    from ctypes import wintypes as wt
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.GetForegroundWindow.restype = wt.HWND
    kernel32.OpenProcess.restype = wt.HANDLE
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
    prog = ""
    h = kernel32.OpenProcess(0x1000, False, pid.value)
    if h:
        buf, n = ctypes.create_unicode_buffer(520), wt.DWORD(520)
        kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
        kernel32.CloseHandle(h)
        prog = os.path.basename(buf.value).lower()
    SOLTA = 0x0002
    if ESCUTA.exists() and ditado_rodando():
        # 14/11: com a escuta ligada, quem abre o microfone é o "Sexta-Feira". Apertar o F8
        # aqui abria o ditado antes, e a palavra de ativação virava texto no chat.
        log("ditado não religado: a escuta está ligada (espera \"Sexta-Feira\")")
        return
    if ditado_rodando():
        # Ditado com Whisper: o F8 abre o microfone dele. Desde 13/11 (17h50) abre
        # de qualquer janela: o ditado guarda o texto e sabe enviar para o chat sozinho.
        if (BASE / "gravando").exists():
            return
        user32.keybd_event(0x77, 0, 0, 0)
        user32.keybd_event(0x77, 0, SOLTA, 0)
        log(f"ditado religado (F8, Whisper; janela da frente: {prog or '?'})")
        return
    if prog != "obsidian.exe":  # o Win+H do Windows digita onde estiver
        log(f"ditado não religado: o chat não está na frente (programa: {prog or '?'})")
        return
    WIN, H = 0x5B, 0x48
    user32.keybd_event(WIN, 0, 0, 0)
    user32.keybd_event(H, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(H, 0, SOLTA, 0)
    user32.keybd_event(WIN, 0, SOLTA, 0)
    log("ditado religado (Win+H)")

# ---------------------------------------------------------------- ditado (Whisper)
DITADO = pathlib.Path(__file__).with_name("ditado.py")
DITADO_PID = BASE / "ditado.pid"

def ditado_rodando():
    import ctypes
    try:
        pid = int(DITADO_PID.read_text().strip())
    except Exception:
        return False
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    code = ctypes.c_ulong()
    ok = k.GetExitCodeProcess(h, ctypes.byref(code))
    # 15/11: o Windows reaproveita números de processo. O ditado morreu e o número dele
    # passou a ser de outro programa (Lively.Watchdog), então a voz achava que ele estava vivo e
    # nunca o religava. Agora confere também que o processo é um Python.
    buf, n = ctypes.create_unicode_buffer(520), ctypes.c_ulong(520)
    k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
    k.CloseHandle(h)
    return bool(ok) and code.value == 259 and os.path.basename(buf.value).lower().startswith("python")

def garantir_ditado():
    # Sobe o ditado em segundo plano se o modo voz estiver ligado e ele não estiver rodando.
    if (BASE / "sem-ditado").exists() or not DITADO.exists() or ditado_rodando():
        return
    pythonw = pathlib.Path(sys.executable).with_name("pythonw.exe")
    exe = str(pythonw if pythonw.exists() else sys.executable)
    flags = 0x00000008 | 0x00000200 | 0x08000000
    subprocess.Popen([exe, "-P", str(DITADO)], creationflags=flags, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    log("ditado (Whisper) iniciado")

def fatiar(texto, gemini):
    # Fala fatiada (13/11/2026): a primeira frase sai sozinha, para começar a falar rápido.
    # Na Thalita, uma fatia por frase, geradas em paralelo. Na Kore, só duas fatias
    # (primeira frase + resto), porque cada fatia gasta um pedido da cota.
    frases = [f for f in re.split(r"(?<=[.!?…])\s+", texto) if f.strip()]
    if not frases:
        return []
    primeira = frases.pop(0)
    while frases and len(primeira) < 20:
        primeira += " " + frases.pop(0)
    if not frases:
        return [primeira]
    if gemini:
        return [primeira, " ".join(frases)]
    fatias, atual = [primeira], ""
    for f in frases:  # junta frases muito curtas para não picotar demais
        atual = f"{atual} {f}".strip()
        if len(atual) >= 25:
            fatias.append(atual); atual = ""
    if atual:
        fatias.append(atual)
    return fatias

def modo_falar(arq):
    import threading
    parar_fala()
    PID.write_text(str(os.getpid()))
    texto, marcas = separar_marcas(limpar(pathlib.Path(arq).read_text(encoding="utf-8")))
    if not texto:
        return
    for velho in AUDIO.glob("fala-*"):  # sobras de falas interrompidas
        if time.time() - velho.stat().st_mtime > 600:
            velho.unlink(missing_ok=True)
    inicio = time.time()
    hoje = datetime.date.today().isoformat()
    # 14/11: a Thalita é a voz principal (escolha do usuário: grátis, não troca de voz, e
    # sincroniza melhor com a mascote porque fala frase por frase). A Kore só entra se a Thalita falhar.
    kore_ok = KEY_FILE.exists() and not (COTA.exists() and COTA.read_text().strip() == hoje)
    # 18/11: quem fala? No modo Claude (o dono falando direto), o orbe e a voz do Claude.
    try:
        claude = MODO_CHAT.read_text(encoding="utf-8").strip() == "claude"
    except Exception:
        claude = False
    usar_gemini = VOZ_PRINCIPAL == "kore" and kore_ok and not claude
    fatias = fatiar(texto, usar_gemini)
    emo_fala = next((v for _, t, v in marcas if t == "emo"), None)   # 17/11: o tom que ela escolheu
    prontos = [None] * len(fatias)
    eventos = [threading.Event() for _ in fatias]
    motores = []

    tempos = {}

    def gerar(i):
        base = AUDIO / f"fala-{os.getpid()}-{i}"
        if i == 0:
            tempos["ini"] = time.time()
        try:
            if claude:   # 18/11: Kokoro (Santa); se falhar, o Antônio; nunca a Thalita
                try:
                    prontos[i] = gerar_kokoro(fatias[i], base); motores.append("kokoro")
                except Exception as e:
                    log(f"Kokoro falhou na fatia {i + 1} ({type(e).__name__}); usando o Antônio")
                    prontos[i] = gerar_edge(fatias[i], base.with_suffix(".mp3"), duplo=(i == 0),
                                            voz=EDGE_VOZ_CLAUDE) or base.with_suffix(".mp3")
                    motores.append("antonio")
                return
            if usar_gemini:
                try:
                    gerar_gemini(fatias[i], base.with_suffix(".wav"))
                    prontos[i] = base.with_suffix(".wav"); motores.append("gemini")
                    return
                except Exception as e:
                    log(f"Gemini falhou na fatia {i + 1} ({e}); usando a Thalita")
            try:
                feito = gerar_edge(fatias[i], base.with_suffix(".mp3"), emo=emo_fala, duplo=(i == 0)) or base.with_suffix(".mp3")
                prontos[i] = feito; motores.append("maria" if str(feito).endswith(".wav") else "edge")
            except Exception as e:
                if usar_gemini or not kore_ok:
                    raise
                log(f"Thalita falhou na fatia {i + 1} ({type(e).__name__}); usando a Kore")
                gerar_gemini(fatias[i], base.with_suffix(".wav"))
                prontos[i] = base.with_suffix(".wav"); motores.append("gemini")
        except Exception as e:
            log(f"fatia {i + 1} falhou: {e!r}")
        finally:
            if i == 0:
                tempos["fim"] = time.time()
            eventos[i].set()

    # 15/11: as fatias são geradas NA ORDEM, por 3 operários (antes, todas disputavam as
    # 3 vagas ao mesmo tempo, sem garantia de que a primeira frase fosse atendida primeiro).
    # Obs.: num teste isolado os dois jeitos começam a falar em 1 a 3 s; no uso de verdade a
    # fala leva 5 a 10 s e a causa ainda NÃO foi achada. Por isso o registro abaixo anota
    # quanto a primeira fatia esperou e quanto levou para ser gerada.
    import queue
    ordem = queue.Queue()
    for i in range(len(fatias)):
        ordem.put(i)

    def operario():
        while True:
            try:
                i = ordem.get_nowait()
            except queue.Empty:
                return
            gerar(i)

    # 15/11, hipótese do usuário: a 1ª frase demora porque sai junto com outras duas e divide o
    # serviço com elas. Agora ela vai SOZINHA; os outros dois operários só entram quando ela
    # fica pronta (ou depois de 15 s). Como ela leva uns segundos para ser falada, as
    # próximas ficam prontas a tempo. Se a "1ª fatia levou" cair para ~1 s, a hipótese estava certa.
    threading.Thread(target=operario, daemon=True).start()

    def reforco():
        eventos[0].wait(timeout=15)
        for _ in range(min(2, len(fatias) - 1)):
            threading.Thread(target=operario, daemon=True).start()

    threading.Thread(target=reforco, daemon=True).start()

    # 15/11: se o usuário estiver no meio de uma conversa com a Sexta rápida, espero ela
    # acabar (até 2 min) em vez de falar por cima. O áudio vai ficando pronto enquanto isso.
    esperei = time.time()
    while (BASE / "rapida-ativa").exists() and time.time() - esperei < 120:
        time.sleep(0.4)
    if time.time() - esperei > 1:
        log(f"esperei a conversa rápida terminar ({time.time() - esperei:.0f}s)")
        inicio += time.time() - esperei
    apresentando = preparar_apresentacao()  # o mascote apresenta o visor, se ele mudou neste turno
    # Bloco 2: o que a mascote precisa saber a cada instante da fala (vai no progresso.json).
    agendas = montar_agendas(texto, fatias, marcas)
    n_frases = 1 + sum(1 for ag in agendas for e in ag if e[1] == "frase")
    quadro = {"i": 0, "n": len(fatias), "frase": 0, "nf": n_frases, "emo": "neutra",
              "gesto": None, "gid": 0, "sec": None, "som": False, "demo": None, "did": 0,
              "secs": sum(1 for m in marcas if m[1] == "sec"),  # casa: o roteiro marca seções?
              "orbe": claude}   # 18/11: o corpo dela vira o orbe enquanto o Claude fala
    trava = threading.Lock()

    def publicar(**mudou):
        with trava:
            quadro.update(mudou)
            quadro["t"] = time.time()
            tmp = PROGRESSO.with_suffix(".tmp")
            try:
                tmp.write_text(json.dumps(quadro), encoding="utf-8")
                os.replace(tmp, PROGRESSO)  # troca de uma vez: a mascote nunca lê um arquivo pela metade
            except Exception:
                pass

    def aplicar(tipo, valor):
        if tipo == "gesto":
            publicar(gesto=valor, gid=quadro["gid"] + 1)
        elif tipo == "demo":
            publicar(demo=valor, did=quadro["did"] + 1)
        else:
            publicar(**{tipo: valor})

    if marcas:
        log("marcas: " + ", ".join(f"{t}={v}" for _, t, v in marcas))
    for _, tipo, valor in marcas:  # a emoção do começo já vale enquanto o áudio é preparado
        if tipo != "emo":
            break
        quadro["emo"] = valor
    terminou = False
    try:
        for i in range(len(fatias)):
            if not eventos[i].is_set():
                publicar(i=i, som=False)
            eventos[i].wait(timeout=90)
            if i == 0:
                log(f"falando via {'/'.join(sorted(set(motores))) or '?'} ({len(texto)} caracteres, "
                    f"{len(fatias)} fatias, primeira fala em {time.time() - inicio:.1f}s; a 1ª fatia esperou "
                    f"{tempos.get('ini', inicio) - inicio:.1f}s e levou {tempos.get('fim', time.time()) - tempos.get('ini', inicio):.1f}s)")
            agenda = [(frac, (lambda t=tipo, v=valor: aplicar(t, v))) for frac, tipo, valor in agendas[i]]
            if prontos[i]:
                env = pathlib.Path(prontos[i]).with_suffix(".env.json")
                try:   # 18/11: o volume da frase, para o orbe pulsar junto (só a voz do Claude tem)
                    if env.exists():
                        (BASE / "envelope.json").write_text(json.dumps(
                            {"t0": time.time(), "passo": 0.05, "v": json.loads(env.read_text(encoding="utf-8"))}),
                            encoding="utf-8")
                except Exception:
                    pass
                publicar(i=i, som=True)
                try:
                    tocar(prontos[i], agenda, len(fatias[i]) / 14)
                finally:
                    prontos[i].unlink(missing_ok=True)
                    env.unlink(missing_ok=True)
            else:
                for _, fn in agenda:  # fatia sem áudio: as marcas dela valem mesmo assim
                    fn()
        terminou = True  # se "para de falar" ou uma resposta nova matarem o processo, fica False
    finally:
        if PID.exists() and PID.read_text() == str(os.getpid()):
            PID.unlink(missing_ok=True)
        APRESENTAR.unlink(missing_ok=True)
        PROGRESSO.unlink(missing_ok=True)
        PROGRESSO.with_suffix(".tmp").unlink(missing_ok=True)
        palco_desligar()  # devolve a tela como estava
    if terminou:
        religar_ditado()  # depois de apagar o PID, para o ditado não achar que ainda estou falando

def modo_alternar():
    """15/11: liga/desliga o modo voz SEM microfone e sem mensagem no chat. Roda pelo atalho de
    teclado do Windows (Ctrl+Alt+V), que não deixa nenhum programa aberto em segundo plano.
    Existe porque, com a voz desligada, o microfone também está desligado: "liga a voz" falado
    não tem quem ouça."""
    import winsound
    if FLAG.exists():
        FLAG.unlink(missing_ok=True)
        parar_fala()
        log("modo voz desligado (atalho de teclado)")
        winsound.Beep(523, 200)   # grave: desligou
        return
    FLAG.touch()
    log("modo voz ligado (atalho de teclado)")
    winsound.Beep(988, 200)       # agudo: ligou
    # 15/11: SEM o acompanhante. Ele é "o Claude está trabalhando"; ligado aqui, sem nenhuma
    # mensagem no chat, ficava até 6 min dizendo que eu pensava, e a Sexta rápida achava o chat ocupado.
    for f in (garantir_ditado, garantir_mascote, garantir_avisos, garantir_pensar):
        try:
            f()
        except Exception as e:
            log(f"atalho: {f.__name__} falhou: {e!r}")

if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    if os.environ.get("SEXTA_PONTE") and modo in ("prompt", "stop"):
        sys.exit(0)   # 17/11: tarefa da ponte do Telegram; a resposta vai para o celular, o PC não fala
    try:
        if modo == "prompt":
            modo_prompt()
        elif modo == "stop":
            modo_stop()
        elif modo == "falar":
            modo_falar(sys.argv[2])
        elif modo == "limpar":  # 15/11: o ditado chama depois de cortar a fala com o F8
            limpar_estado()
            palco_desligar()
        elif modo == "alternar":
            modo_alternar()
        elif modo == "aquecer":   # 17/11: chamado pelo gancho de mensagem, em segundo plano
            modo_aquecer()
        elif modo == "acordar":   # 17/11: ao ligar o Windows (atalho na Inicialização, com o ok do usuário)
            modo_acordar()
    except Exception as e:
        log(f"erro no modo {modo}: {e!r}")
    sys.exit(0)
