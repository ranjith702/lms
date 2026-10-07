class ServiceError(Exception):
    """A business-rule violation. main.py turns it into an HTTP response."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
