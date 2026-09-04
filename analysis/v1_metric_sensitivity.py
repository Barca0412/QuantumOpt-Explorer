#!/usr/bin/env python3
"""Reproduce the post-hoc V1 metric-sensitivity and phenotype audits.

The script is deliberately standard-library only.  It reads the frozen files under
``archive/v1`` and writes derived evidence under ``evidence/v1_*``.  It never edits
the archived experiment.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import struct
import zlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple


POLICIES = ("random", "greedy", "bads")
POLICY_LABELS = {
    "random": "Random",
    "greedy": "Greedy",
    "bads": "BADS",
}


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("mean requires at least one value")
    return float(statistics.fmean(values))


def median(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("median requires at least one value")
    return float(statistics.median(values))


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("Pearson correlation requires paired values")
    x_mean = mean(xs)
    y_mean = mean(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    x_ss = sum((x - x_mean) ** 2 for x in xs)
    y_ss = sum((y - y_mean) ** 2 for y in ys)
    denominator = math.sqrt(x_ss * y_ss)
    if denominator == 0.0:
        raise ValueError("Pearson correlation is undefined for a constant series")
    return float(numerator / denominator)


def write_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("Refusing to write an empty CSV")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: List[str] = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fields.append(key)
                seen.add(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def canonical_phenotype(design: Dict[str, Any]) -> Dict[str, Any]:
    """Drop inactive and physically unused genes from a candidate design."""
    depth = int(design["depth"])
    active_layers = []
    for layer in design["layers"][:depth]:
        pattern = int(layer["pattern"])
        active_theta_count = 2 if pattern == 0 else 1
        active_layers.append(
            {
                "pattern": pattern,
                "theta_indices": [
                    int(value)
                    for value in layer["theta_indices"][:active_theta_count]
                ],
                "phase_indices": [int(value) for value in layer["phase_indices"]],
            }
        )
    return {"depth": depth, "layers": active_layers}


def phenotype_id(design: Dict[str, Any]) -> str:
    payload = json.dumps(
        canonical_phenotype(design), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def aggregate_lookup(
    rows: Sequence[Dict[str, str]], policy: str, metric: str
) -> Dict[str, str]:
    return next(
        row
        for row in rows
        if row["policy"] == policy and row["metric"] == metric
    )


def policy_shift_rows(
    episode_rows: Sequence[Dict[str, str]], aggregate_rows: Sequence[Dict[str, str]]
) -> List[Dict[str, Any]]:
    output = []
    for policy in POLICIES:
        rows = [row for row in episode_rows if row["policy"] == policy]
        fidelity_gaps = [float(row["fidelity_generalization_gap"]) for row in rows]
        survival_gaps = [float(row["success_generalization_gap"]) for row in rows]
        fidelity_summary = aggregate_lookup(
            aggregate_rows, policy, "fidelity_generalization_gap"
        )
        survival_summary = aggregate_lookup(
            aggregate_rows, policy, "success_generalization_gap"
        )
        fidelity_gap = mean(fidelity_gaps)
        survival_gap = mean(survival_gaps)
        output.append(
            {
                "policy": policy,
                "policy_label": POLICY_LABELS[policy],
                "n_episodes": len(rows),
                "train_fidelity_q25_mean": mean(
                    [float(row["train_fidelity_q25"]) for row in rows]
                ),
                "heldout_fidelity_q25_mean": mean(
                    [float(row["heldout_fidelity_q25"]) for row in rows]
                ),
                "fidelity_generalization_gap_mean": fidelity_gap,
                "fidelity_generalization_gap_median": median(fidelity_gaps),
                "fidelity_gap_ci95_low": float(fidelity_summary["mean_ci95_low"]),
                "fidelity_gap_ci95_high": float(fidelity_summary["mean_ci95_high"]),
                "train_survival_q25_mean": mean(
                    [float(row["train_success_q25"]) for row in rows]
                ),
                "heldout_survival_q25_mean": mean(
                    [float(row["heldout_success_q25"]) for row in rows]
                ),
                "survival_generalization_gap_mean": survival_gap,
                "survival_generalization_gap_median": median(survival_gaps),
                "survival_gap_ci95_low": float(survival_summary["mean_ci95_low"]),
                "survival_gap_ci95_high": float(survival_summary["mean_ci95_high"]),
                "absolute_gap_ratio_survival_to_fidelity": (
                    survival_gap / abs(fidelity_gap)
                ),
                "share_of_two_absolute_gaps_carried_by_survival": (
                    abs(survival_gap)
                    / (abs(survival_gap) + abs(fidelity_gap))
                ),
                "evidence_status": "post-hoc diagnostic from frozen V1 outputs",
            }
        )
    return output


def correlation_rows(final_rows: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    selected = [row for row in final_rows if row["selected_for_primary"] == "True"]
    grouped: Dict[Tuple[str, str, str], List[Dict[str, str]]] = defaultdict(list)
    for row in selected:
        grouped[(row["episode_seed"], row["policy"], row["split"])].append(row)

    output = []
    for split in ("train", "heldout"):
        split_rows = [row for row in selected if row["split"] == split]
        losses = [float(row["mean_loss_rate"]) for row in split_rows]
        for metric, source_field in (
            ("normalized_process_fidelity", "fidelity"),
            ("single_photon_survival", "success_probability"),
        ):
            values = [float(row[source_field]) for row in split_rows]
            within = []
            for (_seed, _policy, group_split), rows in grouped.items():
                if group_split != split:
                    continue
                within.append(
                    pearson(
                        [float(row["mean_loss_rate"]) for row in rows],
                        [float(row[source_field]) for row in rows],
                    )
                )
            output.append(
                {
                    "split": split,
                    "metric": metric,
                    "n_pattern_rows": len(split_rows),
                    "n_selected_candidate_groups": len(within),
                    "aggregate_pearson_loss_vs_metric": pearson(losses, values),
                    "within_candidate_pearson_mean": mean(within),
                    "within_candidate_pearson_median": median(within),
                    "within_candidate_pearson_min": min(within),
                    "within_candidate_pearson_max": max(within),
                    "mean_loss_rate": mean(losses),
                    "mean_metric_value": mean(values),
                    "evidence_status": "post-hoc diagnostic; correlation is not causal",
                }
            )
    return output


def uniform_loss_sweep(modes: int, depth: int) -> List[Dict[str, Any]]:
    """Apply the V1 metric formula to scalar loss after every layer.

    For a target unitary U and transfer A = alpha U, normalized process fidelity
    is exactly one for every non-zero alpha, while mean single-photon survival is
    alpha squared.  With uniform per-layer intensity loss l, alpha squared is
    (1-l)**depth.
    """
    rows = []
    for loss in (0.0, 0.01, 0.03, 0.05, 0.10, 0.20):
        amplitude_scale = (math.sqrt(1.0 - loss)) ** depth
        trace_target_target = float(modes)
        trace_transfer_transfer = float(modes) * amplitude_scale**2
        overlap = float(modes) * amplitude_scale
        fidelity = overlap**2 / (
            trace_target_target * trace_transfer_transfer
        )
        survival = trace_transfer_transfer / float(modes)
        rows.append(
            {
                "modes": modes,
                "depth": depth,
                "uniform_intensity_loss_per_layer": loss,
                "net_amplitude_scale": amplitude_scale,
                "normalized_process_fidelity": fidelity,
                "mean_single_photon_survival": survival,
                "evidence_status": "verified analytic sanity check of the V1 formula",
            }
        )
    return rows


def duplicate_rows(
    candidate_rows: Sequence[Dict[str, Any]], query_rows: Sequence[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    by_episode: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    candidate_to_phenotype: Dict[Tuple[int, str], str] = {}
    for row in candidate_rows:
        seed = int(row["episode_seed"])
        pid = phenotype_id(row["design"])
        enriched = dict(row)
        enriched["phenotype_id"] = pid
        by_episode[seed].append(enriched)
        candidate_to_phenotype[(seed, row["candidate_id"])] = pid

    queried_ids: Dict[Tuple[int, str], List[str]] = defaultdict(list)
    repeated_query_counts: Counter[str] = Counter()
    for row in query_rows:
        key = (int(row["episode_seed"]), row["policy"])
        queried_ids[key].append(
            candidate_to_phenotype[(int(row["episode_seed"]), row["candidate_id"])]
        )
    for (_seed, policy), ids in queried_ids.items():
        repeated_query_counts[policy] += len(ids) - len(set(ids))

    output = []
    for seed, rows in sorted(by_episode.items()):
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in rows:
            groups[row["phenotype_id"]].append(row)
        for pid, duplicate_group in sorted(groups.items()):
            if len(duplicate_group) < 2:
                continue
            candidate_ids = [row["candidate_id"] for row in duplicate_group]
            query_occurrences = {
                policy: queried_ids[(seed, policy)].count(pid)
                for policy in POLICIES
            }
            output.append(
                {
                    "episode_seed": seed,
                    "phenotype_id": pid,
                    "genotype_multiplicity": len(duplicate_group),
                    "candidate_ids": ";".join(candidate_ids),
                    "pool_indices": ";".join(
                        str(row["pool_index"]) for row in duplicate_group
                    ),
                    "random_query_occurrences": query_occurrences["random"],
                    "greedy_query_occurrences": query_occurrences["greedy"],
                    "bads_query_occurrences": query_occurrences["bads"],
                    "cause": (
                        "candidate ID retains inactive layers and the second theta gene "
                        "that pattern-1 layers do not execute"
                    ),
                    "evidence_status": "verified from frozen V1 candidate and query logs",
                }
            )
    return output, {policy: repeated_query_counts[policy] for policy in POLICIES}


FONT = {
    " ": ("00000",) * 7,
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00110", "00110"),
    ":": ("00000", "00110", "00110", "00000", "00110", "00110", "00000"),
    "%": ("11001", "11010", "00100", "01000", "10110", "00110", "00000"),
    "/": ("00001", "00010", "00100", "01000", "10000", "00000", "00000"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
}


class Canvas:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray([255] * width * height * 3)

    def pixel(self, x: int, y: int, colour: Tuple[int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            index = (y * self.width + x) * 3
            self.pixels[index : index + 3] = bytes(colour)

    def rectangle(
        self, x0: int, y0: int, x1: int, y1: int, colour: Tuple[int, int, int]
    ) -> None:
        for y in range(max(0, y0), min(self.height, y1)):
            start = (y * self.width + max(0, x0)) * 3
            end = (y * self.width + min(self.width, x1)) * 3
            self.pixels[start:end] = bytes(colour) * max(0, min(self.width, x1) - max(0, x0))

    def line(
        self, x0: int, y0: int, x1: int, y1: int, colour: Tuple[int, int, int]
    ) -> None:
        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        error = dx + dy
        while True:
            self.pixel(x0, y0, colour)
            if x0 == x1 and y0 == y1:
                break
            doubled = 2 * error
            if doubled >= dy:
                error += dy
                x0 += sx
            if doubled <= dx:
                error += dx
                y0 += sy

    def text(
        self,
        x: int,
        y: int,
        value: str,
        colour: Tuple[int, int, int] = (25, 32, 45),
        scale: int = 2,
    ) -> None:
        cursor = x
        for character in value.upper():
            glyph = FONT.get(character, FONT[" "])
            for row_index, row in enumerate(glyph):
                for column_index, bit in enumerate(row):
                    if bit == "1":
                        self.rectangle(
                            cursor + column_index * scale,
                            y + row_index * scale,
                            cursor + (column_index + 1) * scale,
                            y + (row_index + 1) * scale,
                            colour,
                        )
            cursor += 6 * scale

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = bytearray()
        row_width = self.width * 3
        for y in range(self.height):
            raw.append(0)
            start = y * row_width
            raw.extend(self.pixels[start : start + row_width])

        def chunk(kind: bytes, data: bytes) -> bytes:
            return (
                struct.pack(">I", len(data))
                + kind
                + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
            )

        png = b"\x89PNG\r\n\x1a\n"
        png += chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0),
        )
        png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        png += chunk(b"IEND", b"")
        path.write_bytes(png)


def make_figure(
    path: Path,
    shifts: Sequence[Dict[str, Any]],
    sweep: Sequence[Dict[str, Any]],
) -> None:
    canvas = Canvas(1400, 760)
    ink = (27, 35, 48)
    muted = (120, 130, 145)
    grid = (220, 225, 232)
    blue = (45, 103, 210)
    orange = (225, 119, 48)
    canvas.text(60, 35, "V1 METRIC SENSITIVITY AUDIT", ink, 4)
    canvas.text(60, 83, "POST-HOC DIAGNOSTIC - NOT PREREGISTERED", muted, 2)

    # Left panel: empirical mean train-minus-heldout gaps.
    x0, x1, y0, y1 = 80, 650, 160, 650
    canvas.text(x0, 125, "MEAN TRAIN-HELDOUT GAP", ink, 2)
    max_gap = 0.12
    for tick in (0.00, 0.03, 0.06, 0.09, 0.12):
        y = int(y1 - (tick / max_gap) * (y1 - y0))
        canvas.line(x0, y, x1, y, grid)
        canvas.text(15, y - 7, f"{tick:.2f}", muted, 2)
    canvas.line(x0, y0, x0, y1, ink)
    canvas.line(x0, y1, x1, y1, ink)
    group_width = 170
    for index, row in enumerate(shifts):
        centre = x0 + 105 + index * group_width
        for offset, key, colour in (
            (-32, "fidelity_generalization_gap_mean", blue),
            (18, "survival_generalization_gap_mean", orange),
        ):
            value = float(row[key])
            bar_height = max(2, int((value / max_gap) * (y1 - y0)))
            canvas.rectangle(centre + offset, y1 - bar_height, centre + offset + 34, y1, colour)
            canvas.text(centre + offset - 7, y1 - bar_height - 22, f"{value:.4f}", colour, 1)
        canvas.text(centre - 38, y1 + 22, row["policy_label"], ink, 2)
    canvas.rectangle(100, 690, 120, 710, blue)
    canvas.text(130, 691, "FIDELITY", ink, 2)
    canvas.rectangle(300, 690, 320, 710, orange)
    canvas.text(330, 691, "SURVIVAL", ink, 2)

    # Right panel: exact response to scalar loss after every layer.
    x0, x1, y0, y1 = 780, 1330, 160, 650
    canvas.text(x0, 125, "UNIFORM LOSS - DEPTH 5", ink, 2)
    for tick in (0.0, 0.25, 0.50, 0.75, 1.0):
        y = int(y1 - tick * (y1 - y0))
        canvas.line(x0, y, x1, y, grid)
        canvas.text(720, y - 7, f"{tick:.2f}", muted, 2)
    canvas.line(x0, y0, x0, y1, ink)
    canvas.line(x0, y1, x1, y1, ink)
    for tick in (0.0, 0.05, 0.10, 0.15, 0.20):
        x = int(x0 + (tick / 0.20) * (x1 - x0))
        canvas.line(x, y1, x, y1 + 8, ink)
        canvas.text(x - 20, y1 + 18, f"{tick:.2f}", muted, 2)
    canvas.text(890, 700, "PER-LAYER INTENSITY LOSS", ink, 2)

    for key, colour in (
        ("normalized_process_fidelity", blue),
        ("mean_single_photon_survival", orange),
    ):
        points = []
        for row in sweep:
            x = int(
                x0
                + (float(row["uniform_intensity_loss_per_layer"]) / 0.20)
                * (x1 - x0)
            )
            y = int(y1 - float(row[key]) * (y1 - y0))
            points.append((x, y))
        for left, right in zip(points, points[1:]):
            for offset in (-1, 0, 1):
                canvas.line(left[0], left[1] + offset, right[0], right[1] + offset, colour)
        for x, y in points:
            canvas.rectangle(x - 4, y - 4, x + 5, y + 5, colour)
    canvas.rectangle(840, 190, 860, 210, blue)
    canvas.text(870, 191, "FIDELITY", ink, 2)
    canvas.rectangle(1070, 190, 1090, 210, orange)
    canvas.text(1100, 191, "SURVIVAL", ink, 2)
    canvas.save(path)


def bads_findings(
    comparison_rows: Sequence[Dict[str, str]], gate: Dict[str, Any]
) -> Dict[str, Any]:
    selected = {}
    for baseline in ("random", "greedy"):
        row = next(
            item
            for item in comparison_rows
            if item["comparison"] == f"bads_minus_{baseline}"
            and item["metric"] == "heldout_fidelity_q25"
        )
        selected[baseline] = {
            "mean_paired_difference": float(row["mean_paired_difference"]),
            "paired_ci95_low": float(row["paired_ci95_low"]),
            "paired_ci95_high": float(row["paired_ci95_high"]),
            "bads_wins": int(row["bads_wins"]),
            "ties": int(row["ties"]),
            "n_paired_episodes": int(row["n_paired_episodes"]),
        }
    return {
        "discovery_gate_passed": bool(gate["discovery_gate_passed"]),
        "heldout_fidelity_comparisons": selected,
        "evidence_status": "verified frozen V1 result",
    }


def parse_args() -> argparse.Namespace:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive-root",
        type=Path,
        default=repository / "archive" / "v1" / "reproducibility",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=repository / "evidence"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive = args.archive_root.resolve()
    output = args.output_dir.resolve()
    config = json.loads((archive / "config" / "experiment.json").read_text(encoding="utf-8"))
    episode_rows = read_csv(archive / "results" / "episode_summary.csv")
    aggregate_rows = read_csv(archive / "results" / "aggregate_metrics.csv")
    comparison_rows = read_csv(archive / "results" / "statistical_comparisons.csv")
    gate = json.loads((archive / "results" / "discovery_gate.json").read_text(encoding="utf-8"))
    final_rows = read_csv(archive / "raw" / "final_pattern_metrics.csv")
    candidate_rows = read_jsonl(archive / "raw" / "candidate_pool.jsonl")
    query_rows = read_jsonl(archive / "raw" / "query_log.jsonl")

    shifts = policy_shift_rows(episode_rows, aggregate_rows)
    correlations = correlation_rows(final_rows)
    sweep = uniform_loss_sweep(int(config["modes"]), int(config["max_depth"]))
    duplicates, redundant_queries = duplicate_rows(candidate_rows, query_rows)
    bads = bads_findings(comparison_rows, gate)

    source_paths = [
        archive / "config" / "experiment.json",
        archive / "src" / "quantumopt_experiment.py",
        archive / "raw" / "candidate_pool.jsonl",
        archive / "raw" / "query_log.jsonl",
        archive / "raw" / "final_pattern_metrics.csv",
        archive / "results" / "episode_summary.csv",
        archive / "results" / "aggregate_metrics.csv",
        archive / "results" / "statistical_comparisons.csv",
        archive / "results" / "discovery_gate.json",
    ]
    summary = {
        "schema_version": "1.0",
        "analysis_name": "V1 post-hoc metric-sensitivity and phenotype audit",
        "analysis_status": "post-hoc diagnostic; not preregistered",
        "source_release": "archive/v1",
        "source_artifacts": [
            {
                "path": str(path.relative_to(archive.parents[2])),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in source_paths
        ],
        "policy_shift": shifts,
        "pattern_level_correlations": correlations,
        "uniform_loss_sweep": sweep,
        "phenotype_duplicate_audit": {
            "candidate_genotype_rows": len(candidate_rows),
            "duplicate_phenotype_groups": len(duplicates),
            "duplicate_genotype_rows_beyond_first": sum(
                int(row["genotype_multiplicity"]) - 1 for row in duplicates
            ),
            "redundant_physical_queries_by_policy": redundant_queries,
            "groups": duplicates,
            "evidence_status": "verified frozen V1 artifact audit",
        },
        "bads_result": bads,
        "interpretation": {
            "verified": (
                "The V1 discovery gate did not pass, and its frozen artifacts contain "
                "four genotype rows that duplicate another executable phenotype."
            ),
            "post_hoc": (
                "The held-out shift is expressed overwhelmingly through single-photon "
                "survival, while normalized process fidelity changes little. This is "
                "consistent with the metric's exact invariance to scalar attenuation."
            ),
            "not_established": (
                "This diagnostic does not establish why BADS underperformed, physical-device "
                "robustness, or a new quantum-optical discovery."
            ),
        },
        "future_work": [
            "Treat survival or a physically justified joint metric as co-primary.",
            "Add component-specific asymmetric loss, source and detector effects, partial distinguishability, and fabrication perturbations.",
            "Canonicalize executable phenotypes before enforcing candidate uniqueness and query-budget uniqueness.",
            "Test multiple target and topology families with stronger search baselines and preregistered ablations.",
        ],
    }

    write_csv(output / "v1_metric_sensitivity_by_policy.csv", shifts)
    write_csv(output / "v1_metric_sensitivity_correlations.csv", correlations)
    write_csv(output / "v1_uniform_loss_sweep.csv", sweep)
    write_csv(output / "v1_phenotype_duplicates.csv", duplicates)
    (output / "v1_metric_sensitivity.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    make_figure(output / "v1_metric_sensitivity.png", shifts, sweep)

    print(
        json.dumps(
            {
                "status": "generated",
                "output_dir": str(output),
                "duplicate_phenotype_groups": len(duplicates),
                "discovery_gate_passed": bads["discovery_gate_passed"],
                "files": [
                    "v1_metric_sensitivity_by_policy.csv",
                    "v1_metric_sensitivity_correlations.csv",
                    "v1_uniform_loss_sweep.csv",
                    "v1_phenotype_duplicates.csv",
                    "v1_metric_sensitivity.json",
                    "v1_metric_sensitivity.png",
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
