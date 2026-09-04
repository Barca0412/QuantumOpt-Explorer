"""Fixed-topology Perceval model for the catalog heralded CNOT.

The search variables are eight additive compensations, in radians: six beam
splitter angles followed by the two internal phase shifters.  Loss is modeled
with Perceval ``LC`` components, not by post-hoc rescaling probabilities.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

import numpy as np
import perceval as pcvl
from perceval.algorithm.tomography import ProcessTomography


_THETA_1 = 2 * math.acos(math.sqrt(1 / 3))
_THETA_2 = 2 * math.acos(math.sqrt((3 + math.sqrt(6)) / 6))
_NOMINAL_BS_ANGLES = np.asarray(
    [math.pi / 2, _THETA_1, _THETA_1, -_THETA_1, _THETA_2, math.pi / 2],
    dtype=float,
)
_NOMINAL_PS_PHASES = np.asarray([math.pi, math.pi], dtype=float)
_LOGICAL_INPUTS = {
    "00": (1, 0, 1, 0),
    "01": (1, 0, 0, 1),
    "10": (0, 1, 1, 0),
    "11": (0, 1, 0, 1),
}
_EXPECTED_OUTPUTS = {
    "00": "00",
    "01": "01",
    "10": "11",
    "11": "10",
}


@dataclass(frozen=True)
class NoiseRealization:
    """One physical realization of the three declared V2 noise mechanisms."""

    bs_offset: tuple[float, float, float, float, float, float]
    phase_error: tuple[float, float]
    mode_loss: tuple[float, float, float, float, float, float]

    @classmethod
    def ideal(cls) -> "NoiseRealization":
        return cls((0.0,) * 6, (0.0,) * 2, (0.0,) * 6)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InputEvaluation:
    input_label: str
    expected_output_label: str
    usable_success: float
    herald_probability: float
    conditional_truth_fidelity: float
    false_herald_probability: float
    leakage_probability: float
    logical_error_probability: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CnotEvaluation:
    conditional_truth_fidelity: float
    mean_herald_probability: float
    mean_usable_success: float
    mean_false_herald_probability: float
    mean_leakage_probability: float
    mean_logical_error_probability: float
    input_rows: tuple[InputEvaluation, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["input_rows"] = [row.to_dict() for row in self.input_rows]
        return result


@dataclass(frozen=True)
class ProcessTomographyResult:
    average_gate_fidelity: float
    gate_efficiency: float
    chi_trace_real: float
    chi_trace_imag: float
    chi_hermiticity_residual: float
    chi_matrix: np.ndarray

    def to_dict(self, include_matrix: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "average_gate_fidelity": self.average_gate_fidelity,
            "gate_efficiency": self.gate_efficiency,
            "chi_trace_real": self.chi_trace_real,
            "chi_trace_imag": self.chi_trace_imag,
            "chi_hermiticity_residual": self.chi_hermiticity_residual,
        }
        if include_matrix:
            result["chi_real"] = self.chi_matrix.real.tolist()
            result["chi_imag"] = self.chi_matrix.imag.tolist()
        return result


def _as_vector(values: Any, length: int, name: str) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    if vector.shape != (length,) or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must be a finite vector of length {length}")
    return vector


def build_cnot_processor(
    compensation: np.ndarray,
    noise: NoiseRealization,
) -> pcvl.Processor:
    """Build the fixed Perceval catalog topology with offsets and output loss."""
    compensation = _as_vector(compensation, 8, "compensation")
    bs_offset = _as_vector(noise.bs_offset, 6, "bs_offset")
    phase_error = _as_vector(noise.phase_error, 2, "phase_error")
    mode_loss = _as_vector(noise.mode_loss, 6, "mode_loss")
    if np.any(mode_loss < 0) or np.any(mode_loss >= 1):
        raise ValueError("mode_loss entries must be in [0, 1)")

    bs = _NOMINAL_BS_ANGLES + compensation[:6] + bs_offset
    phases = _NOMINAL_PS_PHASES + compensation[6:] + phase_error

    circuit = pcvl.Circuit(6, name="Calibrated heralded CNOT")
    circuit.add(2, pcvl.BS.H(theta=float(bs[0])))
    circuit.add(1, pcvl.PERM([1, 0]))
    circuit.add(3, pcvl.PERM([1, 0]))
    circuit.add(2, pcvl.Barrier(4, visible=False))
    circuit.add(2, pcvl.PS(float(phases[0])))
    circuit.add(5, pcvl.PS(float(phases[1])))
    circuit.add(2, pcvl.Barrier(4, visible=False))
    circuit.add(2, pcvl.BS.H(theta=float(bs[1])))
    circuit.add(4, pcvl.BS.H(theta=float(bs[2])))
    circuit.add(2, pcvl.Barrier(4, visible=False))
    circuit.add(3, pcvl.PERM([1, 0]))
    circuit.add(2, pcvl.BS.H(theta=float(bs[3])))
    circuit.add(4, pcvl.BS.H(theta=float(bs[4])))
    circuit.add(1, pcvl.PERM([1, 0]))
    circuit.add(2, pcvl.BS.H(theta=float(bs[5])))

    processor = pcvl.Processor("SLOS", circuit)
    for mode, loss in enumerate(mode_loss):
        if loss > 0:
            processor.add(mode, pcvl.LC(loss=float(loss)))
    # Retain loss events in the returned distribution.  Otherwise Perceval's
    # default photon-count filter moves them into global_perf and normalizes the
    # surviving states, which is unsuitable for unconditional success metrics.
    processor.min_detected_photons_filter(0)
    return processor


def _logical_state(label: str) -> tuple[int, int, int, int]:
    return _LOGICAL_INPUTS[label]


def _evaluate_input(
    processor: pcvl.Processor,
    input_label: str,
) -> InputEvaluation:
    expected_label = _EXPECTED_OUTPUTS[input_label]
    expected_state = pcvl.BasicState((*_logical_state(expected_label), 1, 1))
    processor.with_input(pcvl.BasicState((*_logical_state(input_label), 1, 1)))
    distribution = processor.probs()["results"]

    usable = float(distribution.get(expected_state, 0.0))
    herald = 0.0
    valid_logical_and_herald = 0.0
    for state, probability in distribution.items():
        probability = float(probability)
        is_herald = state[4] == 1 and state[5] == 1
        if not is_herald:
            continue
        herald += probability
        if state[0] + state[1] == 1 and state[2] + state[3] == 1:
            valid_logical_and_herald += probability

    leakage = max(0.0, herald - valid_logical_and_herald)
    logical_error = max(0.0, valid_logical_and_herald - usable)
    false_herald = max(0.0, herald - usable)
    fidelity = usable / herald if herald > 0 else 0.0
    return InputEvaluation(
        input_label=input_label,
        expected_output_label=expected_label,
        usable_success=usable,
        herald_probability=herald,
        conditional_truth_fidelity=fidelity,
        false_herald_probability=false_herald,
        leakage_probability=leakage,
        logical_error_probability=logical_error,
    )


def evaluate_cnot(
    compensation: np.ndarray,
    noise: NoiseRealization,
) -> CnotEvaluation:
    """Evaluate all four logical inputs without postselecting away failures."""
    processor = build_cnot_processor(compensation, noise)
    rows = tuple(_evaluate_input(processor, label) for label in _LOGICAL_INPUTS)

    def mean(field: str) -> float:
        return float(np.mean([getattr(row, field) for row in rows]))

    return CnotEvaluation(
        conditional_truth_fidelity=mean("conditional_truth_fidelity"),
        mean_herald_probability=mean("herald_probability"),
        mean_usable_success=mean("usable_success"),
        mean_false_herald_probability=mean("false_herald_probability"),
        mean_leakage_probability=mean("leakage_probability"),
        mean_logical_error_probability=mean("logical_error_probability"),
        input_rows=rows,
    )


def process_tomography(
    compensation: np.ndarray,
    noise: NoiseRealization,
) -> ProcessTomographyResult:
    """Run Perceval's coherent two-qubit process tomography for one realization."""
    processor = build_cnot_processor(compensation, noise)
    processor.add_port(0, pcvl.Port(pcvl.Encoding.DUAL_RAIL, "ctrl"))
    processor.add_port(2, pcvl.Port(pcvl.Encoding.DUAL_RAIL, "data"))
    processor.add_herald(4, 1)
    processor.add_herald(5, 1)
    tomography = ProcessTomography(processor)
    chi = np.asarray(tomography.chi_matrix(), dtype=complex)
    ideal_cnot = np.asarray(
        [
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 0, 1],
            [0, 0, 1, 0],
        ],
        dtype=complex,
    )
    gate_efficiency = complex(tomography.gate_efficiency)
    return ProcessTomographyResult(
        average_gate_fidelity=float(np.real(tomography.average_fidelity(ideal_cnot))),
        gate_efficiency=float(np.real(gate_efficiency)),
        chi_trace_real=float(np.trace(chi).real),
        chi_trace_imag=float(np.trace(chi).imag),
        chi_hermiticity_residual=float(np.linalg.norm(chi - chi.conj().T)),
        chi_matrix=chi,
    )
