"""Reliable HTTP transport for the Aaditech UFO agent.

Wraps ``requests.post`` with:
  * Exponential-backoff retries for transient failures (5xx, timeouts, conn errors).
  * A persistent SQLite outbox so payloads survive process restarts and outages.
  * Bounded queue size (oldest entries drop first) to avoid unbounded growth.

Designed to be safe to call from any thread; one ``AgentTransport`` instance per
process is enough.
"""

from __future__ import annotations

import json as _json
import logging
import os
import random
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Any, Iterable

import requests

logger = logging.getLogger('aaditech-agent.transport')


_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


@dataclass
class TransportResult:
    success: bool
    queued: bool
    status_code: int | None
    drained: int
    error: str | None = None


class AgentTransport:
    """HTTP poster with retry + persistent SQLite outbox."""

    def __init__(
        self,
        db_path: str,
        *,
        max_queue: int = 5000,
        max_attempts_per_call: int = 3,
        backoff_base_seconds: float = 0.5,
        backoff_cap_seconds: float = 30.0,
        drain_batch: int = 25,
    ) -> None:
        self._db_path = db_path
        self._max_queue = max(1, int(max_queue))
        self._max_attempts = max(1, int(max_attempts_per_call))
        self._backoff_base = max(0.05, float(backoff_base_seconds))
        self._backoff_cap = max(self._backoff_base, float(backoff_cap_seconds))
        self._drain_batch = max(1, int(drain_batch))
        self._lock = threading.Lock()
        self._ensure_dir()
        self._init_schema()

    def _ensure_dir(self) -> None:
        directory = os.path.dirname(os.path.abspath(self._db_path))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10, isolation_level=None)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                '''CREATE TABLE IF NOT EXISTS outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    method TEXT NOT NULL DEFAULT 'POST',
                    payload TEXT NOT NULL,
                    headers TEXT NOT NULL,
                    timeout REAL NOT NULL,
                    enqueued_at REAL NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_retry_at REAL NOT NULL DEFAULT 0
                )'''
            )

    # ---- public API -----------------------------------------------------

    def post(
        self,
        url: str,
        *,
        json: Any = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> TransportResult:
        """Drain pending entries, then attempt this request.

        Returns ``TransportResult``. The current request is enqueued for later
        when transient failures persist after retries.
        """
        drained = self._drain_once()

        attempt_result = self._attempt(
            url=url,
            payload=json,
            headers=headers or {},
            timeout=timeout,
            max_attempts=self._max_attempts,
        )

        if attempt_result.success:
            return TransportResult(True, False, attempt_result.status_code, drained)

        if attempt_result.permanent:
            logger.warning(
                'Permanent failure for %s (status=%s). Dropping payload.',
                url,
                attempt_result.status_code,
            )
            return TransportResult(False, False, attempt_result.status_code, drained, attempt_result.error)

        self._enqueue(url, json, headers or {}, timeout)
        return TransportResult(False, True, attempt_result.status_code, drained, attempt_result.error)

    def queue_size(self) -> int:
        with self._connect() as conn:
            row = conn.execute('SELECT COUNT(*) FROM outbox').fetchone()
            return int(row[0]) if row else 0

    def clear_queue(self) -> int:
        with self._connect() as conn:
            cur = conn.execute('DELETE FROM outbox')
            return cur.rowcount or 0

    # ---- internals ------------------------------------------------------

    def _attempt(
        self,
        *,
        url: str,
        payload: Any,
        headers: dict[str, str],
        timeout: float,
        max_attempts: int,
    ) -> '_AttemptOutcome':
        last_error: str | None = None
        last_status: int | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=timeout)
                last_status = response.status_code
                if response.status_code < 400:
                    return _AttemptOutcome(success=True, status_code=response.status_code)
                if response.status_code in _RETRYABLE_STATUS:
                    last_error = f'HTTP {response.status_code}: {response.text[:200]}'
                    self._sleep_backoff(attempt)
                    continue
                # Non-retryable 4xx -> permanent failure, do not enqueue.
                return _AttemptOutcome(
                    success=False,
                    status_code=response.status_code,
                    error=f'HTTP {response.status_code}: {response.text[:200]}',
                    permanent=True,
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = f'{type(exc).__name__}: {exc}'
                self._sleep_backoff(attempt)
            except requests.RequestException as exc:
                last_error = f'{type(exc).__name__}: {exc}'
                self._sleep_backoff(attempt)

        return _AttemptOutcome(success=False, status_code=last_status, error=last_error, permanent=False)

    def _sleep_backoff(self, attempt: int) -> None:
        delay = min(self._backoff_cap, self._backoff_base * (2 ** (attempt - 1)))
        delay += random.uniform(0, delay * 0.25)  # jitter
        time.sleep(delay)

    def _enqueue(self, url: str, payload: Any, headers: dict[str, str], timeout: float) -> None:
        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute(
                'INSERT INTO outbox (url, method, payload, headers, timeout, enqueued_at, attempts, next_retry_at)'
                ' VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    url,
                    'POST',
                    _json.dumps(payload, default=str),
                    _json.dumps(headers),
                    float(timeout),
                    now,
                    0,
                    now,
                ),
            )
            # Trim oldest entries past the cap.
            count_row = conn.execute('SELECT COUNT(*) FROM outbox').fetchone()
            count = int(count_row[0]) if count_row else 0
            if count > self._max_queue:
                overflow = count - self._max_queue
                conn.execute(
                    'DELETE FROM outbox WHERE id IN ('
                    'SELECT id FROM outbox ORDER BY id ASC LIMIT ?)',
                    (overflow,),
                )
                logger.warning('Outbox over capacity; dropped %s oldest entries.', overflow)

    def _drain_once(self) -> int:
        """Send up to ``drain_batch`` ready entries. Returns count successfully sent."""
        now = time.time()
        sent = 0
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                'SELECT id, url, payload, headers, timeout, attempts FROM outbox'
                ' WHERE next_retry_at <= ? ORDER BY id ASC LIMIT ?',
                (now, self._drain_batch),
            ).fetchall()

            for row_id, url, payload_json, headers_json, timeout, attempts in rows:
                try:
                    payload = _json.loads(payload_json)
                    headers = _json.loads(headers_json)
                except Exception:
                    conn.execute('DELETE FROM outbox WHERE id = ?', (row_id,))
                    continue

                outcome = self._attempt(
                    url=url,
                    payload=payload,
                    headers=headers,
                    timeout=float(timeout),
                    max_attempts=1,  # one quick try while draining
                )

                if outcome.success:
                    conn.execute('DELETE FROM outbox WHERE id = ?', (row_id,))
                    sent += 1
                elif outcome.permanent:
                    logger.warning(
                        'Dropping queued payload for %s after permanent error %s.',
                        url,
                        outcome.error,
                    )
                    conn.execute('DELETE FROM outbox WHERE id = ?', (row_id,))
                else:
                    new_attempts = attempts + 1
                    delay = min(self._backoff_cap, self._backoff_base * (2 ** new_attempts))
                    conn.execute(
                        'UPDATE outbox SET attempts = ?, next_retry_at = ? WHERE id = ?',
                        (new_attempts, time.time() + delay, row_id),
                    )
        return sent


