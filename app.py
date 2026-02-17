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
TEAM_ORDER = ["🤍", "💚", "🖤"]
TEAM_NAME = {
    "🤍": "𝐃𝐫𝐚𝐠𝐨𝐧𝐬𝐭𝐨𝐧𝐞",
    "💚": "𝐇𝐢𝐠𝐡𝐭𝐨𝐰𝐞𝐫",
    "🖤": "𝐓𝐚𝐫𝐠𝐚𝐫𝐲𝐞𝐧",
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


def parse_podium_positions(podium_raw: str):
    """
    Convierte la línea de podio en una lista de 3 posiciones.
    Cada posición es una lista de 1+ emojis (para empates en paréntesis).

    Ej: "🖤(🤍💚)💚" -> [["🖤"], ["🤍","💚"], ["💚"]]

    Validación:
    - Si hay paréntesis en el podio, deben contener EXACTAMENTE 2 emojis.
    """
    s = normalize_line(podium_raw).replace(" ", "")
    positions: list[list[str]] = []
    errors: list[str] = []

    i = 0
    while i < len(s):
        ch = s[i]

        if ch == "(":
            j = s.find(")", i + 1)
            if j == -1:
                errors.append("Paréntesis '(' sin cerrar en el podio.")
                i += 1
                continue

            inside = s[i + 1 : j]
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
            errors.append("Paréntesis ')' suelto en el podio.")
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


def emojis_in_nonpodium_line(line: str) -> list[str]:
    """
    Para líneas fuera del podio:
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
# Nota: no existe para todos los caracteres; lo que no exista se deja igual.
FANCY_MAP = {
    **{c: f for c, f in zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                            "𝕬𝕭𝕮𝕯𝕰𝕱𝕲𝕳𝕴𝕵𝕶𝕷𝕸𝕹𝕺𝕻𝕼𝕽𝕾𝕿𝖀𝖁𝖂𝖃𝖄𝖅")},
    **{c: f for c, f in zip("abcdefghijklmnopqrstuvwxyz",
                            "𝖆𝖇𝖈𝖉𝖊𝖋𝖌𝖍𝖎𝖏𝖐𝖑𝖒𝖓𝖔𝖕𝖖𝖗𝖘𝖙𝖚𝖛𝖜𝖝𝖞𝖟")},
}


def to_fancy_text(s: str, remove_accents: bool = True) -> str:
    """
    Convierte "Encadenado" -> "𝕰𝖓𝖈𝖆𝖉𝖊𝖓𝖆𝖉𝖔"
    Por compatibilidad visual, por default quita acentos: "Dinámica" -> "Dinamica".
    """
    base = strip_accents(s) if remove_accents else s
    return "".join(FANCY_MAP.get(ch, ch) for ch in base)


# ----------------------------
# Scoring
# ----------------------------
def score_round(lines: list[str], totals: defaultdict[str, int], errors: list[str], rn: int):
    if not lines:
        errors.append(f"Ronda {rn}: no tiene líneas.")
        return

    podium_raw = lines[0]
    positions, podio_errors = parse_podium_positions(podium_raw)
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


def compute_scores(rounds: dict[int, list[str]]):
    totals = defaultdict(int)
    errors: list[str] = []

    for rn in sorted(rounds.keys()):
        score_round(rounds[rn], totals, errors, rn)

    ranking = sorted(totals.items(), key=lambda x: (-x[1], x[0]))
    return totals, ranking, errors


# ----------------------------
# Output (formato decorado)
# ----------------------------
def render_fancy_output(dynamic_name_plain: str, totals: dict[str, int]) -> str:
    """
    Genera el formato decorado.
    - dynamic_name_plain: nombre sin moderador (ej. "Ahorcado")
    - El nombre se imprime en letras bonitas.
    - Puntos con separador de miles con punto (1.680).
    """
    name_plain = dynamic_name_plain or "Dinamica"
    name_fancy = to_fancy_text(name_plain, remove_accents=True)

    pts = {emo: format_points(int(totals.get(emo, 0))) for emo in TEAM_ORDER}

    out = []
    out.append("╭ ㅤ⃝⃕🖤 ᮫   ▭ׅ ▭ׅ ▭ֹ  🔥ᱹ")
    out.append("╭ִ╼࣪━╼࣪╼࣪━╼࣪╼࣪━╼࣪━╯ . .")

    out.append(f"𝇈⃘  𝆬 ֶָ֪ 𝆬🤍̵  ׅ 𖠵 {TEAM_NAME['🤍']} १ׁ꤫•")
    out.append(f"　⃝ ◯˙ ᜔• {pts['🤍']}")
    out.append("")

    out.append(f"𝇈⃘  𝆬 ֶָ֪ 𝆬💚̵  ׅ 𖠵 {TEAM_NAME['💚']} १ׁ꤫•")
    out.append(f"　⃝ ◯˙ ᜔• {pts['💚']}")
    out.append("")

    out.append(f"𝇈⃘  𝆬 ֶָ֪ 𝆬🖤̵  ׅ 𖠵 {TEAM_NAME['🖤']} १ׁ꤫•")
    out.append(f"　⃝ ◯˙ ᜔• {pts['🖤']}")
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
Pega aquí el input completo.

**Formato:**
- La **primera línea** (no vacía) es el encabezado (ej. `Ahorcado - Areli 🐧`).
- Para el **nombre de la dinámica**, se usa solo lo de antes del `-` (trim).
- Cada ronda inicia con `N.`.
- La línea del `N.` es el **podio** y tiene **3 posiciones**:
  - 1er lugar = 100, 2do = 90, 3er = 80
  - Empate por posición con paréntesis, ej: `1. 🖤(🤍💚)💚`
  - **Validación:** si hay paréntesis en el podio, deben contener **EXACTAMENTE 2 emojis**
- Las líneas siguientes dentro de esa ronda: **cada emoji vale 60**.
- Líneas en blanco se ignoran (WhatsApp suele meter espacios invisibles).
"""
)

text = st.text_area("Input", height=520)

if st.button("Calcular"):
    title_raw, rounds = parse_input(text)
    dynamic_name_plain = extract_dynamic_name(title_raw)

    totals, ranking, errors = compute_scores(rounds)

    st.subheader(dynamic_name_plain or "Resultados")
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

            st.markdown("### 🥇 Podio")
            podium = lines[0]
            positions, podio_errors = parse_podium_positions(podium)

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
