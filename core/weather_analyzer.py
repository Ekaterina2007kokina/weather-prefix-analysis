from __future__ import annotations

import csv
from collections import deque
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class WeatherRecord:
    """Одна дневная запись погоды."""

    date: date
    temperature: float


@dataclass
class MonthAverage:
    """Средняя температура месяца."""

    month_number: int
    month_name: str
    days_count: int
    average_temperature: float


@dataclass
class ExtremumDay:
    """Самый теплый или самый холодный день."""

    date: date
    temperature: float


class PrefixSums:
    """Префиксные суммы температур.

    prefix[i] хранит сумму температур на полуинтервале [0; i).
    Благодаря этому сумма температур на любом интервале [left; right)
    вычисляется за O(1): prefix[right] - prefix[left].
    """

    def __init__(self, values: List[float]) -> None:
        self.prefix: List[float] = [0.0]
        current_sum = 0.0

        for value in values:
            current_sum += value
            self.prefix.append(current_sum)

    def range_sum(self, left: int, right: int) -> float:
        """Возвращает сумму на полуинтервале [left; right)."""

        if left < 0 or right > len(self.prefix) - 1 or left > right:
            raise IndexError("Некорректные границы интервала")

        return self.prefix[right] - self.prefix[left]


class TemperatureBSTNode:
    """Узел бинарного дерева поиска по температуре."""

    def __init__(self, temperature: float, record_date: date) -> None:
        self.temperature = temperature
        self.dates: List[date] = [record_date]
        self.left: Optional["TemperatureBSTNode"] = None
        self.right: Optional["TemperatureBSTNode"] = None


class TemperatureBST:
    """Бинарное дерево поиска.

    Ключ — температура.
    Значение — список дат, потому что одинаковая температура может
    встречаться в разные дни.
    """

    def __init__(self) -> None:
        self.root: Optional[TemperatureBSTNode] = None

    def insert(self, temperature: float, record_date: date) -> None:
        """Вставляет температуру и дату в дерево."""

        if self.root is None:
            self.root = TemperatureBSTNode(temperature, record_date)
            return

        self._insert_recursive(self.root, temperature, record_date)

    def _insert_recursive(
        self,
        node: TemperatureBSTNode,
        temperature: float,
        record_date: date,
    ) -> None:
        if temperature == node.temperature:
            node.dates.append(record_date)
        elif temperature < node.temperature:
            if node.left is None:
                node.left = TemperatureBSTNode(temperature, record_date)
            else:
                self._insert_recursive(node.left, temperature, record_date)
        else:
            if node.right is None:
                node.right = TemperatureBSTNode(temperature, record_date)
            else:
                self._insert_recursive(node.right, temperature, record_date)

    def get_dates_above(self, threshold: float) -> List[Tuple[date, float]]:
        """Возвращает все даты с температурой выше порога.

        Используется рекурсивный обход дерева. Если температура текущего
        узла больше порога, подходят сам узел и часть правого поддерева,
        а в левом поддереве тоже могут быть значения выше порога.
        Если температура текущего узла не больше порога, всё левое
        поддерево можно отбросить.
        """

        result: List[Tuple[date, float]] = []
        self._collect_greater_recursive(self.root, threshold, result)
        result.sort(key=lambda item: (item[0], item[1]))
        return result

    def _collect_greater_recursive(
        self,
        node: Optional[TemperatureBSTNode],
        threshold: float,
        result: List[Tuple[date, float]],
    ) -> None:
        if node is None:
            return

        if node.temperature > threshold:
            self._collect_greater_recursive(node.left, threshold, result)

            for record_date in node.dates:
                result.append((record_date, node.temperature))

            self._collect_greater_recursive(node.right, threshold, result)
        else:
            self._collect_greater_recursive(node.right, threshold, result)


