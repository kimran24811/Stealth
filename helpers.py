def structured_log(message: str, **kwargs) -> None:
    import structlog

    logger = structlog.get_logger()
    logger.info(message, **kwargs)

def filter_headers(headers: dict) -> dict:
    sensitive_headers = ['Authorization', 'Cookie']
    return {k: v for k, v in headers.items() if k not in sensitive_headers}