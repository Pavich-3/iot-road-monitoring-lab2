from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))  # Allow imports from the repository when script is run directly.

from app.shared.sensor_models import EnvironmentalSensor, ParkingSensor, SmartEnergySensor, TrafficLightSensor
from app.usecases.sensor_generator import ReferenceBasedSyntheticFactory


GENERATED_DIR = REPO_ROOT / "data" / "generated"


def parking_row_from_message(message: ParkingSensor) -> dict[str, object]:
    return {
        "timestamp": message.timestamp.isoformat(),  # Persist generated timestamp as text for CSV.
        "total_slots": message.payload.total_slots,  # Persist parking capacity.
        "occupied_slots": message.payload.occupied_slots,  # Persist occupancy.
        "free_slots": message.payload.free_slots,  # Persist derived free capacity.
        "occupancy_rate": message.payload.occupancy_rate,  # Persist normalized occupancy.
        "barrier_state": message.payload.barrier_state,  # Persist barrier state.
        "queue_length": message.payload.queue_length,  # Persist queue estimate.
        "area": message.location.area,  # Persist zone name.
        "latitude": message.location.latitude,  # Persist location for analysis.
        "longitude": message.location.longitude,  # Persist location for analysis.
    }


def traffic_light_row_from_message(message: TrafficLightSensor) -> dict[str, object]:
    return {
        "timestamp": message.timestamp.isoformat(),  # Persist generated timestamp as text for CSV.
        "intersection_id": message.metadata.sensor_id,  # Persist reference intersection identifier.
        "current_phase": message.payload.current_phase,  # Persist signal phase.
        "vehicle_count": message.payload.vehicle_count,  # Persist traffic load.
        "remaining_time_sec": message.payload.remaining_time_sec,  # Persist current phase timer.
        "cycle_time_sec": message.payload.cycle_time_sec,  # Persist full cycle length.
        "pedestrian_request": message.payload.pedestrian_request,  # Persist crossing request state.
        "latitude": message.location.latitude,  # Persist location for analysis.
        "longitude": message.location.longitude,  # Persist location for analysis.
    }


def environmental_row_from_message(message: EnvironmentalSensor) -> dict[str, object]:
    return {
        "timestamp": message.timestamp.isoformat(),  # Persist generated timestamp as text for CSV.
        "temperature_c": message.payload.temperature_c,  # Persist noisy environmental temperature.
        "humidity_pct": message.payload.humidity_pct,  # Persist noisy humidity.
        "pm2_5": message.payload.pm2_5,  # Persist noisy PM2.5 concentration.
        "pm10": message.payload.pm10,  # Persist noisy PM10 concentration.
        "co2_ppm": message.payload.co2_ppm,  # Persist noisy CO2 concentration.
        "latitude": message.location.latitude,  # Persist location for analysis.
        "longitude": message.location.longitude,  # Persist location for analysis.
    }


def energy_row_from_message(message: SmartEnergySensor) -> dict[str, object]:
    return {
        "timestamp": message.timestamp.isoformat(),  # Persist generated timestamp as text for CSV.
        "voltage_v": message.payload.voltage_v,  # Persist noisy voltage.
        "current_a": message.payload.current_a,  # Persist noisy current.
        "power_kw": message.payload.power_kw,  # Persist noisy power.
        "frequency_hz": message.payload.frequency_hz,  # Persist noisy grid frequency.
        "transformer_temp_c": message.payload.transformer_temp_c,  # Persist noisy transformer temperature.
        "latitude": message.location.latitude,  # Persist location for analysis.
        "longitude": message.location.longitude,  # Persist location for analysis.
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)  # Stable field order makes files easier to review in defense.
        writer.writeheader()  # CSV header preserves academic report structure.
        writer.writerows(rows)  # Dump all synthesized rows for one domain.


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic sensor data from lightweight reference CSV samples."
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=100,
        help="Number of rows to generate for each generated CSV file.",
    )
    args = parser.parse_args()

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    factory = ReferenceBasedSyntheticFactory(seed=42)  # Fixed seed gives deterministic outputs for the same row count.

    parking_rows: list[dict[str, object]] = []  # CSV-ready rows for parking dataset.
    traffic_rows: list[dict[str, object]] = []  # CSV-ready rows for traffic light dataset.
    environmental_rows: list[dict[str, object]] = []  # CSV-ready rows for environmental dataset.
    energy_rows: list[dict[str, object]] = []  # CSV-ready rows for energy dataset.
    jsonl_messages: list[str] = []  # Ready-to-publish SensorMessage JSON lines.

    for _ in range(args.rows):
        parking_message = factory.build_parking_sensor()  # Generate one parking message from transport reference sample.
        traffic_message = factory.build_traffic_light_sensor()  # Generate one traffic light message from transport reference sample.
        environmental_message = factory.build_environmental_sensor()  # Generate one environmental message from environmental reference sample.
        energy_message = factory.build_energy_sensor()  # Generate one energy message from energy reference sample.

        parking_rows.append(parking_row_from_message(parking_message))  # Convert message to flat CSV row.
        traffic_rows.append(traffic_light_row_from_message(traffic_message))  # Convert message to flat CSV row.
        environmental_rows.append(environmental_row_from_message(environmental_message))  # Convert message to flat CSV row.
        energy_rows.append(energy_row_from_message(energy_message))  # Convert message to flat CSV row.

        jsonl_messages.extend(
            [
                parking_message.model_dump_json(),  # MQTT-ready universal JSON message.
                traffic_message.model_dump_json(),  # MQTT-ready universal JSON message.
                environmental_message.model_dump_json(),  # MQTT-ready universal JSON message.
                energy_message.model_dump_json(),  # MQTT-ready universal JSON message.
            ]
        )

    write_csv(
        GENERATED_DIR / "parking_synthetic.csv",
        [
            "timestamp",
            "total_slots",
            "occupied_slots",
            "free_slots",
            "occupancy_rate",
            "barrier_state",
            "queue_length",
            "area",
            "latitude",
            "longitude",
        ],
        parking_rows,
    )
    write_csv(
        GENERATED_DIR / "traffic_light_synthetic.csv",
        [
            "timestamp",
            "intersection_id",
            "current_phase",
            "vehicle_count",
            "remaining_time_sec",
            "cycle_time_sec",
            "pedestrian_request",
            "latitude",
            "longitude",
        ],
        traffic_rows,
    )
    write_csv(
        GENERATED_DIR / "environmental_synthetic.csv",
        [
            "timestamp",
            "temperature_c",
            "humidity_pct",
            "pm2_5",
            "pm10",
            "co2_ppm",
            "latitude",
            "longitude",
        ],
        environmental_rows,
    )
    write_csv(
        GENERATED_DIR / "energy_synthetic.csv",
        [
            "timestamp",
            "voltage_v",
            "current_a",
            "power_kw",
            "frequency_hz",
            "transformer_temp_c",
            "latitude",
            "longitude",
        ],
        energy_rows,
    )

    with (GENERATED_DIR / "sensor_messages.jsonl").open("w", encoding="utf-8") as target:
        for line in jsonl_messages:
            target.write(line)  # Write one complete SensorMessage per line.
            target.write("\n")  # JSONL format requires newline-separated JSON objects.

    print(f"Generated synthetic datasets in {GENERATED_DIR}")  # Output folder summary for quick terminal feedback.
    print(f"Rows per CSV: {args.rows}")  # Confirm requested dataset size.
    print(f"Total SensorMessage JSONL lines: {len(jsonl_messages)}")  # Confirm total publishable message count.


if __name__ == "__main__":
    main()
