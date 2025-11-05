"""
Logging formatters configuration.

Provides environment-specific log formatting for:
- Detailed multi-line format (development)
- Simple format (test)
- JSON format (production, observability)
- Colored format (development console)
"""


def get_formatters(environment):
    """
    Get formatters based on environment.

    Returns:
        Dictionary of logging formatter configurations
    """
    formatters = {
        "detailed": {
            "format": "%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "simple": {
            "format": "%(levelname)s | %(name)s | %(message)s"
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(funcName)s %(lineno)d %(message)s"
        }
    }

    if environment == 'development':
        formatters["colored"] = {
            "()": "colorlog.ColoredFormatter",
            "format": "%(log_color)s%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            "datefmt": "%H:%M:%S"
        }

    return formatters
