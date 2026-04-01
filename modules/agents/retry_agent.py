def should_retry(output: str) -> bool:
    return "[ERROR]" in output or "Traceback" in output
