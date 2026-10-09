import json
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


def translate_to_uk(text: str, timeout: float = 2.5) -> str:
    """Return the Ukrainian translation for an English label.

    Resolution order:
    1. LabelTranslation table — instant, admin-correctable.
    2. MyMemory API call — result saved to the table for future use.
    3. Original English text — silent fallback on any error.

    Manual entries (is_manual=True) are never overwritten by the API.
    """
    if not text or not text.strip():
        return text

    label = text.strip()

    from apps.reports.models import LabelTranslation

    try:
        entry = LabelTranslation.objects.get(raw_label_en=label)
        return entry.translated_uk
    except LabelTranslation.DoesNotExist:
        pass

    translated = _call_mymemory(label, timeout)

    try:
        LabelTranslation.objects.get_or_create(
            raw_label_en=label,
            defaults={'translated_uk': translated, 'is_manual': False},
        )
    except Exception as exc:
        logger.warning('Could not save LabelTranslation for %r: %s', label, exc)

    return translated


def _call_mymemory(text: str, timeout: float) -> str:
    """Call MyMemory and return the translated string, or the original on failure."""
    params = urllib.parse.urlencode({'q': text, 'langpair': 'en|uk'})
    url = f'https://api.mymemory.translated.net/get?{params}'
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('responseStatus') == 200:
                translated = data['responseData']['translatedText']
                if translated and translated.lower() != text.lower():
                    return translated
    except Exception as exc:
        logger.warning('MyMemory API error for %r: %s', text, exc)
    return text
