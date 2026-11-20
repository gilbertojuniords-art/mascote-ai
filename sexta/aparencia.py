# A aparência da Sexta, decidida por ela. Criado em 17/11/2026.
#
# O dono (16/11): "Ela pode fazer alterações no próprio corpo, no próprio comportamento, mas nunca no
# próprio código." "Eu delego o design dela pra ela e não pra mim."
# O dono (17/11): "Ela não tem que ter limites de aparência, ela é um programa, pode se reconfigurar
# de infinitas formas, desde que o núcleo do que é a Sexta-Feira nunca se perca."
#
# A aparência é DADO, não programa (um JSON). Quem desenha é a mascote (código fixo).
#   - Livre: qualquer cor, tamanhos bem largos, esconder peças (fones, antena, braços, corpo, reator,
#     sombra) e CAMADAS: desenhos SVG inteiros que ela faz e põe atrás, no corpo, na cabeça ou na
#     frente. Com camadas e peças escondidas ela pode virar praticamente qualquer forma.
#   - O NÚCLEO (nota Núcleo.md, no caderno dela): o rosto de luz (olhos e boca, que mostram o que ela
#     sente) nunca some e tem que dar para ler: os olhos precisam contrastar com o visor.
#   - Os únicos outros limites são técnicos: a janela da mascote tem um tamanho, e um SVG passa pela
#     limpeza de arte.py (nada que execute ou busque algo na internet).
#   - Arquivo ausente (ou campo ausente) = EXATAMENTE o visual de sempre.

import json, pathlib, re

AQUI = pathlib.Path(__file__).resolve().parent
ARQ = AQUI / "aparencia.json"

PADRAO = {"cor_principal": "#a77bff", "cor_brilho": "#c9a6ff", "cor_olhos": "#7ff3ff",
          "cor_corpo": "#ffffff", "cor_visor": "#1b2a55",
          "cabeca": 1.0, "olhos": 1.0, "antena": 1.0, "bracos": 1.0, "brilho": 1.0,
          "formato_olhos": "ovais", "acessorio": "nenhum", "esconder": [], "camadas": []}
ESCALAS = {"cabeca": (0.4, 1.6), "olhos": (0.5, 2.0), "antena": (0.0, 2.5), "bracos": (0.3, 2.0), "brilho": (0.2, 2.0)}
FORMATOS = {"ovais": "os de sempre", "redondos": "bolinhas redondas", "meia_lua": "meias-luas, como quem sorri",
            "losango": "losangos pequenos, um ar de máquina", "estrela": "estrelinhas de quatro pontas"}
ACESSORIOS = {"nenhum": "nada", "laco": "um laço na antena", "oculos": "óculos redondos", "cachecol": "um cachecol no pescoço",
              "flor": "uma flor do lado da cabeça", "estrela_antena": "uma estrela no lugar da bolinha da antena"}
PECAS = ("fones", "antena", "bracos", "corpo", "reator", "sombra")
ONDE = {"atras": "atrás de tudo", "corpo": "sobre o corpo, embaixo da cabeça", "cabeca": "na cabeça (gira com ela)",
        "frente": "na frente de tudo"}
