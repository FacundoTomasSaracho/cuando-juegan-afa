"""
Scraper para promiedos.com.ar
Extrae los partidos del día de la Liga Profesional Argentina.
"""
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from config import (
    ARGENTINA_TZ,
    LIGA_PROFESIONAL_ID,
    LIGA_PROFESIONAL_NAME,
    PROMIEDOS_URL,
)

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# Status enum values
STATUS_SCHEDULED = 1
STATUS_IN_PROGRESS = 2
STATUS_FINISHED = 3


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_html() -> str:
    """Descarga el HTML de promiedos.com.ar."""
    resp = requests.get(PROMIEDOS_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


# ---------------------------------------------------------------------------
# Extraction strategies
# ---------------------------------------------------------------------------

def _try_next_data(html: str) -> Optional[Dict]:
    """Intenta extraer JSON de la tag __NEXT_DATA__ de Next.js."""
    pattern = r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as e:
        logger.debug(f"__NEXT_DATA__ JSON parse error: {e}")
        return None


def _try_script_tags(html: str) -> Optional[Any]:
    """Busca en todos los <script> uno que contenga datos de la liga."""
    soup = BeautifulSoup(html, "lxml")
    candidates = []

    for script in soup.find_all("script"):
        text = script.string or ""
        if not text:
            continue
        # Busca el ID de liga o el nombre
        if (
            f'"{LIGA_PROFESIONAL_ID}"' in text
            or "liga profesional" in text.lower()
        ):
            candidates.append(text)

    for text in candidates:
        # Intenta diferentes patrones de asignación JS
        patterns = [
            r'window\.__NEXT_DATA__\s*=\s*(\{.*)',
            r'window\.dataLayer\s*=\s*(\[.*?\])\s*;',
            r'dataLayer\.push\((\{.*?\})\)\s*;',
            r'var\s+\w+\s*=\s*(\{.*?\})\s*;',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass

        # Intenta parsear el texto completo como JSON
        stripped = text.strip()
        if stripped.startswith(("{", "[")):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass

    return None


# ---------------------------------------------------------------------------
# Structure traversal
# ---------------------------------------------------------------------------

def _is_liga_league(obj: Any) -> bool:
    """Devuelve True si el objeto parece ser el contenedor de Liga Profesional."""
    if not isinstance(obj, dict):
        return False
    league_id = str(obj.get("id", "")).lower()
    league_name = str(obj.get("name", "")).lower()
    has_games = bool(obj.get("games") or obj.get("matches") or obj.get("fixtures"))
    return (
        league_id == LIGA_PROFESIONAL_ID
        or "liga profesional" in league_name
    ) and has_games


def _find_all(obj: Any, predicate, depth: int = 0, max_depth: int = 20) -> List[Any]:
    """Recorre recursivamente la estructura y retorna todos los objetos que cumplan predicate."""
    if depth > max_depth:
        return []
    results = []
    if predicate(obj):
        results.append(obj)
    if isinstance(obj, dict):
        for v in obj.values():
            results.extend(_find_all(v, predicate, depth + 1, max_depth))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_find_all(item, predicate, depth + 1, max_depth))
    return results


def _extract_games(league_obj: Dict) -> List[Dict]:
    """Extrae el array de partidos del objeto liga."""
    return (
        league_obj.get("games")
        or league_obj.get("matches")
        or league_obj.get("fixtures")
        or []
    )


# ---------------------------------------------------------------------------
# Match parsing
# ---------------------------------------------------------------------------

def _parse_start_time(raw: str) -> Optional[datetime]:
    """Parsea 'DD-MM-YYYY HH:MM' en datetime naive (hora argentina)."""
    for fmt in ("%d-%m-%Y %H:%M", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def _parse_match(game: Dict) -> Optional[Dict]:
    """Convierte un dict de partido raw en un dict normalizado."""
    try:
        teams = game.get("teams", [])
        if len(teams) < 2:
            return None

        home, away = teams[0], teams[1]

        scores = game.get("scores", [])
        home_score = scores[0] if len(scores) > 0 else None
        away_score = scores[1] if len(scores) > 1 else None

        # Score puede venir como int o string vacío
        if home_score == "" or home_score is None:
            home_score = None
        if away_score == "" or away_score is None:
            away_score = None

        status = game.get("status", {})
        if isinstance(status, int):
            status_enum = status
            status_name = {1: "Programado", 2: "En curso", 3: "Finalizado"}.get(status, "")
        else:
            status_enum = status.get("enum", 0)
            status_name = status.get("name", "")

        start_raw = game.get("start_time", "")
        start_dt = _parse_start_time(start_raw) if start_raw else None
        start_str = start_dt.strftime("%H:%M") if start_dt else "?"

        tv_networks = [
            tv.get("name", "") for tv in game.get("tv_networks", []) if tv.get("name")
        ]

        return {
            "id": game.get("id", ""),
            "round": game.get("stage_round_name", ""),
            "home_team": home.get("name", "Equipo Local"),
            "away_team": away.get("name", "Equipo Visitante"),
            "home_short": home.get("short_name") or home.get("name", ""),
            "away_short": away.get("short_name") or away.get("name", ""),
            "home_score": home_score,
            "away_score": away_score,
            "start_time": start_dt,          # datetime naive (ART)
            "start_time_str": start_str,
            "status_enum": status_enum,      # 1=prog, 2=en curso, 3=finalizado
            "status_name": status_name,
            "game_time": game.get("game_time", ""),
            "tv_networks": tv_networks,
        }
    except Exception as e:
        logger.warning(f"Error parseando partido: {e} | raw: {game}")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_todays_matches() -> List[Dict]:
    """
    Descarga promiedos.com.ar y retorna los partidos de hoy
    de la Liga Profesional Argentina, ordenados por hora.
    """
    try:
        html = fetch_html()
    except requests.RequestException as e:
        logger.error(f"Error descargando página: {e}")
        return []

    # Intenta extraer la estructura de datos
    data = _try_next_data(html)
    if data is None:
        logger.debug("__NEXT_DATA__ no encontrado, probando script tags...")
        data = _try_script_tags(html)

    if data is None:
        logger.error("No se pudo extraer datos de la página.")
        return []

    # Busca el nodo de Liga Profesional
    league_nodes = _find_all(data, _is_liga_league)

    if not league_nodes:
        logger.warning(
            "No se encontró sección de Liga Profesional Argentina en los datos. "
            "El sitio puede haber cambiado su estructura."
        )
        return []

    logger.info(f"Encontré {len(league_nodes)} nodo(s) de Liga Profesional")

    raw_games: List[Dict] = []
    for node in league_nodes:
        raw_games.extend(_extract_games(node))

    # Deduplica por ID
    seen_ids = set()
    unique_games = []
    for g in raw_games:
        gid = g.get("id", "")
        if gid not in seen_ids:
            seen_ids.add(gid)
            unique_games.append(g)

    # Parsea y filtra
    today_arg = datetime.now(ARGENTINA_TZ).date()
    matches = []
    for raw in unique_games:
        parsed = _parse_match(raw)
        if parsed is None:
            continue
        # Filtra solo partidos de hoy (o sin fecha asignada todavía)
        if parsed["start_time"] is None or parsed["start_time"].date() == today_arg:
            matches.append(parsed)

    # Ordena por hora de inicio
    matches.sort(key=lambda m: m["start_time"] or datetime.min)

    logger.info(
        f"Partidos de hoy en Liga Profesional Argentina: {len(matches)}"
    )
    for m in matches:
        logger.info(
            f"  {m['start_time_str']} | {m['home_team']} vs {m['away_team']} "
            f"[{m['status_name']}]"
        )

    return matches
