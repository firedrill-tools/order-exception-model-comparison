"""Read-only complete study snapshot; the oracle never becomes model input."""

import os
import base64
import stat
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from .schema import OrderCase, Expectation
from .native import strict_json, DEFAULT_URLS
from .evidence import sha


class SourceChanged(RuntimeError):
    pass


def read_document(path, maximum, *, capture_bytes=False):
    path = Path(os.path.abspath(path))
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
        raise ValueError("study source requires a bounded regular file")
    raw = path.read_bytes()
    after = path.lstat()
    if len(raw) > maximum or (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise SourceChanged("study source changed during read")
    return strict_json(raw), {
        "path": str(path),
        "sha256": sha(raw),
        "device": after.st_dev,
        "inode": after.st_ino,
        "bytes": len(raw),
        **(
            {"original_bytes_base64": base64.b64encode(raw).decode()}
            if capture_bytes
            else {}
        ),
    }


def validate_models(models):
    if not models or len(models) > 8 or len(set(models)) != len(models):
        raise ValueError("1–8 unique model configurations are required")
    for value in models:
        if (
            not isinstance(value, str)
            or ":" not in value
            or value.split(":", 1)[0] not in DEFAULT_URLS
            or not value.split(":", 1)[1]
            or len(value) > 200
            or any(c.isspace() for c in value)
        ):
            raise ValueError(
                "explicit openai:, anthropic: or google: models are required"
            )
    return tuple(models)


@dataclass(frozen=True)
class Study:
    cases: tuple
    expectations: object
    sources: tuple = ()

    @classmethod
    def create(cls, cases, expectations, sources=()):
        cases = tuple(
            OrderCase.model_validate(row).model_copy(deep=True) for row in cases
        )
        if not 1 <= len(cases) <= 64 or len({row.case_id for row in cases}) != len(
            cases
        ):
            raise ValueError("study requires1–64 unique business cases")
        if not isinstance(expectations, dict) or set(expectations) != {
            row.case_id for row in cases
        }:
            raise ValueError("exactly one external expectation per case is required")
        oracle = MappingProxyType(
            {
                key: Expectation.model_validate(value)
                for key, value in expectations.items()
            }
        )
        return cls(cases, oracle, tuple(dict(source) for source in sources))

    @classmethod
    def from_files(cls, cases_path, expectations_path):
        cases, left = read_document(cases_path, 1048576, capture_bytes=True)
        expected, right = read_document(expectations_path, 262144, capture_bytes=True)
        if not isinstance(cases, list):
            raise ValueError("study case source requires a JSON array")
        return cls.create(cases, expected, (left, right))

    def guard(self):
        for original in self.sources:
            try:
                _, current = read_document(original["path"], 1048576)
            except Exception as error:
                raise SourceChanged(
                    "study source became unavailable or invalid"
                ) from error
            if any(
                current[key] != original[key] for key in ("sha256", "device", "inode")
            ):
                raise SourceChanged(
                    "original cases or external expectations changed during comparison"
                )

    def public(self):
        return {
            "case_order": [row.case_id for row in self.cases],
            "cases_sha256": sha([row.model_dump(mode="json") for row in self.cases]),
            "expectations_sha256": sha(
                {key: value.model_dump() for key, value in self.expectations.items()}
            ),
            "sources": [
                {
                    key: value
                    for key, value in source.items()
                    if key != "original_bytes_base64"
                }
                for source in self.sources
            ],
        }
