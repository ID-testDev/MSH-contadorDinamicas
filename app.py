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

# Equipos fijos (por ahora)
TEAM_ORDER = ["❤️", "🧡", "🩶"]
TEAM_NAME = {
    "❤️": "𝐅𝐞𝐫𝐫𝐚𝐫𝐢",
    "🧡": "𝐌𝐜𝐋𝐚𝐫𝐞𝐧",
    "🩶": "𝐌𝐞𝐫𝐜𝐞𝐝𝐞𝐬",
}


# ----------------------------
# Helpers (texto / emojis)
# ----------------------------
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
        return [g for g in re.findall(r"\X", s) if g and g != "\u200d"]
    return list(s)


def parse_input(text: str):
    """
    title_raw = primera línea no vacía (ej. "Ahorcado - Areli 🐧")
    rounds[ronda] = lista de líneas (strings) dentro de la ronda, en orden,
                   donde rounds[ronda][0] es el podio (3 posiciones).
    """
    lines = text.splitlines()
    cleaned = [unicodedata.normalize("NFC", ln.rstrip("\n\r")) for ln in lines]

    # encabezado
    title_raw = ""
    i = 0
    while i < len(cleaned) and not normalize_line(cleaned[i]):
        i += 1
    if i < len(cleaned):
        title_raw = normalize_line(cleaned[i])
        i += 1

    rounds: dict[int, list[str]] = {}
    current_round: int | None = None

    for j in range(i, len(cleaned)):
        line = normalize_line(cleaned[j])

        if not line:
            continue  # separadores (incluye "líneas vacías" con espacios)

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

    return title_raw, rounds


# ----------------------------
# Detección automática de formato
# ----------------------------
def detect_format(rounds: dict[int, list[str]]) -> str:
    """
    Detecta si el input es formato 'podio' (clásico) o 'lineal' (nuevo).

    Formato PODIO (clásico):
      - Cada ronda tiene EXACTAMENTE 3 posiciones en la primera línea (el podio)
      - Puede tener líneas extra con emojis sueltos (60 pts c/u)
      - Si TODAS las rondas tienen solo 1 línea con exactamente 3 posiciones -> podio

    Formato LINEAL (nuevo):
      - Cada ronda es UNA sola línea con N posiciones en orden
      - Las posiciones son: 1ro=100, 2do=90, 3ro=80, resto=60
      - Si alguna ronda tiene solo 1 línea con MÁS de 3 posiciones -> lineal

    Heurística:
      - Parsear las posiciones de la primera línea de cada ronda
      - Si la mayoría tiene >3 posiciones -> lineal
      - Si la mayoría tiene exactamente 3 -> podio
    """
    if not rounds:
        return "podio"

    lineal_votes = 0
    podio_votes = 0

    for rn, lines in rounds.items():
        if not lines:
            continue
        first_line = lines[0]
        positions, _ = parse_positions_line(first_line)
        n = len(positions)

        if n > 3:
            lineal_votes += 1
        elif n == 3 and len(lines) == 1:
            # Podría ser cualquiera; si no hay líneas extra pesa poco
            podio_votes += 1
        elif n == 3 and len(lines) > 1:
            # Tiene líneas extra -> claramente formato podio
            podio_votes += 2
        else:
            # n < 3 o n == 0: ambiguo, no cuenta
            pass

    if lineal_votes > podio_votes:
        return "lineal"
    return "podio"


# ----------------------------
# Parser de posiciones (genérico, para ambos formatos)
# ----------------------------
def parse_positions_line(line_raw: str):
    """
    Convierte una línea de emojis/grupos en una lista de posiciones.
    Cada posición es una lista de 1+ emojis (empate si >1).

    Ej: "❤️(🧡🩶)🩶❤️" -> [["❤️"], ["🧡","🩶"], ["🩶"], ["❤️"]]

    Validación: paréntesis deben contener EXACTAMENTE 2 emojis.
    """
    s = normalize_line(line_raw).replace(" ", "")
    positions: list[list[str]] = []
    errors: list[str] = []

    i = 0
    while i < len(s):
        ch = s[i]

        if ch == "(":
            j = s.find(")", i + 1)
            if j == -1:
                errors.append("Paréntesis '(' sin cerrar.")
                i += 1
                continue

            inside = s[i + 1: j]
            emos = [e for e in split_graphemes(inside) if e not in ("(", ")")]

            if len(emos) != 2:
                errors.append(
                    f"Grupo con paréntesis inválido: se esperaban EXACTAMENTE 2 emojis dentro de '(...)' "
                    f"pero encontré {len(emos)} en: '({inside})'"
                )

            if emos:
                positions.append(emos)

            i = j + 1
            continue

        if ch == ")":
            errors.append("Paréntesis ')' suelto.")
            i += 1
            continue

        # Tomar 1 emoji (grapheme) desde i
        if HAS_REGEX:
            m = re.match(r"\X", s[i:])
            g = m.group(0) if m else s[i]
            if g not in ("(", ")"):
                positions.append([g])
            i += len(g)
        else:
            positions.append([ch])
            i += 1

    return positions, errors


