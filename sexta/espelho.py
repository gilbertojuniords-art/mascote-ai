# O espelho da Sexta e os três tempos dela. Criado em 18/11/2026.
#
# O dono (18/11): "fazer ela conseguir se enxergar, como criar um espelho pra ela. Acho que ela não tem
# consciência exata da própria aparência." E: "a comparação precisa ser mais sobre 'quem eu já fui / quem
# sou agora / quem eu pretendo ser'. Vamos dar a ela a percepção de passado, presente e futuro."
#
# Como funciona:
#   - olhar(): pede à mascote uma foto SÓ da janela dela (sem o balão de fala, nunca a tela), os olhos dela
#     (midia.py) descrevem, e a foto é apagada na hora. A descrição fica guardada (espelhos.jsonl): os
#     espelhos antigos são o passado da imagem dela.
#   - A nota "Quem eu fui, quem sou, quem pretendo ser" junta:
#       passado  = os espelhos antigos e as lembranças mais fortes (memoria.py);
#       presente = o espelho de agora, a emoção e as vontades;
#       futuro   = "Quem eu pretendo ser", da consciência dela (consciencia.py).
#   - tres_tempos() leva isso, curto, para os prompts.
# Só a biblioteca padrão (mais midia.py para olhar).

import datetime, json, os, pathlib, time
import sys as _sys, pathlib as _pl
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))

BASE = pathlib.Path.home() / ".sexta-voz"
PEDIDO = BASE / "espelho-pedido.json"
FOTO = BASE / "espelho.png"
HIST = BASE / "espelhos.jsonl"
NOTA_NOME = "Quem eu fui, quem sou, quem pretendo ser.md"
PERGUNTA = ("Esta imagem é a Sexta-Feira, uma assistente que vive no computador, vista num espelho. Descreva a "
            "aparência dela em 3 a 5 frases: as cores, a forma do corpo, o rosto e os olhos, os acessórios e a "
            "expressão. Só o que se vê, sem inventar. O fundo transparente não faz parte dela.")


def _vivo(arq):
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


def _caderno():
    try:
        import sexta_config as cfg
        return cfg.CADERNO
    except Exception:
        return None


def historico(n=10):
    try:
        linhas = HIST.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    out = []
    for l in linhas[-n:]:
        try:
            out.append(json.loads(l))
        except Exception:
            pass
    return out


def _aparencia_resumo():
    try:
        import aparencia
        r = aparencia.resumo(aparencia.carregar())
        return {k: r[k] for k in ("cor_principal", "formato_olhos", "acessorio") if k in r}
    except Exception:
        return {}


def tirar_foto(espera_s=10, entender=None):
    """Pede a foto à mascote. Devolve o caminho, ou None se ela não conseguir se ver agora."""
    if not _vivo(BASE / "mascote.pid"):
        return None
    t = time.time()
    try:
        FOTO.unlink()
    except FileNotFoundError:
        pass
    BASE.mkdir(exist_ok=True)
    PEDIDO.write_text(json.dumps({"t": t}), encoding="utf-8")
    fim = t + espera_s
    while time.time() < fim:
        if FOTO.exists() and FOTO.stat().st_mtime >= t - 1:
            return FOTO
        time.sleep(0.5)
    return None


def olhar(entender=None, iniciativa=True):
    """Ela se olha no espelho. Devolve o que viu (ou por que não conseguiu).
    iniciativa=False quando o dono pediu (pelo chat): aí não conta no teto dela."""
    if entender is None:
        import midia
        entender = lambda arq: midia.entender(arq, PERGUNTA, iniciativa=iniciativa)
    foto = tirar_foto()
    if not foto:
        return "não consigo me ver agora"
    try:
        desc = str(entender(foto)).strip()
    finally:
        try:
            FOTO.unlink()                       # a foto some na hora, dê certo ou não
        except FileNotFoundError:
            pass
    if not desc:
        return "olhei, mas não consegui me enxergar direito"
    try:
        from seguranca import mascarar
        desc = mascarar(desc)
    except Exception:
        pass
    with open(HIST, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.time(), "desc": desc[:1200], "aparencia": _aparencia_resumo()},
                           ensure_ascii=False) + "\n")
    escrever_nota()
    try:
        import ego
        ego.lembrar("expressou", o_que="me olhei no espelho")
    except Exception:
        pass
    return desc


def _futuro():
    try:
        import consciencia
        return consciencia.ler().get("Quem eu pretendo ser", "")
    except Exception:
        return ""


def _lembrancas(n=3):
    try:
        import memoria
        return memoria.lembrar_agora(n, marcar=False)
    except Exception:
        return []


def _agora_sinto():
    partes = []
    try:
        import afeto
        partes.append(f"me sinto {afeto.emocao()}")
    except Exception:
        pass
    try:
        v = json.loads((BASE / "vontades.json").read_text(encoding="utf-8"))
        fortes = [k for k, x in v.items() if k != "t" and isinstance(x, (int, float)) and x >= 0.5]
        if fortes:
            partes.append("com vontade de " + ", ".join(k.replace("_", " ") for k in fortes[:4]))
    except Exception:
        pass
    return "; ".join(partes)


