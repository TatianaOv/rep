DAY_NAMES = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]

import unicodedata


def _normalize_subject(text: str) -> str:
    """Lowercase and strip Latin diacritics, so "Nemački"/"Nemacki"/"немачки"
    style variants of the same subject name all collapse onto one lookup key."""
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


# Telegram не поддерживает цветной текст в сообщениях, поэтому "цвет" предмета
# обозначается цветным эмодзи-маркером перед названием. Голубой/аквамарин и
# зелёный/салатовый делят ближайший доступный эмодзи — в Telegram нет отдельных
# кружков под эти оттенки. История и Физкультура делят красный намеренно.
#
# Предметы в расписании бывают на русском и на сербском (кириллица и латиница,
# с диакритикой типа "č"/"ć" или без неё), поэтому у каждого предмета — несколько
# вариантов написания, ведущих к одному и тому же эмодзи. Ключи уже прогнаны
# через _normalize_subject (нижний регистр, без диакритики).
_SUBJECT_COLORS_RAW: dict[str, str] = {
    # Математика
    "математика": "🟢",
    "matematika": "🟢",
    # Сербский язык
    "сербский": "🩵",
    "сербский язык": "🩵",
    "српски": "🩵",
    "српски језик": "🩵",
    "srpski": "🩵",
    "srpski jezik": "🩵",
    # Немецкий
    "немецкий": "💚",
    "немецкий язык": "💚",
    "немачки": "💚",
    "немачки језик": "💚",
    "nemacki": "💚",
    "nemacki jezik": "💚",
    # Английский
    "английский": "🩵",
    "английский язык": "🩵",
    "енглески": "🩵",
    "енглески језик": "🩵",
    "engleski": "🩵",
    "engleski jezik": "🩵",
    # Физика
    "физика": "🟠",
    "fizika": "🟠",
    # Химия
    "химия": "🟣",
    "хемија": "🟣",
    "hemija": "🟣",
    # Биология
    "биология": "🟡",
    "биологија": "🟡",
    "biologija": "🟡",
    # География
    "география": "🔵",
    "географија": "🔵",
    "geografija": "🔵",
    # История
    "история": "🔴",
    "историја": "🔴",
    "istorija": "🔴",
    # Техника и технология
    "техника и технология": "🩷",
    "техника и технологија": "🩷",
    "техничко и информатичко образовање": "🩷",
    "тио": "🩷",
    "tehnika i tehnologija": "🩷",
    "tehnicko i informaticko obrazovanje": "🩷",
    "tio": "🩷",
    # Физкультура
    "физкультура": "🔴",
    "физичко": "🔴",
    "физичко васпитање": "🔴",
    "fizicko": "🔴",
    "fizicko vaspitanje": "🔴",
}

SUBJECT_COLORS: dict[str, str] = {_normalize_subject(k): v for k, v in _SUBJECT_COLORS_RAW.items()}


def subject_marker(subject: str) -> str:
    """Returns a colored emoji + trailing space for known subjects, or '' otherwise."""
    emoji = SUBJECT_COLORS.get(_normalize_subject(subject))
    return f"{emoji} " if emoji else ""
