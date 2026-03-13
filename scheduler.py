"""
Scheduler de jobs usando APScheduler.

Jobs definidos:
  1. daily_summary   – Todos los días a las 12:00 ART: tweetea los partidos del día.
  2. schedule_reminders – Todos los días a las 00:05 ART (y al inicio):
                          lee los partidos de hoy y programa un recordatorio
                          por cada uno, 10 minutos antes de que empiece.
  3. prematch_<id>   – Job dinámico: avisa que un partido empieza en 10 min.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from config import (
    ARGENTINA_TZ,
    DAILY_TWEET_HOUR,
    DAILY_TWEET_MINUTE,
    PRE_MATCH_MINUTES_BEFORE,
    Config,
)
from formatter import build_daily_tweets, build_reminder_tweet
from scraper import get_todays_matches
from twitter_client import TwitterClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Funciones de job (deben ser importables por APScheduler)
# ---------------------------------------------------------------------------

def job_daily_summary(twitter: TwitterClient) -> None:
    """Job: publica el resumen diario a las 12:00 ART."""
    logger.info("─" * 60)
    logger.info("▶ JOB: Resumen diario")
    logger.info("─" * 60)

    matches = get_todays_matches()
    tweets = build_daily_tweets(matches)
    twitter.post_thread(tweets)

    logger.info(f"Resumen diario enviado ({len(tweets)} tweet(s)).")


def job_prematch_reminder(match: Dict, twitter: TwitterClient) -> None:
    """Job: publica el recordatorio 10 min antes del partido."""
    logger.info("─" * 60)
    logger.info(
        f"▶ JOB: Recordatorio → {match['home_team']} vs {match['away_team']}"
    )
    logger.info("─" * 60)

    tweet = build_reminder_tweet(match)
    twitter.post_tweet(tweet)

    logger.info(
        f"Recordatorio enviado: {match['home_team']} vs {match['away_team']} "
        f"a las {match['start_time_str']}"
    )


def job_schedule_reminders(scheduler: BlockingScheduler, twitter: TwitterClient) -> None:
    """
    Job: se ejecuta a las 00:05 ART y al inicio.
    Descarga los partidos de hoy y agenda un job de recordatorio por cada uno.
    """
    logger.info("─" * 60)
    logger.info("▶ JOB: Programando recordatorios de hoy")
    logger.info("─" * 60)

    matches = get_todays_matches()
    now_arg = datetime.now(ARGENTINA_TZ)
    scheduled = 0

    for match in matches:
        if match["start_time"] is None:
            logger.warning(
                f"Sin hora definida: {match['home_team']} vs {match['away_team']} — se omite."
            )
            continue

        # Localiza la hora del partido a zona Argentina
        match_dt = ARGENTINA_TZ.localize(match["start_time"])
        reminder_dt = match_dt - timedelta(minutes=PRE_MATCH_MINUTES_BEFORE)

        if reminder_dt <= now_arg:
            logger.info(
                f"  ⏭ {match['home_team']} vs {match['away_team']} "
                f"ya pasó o es en menos de {PRE_MATCH_MINUTES_BEFORE} min — se omite."
            )
            continue

        job_id = f"prematch_{match['id']}"
        scheduler.add_job(
            job_prematch_reminder,
            trigger=DateTrigger(run_date=reminder_dt, timezone=ARGENTINA_TZ),
            args=[match, twitter],
            id=job_id,
            replace_existing=True,
            name=f"Recordatorio: {match['home_team']} vs {match['away_team']}",
        )
        logger.info(
            f"  ✅ Recordatorio programado: {match['home_team']} vs {match['away_team']} "
            f"a las {reminder_dt.strftime('%H:%M')} ART"
        )
        scheduled += 1

    logger.info(f"Total recordatorios programados: {scheduled}")


# ---------------------------------------------------------------------------
# Clase principal del scheduler
# ---------------------------------------------------------------------------

class MatchScheduler:
    def __init__(self, config: Config, twitter: TwitterClient):
        self.config = config
        self.twitter = twitter
        self.scheduler = BlockingScheduler(timezone=ARGENTINA_TZ)

    def _register_static_jobs(self) -> None:
        """Registra los jobs cron fijos (resumen diario y reprogramación de recordatorios)."""

        # Job 1: Resumen diario a las 12:00 ART
        self.scheduler.add_job(
            job_daily_summary,
            trigger=CronTrigger(
                hour=DAILY_TWEET_HOUR,
                minute=DAILY_TWEET_MINUTE,
                timezone=ARGENTINA_TZ,
            ),
            args=[self.twitter],
            id="daily_summary",
            name="Resumen diario 12:00 ART",
            replace_existing=True,
        )
        logger.info(
            f"Job registrado: Resumen diario a las "
            f"{DAILY_TWEET_HOUR:02d}:{DAILY_TWEET_MINUTE:02d} ART"
        )

        # Job 2: Reprogramar recordatorios a las 00:05 ART (cada día nuevo)
        self.scheduler.add_job(
            job_schedule_reminders,
            trigger=CronTrigger(hour=0, minute=5, timezone=ARGENTINA_TZ),
            args=[self.scheduler, self.twitter],
            id="schedule_reminders_cron",
            name="Reprogramar recordatorios 00:05 ART",
            replace_existing=True,
        )
        logger.info("Job registrado: Reprogramación de recordatorios a las 00:05 ART")

    def start(self) -> None:
        """Inicia el scheduler. Bloquea el hilo principal."""
        self._register_static_jobs()

        # Al inicio, programa los recordatorios de hoy inmediatamente
        logger.info("Programando recordatorios para hoy al inicio...")
        job_schedule_reminders(self.scheduler, self.twitter)

        logger.info("=" * 60)
        logger.info("Scheduler iniciado. Esperando próximos jobs...")
        logger.info("(Ctrl+C para detener)")
        logger.info("=" * 60)

        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler detenido.")
            self.scheduler.shutdown(wait=False)
