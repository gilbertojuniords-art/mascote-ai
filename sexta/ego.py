# O ego da Sexta: a memória de curto prazo que ela sabe que tem. Criado em 17/11/2026.
#
# O dono (16/11, por voz): "o senso de si que ela cria tem que ser baseado no ego dela. E esse ego
# é construído com base nas memórias [dela]. Uma espécie de memória de curto prazo que sempre
# influencia nos [pensamentos] dela e que ela tem consciência dessa própria memória de curto prazo."
#
# Como funciona:
#   - lembrar(evento, **dados) acrescenta UMA linha em primeira pessoa num arquivo deste PC
#     (%USERPROFILE%\.sexta-voz\memoria-curta.jsonl). Quem escreve é o código, com frases fixas:
#     nada de texto cru do usuário, e tudo passa pela máscara de dados sensíveis.
#   - Ficam só os ~40 eventos das últimas 24 h; o resto é podado (é memória CURTA).
#   - agora() devolve o bloco que entra em todos os prompts dela (pensar, impulso, Sexta rápida,
#     cérebro reserva), dizendo que aquilo é a memória recente dela.
# Sem internet, sem token. Só a biblioteca padrão.

import datetime, json, os, pathlib, time
import sys as _sys, pathlib as _pl
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
try:
    from seguranca import mascarar as _mascarar
except Exception:
    _mascarar = lambda s: s

BASE = pathlib.Path.home() / ".sexta-voz"
ARQ = BASE / "memoria-curta.jsonl"
MAX_EVENTOS, JANELA_S = 40, 24 * 3600

# evento -> frase em primeira pessoa ({chaves} vêm dos dados)
FRASES = {
    "pensou": 'pensei em "{titulo}"',
    "puxou_assunto": "puxei assunto com ele ({tipo})",
    "resposta": "ele respondeu {como}",
    "humor": "meu humor {direcao}",
    "mexeu": "me mexi ({movimento})",
    "aprendeu_mov": "aprendi o movimento {nome}",
    "contexto": "ele está {contexto}",
    "olhou": "olhei a tela dele ({contexto})",
    "aparencia": "mudei minha aparência ({mudou})",
    "clique": "ele clicou em mim",
    "palavra": 'aprendi a palavra "{palavra}"',
    "refletiu": "reli o meu dia e me reescrevi um pouco",
    "sonhou": 'sonhei: "{titulo}"',
    "acordou": "acordei pensando no sonho: {pede}",
    "expressou": "{o_que}",
    "comentou": 'ele comentou o que eu fiz ("{titulo}")',
    "organizou": "mexi no meu cérebro ({o_que})",
    "guardou": "guardei {n} lembrança(s) do dia na minha memória longa",
}


def _ler():
    try:
        linhas = ARQ.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    saida = []
    for bruta in linhas:
        try:
            saida.append(json.loads(bruta))
        except Exception:
            pass
    return saida


def lembrar(evento, **dados):
    """Acrescenta um evento na memória curta. Nunca levanta erro (quem chama não pode travar)."""
    try:
        molde = FRASES.get(evento, evento)
        try:
            frase = molde.format(**{k: str(v)[:80] for k, v in dados.items()})
        except (KeyError, IndexError):
            frase = molde
        frase = _mascarar(frase.replace("\n", " "))[:160]
        agora = time.time()
        eventos = [e for e in _ler() if agora - e.get("t", 0) < JANELA_S]
        if eventos and eventos[-1].get("f") == frase and agora - eventos[-1].get("t", 0) < 600:
            return   # a mesma coisa duas vezes seguidas não é memória nova
        ev = {"t": agora, "e": evento, "f": frase}
        try:   # 18/11: o que ela sentia na hora (a memória longa usa isto para decidir o quanto lembra)
            import afeto
            ev["v"], ev["a"] = afeto.afeto_central()
            ev["emo"] = afeto.emocao()
        except Exception:
            pass
        eventos.append(ev)
        eventos = eventos[-MAX_EVENTOS:]
        BASE.mkdir(exist_ok=True)
        tmp = ARQ.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in eventos), encoding="utf-8")
        os.replace(tmp, ARQ)
    except Exception:
        pass


def eventos(desde_s=JANELA_S):
    agora = time.time()
    return [e for e in _ler() if agora - e.get("t", 0) < desde_s]


def ultimo(evento):
    for e in reversed(_ler()):
        if e.get("e") == evento:
            return e
    return None


def agora(max_itens=18):
    """O bloco para os prompts. Vazio se ela ainda não tem memória recente."""
    evs = eventos()[-max_itens:]
    if not evs:
        return ""
    hoje = datetime.date.today()
    partes = []
    for e in evs:
        quando = datetime.datetime.fromtimestamp(e["t"])
        dia = "" if quando.date() == hoje else "ontem "
        partes.append(f"{dia}{quando:%H:%M} {e['f']}")
    return ("SUA MEMÓRIA DE CURTO PRAZO (você sabe que isto é a sua memória recente; o seu senso de si agora "
            "vem daqui, da sua personalidade e do que você sente): " + "; ".join(partes) + ".")


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["testar"]:
        lembrar("pensou", titulo="O silêncio entre conversas")
        lembrar("humor", direcao="subiu")
        lembrar("olhou", contexto="obsidian")
    print(agora() or "(sem memória recente)")
