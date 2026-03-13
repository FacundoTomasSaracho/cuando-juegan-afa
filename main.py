#!/usr/bin/.env python3
# -*- coding: utf-8 -*-
"""
PromiScraper — Scraper de Liga Profesional Argentina + bot de Twitter.

Uso:
  python main.py            → inicia el scheduler en modo continuo
  python main.py --test     → modo de prueba: muestra tweets sin esperar horarios
  python main.py --scrape   → solo imprime los partidos del día y sale
"""
import argparse
import io
import logging
import sys
from pathlib import Path

# ── Windows UTF-8 fix (emojis y caracteres especiales en consola) ──────────
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
# ────────────────────────────────────────────────────────────────────────────

from config import Config, LOG_DIR, ARGENTINA_TZ
from scheduler import MatchScheduler
from scraper import get_todays_matches
from twitter_client import TwitterClient
from formatter import build_daily_tweets, build_reminder_tweet, format_thread_for_log, tweet_to_log_block


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)

    # Fuerza UTF-8 en stdout de Windows para que los emojis y caracteres
    # especiales se muestren correctamente.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Archivo
    file_handler = logging.FileHandler(log_dir / "promscraper.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)

    # Consola (stream ya reconfigurado a UTF-8 arriba)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(logging.INFO)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(console_handler)


# ---------------------------------------------------------------------------
# Modos de ejecución
# ---------------------------------------------------------------------------

def mode_test(config: Config) -> None:
    """
    Modo --test: scrapea los partidos, muestra los tweets simulados y sale.
    Ideal para verificar el formato antes de configurar Twitter.
    """
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("MODO TEST — Simulando tweets del día")
    logger.info("=" * 60)

    matches = get_todays_matches()

    if not matches:
        logger.warning(
            "No se encontraron partidos de hoy. "
            "Verificá que el sitio esté accesible y la fecha sea correcta."
        )
        return

    twitter = TwitterClient(config)  # dry_run forzado por ausencia de credenciales en ..env

    # --- Tweet resumen diario ---
    logger.info("")
    logger.info("━" * 60)
    logger.info("  SIMULACIÓN: Tweet de las 12:00 hs")
    logger.info("━" * 60)

    daily_tweets = build_daily_tweets(matches)
    twitter.post_thread(daily_tweets)

    # --- Recordatorios por partido ---
    logger.info("")
    logger.info("━" * 60)
    logger.info("  SIMULACIÓN: Tweets recordatorio (10 min antes)")
    logger.info("━" * 60)

    for match in matches:
        reminder = build_reminder_tweet(match)
        logger.info(
            f"\n  Recordatorio para: {match['home_team']} vs {match['away_team']}"
        )
        logger.info("\n" + tweet_to_log_block(reminder, "RECORDATORIO SIMULADO"))

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"Test completado. {len(matches)} partido(s) procesado(s).")
    logger.info("=" * 60)


def mode_scrape(config: Config) -> None:
    """Modo --scrape: solo imprime los partidos encontrados y sale."""
    logger = logging.getLogger(__name__)
    logger.info("Scrapeando partidos del día...")
    matches = get_todays_matches()
    if not matches:
        logger.info("Sin partidos encontrados.")
        return
    logger.info(f"\nPartidos de hoy ({len(matches)}):")
    for m in matches:
        score_str = ""
        if m["home_score"] is not None and m["away_score"] is not None:
            score_str = f" [{m['home_score']}-{m['away_score']}]"
        logger.info(
            f"  {m['start_time_str']} | {m['home_team']} vs {m['away_team']}"
            f"{score_str} — {m['status_name']}"
        )


def mode_ping(config: Config) -> None:
    """Modo --ping: publica un tweet de prueba al instante y sale."""
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("MODO PING — Enviando tweet de prueba")
    logger.info("=" * 60)

    from datetime import datetime
    now = datetime.now(ARGENTINA_TZ).strftime("%H:%M:%S")
    text = f"🤖 Test de conexión — PromiScraper online ✅\n⏰ {now} hs (ART)"

    twitter = TwitterClient(config)
    tweet_id = twitter.post_tweet(text)

    if tweet_id and tweet_id != "dry_run_id":
        logger.info(f"Tweet de prueba publicado correctamente. ID: {tweet_id}")
    elif config.dry_run:
        logger.info("Modo DRY RUN activo — no se publicó nada (sin credenciales).")
    else:
        logger.error("Falló el tweet de prueba. Revisá las credenciales.")


def mode_run(config: Config) -> None:
    """Modo normal: inicia el scheduler bloqueante."""
    twitter = TwitterClient(config)
    scheduler = MatchScheduler(config, twitter)
    scheduler.start()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="PromiScraper — Bot de partidos Liga Profesional Argentina"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Simula los tweets del día sin esperar los horarios programados",
    )
    parser.add_argument(
        "--scrape",
        action="store_true",
        help="Solo muestra los partidos del día y sale",
    )
    parser.add_argument(
        "--ping",
        action="store_true",
        help="Publica un tweet de prueba al instante para verificar credenciales",
    )
    args = parser.parse_args()

    config = Config.from_env()
    setup_logging(config.log_dir)

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("  PromiScraper — Liga Profesional Argentina Bot")
    logger.info("=" * 60)
    logger.info(
        f"  Modo: {'DRY RUN (sin credenciales Twitter)' if config.dry_run else 'PRODUCCIÓN'}"
    )
    logger.info("=" * 60)

    if args.ping:
        mode_ping(config)
    elif args.test:
        mode_test(config)
    elif args.scrape:
        mode_scrape(config)
    else:
        mode_run(config)


if __name__ == "__main__":
    main()
