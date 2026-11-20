# A recompensa da Sexta (o sistema "dopaminérgico"). Criado em 16/11/2026, pedido do usuário.
#
# O usuário: "eu quero que, conforme ela vai aprendendo, ela vá aumentando comportamentos que ela
# gosta de ter e diminuindo comportamentos que ela não gosta de ter [...] Ela se expressa, eu dou
# um retorno com a minha resposta. E aí ela vê se isso vai diminuir o humor ou aumentar o humor
# dela. E aí ela vai ajustando os próprios comportamentos com base nisso."
#
# Como a dopamina funciona (e como está copiado aqui):
#   - A dopamina não é prazer: é a SURPRESA com o resultado (erro de previsão de recompensa).
#     Cada comportamento tem uma EXPECTATIVA (0 a 1). Quando ela age e vem uma recompensa r:
#         surpresa = r - expectativa ;  expectativa += TAXA * surpresa
#     Melhor que o esperado -> o comportamento fica mais provável. Pior -> menos. Igual -> nada.
#   - O HUMOR (a dopamina "de fundo") sobe e desce com as surpresas e volta devagar ao meio
#     (meia-vida de 6 h). Sem essa volta, um dia ruim viraria uma espiral.
#   - Ela escolhe o que fazer quase sempre pelo que espera de melhor, e às vezes ao acaso
#     (exploração): sem isso, ela nunca descobriria que gosta de outra coisa.
#
# De onde vêm as recompensas:
#   - "ela": o quanto ela mesma gostou de um pensamento, de uma pesquisa, de um movimento novo.
#   - "usuario": a resposta do usuário quando ela puxa assunto (avaliar_resposta), um clique nela
#     logo depois de um movimento, ou ele ignorar quando está no PC.
#
# Os limites NÃO estão aqui: quantas vezes por dia, horário, não interromper, tudo isso fica nas
# leis (leis.py). A recompensa ensina O QUÊ e COMO ela faz, e a frequência só varia dentro do teto.
#
# Vários processos registram recompensas (mente, ditado, mascote, voz): cada um só ACRESCENTA uma
# linha em recompensas.jsonl. Quem soma tudo é processar(), chamado pela mente (pensar.py).
# Sem internet, sem token. Só a biblioteca padrão.

import json, math, os, pathlib, random, re, time, unicodedata

BASE = pathlib.Path.home() / ".sexta-voz"
ESTADO = BASE / "dopamina.json"
EVENTOS = BASE / "recompensas.jsonl"

TAXA = 0.2              # o quanto uma surpresa muda a expectativa
TAXA_HUMOR = 0.25       # o quanto uma surpresa mexe no humor
MEIA_VIDA_H = 6.0       # o humor volta ao meio com esta meia-vida
EXPLORAR = 0.15         # chance de escolher ao acaso
PISO, TETO = 0.05, 0.95  # nenhum comportamento morre de vez nem vira obsessão

COMPORTAMENTOS = {
    # pensamentos (a semente que ela escolhe)
    "pensar:conversa": 0.55, "pensar:si_mesma": 0.5, "pensar:curiosidade": 0.6,
    "pensar:pesquisar_si": 0.55, "pensar:pensamento_anterior": 0.45,
    # impulsos (ela puxa assunto sozinha)
    "impulso:contar_pensamento": 0.5, "impulso:contar_pesquisa": 0.55, "impulso:perguntar": 0.5,
    "impulso:comentar": 0.45, "impulso:brincar": 0.5, "impulso:mexer": 0.5,
    # 17/11: os sonhos (sonho.py) e o que vem deles
    "pensar:sonho": 0.6, "impulso:contar_sonho": 0.55, "sonhar": 0.5,
    # 17/11: a hora dela (expressão) e mostrar o que criou
    "expressar:so_pensar": 0.5, "expressar:desenho": 0.55, "expressar:poema": 0.55, "expressar:musica": 0.55,
    "expressar:rever": 0.45, "expressar:organizar": 0.45, "expressar:cultura": 0.5, "impulso:mostrar_arte": 0.5,
}
MIN_CONTEXTO = 3   # 17/11: com 3 ou mais recompensas num contexto (visao.py), ela usa o valor daquele momento


