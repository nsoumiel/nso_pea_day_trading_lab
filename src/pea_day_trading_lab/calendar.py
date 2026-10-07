from datetime import timedelta
from .models import timestamp, STEP


class Calendar:
    def __init__(self, sessions):
        self.sessions = sessions  # ISO day -> (UTC opening, UTC continuous close)

    def bounds(self, t):
        from zoneinfo import ZoneInfo
        day = t.astimezone(ZoneInfo('Europe/Paris')).date().isoformat()
        return self.sessions.get(day)

    def slot(self, t):
        bounds = self.bounds(t)
        if not bounds or not bounds[0] <= t < bounds[1]:
            return None
        return int((t - bounds[0]) / STEP)

    def deadlines(self, t, config):
        opening, close = self.bounds(t)
        return (close - timedelta(minutes=config.no_entry_before_close_minutes),
                close - timedelta(minutes=config.exit_before_close_minutes))


def xpar_sessions(start, end):
    import exchange_calendars as xc
    cal = xc.get_calendar('XPAR', start=start, end=end)
    result = {}
    for day in cal.sessions_in_range(start, end):
        result[str(day.date())] = (cal.session_open(day).to_pydatetime(),
                                  cal.session_close(day).to_pydatetime())
    return result