@dataclass
class _AttemptOutcome:
    success: bool
    status_code: int | None = None
    error: str | None = None
    permanent: bool = False


def default_state_path(state_dir: str | None, frozen_executable: str | None = None) -> str:
    """Derive a sensible default location for the SQLite outbox.

    Mirrors the convention used by ``log_forwarder.py``.
    """
    if state_dir:
        base = state_dir
    elif frozen_executable:
        base = os.path.dirname(os.path.abspath(frozen_executable))
    else:
        base = os.path.join(os.path.expanduser('~'), '.aaditech-agent')
    if not os.path.isdir(base):
        os.makedirs(base, exist_ok=True)
    return os.path.join(base, 'outbox.sqlite3')


def collect_attempts(transport: AgentTransport) -> Iterable[dict[str, Any]]:
    """Debug helper: dump current queue contents (used by tests)."""
    with transport._connect() as conn:  # noqa: SLF001 - intentional for tests
        rows = conn.execute(
            'SELECT id, url, payload, attempts, next_retry_at FROM outbox ORDER BY id ASC'
        ).fetchall()
    for row_id, url, payload_json, attempts, next_retry in rows:
        yield {
            'id': row_id,
            'url': url,
            'payload': _json.loads(payload_json),
            'attempts': attempts,
            'next_retry_at': next_retry,
        }
