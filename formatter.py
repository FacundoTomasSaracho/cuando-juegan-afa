"""
Genera el texto de los tweets a partir de los datos de los partidos.
Maneja el límite de 280 caracteres y produce hilos cuando es necesario.
"""
import re
from datetime import datetime
from typing import Dict, List, Tuple

from config import (
    ARGENTINA_TZ,
    LIGA_PROFESIONAL_NAME,
    STOPWORDS_HASHTAG,
    TWEET_MAX_CHARS,
)

# ---------------------------------------------------------------------------
# Helpers de hashtags
# ---------------------------------------------------------------------------

def _team_to_hashtag(team_name: str) -> str:
    """
    'Talleres de Córdoba' -> '#TalleresdeCórdoba'
    'River Plate'        -> '#RiverPlate'
    'Defensa y Justicia' -> '#DefensaJusticia'
    """
    words = team_name.split()
    filtered = [w for w in words if w.lower() not in STOPWORDS_HASHTAG]
    if not filtered:
        filtered = words  # fallback: sin filtrar
    # Primera palabra capitalizada, resto sin cambios
    result = filtered[0].capitalize() + "".join(filtered[1:])
    # Elimina caracteres no permitidos en hashtags (excepto letras, números, _)
    result = re.sub(r"[^\w]", "", result, flags=re.UNICODE)
    return f"#{result}"


def _liga_hashtags() -> str:
    return "#LigaProfesional #Fútbol"


def _match_hashtags(match: Dict) -> str:
    home_tag = _team_to_hashtag(match["home_team"])
    away_tag = _team_to_hashtag(match["away_team"])
    return f"{home_tag} {away_tag} #LigaProfesional"


# ---------------------------------------------------------------------------
# Formato de fecha en español
# ---------------------------------------------------------------------------

DIAS_ES = {
    0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves",
    4: "viernes", 5: "sábado", 6: "domingo",
}
MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def _fecha_hoy() -> str:
    now = datetime.now(ARGENTINA_TZ)
    dia_semana = DIAS_ES[now.weekday()]
    dia_num = now.day
    mes = MESES_ES[now.month]
    return f"{dia_semana} {dia_num} de {mes}"


# ---------------------------------------------------------------------------
# Formato de partidos en línea
# ---------------------------------------------------------------------------

def _match_line(match: Dict) -> str:
    """⏰ 19:15 | Talleres de Córdoba vs Instituto"""
    hora = match["start_time_str"]
    home = match["home_team"]
    away = match["away_team"]
    return f"⏰ {hora} | {home} vs {away}"


def _match_line_short(match: Dict) -> str:
    """⏰ 19:15 | Talleres vs Instituto  (usa short names)"""
    hora = match["start_time_str"]
    home = match["home_short"] or match["home_team"]
    away = match["away_short"] or match["away_team"]
    return f"⏰ {hora} | {home} vs {away}"


# ---------------------------------------------------------------------------
# Tweet diario (hilo si supera 280 chars)
# ---------------------------------------------------------------------------

def build_daily_tweets(matches: List[Dict]) -> List[str]:
    """
    Genera la lista de tweets del resumen diario.
    Si todos caben en 280 chars → retorna [tweet_único].
    Si no → retorna [tweet_intro, tweet_matches_1, ..., tweet_matches_n].
    """
    if not matches:
        return [
            f"🏆 {LIGA_PROFESIONAL_NAME}\n"
            f"📅 Hoy, {_fecha_hoy()}\n\n"
            f"No hay partidos programados para hoy.\n\n"
            f"{_liga_hashtags()}"
        ]

    fecha = _fecha_hoy()
    hashtags = _liga_hashtags()

    # Intenta armar un único tweet
    lineas = [_match_line(m) for m in matches]
    cuerpo = "\n".join(lineas)
    tweet_unico = (
        f"🏆 {LIGA_PROFESIONAL_NAME}\n"
        f"📅 Hoy, {fecha}\n\n"
        f"{cuerpo}\n\n"
        f"{hashtags}"
    )

    if len(tweet_unico) <= TWEET_MAX_CHARS:
        return [tweet_unico]

    # No cabe → construye hilo
    tweets: List[str] = []

    # Tweet 1: intro
    intro = (
        f"🏆 {LIGA_PROFESIONAL_NAME}\n"
        f"📅 Hoy, {fecha}\n"
        f"Se juegan {len(matches)} partido(s) 👇\n\n"
        f"{hashtags}"
    )
    tweets.append(intro)

    # Tweets siguientes: partidos agrupados de a ~3
    chunk: List[str] = []
    for match in matches:
        line = _match_line(match)
        chunk.append(line)
        candidate = "\n".join(chunk)
        # Con margen para numeración (ej "1/3\n")
        if len(candidate) + 10 > TWEET_MAX_CHARS:
            tweets.append("\n".join(chunk[:-1]))
            chunk = [line]

    if chunk:
        tweets.append("\n".join(chunk))

    # Numera los tweets del hilo (excepto el primero)
    total = len(tweets)
    numbered: List[str] = [tweets[0]]
    for i, t in enumerate(tweets[1:], start=2):
        numbered.append(f"{i}/{total}\n{t}")

    return numbered


