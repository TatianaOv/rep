import unicodedata

DAY_NAMES = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]


def _normalize_subject(text: str) -> str:
    """Lowercase and strip Latin diacritics, so "Nemački"/"Nemacki"/"немачки"
    style variants of the same subject name all collapse onto one lookup key."""
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


# Telegram не поддерживает цветной текст в сообщениях, поэтому "цвет"/визуальный
# маркер предмета — это эмодзи перед названием. Часть предметов помечена цветным
# кружком (когда важнее сам цвет), часть — тематической картинкой (когда она
# понятнее ребёнку, чем абстрактный цвет). Египетской пирамиды в Unicode нет —
# для Истории взята классическая колонна как ближайшая по смыслу замена.
#
# Предметы в расписании бывают на русском и на сербском (кириллица и латиница,
# с диакритикой типа "č"/"ć" или без неё), поэтому у каждого предмета — несколько
# вариантов написания, ведущих к одному и тому же эмодзи. Ключи уже прогнаны
# через _normalize_subject (нижний регистр, без диакритики).
_SUBJECT_COLORS_RAW: dict[str, str] = {
    # Математика — "2 в степени"
    "математика": "x²",
    "matematika": "x²",
    # Сербский язык и литература — книга
    "сербский": "📖",
    "сербский язык": "📖",
    "српски": "📖",
    "српски језик": "📖",
    "српски језик и књижевност": "📖",
    "srpski": "📖",
    "srpski jezik": "📖",
    "srpski jezik i knjizevnost": "📖",
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
    # Биология — листок
    "биология": "🍃",
    "биологија": "🍃",
    "biologija": "🍃",
    # География
    "география": "🔵",
    "географија": "🔵",
    "geografija": "🔵",
    # История — колонна (пирамиды нет среди эмодзи Unicode)
    "история": "🏛️",
    "историја": "🏛️",
    "istorija": "🏛️",
    # Техника и технология
    "техника и технология": "🩷",
    "техника и технологија": "🩷",
    "техничко и информатичко образовање": "🩷",
    "тио": "🩷",
    "tehnika i tehnologija": "🩷",
    "tehnicko i informaticko obrazovanje": "🩷",
    "tio": "🩷",
    # Физкультура — волейбольный мяч
    "физкультура": "🏐",
    "физичко": "🏐",
    "физичко васпитање": "🏐",
    "физичко и здравствено васпитање": "🏐",
    "fizicko": "🏐",
    "fizicko vaspitanje": "🏐",
    "fizicko i zdravstveno vaspitanje": "🏐",
    # Музыкальная культура — скрипичный ключ
    "музичка култура": "🎼",
    "muzicka kultura": "🎼",
    # Информатика и вычислительная техника — ноутбук
    "информатика и рачунарство": "💻",
    "informatika i racunarstvo": "💻",
}

SUBJECT_COLORS: dict[str, str] = {_normalize_subject(k): v for k, v in _SUBJECT_COLORS_RAW.items()}


def subject_marker(subject: str) -> str:
    """Returns an emoji marker + trailing space for known subjects, or '' otherwise."""
    emoji = SUBJECT_COLORS.get(_normalize_subject(subject))
    return f"{emoji} " if emoji else ""