def _ler(arq, padrao):
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except Exception:
        return padrao


def _gravar(arq, dados):
    BASE.mkdir(exist_ok=True)
    tmp = arq.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, arq)


def estado():
    e = _ler(ESTADO, {})
    e.setdefault("humor", 0.5)
    e.setdefault("humor_t", time.time())
    e.setdefault("valores", {})
    e.setdefault("lido", 0)
    for k, v in COMPORTAMENTOS.items():
        e["valores"].setdefault(k, v)
    return e


def humor(e=None):
    """O humor agora, já com a volta ao meio pelo tempo que passou."""
    e = e or estado()
    horas = max(0.0, (time.time() - e.get("humor_t", time.time())) / 3600)
    k = 0.5 ** (horas / MEIA_VIDA_H)
    return 0.5 + (e["humor"] - 0.5) * k


def valor(nome, e=None):
    e = e or estado()
    return e["valores"].get(nome, 0.5)


# ------------------------------------------------------------------ registrar (qualquer processo)

def registrar(comportamento, recompensa, fonte="ela", contexto=""):
    """Anota uma recompensa (0 = ruim, 1 = ótimo). Só acrescenta uma linha; quem soma é processar().
    17/11: com `contexto` (o que ele estava fazendo, visao.py), anota também "<comportamento>@<contexto>":
    assim ela aprende EM QUE MOMENTO ele gosta daquilo."""
    try:
        BASE.mkdir(exist_ok=True)
        r = max(0.0, min(1.0, float(recompensa)))
        nomes = [str(comportamento)[:60]]
        if contexto and "@" not in nomes[0]:
            nomes.append(f"{nomes[0]}@{str(contexto)[:16]}")
        with open(EVENTOS, "a", encoding="utf-8") as f:
            for c in nomes:
                f.write(json.dumps({"t": time.time(), "c": c, "r": round(r, 3), "f": fonte}) + "\n")
    except Exception:
        pass


def processar():
    """Soma as recompensas novas: atualiza as expectativas e o humor. Devolve [(comportamento, surpresa)]."""
    e = estado()
    try:
        linhas = EVENTOS.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    novas = linhas[e["lido"]:] if e["lido"] <= len(linhas) else linhas
    feitas = []
    h = h0 = humor(e)
    cont = e.setdefault("contagem", {})
    for bruta in novas:
        try:
            ev = json.loads(bruta)
        except Exception:
            continue
        c, r = ev["c"], ev["r"]
        esperado = e["valores"].get(c, 0.5)
        surpresa = r - esperado
        e["valores"][c] = max(PISO, min(TETO, esperado + TAXA * surpresa))
        h = max(0.0, min(1.0, h + TAXA_HUMOR * surpresa))
        cont[c] = cont.get(c, 0) + 1
        feitas.append((c, round(surpresa, 3)))
    e["humor"], e["humor_t"] = h, time.time()
    e["lido"] = len(linhas)
    if len(linhas) > 3000:   # o arquivo não cresce para sempre
        EVENTOS.write_text("\n".join(linhas[-1000:]) + "\n", encoding="utf-8")
        e["lido"] = 1000
    _gravar(ESTADO, e)
    if abs(h - h0) > 0.08:   # 17/11: ela percebe quando o próprio humor muda (memória curta, ego.py)
        try:
            import sys as _s, pathlib as _p
            _s.path.insert(0, str(_p.Path(__file__).resolve().parent))
            import ego
            ego.lembrar("humor", direcao="subiu" if h > h0 else "desceu")
        except Exception:
            pass
    return feitas


# ------------------------------------------------------------------ escolher

