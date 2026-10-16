"""Private case/configuration attempt evidence with sticky recording authority."""

import asyncio
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(value):
    return hashlib.sha256(
        value
        if isinstance(value, bytes)
        else json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


class Receipt:
    sha = staticmethod(sha)

    def __init__(
        self, case, model, policy, output_root, timeout, writer=None, source_guard=None
    ):
        self.deadline = time.monotonic() + timeout
        self.writer = writer
        self.recording_error = None
        self.native_failure = None
        self.source_guard = source_guard
        root = Path(output_root or ".runs")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory = root / str(uuid.uuid4())
        directory.mkdir(mode=0o700)
        self.path = directory / "trace.json"
        self.data = {
            "schema_version": 1,
            "run_id": directory.name,
            "started_at": now(),
            "status": "prepared",
            "model": model,
            "configuration": None,
            "case": case.model_dump(mode="json"),
            "case_sha256": sha(case.model_dump(mode="json")),
            "policy_sha256": sha(policy.encode()),
            "native": [],
            "tool_attempts": [],
            "successful_reads": [],
            "sdk_messages": [],
            "sdk_usage": None,
            "native_clients_closed": False,
            "proposal": None,
            "error": None,
            "cost_usd": None,
        }

    def guard(self):
        try:
            task = asyncio.current_task()
        except RuntimeError:
            task = None
        if task is not None and task.cancelling():
            raise asyncio.CancelledError("comparison cancellation requested")
        if self.recording_error:
            raise self.recording_error
        if self.native_failure:
            raise RuntimeError("prior native boundary failed") from self.native_failure
        if time.monotonic() >= self.deadline:
            raise TimeoutError("case operation deadline exceeded")
        if self.source_guard:
            self.source_guard()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError("comparison cancellation requested")
        if time.monotonic() >= self.deadline:
            raise TimeoutError("operation deadline exceeded after source check")

    def save(self, final=False):
        if self.recording_error and not final:
            raise self.recording_error
        staged = self.path.with_name("." + str(uuid.uuid4()) + ".tmp")
        try:
            value = json.loads(json.dumps(self.data, allow_nan=False))
            if self.writer is not None:
                self.writer(self.path, value)
                return
            with staged.open("xb") as file:
                os.chmod(staged, 0o600)
                file.write(
                    (
                        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
                        + "\n"
                    ).encode()
                )
                file.flush()
                os.fsync(file.fileno())
            os.replace(staged, self.path)
            fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except BaseException as error:
            self.recording_error = error
            raise
        finally:
            staged.unlink(missing_ok=True)

    def finish(self, proposal, failure):
        self.data.update(
            status="failed" if failure else "completed",
            finished_at=now(),
            proposal=proposal.model_dump(mode="json")
            if proposal is not None and failure is None
            else None,
        )
        if failure:
            for item in self.data["native"]:
                if item["status"] in {"prepared", "received"}:
                    item.update(
                        status="failed",
                        error={"name": type(failure).__name__, "message": str(failure)},
                    )
            chain = []
            seen = set()
            current = failure
            while current is not None and id(current) not in seen and len(chain) < 5:
                seen.add(id(current))
                chain.append(
                    {
                        "name": type(current).__name__,
                        "message": str(current),
                        "status_code": getattr(current, "status_code", None),
                    }
                )
                current = current.__cause__ or current.__context__
            self.data["error"] = {
                "name": type(failure).__name__,
                "message": str(failure),
                "causes": chain,
            }
        self.save(final=True)
