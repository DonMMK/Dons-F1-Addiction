"""Typed provider failures; never disguise upstream access errors as missing routes."""

from fastapi import HTTPException


class SessionDataError(HTTPException):
    def __init__(self, code, message, status_code=503, retry_after=None):
        self.code = code
        headers = {"X-F1-Data-Error": code}
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
        super().__init__(status_code=status_code, detail=message, headers=headers)
