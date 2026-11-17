"""Independent research and paper-trading infrastructure."""

import logging as _logging

# httpx logs full request URLs at INFO; some carry API keys.
_logging.getLogger("httpx").setLevel(_logging.WARNING)
_logging.getLogger("httpcore").setLevel(_logging.WARNING)
