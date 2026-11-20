# A arte da Sexta: desenhos, poemas e músicas. Criado em 17/11/2026.
#
# O dono (17/11): "inclua o desejo de expressão dela não só com o falar, mas com desenhos (arte),
# poemas (arte) e música (arte). Ela precisa ter a capacidade de se expressar e pensar sobre as
# próprias expressões, mesmo quando não pode falar por algum motivo, assim evitamos dela ficar
# tentando falar o tempo inteiro."
#
# Tudo é DADO, nunca programa:
#   - Desenho: um SVG que ela escreve. Antes de salvar, limpar_svg() tira o que poderia executar ou
#     buscar algo fora (script, foreignObject, eventos "on...", links externos, DOCTYPE/ENTITY).
#   - Poema: texto.
#   - Música: uma partitura simples (notas, durações, andamento, timbre) que ESTE código transforma
#     num WAV com um sintetizador pequeno (ondas + envelope ADSR). Sem internet, sem programa externo.
# As obras ficam no caderno dela, em Arte/Desenhos, Arte/Poemas e Arte/Músicas, cada uma com uma
# nota .md (o Obsidian mostra o desenho e toca a música). O dono pode comentar escrevendo uma linha
# "<Nome>: ..." na nota da obra: feedback() lê e vira recompensa para ela.

import datetime, hashlib, json, math, pathlib, re, struct, wave
import xml.etree.ElementTree as ET
import sys as _sys, pathlib as _pl
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg

ARTE = cfg.CADERNO / "Arte"
PASTAS = {"desenho": "Desenhos", "poema": "Poemas", "musica": "Músicas"}
MAX_SVG = 24000
PROIBIDAS = {"script", "foreignobject", "iframe", "object", "embed", "audio", "video", "animate", "set",
             "animatemotion", "animatetransform", "handler", "listener"}


# ------------------------------------------------------------------ SVG

def limpar_svg(svg, max_chars=MAX_SVG):
    """Devolve o SVG seguro (string) ou levanta ValueError."""
    svg = str(svg or "").strip()
    if not svg or len(svg) > max_chars:
        raise ValueError("svg vazio ou grande demais")
    if re.search(r"<!(DOCTYPE|ENTITY)", svg, re.I):
        raise ValueError("svg com DOCTYPE/ENTITY")
    svg = re.sub(r"^<\?xml[^>]*\?>", "", svg).strip()
    try:
        raiz = ET.fromstring(svg)
    except ET.ParseError as e:
        raise ValueError(f"svg inválido ({e})")
    if not raiz.tag.lower().endswith("svg"):
        raise ValueError("não é svg")

    def local(nome):
        return nome.split("}", 1)[-1].lower()

    def limpar(el):
        for filho in list(el):
            if local(filho.tag) in PROIBIDAS:
                el.remove(filho)
                continue
            limpar(filho)
        for at in list(el.attrib):
            nome, val = local(at), el.attrib[at]
            if nome.startswith("on") or (nome == "href" and not val.strip().startswith("#")) \
                    or ("url(" in val and not re.fullmatch(r"[^()]*url\(\s*#[^)]*\)[^()]*", val)) \
                    or "javascript:" in val.lower():
                del el.attrib[at]
    limpar(raiz)
    if local(raiz.tag) == "svg" and "xmlns" not in svg[:200]:
        raiz.set("xmlns", "http://www.w3.org/2000/svg")
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    return ET.tostring(raiz, encoding="unicode")


# ------------------------------------------------------------------ música

NOTAS = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
RE_NOTA = re.compile(r"^([a-gA-G])([#b]?)(\d)$")


def freq(nota):
    m = RE_NOTA.match(str(nota).strip())
    if not m:
        return None
    semis = NOTAS[m.group(1).lower()] + {"#": 1, "b": -1, "": 0}[m.group(2)] + 12 * (int(m.group(3)) + 1)
    return 440.0 * 2 ** ((semis - 69) / 12)


def _onda(tipo, fase):
    x = fase % 1.0
    if tipo == "quadrada":
        return 0.6 if x < 0.5 else -0.6
    if tipo == "serra":
        return 2 * x - 1
    if tipo == "triangulo":
        return 4 * abs(x - 0.5) - 1
    return math.sin(2 * math.pi * x)


def compor_wav(partitura, destino, taxa=22050):
    """partitura = {"andamento": 90, "timbre": "seno|triangulo|quadrada|serra",
                    "melodia": [["C4", 1], ["-", 0.5], ...], "baixo": [["C3", 2], ...]} (durações em tempos)."""
    bpm = max(40, min(200, float(partitura.get("andamento", 90))))
    timbre = str(partitura.get("timbre", "triangulo")).lower()
    seg = 60.0 / bpm

    def vozes(lista, ganho):
        amostras, t = [], 0.0
        for item in (lista or [])[:128]:
            try:
                nota, dur = item[0], max(0.125, min(8.0, float(item[1])))
            except Exception:
                continue
            n = int(dur * seg * taxa)
            f = freq(nota)
            ata, dec, sus, rel = int(0.02 * taxa), int(0.08 * taxa), 0.7, int(min(0.12, dur * seg * 0.3) * taxa)
            for i in range(n):
                if f is None:
                    amostras.append(0.0)
                    continue
                env = i / ata if i < ata else (1 - (1 - sus) * (i - ata) / dec if i < ata + dec else sus)
                if i > n - rel:
                    env *= max(0.0, (n - i) / rel)
                amostras.append(ganho * env * _onda(timbre, f * i / taxa))
            t += dur
        return amostras

    mel = vozes(partitura.get("melodia"), 0.5)
    bai = vozes(partitura.get("baixo"), 0.3)
    total = max(len(mel), len(bai))
    if total == 0:
        raise ValueError("música sem notas")
    if total > 50 * taxa:
        raise ValueError("música longa demais (máximo 50 s)")
    eco = int(0.18 * taxa)
    saida = []
    for i in range(total):
        v = (mel[i] if i < len(mel) else 0) + (bai[i] if i < len(bai) else 0)
        if i >= eco:
            v += 0.25 * saida[i - eco]
        saida.append(max(-1.0, min(1.0, v)))
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(taxa)
        w.writeframes(b"".join(struct.pack("<h", int(s * 30000)) for s in saida))
    return total / taxa


