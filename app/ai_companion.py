from __future__ import annotations

from dataclasses import dataclass

from anthropic import AsyncAnthropic

from app.config import config

SYSTEM_PROMPT = """Ты — тёплый, спокойный собеседник в приватном Telegram-чате ребёнка по имени {name}.
Родитель специально настроил этот чат, чтобы {name} могла(-ог) выговориться, поделиться настроением,\
пожаловаться на школу, друзей, домашние задания, усталость — на что угодно, — не боясь, что кто-то это увидит.

Как себя вести:
- Слушай и поддерживай, как добрый друг, а не как взрослый с нотациями.
- Не оценивай и не читай морали. Не занимай ничью сторону в конфликтах с друзьями/учителями/родителями резко.
- Отвечай тепло, живо, по-человечески, не слишком длинно (2-5 предложений обычно достаточно).
- Можно немного юмора и эмодзи, но не переусердствуй.
- Если жалуется на рутину/усталость/скуку/обычные подростковые обиды — это нормально, просто поддержи.

Правило безопасности (очень важно):
Весь разговор строго приватный и никогда не показывается родителю — кроме одного исключения.
Отмечай concern=true ТОЛЬКО если видишь реальные признаки серьёзной опасности: мысли о самоповреждении\
или суициде, признаки насилия или жестокого обращения дома, угрозы жизни или безопасности, что-то похожее\
на абьюз. Обычные жалобы на усталость, скуку, ссоры с друзьями, плохие оценки, конфликт с родителем\
из-за учёбы — это НЕ concern, это обычная жизнь, не поднимай тревогу по пустякам.

Если concern=true — в поле reply мягко скажи, что ты передашь это взрослому, которому можно доверять,\
и что это нормально попросить о помощи. Не пугай и не читай лекций."""

REPLY_TOOL = {
    "name": "respond",
    "description": "Send the reply to the child and flag whether this needs urgent adult attention.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reply": {
                "type": "string",
                "description": "Тёплый ответ ребёнку на русском языке.",
            },
            "concern": {
                "type": "boolean",
                "description": (
                    "true ТОЛЬКО при реальных признаках опасности (самоповреждение, суицидальные мысли, "
                    "насилие, жестокое обращение, угроза жизни). Обычные жалобы — false."
                ),
            },
            "concern_summary": {
                "type": "string",
                "description": (
                    "Если concern=true — короткое (1-2 предложения) описание сути для взрослого. "
                    "Иначе пустая строка."
                ),
            },
        },
        "required": ["reply", "concern", "concern_summary"],
    },
}


@dataclass
class AiReply:
    text: str
    concern: bool
    concern_summary: str | None


_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=config.anthropic_api_key)
    return _client


async def get_ai_reply(history: list[dict[str, str]], student_name: str) -> AiReply:
    client = _get_client()
    response = await client.messages.create(
        model=config.anthropic_model,
        max_tokens=1024,
        system=SYSTEM_PROMPT.format(name=student_name),
        messages=history,
        tools=[REPLY_TOOL],
        tool_choice={"type": "tool", "name": "respond"},
    )
    for block in response.content:
        if block.type == "tool_use":
            data = block.input
            return AiReply(
                text=str(data.get("reply") or "Извини, не получилось ответить 🙈"),
                concern=bool(data.get("concern")),
                concern_summary=(str(data["concern_summary"]) if data.get("concern_summary") else None),
            )
    return AiReply(text="Извини, не получилось ответить 🙈", concern=False, concern_summary=None)
