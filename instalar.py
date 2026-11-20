# Instala ou atualiza a Sexta num cofre do Obsidian.
#
#   py -3.12 instalar.py "C:\caminho\do\cofre"
#
# O que faz:
#   1. Guarda uma cópia da versão instalada em %USERPROFILE%\.sexta-voz\backup\sexta-<data-hora>\
#   2. Copia o código de sexta\ para <cofre>\.claude\sexta\
#   3. Se não houver sexta.config.json lá, cria um a partir do config.exemplo.json (edite depois)
#   4. Cria as notas que faltarem (modelos\notas\) na pasta da Sexta. Nunca sobrescreve nota sua.
#   5. Mostra o trecho de hooks para o .claude\settings.json do cofre (não mexe nele sozinho)
#
# Não apaga nada. Só a biblioteca padrão.

import datetime, importlib.util, os, pathlib, shutil, sys

AQUI = pathlib.Path(__file__).resolve().parent
CODIGO = AQUI / "sexta"
MODELOS = AQUI / "modelos" / "notas"
NOTA_DE = {  # modelo -> chave em sexta_config.nota()
    "Avisos.md": "avisos", "Visor.md": "visor", "Repertório.md": "repertorio",
    "Sexta rápida - perfil.md": "perfil", "Onde paramos.md": "onde_paramos",
    "Filosofia/O bem do usuário.md": "bem",
}


def main():
    if len(sys.argv) < 2:
        print(__doc__ or "uso: py -3.12 instalar.py <pasta do cofre>")
        sys.exit(1)
    cofre = pathlib.Path(sys.argv[1]).expanduser().resolve()
    if not (cofre / ".obsidian").is_dir():
        sys.exit(f"Não parece um cofre do Obsidian (falta a pasta .obsidian): {cofre}")
    destino = cofre / ".claude" / "sexta"

    if destino.exists() and any(destino.glob("*.py")):
        copia = pathlib.Path.home() / ".sexta-voz" / "backup" / f"sexta-{datetime.datetime.now():%Y-%m-%d-%H%M%S}"
        shutil.copytree(destino, copia, ignore=shutil.ignore_patterns("__pycache__"))
        print(f"Cópia da versão anterior: {copia}")

    destino.mkdir(parents=True, exist_ok=True)
    n = 0
    for arq in CODIGO.iterdir():
        if arq.is_file() and arq.suffix in (".py", ".html", ".js", ".json") and arq.name != "sexta.config.json":
            shutil.copy2(arq, destino / arq.name)
            n += 1
    print(f"{n} arquivos copiados para {destino}")

    config = destino / "sexta.config.json"
    if not config.exists():
        shutil.copy2(AQUI / "config.exemplo.json", config)
        print(f"Criei {config}: troque pelos seus dados (nome, pastas, apps).")

    # Notas que faltam, onde o config disser
    os.environ.pop("SEXTA_CONFIG", None)
    spec = importlib.util.spec_from_file_location("sexta_config_inst", destino / "sexta_config.py")
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    for modelo, chave in NOTA_DE.items():
        alvo = cfg.nota(chave)
        if not alvo.exists():
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(MODELOS / modelo, alvo)
            print(f"Nota criada: {cfg.rel(alvo)}")
    cfg.nota("entrada").mkdir(parents=True, exist_ok=True)
    # 16/11: o caderno dela (pensar.py). Nunca sobrescreve: o que ela escreveu fica.
    (cfg.CADERNO / "Pensamentos").mkdir(parents=True, exist_ok=True)
    for modelo in (MODELOS / "Caderno da Sexta").glob("*.md"):
        alvo = cfg.CADERNO / modelo.name
        if not alvo.exists():
            alvo.write_text(modelo.read_text(encoding="utf-8").replace("{NOME}", cfg.NOME), encoding="utf-8")
            print(f"Nota criada: {cfg.rel(alvo)}")

    print("\nFalta você (uma vez só):")
    print(f"  1. Juntar os hooks de {AQUI / 'modelos' / 'settings.hooks.json'}")
    print(f"     ao {cofre / '.claude' / 'settings.json'}")
    print("  2. py -3.12 -m pip install -r requirements.txt")
    print("  3. No chat do Claudian: \"liga a voz\"")


if __name__ == "__main__":
    main()
