import logging
import time
from fastapi import Request


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


async def log_requests(request: Request, call_next):
    logger = logging.getLogger("app.requests")
    start = time.time()
    response = await call_next(request)
    # Emit one structured line per request for easy API latency/status tracing.
    duration_ms = round((time.time() - start) * 1000, 2)
    logger.info("%s %s %s %sms", request.method, request.url.path, response.status_code, duration_ms)
    return response
