from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from .models import SatelliteOrbitRecord

ScenarioName = Literal["nominal", "thermal_drift", "power_drop", "comms_degradation"]
PolicyName = Literal["conservative_ops", "balanced_ops", "relaxed_ops"]
Severity = Literal["info", "warning", "critical"]

SIMULATION_VERSION = "sim-telemetry-v1"
SCENARIOS: set[str] = {"nominal", "thermal_drift", "power_drop", "comms_degradation"}
POLICIES: set[str] = {"conservative_ops", "balanced_ops", "relaxed_ops"}
LIMITATIONS = [
    "Simulated spacecraft telemetry layered on public CelesTrak orbit context.",
    "Not real spacecraft telemetry and not live spacecraft telemetry.",
    "Not a live spacecraft monitoring system.",
    "Not mission-grade operations software or validated anomaly detection.",
]


@dataclass(frozen=True)
class PolicyProfile:
    name: str
    warning_thresholds: dict[str, float]
    critical_thresholds: dict[str, float]
    required_persistence: int
    recommended_operator_action: str
    notes: str


POLICY_PROFILES: dict[str, PolicyProfile] = {
    "conservative_ops": PolicyProfile(
        name="conservative_ops",
        warning_thresholds={
            "battery_temperature_c": 31.0,
            "bus_voltage_v": 27.2,
            "downlink_margin_db": 5.5,
        },
        critical_thresholds={
            "battery_temperature_c": 42.0,
            "bus_voltage_v": 26.2,
            "downlink_margin_db": 3.0,
        },
        required_persistence=1,
        recommended_operator_action="Start immediate subsystem triage and prepare mitigation review.",
        notes="Lower thresholds and single-sample persistence; catches weak signals early with more noise.",
    ),
    "balanced_ops": PolicyProfile(
        name="balanced_ops",
        warning_thresholds={
            "battery_temperature_c": 36.0,
            "bus_voltage_v": 26.7,
            "downlink_margin_db": 4.5,
        },
        critical_thresholds={
            "battery_temperature_c": 48.0,
            "bus_voltage_v": 25.8,
            "downlink_margin_db": 2.2,
        },
        required_persistence=2,
        recommended_operator_action="Validate trend, compare against contact plan, and assign focused subsystem check.",
        notes="Requires short persistence before escalation to balance sensitivity and alert fatigue.",
    ),
    "relaxed_ops": PolicyProfile(
        name="relaxed_ops",
        warning_thresholds={
            "battery_temperature_c": 44.0,
            "bus_voltage_v": 26.0,
            "downlink_margin_db": 3.2,
        },
        critical_thresholds={
            "battery_temperature_c": 56.0,
            "bus_voltage_v": 25.2,
            "downlink_margin_db": 1.4,
        },
        required_persistence=3,
        recommended_operator_action="Monitor for sustained degradation before interrupting the nominal plan.",
        notes="Higher thresholds and longer persistence; fewer alerts but later operator visibility.",
    ),
}


def validate_scenario(scenario: str) -> ScenarioName:
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown simulated telemetry scenario: {scenario}")
    return scenario  # type: ignore[return-value]


def validate_policy(policy: str) -> PolicyName:
    if policy not in POLICIES:
        raise ValueError(f"Unknown operations policy profile: {policy}")
    return policy  # type: ignore[return-value]


def simulate_telemetry(
    record: SatelliteOrbitRecord,
    *,
    scenario: str,
    seed: int | None = None,
    duration_minutes: int = 60,
    step_seconds: int = 60,
) -> dict[str, Any]:
    scenario_name = validate_scenario(scenario)
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be positive")
    if step_seconds <= 0:
        raise ValueError("step_seconds must be positive")
    if duration_minutes > 24 * 60:
        raise ValueError("duration_minutes must be 1440 or less")
    if step_seconds > duration_minutes * 60:
        raise ValueError("step_seconds must not exceed the simulation duration")

    start = record.epoch or record.ingested_at
    start = _ensure_utc(start)
    generated_at = start + timedelta(seconds=17)
    rng = random.Random(f"{record.norad_cat_id}:{scenario_name}:{seed}")

    samples: list[dict[str, Any]] = []
    step_count = int(duration_minutes * 60 / step_seconds) + 1
    for sequence in range(step_count):
        event_time = start + timedelta(seconds=sequence * step_seconds)
        fraction = sequence / max(step_count - 1, 1)
        values = _scenario_values(scenario_name, fraction, rng)
        for subsystem, measurement_name, value, unit in values:
            samples.append(
                {
                    "source_event_time": _iso(event_time),
                    "generated_at": _iso(generated_at),
                    "sequence_count": sequence,
                    "subsystem": subsystem,
                    "measurement_name": measurement_name,
                    "measurement_value": round(value, 3),
                    "unit": unit,
                    "status": _sample_status(measurement_name, value),
                    "quality_flag": "simulated_nominal" if scenario_name == "nominal" else "simulated_scenario",
                }
            )

    return {
        "data_kind": "simulated_telemetry",
        "scenario": scenario_name,
        "simulation_version": SIMULATION_VERSION,
        "generated_at": _iso(generated_at),
        "seed": seed,
        "norad_cat_id": record.norad_cat_id,
        "object_name": record.object_name,
        "duration_minutes": duration_minutes,
        "step_seconds": step_seconds,
        "source_orbit_epoch": _iso(start),
        "limitations": LIMITATIONS,
        "samples": samples,
    }


