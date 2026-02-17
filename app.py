# app.py
import streamlit as st
from collections import defaultdict
import unicodedata

# Recomendado para emojis compuestos (pip install regex)
try:
    import regex as re  # type: ignore
    HAS_REGEX = True
except Exception:
    import re  # type: ignore
    HAS_REGEX = False

ROUND_RE = re.compile(r"^\s*(\d+)\.\s*(.*)\s*$")


def normalize_line(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip()


def split_graphemes(s: str) -> list[str]:
    """
    Divide en 'grapheme clusters' para soportar emojis compuestos.
    Si no hay regex, cae al fallback por caracteres.
    """
    s = normalize_line(s).replace(" ", "")
    if not s:
        return []
    if HAS_REGEX:
        # \X = grapheme cluster
        return [g for g in re.findall(r"\X", s) if g and g != "\u200d"]
    return list(s)


def parse_input(text: str):
    """
    title = primera línea no vacía
    rounds[ronda] = lista de líneas (strings) dentro de la ronda, en orden,
                   donde rounds[ronda][0] es el podio (3 emojis).
    """
    lines = text.splitlines()
    cleaned = [unicodedata.normalize("NFC", ln.rstrip("\n\r")) for ln in lines]

    # título
    title = ""
    i = 0
    while i < len(cleaned) and not normalize_line(cleaned[i]):
        i += 1
    if i < len(cleaned):
        title = normalize_line(cleaned[i])
        i += 1

    rounds: dict[int, list[str]] = {}
    current_round: int | None = None

    for j in range(i, len(cleaned)):
        line = normalize_line(cleaned[j])

        if not line:
            continue  # separadores

        m = ROUND_RE.match(line)
        if m:
            rn = int(m.group(1))
            rest = (m.group(2) or "").strip()
            current_round = rn
            rounds.setdefault(rn, [])
            rounds[rn].append(rest)  # podio puede venir aquí
        else:
            if current_round is None:
                continue
            rounds[current_round].append(line)

    # Si el podio quedó vacío (ej. "1."), intenta usar la siguiente línea como podio
    for rn, lst in rounds.items():
        if lst and normalize_line(lst[0]) == "":
            lst.pop(0)

    return title, rounds


def score_round(lines: list[str], totals: defaultdict[str, int], errors: list[str], rn: int):
    if not lines:
        errors.append(f"Ronda {rn}: no tiene líneas.")
        return

    podium_raw = normalize_line(lines[0])
    podium_emojis = split_graphemes(podium_raw)

    if len(podium_emojis) != 3:
        errors.append(
            f"Ronda {rn}: la línea de podio debe tener EXACTAMENTE 3 emojis, pero encontré {len(podium_emojis)} en: '{podium_raw}'"
        )
    else:
        for emo, pts in zip(podium_emojis, [100, 90, 80]):
            totals[emo] += pts

    for extra_line in lines[1:]:
        for emo in split_graphemes(extra_line):
            totals[emo] += 60


def compute_scores(rounds: dict[int, list[str]]):
    totals = defaultdict(int)
    errors: list[str] = []

    for rn in sorted(rounds.keys()):
        score_round(rounds[rn], totals, errors, rn)

    ranking = sorted(totals.items(), key=lambda x: (-x[1], x[0]))
    return ranking, errors


# ----------------------------
# Streamlit UI
# ----------------------------
st.set_page_config(page_title="Contador de dinámicas", layout="centered")
st.title("🧮 Contador de dinámicas")

st.markdown(
    """
Pega aquí el input completo.

**Formato:**
- La **primera línea** (no vacía) es el **título** (puede variar).
- Cada ronda inicia con `N.`.
- La línea del `N.` es el **podio** y debe tener **3 emojis** → 100 / 90 / 80.
- Las líneas siguientes dentro de esa ronda: **cada emoji vale 60**.
- Líneas en blanco se ignoran (solo separan).
"""
)

text = st.text_area("Input", height=460)

if st.button("Calcular"):
    title, rounds = parse_input(text)
    ranking, errors = compute_scores(rounds)

    st.subheader(title or "Resultados")

    st.write(f"Rondas detectadas: **{len(rounds)}**")

    if errors:
        st.error("Problemas detectados:")
        for e in errors:
            st.write(f"- {e}")

    if not ranking:
        st.warning("No se detectaron emojis para puntuar.")
    else:
        st.markdown("### 🏆 Ranking final")
        st.table([{"Participante": emo, "Puntos": pts} for emo, pts in ranking])

        st.markdown("### 📋 Salida para copiar")
        out_lines = [title] if title else ["Resultados"]
        out_lines += [f"{emo}: {pts}" for emo, pts in ranking]
        st.code("\n".join(out_lines), language="text")
