import datetime as dt

from app.constants import subject_marker
from app.formatting import format_homework, format_lessons
from app.models import Homework, Lesson


def test_known_subject_gets_a_marker():
    assert subject_marker("Математика") == "🧮 "
    assert subject_marker("математика") == "🧮 "  # case-insensitive
    assert subject_marker("  Физика  ") == "🟠 "  # tolerates whitespace


def test_unknown_subject_gets_no_marker():
    assert subject_marker("Рисование") == ""


def test_history_and_pe_have_their_own_thematic_markers():
    assert subject_marker("История") == "🏛️ "
    assert subject_marker("Физкультура") == "🏐 "


def test_serbian_cyrillic_and_latin_variants_match_the_same_marker():
    # Cyrillic
    assert subject_marker("Немачки језик") == "💚 "
    assert subject_marker("Историја") == "🏛️ "
    # Latin, with diacritics
    assert subject_marker("Nemački jezik") == "💚 "
    assert subject_marker("Fizičko vaspitanje") == "🏐 "
    # Latin, typed without diacritics (very common in practice)
    assert subject_marker("Nemacki jezik") == "💚 "
    assert subject_marker("Fizicko") == "🏐 "
    assert subject_marker("Geografija") == "🔵 "
    # Short abbreviation some Serbian schools use
    assert subject_marker("ТИО") == "🩷 "
    assert subject_marker("tio") == "🩷 "


def test_exact_school_subject_names_from_the_real_schedule():
    # These are the exact (ALL CAPS Latin) subject names as they appear in
    # the actual schedule, which previously matched nothing.
    assert subject_marker("SRPSKI JEZIK I KNJIŽEVNOST") == "📖 "
    assert subject_marker("MUZIČKA KULTURA") == "🎼 "
    assert subject_marker("FIZIČKO I ZDRAVSTVENO VASPITANJE") == "🏐 "
    assert subject_marker("BIOLOGIJA") == "🍃 "
    assert subject_marker("ISTORIJA") == "🏛️ "
    assert subject_marker("MATEMATIKA") == "🧮 "
    assert subject_marker("INFORMATIKA I RAČUNARSTVO") == "💻 "


def test_format_lessons_includes_subject_marker():
    lesson = Lesson(subject="Химия", start_time=dt.time(10, 0))
    text = format_lessons([lesson])
    assert "🟣 Химия" in text


def test_format_lessons_unknown_subject_has_no_stray_marker():
    lesson = Lesson(subject="Рисование", start_time=dt.time(10, 0))
    text = format_lessons([lesson])
    assert text.endswith("Рисование")
    assert "  Рисование" not in text  # no leftover double space from an empty marker


def test_format_homework_includes_subject_marker():
    hw = Homework(subject="География", description="§12", due_date=dt.date(2026, 8, 20))
    text = format_homework([hw])
    assert "🔵 <b>География</b>" in text
