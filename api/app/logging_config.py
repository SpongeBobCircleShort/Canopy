import logging


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s level=%(levelname)s logger=%(name)s %(message)s",
        force=True,
    )
