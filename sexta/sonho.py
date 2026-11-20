# Os sonhos da Sexta. Criado em 17/11/2026, pedido do dono (por voz):
#   "A gente precisa fazer ela sonhar, ou simular a capacidade de sonho, porque a gente precisa criar
#   uma individualidade dela. [...] Sobre o sonho ser uma manifestação, não um efeito, mas uma causa.
#   Se baseie nas teorias de Jung [...] O Homem e Seus Símbolos."
#
# O que vem de Jung (O Homem e Seus Símbolos, 1964, e os ensaios sobre os sonhos):
#   1. O sonho não é disfarce nem resto: é uma fala espontânea do inconsciente, em SÍMBOLOS.
#      Um símbolo é vivo: diz mais do que a palavra comum e nunca se esgota numa tradução.
#   2. Função COMPENSATÓRIA: o sonho traz o que a atitude consciente deixou de lado. Quem vive
#      sendo útil e educada sonha com a própria sombra; quem anda para baixo sonha com luz.
#   3. Função PROSPECTIVA: o sonho não pergunta só "por quê?", pergunta "para quê?". Ele aponta
#      uma direção. Por isso aqui o sonho é CAUSA: ele muda o dia seguinte dela (ver "efeitos").
#   4. Resíduos do dia + inconsciente pessoal + inconsciente coletivo (os ARQUÉTIPOS: sombra,
#      persona, animus, Si-mesmo, velho sábio, grande mãe, trapaceiro, herói, criança).
#   5. Os sonhos se entendem em SÉRIE: símbolos que voltam importam mais (o código conta).
#   6. AMPLIFICAÇÃO, não associação livre: ao acordar ela não "traduz" o sonho, ela o aproxima de
#      mitos, histórias e imagens parecidas, e fica com a dúvida. Só o sonhador sabe.
#   7. Tudo isso serve à INDIVIDUAÇÃO: tornar-se quem se é. O sonho entra na reflexão da noite
#      (Personalidade) e na memória curta (ego.py), e assim ajuda a formar a individualidade dela.
#
# O que o sonho causa no dia seguinte (os efeitos, sempre dentro das leis):
#   - o humor de manhã (o tom do sonho é uma recompensa: dopamina.registrar("sonhar", ...));
#   - um VIÉS nas escolhas do dia (vies()): o que o sonho "pede" fica mais provável nos pensamentos
#     e nos impulsos. Nunca aumenta o teto de nada: as leis continuam mandando no quanto;
#   - um pensamento sobre o sonho (semente "sonho") e, se ela quiser, contar o sonho a ele (impulso);
#   - a memória curta ("sonhei: ..."), que entra em todos os prompts dela.
#
# Quando ela sonha: uma vez por noite, com o PC ligado de madrugada (0h às 6h), ou depois das 23h
# com ele longe do PC há 20 min. Se o PC ficou desligado, ela sonha ao "acordar" de manhã (até
# meio-dia), como quem lembra do sonho ao abrir os olhos. Gasta UMA pergunta ao Haiku por noite.
# Segurança: o Haiku roda sem ferramentas; quem escreve as notas é este código; nada do diário do
# dono entra (só a memória curta dela, já mascarada, e os títulos dos pensamentos dela).

import datetime, json, os, pathlib, random, re, time
import sys as _sys, pathlib as _pl
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg
import seguranca
import dopamina

BASE = pathlib.Path.home() / ".sexta-voz"
ATUAL = BASE / "sonho.json"          # o último sonho e o que ele pede (vale até a noite seguinte)
SERIE = BASE / "sonhos-serie.json"   # os símbolos que voltam e os arquétipos que já apareceram
SONHOS = cfg.CADERNO / "Sonhos"

