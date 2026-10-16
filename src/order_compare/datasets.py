"""Hash-bound study populations and exclusive private model-free workspaces."""

import json
import os
import re
import stat
import uuid
from importlib.resources import files
from pathlib import Path
from ._dataset_manifest import INDEX_SHA256
from .fixture_source import validate_bundle
from .source import Study
from .native import strict_json
from .evidence import sha, now

DATASET = "order-comparison-studies"
VERSION = "1.0.0"


def encoded(value):
    return (
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()


def data_root():
    installed = files("order_compare").joinpath("sample_data")
    return (
        installed
        if installed.is_dir()
        else Path(__file__).resolve().parents[2] / "data"
    )


def original_paths():
    installed = files("order_compare").joinpath("original_data")
    if installed.is_dir():
        return Path(str(installed.joinpath("cases.json"))), Path(
            str(installed.joinpath("expected.json"))
        )
    root = Path(__file__).resolve().parents[2]
    return root / "fixtures/cases.json", root / "grader/expected.json"


def read_data(root, name, maximum):
    if not re.fullmatch("[a-z0-9-]+[.]json", name):
        raise ValueError("invalid dataset filename")
    raw = root.joinpath(name).read_bytes()
    if len(raw) > maximum:
        raise ValueError("dataset exceeds supported retained bytes")
    return raw


def index(root=None):
    raw = read_data(root or data_root(), "index.json", 65536)
    if sha(raw) != INDEX_SHA256:
        raise ValueError("dataset index hash differs from source authority")
    value = strict_json(raw)
    if (
        value.get("schema_version") != 1
        or value.get("dataset") != DATASET
        or value.get("version") != VERSION
        or not isinstance(value.get("cases"), list)
        or not 1 <= len(value["cases"]) <= 100
    ):
        raise ValueError("unsupported dataset index")
    return value


def load_case(identifier, root=None):
    root = root or data_root()
    manifest = index(root)
    entry = next(
        (row for row in manifest["cases"] if row["case_id"] == identifier), None
    )
    if entry is None:
        raise ValueError("unknown order study population")
    raw = read_data(root, entry["file"], 4 * 1048576)
    if sha(raw) != entry["sha256"]:
        raise ValueError("dataset population hash differs from index")
    value = strict_json(raw)
    if (
        value.get("schema_version") != 1
        or value.get("dataset") != DATASET
        or value.get("version") != VERSION
        or value.get("case_id") != identifier
        or value.get("profile") != entry["profile"]
    ):
        raise ValueError("unsupported study population")
    validate_bundle(value["population"])
    return value, entry


def list_cases(root=None):
    value = index(root)
    for entry in value["cases"]:
        load_case(entry["case_id"], root)
    return value


def write_private(path, raw):
    with path.open("xb") as file:
        os.chmod(path, 0o600)
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())


def initialize_workspace(identifier, directory, root=None):
    case, entry = load_case(identifier, root)
    directory = Path(os.path.abspath(directory))
    directory.mkdir(mode=0o700)
    population = case["population"]
    payloads = {
        "cases.json": encoded(population["cases"]),
        "expected.json": encoded(population["expectations"]),
        "source-history.json": encoded(
            {
                "as_of": population["as_of"],
                "customers": population["customers"],
                "source_history": population["source_history"],
                "scope": "original_seed_snapshot",
                "provenance": case["provenance"],
            }
        ),
    }
    identity = {
        "schema_version": 1,
        "dataset": DATASET,
        "version": VERSION,
        "case_id": identifier,
        "case_sha256": entry["sha256"],
        "index_sha256": INDEX_SHA256,
        "instance_id": str(uuid.uuid4()),
        "initialized_at": now(),
        "seed_files": {name: sha(raw) for name, raw in payloads.items()},
    }
    for name, raw in payloads.items():
        write_private(directory / name, raw)
    write_private(directory / "workspace.json", encoded(identity))
    write_private(
        directory / "TASK.md",
        (case["task"] + "\n\n" + case["provenance"] + "\n").encode(),
    )
    return inspect_workspace(directory, root)


def inspect_workspace(directory, root=None):
    directory = Path(os.path.abspath(directory))
    identity_path = directory / "workspace.json"
    info = identity_path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 65536:
        raise ValueError("workspace identity requires a bounded regular file")
    identity = strict_json(identity_path.read_bytes())
    if (
        set(identity)
        != {
            "schema_version",
            "dataset",
            "version",
            "case_id",
            "case_sha256",
            "index_sha256",
            "instance_id",
            "initialized_at",
            "seed_files",
        }
        or type(identity["schema_version"]) is not int
        or identity["schema_version"] != 1
        or identity["dataset"] != DATASET
        or identity["version"] != VERSION
        or identity["index_sha256"] != INDEX_SHA256
    ):
        raise ValueError("unsupported workspace identity")
    if (
        str(uuid.UUID(identity["instance_id"])) != identity["instance_id"]
        or uuid.UUID(identity["instance_id"]).version != 4
    ):
        raise ValueError("invalid workspace instance")
    case, entry = load_case(identity["case_id"], root)
    population = case["population"]
    seeds = {
        "cases.json": encoded(population["cases"]),
        "expected.json": encoded(population["expectations"]),
        "source-history.json": encoded(
            {
                "as_of": population["as_of"],
                "customers": population["customers"],
                "source_history": population["source_history"],
                "scope": "original_seed_snapshot",
                "provenance": case["provenance"],
            }
        ),
    }
    if identity["case_sha256"] != entry["sha256"] or identity["seed_files"] != {
        name: sha(raw) for name, raw in seeds.items()
    }:
        raise ValueError("workspace dataset identity changed")
    study = Study.from_files(directory / "cases.json", directory / "expected.json")
    current = {
        source["path"].rsplit("/", 1)[1]: source["sha256"] for source in study.sources
    }
    history_path = directory / "source-history.json"
    history_info = history_path.lstat()
    if not stat.S_ISREG(history_info.st_mode) or history_info.st_size > 4 * 1048576:
        raise ValueError("history requires a bounded regular file")
    history = history_path.read_bytes()
    strict_json(history)
    current["source-history.json"] = sha(history)
    return {
        "directory": str(directory),
        "cases": str(directory / "cases.json"),
        "expectations": str(directory / "expected.json"),
        "identity": identity,
        "orders": len(study.cases),
        "current_files": current,
        "matches_seed": all(
            current[name] == digest for name, digest in identity["seed_files"].items()
        ),
        "history_scope": "original_seed_snapshot; valid current edits do not rewrite imported history",
    }


def reset_workspace(directory, destination, instance, root=None):
    previous = inspect_workspace(directory, root)
    if instance != previous["identity"]["instance_id"]:
        raise ValueError("reset source instance is no longer current")
    return initialize_workspace(previous["identity"]["case_id"], destination, root)