# Alias para compatibilidad con código existente
def parse_podium_positions(podium_raw: str):
    return parse_positions_line(podium_raw)


def emojis_in_nonpodium_line(line: str) -> list[str]:
    """
    Para líneas fuera del podio (formato clásico):
    - contamos TODOS los emojis, aunque vengan en paréntesis
    - quitamos paréntesis y contamos lo de adentro igual
    """
    s = normalize_line(line).replace(" ", "").replace("(", "").replace(")", "")
    return split_graphemes(s)


# ----------------------------
# Helpers (puntos / nombre dinámica / letras bonitas)
# ----------------------------
def format_points(n: int) -> str:
    # 1680 -> "1.680"
    return f"{int(n):,}".replace(",", ".")


def extract_dynamic_name(title_raw: str) -> str:
    """
    "Ahorcado - Areli 🐧" -> "Ahorcado"
    "Reloj de Arena - Yuls 🌙" -> "Reloj de Arena"
    Si no hay '-', regresa el título completo.
    """
    t = normalize_line(title_raw)
    if "-" in t:
        left = t.split("-", 1)[0].strip()
        return left if left else t
    return t


def strip_accents(s: str) -> str:
    # "Dinámica" -> "Dinamica" (mejor para letras Unicode que no soportan acentos)
    decomposed = unicodedata.normalize("NFD", s)
    no_marks = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", no_marks)


# Mapa a "letras bonitas" (Mathematical Bold Fraktur)
FANCY_MAP = {
    **{c: f for c, f in zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                            "𝕬𝕭𝕮𝕯𝕰𝕱𝕲𝕳𝕴𝕵𝕶𝕷𝕸𝕹𝕺𝕻𝕼𝕽𝕾𝕿𝖀𝖁𝖂𝖃𝖄𝖅")},
    **{c: f for c, f in zip("abcdefghijklmnopqrstuvwxyz",
                            "𝖆𝖇𝖈𝖉𝖊𝖋𝖌𝖍𝖎𝖏𝖐𝖑𝖒𝖓𝖔𝖕𝖖𝖗𝖘𝖙𝖚𝖛𝖜𝖝𝖞𝖟")},
}


def to_fancy_text(s: str, remove_accents: bool = True) -> str:
    base = strip_accents(s) if remove_accents else s
    return "".join(FANCY_MAP.get(ch, ch) for ch in base)


# ----------------------------
# Scoring — Formato PODIO (clásico)
# ----------------------------
def score_round_podio(lines: list[str], totals: defaultdict[str, int], errors: list[str], rn: int):
    if not lines:
        errors.append(f"Ronda {rn}: no tiene líneas.")
        return

    podium_raw = lines[0]
    positions, podio_errors = parse_positions_line(podium_raw)
    for pe in podio_errors:
        errors.append(f"Ronda {rn}: {pe}")

    # Validación: 3 posiciones
    if len(positions) != 3:
        errors.append(
            f"Ronda {rn}: el podio debe tener EXACTAMENTE 3 posiciones (emojis sueltos o grupos), "
            f"pero encontré {len(positions)} en: '{normalize_line(podium_raw)}'"
        )
    else:
        for pos_idx, pts in enumerate([100, 90, 80]):
            for emo in positions[pos_idx]:
                totals[emo] += pts

    # Resto de líneas: cada emoji vale 60
    for extra_line in lines[1:]:
        for emo in emojis_in_nonpodium_line(extra_line):
            totals[emo] += 60


