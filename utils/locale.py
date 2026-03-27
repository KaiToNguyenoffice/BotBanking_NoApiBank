import json
import os

_locales = {}
_locale_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "locales")


def _load_locale(lang: str) -> dict:
    if lang not in _locales:
        path = os.path.join(_locale_dir, f"{lang}.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                _locales[lang] = json.load(f)
        else:
            _locales[lang] = {}
    return _locales[lang]


def t(key: str, lang: str = "vi", **kwargs) -> str:
    """Get translated string. Falls back to Vietnamese if key not found."""
    data = _load_locale(lang)
    text = data.get(key)
    if text is None:
        # Fallback to Vietnamese
        data_vi = _load_locale("vi")
        text = data_vi.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


async def get_user_lang(session, telegram_id: int) -> str:
    """Get user language from DB. Returns 'vi' if not found."""
    from database.models import User
    from sqlalchemy import select
    result = await session.execute(
        select(User.language).where(User.telegram_id == telegram_id)
    )
    lang = result.scalar_one_or_none()
    return lang or "vi"