def generate_events(
    record: SatelliteOrbitRecord,
    *,
    scenario: str,
    policy: str,
    seed: int | None = None,
    duration_minutes: int = 60,
    step_seconds: int = 60,
) -> dict[str, Any]:
    scenario_name = validate_scenario(scenario)
    policy_name = validate_policy(policy)
    telemetry = simulate_telemetry(
        record,
        scenario=scenario_name,
        seed=seed,
        duration_minutes=duration_minutes,
        step_seconds=step_seconds,
    )
    profile = POLICY_PROFILES[policy_name]
    events = _events_from_samples(
        telemetry["samples"],
        norad_cat_id=record.norad_cat_id,
        scenario=scenario_name,
        policy=profile,
    )
    return {
        "data_kind": "simulated_event_workflow",
        "scenario": scenario_name,
        "policy": policy_name,
        "simulation_version": SIMULATION_VERSION,
        "generated_at": telemetry["generated_at"],
        "seed": seed,
        "norad_cat_id": record.norad_cat_id,
        "object_name": record.object_name,
        "event_count": len(events),
        "events": events,
        "runbook_summary": _runbook_summary(events, scenario=scenario_name, policy=profile),
        "limitations": LIMITATIONS,
    }


def compare_policies(
    record: SatelliteOrbitRecord,
    *,
    scenario: str,
    seed: int | None = None,
    duration_minutes: int = 60,
    step_seconds: int = 60,
) -> dict[str, Any]:
    scenario_name = validate_scenario(scenario)
    policies: dict[str, dict[str, Any]] = {}
    for policy_name in ["conservative_ops", "balanced_ops", "relaxed_ops"]:
        event_payload = generate_events(
            record,
            scenario=scenario_name,
            policy=policy_name,
            seed=seed,
            duration_minutes=duration_minutes,
            step_seconds=step_seconds,
        )
        events = event_payload["events"]
        warning_events = [event for event in events if event["severity"] == "warning"]
        critical_events = [event for event in events if event["severity"] == "critical"]
        policies[policy_name] = {
            "event_count": len(events),
            "first_warning_time": warning_events[0]["event_time"] if warning_events else None,
            "first_critical_time": critical_events[0]["event_time"] if critical_events else None,
            "top_affected_subsystem": _top_subsystem(events),
            "recommended_operator_action": POLICY_PROFILES[policy_name].recommended_operator_action,
            "policy_notes": POLICY_PROFILES[policy_name].notes,
        }

    return {
        "data_kind": "simulated_ops_policy_comparison",
        "scenario": scenario_name,
        "simulation_version": SIMULATION_VERSION,
        "seed": seed,
        "norad_cat_id": record.norad_cat_id,
        "object_name": record.object_name,
        "policies": policies,
        "limitations": LIMITATIONS,
    }


