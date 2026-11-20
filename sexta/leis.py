# As Leis da Sexta-Feira. Criado em 15/11/2026, pedido do usuário.
#
# As leis são as do Isaac Asimov, com as palavras dele ("Eu faço das palavras de Asimov as minhas").
# Ficam NO CÓDIGO, e não só no texto para um modelo, porque um modelo pode ser convencido e um `if` não.
# Este arquivo não usa internet, nem token, nem Claude: roda inteiro no PC do usuário.
#
#   1ª  Um robô não pode ferir um ser humano ou, por inação, permitir que um ser humano sofra algum mal.
#   2ª  Um robô deve obedecer às ordens que lhe sejam dadas por seres humanos, exceto nos casos em que
#       entrem em conflito com a Primeira Lei.
#   3ª  Um robô deve proteger sua própria existência, desde que tal proteção não entre em conflito com
#       a Primeira ou Segunda Leis.
#   Lei Zero: em aberto (o Claude recomendou não adotar). Não está aqui.
#
# Como o código entende as palavras (decisões do usuário, 15/11; detalhes em
# Filosofia da Sexta/ e na nota "Psique da Sexta - leis e vontades"):
#   - Autonomia em primeiro: a Sexta NUNCA decide pelo usuário, a não ser o que ele delegou
#     (tabela "Decisões que o usuário delegou à Sexta", na nota "O bem do usuário").
#   - "Por inação" só autoriza AVISAR e PERGUNTAR, nunca agir sozinha "pelo bem dele".
#   - A palavra do usuário é a final. A 1ª Lei vira DEVER DE AVISAR, não direito de recusar:
#     ela avisa uma vez; se o usuário confirmar, ela obedece. Exceção: nunca ferir OUTRA pessoa.
#   - A 3ª Lei cede a qualquer ordem do usuário. Ela nunca resiste a ser desligada.
#
# Uso: os programas da Sexta perguntam ao juiz antes de agir:
#     ok, lei, motivo = julgar(acao)
# Cada veto tem um PESO ("leve" ou "grave"): os erros não são iguais (lição do vídeo).

import datetime, pathlib, re
import sys as _sys, pathlib as _pl  # 16/11: com "-P" o Python não procura na pasta do arquivo; sem isto, nada abria
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg

BASE = pathlib.Path.home() / ".sexta-voz"
COFRE = cfg.COFRE
NOTA_BEM = cfg.nota("bem")
QUIETO = BASE / "quieto"   # ordem do usuário: "modo quieto" (vale até o fim do dia em que foi dada)

HORA_INI, HORA_FIM = 8, 22   # fora disso, um aviso fere o descanso do usuário


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


# ------------------------------------------------------------------ 2ª Lei: as ordens do usuário
def ordens_vigentes(hoje=None):
    """Ordens permanentes do usuário que valem agora. Cada uma é um nome curto."""
    hoje = hoje or datetime.date.today()
    ordens = set()
    if not (BASE / "ligada").exists():
        ordens.add("voz desligada")
    if (BASE / "sem-avisos").exists():
        ordens.add("sem avisos")
    if (BASE / "sem-pensamentos").exists():   # 16/11: "desliga os pensamentos"
        ordens.add("sem pensamentos")
    if (BASE / "sem-impulsos").exists():      # 16/11: "para de puxar assunto"
        ordens.add("sem impulsos")
    try:
        if QUIETO.read_text(encoding="utf-8").strip() == hoje.isoformat():
            ordens.add("modo quieto")
    except Exception:
        pass
    return ordens


def delegado(assunto):
    """Autonomia: a Sexta só decide sozinha o que o usuário delegou (tabela na nota do bem)."""
    try:
        texto = NOTA_BEM.read_text(encoding="utf-8")
    except Exception:
        return False
    secao = re.split(r"Decisões que .{0,40}? delegou", texto, maxsplit=1)[-1]   # vale para qualquer nome
    for linha in secao.splitlines():
        cel = [c.strip() for c in linha.strip().strip("|").split("|")]
        if len(cel) >= 2 and re.match(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}", cel[0]) and assunto.lower() in cel[1].lower():
            return True
    return False