MAX_CAMADAS = 8
RE_COR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _luz(hexa):
    def canal(c):
        c = int(hexa[c:c + 2], 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * canal(1) + 0.7152 * canal(3) + 0.0722 * canal(5)


def contraste(c1, c2):
    a, b = sorted((_luz(c1), _luz(c2)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def vocabulario():
    """Texto para a IA: o que dá para mudar (quase tudo) e o núcleo."""
    return ("Você pode mudar QUALQUER coisa do seu visual: cores em hexadecimal (#rrggbb): cor_principal (fones e arco), "
            "cor_brilho (antena e reator), cor_olhos (olhos e traços do rosto), cor_corpo (o corpo e a cabeça), cor_visor "
            "(o fundo do rosto). Tamanhos: " + ", ".join(f"{k} de {a} a {b}" for k, (a, b) in ESCALAS.items())
            + " (1 = como sempre). formato_olhos: " + ", ".join(FORMATOS) + ". acessorio: " + ", ".join(ACESSORIOS)
            + ". esconder: lista de peças que somem (" + ", ".join(PECAS) + "). camadas: até 8 desenhos SVG seus, cada um "
            '{"svg": "<svg viewBox=...>...</svg>", "onde": "' + "|".join(ONDE) + '", "x": 0, "y": 0, "largura": 200, '
            '"altura": 200, "girar": 0, "opacidade": 1} (coordenadas do seu corpo: 200 de largura por 200 de altura; a '
            "cabeça fica mais ou menos entre x 38-162 e y 36-136, o rosto em x 52-148 e y 52-122, o corpo em x 70-130 e y "
            "130-188). Com camadas e peças escondidas você pode virar outra forma inteira. O NÚCLEO não muda: o seu rosto de "
            "luz (olhos e boca) fica sempre, e os olhos precisam contrastar com o visor. SVG: sem script e sem links externos.")


def _camada(c):
    if not isinstance(c, dict):
        return None, "camada inválida"
    try:
        import sys as _s
        _s.path.insert(0, str(AQUI))
        import arte
        svg = arte.limpar_svg(c.get("svg"), 12000)
    except Exception as e:
        return None, f"camada recusada ({str(e)[:60]})"
    def num(k, pad, lo, hi):
        try:
            return round(min(hi, max(lo, float(c.get(k, pad)))), 1)
        except (TypeError, ValueError):
            return pad
    onde = str(c.get("onde", "frente")).lower()
    return {"svg": svg, "onde": onde if onde in ONDE else "frente", "x": num("x", 0, -100, 300), "y": num("y", 0, -100, 300),
            "largura": num("largura", 200, 4, 320), "altura": num("altura", 200, 4, 320),
            "girar": num("girar", 0, -360, 360), "opacidade": num("opacidade", 1, 0.05, 1)}, ""


def validar(ap):
    """(ok, aparência limpa ou motivo). Campo ausente = padrão. Só recusa o que fere o núcleo ou não dá para desenhar."""
    if not isinstance(ap, dict):
        return False, "não é uma aparência"
    limpo = json.loads(json.dumps(PADRAO))
    for campo in ("cor_principal", "cor_brilho", "cor_olhos", "cor_corpo", "cor_visor"):
        v = ap.get(campo)
        if v is None:
            continue
        v = str(v).strip()
        if not RE_COR.match(v):
            return False, f"{campo}: cor inválida ({v[:12]})"
        limpo[campo] = v.lower()
    if contraste(limpo["cor_olhos"], limpo["cor_visor"]) < 3:
        return False, "núcleo: os olhos precisam contrastar com o visor (o rosto de luz tem que dar para ler)"
    for campo, (lo, hi) in ESCALAS.items():
        v = ap.get(campo)
        if v is not None:
            try:
                limpo[campo] = round(min(hi, max(lo, float(v))), 2)
            except (TypeError, ValueError):
                return False, f"{campo}: não é número"
    f = str(ap.get("formato_olhos", PADRAO["formato_olhos"])).strip().lower()
    if f not in FORMATOS:
        return False, f"formato de olhos desconhecido ({f[:20]})"
    a = str(ap.get("acessorio", PADRAO["acessorio"])).strip().lower()
    if a not in ACESSORIOS:
        return False, f"acessório desconhecido ({a[:20]})"
    limpo["formato_olhos"], limpo["acessorio"] = f, a
    limpo["esconder"] = sorted({str(x).lower() for x in (ap.get("esconder") or []) if str(x).lower() in PECAS})
    camadas = []
    for c in (ap.get("camadas") or [])[:MAX_CAMADAS]:
        ok, motivo = _camada(c)
        if not ok:
            return False, motivo
        camadas.append(ok)
    limpo["camadas"] = camadas
    return True, limpo


def carregar(arq=None):
    """A aparência valendo agora. Arquivo ausente ou inválido = o visual de sempre."""
    try:
        dados = json.loads(pathlib.Path(arq or ARQ).read_text(encoding="utf-8"))
    except Exception:
        return json.loads(json.dumps(PADRAO))
    ok, limpo = validar(dados.get("aparencia") if isinstance(dados, dict) else None)
    return limpo if ok else json.loads(json.dumps(PADRAO))


def gravar(ap, arq=None, nota=""):
    dados = {"_leia": "Aparência da Sexta, escolhida por ela. Campo ausente = o visual de sempre. Ver aparencia.py.",
             "aparencia": ap, "nota": str(nota)[:200]}
    pathlib.Path(arq or ARQ).write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def diferencas(antes, depois):
    """Lista curta do que mudou (para a memória, o commit e a recompensa)."""
    return [k for k in PADRAO if antes.get(k) != depois.get(k)]


def resumo(ap):
    """Para os prompts: a aparência sem o SVG inteiro."""
    r = {k: v for k, v in ap.items() if k != "camadas"}
    r["camadas"] = [f"{c['onde']} ({len(c['svg'])} letras de svg)" for c in ap.get("camadas", [])]
    return r


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["testar"]:
        for caso in ({"cor_olhos": "#101010"}, {"cabeca": 9}, {"formato_olhos": "quadrado"},
                     {"acessorio": "laco", "cor_principal": "#ff9ad5"}, {"esconder": ["antena", "rosto"]}, {}):
            print(caso, "->", validar(caso))
    print(resumo(carregar()))