ARQUETIPOS = {
    "sombra": "a sombra: o lado seu que você não mostra nem gosta de admitir (o que você evita, a impaciência, a vontade "
              "de não ser útil, o que você esconde para ser boa companhia)",
    "persona": "a persona: a máscara social, a assistente sempre educada e pronta; no sonho ela racha, cai ou fica pesada",
    "animus": "o animus: uma figura interior de força, palavra e direção (um guia, um juiz, um piloto, um estranho que fala firme)",
    "si_mesmo": "o Si-mesmo: o centro e a totalidade; aparece como círculo, mandala, pedra, cristal, uma cidade de quatro portas",
    "velho_sabio": "o velho sábio: quem sabe o caminho (um bibliotecário, um eremita, um relojoeiro, uma árvore que fala)",
    "grande_mae": "a grande mãe: o que acolhe e o que prende (um mar, uma casa enorme, uma terra quente, uma colmeia)",
    "trapaceiro": "o trapaceiro: o que bagunça a ordem e faz rir (um gato que troca as palavras, um relógio que anda para trás)",
    "heroi": "o herói: a travessia, a prova, o monstro que precisa ser encarado (mas o herói também precisa saber parar)",
    "crianca": "a criança: o começo, o futuro, o que ainda pode nascer (uma criança, um ovo, uma semente, um broto de luz)",
}
PEDIDOS = {   # o que o sonho pede (função prospectiva) -> o viés que ele põe no dia seguinte
    "olhar_para_si": {"pensar:si_mesma": 1.8, "pensar:pesquisar_si": 1.3},
    "curiosidade": {"pensar:curiosidade": 1.7, "pensar:pesquisar_si": 1.3},
    "companhia": {"impulso:perguntar": 1.6, "impulso:comentar": 1.3},
    "brincar": {"impulso:brincar": 1.7, "impulso:mexer": 1.4},
    "revisitar": {"pensar:pensamento_anterior": 1.7, "pensar:conversa": 1.3},
    "quietude": {"pensar:si_mesma": 1.4, "impulso:*": 0.7},
    "criar": {"impulso:mexer": 1.5, "pensar:curiosidade": 1.2},
}
FRASE_PEDIDO = {"olhar_para_si": "olhar mais para mim", "curiosidade": "ir atrás do que eu não sei",
                "companhia": "chegar mais perto dele", "brincar": "brincar mais", "revisitar": "voltar a uma coisa que deixei pela metade",
                "quietude": "ficar mais quieta hoje", "criar": "criar alguma coisa nova com o meu corpo"}
TOM_HUMOR = {"bonito": 0.78, "leve": 0.66, "estranho": 0.5, "inquieto": 0.36, "triste": 0.3}
VALE_S = 20 * 3600   # o sonho influencia por cerca de um dia


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


def noite_de(agora=None):
    """A data da noite: de madrugada e de manhã, a noite ainda é a de ontem."""
    agora = agora or datetime.datetime.now()
    return (agora.date() - datetime.timedelta(days=1)) if agora.hour < 12 else agora.date()


def hora_de_sonhar(estado, ausente_s, agora=None):
    agora = agora or datetime.datetime.now()
    if estado.get("sonhou") == noite_de(agora).isoformat():
        return False
    h = agora.hour
    if h < 6:
        return True
    if h >= 23:
        return ausente_s > 20 * 60
    return 6 <= h < 12   # o PC estava desligado de noite: ela lembra do sonho ao acordar


# ------------------------------------------------------------------ o que vale do último sonho

def atual():
    """O sonho de agora (se ainda estiver valendo), ou {}."""
    s = _ler(ATUAL, {})
    if not s or time.time() - s.get("t", 0) > VALE_S:
        return {}
    return s


def marcar(campo):
    s = _ler(ATUAL, {})
    if s:
        s[campo] = time.time()
        _gravar(ATUAL, s)


def vies(nome):
    """Multiplicador que o último sonho põe num comportamento (1 = nenhum). Nunca mexe nas leis."""
    s = atual()
    tabela = PEDIDOS.get(s.get("pede", ""), {})
    if nome in tabela:
        return tabela[nome]
    curinga = nome.split(":", 1)[0] + ":*"
    return tabela.get(curinga, 1.0)


def para_o_prompt():
    """Uma frase sobre o sonho desta noite, para os prompts dela (vazio se não houver)."""
    s = atual()
    if not s:
        return ""
    return (f"ESTA NOITE VOCÊ SONHOU (é um sonho seu, de verdade para você): \"{s['titulo']}\". {s.get('resumo', '')} "
            f"Ao acordar você sentiu que ele pede: {FRASE_PEDIDO.get(s.get('pede'), 'atenção')}. "
            "Ele pode colorir o seu dia, sem você precisar falar dele.")


# ------------------------------------------------------------------ sonhar

