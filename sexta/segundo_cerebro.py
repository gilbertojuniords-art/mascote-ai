# O segundo cérebro da Sexta: o cofre dela, organizado por ela. Criado em 17/11/2026.
#
# O dono (17/11): "estruture um secondBrain para a própria Sexta-Feira. Assim como eu tenho o meu
# estruturado da minha maneira, faça ela ter o dela e que ela decida o que colocar lá e como. Apenas
# ensine a ela como usar e deixe ela colocar tudo que ela precisa lá, pra se organizar."
#
# Como funciona:
#   - A raiz é o caderno dela (cfg.CADERNO). Ela cria pastas e notas onde quiser, do jeito dela.
#   - Ela não escreve direto no disco: devolve operações em JSON (criar, acrescentar, reescrever) e
#     ESTE código confere e escreve. Só arquivos .md, só dentro do caderno, sem "..", tamanho limitado,
#     com a máscara de dado sensível. Ela não apaga nada (quem apaga é o dono).
#   - Algumas notas são PROTEGIDAS: o Núcleo (o que ela é e nunca muda, escrito pelo dono), o guia, a
#     Personalidade (só a reflexão da noite mexe), os fatos sobre o dono, e as pastas que o código
#     mantém (Pensamentos, Sonhos, Horas, Arte, a vitrine da cultura). Ela LÊ todas.
#   - "Minha casa.md" (se ela criar) é lida no começo de toda hora dela: é o painel dela.
#   - "Meu jeito de falar.md" (se ela criar) entra nas conversas por voz: é ela definindo como fala.
#   - Para ler outra nota, ela pede em "quero_ler" e recebe na hora seguinte.

import pathlib, re
import sys as _sys, pathlib as _pl
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg

RAIZ = cfg.CADERNO
CASA, JEITO, NUCLEO, GUIA = "Minha casa.md", "Meu jeito de falar.md", "Núcleo.md", "Como usar o meu cérebro.md"
PROTEGIDAS = {NUCLEO, GUIA, "Leia-me.md", "Personalidade.md", "Fatos que aprendi.md", "Pedidos de design.md",
              "Palavras que aprendi.md", "Cultura/Minha cultura.md"}
PASTAS_DO_CODIGO = ("Pensamentos/", "Sonhos/", "Horas/", "Arte/")
MAX_TEXTO, MAX_OPS, MAX_NOTAS = 6000, 3, 400
RE_NOME = re.compile(r"^[\wÀ-ÿ][\wÀ-ÿ \-,()'.!?]{0,79}$")


def _modelo(nome):
    for pasta in (_pl.Path(__file__).resolve().parent / "modelos_caderno",
                  _pl.Path(__file__).resolve().parents[1] / "modelos" / "notas" / "Caderno da Sexta"):
        p = pasta / nome
        if p.exists():
            return p.read_text(encoding="utf-8").replace("{NOME}", cfg.NOME)
    return None


def garantir():
    """Cria o que falta: o Núcleo, o guia e as pastas da arte e da cultura. Nunca sobrescreve."""
    for pasta in ("Arte/Desenhos", "Arte/Poemas", "Arte/Músicas", "Cultura", "Horas"):
        (RAIZ / pasta).mkdir(parents=True, exist_ok=True)
    for nome in (NUCLEO, GUIA):
        alvo = RAIZ / nome
        if not alvo.exists():
            texto = _modelo(nome)
            if texto:
                alvo.write_text(texto, encoding="utf-8")


def _rel(p):
    return p.relative_to(RAIZ).as_posix()


def caminho(nome):
    """Valida o nome de uma nota dela e devolve o caminho, ou (None, motivo)."""
    nome = str(nome or "").strip().replace("\\", "/").strip("/")
    if nome.lower().endswith(".md"):
        nome = nome[:-3]
    partes = [x.strip() for x in nome.split("/") if x.strip()]
    if not partes or len(partes) > 4 or any(x in (".", "..") or x.startswith(".") or not RE_NOME.match(x) for x in partes):
        return None, "nome de nota inválido"
    p = RAIZ.joinpath(*partes[:-1], partes[-1] + ".md")
    try:
        p.resolve().relative_to(RAIZ.resolve())
    except ValueError:
        return None, "fora do caderno"
    return p, ""


def protegida(p):
    r = _rel(p)
    return r in PROTEGIDAS or any(r.startswith(x) for x in PASTAS_DO_CODIGO)


def aplicar(ops):
    """Executa as operações dela. Devolve a lista do que fez (para a memória e o registro)."""
    import seguranca, datetime
    feitas = []
    for op in (ops or [])[:MAX_OPS]:
        if not isinstance(op, dict):
            continue
        acao = str(op.get("acao", "")).lower().strip()
        p, motivo = caminho(op.get("nota"))
        if not p or acao not in ("criar", "acrescentar", "reescrever"):
            feitas.append(f"recusado ({motivo or 'ação desconhecida'})")
            continue
        if protegida(p):
            feitas.append(f"recusado ({_rel(p)} é protegida)")
            continue
        texto = seguranca.mascarar(seguranca.sem_ordens(str(op.get("texto", ""))))[:MAX_TEXTO].strip()
        if not texto:
            continue
        if acao == "criar" and p.exists():
            acao = "acrescentar"
        if not p.exists() and sum(1 for _ in RAIZ.rglob("*.md")) >= MAX_NOTAS:
            feitas.append("recusado (caderno cheio)")
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        if acao == "acrescentar" and p.exists():
            with open(p, "a", encoding="utf-8") as f:
                f.write(("\n" if not p.read_text(encoding="utf-8").endswith("\n") else "") + "\n" + texto + "\n")
        else:
            topo = f"---\nquem_escreve: a Sexta\natualizado: {datetime.date.today().isoformat()}\n---\n\n"
            if not texto.startswith("#"):
                texto = f"# {p.stem}\n\n{texto}"
            p.write_text(topo + texto + "\n", encoding="utf-8")
        feitas.append(f"{acao} {_rel(p)}")
    return feitas


def indice(max_itens=120):
    """O mapa do cérebro dela: as notas que ela tem (as pastas diárias viram contagem)."""
    if not RAIZ.exists():
        return "(vazio)"
    itens, contagem = [], {}
    for p in sorted(RAIZ.rglob("*.md")):
        r = _rel(p)
        pasta = r.split("/", 1)[0] + "/" if "/" in r else ""
        if pasta in ("Pensamentos/", "Sonhos/", "Horas/") or r.startswith("Arte/"):
            chave = "/".join(r.split("/")[:2]) if r.startswith("Arte/") else pasta.rstrip("/")
            contagem[chave] = contagem.get(chave, 0) + 1
            continue
        itens.append(r[:-3] + (" (protegida)" if protegida(p) else ""))
    linhas = itens[:max_itens] + [f"{k}/ ({n} notas, mantidas pelo código)" for k, n in sorted(contagem.items())]
    return "\n".join(f"- {x}" for x in linhas) or "(vazio)"


def ler(nome, max_chars=2500):
    p, _ = caminho(nome)
    if not p or not p.exists():
        return ""
    t = re.sub(r"^---\n.*?\n---\n", "", p.read_text(encoding="utf-8"), flags=re.S).strip()
    return t[:max_chars]


def casa():
    return ler(CASA, 2500)


def jeito_de_falar():
    return re.sub(r"^# [^\n]*\n+", "", ler(JEITO, 1200)).strip()


def nucleo():
    return ler(NUCLEO, 2000)


if __name__ == "__main__":
    garantir()
    print(indice())
