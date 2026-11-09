"""nflreadpy with retries.

Use `import nflsafe as nfl` in place of `import nflreadpy as nfl`. Every
`load_*` function is the nflreadpy one, retried on network errors.

Why: on November 8, 2026, GitHub returned 504 Gateway Time-out and read
timeouts on nflverse release downloads for about two hours (runs #561 to
#563). nflreadpy raises ConnectionError on those, and one failed download
ended the whole run.

Only network errors are retried (OSError covers ConnectionError, timeouts,
and requests' exceptions). Anything else, such as a missing column, fails
on the first try as before.
"""
from __future__ import annotations

import functools
import time

import nflreadpy as _nfl

# Seconds to wait before the 2nd and 3rd tries. Three tries cost at most a
# minute of waiting on top of the downloads themselves.
WAITS = (15, 45)
_sleep = time.sleep  # tests replace this


def retry(fn, waits=None):
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        plan = WAITS if waits is None else waits
        for attempt in range(len(plan) + 1):
            try:
                return fn(*args, **kwargs)
            except OSError as e:
                if attempt == len(plan):
                    raise
                print(f"[retry] {fn.__name__} try {attempt + 1} failed ({e}); "
                      f"retrying in {plan[attempt]} s", flush=True)
                _sleep(plan[attempt])
    return wrapped


def __getattr__(name):
    attr = getattr(_nfl, name)
    return retry(attr) if name.startswith("load_") and callable(attr) else attr
