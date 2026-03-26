"""
Background worker that processes order scoring from Redis queue.
Run with: python -m app.services.worker
"""
import time
import json
import logging
from app.redis_client import RedisClient
from app.config import settings
from app.database import SessionLocal
from app.scoring.signals import OrderPayload
from app.services.scoring_pipeline import ScoringPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QUEUE_NAME = "shieldcommerce:scoring:queue"


def process_queue():
    redis = RedisClient(url=settings.redis_url)
    pipeline = ScoringPipeline()

    logger.info("Worker started. Listening on queue: %s", QUEUE_NAME)

    while True:
        try:
            payload = redis.dequeue(QUEUE_NAME, timeout=5)
            if payload is None:
                continue

            merchant_id = payload.pop("merchant_id")
            order = OrderPayload(**payload)

            db = SessionLocal()
            try:
                result = pipeline.score_order(db, merchant_id, order)
                logger.info("Scored order %s: %s (%s)", order.order_id, result["risk_score"], result["risk_level"])
            except Exception as e:
                logger.error("Failed to score order %s: %s", order.order_id, e)
            finally:
                db.close()

        except KeyboardInterrupt:
            logger.info("Worker shutting down.")
            break
        except Exception as e:
            logger.error("Worker error: %s", e)
            time.sleep(1)


if __name__ == "__main__":
    process_queue()