def _events_from_samples(
    samples: list[dict[str, Any]],
    *,
    norad_cat_id: int,
    scenario: str,
    policy: PolicyProfile,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    persistence: dict[tuple[str, Severity], int] = {}
    last_severity_by_metric: dict[str, Severity] = {}

    for sample in samples:
        metric = sample["measurement_name"]
        if metric not in policy.warning_thresholds:
            continue
        value = float(sample["measurement_value"])
        severity, threshold = _severity_for(metric, value, policy)
        if severity == "info":
            persistence[(metric, "warning")] = 0
            persistence[(metric, "critical")] = 0
            last_severity_by_metric.pop(metric, None)
            continue
        key = (metric, severity)
        persistence[key] = persistence.get(key, 0) + 1
        if persistence[key] < policy.required_persistence:
            continue
        if last_severity_by_metric.get(metric) == severity:
            continue
        last_severity_by_metric[metric] = severity
        events.append(
            {
                "event_id": f"SIM-{norad_cat_id}-{scenario}-{policy.name}-{len(events) + 1:03d}",
                "event_time": sample["source_event_time"],
                "subsystem": sample["subsystem"],
                "severity": severity,
                "scenario": scenario,
                "policy": policy.name,
                "triggered_by": metric,
                "measurement_value": value,
                "threshold": threshold,
                "summary": _event_summary(sample["subsystem"], metric, value, severity),
                "recommended_operator_check": _operator_check(sample["subsystem"], severity),
                "is_simulated": True,
            }
        )
    return events


def _scenario_values(
    scenario: str, fraction: float, rng: random.Random) -> list[tuple[str, str, float, str]]:
    battery_temp = 22.0 + rng.uniform(-0.2, 0.2)
    bus_voltage = 28.2 + rng.uniform(-0.03, 0.03)
    downlink_margin = 8.4 + rng.uniform(-0.08, 0.08)
    payload_current = 1.8 + rng.uniform(-0.02, 0.02)
    pointing_error = 0.05 + rng.uniform(-0.005, 0.005)

    if scenario == "thermal_drift":
        battery_temp = 24.0 + 38.0 * fraction + rng.uniform(-0.15, 0.15)
    elif scenario == "power_drop":
        bus_voltage = 28.2 - 3.4 * fraction + rng.uniform(-0.03, 0.03)
        payload_current = 1.8 - 0.55 * fraction + rng.uniform(-0.02, 0.02)
    elif scenario == "comms_degradation":
        downlink_margin = 8.4 - 7.6 * fraction + rng.uniform(-0.08, 0.08)
        pointing_error = 0.05 + 0.22 * fraction + rng.uniform(-0.005, 0.005)

    return [
        ("power", "bus_voltage_v", bus_voltage, "V"),
        ("thermal", "battery_temperature_c", battery_temp, "degC"),
        ("communications", "downlink_margin_db", downlink_margin, "dB"),
        ("payload", "payload_current_a", payload_current, "A"),
        ("attitude_mode", "pointing_error_deg", pointing_error, "deg"),
    ]


def _sample_status(metric: str, value: float) -> str:
    balanced = POLICY_PROFILES["balanced_ops"]
    severity, _threshold = _severity_for(metric, value, balanced)
    return severity


def _severity_for(metric: str, value: float, policy: PolicyProfile) -> tuple[Severity, float | None]:
    if metric == "battery_temperature_c":
        if value >= policy.critical_thresholds[metric]:
            return "critical", policy.critical_thresholds[metric]
        if value >= policy.warning_thresholds[metric]:
            return "warning", policy.warning_thresholds[metric]
    if metric in {"bus_voltage_v", "downlink_margin_db"}:
        if value <= policy.critical_thresholds[metric]:
            return "critical", policy.critical_thresholds[metric]
        if value <= policy.warning_thresholds[metric]:
            return "warning", policy.warning_thresholds[metric]
    return "info", None


def _event_summary(subsystem: str, metric: str, value: float, severity: Severity) -> str:
    return f"{severity.title()} simulated {subsystem} event: {metric} reached {value:g}."


def _operator_check(subsystem: str, severity: Severity) -> str:
    checks = {
        "thermal": "Review thermal trend, payload duty cycle, and recent eclipse/contact context.",
        "power": "Compare bus voltage trend with payload load and expected sunlight/eclipse period.",
        "communications": "Check next contact geometry, downlink margin assumptions, and antenna pointing context.",
    }
    prefix = "Immediate" if severity == "critical" else "Focused"
    return f"{prefix} check: {checks.get(subsystem, 'Review subsystem trend and recent scenario context.')}"


def _runbook_summary(events: list[dict[str, Any]], *, scenario: str, policy: PolicyProfile) -> str:
    if not events:
        return (
            f"No warning or critical events were generated from simulated spacecraft telemetry for "
            f"scenario '{scenario}' under {policy.name}. Continue nominal review; this is not live spacecraft telemetry."
        )
    first = events[0]
    critical_count = sum(1 for event in events if event["severity"] == "critical")
    return (
        f"Simulated spacecraft telemetry for scenario '{scenario}' produced {len(events)} event(s) "
        f"under {policy.name}; first affected subsystem is {first['subsystem']} at {first['event_time']}. "
        f"Critical events: {critical_count}. Recommended action: {policy.recommended_operator_action}"
    )


def _top_subsystem(events: list[dict[str, Any]]) -> str | None:
    if not events:
        return None
    counts: dict[str, int] = {}
    for event in events:
        counts[event["subsystem"]] = counts.get(event["subsystem"], 0) + 1
    return max(counts, key=lambda subsystem: counts[subsystem])


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _ensure_utc(value).isoformat().replace("+00:00", "Z")