# ----------------------------
# Scoring — Formato LINEAL (nuevo)
# ----------------------------
def score_round_lineal(lines: list[str], totals: defaultdict[str, int], errors: list[str], rn: int):
    """
    Formato lineal: cada ronda es una sola línea con N posiciones en orden.
    - 1ra posición = 100 pts
    - 2da posición = 90 pts
    - 3ra posición = 80 pts
    - 4ta en adelante = 60 pts c/u
    Los paréntesis siguen siendo empates (ambos equipos reciben los mismos puntos).
    """
    if not lines:
        errors.append(f"Ronda {rn}: no tiene líneas.")
        return

    line_raw = lines[0]
    positions, line_errors = parse_positions_line(line_raw)
    for le in line_errors:
        errors.append(f"Ronda {rn}: {le}")

    if not positions:
        errors.append(f"Ronda {rn}: no se encontraron posiciones en: '{normalize_line(line_raw)}'")
        return

    pts_map = [100, 90, 80]
    for pos_idx, pos_emojis in enumerate(positions):
        pts = pts_map[pos_idx] if pos_idx < len(pts_map) else 60
        for emo in pos_emojis:
            totals[emo] += pts


def compute_scores(rounds: dict[int, list[str]], fmt: str):
    totals = defaultdict(int)
    errors: list[str] = []

    for rn in sorted(rounds.keys()):
        if fmt == "lineal":
            score_round_lineal(rounds[rn], totals, errors, rn)
        else:
            score_round_podio(rounds[rn], totals, errors, rn)

    ranking = sorted(totals.items(), key=lambda x: (-x[1], x[0]))
    return totals, ranking, errors


# ----------------------------
# Output (formato decorado)
# ----------------------------
def render_fancy_output(dynamic_name_plain: str, totals: dict[str, int]) -> str:
    name_plain = dynamic_name_plain or "Dinamica"
    name_fancy = to_fancy_text(name_plain, remove_accents=True)

    pts = {emo: format_points(int(totals.get(emo, 0))) for emo in TEAM_ORDER}

    out = []
    out.append("╭ ㅤ⃝⃕🖤 ᮫   ▭ׅ ▭ׅ ▭ֹ  🔥ᱹ")
    out.append("╭ִ╼࣪━╼࣪╼࣪━╼࣪╼࣪━╼࣪━╯ . .")

    out.append(f"𝇈⃘  𝆬 ֶָ֪ 𝆬❤️̵  ׅ 𖠵 {TEAM_NAME['❤️']} १ׁ꤫•")
    out.append(f"　⃝ ◯˙ ᜔• {pts['❤️']}")
    out.append("")

    out.append(f"𝇈⃘  𝆬 ֶָ֪ 𝆬🧡̵  ׅ 𖠵 {TEAM_NAME['🧡']} १ׁ꤫•")
    out.append(f"　⃝ ◯˙ ᜔• {pts['🧡']}")
    out.append("")

    out.append(f"𝇈⃘  𝆬 ֶָ֪ 𝆬🩶̵  ׅ 𖠵 {TEAM_NAME['🩶']} १ׁ꤫•")
    out.append(f"　⃝ ◯˙ ᜔• {pts['🩶']}")
    out.append("")
    out.append(f"    ╾─̇─ ׄ  𖤐 ׅ ⇢ {name_fancy}  ׅ  ׅ ׅ   ׄ  ׄ  ׄ ")
    out.append("╰▭ׄ ׅ▬ׅ ▭ׄ ׅ▬ׅ ▭ׄ ׅ▬ׅ ׄ▭ׅ ׄ▬ׅ ׄ▭ ׅ ׄ▬ׅ ִ")

    return "\n".join(out)


# ----------------------------
# Streamlit UI
# ----------------------------
st.set_page_config(page_title="Contador de dinámicas", layout="centered")
st.title("🧮 Contador de dinámicas")

st.markdown(
    """
Pega aquí el input completo. La app detecta el formato automáticamente.

**Formato clásico (podio):**
- Primera línea = encabezado (`Ahorcado - Areli 🐧`)
- Cada ronda `N.` tiene el podio en la misma línea con **3 posiciones** (1ro=100, 2do=90, 3ro=80)
- Las líneas siguientes dentro de la ronda: cada emoji vale **60 pts**
- Empates con paréntesis: `1. 🖤(🤍💚)💚`

**Formato lineal (nuevo):**
- Primera línea = encabezado
- Cada ronda `N.` es **una sola línea** con todas las posiciones en orden
- 1ra posición=100, 2da=90, 3ra=80, resto=60
- Empates con paréntesis: `1. ❤️(🧡🩶)🩶❤️...`

En ambos formatos los paréntesis deben contener **exactamente 2 emojis**.
"""
)

