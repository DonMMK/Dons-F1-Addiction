"""Public schedule backends only; metadata must never trigger archive login."""

import fastf1

from .loading_errors import SessionDataError


def _public(call, *args, **kwargs):
    failure = None
    for backend in ("fastf1", "ergast"):
        try:
            return call(*args, **kwargs, backend=backend)
        except Exception as exc:
            failure = exc
    raise SessionDataError(
        "schedule_provider_error",
        "The public F1 schedule could not be loaded. Retry shortly.",
        502,
        20,
    ) from failure


def get_session(year, event, kind):
    return _public(fastf1.get_session, year, event, kind)


def get_schedule(year, **kwargs):
    return _public(fastf1.get_event_schedule, year, **kwargs)


def get_event(year, event):
    return _public(fastf1.get_event, year, event)