# ---------------------------------------------------------------------------
# Tweet recordatorio (10 min antes)
# ---------------------------------------------------------------------------

def build_reminder_tweet(match: Dict) -> str:
    """
    Genera el tweet de aviso 10 minutos antes del partido.
    """
    home = match["home_team"]
    away = match["away_team"]
    hora = match["start_time_str"]
    hashtags = _match_hashtags(match)

    tweet = (
        f"⚽ ¡Faltan 10 minutos!\n\n"
        f"🏆 {LIGA_PROFESIONAL_NAME}\n"
        f"{home} 🆚 {away}\n"
        f"⏰ {hora} hs\n\n"
        f"{hashtags}"
    )

    # Si supera el límite, usa nombres cortos
    if len(tweet) > TWEET_MAX_CHARS:
        home = match["home_short"] or home
        away = match["away_short"] or away
        tweet = (
            f"⚽ ¡Faltan 10 minutos!\n\n"
            f"🏆 {LIGA_PROFESIONAL_NAME}\n"
            f"{home} 🆚 {away}\n"
            f"⏰ {hora} hs\n\n"
            f"{hashtags}"
        )

    return tweet[:TWEET_MAX_CHARS]


# ---------------------------------------------------------------------------
# Representación visual de un tweet para logs
# ---------------------------------------------------------------------------

def tweet_to_log_block(tweet: str, label: str = "TWEET SIMULADO") -> str:
    """
    Envuelve el contenido del tweet en un bloque visual para los logs.

    Ejemplo de salida:
    ╔══════════════════════════════════════════╗
    ║          [TWEET SIMULADO]  (247 chars)   ║
    ╠══════════════════════════════════════════╣
    ║ 🏆 Liga Profesional Argentina            ║
    ║ 📅 Hoy, jueves 12 de marzo              ║
    ...
    ╚══════════════════════════════════════════╝
    """
    WIDTH = 54  # ancho interior del bloque

    lines = tweet.split("\n")

    def pad(text: str) -> str:
        # Calcula padding teniendo en cuenta emojis (2 chars de ancho visual)
        visible_len = sum(2 if ord(c) > 0xFFFF or (0x1F300 <= ord(c) <= 0x1FAFF) else 1 for c in text)
        pad_needed = max(0, WIDTH - visible_len)
        return f"║ {text}{' ' * pad_needed} ║"

    header_text = f"[{label}]  ({len(tweet)} chars)"
    header_pad = max(0, WIDTH - len(header_text))
    left_pad = header_pad // 2
    right_pad = header_pad - left_pad

    separator = "╠" + "═" * (WIDTH + 2) + "╣"
    top = "╔" + "═" * (WIDTH + 2) + "╗"
    bottom = "╚" + "═" * (WIDTH + 2) + "╝"
    header_line = f"║{' ' * left_pad} {header_text} {' ' * right_pad}║"

    block_lines = [top, header_line, separator]
    block_lines.append(pad(""))
    for line in lines:
        block_lines.append(pad(line))
    block_lines.append(pad(""))
    block_lines.append(bottom)

    return "\n".join(block_lines)


def format_thread_for_log(tweets: List[str], thread_label: str = "HILO DIARIO") -> str:
    """Formatea un hilo completo para el log."""
    parts = []
    for i, tweet in enumerate(tweets, start=1):
        label = f"{thread_label} - Tweet {i}/{len(tweets)}"
        parts.append(tweet_to_log_block(tweet, label))
    return "\n\n".join(parts)
