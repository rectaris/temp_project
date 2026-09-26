#!/usr/bin/env python3
"""Predict plan implementation risk from weighted feature scores offline.

`fit`, `score-holdout`, and `report` read explicitly supplied local records,
committed Git history, and the committed evaluation protocol only. They call no
provider, need no network, and write to stdout. `score-holdout` also appends one
entry to an explicit ledger file that must lie outside the repository worktree.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import math
import os
import re
import stat
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any


SCHEMA_VERSION = 1
PROTOCOL_PATH = "tests/fixtures/feature-scoring/evaluation-protocol.md"
PROTOCOL_KIND = "feature_scoring_protocol"
DIMENSIONS_KIND = "feature_dimensions"
SCORES_KIND = "feature_scores"
WEIGHTS_KIND = "feature_weights"
SCORING_KIND = "feature_holdout_scoring"
REPORT_KIND = "feature_scoring_report"
LEDGER_KIND = "feature_scoring_ledger_entry"
BAND_NAMES = ("high", "middle", "low")
FIXED_FIT = {
    "method": "multinomial_logistic_regression",
    "optimizer": "batch_gradient_descent",
    "initial_weights": "zero",
    "feature_scaling": "tuning_mean_population_standard_deviation",
}
FIXED_PROTOCOL = {
    "confidence": "max_class_probability",
    "baseline": "tuning_majority_class",
    "min_count_source": "question_set_protocol_min_class_count",
}
LIMIT_KEY = "min_overall_accuracy_gain_over_baseline"
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_DIMENSIONS = 64
MAX_SCORE_RECORDS = 4096
MAX_TEXT_BYTES = 2000
MAX_IDENTITY_BYTES = 200
MAX_ITERATIONS = 100_000
DIMENSION_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
PROTOCOL_BLOCK = re.compile(r"^```json\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)


class FeatureScoringError(RuntimeError):
    """An input, binding, or ledger check refused the evaluation."""


def load_question_set_module() -> ModuleType:
    name = "_score_plan_features_question_set"
    if name in sys.modules:
        return sys.modules[name]
    path = Path(__file__).resolve().with_name("build-plan-question-set.py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise FeatureScoringError(f"cannot load question set module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    # Importing must not write a bytecode cache into the tool checkout.
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


QS = load_question_set_module()
CLASSES = tuple(QS.LABEL_VALUES)


def canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except ValueError as exc:
        raise FeatureScoringError(f"record is not canonical JSON: {exc}") from exc


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def encode(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def reject_constant(value: str) -> Any:
    raise FeatureScoringError(f"non-finite number {value} is not admitted")


def parse_json(text: str, label: str) -> Any:
    try:
        return json.loads(text, parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise FeatureScoringError(f"{label} is not valid JSON: {exc}") from exc


def read_json(path: Path, label: str) -> Any:
    try:
        if path.is_symlink() or not path.is_file():
            raise FeatureScoringError(f"{label} must be a regular file: {path}")
        if path.stat().st_size > MAX_INPUT_BYTES:
            raise FeatureScoringError(f"{label} exceeds {MAX_INPUT_BYTES} bytes: {path}")
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise FeatureScoringError(f"{label} is unreadable: {exc}") from exc
    return parse_json(text, label)


def exact_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FeatureScoringError(f"{label} must be an object")
    if set(value) != keys:
        extra = sorted(set(value) - keys)
        missing = sorted(keys - set(value))
        raise FeatureScoringError(f"{label} keys differ: unexpected {extra}, missing {missing}")
    return value


def finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise FeatureScoringError(f"{label} must be a finite number")
    return float(value)


def unit_number(value: Any, label: str) -> float:
    number = finite_number(value, label)
    if not 0.0 <= number <= 1.0:
        raise FeatureScoringError(f"{label} must lie from 0 to 1, got {value}")
    return number


def bounded_text(value: Any, limit: int, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > limit:
        raise FeatureScoringError(f"{label} must be a nonblank string of at most {limit} bytes")
    return value


def digest_field(value: Any, label: str) -> str:
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        raise FeatureScoringError(f"{label} must be a sha256 digest")
    return value


# Protocol -------------------------------------------------------------------


def parse_protocol(text: str) -> dict[str, Any]:
    blocks = PROTOCOL_BLOCK.findall(text)
    if len(blocks) != 1:
        raise FeatureScoringError(f"protocol must contain exactly one json block, found {len(blocks)}")
    protocol = exact_object(
        parse_json(blocks[0], "protocol parameters"),
        {"schema_version", "kind", "label_field", "classes", "fit", "bands", "decision_limits", *FIXED_PROTOCOL},
        "protocol parameters",
    )
    if protocol["schema_version"] != SCHEMA_VERSION or protocol["kind"] != PROTOCOL_KIND:
        raise FeatureScoringError("protocol parameters are not a schema-1 feature scoring protocol")
    if protocol["label_field"] != QS.LABEL_FIELD or protocol["classes"] != list(CLASSES):
        raise FeatureScoringError(f"protocol must predict {QS.LABEL_FIELD} over {list(CLASSES)}")
    for key, value in FIXED_PROTOCOL.items():
        if protocol[key] != value:
            raise FeatureScoringError(f"protocol {key} must be {value}")
    fit = exact_object(protocol["fit"], {*FIXED_FIT, "learning_rate", "iterations", "l2_weight"}, "protocol fit")
    for key, value in FIXED_FIT.items():
        if fit[key] != value:
            raise FeatureScoringError(f"protocol fit {key} must be {value}")
    if not 0.0 < finite_number(fit["learning_rate"], "protocol learning_rate") <= 10.0:
        raise FeatureScoringError("protocol learning_rate must lie above 0 and at most 10")
    iterations = fit["iterations"]
    if isinstance(iterations, bool) or not isinstance(iterations, int) or not 1 <= iterations <= MAX_ITERATIONS:
        raise FeatureScoringError(f"protocol iterations must be an integer from 1 to {MAX_ITERATIONS}")
    if finite_number(fit["l2_weight"], "protocol l2_weight") < 0.0:
        raise FeatureScoringError("protocol l2_weight must not be negative")
    bands = protocol["bands"]
    if not isinstance(bands, list) or len(bands) != len(BAND_NAMES):
        raise FeatureScoringError(f"protocol bands must list {list(BAND_NAMES)}")
    previous = math.inf
    for index, (band, name) in enumerate(zip(bands, BAND_NAMES)):
        exact_object(band, {"band", "lower_inclusive"}, f"protocol band {index}")
        lower = unit_number(band["lower_inclusive"], f"protocol band {name} lower_inclusive")
        if band["band"] != name or lower >= previous:
            raise FeatureScoringError("protocol bands must be high, middle, low with strictly falling lower bounds")
        previous = lower
    if previous != 0.0:
        raise FeatureScoringError("protocol low band must start at 0")
    limits = exact_object(protocol["decision_limits"], {LIMIT_KEY}, "protocol decision_limits")
    unit_number(limits[LIMIT_KEY], f"protocol {LIMIT_KEY}")
    return protocol


def load_protocol(repo: Path) -> tuple[dict[str, Any], str]:
    """Read the protocol parameters as committed at HEAD of the repository."""

    try:
        commit = QS.resolve_revision(repo, "HEAD")
        data = QS.git(repo, "cat-file", "blob", f"{commit}:{PROTOCOL_PATH}")
    except QS.QuestionSetError as exc:
        raise FeatureScoringError(f"committed protocol {PROTOCOL_PATH} is unavailable: {exc}") from exc
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FeatureScoringError(f"committed protocol is not UTF-8: {exc}") from exc
    protocol = parse_protocol(text)
    return protocol, digest(protocol)


# Inputs ---------------------------------------------------------------------


def load_verified_question_set(repo: Path, path: Path) -> tuple[dict[str, Any], str]:
    """Accept a question set only when build-plan-question-set verify regenerates it."""

    try:
        report = QS.load_report(path)
        result = QS.verify_report(repo, report)
    except QS.QuestionSetError as exc:
        raise FeatureScoringError(f"question set is refused: {exc}") from exc
    if not result["verified"]:
        problems = {
            key: result[key]
            for key in ("mismatched_questions", "missing_questions", "unexpected_questions", "mismatched_sections")
            if result[key]
        }
        raise FeatureScoringError(f"question set does not pass verify: {json.dumps(problems, sort_keys=True)}")
    if report["protocol"].get("label_values") != list(CLASSES):
        raise FeatureScoringError(f"question set labels must be {list(CLASSES)}")
    return report, digest(report)


def load_dimensions(path: Path) -> tuple[list[str], str]:
    document = exact_object(read_json(path, "dimensions"), {"schema_version", "kind", "dimensions"}, "dimensions")
    if document["schema_version"] != SCHEMA_VERSION or document["kind"] != DIMENSIONS_KIND:
        raise FeatureScoringError("dimensions file is not a schema-1 feature_dimensions record")
    entries = document["dimensions"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_DIMENSIONS:
        raise FeatureScoringError(f"dimensions must list 1 to {MAX_DIMENSIONS} entries")
    identifiers: list[str] = []
    for index, entry in enumerate(entries):
        exact_object(entry, {"id", "text"}, f"dimension {index}")
        identifier = entry["id"]
        if not isinstance(identifier, str) or not DIMENSION_ID.fullmatch(identifier):
            raise FeatureScoringError(f"dimension {index} id must match {DIMENSION_ID.pattern}")
        if identifier in identifiers:
            raise FeatureScoringError(f"dimension id {identifier} is repeated")
        bounded_text(entry["text"], MAX_TEXT_BYTES, f"dimension {identifier} text")
        identifiers.append(identifier)
    return identifiers, digest(document)


def load_scores(
    path: Path, dimension_ids: list[str], dimensions_sha256: str
) -> tuple[dict[str, str], list[dict[str, Any]], str]:
    document = exact_object(
        read_json(path, "scores"), {"schema_version", "kind", "dimensions_sha256", "recorder", "scores"}, "scores"
    )
    if document["schema_version"] != SCHEMA_VERSION or document["kind"] != SCORES_KIND:
        raise FeatureScoringError("scores file is not a schema-1 feature_scores record")
    bound = digest_field(document["dimensions_sha256"], "scores dimensions_sha256")
    if bound != dimensions_sha256:
        raise FeatureScoringError(f"scores bind dimensions {bound}, not the supplied {dimensions_sha256}")
    recorder = exact_object(document["recorder"], {"identity", "model_id"}, "scores recorder")
    for key in ("identity", "model_id"):
        bounded_text(recorder[key], MAX_IDENTITY_BYTES, f"scores recorder {key}")
    records = document["scores"]
    if not isinstance(records, list) or len(records) > MAX_SCORE_RECORDS:
        raise FeatureScoringError(f"scores must list at most {MAX_SCORE_RECORDS} records")
    seen: set[str] = set()
    expected = set(dimension_ids)
    for index, record in enumerate(records):
        exact_object(record, {"question_id", "input_sha256", "values"}, f"score record {index}")
        identifier = bounded_text(record["question_id"], MAX_IDENTITY_BYTES, f"score record {index} question_id")
        if identifier in seen:
            raise FeatureScoringError(f"score record {identifier} is repeated")
        seen.add(identifier)
        digest_field(record["input_sha256"], f"score record {identifier} input_sha256")
        values = record["values"]
        if not isinstance(values, dict) or set(values) != expected:
            raise FeatureScoringError(f"score record {identifier} must score exactly the dimensions {dimension_ids}")
        for key in dimension_ids:
            unit_number(values[key], f"score record {identifier} {key}")
    return dict(recorder), records, digest(document)


def join_scores(
    report: dict[str, Any], records: list[dict[str, Any]], partition: str, command: str
) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], list[str], list[str]]:
    """Join score records to one partition by question_id and input_sha256, refusing any other record."""

    questions = {item["question_id"]: item for item in report["questions"]}
    joined: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for record in records:
        identifier = record["question_id"]
        question = questions.get(identifier)
        if question is None:
            raise FeatureScoringError(f"score record {identifier} names no question in the question set")
        if record["input_sha256"] != question["input_sha256"]:
            raise FeatureScoringError(f"score record {identifier} input_sha256 does not match its question")
        if question["partition"] != partition:
            raise FeatureScoringError(
                f"score record {identifier} is a {question['partition']} question; {command} accepts only {partition}"
            )
        joined.append((question, record))
    joined.sort(key=lambda pair: pair[0]["question_id"])
    expected = sorted(identifier for identifier, item in questions.items() if item["partition"] == partition)
    scored = {question["question_id"] for question, _ in joined}
    return joined, expected, [identifier for identifier in expected if identifier not in scored]


# Model ----------------------------------------------------------------------


def softmax(logits: list[float]) -> list[float]:
    top = max(logits)
    exponentials = [math.exp(value - top) for value in logits]
    total = sum(exponentials)
    return [value / total for value in exponentials]


def fit_weights(
    features: list[list[float]], labels: list[int], learning_rate: float, iterations: int, l2_weight: float
) -> tuple[list[float], list[float], list[list[float]]]:
    """Fit multinomial logistic regression by batch gradient descent from zero weights."""

    count = len(features)
    width = len(features[0])
    mean = [sum(row[column] for row in features) / count for column in range(width)]
    scale = []
    for column in range(width):
        deviation = math.sqrt(sum((row[column] - mean[column]) ** 2 for row in features) / count)
        scale.append(deviation if deviation > 0.0 else 1.0)
    rows = [[1.0] + [(row[column] - mean[column]) / scale[column] for column in range(width)] for row in features]
    weights = [[0.0] * (width + 1) for _ in CLASSES]
    for _ in range(iterations):
        gradient = [[0.0] * (width + 1) for _ in CLASSES]
        for row, label in zip(rows, labels):
            probabilities = softmax([sum(w * x for w, x in zip(weights[k], row)) for k in range(len(CLASSES))])
            for k, probability in enumerate(probabilities):
                error = probability - (1.0 if k == label else 0.0)
                gradient_row = gradient[k]
                for column, value in enumerate(row):
                    gradient_row[column] += error * value
        for k in range(len(CLASSES)):
            for column in range(width + 1):
                penalty = l2_weight * weights[k][column] if column else 0.0
                weights[k][column] -= learning_rate * (gradient[k][column] / count + penalty)
    return mean, scale, weights


def fit(repo: Path, question_set: Path, dimensions: Path, scores: Path) -> dict[str, Any]:
    protocol, protocol_sha256 = load_protocol(repo)
    report, question_set_sha256 = load_verified_question_set(repo, question_set)
    dimension_ids, dimensions_sha256 = load_dimensions(dimensions)
    recorder, records, scores_sha256 = load_scores(scores, dimension_ids, dimensions_sha256)
    joined, expected, missing = join_scores(report, records, "tuning", "fit")
    if not joined:
        raise FeatureScoringError("no tuning score record joins the question set")
    parameters = protocol["fit"]
    mean, scale, weights = fit_weights(
        [[float(record["values"][key]) for key in dimension_ids] for _, record in joined],
        [CLASSES.index(question["label"]) for question, _ in joined],
        float(parameters["learning_rate"]),
        parameters["iterations"],
        float(parameters["l2_weight"]),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": WEIGHTS_KIND,
        "question_set": {
            "sha256": question_set_sha256,
            "source_commit": report["revision"]["commit"],
            "tuning_expected": len(expected),
            "tuning_fitted": len(joined),
            "tuning_missing": missing,
        },
        "protocol_sha256": protocol_sha256,
        "dimensions_sha256": dimensions_sha256,
        "scores_sha256": scores_sha256,
        "recorder": recorder,
        "classes": list(CLASSES),
        "dimension_ids": dimension_ids,
        "fit": {key: parameters[key] for key in ("learning_rate", "iterations", "l2_weight")},
        "standardization": {"mean": mean, "scale": scale},
        "weights": {
            label: {"bias": row[0], "dimensions": dict(zip(dimension_ids, row[1:]))}
            for label, row in zip(CLASSES, weights)
        },
    }


def load_weights(path: Path) -> dict[str, Any]:
    keys = {
        "schema_version", "kind", "question_set", "protocol_sha256", "dimensions_sha256", "scores_sha256",
        "recorder", "classes", "dimension_ids", "fit", "standardization", "weights",
    }
    weights = exact_object(read_json(path, "weights"), keys, "weights")
    if weights["schema_version"] != SCHEMA_VERSION or weights["kind"] != WEIGHTS_KIND:
        raise FeatureScoringError("weights file is not a schema-1 feature_weights record")
    if weights["classes"] != list(CLASSES):
        raise FeatureScoringError(f"weights classes must be {list(CLASSES)}")
    source = exact_object(
        weights["question_set"],
        {"sha256", "source_commit", "tuning_expected", "tuning_fitted", "tuning_missing"},
        "weights question_set",
    )
    for key in ("tuning_expected", "tuning_fitted"):
        if isinstance(source[key], bool) or not isinstance(source[key], int) or source[key] < 0:
            raise FeatureScoringError(f"weights {key} must be a count")
    if not isinstance(source["tuning_missing"], list):
        raise FeatureScoringError("weights tuning_missing must be a list")
    identifiers = weights["dimension_ids"]
    if not isinstance(identifiers, list) or not identifiers:
        raise FeatureScoringError("weights dimension_ids must be a nonempty list")
    standardization = exact_object(weights["standardization"], {"mean", "scale"}, "weights standardization")
    for key in ("mean", "scale"):
        values = standardization[key]
        if not isinstance(values, list) or len(values) != len(identifiers):
            raise FeatureScoringError(f"weights standardization {key} must hold one value per dimension")
        for value in values:
            number = finite_number(value, f"weights standardization {key}")
            if key == "scale" and number <= 0.0:
                raise FeatureScoringError("weights standardization scale must be positive")
    rows = exact_object(weights["weights"], set(CLASSES), "weights weights")
    for label in CLASSES:
        row = exact_object(rows[label], {"bias", "dimensions"}, f"weights {label}")
        finite_number(row["bias"], f"weights {label} bias")
        values = exact_object(row["dimensions"], set(identifiers), f"weights {label} dimensions")
        for key in identifiers:
            finite_number(values[key], f"weights {label} {key}")
    return weights


def predict(weights: dict[str, Any], values: dict[str, float]) -> tuple[str, float, dict[str, float]]:
    identifiers = weights["dimension_ids"]
    mean = weights["standardization"]["mean"]
    scale = weights["standardization"]["scale"]
    row = [(float(values[key]) - mean[index]) / scale[index] for index, key in enumerate(identifiers)]
    logits = []
    for label in CLASSES:
        entry = weights["weights"][label]
        logits.append(entry["bias"] + sum(entry["dimensions"][key] * x for key, x in zip(identifiers, row)))
    probabilities = softmax(logits)
    best = max(range(len(CLASSES)), key=lambda k: (probabilities[k], -k))
    return CLASSES[best], probabilities[best], dict(zip(CLASSES, probabilities))


# Ledger ---------------------------------------------------------------------


def protected_roots(repo: Path) -> set[Path]:
    """Collect every worktree and common Git directory of the data and tool repositories."""

    roots: set[Path] = set()
    for start in (repo, Path(__file__).resolve().parent):
        try:
            common = QS.git(start, "rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip()
            listing = QS.git(start, "worktree", "list", "--porcelain", "-z").decode("utf-8", "surrogateescape")
        except QS.QuestionSetError as exc:
            raise FeatureScoringError(f"cannot resolve the repository worktrees: {exc}") from exc
        roots.add(Path(common).resolve())
        roots.update(
            Path(field[len("worktree "):]).resolve() for field in listing.split("\0") if field.startswith("worktree ")
        )
    return roots


def ledger_path(value: Path, repo: Path) -> Path:
    """Return the ledger location after proving it lies outside every repository worktree."""

    absolute = Path(os.path.abspath(value))
    try:
        parent = absolute.parent.resolve(strict=True)
    except OSError as exc:
        raise FeatureScoringError(f"ledger directory does not exist: {absolute.parent}") from exc
    candidate = parent / absolute.name
    for root in protected_roots(repo):
        if candidate == root or root in candidate.parents:
            raise FeatureScoringError(f"ledger must lie outside the repository worktree {root}: {candidate}")
    return candidate


@contextlib.contextmanager
def open_ledger(path: Path, *, write: bool) -> Iterator[int]:
    """Open the ledger without following a symlink, check ownership and mode, and lock it."""

    base = os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = -1
    try:
        if write:
            try:
                descriptor = os.open(path, base | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_EXCL, 0o600)
                os.fchmod(descriptor, 0o600)
            except FileExistsError:
                descriptor = os.open(path, base | os.O_RDWR | os.O_APPEND)
        else:
            descriptor = os.open(path, base | os.O_RDONLY)
    except FileNotFoundError as exc:
        raise FeatureScoringError(f"ledger does not exist: {path}") from exc
    except OSError as exc:
        raise FeatureScoringError(f"ledger cannot be opened without following a link: {exc}") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise FeatureScoringError(f"ledger must be a regular file: {path}")
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise FeatureScoringError(f"ledger must be owned by the caller with mode 0600: {path}")
        if info.st_nlink != 1:
            raise FeatureScoringError(f"ledger must have exactly one link: {path}")
        fcntl.flock(descriptor, fcntl.LOCK_EX if write else fcntl.LOCK_SH)
        yield descriptor
    finally:
        os.close(descriptor)


def read_ledger(descriptor: int) -> list[dict[str, Any]]:
    size = os.fstat(descriptor).st_size
    if size > MAX_INPUT_BYTES:
        raise FeatureScoringError(f"ledger exceeds {MAX_INPUT_BYTES} bytes")
    chunks = []
    offset = 0
    while offset < size:
        chunk = os.pread(descriptor, size - offset, offset)
        if not chunk:
            break
        chunks.append(chunk)
        offset += len(chunk)
    data = b"".join(chunks)
    if data and not data.endswith(b"\n"):
        raise FeatureScoringError("ledger is malformed: its last entry is incomplete")
    entries = []
    for number, line in enumerate(data.splitlines(), start=1):
        try:
            entry = exact_object(
                parse_json(line.decode("utf-8"), f"ledger line {number}"),
                {"schema_version", "kind", "key", "scoring_sha256"},
                f"ledger line {number}",
            )
        except UnicodeDecodeError as exc:
            raise FeatureScoringError(f"ledger line {number} is not UTF-8") from exc
        if entry["schema_version"] != SCHEMA_VERSION or entry["kind"] != LEDGER_KIND:
            raise FeatureScoringError(f"ledger line {number} is not a feature scoring ledger entry")
        digest_field(entry["key"], f"ledger line {number} key")
        digest_field(entry["scoring_sha256"], f"ledger line {number} scoring_sha256")
        entries.append(entry)
    return entries


# Holdout scoring ------------------------------------------------------------


def baseline_class(report: dict[str, Any]) -> str:
    labels = report["statistics"]["tuning"]["majority_class"]["labels"]
    for label in CLASSES:
        if label in labels:
            return label
    raise FeatureScoringError("the tuning partition has no majority class")


def score_holdout(
    repo: Path, question_set: Path, dimensions: Path, scores: Path, weights_path: Path, ledger: Path
) -> dict[str, Any]:
    protocol, protocol_sha256 = load_protocol(repo)
    bands = protocol["bands"]
    location = ledger_path(ledger, repo)
    report, question_set_sha256 = load_verified_question_set(repo, question_set)
    dimension_ids, dimensions_sha256 = load_dimensions(dimensions)
    weights = load_weights(weights_path)
    if weights["protocol_sha256"] != protocol_sha256:
        raise FeatureScoringError("weights were fitted under a different committed protocol")
    if weights["question_set"]["sha256"] != question_set_sha256:
        raise FeatureScoringError("weights were fitted on a different question set")
    if weights["dimensions_sha256"] != dimensions_sha256 or weights["dimension_ids"] != dimension_ids:
        raise FeatureScoringError("weights were fitted on different dimensions")
    recorder, records, scores_sha256 = load_scores(scores, dimension_ids, dimensions_sha256)
    joined, expected, missing = join_scores(report, records, "holdout", "score-holdout")
    if not expected:
        raise FeatureScoringError("the question set has no holdout question")
    questions = {item["question_id"]: item for item in report["questions"]}
    key_material = {
        "source_commit": report["revision"]["commit"],
        "holdout_input_sha256s": sorted(questions[identifier]["input_sha256"] for identifier in expected),
        "dimensions_sha256": dimensions_sha256,
        "weights_sha256": digest(weights),
        "band_thresholds_sha256": digest(bands),
    }
    key = digest(key_material)
    with open_ledger(location, write=True) as descriptor:
        if any(entry["key"] == key for entry in read_ledger(descriptor)):
            raise FeatureScoringError(f"the holdout was already scored for key {key}")
        values = {question["question_id"]: record["values"] for question, record in joined}
        predictions = []
        for identifier in expected:
            question = questions[identifier]
            entry: dict[str, Any] = {
                "question_id": identifier,
                "input_sha256": question["input_sha256"],
                "label": question["label"],
                "scored": identifier in values,
                "predicted": None,
                "confidence": None,
                "probabilities": None,
            }
            if entry["scored"]:
                entry["predicted"], entry["confidence"], entry["probabilities"] = predict(weights, values[identifier])
            predictions.append(entry)
        source = weights["question_set"]
        scoring = {
            "schema_version": SCHEMA_VERSION,
            "kind": SCORING_KIND,
            "key": key,
            "key_material": key_material,
            "question_set_sha256": question_set_sha256,
            "protocol_sha256": protocol_sha256,
            "scores_sha256": scores_sha256,
            "recorder": recorder,
            "classes": list(CLASSES),
            "min_class_count": report["protocol"]["min_class_count"],
            "baseline_class": baseline_class(report),
            "bands": bands,
            "decision_limits": protocol["decision_limits"],
            "tuning_coverage": {
                "expected": source["tuning_expected"],
                "fitted": source["tuning_fitted"],
                "missing": source["tuning_missing"],
            },
            "holdout_missing": missing,
            "records": predictions,
        }
        entry_bytes = canonical(
            {"schema_version": SCHEMA_VERSION, "kind": LEDGER_KIND, "key": key, "scoring_sha256": digest(scoring)}
        )
        os.write(descriptor, entry_bytes + b"\n")
        os.fsync(descriptor)
    return scoring


# Report ---------------------------------------------------------------------


def section(records: list[dict[str, Any]], minimum: int, baseline: str) -> dict[str, Any]:
    count = len(records)
    if count < minimum:
        return {"count": count, "status": "not_measurable", "correct": None, "accuracy": None, "baseline": None}
    correct = sum(1 for record in records if record["scored"] and record["predicted"] == record["label"])
    baseline_correct = sum(1 for record in records if record["label"] == baseline)
    return {
        "count": count,
        "status": "measured",
        "correct": correct,
        "accuracy": round(correct / count, 6),
        "baseline": {
            "majority_class": baseline,
            "count": count,
            "correct": baseline_correct,
            "accuracy": round(baseline_correct / count, 6),
        },
    }


def evaluate(scoring: dict[str, Any]) -> dict[str, Any]:
    """Compute paired accuracies, per-class and per-band denominators, and the outcome."""

    records = scoring["records"]
    minimum = scoring["min_class_count"]
    baseline = scoring["baseline_class"]
    overall = section(records, minimum, baseline)
    classes = {label: section([r for r in records if r["label"] == label], minimum, baseline) for label in CLASSES}
    bands: dict[str, Any] = {}
    upper: float | None = None
    for band in scoring["bands"]:
        lower = band["lower_inclusive"]
        members = [
            r for r in records if r["scored"] and r["confidence"] >= lower and (upper is None or r["confidence"] < upper)
        ]
        bands[band["band"]] = {"lower_inclusive": lower, "upper_exclusive": upper, **section(members, minimum, baseline)}
        upper = lower
    tuning = scoring["tuning_coverage"]
    holdout_missing = scoring["holdout_missing"]
    blockers = []
    if tuning["missing"]:
        blockers.append("tuning_coverage_incomplete")
    if holdout_missing:
        blockers.append("holdout_coverage_incomplete")
    if overall["status"] != "measured":
        blockers.append("overall_not_measurable")
    blockers.extend(f"band_not_measurable:{name}" for name, value in bands.items() if value["status"] != "measured")
    limit = scoring["decision_limits"][LIMIT_KEY]
    gain = None
    if overall["status"] == "measured":
        gain = round((overall["correct"] - overall["baseline"]["correct"]) / overall["count"], 6)
    if blockers:
        outcome = "insufficient_evidence"
    elif (overall["correct"] - overall["baseline"]["correct"]) / overall["count"] >= limit:
        outcome = "meets_limits"
    else:
        outcome = "below_limits"
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": REPORT_KIND,
        "key": scoring["key"],
        "question_set_sha256": scoring["question_set_sha256"],
        "protocol_sha256": scoring["protocol_sha256"],
        "scores_sha256": scoring["scores_sha256"],
        "weights_sha256": scoring["key_material"]["weights_sha256"],
        "recorder": scoring["recorder"],
        "min_class_count": minimum,
        "decision_limits": scoring["decision_limits"],
        "coverage": {
            "holdout_expected": len(records),
            "holdout_scored": sum(1 for record in records if record["scored"]),
            "holdout_missing": holdout_missing,
            "tuning_expected": tuning["expected"],
            "tuning_fitted": tuning["fitted"],
            "tuning_missing": tuning["missing"],
        },
        "overall": overall,
        "classes": classes,
        "not_measurable_classes": [label for label in CLASSES if classes[label]["status"] != "measured"],
        "bands": bands,
        "unbanded_unscored": sum(1 for record in records if not record["scored"]),
        "accuracy_gain_over_baseline": gain,
        "outcome": outcome,
        "blockers": blockers,
    }


def require_paired_baselines(report: dict[str, Any]) -> None:
    """Refuse any accuracy without a majority-class baseline over the same denominator."""

    sections = [("overall", report["overall"])]
    sections += [(f"class {name}", value) for name, value in report["classes"].items()]
    sections += [(f"band {name}", value) for name, value in report["bands"].items()]
    for name, value in sections:
        if value["status"] == "not_measurable":
            if value["accuracy"] is not None or value["baseline"] is not None:
                raise FeatureScoringError(f"report {name} is not measurable but carries an accuracy")
            continue
        baseline = value.get("baseline")
        if (
            value.get("accuracy") is None
            or not isinstance(baseline, dict)
            or baseline.get("accuracy") is None
            or baseline.get("count") != value.get("count")
        ):
            raise FeatureScoringError(f"report {name} lacks a paired baseline over its own count")


def encode_report(report: dict[str, Any]) -> bytes:
    require_paired_baselines(report)
    return encode(report)


def validate_scoring(scoring: Any) -> dict[str, Any]:
    keys = {
        "schema_version", "kind", "key", "key_material", "question_set_sha256", "protocol_sha256", "scores_sha256",
        "recorder", "classes", "min_class_count", "baseline_class", "bands", "decision_limits", "tuning_coverage",
        "holdout_missing", "records",
    }
    scoring = exact_object(scoring, keys, "holdout scoring")
    if scoring["schema_version"] != SCHEMA_VERSION or scoring["kind"] != SCORING_KIND:
        raise FeatureScoringError("holdout scoring is not a schema-1 feature_holdout_scoring record")
    if scoring["classes"] != list(CLASSES) or scoring["baseline_class"] not in CLASSES:
        raise FeatureScoringError("holdout scoring classes are malformed")
    minimum = scoring["min_class_count"]
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 1:
        raise FeatureScoringError("holdout scoring min_class_count must be a positive integer")
    records = scoring["records"]
    if not isinstance(records, list):
        raise FeatureScoringError("holdout scoring records must be a list")
    for index, record in enumerate(records):
        exact_object(
            record,
            {"question_id", "input_sha256", "label", "scored", "predicted", "confidence", "probabilities"},
            f"holdout scoring record {index}",
        )
        if record["label"] not in CLASSES or not isinstance(record["scored"], bool):
            raise FeatureScoringError(f"holdout scoring record {index} is malformed")
        if record["scored"]:
            if record["predicted"] not in CLASSES:
                raise FeatureScoringError(f"holdout scoring record {index} prediction is malformed")
            unit_number(record["confidence"], f"holdout scoring record {index} confidence")
    return scoring


def report(repo: Path, scoring_path: Path, ledger: Path) -> dict[str, Any]:
    protocol, protocol_sha256 = load_protocol(repo)
    location = ledger_path(ledger, repo)
    scoring = validate_scoring(read_json(scoring_path, "holdout scoring"))
    if scoring["protocol_sha256"] != protocol_sha256 or scoring["bands"] != protocol["bands"]:
        raise FeatureScoringError("holdout scoring was produced under a different committed protocol")
    if scoring["decision_limits"] != protocol["decision_limits"]:
        raise FeatureScoringError("holdout scoring decision limits differ from the committed protocol")
    if digest(scoring["key_material"]) != scoring["key"]:
        raise FeatureScoringError("holdout scoring key does not match its key material")
    if scoring["key_material"].get("band_thresholds_sha256") != digest(protocol["bands"]):
        raise FeatureScoringError("holdout scoring key binds different band thresholds")
    with open_ledger(location, write=False) as descriptor:
        entries = [entry for entry in read_ledger(descriptor) if entry["key"] == scoring["key"]]
    if len(entries) != 1 or entries[0]["scoring_sha256"] != digest(scoring):
        raise FeatureScoringError("holdout scoring is not the one recorded in the ledger for its key")
    try:
        return evaluate(scoring)
    except (KeyError, TypeError) as exc:
        raise FeatureScoringError(f"holdout scoring is malformed: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    fit_parser = commands.add_parser("fit", help="fit weights on the tuning partition and print them")
    score_parser = commands.add_parser("score-holdout", help="score the holdout once and print the scoring record")
    report_parser = commands.add_parser("report", help="print the evaluation report for a recorded scoring")
    for sub in (fit_parser, score_parser, report_parser):
        sub.add_argument("--repo", help="repository holding the question set history and committed protocol")
    for sub in (fit_parser, score_parser):
        sub.add_argument("--question-set", type=Path, required=True)
        sub.add_argument("--dimensions", type=Path, required=True)
        sub.add_argument("--scores", type=Path, required=True)
    score_parser.add_argument("--weights", type=Path, required=True)
    for sub in (score_parser, report_parser):
        sub.add_argument("--ledger", type=Path, required=True, help="append-only ledger outside the worktree")
    report_parser.add_argument("--scoring", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        repo = QS.repository_root(args.repo)
        if args.command == "fit":
            output = encode(fit(repo, args.question_set, args.dimensions, args.scores))
        elif args.command == "score-holdout":
            output = encode(
                score_holdout(repo, args.question_set, args.dimensions, args.scores, args.weights, args.ledger)
            )
        else:
            output = encode_report(report(repo, args.scoring, args.ledger))
    except (FeatureScoringError, QS.QuestionSetError) as exc:
        sys.stderr.write(f"score-plan-features: {exc}\n")
        return 2
    sys.stdout.buffer.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
