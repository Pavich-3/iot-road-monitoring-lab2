from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.shared.sensor_models import EnvironmentalSensor, ParkingSensor, SmartEnergySensor, TrafficLightSensor
from app.usecases.sensor_generator import ReferenceBasedSyntheticFactory


GENERATED_DIR = REPO_ROOT / "data" / "generated"


def parking_row_from_message(message: ParkingSensor) -> dict[str, object]:
    return {
        "timestamp": message.timestamp.isoformat(),
        "total_slots": message.payload.total_slots,
        "occupied_slots": message.payload.occupied_slots,
        "free_slots": message.payload.free_slots,
        "occupancy_rate": message.payload.occupancy_rate,
        "barrier_state": message.payload.barrier_state,
        "queue_length": message.payload.queue_length,
        "area": message.location.area,
        "latitude": message.location.latitude,
        "longitude": message.location.longitude,
    }


def traffic_light_row_from_message(message: TrafficLightSensor) -> dict[str, object]:
    return {
        "timestamp": message.timestamp.isoformat(),
        "intersection_id": message.metadata.sensor_id,
        "current_phase": message.payload.current_phase,
        "vehicle_count": message.payload.vehicle_count,
        "remaining_time_sec": message.payload.remaining_time_sec,
        "cycle_time_sec": message.payload.cycle_time_sec,
        "pedestrian_request": message.payload.pedestrian_request,
        "latitude": message.location.latitude,
        "longitude": message.location.longitude,
    }


def environmental_row_from_message(message: EnvironmentalSensor) -> dict[str, object]:
    return {
        "timestamp": message.timestamp.isoformat(),
        "temperature_c": message.payload.temperature_c,
        "humidity_pct": message.payload.humidity_pct,
        "pm2_5": message.payload.pm2_5,
        "pm10": message.payload.pm10,
        "co2_ppm": message.payload.co2_ppm,
        "latitude": message.location.latitude,
        "longitude": message.location.longitude,
    }


def energy_row_from_message(message: SmartEnergySensor) -> dict[str, object]:
    return {
        "timestamp": message.timestamp.isoformat(),
        "voltage_v": message.payload.voltage_v,
        "current_a": message.payload.current_a,
        "power_kw": message.payload.power_kw,
        "frequency_hz": message.payload.frequency_hz,
        "transformer_temp_c": message.payload.transformer_temp_c,
        "latitude": message.location.latitude,
        "longitude": message.location.longitude,
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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

    factory = ReferenceBasedSyntheticFactory(seed=42)

    parking_rows: list[dict[str, object]] = []
    traffic_rows: list[dict[str, object]] = []
    environmental_rows: list[dict[str, object]] = []
    energy_rows: list[dict[str, object]] = []
    jsonl_messages: list[str] = []

    for _ in range(args.rows):
        parking_message = factory.build_parking_sensor()
        traffic_message = factory.build_traffic_light_sensor()
        environmental_message = factory.build_environmental_sensor()
        energy_message = factory.build_energy_sensor()

        parking_rows.append(parking_row_from_message(parking_message))
        traffic_rows.append(traffic_light_row_from_message(traffic_message))
        environmental_rows.append(environmental_row_from_message(environmental_message))
        energy_rows.append(energy_row_from_message(energy_message))

        jsonl_messages.extend(
            [
                parking_message.model_dump_json(),
                traffic_message.model_dump_json(),
                environmental_message.model_dump_json(),
                energy_message.model_dump_json(),
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
            target.write(line)
            target.write("\n")

    print(f"Generated synthetic datasets in {GENERATED_DIR}")
    print(f"Rows per CSV: {args.rows}")
    print(f"Total SensorMessage JSONL lines: {len(jsonl_messages)}")


if __name__ == "__main__":
    main()
