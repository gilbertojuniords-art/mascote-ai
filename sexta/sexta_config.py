# Configuração da Sexta: tudo o que é de cada pessoa ou PC fica num JSON fora do Git.
#
# Procura, nesta ordem:
#   1. o caminho na variável de ambiente SEXTA_CONFIG
#   2. sexta.config.json, na mesma pasta deste arquivo
#   3. %USERPROFILE%\.sexta-voz\config.json
# Sem arquivo, valem os padrões abaixo (cofre = duas pastas acima: <cofre>/.claude/sexta/).
# Modelo comentado: config.exemplo.json, na raiz do repositório.

import json, os, pathlib

AQUI = pathlib.Path(__file__).resolve().parent
BASE = pathlib.Path.home() / ".sexta-voz"   # estado de cada PC (fala, ditado, log); nunca vai para o Git


def _ler():
    for p in (os.environ.get("SEXTA_CONFIG"), AQUI / "sexta.config.json", BASE / "config.json"):
        if p and pathlib.Path(p).is_file():
            try:
                d = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
                if isinstance(d, dict):
                    return d
            except Exception:
                pass
    return {}


C = _ler()

NOME = C.get("nome") or "chefe"                       # como a Sexta chama o usuário
COFRE = pathlib.Path(os.path.expandvars(C.get("cofre") or str(AQUI.parents[1])))
NOME_COFRE = C.get("nome_cofre") or COFRE.name        # nome do cofre na linha de comando do Obsidian
RAIZ_NOTAS = COFRE / C.get("raiz_notas", "")          # onde ficam as notas (a central indexa daqui)
PASTA = COFRE / C.get("pasta_sexta", "Sexta")         # notas que a Sexta lê e escreve
PASTA_DIARIO = C.get("pasta_diario", "Diário")        # nome da pasta do diário (dentro de RAIZ_NOTAS)
VOCABULARIO = C.get("vocabulario", "")                # palavras que o Whisper deve reconhecer
VOZ_EDGE = C.get("voz_edge", "pt-BR-ThalitaMultilingualNeural")
# 16/11: o caderno dela (pensamentos, personalidade, fatos que aprendeu). Relativo ao cofre.
CADERNO = COFRE / C["pasta_caderno"] if C.get("pasta_caderno") else PASTA / "Caderno da Sexta"

_NOTAS = {
    "avisos": "Avisos.md",
    "visor": "Visor.md",
    "repertorio": "Repertório.md",
    "perfil": "Sexta rápida - perfil.md",
    "onde_paramos": "Onde paramos.md",
    "bem": "Filosofia/O bem do usuário.md",
    "entrada": "Entrada",
}
_NOTAS.update(C.get("notas") or {})


def nota(chave):
    """Caminho de uma nota da Sexta (relativo a PASTA no JSON)."""
    return PASTA / _NOTAS[chave]


def rel(caminho):
    """Caminho relativo ao cofre, com barras normais (para o Obsidian)."""
    try:
        return pathlib.Path(caminho).relative_to(COFRE).as_posix()
    except ValueError:
        return pathlib.Path(caminho).as_posix()


# Apps da central de comando: [nome, ícone, o que abrir]. Aceita %APPDATA% e afins.
# Ícones desenhados: opera, obsidian, pasta, spotify, painel, claude.
APPS = [(n, i, os.path.expandvars(a)) for n, i, a in (C.get("apps") or [
    ["Obsidian", "obsidian", "obsidian:"],
    ["Explorador", "pasta", "explorer.exe"],
])]