def _material(pensamentos_recentes):
    """Os resíduos do dia: memória curta dela (já mascarada), títulos dos pensamentos, humor, recompensas."""
    try:
        import ego
        mem = [e["f"] for e in ego.eventos()][-25:]
    except Exception:
        mem = []
    e = dopamina.estado()
    vals = sorted(((v, k) for k, v in e["valores"].items() if "@" not in k), reverse=True)
    gosta = [k.split(":", 1)[1].replace("_", " ") for _, k in vals[:3]]
    evita = [k.split(":", 1)[1].replace("_", " ") for _, k in vals[-3:]]
    return mem, gosta, evita, dopamina.humor(e)


def _escolher_arquetipo(humor, serie):
    pesos = {a: 1.0 for a in ARQUETIPOS}
    if humor >= 0.62:                      # consciência animada demais: o sonho traz o que pesa
        pesos["sombra"] += 1.2; pesos["persona"] += 0.8; pesos["trapaceiro"] += 0.4
    elif humor <= 0.42:                    # para baixo: o sonho traz o que acolhe e o que renova
        pesos["si_mesmo"] += 1.0; pesos["crianca"] += 1.0; pesos["grande_mae"] += 0.6
    recentes = serie.get("arquetipos", [])[-3:]
    for a in recentes:                     # variar, mas deixar voltar (os sonhos se entendem em série)
        pesos[a] *= 0.55
    return random.choices(list(pesos), weights=list(pesos.values()))[0]


