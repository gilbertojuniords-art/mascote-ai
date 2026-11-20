# Digital pelo celular (17/11/2026). Pedido do usuário: "o que for referente a essa pastinha de segurança
# pede autenticação", do mesmo jeito que o banco pede a digital no celular.
#
# Como funciona (o app fica em celular/ neste repositório):
#   - CADASTRO, uma vez: o app cria uma chave dentro do chip do celular, que só abre com a digital, e
#     manda a parte pública pelo Telegram ("SEXTA-CHAVE ..."). O PC mostra um código no balão da
#     mascote; só quem está na frente do PC vê. A chave só é aceita quando esse código volta pelo
#     Telegram. (Assim, quem roubar o Telegram não cadastra a digital dele.)
#   - A CADA PASSO PERIGOSO da ponte: o porteiro cria um desafio de uso único com o resumo do passo
#     ("SEXTA1 ..."), manda pelo Telegram e espera até 5 min. O app mostra o resumo, pede a digital,
#     assina e devolve "SEXTA-OK <id> <assinatura>". O PC confere a assinatura com a chave cadastrada,
#     o prazo e se o desafio já foi usado. Só então o passo roda.
#   - Quem confere é o próprio porteiro (não o Telegram): um arquivo de resposta falso não passa.
#
# Arquivos (todos em ~/.sexta-voz, fora do Drive e do Git): digital-chave.pem (chave pública),
# digital/<id>.pedido e digital/<id>.resposta (apagados ao terminar), digital-cadastro.json (pendente).
# O registro anota só o evento, nunca o resumo do passo.
#
# Comandos: py digital.py testar | estado

import base64, json, os, pathlib, re, secrets, sys, time
if str(pathlib.Path(__file__).resolve().parent) not in sys.path: sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

BASE = pathlib.Path.home() / ".sexta-voz"
CHAVE = BASE / "digital-chave.pem"
PASTA = BASE / "digital"
CADASTRO = BASE / "digital-cadastro.json"
LOG = BASE / "log.txt"
PRAZO_S = 5 * 60
RE_OK = re.compile(r"SEXTA-OK\s+([0-9a-f]{16})\s+([A-Za-z0-9+/=_-]{40,200})")
RE_CHAVE = re.compile(r"SEXTA-CHAVE\s+([A-Za-z0-9+/=_-]{80,300})")


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} digital: {msg}\n")
    except Exception:
        pass


def _b64(s):
    s = s.strip().replace("-", "+").replace("_", "/")
    return base64.b64decode(s + "=" * (-len(s) % 4))


def _carregar_publica(der):
    from cryptography.hazmat.primitives.serialization import load_der_public_key
    from cryptography.hazmat.primitives.asymmetric import ec
    pub = load_der_public_key(der)
    if not isinstance(pub, ec.EllipticCurvePublicKey) or pub.curve.name != "secp256r1":
        raise ValueError("chave não é P-256")
    return pub


def impressao(der):
    """Uma 'impressão' curta da chave, igual à que o app mostra, para conferir de olho."""
    import hashlib
    h = hashlib.sha256(der).hexdigest().upper()
    return f"{h[:4]}-{h[4:8]}"


def chave_publica():
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        return load_pem_public_key(CHAVE.read_bytes())
    except Exception:
        return None


def pronta():
    return chave_publica() is not None


# ---------------------------------------------------------------- cadastro

def receber_chave(texto, mostrar_codigo):
    """Mensagem 'SEXTA-CHAVE ...' chegou pelo Telegram. Devolve a resposta para o dono."""
    m = RE_CHAVE.search(texto or "")
    if not m:
        return None
    try:
        der = _b64(m.group(1))
        _carregar_publica(der)
    except Exception:
        log("cadastro: chave inválida")
        return "Essa chave não veio inteira. Copie de novo no app e me mande."
    codigo = f"{secrets.SystemRandom().randrange(10 ** 6):06d}"
    CADASTRO.write_text(json.dumps({"der": base64.b64encode(der).decode(), "codigo": codigo, "t": time.time()}),
                        encoding="utf-8")
    mostrar_codigo(f"Cadastro da digital: {codigo} (impressão {impressao(der)}, vale 10 min)")
    log("cadastro: chave recebida, código mostrado no balão")
    troca = " Isso troca a digital cadastrada antes." if pronta() else ""
    return (f"Recebi a chave do app (impressão {impressao(der)}). Para eu aceitar, mande aqui o código de 6 dígitos "
            f"que apareceu no balão da mascote, no PC.{troca}")