text = st.text_area("Input", height=520)

if st.button("Calcular"):
    title_raw, rounds = parse_input(text)
    dynamic_name_plain = extract_dynamic_name(title_raw)

    fmt = detect_format(rounds)
    fmt_label = "📋 Formato detectado: **Lineal** (nuevo)" if fmt == "lineal" else "📋 Formato detectado: **Podio** (clásico)"

    totals, ranking, errors = compute_scores(rounds, fmt)

    st.subheader(dynamic_name_plain or "Resultados")
    st.info(fmt_label)
    st.write(f"Rondas detectadas: **{len(rounds)}**")

    if errors:
        st.error("Problemas detectados:")
        for e in errors:
            st.write(f"- {e}")

    fancy = render_fancy_output(dynamic_name_plain, totals)
    st.markdown("### 📋 Output (formato para WhatsApp)")
    st.code(fancy, language="text")

    with st.expander("Ver tabla de puntos (interno)"):
        st.table([{"Equipo": emo, "Puntos": format_points(int(totals.get(emo, 0)))} for emo in TEAM_ORDER])

    with st.expander("Ver rondas parseadas (debug)"):
        for rn in sorted(rounds.keys()):
            st.markdown(f"## Ronda {rn}")
            lines = rounds[rn]

            if not lines:
                st.write("⚠️ Sin datos")
                st.markdown("---")
                continue

            if fmt == "lineal":
                # --- Debug formato lineal ---
                line_raw = lines[0]
                positions, line_errors = parse_positions_line(line_raw)

                if line_errors:
                    for e in line_errors:
                        st.write(f"⚠️ {e}")

                pts_map = [100, 90, 80]
                temp_totals = defaultdict(int)

                for pos_idx, pos_emojis in enumerate(positions):
                    pts = pts_map[pos_idx] if pos_idx < len(pts_map) else 60
                    label = f"Posición {pos_idx + 1}"
                    if len(pos_emojis) == 1:
                        st.write(f"{label}: {pos_emojis[0]} → {format_points(pts)} pts")
                    else:
                        st.write(f"{label}: {' '.join(pos_emojis)} → {format_points(pts)} pts c/u (empate)")
                    for emo in pos_emojis:
                        temp_totals[emo] += pts

                st.markdown("### 📊 Total por ronda")
                for emo, pts in sorted(temp_totals.items(), key=lambda x: (-x[1], x[0])):
                    st.write(f"{emo}: **{format_points(pts)}**")

            else:
                # --- Debug formato podio (clásico) ---
                st.markdown("### 🥇 Podio")
                podium = lines[0]
                positions, podio_errors = parse_positions_line(podium)

                if podio_errors:
                    for e in podio_errors:
                        st.write(f"⚠️ {e}")

                pts_map = [100, 90, 80]
                if len(positions) != 3:
                    st.write(f"❌ Podio inválido: `{podium}`")
                else:
                    for pos_idx, (pos, pts) in enumerate(zip(positions, pts_map), start=1):
                        if len(pos) == 1:
                            st.write(f"Posición {pos_idx}: {pos[0]} → {format_points(pts)} pts")
                        else:
                            st.write(f"Posición {pos_idx}: {' '.join(pos)} → {format_points(pts)} pts c/u (empate)")

                if len(lines) > 1:
                    st.markdown("### 📌 Líneas extra (60 pts c/u)")
                    for idx, extra in enumerate(lines[1:], start=2):
                        emos = emojis_in_nonpodium_line(extra)
                        subtotal = len(emos) * 60
                        shown = normalize_line(extra)
                        st.write(f"Línea {idx}: {shown} — **{format_points(subtotal)} puntos**")

                st.markdown("### 📊 Total por ronda")
                temp_totals = defaultdict(int)

                if len(positions) == 3:
                    for pos, pts in zip(positions, pts_map):
                        for emo in pos:
                            temp_totals[emo] += pts

                for extra in lines[1:]:
                    for emo in emojis_in_nonpodium_line(extra):
                        temp_totals[emo] += 60

                for emo, pts in sorted(temp_totals.items(), key=lambda x: (-x[1], x[0])):
                    st.write(f"{emo}: **{format_points(pts)}**")

            st.markdown("---")