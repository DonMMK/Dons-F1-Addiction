"""FastF1 3.9 archive access, non-interactive auth and cache preservation.

FastF1 owns login and tokens. The small internal-auth bridge is isolated here
because FastF1 does not yet expose a public non-interactive server API.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import logging
import os
import shutil
import threading

import fastf1
from packaging.version import Version, InvalidVersion

from .loading_errors import SessionDataError

MIN_VERSION = "3.9.2"
LOGIN_COMMAND = "python -m fastf1 auth f1tv --authenticate"
CACHE_ONLY = ContextVar("f1_archive_cache_only", default=False)
LOG = logging.getLogger(__name__)
AUTH_LOCK = threading.RLock()
_TOKEN_STAMP = None


def check_version():
    try:
        supported = Version(fastf1.__version__) >= Version(MIN_VERSION)
    except InvalidVersion:
        supported = False
    if not supported:
        raise SessionDataError(
            "fastf1_upgrade_required",
            f"FastF1 {fastf1.__version__} cannot load the current timing archive correctly. Install backend/requirements.txt (FastF1 >= {MIN_VERSION}) and restart the backend.",
        )


def configure_cache(root, data_dir):
    configured = os.environ.get("F1_CACHE_DIR")
    candidates = [
        data_dir / "fastf1",
        root / "f1_cache",
        root / "formula1-prediction" / "f1_cache",
        root / "formula1-ghost-car" / ".fastf1_cache",
        root / "formula1-best-car" / "cache",
    ]
    populated = (
        lambda path: path.is_dir() and next(path.rglob("*.ff1pkl"), None) is not None
    )
    target = (
        Path(configured).expanduser().resolve()
        if configured
        else next((p for p in candidates if populated(p)), candidates[0])
    )
    target.mkdir(parents=True, exist_ok=True)
    # Preserve all existing parsed caches. Never overwrite, delete or ignore versions.
    for old in candidates:
        if not old.is_dir() or old.resolve() == target.resolve():
            continue
        for source in old.rglob("*.ff1pkl"):
            if source.is_symlink() or target.resolve() in source.resolve().parents:
                continue
            dest = target / source.relative_to(old)
            if dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                with source.open("rb") as src, dest.open("xb") as out:
                    shutil.copyfileobj(src, out)
            except FileExistsError:
                pass
    if hasattr(fastf1.Cache, "configure"):
        fastf1.Cache.configure(cache_dir=str(target))
    else:
        fastf1.Cache.enable_cache(str(target))
    return target


def has_cached_timing(session, directory):
    """Avoid running every parser against an entirely cold cache."""
    path = getattr(session, "api_path", "")
    if not path.startswith("/static/"):
        return False
    parsed = directory / path.removeprefix("/static/") / "_extended_timing_data.ff1pkl"
    if parsed.is_file():
        return True
    # Cache 3.9 exposes no public cache-only existence query. Use the underlying
    # requests-cache's public contains() API without making a network request.
    client = getattr(fastf1.Cache, "_requests_session_cached", None)
    if client is not None:
        try:
            return any(
                client.cache.contains(url=f"{host}{path}TimingData.jsonStream")
                for host in (
                    "https://livetiming.formula1.com",
                    "https://livetiming-mirror.fastf1.dev",
                )
            )
        except Exception:
            return False
    return False


def _auth_module():
    from fastf1.internals import f1account

    if not hasattr(f1account.token_manager, "get_stored"):
        raise SessionDataError(
            "auth_integration_unavailable",
            "FastF1 authentication interface changed. Install the supported version from backend/requirements.txt.",
        )
    return f1account


def auth_status():
    """Status only. Never return credentials, claims, JWTs or account details."""
    try:
        module = _auth_module()
        global _TOKEN_STAMP
        manager = module.token_manager
        path = getattr(manager, "_token_path", None)
        if path is not None:
            try:
                info = path.stat()
                stamp = (info.st_mtime_ns, info.st_size)
            except OSError:
                stamp = None
            with AUTH_LOCK:
                if stamp != _TOKEN_STAMP:
                    manager._token = None
                    _TOKEN_STAMP = stamp
        token = manager.get_stored()
        return {
            "authenticated": token is not None and token.is_valid(),
            "credentialsConfigured": bool(
                os.environ.get("F1_USERNAME") and os.environ.get("F1_PASSWORD")
            ),
            "loginCommand": LOGIN_COMMAND,
        }
    except (ImportError, AttributeError, SessionDataError):
        return {
            "authenticated": False,
            "credentialsConfigured": False,
            "loginCommand": LOGIN_COMMAND,
        }


def install_server_policy():
    # The flag is local to this execution context. Other threads' standings and
    # calendar requests are not temporarily switched into offline mode.
    if not getattr(fastf1.Cache.requests_get, "_dashboard_policy", False):
        original = fastf1.Cache.requests_get

        def scoped_get(cls, url, **kwargs):
            if CACHE_ONLY.get():
                kwargs["only_if_cached"] = True
            kwargs.setdefault("timeout", (5, 20))
            return original(url, **kwargs)

        scoped_get._dashboard_policy = True
        fastf1.Cache.requests_get = classmethod(scoped_get)
    try:
        module = _auth_module()
    except (ImportError, SessionDataError):
        return

    def server_login():
        from fastf1.exceptions import F1AuthError

        if (
            module.get_auth_method() == "password"
            and os.environ.get("F1_USERNAME")
            and os.environ.get("F1_PASSWORD")
        ):
            from fastf1.internals.f1account.login import default_login

            return default_login()
        raise F1AuthError(
            f"Backend requests do not prompt for credentials. Run {LOGIN_COMMAND} in a terminal, then retry."
        )

    module.token_manager._default_auth_func = server_login


@contextmanager
def cache_only():
    token = CACHE_ONLY.set(True)
    try:
        yield
    finally:
        CACHE_ONLY.reset(token)


def ensure_authenticated():
    check_version()
    state = auth_status()
    if state["authenticated"]:
        return
    if state["credentialsConfigured"]:
        module = _auth_module()
        with AUTH_LOCK:
            try:
                module.token_manager.get()
                return
            except Exception as exc:
                # Do not expose OAuth response bodies or credentials in API errors.
                raise SessionDataError(
                    "archive_auth_failed",
                    f"F1TV sign-in failed. Authenticate in a terminal with {LOGIN_COMMAND}; an active Access/Pro/Premium subscription is required.",
                ) from exc
    raise SessionDataError(
        "archive_auth_required",
        f"Uncached F1 lap timing, weather and telemetry require F1TV authentication. Run {LOGIN_COMMAND} with an active Access/Pro/Premium account, then retry. Standings and published qualifying/race results remain available without this login.",
    )


def probe_archive(session):
    """Probe one real archive resource using FastF1's authenticated transport."""
    url = f"https://livetiming.formula1.com{session.api_path}SessionInfo.jsonStream"
    try:
        response = fastf1.Cache.requests_get(url, timeout=(5, 15))
    except Exception as exc:
        raise SessionDataError(
            "archive_network_error",
            "The F1 timing archive could not be reached. Check the backend network connection and retry.",
            502,
            15,
        ) from exc
    code = response.status_code
    if code == 401:
        raise SessionDataError(
            "archive_auth_rejected",
            f"The F1 archive rejected authentication. Run {LOGIN_COMMAND} again and verify the account subscription.",
        )
    if code == 403:
        raise SessionDataError(
            "archive_access_denied",
            "The F1 archive refused access (HTTP 403). Verify the F1TV account entitlement and network access to livetiming.formula1.com.",
        )
    if code == 404:
        raise SessionDataError(
            "session_not_published",
            "This session's archive data is not published at the expected path yet. Retry later.",
            425,
            60,
        )
    if code == 429:
        raise SessionDataError(
            "archive_rate_limited",
            "The F1 timing provider is rate limiting requests. Retry shortly.",
            503,
            60,
        )
    if code != 200:
        raise SessionDataError(
            "archive_upstream_error",
            f"The F1 archive returned HTTP {code}; retry later.",
            502,
            30,
        )