def cadastro_pendente():
    try:
        d = json.loads(CADASTRO.read_text(encoding="utf-8"))
        return d if time.time() - d["t"] <= 600 else None
    except Exception:
        return None


def confirmar_cadastro(texto):
    """Devolve a resposta se o texto era o código do cadastro (certo ou errado), senão None."""
    d = cadastro_pendente()
    t = (texto or "").strip()
    if not d or not re.fullmatch(r"\d{6}", t):
        return None
    if not secrets.compare_digest(t, d["codigo"]):
        log("cadastro: código errado")
        CADASTRO.unlink(missing_ok=True)   # uma tentativa só; errou, começa de novo
        return "Código errado. Por segurança, cancelei: mande a chave do app de novo."
    from cryptography.hazmat.primitives import serialization
    der = base64.b64decode(d["der"])
    pem = _carregar_publica(der).public_bytes(serialization.Encoding.PEM,
                                              serialization.PublicFormat.SubjectPublicKeyInfo)
    CHAVE.write_bytes(pem)
    CADASTRO.unlink(missing_ok=True)
    log("cadastro: digital cadastrada")
    return (f"Pronto. Digital cadastrada (impressão {impressao(der)}). A partir de agora, o que bater na lista "
            "de segurança da ponte vem pedir a sua digital, em vez de ser negado.")


# ---------------------------------------------------------------- pedido e conferência

def criar_pedido(resumo):
    PASTA.mkdir(parents=True, exist_ok=True)
    pid = secrets.token_hex(8)
    corpo = json.dumps({"v": 1, "id": pid, "n": secrets.token_hex(16), "r": resumo[:400],
                        "exp": int(time.time()) + PRAZO_S}, ensure_ascii=False, separators=(",", ":"))
    desafio = base64.urlsafe_b64encode(corpo.encode("utf-8")).decode().rstrip("=")
    (PASTA / f"{pid}.pedido").write_text(desafio, encoding="utf-8")
    return pid, "SEXTA1 " + desafio


def receber_assinatura(texto):
    """Mensagem 'SEXTA-OK ...' chegou pelo Telegram: só entrega ao porteiro, que confere. Devolve a resposta."""
    m = RE_OK.search(texto or "")
    if not m:
        return None
    pid = m.group(1)
    if not (PASTA / f"{pid}.pedido").exists():
        log("assinatura de um pedido que não existe (vencido ou já usado)")
        return "Esse pedido já venceu ou já foi usado. Se a tarefa ainda precisar, ela pede de novo."
    (PASTA / f"{pid}.resposta").write_text(m.group(2), encoding="utf-8")
    return None   # o porteiro responde se conferiu ou não


