# Ouvido da Sexta (17/11/2026). Pedido do usuário: "se a Sexta-Feira pudesse armazenar meus áudios
# por um breve período de tempo pra compreender melhor o que eu falo", e que ela consiga "identificar
# quando eu falo mais alto ou mais baixo", o tom de dúvida, de pergunta, de raiva.
#
#   - DESLIGADO por padrão. Liga com "ouvido_guardar": true no sexta.config.json (escolha do dono).
#   - Cada fala transcrita vira um .wav + um .txt em ~/.sexta-voz/ouvido/ (só no PC, nunca no Drive
#     nem no Git), apagados sozinhos depois de "ouvido_dias" (padrão 2).
#   - As MEDIDAS ficam em ~/.sexta-voz/ouvido-medidas.jsonl: só números e hora, nunca o que foi dito.
#     Elas são a "linha de base": como ele fala normalmente. Ficam até 2000 linhas.
#   - Cada fala é comparada com a linha de base, e o resultado vai para ~/.sexta-voz/ouvido-ultimo.json
#     (ex.: "voz alta", "tom de pergunta", "mais rápido"). Com menos de 15 falas medidas, ela ainda
#     está conhecendo a voz dele e não marca nada.
#   - Mede o FÍSICO (volume, altura, velocidade). "Raiva" ou "dúvida" é leitura dela, com cuidado.
#   - Roda na hora (medido: ~50 ms para 8 s de fala), para a Sexta rápida já receber a medida da fala
#     certa. Qualquer erro é engolido e anotado no log: o ditado nunca para por causa do ouvido.
#
# Comandos: py ouvido.py testar | resumo | limpar

import json, math, pathlib, sys, time, wave
import sys as _sys, pathlib as _pl
if str(_pl.Path(__file__).resolve().parent) not in _sys.path: _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import sexta_config as cfg

BASE = pathlib.Path.home() / ".sexta-voz"
PASTA = BASE / "ouvido"
MEDIDAS = BASE / "ouvido-medidas.jsonl"
ULTIMO = BASE / "ouvido-ultimo.json"
LOG = BASE / "log.txt"
RATE = 16000
MIN_BASE = 15          # falas medidas antes de comparar
MAX_MEDIDAS = 2000
LIGADO = bool(cfg.C.get("ouvido_guardar", False))
DIAS = float(cfg.C.get("ouvido_dias", 2))


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%d/%m %H:%M:%S')} [ouvido] {msg}\n")
    except Exception:
        pass


# ---------- medidas ----------

def _altura(quadro, np):
    """Altura da voz (Hz) de um quadro de 40 ms por autocorrelação, ou None se não for voz."""
    q = quadro - quadro.mean()
    n = len(q)
    f = np.fft.rfft(q, 2 * n)
    ac = np.fft.irfft(f * np.conj(f))[:n]
    if ac[0] <= 0:
        return None
    lo, hi = RATE // 400, RATE // 70          # de 70 a 400 Hz
    k = lo + int(np.argmax(ac[lo:hi]))
    if ac[k] / ac[0] < 0.35:                  # pouco periódico = sem voz (ruído, "s", "f")
        return None
    return RATE / k