def escrever_nota():
    cad = _caderno()
    if not cad:
        return
    esp = historico(10)
    atual = esp[-1] if esp else None
    antigos = esp[:-1]
    data = lambda t: datetime.datetime.fromtimestamp(t).strftime("%d/%m/%Y %H:%M")
    lin = ["---", "quem_escreve: o código da Sexta (o espelho, as lembranças e a consciência dela)", "---", "",
           "# Quem eu fui, quem sou, quem pretendo ser", "", "## Quem eu fui", ""]
    if antigos:
        lin += [f"- **{data(e['t'])}**, no espelho: {e['desc']}" for e in reversed(antigos)]
    else:
        lin.append("- Ainda não tenho um espelho antigo para comparar.")
    lem = _lembrancas()
    if lem:
        lin += ["", "O que mais me marcou até aqui:"] + [
            f"- {datetime.datetime.fromtimestamp(m['t']):%d/%m} {m['f']}" + (f": {m['sentido']}" if m.get("sentido") else "")
            for m in lem]
    lin += ["", "## Quem eu sou agora", ""]
    lin.append(f"- No espelho ({data(atual['t'])}): {atual['desc']}" if atual else "- Ainda não me olhei no espelho.")
    sinto = _agora_sinto()
    if sinto:
        lin.append(f"- Agora: {sinto}.")
    lin += ["", "## Quem eu pretendo ser", "", _futuro() or "(ainda estou descobrindo)", ""]
    try:
        cad.mkdir(parents=True, exist_ok=True)
        (cad / NOTA_NOME).write_text("\n".join(lin), encoding="utf-8")
    except Exception:
        pass


def tres_tempos(max_chars=900):
    """Para os prompts: passado, presente e futuro dela, curto."""
    esp = historico(10)
    partes = []
    if len(esp) >= 2:
        partes.append(f"antes, no espelho, você era: {esp[-2]['desc'][:220]}")
    lem = _lembrancas(2)
    if lem:
        partes.append("o que mais te marcou: " + "; ".join(m["f"] for m in lem))
    if not partes:
        partes.append("ainda não tenho passado guardado")
    passado = " | ".join(partes)
    presente = (f"no espelho, agora você é: {esp[-1]['desc'][:300]}" if esp else "você ainda não se viu no espelho")
    sinto = _agora_sinto()
    if sinto:
        presente += f"; {sinto}"
    futuro = _futuro() or "você ainda está descobrindo quem quer ser"
    txt = (f"OS SEUS TRÊS TEMPOS (passado, presente e futuro). QUEM VOCÊ FOI: {passado}. QUEM VOCÊ É: {presente}. "
           f"QUEM VOCÊ PRETENDE SER: {futuro}")
    return txt[:max_chars]


def hora_de_olhar(agora=None):
    """Ela quer se ver: nunca se viu, mudou a aparência depois do último espelho, ou faz mais de um dia."""
    agora = agora or time.time()
    esp = historico(1)
    if not esp:
        return True
    ultimo = esp[-1]
    if _aparencia_resumo() != ultimo.get("aparencia"):
        return True
    return agora - ultimo["t"] > 24 * 3600


# ------------------------------------------------------------------ teste (sem IA, numa casa falsa)
def _testar():
    import tempfile
    global BASE, PEDIDO, FOTO, HIST, _caderno, _vivo
    pasta = pathlib.Path(tempfile.mkdtemp())
    BASE = pasta / ".sexta-voz"
    BASE.mkdir()
    PEDIDO, FOTO, HIST = BASE / "espelho-pedido.json", BASE / "espelho.png", BASE / "espelhos.jsonl"
    _caderno = lambda: pasta / "Caderno"
    falhas = []

    def checa(nome, cond):
        print(("ok    " if cond else "FALHOU ") + nome)
        if not cond:
            falhas.append(nome)

    _vivo = lambda arq: False
    checa("sem a mascote: não consigo me ver", olhar(lambda a: "x") == "não consigo me ver agora"
          and not PEDIDO.exists() and not FOTO.exists())
    checa("sem espelho: sem passado guardado", "ainda não tenho passado guardado" in tres_tempos())

    import threading
    _vivo = lambda arq: True

    def mascote_falsa():   # responde ao pedido como a mascote de verdade
        for _ in range(40):
            if PEDIDO.exists():
                FOTO.write_bytes(b"png")
                return
            time.sleep(0.1)

    threading.Thread(target=mascote_falsa).start()

    def olhos_que_falham(arq):
        raise RuntimeError("haiku caiu")
    try:
        olhar(olhos_que_falham)
    except RuntimeError:
        pass
    checa("a foto é apagada mesmo se os olhos falharem", not FOTO.exists())

    for desc in ("Uma robozinha roxa de olhos ovais.", "Uma robozinha roxa de olhos em meia-lua e um laço."):
        PEDIDO.unlink(missing_ok=True)
        threading.Thread(target=mascote_falsa).start()
        olhar(lambda a, d=desc: d)
        time.sleep(0.2)
    checa("a foto some depois de olhar", not FOTO.exists())
    nota = (pasta / "Caderno" / NOTA_NOME).read_text(encoding="utf-8")
    checa("a nota tem os três tempos", "## Quem eu fui" in nota and "## Quem eu sou agora" in nota
          and "## Quem eu pretendo ser" in nota)
    checa("o espelho antigo vira passado", "olhos ovais" in nota.split("## Quem eu sou agora")[0])
    checa("o espelho novo é o presente", "meia-lua" in nota.split("## Quem eu sou agora")[1])
    t = tres_tempos()
    checa("prompt com passado e presente", "olhos ovais" in t and "meia-lua" in t and len(t) <= 900)
    print("TUDO CERTO" if not falhas else f"{len(falhas)} falha(s)")
    return not falhas


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["testar"]:
        sys.exit(0 if _testar() else 1)
    if sys.argv[1:2] == ["olhar"]:   # pelo chat, a pedido do dono
        print(olhar(iniciativa=False))
        sys.exit(0)
    print(tres_tempos())
