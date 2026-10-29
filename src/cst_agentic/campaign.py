"""Explicit, durable campaign admission; no provider calls or configuration reads.

SQLite transactions serialize admission across evaluator processes. Settlement
never cancels admitted work. This is process-crash persistence, not protection
against deleting the complete ledger, hostile edits or storage failure.
"""

from __future__ import annotations

import math
import sqlite3
import time
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

REQUEST_LIMIT = 1_600
TOKEN_LIMIT = 500_000
ACTIVE_LIMIT_S = 7_200


class CampaignStopped(Exception):
    """Bounded admission/storage failure; never includes provider data."""


class CampaignLedger:
    def __init__(self, path: Path, identity: str):
        self.path = path.resolve()
        self.identity = identity
        self.clock: Callable[[], float] = time.time
        self._owned: set[int] = set()
        self._active: int | None = None
        self._failed = False

    @classmethod
    def create(cls, path: Path, *, identity: str) -> CampaignLedger:
        if not identity.strip():
            raise CampaignStopped("A frozen campaign identity is required.")
        try:
            # Exclusive creation: never replace or reset a consumed ledger.
            with path.open("xb"):
                pass
            with sqlite3.connect(path) as db:
                db.executescript(
                    "CREATE TABLE campaign (identity TEXT NOT NULL, version INTEGER NOT NULL, "
                    "revision INTEGER NOT NULL DEFAULT 0);"
                    "CREATE TABLE requests (id INTEGER PRIMARY KEY, purpose TEXT NOT NULL, "
                    "settled INTEGER NOT NULL DEFAULT 0, tokens INTEGER, latency REAL);"
                    "CREATE TABLE active (id INTEGER PRIMARY KEY, start REAL NOT NULL, end REAL);"
                    "CREATE TABLE trials (id TEXT PRIMARY KEY);"
                )
                db.execute("INSERT INTO campaign (identity, version) VALUES (?, 1)", (identity,))
        except (OSError, sqlite3.Error):
            raise CampaignStopped(
                "Campaign creation failed; existing ledgers are never reset."
            ) from None
        return cls.open(path, identity=identity)

    @classmethod
    def open(cls, path: Path, *, identity: str) -> CampaignLedger:
        ledger = cls(path, identity)
        with ledger._transaction():
            pass
        return ledger

    @contextmanager
    def _transaction(self):
        if self._failed:
            raise CampaignStopped("Campaign storage previously failed; admission blocked.")
        db = None
        try:
            db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=5)
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT identity, version FROM campaign").fetchall() != [
                (self.identity, 1)
            ]:
                raise CampaignStopped("Campaign identity or version mismatch.")
            yield db
            db.commit()
        except (OSError, sqlite3.Error):
            self._failed = True
            raise CampaignStopped(
                "Campaign storage unavailable or invalid; admission blocked."
            ) from None
        finally:
            if db is not None:
                db.close()

    def _snapshot(self, db: sqlite3.Connection) -> dict[str, Any]:
        requests, tokens, missing, pending = db.execute(
            "SELECT count(*), coalesce(sum(tokens), 0), "
            "coalesce(sum(settled=1 AND tokens IS NULL), 0), "
            "coalesce(sum(settled=0), 0) FROM requests"
        ).fetchone()
        now = self.clock()
        intervals = db.execute("SELECT start, end FROM active").fetchall()
        if not math.isfinite(now) or any(
            (end if end is not None else now) < start for start, end in intervals
        ):
            raise CampaignStopped("Campaign active clock moved backwards; admission blocked.")
        active = sum((end if end is not None else now) - start for start, end in intervals)
        return {
            "requests": requests,
            "reported_tokens": tokens,
            "missing_usage": missing,
            "pending_requests": pending,
            "token_overshoot": max(0, tokens - TOKEN_LIMIT),
            "active_seconds": active,
            "active_overshoot_s": max(0, active - ACTIVE_LIMIT_S),
            "revision_claimed": bool(db.execute("SELECT revision FROM campaign").fetchone()[0]),
            "latency_samples_s": [
                row[0]
                for row in db.execute("SELECT latency FROM requests WHERE settled=1 ORDER BY id")
            ],
            "claimed_trials": [row[0] for row in db.execute("SELECT id FROM trials ORDER BY id")],
        }

    def snapshot(self) -> dict[str, Any]:
        with self._transaction() as db:
            return self._snapshot(db)

    def admit(self, purpose: str) -> int:
        if purpose not in {"probe", "trial", "engineering", "retest"}:
            raise CampaignStopped("Unknown campaign request purpose.")
        with self._transaction() as db:
            state = self._snapshot(db)
            if state["requests"] >= REQUEST_LIMIT:
                raise CampaignStopped("Campaign model-request budget exhausted.")
            if state["reported_tokens"] >= TOKEN_LIMIT:
                raise CampaignStopped("Campaign reported-token budget exhausted.")
            if state["active_seconds"] >= ACTIVE_LIMIT_S:
                raise CampaignStopped("Campaign active-time budget exhausted.")
            pending = {row[0] for row in db.execute("SELECT id FROM requests WHERE settled=0")}
            if pending - self._owned:
                raise CampaignStopped("Campaign has unsettled requests from another evaluator.")
            if (
                purpose == "probe"
                and db.execute("SELECT count(*) FROM requests WHERE purpose='probe'").fetchone()[0]
                >= 16
            ):
                raise CampaignStopped("Campaign endpoint-probe allowance exhausted.")
            if purpose == "retest" and not state["revision_claimed"]:
                raise CampaignStopped("Claim the one permitted revision before retesting.")
            cursor = db.execute("INSERT INTO requests (purpose) VALUES (?)", (purpose,))
            assert cursor.lastrowid is not None
            self._owned.add(cursor.lastrowid)
            return cursor.lastrowid

    def claim_revision(self) -> None:
        with self._transaction() as db:
            if db.execute("UPDATE campaign SET revision=1 WHERE revision=0").rowcount != 1:
                raise CampaignStopped("Campaign prompt revision already consumed.")

    def claim_trial(self, trial_id: str) -> None:
        from .evaluation_pack import trial_schedule

        if trial_id not in {t.id for t in (*trial_schedule(), *trial_schedule(retest=True))}:
            raise CampaignStopped("Trial is outside the frozen campaign.")
        with self._transaction() as db:
            if trial_id.startswith("retest-") and not self._snapshot(db)["revision_claimed"]:
                raise CampaignStopped("Claim the permitted revision before retest trials.")
            if db.execute("SELECT 1 FROM trials WHERE id=?", (trial_id,)).fetchone():
                raise CampaignStopped("Campaign trial already admitted; no replay allowance.")
            db.execute("INSERT INTO trials VALUES (?)", (trial_id,))

    def work_allowed(self) -> bool:
        """Synchronous final admission for newly proposed effects, not cancellation."""
        state = self.snapshot()
        return (
            state["requests"] < REQUEST_LIMIT
            and state["reported_tokens"] < TOKEN_LIMIT
            and state["active_seconds"] < ACTIVE_LIMIT_S
        )

    def begin_active(self) -> int:
        """One active evaluator at a time; never include time waiting at a user prompt."""
        with self._transaction() as db:
            if db.execute("SELECT 1 FROM active WHERE end IS NULL").fetchone():
                raise CampaignStopped("An active interval requires explicit settlement.")
            if self._snapshot(db)["active_seconds"] >= ACTIVE_LIMIT_S:
                raise CampaignStopped("Campaign active-time budget exhausted.")
            cursor = db.execute("INSERT INTO active (start) VALUES (?)", (self.clock(),))
            assert cursor.lastrowid is not None
            self._active = cursor.lastrowid
            return cursor.lastrowid

    @property
    def active(self) -> bool:
        return self._active is not None

    def end_active(self, interval: int) -> None:
        """After a crash, elapsed downtime is conservatively charged, never reset."""
        with self._transaction() as db:
            self._snapshot(db)  # Refuse backwards clock changes before writing.
            if (
                db.execute(
                    "UPDATE active SET end=? WHERE id=? AND end IS NULL", (self.clock(), interval)
                ).rowcount
                != 1
            ):
                raise CampaignStopped("Active interval missing or already settled.")
        if self._active == interval:
            self._active = None

    def settle(self, request: int, *, total_tokens: int | None, latency_s: float) -> None:
        if (
            (total_tokens is not None and (type(total_tokens) is not int or total_tokens < 0))
            or not math.isfinite(latency_s)
            or latency_s < 0
        ):
            raise CampaignStopped("Invalid reported usage or latency.")
        with self._transaction() as db:
            changed = db.execute(
                "UPDATE requests SET settled=1, tokens=?, latency=? WHERE id=? AND settled=0",
                (total_tokens, latency_s, request),
            ).rowcount
            if changed != 1:
                raise CampaignStopped("Request missing or already settled.")