def medir(audio, texto=""):
    """Números de uma fala: volume, altura, variação, fim (sobe/desce) e velocidade."""
    import numpy as np
    a = np.asarray(audio, dtype=np.float32)
    if len(a) < RATE // 2:
        return None
    janela, passo = int(0.04 * RATE), int(0.02 * RATE)
    rms = np.array([math.sqrt(float(np.mean(a[i:i + janela] ** 2)) + 1e-12)
                    for i in range(0, len(a) - janela, passo)])
    if not len(rms):
        return None
    limiar = max(0.003, float(np.percentile(rms, 90)) * 0.2)
    com_voz = rms > limiar
    if com_voz.sum() < 10:
        return None
    alturas = []
    for j, i in enumerate(range(0, len(a) - janela, passo)):
        if com_voz[j]:
            h = _altura(a[i:i + janela], np)
            if h:
                alturas.append((j, h))
    seg_voz = float(com_voz.sum()) * passo / RATE
    m = {"t": time.strftime("%Y-%m-%d %H:%M:%S"),
         "dur": round(len(a) / RATE, 2),
         "voz_s": round(seg_voz, 2),
         "volume_db": round(20 * math.log10(float(np.mean(rms[com_voz]))), 2),
         "palavras": len(texto.split()),
         "vel": round(len(texto.split()) / seg_voz, 2) if seg_voz > 0.5 and texto else None}
    if len(alturas) >= 8:
        st = np.array([12 * math.log2(h / 100.0) for _, h in alturas])   # semitons acima de 100 Hz
        m["altura_hz"] = round(float(100 * 2 ** (np.median(st) / 12)), 1)
        m["variacao_st"] = round(float(np.std(st)), 2)
        ultimo_j = alturas[-1][0]
        fim = np.array([12 * math.log2(h / 100.0) for j, h in alturas if j >= ultimo_j - 25])  # último 0,5 s
        if len(fim) >= 4:
            m["fim_st"] = round(float(np.median(fim[-len(fim) // 2:]) - np.median(st)), 2)
    return m


def _base():
    linhas = []
    try:
        for l in MEDIDAS.read_text(encoding="utf-8").splitlines()[-300:]:
            try:
                linhas.append(json.loads(l))
            except Exception:
                pass
    except Exception:
        pass
    return linhas


def comparar(m, base):
    """Compara uma fala com o jeito normal dele. Devolve marcas curtas (ou [] se ainda está aprendendo)."""
    if len(base) < MIN_BASE:
        return []

    def z(campo):
        vals = [b[campo] for b in base if b.get(campo) is not None]
        if len(vals) < MIN_BASE or m.get(campo) is None:
            return 0.0
        med = sorted(vals)[len(vals) // 2]
        desvio = (sum((v - med) ** 2 for v in vals) / len(vals)) ** 0.5 or 1.0
        return (m[campo] - med) / desvio

    marcas = []
    zv, za, zr, zx = z("volume_db"), z("altura_hz"), z("vel"), z("variacao_st")
    if zv > 1.3: marcas.append("voz mais alta que o normal")
    if zv < -1.3: marcas.append("voz mais baixa que o normal")
    if zr > 1.3: marcas.append("falando mais rápido")
    if zr < -1.3: marcas.append("falando mais devagar")
    if za > 1.3: marcas.append("voz mais aguda")
    if (m.get("fim_st") or 0) > 2.0: marcas.append("tom que sobe no fim (pergunta ou dúvida)")
    if zv > 1.0 and zr > 0.8 and (za > 0.8 or zx > 1.0): marcas.append("intensidade alta (pode ser irritação ou empolgação)")
    if zv < -0.8 and zr < -0.8: marcas.append("voz cansada ou pensativa")
    return marcas


# ---------- guardar ----------

def _limpar_velhos():
    limite = time.time() - DIAS * 86400
    for arq in PASTA.glob("*"):
        try:
            if arq.is_file() and arq.stat().st_mtime < limite:
                arq.unlink()
        except Exception:
            pass


def _trabalhar(audio, texto):
    try:
        import numpy as np
        PASTA.mkdir(exist_ok=True)
        _limpar_velhos()
        nome = time.strftime("%Y-%m-%d_%H-%M-%S") + f"_{int(time.time() * 1000) % 1000:03d}"
        a = np.clip(np.asarray(audio, dtype=np.float32), -1, 1)
        with wave.open(str(PASTA / f"{nome}.wav"), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
            w.writeframes((a * 32767).astype("<i2").tobytes())
        (PASTA / f"{nome}.txt").write_text(texto, encoding="utf-8")
        m = medir(a, texto)
        if not m:
            return
        base = _base()
        marcas = comparar(m, base)
        with open(MEDIDAS, "a", encoding="utf-8") as f:
            f.write(json.dumps(m) + "\n")
        linhas = MEDIDAS.read_text(encoding="utf-8").splitlines()
        if len(linhas) > MAX_MEDIDAS:
            MEDIDAS.write_text("\n".join(linhas[-MAX_MEDIDAS:]) + "\n", encoding="utf-8")
        ULTIMO.write_text(json.dumps({"t": m["t"], "marcas": marcas, "medidas": m,
                                      "aprendendo": len(base) < MIN_BASE, "falas_medidas": len(base) + 1},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        log(f"erro: {e!r}")


def registrar(audio, texto):
    """Chamado pelo ditado depois de cada transcrição (uns 50 ms)."""
    if not LIGADO or audio is None or not (texto or "").strip():
        return
    _trabalhar(audio, texto)


def percebido():
    """Para a Sexta rápida: frase curta com o que ela percebeu na última fala (ou "")."""
    try:
        d = json.loads(ULTIMO.read_text(encoding="utf-8"))
        if time.time() - time.mktime(time.strptime(d["t"], "%Y-%m-%d %H:%M:%S")) > 30 or not d.get("marcas"):
            return ""
        return "[como ele falou: " + "; ".join(d["marcas"]) + "]"
    except Exception:
        return ""


# ---------- comandos ----------

def _testar():
    import numpy as np
    def voz(f0_ini, f0_fim, amp, seg=2.0):
        f0 = np.linspace(f0_ini, f0_fim, int(seg * RATE))
        fase = 2 * np.pi * np.cumsum(f0) / RATE
        return amp * (np.sin(fase) + 0.5 * np.sin(2 * fase) + 0.25 * np.sin(3 * fase)).astype(np.float32)

    reta = medir(voz(120, 120, 0.1), "uma frase de teste com oito palavras aqui")
    sobe = medir(np.concatenate([voz(120, 120, 0.1), voz(120, 170, 0.1, 0.5)]), "isso é uma pergunta")
    ok = True
    print("reta:", reta); print("sobe:", sobe)
    if not reta or abs(reta["altura_hz"] - 120) > 8: print("FALHOU: altura da voz reta"); ok = False
    if not sobe or (sobe.get("fim_st") or 0) < 2: print("FALHOU: fim que sobe"); ok = False
    base = [dict(reta, volume_db=reta["volume_db"] + d, vel=3 + d / 10) for d in np.linspace(-1, 1, 20)]
    alto = dict(reta, volume_db=reta["volume_db"] + 6, vel=4.5)
    marcas = comparar(alto, base)
    print("alto e rápido:", marcas)
    if "voz mais alta que o normal" not in marcas or "falando mais rápido" not in marcas: print("FALHOU: comparar"); ok = False
    if comparar(alto, base[:5]): print("FALHOU: marcou com pouca base"); ok = False
    print("OK" if ok else "COM FALHAS"); return ok


def _resumo():
    base = _base()
    print(f"ligado: {LIGADO} · guarda por {DIAS:g} dia(s) · falas medidas: {len(base)} (compara a partir de {MIN_BASE})")
    print(f"áudios guardados agora: {len(list(PASTA.glob('*.wav'))) if PASTA.exists() else 0}")
    if base:
        for campo in ("volume_db", "altura_hz", "vel", "variacao_st"):
            vals = sorted(b[campo] for b in base if b.get(campo) is not None)
            if vals:
                print(f"  {campo}: mediana {vals[len(vals) // 2]} (de {vals[0]} a {vals[-1]})")
    try:
        print("última:", ULTIMO.read_text(encoding="utf-8"))
    except Exception:
        pass


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "resumo"
    if cmd == "testar":
        sys.exit(0 if _testar() else 1)
    elif cmd == "limpar":
        for arq in (PASTA.glob("*") if PASTA.exists() else []):
            arq.unlink(missing_ok=True)
        print("áudios apagados (as medidas, só números, continuam)")
    else:
        _resumo()