class WeatherAnalyzer:
    """Класс с алгоритмами анализа температурного ряда."""

    MONTH_NAMES: Dict[int, str] = {
        1: "Январь",
        2: "Февраль",
        3: "Март",
        4: "Апрель",
        5: "Май",
        6: "Июнь",
        7: "Июль",
        8: "Август",
        9: "Сентябрь",
        10: "Октябрь",
        11: "Ноябрь",
        12: "Декабрь",
    }

    def __init__(self, records: List[WeatherRecord]) -> None:
        if not records:
            raise ValueError("Список погодных записей пуст")

        self.records = sorted(records, key=lambda record: record.date)
        self.temperatures = [record.temperature for record in self.records]
        self.prefix_sums = PrefixSums(self.temperatures)

        self.temperature_tree = TemperatureBST()
        for record in self.records:
            self.temperature_tree.insert(record.temperature, record.date)

    @staticmethod
    def read_csv(file_path: str) -> List[WeatherRecord]:
        """Читает CSV-файл с колонками date и temperature."""

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")

        records: List[WeatherRecord] = []

        with path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)

            required_columns = {"date", "temperature"}
            current_columns = set(reader.fieldnames or [])

            if not required_columns.issubset(current_columns):
                raise ValueError("CSV должен содержать колонки date и temperature")

            for row_number, row in enumerate(reader, start=2):
                try:
                    record_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
                    temperature = float(row["temperature"])
                except ValueError as error:
                    raise ValueError(
                        f"Ошибка в строке {row_number}: дата должна иметь формат "
                        f"YYYY-MM-DD, температура должна быть числом"
                    ) from error

                records.append(WeatherRecord(date=record_date, temperature=temperature))

        if not records:
            raise ValueError("CSV-файл не содержит записей")

        return records

    @staticmethod
    def from_dates_and_temperatures(
        date_values: List[str],
        temperature_values: List[float],
    ) -> "WeatherAnalyzer":
        """Создает анализатор из данных, сохраненных в Flask-сессии."""

        if len(date_values) != len(temperature_values):
            raise ValueError("Количество дат не совпадает с количеством температур")

        records = [
            WeatherRecord(
                date=datetime.strptime(date_text, "%Y-%m-%d").date(),
                temperature=float(temperature),
            )
            for date_text, temperature in zip(date_values, temperature_values)
        ]

        return WeatherAnalyzer(records)

    def calculate_monthly_averages(self) -> List[MonthAverage]:
        """Вычисляет среднюю температуру за каждый месяц через префиксные суммы."""

        month_ranges: Dict[int, List[int]] = {}

        for index, record in enumerate(self.records):
            month_ranges.setdefault(record.date.month, []).append(index)

        averages: List[MonthAverage] = []

        for month_number in sorted(month_ranges):
            indexes = month_ranges[month_number]
            left = indexes[0]
            right = indexes[-1] + 1
            days_count = right - left
            total_temperature = self.prefix_sums.range_sum(left, right)
            average_temperature = total_temperature / days_count

            averages.append(
                MonthAverage(
                    month_number=month_number,
                    month_name=self.MONTH_NAMES[month_number],
                    days_count=days_count,
                    average_temperature=average_temperature,
                )
            )

        return averages

    def sort_months_by_average_temperature(self) -> List[MonthAverage]:
        """Сортирует месяцы по средней температуре.

        Используется встроенная сортировка Python. Для учебной задачи это
        допустимый вариант сортировки списка объектов.
        """

        monthly_averages = self.calculate_monthly_averages()
        return sorted(monthly_averages, key=lambda item: item.average_temperature)

    def find_warmest_day(self) -> ExtremumDay:
        """Находит самый теплый день линейным поиском."""

        max_record = self.records[0]

        for record in self.records[1:]:
            if record.temperature > max_record.temperature:
                max_record = record

        return ExtremumDay(date=max_record.date, temperature=max_record.temperature)

    def find_coldest_day(self) -> ExtremumDay:
        """Находит самый холодный день линейным поиском."""

        min_record = self.records[0]

        for record in self.records[1:]:
            if record.temperature < min_record.temperature:
                min_record = record

        return ExtremumDay(date=min_record.date, temperature=min_record.temperature)

    def get_days_above_temperature(self, threshold: float) -> List[Tuple[date, float]]:
        """Ищет дни с температурой выше порога через бинарное дерево поиска."""

        return self.temperature_tree.get_dates_above(threshold)

    def moving_average_7_days(self) -> List[float]:
        """Сглаживает температурный ряд скользящим средним с окном 7 дней.

        Для хранения последних значений используется очередь deque.
        В первые 6 дней среднее считается по фактически доступному числу дней,
        поэтому длина результата совпадает с длиной исходного ряда.
        """

        window: deque[float] = deque()
        window_sum = 0.0
        smoothed: List[float] = []

        for temperature in self.temperatures:
            window.append(temperature)
            window_sum += temperature

            if len(window) > 7:
                removed_value = window.popleft()
                window_sum -= removed_value

            smoothed.append(round(window_sum / len(window), 2))

        return smoothed

    def get_basic_table(self, limit: int = 20) -> List[Dict[str, object]]:
        """Возвращает первые строки временного ряда для отображения в HTML."""

        return [
            {
                "date": record.date.strftime("%Y-%m-%d"),
                "temperature": round(record.temperature, 2),
            }
            for record in self.records[:limit]
        ]

    def to_session_payload(self) -> Dict[str, List[object]]:
        """Подготавливает данные для сохранения в Flask-сессии."""

        return {
            "dates": [record.date.strftime("%Y-%m-%d") for record in self.records],
            "temperatures": [round(record.temperature, 2) for record in self.records],
        }