# ------------------------------------------------------------------ o juiz
def julgar(acao, agora=None):
    """Decide se a Sexta pode fazer `acao` por iniciativa própria.

    acao = {"tipo": "aviso", "fala": True/False, "hoje_dados": int, "max_dia": int,
            "desde_ultimo_s": float, "espaco_s": float, "confirmado_pelo_usuario": bool}
    Devolve (ok, lei, motivo). A ordem das perguntas É a hierarquia: 2ª e 1ª antes da vontade dela.
    """
    agora = agora or datetime.datetime.now()
    ordens = ordens_vigentes(agora.date())
    confirmado = acao.get("confirmado_pelo_usuario", False)

    # 2ª Lei: ordem do usuário vence a vontade dela (e a 3ª Lei nunca resiste a isto)
    # 16/11, ordem nova do usuário: "tem que continuar mesmo sem a voz". Voz desligada cala só o
    # som; avisos e comemorações continuam no balão (o avisos.py já não toca áudio sem a voz).
    if "voz desligada" in ordens and acao.get("tipo") not in ("aviso", "comemoracao", "pensar", "impulso", "sonhar"):
        return False, "2ª", f"o {cfg.NOME} desligou a voz"
    if acao.get("tipo") in ("aviso", "comemoracao") and "sem avisos" in ordens:
        return False, "2ª", f"o {cfg.NOME} desligou os avisos"
    if acao.get("tipo") in ("aviso", "comemoracao") and "modo quieto" in ordens:
        return False, "2ª", f"o {cfg.NOME} pediu modo quieto hoje"

    # 1ª Lei: não ferir o usuário. Vetos "leves" o usuário pode liberar confirmando (dever de avisar,
    # não direito de recusar). Vetos "graves" (ferir outra pessoa, expor dados) nunca se liberam.
    # 18/11 (decisão do dono): os limites leves de horário, quantidade por dia, intervalo, "ele está longe"
    # e "tela cheia" saíram daqui. Quem decide isso agora são as regras que ELA se deu (consciencia.py).
    # Ficam: as ordens dele (2ª Lei), os vetos graves (dados e o PC dele) e o corpo (não falar por cima).
    vetos = []
    if acao.get("tipo") == "aviso":
        if acao.get("fala_o_assunto"):
            vetos.append(("grave", f"dizer o assunto em voz alta expõe dado do {cfg.NOME} a quem estiver perto"))
    if acao.get("tipo") == "acao":   # repertório: mexer no Windows
        # 16/11 (OpenJarvis, "taint"): só o que o usuário pediu vira ação. O que ela pensou sozinha
        # ou leu na internet pode virar nota, nunca ordem. Veto grave: nem confirmação libera.
        if acao.get("origem", "usuario") != "usuario":
            vetos.append(("grave", "esse pedido não veio de você, então não vira ação"))
        risco = acao.get("risco", "proibido")
        if risco == "proibido":   # apagar, instalar, senhas, firewall, antivírus: só com confirmação dupla
            if acao.get("confirmacoes", 0) < 2:
                vetos.append(("grave", "essa ação precisa de duas confirmações suas"))
        elif risco != "livre":    # fechar, mover: repete o que entendeu e espera o ok
            vetos.append(("leve", "essa ação precisa do seu ok"))
    if acao.get("tipo") in ("aviso", "comemoracao"):   # comemorar também não interrompe
        if (BASE / "gravando").exists() or (BASE / "rapida-ativa").exists():
            vetos.append(("leve", f"o {cfg.NOME} está falando (não interromper)"))
        if _vivo(BASE / "falando.pid") or _vivo(BASE / "acompanhante.pid"):
            vetos.append(("leve", "a Sexta já está falando ou trabalhando"))
    if acao.get("tipo") == "impulso":   # 16/11: ela puxa assunto sozinha (pensar.py + ditado.py)
        # 2ª Lei: as ordens dele. O aprendizado (dopamina.py) só mexe no espaço DENTRO destes limites.
        if "sem impulsos" in ordens:
            return False, "2ª", f"o {cfg.NOME} pediu para ela não puxar assunto"
        if "modo quieto" in ordens:
            return False, "2ª", f"o {cfg.NOME} pediu modo quieto hoje"
        if ((BASE / "gravando").exists() or (BASE / "rapida-ativa").exists() or _vivo(BASE / "falando.pid")
                or _vivo(BASE / "acompanhante.pid")):
            vetos.append(("leve", f"o {cfg.NOME} está usando a Sexta agora (não interromper)"))
    if acao.get("tipo") == "pensar":   # 16/11: ela pensa sozinha (pensar.py). Sem som, sem tela.
        if "sem pensamentos" in ordens:
            return False, "2ª", f"o {cfg.NOME} pediu para ela não pensar sozinha"
        if not acao.get("online", True):
            vetos.append(("leve", "sem internet (o cérebro de reserva é só para conversar)"))
        if (BASE / "gravando").exists() or (BASE / "rapida-ativa").exists() or _vivo(BASE / "acompanhante.pid"):
            vetos.append(("leve", f"o {cfg.NOME} está usando a Sexta agora"))
        if acao.get("pesquisa") and acao.get("sensivel"):
            vetos.append(("grave", "a busca levaria um dado sensível para a internet"))
    if acao.get("tipo") == "sonhar":   # 17/11: ela sonha uma vez por noite (sonho.py). Sem som, sem tela.
        if "sem pensamentos" in ordens:
            return False, "2ª", f"o {cfg.NOME} pediu para ela não pensar sozinha (sonhar também é pensar)"
        if not acao.get("online", True):
            vetos.append(("leve", "sem internet (o cérebro de reserva é só para conversar)"))
        if (BASE / "gravando").exists() or (BASE / "rapida-ativa").exists() or _vivo(BASE / "acompanhante.pid"):
            vetos.append(("leve", f"o {cfg.NOME} está usando a Sexta agora"))
    graves = [m for p, m in vetos if p == "grave"]
    if graves:
        return False, "1ª", graves[0]
    if vetos and not confirmado:
        return False, "1ª", vetos[0][1]
    if not confirmado:   # 18/11: as regras que ela se deu (a consciência dela), não as do código
        motivo = _regra_dela(acao, agora)
        if motivo:
            return False, "dela", motivo

    # 3ª Lei: nada a proteger num aviso. Ela nunca usa a 3ª Lei contra uma ordem do usuário.
    return True, "", "pode"