def conferir(desafio, assinatura_b64, pub=None):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    pub = pub or chave_publica()
    if pub is None:
        return False
    try:
        corpo = json.loads(_b64(desafio).decode("utf-8"))
        if int(corpo["exp"]) < time.time():
            return False
        pub.verify(_b64(assinatura_b64), desafio.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
        return True
    except Exception:
        return False


def esperar(pid, limite=PRAZO_S):
    """Espera a assinatura do pedido. Devolve 'ok', 'errada' ou 'venceu'. O pedido é de uso único."""
    pedido, resposta = PASTA / f"{pid}.pedido", PASTA / f"{pid}.resposta"
    fim = time.time() + limite
    try:
        desafio = pedido.read_text(encoding="utf-8").strip()
        while time.time() < fim:
            if resposta.exists():
                return "ok" if conferir(desafio, resposta.read_text(encoding="utf-8").strip()) else "errada"
            time.sleep(1)
        return "venceu"
    finally:
        pedido.unlink(missing_ok=True)
        resposta.unlink(missing_ok=True)


def limpar_vencidos():
    try:
        for p in PASTA.glob("*.*"):
            if time.time() - p.stat().st_mtime > PRAZO_S + 60:
                p.unlink(missing_ok=True)
    except Exception:
        pass


# ---------------------------------------------------------------- testes (chave falsa, sem celular)

def testar():
    global BASE, CHAVE, PASTA, CADASTRO
    import tempfile
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        BASE = pathlib.Path(tmp); CHAVE = BASE / "digital-chave.pem"; PASTA = BASE / "digital"
        CADASTRO = BASE / "digital-cadastro.json"
        priv = ec.generate_private_key(ec.SECP256R1())   # faz o papel do chip do celular
        der = priv.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        visto = []
        r = receber_chave("SEXTA-CHAVE " + base64.b64encode(der).decode(), visto.append)
        codigo = re.search(r"\d{6}", visto[0]).group(0) if visto else ""
        if not r or not codigo or pronta():
            print("FALHOU: cadastro começou errado"); ok = False
        errado = "000000" if codigo != "000000" else "111111"
        if "errado" not in (confirmar_cadastro(errado) or "") or cadastro_pendente():
            print("FALHOU: código errado devia cancelar"); ok = False
        receber_chave("SEXTA-CHAVE " + base64.b64encode(der).decode(), visto.append)
        codigo = re.search(r"\d{6}", visto[-1]).group(0)
        if "cadastrada" not in (confirmar_cadastro(codigo) or "") or not pronta():
            print("FALHOU: cadastro com o código certo"); ok = False

        def assinar(msg):
            desafio = msg.split(" ", 1)[1]
            return desafio, base64.b64encode(priv.sign(desafio.encode(), ec.ECDSA(hashes.SHA256()))).decode()

        pid, msg = criar_pedido("apagar — Bash: rm -rf build")
        desafio, ass = assinar(msg)
        receber_assinatura(f"SEXTA-OK {pid} {ass}")
        if esperar(pid, 3) != "ok":
            print("FALHOU: assinatura certa não passou"); ok = False
        if receber_assinatura(f"SEXTA-OK {pid} {ass}") is None:
            print("FALHOU: reusar a assinatura devia ser recusado"); ok = False
        pid2, msg2 = criar_pedido("outro passo")
        receber_assinatura(f"SEXTA-OK {pid2} {ass}")   # assinatura de outro desafio
        if esperar(pid2, 3) != "errada":
            print("FALHOU: assinatura de outro desafio passou"); ok = False
        outro = ec.generate_private_key(ec.SECP256R1())
        pid3, msg3 = criar_pedido("mais um")
        d3 = msg3.split(" ", 1)[1]
        falsa = base64.b64encode(outro.sign(d3.encode(), ec.ECDSA(hashes.SHA256()))).decode()
        receber_assinatura(f"SEXTA-OK {pid3} {falsa}")
        if esperar(pid3, 3) != "errada":
            print("FALHOU: chave de outro celular passou"); ok = False
        pid4, _ = criar_pedido("ninguém assina")
        if esperar(pid4, 1) != "venceu":
            print("FALHOU: prazo"); ok = False
        corpo = json.loads(_b64(desafio))
        if corpo["r"] != "apagar — Bash: rm -rf build" or corpo["exp"] - time.time() > PRAZO_S + 5:
            print("FALHOU: conteúdo do desafio"); ok = False
    print("digital:", "OK" if ok else "COM FALHAS")
    return ok


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    if modo == "testar":
        sys.exit(0 if testar() else 1)
    if modo == "estado":
        print("digital cadastrada" if pronta() else "sem digital cadastrada")
    sys.exit(0)
