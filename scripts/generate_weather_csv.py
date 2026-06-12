from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"


def generate_year_weather(
    output_path: Path,
    year: int,
    base_temperature: float,
    amplitude: float,
    noise_level: float,
    phase_shift: int,
    seed: int,
) -> None:
    """Генерирует CSV с ежедневной температурой за год."""

    random.seed(seed)
    DATA_DIR.mkdir(exist_ok=True)

    start_date = date(year, 1, 1)
    end_date = date(year + 1, 1, 1)

    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["date", "temperature"])
        writer.writeheader()

        current_date = start_date

        while current_date < end_date:
            day_of_year = current_date.timetuple().tm_yday

            seasonal_component = amplitude * math.sin(
                2 * math.pi * (day_of_year - phase_shift) / 365
            )
            weekly_component = 1.5 * math.sin(2 * math.pi * day_of_year / 7)
            random_noise = random.uniform(-noise_level, noise_level)

            temperature = base_temperature + seasonal_component + weekly_component + random_noise

            writer.writerow(
                {
                    "date": current_date.strftime("%Y-%m-%d"),
                    "temperature": round(temperature, 1),
                }
            )

            current_date += timedelta(days=1)


def main() -> None:
    generate_year_weather(
        output_path=DATA_DIR / "weather_moscow_2025.csv",
        year=2025,
        base_temperature=7.0,
        amplitude=18.0,
        noise_level=3.0,
        phase_shift=100,
        seed=42,
    )

    generate_year_weather(
        output_path=DATA_DIR / "weather_saint_petersburg_2025.csv",
        year=2025,
        base_temperature=6.0,
        amplitude=15.0,
        noise_level=3.5,
        phase_shift=105,
        seed=77,
    )

    generate_year_weather(
        output_path=DATA_DIR / "weather_krasnoyarsk_2025.csv",
        year=2025,
        base_temperature=2.0,
        amplitude=27.0,
        noise_level=4.5,
        phase_shift=98,
        seed=123,
    )


if __name__ == "__main__":
    main()
