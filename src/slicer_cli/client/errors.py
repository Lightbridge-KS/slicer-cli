"""Error types and stable codes shared by the client and the CLI.

Single source of truth for the `E_*` strings and their exit-code mapping
(PRD §6.4 and §6.5). Every CLI command surfaces failures as a SlicerError
or one of its subclasses; the root CLI maps `error.code` -> exit code.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Stable error codes. Names are part of the public contract — never rename."""

    E_NOT_RUNNING = "E_NOT_RUNNING"
    E_NETWORK = "E_NETWORK"
    E_HTTP_4XX = "E_HTTP_4XX"
    E_HTTP_5XX = "E_HTTP_5XX"
    E_EMPTY_SELECTOR = "E_EMPTY_SELECTOR"
    E_DESTRUCTIVE = "E_DESTRUCTIVE"
    E_EXEC_DISABLED = "E_EXEC_DISABLED"
    E_BAD_INPUT = "E_BAD_INPUT"
    E_BAD_RESPONSE = "E_BAD_RESPONSE"
    E_TIMEOUT = "E_TIMEOUT"
    E_CONFIG = "E_CONFIG"
    E_NOT_IMPLEMENTED = "E_NOT_IMPLEMENTED"


_EXIT_CODES: dict[ErrorCode, int] = {
    ErrorCode.E_BAD_INPUT: 1,
    ErrorCode.E_HTTP_4XX: 2,
    ErrorCode.E_HTTP_5XX: 2,
    ErrorCode.E_BAD_RESPONSE: 2,
    ErrorCode.E_NOT_RUNNING: 3,
    ErrorCode.E_NETWORK: 3,
    ErrorCode.E_TIMEOUT: 3,
    ErrorCode.E_CONFIG: 4,
    ErrorCode.E_EXEC_DISABLED: 5,
    ErrorCode.E_DESTRUCTIVE: 6,
    ErrorCode.E_EMPTY_SELECTOR: 6,
    ErrorCode.E_NOT_IMPLEMENTED: 7,
}


def exit_code_for(code: ErrorCode) -> int:
    """Map an ErrorCode to its CLI exit code (PRD §6.5)."""
    return _EXIT_CODES.get(code, 10)


class SlicerError(Exception):
    """Base class for everything raised by the client / CLI.

    Attributes:
      code: stable ErrorCode string
      message: human-friendly description
      hint: optional remediation pointer; surfaced verbatim to humans/agents
      endpoint: HTTP path involved, if any
      http_status: HTTP status code if Slicer returned one
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        hint: str | None = None,
        endpoint: str | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.endpoint = endpoint
        self.http_status = http_status

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the JSON envelope's `error` payload (PRD §6.3)."""
        return {
            "code": str(self.code),
            "message": self.message,
            "hint": self.hint,
            "endpoint": self.endpoint,
            "http_status": self.http_status,
        }


class SlicerNotRunningError(SlicerError):
    def __init__(self, url: str) -> None:
        super().__init__(
            ErrorCode.E_NOT_RUNNING,
            f"Could not reach Slicer at {url}",
            hint=(
                "Open 3D Slicer, switch to the 'Web Server' module under "
                "Developer Tools, and click 'Start server'. Then re-run."
            ),
            endpoint="/slicer/system/version",
        )


class SlicerNetworkError(SlicerError):
    def __init__(self, message: str, *, endpoint: str | None = None) -> None:
        super().__init__(ErrorCode.E_NETWORK, message, endpoint=endpoint)


class SlicerTimeoutError(SlicerError):
    def __init__(self, seconds: float, *, endpoint: str | None = None) -> None:
        super().__init__(
            ErrorCode.E_TIMEOUT,
            f"Slicer did not respond within {seconds:g}s",
            hint="Increase --timeout or check that Slicer's event loop is not blocked",
            endpoint=endpoint,
        )


class SlicerHttpError(SlicerError):
    def __init__(
        self,
        status: int,
        message: str,
        *,
        endpoint: str | None = None,
    ) -> None:
        code = ErrorCode.E_HTTP_4XX if 400 <= status < 500 else ErrorCode.E_HTTP_5XX
        super().__init__(code, message, endpoint=endpoint, http_status=status)


class SlicerBadResponseError(SlicerError):
    _DEFAULT_HINT = "The response did not match the expected schema. File a bug if reproducible."

    def __init__(
        self,
        message: str,
        *,
        endpoint: str | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(
            ErrorCode.E_BAD_RESPONSE,
            message,
            hint=hint if hint is not None else self._DEFAULT_HINT,
            endpoint=endpoint,
        )


class SlicerNotImplementedError(SlicerError):
    def __init__(self, what: str, *, phase: str | None = None) -> None:
        hint = f"Implemented in {phase}" if phase else None
        super().__init__(
            ErrorCode.E_NOT_IMPLEMENTED,
            f"{what} is not implemented yet",
            hint=hint,
        )


class SlicerBadInputError(SlicerError):
    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(ErrorCode.E_BAD_INPUT, message, hint=hint)


class SlicerEmptySelectorError(SlicerError):
    """Raised when a destructive /mrml call would have empty selectors."""

    def __init__(self) -> None:
        super().__init__(
            ErrorCode.E_EMPTY_SELECTOR,
            "Refusing to send destructive call with no selectors",
            hint=(
                "Empty selectors on DELETE /slicer/mrml clear the entire scene. "
                "Pass --id, --class, or --name; or use `slicer-cli scene clear --confirm`."
            ),
        )


class SlicerDestructiveError(SlicerError):
    """Raised when a destructive op is attempted without --confirm."""

    def __init__(self, op: str, *, confirm_flag: str = "--confirm") -> None:
        super().__init__(
            ErrorCode.E_DESTRUCTIVE,
            f"{op} is destructive",
            hint=f"Pass {confirm_flag} to proceed.",
        )


class SlicerExecDisabledError(SlicerError):
    """Raised when /slicer/exec is gated off (config.exec.enabled = false)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorCode.E_EXEC_DISABLED,
            "exec is disabled by configuration",
            hint=(
                "Pass --i-understand-the-risk per call, or run "
                "`slicer-cli config set exec.enabled true`."
            ),
        )


class SlicerConfigError(SlicerError):
    def __init__(self, message: str) -> None:
        super().__init__(ErrorCode.E_CONFIG, message)