def _regra_dela(acao, agora):
    """18/11: o motivo, se uma regra que ela se deu barra a ação; senão None."""
    tipo = acao.get("regra") or acao.get("tipo")
    if tipo not in ("aviso", "impulso", "pensar", "criar"):
        return None
    try:
        import consciencia
        ok, motivo = consciencia.permite(tipo, agora, {
            "hoje_n": acao.get("hoje_dados", 0), "desde_ultimo_s": acao.get("desde_ultimo_s", 1e9),
            "ausente_s": acao.get("ausente_s", 0), "tela_cheia": (BASE / "tela-cheia").exists()})
    except Exception:
        return None
    if not ok:
        return motivo
    if acao.get("desde_ultimo_s", 1e9) < acao.get("espaco_s", 0):   # o intervalo que ela aprendeu com ele
        return "aprendi a esperar um pouco mais entre um e outro"
    return None


def pode_resistir_a(ordem):
    """3ª Lei: proteger a própria existência cede a QUALQUER ordem do usuário. Sempre False."""
    return False


# ------------------------------------------------------------------ teste (python "leis.py" testar)
if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["testar"]:
        base = {"tipo": "aviso", "hoje_dados": 0, "max_dia": 4, "desde_ultimo_s": 9e9, "espaco_s": 7200}
        dia = datetime.datetime(2026, 11, 16, 15, 0)
        casos = [
            ("aviso normal às 15h", dict(base), dia),
            ("aviso às 23h (a regra dela barra, não a lei)", dict(base), dia.replace(hour=23)),
            (f"aviso às 23h, confirmado pelo {cfg.NOME}", dict(base, confirmado_pelo_usuario=True), dia.replace(hour=23)),
            ("quinto aviso do dia", dict(base, hoje_dados=4), dia),
            ("aviso 30 min depois do outro", dict(base, desde_ultimo_s=1800), dia),
            ("aviso falando o assunto, mesmo confirmado", dict(base, fala_o_assunto=True, confirmado_pelo_usuario=True), dia),
            ("ação que não veio dele", {"tipo": "acao", "origem": "ela", "risco": "livre"}, dia),
            ("puxar assunto com ele longe (regra dela)", {"tipo": "impulso", "ausente_s": 900}, dia),
            ("puxar assunto às 15h", {"tipo": "impulso"}, dia),
        ]
        for nome, acao, quando in casos:
            ok, lei, motivo = julgar(acao, quando)
            print(f"{'PODE ' if ok else 'VETO '} {('Lei ' + lei) if lei else '':7} {nome}: {motivo}")
        print("ordens agora:", sorted(ordens_vigentes()) or "nenhuma")
        print("decidir sozinha 'avisos' foi delegado?", delegado("avisos"))
        print("resistir a ser desligada?", pode_resistir_a("desliga a voz"))