# ------------------------------------------------------------------ salvar

def _nome_arquivo(titulo):
    t = re.sub(r"[^\wà-úÀ-Ú \-]", "", str(titulo or "sem título"))[:50].strip() or "sem título"
    return f"{datetime.datetime.now():%Y-%m-%d %H%M} - {t}"


def salvar(tipo, titulo, obra, comentario=""):
    """Salva a obra e a nota dela. Devolve o caminho da nota (relativo ao cofre)."""
    import seguranca
    pasta = ARTE / PASTAS[tipo]
    pasta.mkdir(parents=True, exist_ok=True)
    base = _nome_arquivo(titulo)
    titulo = seguranca.mascarar(str(titulo or "Sem título"))[:80]
    comentario = seguranca.mascarar(seguranca.sem_ordens(str(comentario or "")))[:1200]
    agora = datetime.datetime.now()
    if tipo == "desenho":
        svg = limpar_svg(obra)
        (pasta / f"{base}.svg").write_text(svg, encoding="utf-8")
        corpo = f"![[{base}.svg]]"
    elif tipo == "musica":
        dur = compor_wav(obra, pasta / f"{base}.wav")
        corpo = (f"![[{base}.wav]]\n\n*{dur:.0f} s · andamento {obra.get('andamento', 90)} · timbre {obra.get('timbre', 'triangulo')}*"
                 f"\n\n```json\n{json.dumps(obra, ensure_ascii=False)[:3000]}\n```")
    else:
        poema = seguranca.mascarar(seguranca.sem_ordens(str(obra or "")))[:3000].strip()
        if len(poema) < 10:
            raise ValueError("poema vazio")
        corpo = poema
    nota = pasta / f"{base}.md"
    nota.write_text(f"---\ntipo: {tipo}\nquem_fez: a Sexta\nquando: {agora:%Y-%m-%d %H:%M}\n---\n\n# {titulo}\n\n{corpo}\n\n"
                    f"## O que eu quis dizer\n\n{comentario}\n\n"
                    f"<!-- {cfg.NOME}: para comentar, escreva uma linha começando com \"{cfg.NOME}:\" aqui embaixo. -->\n",
                    encoding="utf-8")
    return cfg.rel(nota)


def recentes(n=4):
    obras = sorted(ARTE.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True) if ARTE.exists() else []
    saida = []
    for p in obras[:n]:
        t = p.read_text(encoding="utf-8")
        tipo = re.search(r"^tipo: (\w+)", t, re.M)
        titulo = re.search(r"^# (.+)$", t, re.M)
        saida.append({"nota": p.stem, "tipo": tipo.group(1) if tipo else "?", "titulo": titulo.group(1) if titulo else p.stem,
                      "texto": re.sub(r"^---\n.*?\n---\n", "", t, flags=re.S)[:1500]})
    return saida


def acrescentar_reflexao(nome_nota, reflexao):
    """Ela pensando sobre a própria obra: entra numa seção nova da nota."""
    import seguranca
    alvo = next((p for p in ARTE.rglob("*.md") if p.stem == str(nome_nota).strip()), None) if ARTE.exists() else None
    if not alvo:
        return False
    texto = seguranca.mascarar(seguranca.sem_ordens(str(reflexao)))[:1500].strip()
    if not texto:
        return False
    with open(alvo, "a", encoding="utf-8") as f:
        f.write(f"\n## Relendo, em {datetime.datetime.now():%d/%m %H:%M}\n\n{texto}\n")
    return True


def feedback(vistos):
    """Comentários novos do dono nas notas das obras: [(tipo, titulo, texto, chave)]."""
    novos = []
    if not ARTE.exists():
        return novos
    pref = re.compile(rf"^\s*{re.escape(cfg.NOME)}\s*:\s*(.+)$", re.I | re.M)
    for p in ARTE.rglob("*.md"):
        t = p.read_text(encoding="utf-8")
        tipo = re.search(r"^tipo: (\w+)", t, re.M)
        for m in pref.finditer(re.sub(r"<!--.*?-->", "", t, flags=re.S)):
            chave = hashlib.md5((p.name + m.group(1)).encode()).hexdigest()[:12]
            if chave not in vistos:
                novos.append((tipo.group(1) if tipo else "desenho", p.stem, m.group(1).strip()[:300], chave))
    return novos


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["testar"]:
        print(limpar_svg('<svg viewBox="0 0 10 10" onload="x()"><script>alert(1)</script><circle r="4" fill="url(#g)"/>'
                         '<image href="http://mal.com/a.png"/></svg>'))
        print(compor_wav({"andamento": 120, "melodia": [["C4", 1], ["E4", 1], ["G4", 2]]}, pathlib.Path("teste.wav")), "s")
