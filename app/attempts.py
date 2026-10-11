"""Wrong admin passwords, per client address: in standalone or Docker mode the settings
are open to the whole network, so guessing the password is slowed down. After FREE
failures in a row, each further one locks the address out for twice as long as the
previous (1 s, 2 s, 4 s… up to LONGEST); the right password clears its count. In
memory only: a few addresses on a home network."""

import math
import threading
import time
from collections.abc import Callable

FREE = 5
FIRST = 1.0  # seconds
LONGEST = 15 * 60.0
MAX_ADDRESSES = 10_000  # beyond, the oldest entries are forgotten (bounded memory)


class Attempts:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self._lock = threading.Lock()
        self._failures: dict[str, tuple[int, float]] = {}  # address → (failures, locked until)

    def wait(self, address: str) -> int:
        """Seconds before this address may try again (0: now)."""
        with self._lock:
            _, until = self._failures.get(address, (0, 0.0))
        return max(0, math.ceil(until - self.clock()))

    def failed(self, address: str) -> None:
        with self._lock:
            count = self._failures.pop(address, (0, 0.0))[0] + 1
            delay = 0.0 if count <= FREE else min(FIRST * 2 ** (count - FREE - 1), LONGEST)
            self._failures[address] = (count, self.clock() + delay)
            while len(self._failures) > MAX_ADDRESSES:
                del self._failures[next(iter(self._failures))]

    def succeeded(self, address: str) -> None:
        with self._lock:
            self._failures.pop(address, None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()