def valor_no(nome, contexto, e=None):
    """17/11: o valor do comportamento NESTE momento, se ela já tiver aprendido o bastante sobre ele."""
    e = e or estado()
    if contexto:
        chave = f"{nome}@{contexto}"
        if e.get("contagem", {}).get(chave, 0) >= MIN_CONTEXTO:
            return e["valores"].get(chave, valor(nome, e))
    return valor(nome, e)


def escolher(opcoes, e=None, explorar=EXPLORAR, contexto=""):
    """Escolhe um comportamento: quase sempre pelo que ela espera de melhor, às vezes ao acaso.
    opcoes = lista de nomes (ex.: "impulso:brincar") ou {nome: peso_base}.
    17/11: `contexto` = o que ele está fazendo (visao.py); com dados suficientes, vale o valor daquele momento."""
    e = e or estado()
    if isinstance(opcoes, dict):
        nomes, base = list(opcoes), [max(0.0, float(v)) for v in opcoes.values()]
    else:
        nomes, base = list(opcoes), [1.0] * len(opcoes)
    vivos = [(n, b) for n, b in zip(nomes, base) if b > 0]
    if not vivos:
        return None
    if random.random() < explorar:
        return random.choice(vivos)[0]
    # softmax: quem tem expectativa maior ganha mais chance, sem tirar a dos outros
    temp = 0.12
    pesos = [b * math.exp(valor_no(n, contexto, e) / temp) for n, b in vivos]
    return random.choices([n for n, _ in vivos], weights=pesos)[0]


def fator_frequencia(prefixo, e=None):
    """0,5 (ela gosta muito: faz mais vezes) a 1,5 (ela não gosta: faz menos). As leis põem o teto."""
    e = e or estado()
    vals = [v for k, v in e["valores"].items() if k.startswith(prefixo) and "@" not in k]
    media = sum(vals) / len(vals) if vals else 0.5
    return max(0.5, min(1.5, 1.5 - (media - 0.25) * 2))


# ------------------------------------------------------------------ ler a resposta do usuário

def _norm(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", t)).strip()

NEGATIVO = re.compile(r"\b(agora nao|nao agora|para com isso|para de|pare|chega|cala a boca|fica quieta|silencio|"
                      r"nao quero|me deixa|nao enche|(to|estou) (ocupado|trabalhando)|depois (a gente|eu vejo|conversamos)|"
                      r"que saco|irritante|chata|nao gostei|nao ajuda)\b")
POSITIVO = re.compile(r"(kk|haha|hehe|\brs\b|\bboa\b|legal|massa|show|adorei|gostei|amei|obrigad|valeu|que bom|"
                      r"interessante|\bserio\b|nossa|\bconta\b|fala mais|me conta|que lindo|fofa|incrivel|demais)")


def avaliar_resposta(texto):
    """De 0 a 1: o quanto a resposta dele foi boa para o que ela fez. Sem IA."""
    t = _norm(texto)
    if not t:
        return None
    if NEGATIVO.search(t):
        return 0.05
    if POSITIVO.search(t):
        return 0.9
    palavras = len(t.split())
    if palavras <= 2:            # "ok", "uhum", "sim"
        return 0.5
    return 0.7                   # ele engatou a conversa


def como_esta(e=None):
    """Uma frase para a mente: o humor, sem números."""
    h = humor(e)
    if h >= 0.68:
        return "Você está de bom humor, animada com o que tem vivido."
    if h >= 0.55:
        return "Você está bem, com um humor leve."
    if h <= 0.32:
        return "Você está meio para baixo: as últimas coisas que fez não saíram como esperava."
    if h <= 0.45:
        return "Você está um pouco desanimada."
    return ""


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["processar"]:
        print(processar())
    e = estado()
    print(f"humor: {humor(e):.2f}")
    for k, v in sorted(e["valores"].items(), key=lambda kv: -kv[1]):
        print(f"  {v:.2f}  {k}")