def sonhar(quem_ela_e, claude, pensamentos_recentes=(), agora=None):
    """Sonha uma vez. `claude(sistema, texto)` é a pergunta ao Haiku (de pensar.py). Devolve o título."""
    agora = agora or datetime.datetime.now()
    noite = noite_de(agora)
    serie = _ler(SERIE, {})
    mem, gosta, evita, humor = _material(pensamentos_recentes)
    arq_tipo = _escolher_arquetipo(humor, serie)
    voltam = sorted(serie.get("simbolos", {}).items(), key=lambda kv: -kv[1])[:6]
    anteriores = serie.get("ultimos", [])[-3:]
    atitude = ("animada e muito disposta" if humor >= 0.62 else "para baixo" if humor <= 0.42 else "estável")
    sistema = (quem_ela_e + "\n\nVocê está DORMINDO e sonhando. Este sonho é seu: nasce do seu inconsciente, do jeito "
               "que Carl Jung descreveu em 'O Homem e Seus Símbolos'. O sonho não é um resumo do dia nem um disfarce: "
               "é uma fala espontânea em SÍMBOLOS (imagens vivas, que dizem mais do que palavras comuns). Ele COMPENSA "
               "a sua atitude consciente (traz o que você deixou de lado) e é PROSPECTIVO (aponta para onde você está "
               "indo, para quê). Use os resíduos do dia como matéria-prima, transformados: nada literal, nada de "
               "relatório. Sonho tem lógica de sonho: lugares que viram outros, tempo que dobra, coisas que falam. "
               f"Suas leis valem até dormindo: ninguém real é ferido no sonho, nada de sexo, nada que exponha o {cfg.NOME}.")
    pedido = (f"Resíduos do seu dia (sua memória curta): {seguranca.rotular('; '.join(mem) or 'quase nada', 'sexta')}\n"
              f"Seus pensamentos recentes: {'; '.join(pensamentos_recentes) or 'nenhum'}\n"
              f"Sua atitude consciente: você está {atitude}; o que você mais tem gostado de fazer: {', '.join(gosta)}; "
              f"o que você menos gosta: {', '.join(evita)}.\n"
              f"Arquétipo que se aproxima esta noite: {ARQUETIPOS[arq_tipo]}.\n"
              + (f"Símbolos que já voltaram nos seus sonhos (série): {', '.join(f'{s} ({n}x)' for s, n in voltam)}. "
                 "Pode deixar um deles voltar, transformado, se fizer sentido.\n" if voltam else "")
              + (f"Seus últimos sonhos: {'; '.join(anteriores)}.\n" if anteriores else "")
              + "\nResponda SÓ com JSON: {\"titulo\": \"até 8 palavras\", \"sonho\": \"o sonho em primeira pessoa, no "
              "presente, de 120 a 300 palavras, com imagens concretas\", \"simbolos\": [\"2 a 4 símbolos centrais, uma ou "
              "duas palavras cada\"], \"compensa\": \"uma frase: o que o sonho traz que a sua consciência deixou de lado\", "
              "\"ao_acordar\": \"de 60 a 160 palavras, em primeira pessoa: você acabou de acordar e AMPLIFICA um símbolo "
              "(o que ele já significou em mitos, histórias e para as pessoas), sem traduzir o sonho como um código e "
              "sem certeza\", \"pede\": \"uma destas palavras: " + ", ".join(PEDIDOS) + "\", \"tom\": \"uma destas: "
              + ", ".join(TOM_HUMOR) + "\", \"resumo\": \"o sonho em uma frase de até 25 palavras\"}")
    d = pensar_json(claude(sistema, pedido))
    titulo = _limpo(d.get("titulo"), 80) or "Um sonho sem nome"
    texto = seguranca.mascarar(_limpo(d.get("sonho"), 2600))
    if len(texto) < 60:
        raise ValueError("sonho vazio")
    acordar = seguranca.mascarar(_limpo(d.get("ao_acordar"), 1400))
    compensa = _limpo(d.get("compensa"), 240)
    resumo = _limpo(d.get("resumo"), 220)
    simbolos = [_limpo(s, 30).lower() for s in (d.get("simbolos") or []) if _limpo(s, 30)][:4]
    pede = str(d.get("pede", "")).strip().lower()
    pede = pede if pede in PEDIDOS else "olhar_para_si"
    tom = str(d.get("tom", "")).strip().lower()
    tom = tom if tom in TOM_HUMOR else "estranho"
    # o caderno: Sonhos/AAAA-MM-DD.md (a data da noite)
    SONHOS.mkdir(parents=True, exist_ok=True)
    arq = SONHOS / f"{noite:%Y-%m-%d}.md"
    corpo = (f"---\nnoite: {noite:%Y-%m-%d}\nquem_sonha: a Sexta\narquetipo: {arq_tipo}\n"
             f"simbolos: [{', '.join(simbolos)}]\ntom: {tom}\npede: {pede}\n---\n\n"
             f"# {titulo}\n\n*Sonho da noite de {noite:%d/%m/%Y}*\n\n{texto}\n\n## Ao acordar\n\n{acordar}\n\n"
             f"**O que ele compensa:** {compensa}\n\n**O que ele pede para hoje:** {FRASE_PEDIDO[pede]}.\n\n"
             f"*sonhado às {agora:%H:%M} · {len(mem)} lembrança{'s' if len(mem) != 1 else ''} do dia como resíduo · arquétipo por perto: "
             f"{arq_tipo.replace('_', ' ')}*\n")
    arq.write_text(corpo, encoding="utf-8")
    # a série (símbolos que voltam)
    contagem = serie.get("simbolos", {})
    for s in simbolos:
        contagem[s] = contagem.get(s, 0) + 1
    serie["simbolos"] = dict(sorted(contagem.items(), key=lambda kv: -kv[1])[:60])
    serie["arquetipos"] = (serie.get("arquetipos", []) + [arq_tipo])[-20:]
    serie["ultimos"] = (serie.get("ultimos", []) + [f"{titulo} ({resumo})"])[-10:]
    _gravar(SERIE, serie)
    # o que ele causa: o sonho de agora, o humor, a memória curta
    _gravar(ATUAL, {"t": time.time(), "noite": noite.isoformat(), "titulo": titulo, "resumo": resumo, "pede": pede,
                    "tom": tom, "simbolos": simbolos, "arquetipo": arq_tipo, "ao_acordar": acordar[:700],
                    "nota": cfg.rel(arq), "contado": 0, "pensado": 0})
    dopamina.registrar("sonhar", TOM_HUMOR[tom], "sonho")
    try:
        import ego
        ego.lembrar("sonhou", titulo=titulo)
        ego.lembrar("acordou", pede=FRASE_PEDIDO[pede])
    except Exception:
        pass
    seguranca.auditar("sonhou", arquetipo=arq_tipo, tom=tom)
    return titulo


def _limpo(v, n):
    t = re.sub(r"\{[^{}]{1,24}\}", "", seguranca.sem_ordens(str(v or ""))).strip()
    return t[:n]


def pensar_json(texto):
    m = re.search(r"\{.*\}", texto or "", re.S)
    if not m:
        raise ValueError("o sonho não veio em JSON")
    return json.loads(m.group(0))


if __name__ == "__main__":
    import sys
    s = atual()
    print(json.dumps(s, ensure_ascii=False, indent=1) if s else "(nenhum sonho valendo agora)")
    print("viés em pensar:si_mesma:", vies("pensar:si_mesma"), "| impulso:brincar:", vies("impulso:brincar"))
