from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import List

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from core.weather_analyzer import WeatherAnalyzer


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"
ALLOWED_EXTENSIONS = {".csv"}


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024


def get_sample_files() -> List[str]:
    """Возвращает список демонстрационных CSV-файлов."""

    return sorted(file.name for file in DATA_DIR.glob("*.csv"))


def is_allowed_csv(filename: str) -> bool:
    """Проверяет расширение файла."""

    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def save_records_to_session(analyzer: WeatherAnalyzer, source_name: str) -> None:
    """Сохраняет текущий температурный ряд в пользовательскую сессию."""

    payload = analyzer.to_session_payload()
    session["dates"] = payload["dates"]
    session["temperatures"] = payload["temperatures"]
    session["source_name"] = source_name
    session["undo_stack"] = []
    session["is_smoothed"] = False


def get_analyzer_from_session() -> WeatherAnalyzer:
    """Восстанавливает анализатор из Flask-сессии."""

    if "dates" not in session or "temperatures" not in session:
        raise ValueError("Сначала загрузите или выберите CSV-файл")

    return WeatherAnalyzer.from_dates_and_temperatures(
        date_values=session["dates"],
        temperature_values=session["temperatures"],
    )


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", sample_files=get_sample_files())


@app.route("/load", methods=["POST"])
def load_dataset():
    """Загружает пользовательский CSV или выбранный демонстрационный файл."""

    uploaded_file = request.files.get("csv_file")
    selected_sample = request.form.get("sample_file", "").strip()

    try:
        if uploaded_file and uploaded_file.filename:
            if not is_allowed_csv(uploaded_file.filename):
                flash("Можно загружать только CSV-файлы.", "error")
                return redirect(url_for("index"))

            safe_name = f"{uuid.uuid4().hex}.csv"
            saved_path = UPLOAD_DIR / safe_name
            uploaded_file.save(saved_path)

            analyzer = WeatherAnalyzer(WeatherAnalyzer.read_csv(str(saved_path)))
            save_records_to_session(analyzer, uploaded_file.filename)
        else:
            if not selected_sample:
                flash("Выберите демонстрационный файл или загрузите свой CSV.", "error")
                return redirect(url_for("index"))

            sample_path = DATA_DIR / selected_sample

            if not sample_path.exists():
                flash("Выбранный демонстрационный файл не найден.", "error")
                return redirect(url_for("index"))

            analyzer = WeatherAnalyzer(WeatherAnalyzer.read_csv(str(sample_path)))
            save_records_to_session(analyzer, selected_sample)

        threshold = request.form.get("threshold", "20")
        session["threshold"] = float(threshold)

        return redirect(url_for("dashboard"))

    except Exception as error:
        flash(str(error), "error")
        return redirect(url_for("index"))


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    """Показывает результаты анализа."""

    try:
        analyzer = get_analyzer_from_session()

        if request.method == "POST":
            session["threshold"] = float(request.form.get("threshold", "20"))

        threshold = float(session.get("threshold", 20.0))

        monthly_averages = analyzer.calculate_monthly_averages()
        sorted_months = analyzer.sort_months_by_average_temperature()
        warmest_day = analyzer.find_warmest_day()
        coldest_day = analyzer.find_coldest_day()
        days_above = analyzer.get_days_above_temperature(threshold)
        preview_rows = analyzer.get_basic_table(limit=20)

        return render_template(
            "dashboard.html",
            source_name=session.get("source_name", "неизвестный файл"),
            threshold=threshold,
            monthly_averages=monthly_averages,
            sorted_months=sorted_months,
            warmest_day=warmest_day,
            coldest_day=coldest_day,
            days_above=days_above,
            days_above_count=len(days_above),
            preview_rows=preview_rows,
            records_count=len(analyzer.records),
            can_undo=bool(session.get("undo_stack")),
            is_smoothed=bool(session.get("is_smoothed")),
        )

    except Exception as error:
        flash(str(error), "error")
        return redirect(url_for("index"))


@app.route("/smooth", methods=["POST"])
def smooth():
    """Применяет сглаживание скользящим средним.

    Перед изменением температур текущий ряд помещается в стек отмены.
    """

    try:
        analyzer = get_analyzer_from_session()
        undo_stack = session.get("undo_stack", [])

        undo_stack.append(session["temperatures"])
        session["undo_stack"] = undo_stack
        session["temperatures"] = analyzer.moving_average_7_days()
        session["is_smoothed"] = True

        flash("Сглаживание выполнено. Предыдущее состояние сохранено в стеке отмены.", "success")
        return redirect(url_for("dashboard"))

    except Exception as error:
        flash(str(error), "error")
        return redirect(url_for("dashboard"))


@app.route("/undo", methods=["POST"])
def undo():
    """Отменяет последнее преобразование температурного ряда."""

    try:
        undo_stack = session.get("undo_stack", [])

        if not undo_stack:
            flash("Стек отмены пуст: нечего отменять.", "error")
            return redirect(url_for("dashboard"))

        previous_temperatures = undo_stack.pop()
        session["temperatures"] = previous_temperatures
        session["undo_stack"] = undo_stack
        session["is_smoothed"] = bool(undo_stack)

        flash("Последнее преобразование отменено: ряд восстановлен из стека.", "success")
        return redirect(url_for("dashboard"))

    except Exception as error:
        flash(str(error), "error")
        return redirect(url_for("dashboard"))


@app.route("/reset", methods=["POST"])
def reset():
    """Очищает текущую сессию анализа."""

    session.clear()
    flash("Текущий набор данных сброшен.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    UPLOAD_DIR.mkdir(exist_ok=True)
    app.run(debug=True)