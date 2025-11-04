import os
import tempfile
import logging
from logging.handlers import RotatingFileHandler

LOG_DIR = tempfile.gettempdir()
LOG_FILE = os.path.join(LOG_DIR, "plotune_sdk.log")


MAX_LOG_SIZE = 5 * 1024 * 1024  # bytes
BACKUP_COUNT = 1  # bir eski dosya tutulur


def get_logger(name: str = "plotune_sdk", console: bool = True) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # 🔸 File Handler — rotates automatically
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 🔸 Optional Console Handler
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    logger.debug(f"Logger initialized at {LOG_FILE}")
    return logger


if __name__ == "__main__":
    log = get_logger(console=True)
    log.info("Logger initialized")
    log.debug("Debug message test")
    log.warning("Rotation test will trigger after ~5 MB of logs.")
