from __future__ import annotations

import os
import signal
import time
from typing import Iterable


class BrowserCleanupTimeout(RuntimeError):
    """Raised when Camoufox/Playwright cleanup does not return in time."""


def _proc_ppid(pid: int) -> int | None:
    try:
        with open(f"/proc/{pid}/status", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("PPid:"):
                    return int(line.split()[1])
    except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError):
        return None
    return None


def descendant_pids(root_pid: int | None = None) -> list[int]:
    root = int(root_pid or os.getpid())
    parent_map: dict[int, int] = {}
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        pid = int(name)
        ppid = _proc_ppid(pid)
        if ppid is not None:
            parent_map[pid] = ppid

    descendants: set[int] = set()
    changed = True
    while changed:
        changed = False
        for pid, ppid in parent_map.items():
            if pid == root or pid in descendants:
                continue
            if ppid == root or ppid in descendants:
                descendants.add(pid)
                changed = True
    # Children first makes shutdown a little cleaner for nested helpers.
    return sorted(descendants, reverse=True)


def _signal_many(pids: Iterable[int], sig: int) -> None:
    for pid in pids:
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError):
            pass


def terminate_browser_children(logger, *, term_grace_sec: float = 0.5) -> dict:
    """Terminate all child processes of the runner.

    The container runs one scenario per process, so browser/Xvfb/helper children are
    safe to terminate after an unrecoverable Playwright/Camoufox transport hang.
    """
    pids = descendant_pids()
    if not pids:
        logger.warning("Browser cleanup fallback: no child processes found")
        return {"terminated": [], "killed": []}

    logger.warning("Browser cleanup fallback: terminating child processes %s", pids)
    _signal_many(pids, signal.SIGTERM)
    deadline = time.monotonic() + max(0.0, float(term_grace_sec))
    survivors = list(pids)
    while survivors and time.monotonic() < deadline:
        time.sleep(0.05)
        survivors = [pid for pid in survivors if os.path.exists(f"/proc/{pid}")]

    killed: list[int] = []
    if survivors:
        logger.warning("Browser cleanup fallback: force killing child processes %s", survivors)
        _signal_many(survivors, signal.SIGKILL)
        killed = list(survivors)
    return {"terminated": pids, "killed": killed}


def bounded_manager_exit(manager, exc_info, logger, *, timeout_sec: float = 4.0) -> bool:
    """Call a context manager __exit__ with a hard wall-clock deadline.

    Returns the context manager suppression flag. If cleanup hangs, raises
    BrowserCleanupTimeout so the caller can kill browser child processes and keep
    finalizing the run instead of leaving the container stuck forever.
    """
    exc_type, exc, tb = exc_info
    timeout = max(0.1, float(timeout_sec))

    if not hasattr(signal, "SIGALRM"):
        return bool(manager.__exit__(exc_type, exc, tb))

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)

    def _handler(_signum, _frame):
        raise BrowserCleanupTimeout(
            f"Camoufox cleanup exceeded hard timeout of {timeout:.3f}s"
        )

    signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        return bool(manager.__exit__(exc_type, exc, tb))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])
