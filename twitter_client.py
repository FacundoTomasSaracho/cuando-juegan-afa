"""
Cliente de Twitter con soporte de modo DRY RUN.
En dry_run=True solo genera logs; en False publica a Twitter vía Tweepy.
"""
import logging
from typing import List, Optional

from config import Config
from formatter import format_thread_for_log, tweet_to_log_block

logger = logging.getLogger(__name__)


class TwitterClient:
    def __init__(self, config: Config):
        self.config = config
        self.dry_run = config.dry_run
        self._client = None

        if not self.dry_run:
            self._init_tweepy()

    # ------------------------------------------------------------------
    # Inicialización de Tweepy
    # ------------------------------------------------------------------

    def _init_tweepy(self):
        try:
            import tweepy  # noqa: PLC0415

            self._client = tweepy.Client(
                consumer_key=self.config.api_key,
                consumer_secret=self.config.api_secret,
                access_token=self.config.access_token,
                access_token_secret=self.config.access_secret,
                wait_on_rate_limit=True,
            )
            logger.info("Tweepy inicializado correctamente.")
        except ImportError:
            logger.error("tweepy no instalado. Ejecutá: pip install tweepy")
            self.dry_run = True
        except Exception as e:
            logger.error(f"Error inicializando Tweepy: {e}. Cambiando a dry_run.")
            self.dry_run = True

    # ------------------------------------------------------------------
    # Publicación de tweets
    # ------------------------------------------------------------------

    def post_tweet(self, text: str, reply_to_id: Optional[str] = None) -> Optional[str]:
        """
        Publica un tweet y retorna su ID.
        En dry_run solo loguea el contenido.
        """
        if self.dry_run:
            label = "TWEET SIMULADO"
            logger.info("\n" + tweet_to_log_block(text, label))
            return "dry_run_id"

        try:
            kwargs = {"text": text}
            if reply_to_id:
                kwargs["in_reply_to_tweet_id"] = reply_to_id
            resp = self._client.create_tweet(**kwargs)
            tweet_id = str(resp.data["id"])
            logger.info(f"Tweet publicado: https://twitter.com/i/web/status/{tweet_id}")
            return tweet_id
        except Exception as e:
            logger.error(f"Error publicando tweet: {e}")
            return None

    def post_thread(self, tweets: List[str]) -> List[Optional[str]]:
        """
        Publica una lista de tweets como hilo.
        Cada tweet siguiente responde al anterior.
        En dry_run muestra el hilo completo formateado.
        """
        if not tweets:
            return []

        if self.dry_run:
            logger.info("\n" + format_thread_for_log(tweets, "HILO DIARIO SIMULADO"))
            return ["dry_run_id"] * len(tweets)

        ids: List[Optional[str]] = []
        last_id: Optional[str] = None

        for i, text in enumerate(tweets):
            tweet_id = self.post_tweet(text, reply_to_id=last_id)
            ids.append(tweet_id)
            if tweet_id and tweet_id != "dry_run_id":
                last_id = tweet_id
            else:
                # Si falla uno, detiene el hilo
                logger.warning(f"Tweet {i + 1}/{len(tweets)} falló. Se detiene el hilo.")
                break

        return ids
