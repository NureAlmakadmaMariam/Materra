import logging
import time

from django.conf import settings
from PIL import Image

logger = logging.getLogger(__name__)


# ── Ukrainian display labels for all 14 waste class codes ────────────────────
_WASTE_LABELS_UK: dict[str, str] = {
    'concrete':     'Бетон',
    'brick':        'Цегла',
    'metal':        'Метал',
    'wood':         'Деревина',
    'glass':        'Скло',
    'plastic':      'Пластик',
    'ceramic_tile': 'Керамічна плитка',
    'asphalt':      'Асфальт',
    'gypsum':       'Гіпс',
    'insulation':   'Утеплювач',
    'mixed_debris': 'Змішані відходи',
    'soil':         'Ґрунт',
    'hazardous':    'Небезпечні відходи',
    'unknown':      'Невизначено',
}

# ── CLIP candidate phrases ────────────────────────────────────────────────────
# Each phrase is a natural-language description CLIP compares directly against
# the image embedding. Descriptive construction-waste context beats bare keywords.
# Order does not matter — CLIP scores all candidates simultaneously.
_CLIP_CANDIDATES: list[tuple[str, str]] = [
    ('chunks of concrete or concrete rubble from demolition',            'concrete'),
    ('red or clay bricks from masonry or demolition',                    'brick'),
    ('metal scrap, steel pipes, iron beams or rebar',                    'metal'),
    ('wooden planks, timber, lumber or wood debris',                     'wood'),
    ('broken glass panels, glass bottles or glass fragments',            'glass'),
    ('plastic pipes, plastic packaging or synthetic construction waste',  'plastic'),
    ('ceramic floor tiles or broken porcelain pieces',                   'ceramic_tile'),
    ('asphalt road surface, bitumen or pavement material',               'asphalt'),
    ('gypsum plasterboard, drywall or plaster construction material',    'gypsum'),
    ('insulation foam, mineral wool or fiberglass batting',              'insulation'),
    ('mixed unsorted construction and demolition debris',                'mixed_debris'),
    ('soil, dirt, gravel, sand or excavated earth',                      'soil'),
    ('hazardous chemical waste barrels or dangerous material drums',     'hazardous'),
]

# ── OCR hazard keywords ───────────────────────────────────────────────────────
_HAZARD_OCR_KEYWORDS: frozenset[str] = frozenset({
    'caution', 'warning', 'danger', 'radioactive', 'toxic',
    'flammable', 'explosive', 'hazmat', 'poison', 'corrosive',
    'biohazard', 'chemical', 'dangerous', 'harmful',
})

_VALID_SLUGS = frozenset({
    'concrete', 'brick', 'metal', 'wood', 'glass', 'plastic',
    'ceramic_tile', 'asphalt', 'gypsum', 'insulation',
    'mixed_debris', 'soil', 'hazardous', 'unknown',
})

_MODEL_ID            = 'openai/clip-vit-base-patch32'
_REVIEW_THRESHOLD    = 0.05   # below this → needs_human_review
_MIN_PRED_CONFIDENCE = 0.04   # exclude near-zero entries from the predictions array


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ocr_hazard_check(image: Image.Image) -> bool:
    """Return True if OCR finds a hazard warning keyword in the image.

    Silently returns False if pytesseract or the Tesseract binary is missing,
    so inference degrades gracefully rather than hard-failing.
    """
    try:
        import pytesseract
        text = pytesseract.image_to_string(image).lower()
        return any(kw in text for kw in _HAZARD_OCR_KEYWORDS)
    except Exception:
        return False


def _prediction(slug: str, confidence: float, raw_label: str) -> dict:
    return {
        'class':      slug,
        'confidence': round(confidence, 6),
        'label_uk':   _WASTE_LABELS_UK.get(slug, ''),
        'raw_label':  raw_label,
    }


# ── Service ───────────────────────────────────────────────────────────────────

class LocalAIService:
    """CLIP zero-shot image-classification pipeline for waste category detection.

    Compares the image embedding directly against natural-language descriptions
    of each waste category — no keyword mapping layer required. Covers all 13
    real waste slugs including asphalt, gypsum and insulation which were
    unreachable via the previous ResNet-50 + mapping approach.

    The pipeline is lazy-loaded on the first classify() call and cached as a
    class-level singleton. device=-1 forces CPU-only execution.
    """

    _model = None

    @classmethod
    def _load(cls) -> None:
        if cls._model is not None:
            return
        from transformers import pipeline
        cls._model = pipeline(
            'zero-shot-image-classification',
            model=_MODEL_ID,
            device=-1,  # -1 → CPU; never attempts CUDA
        )

    @classmethod
    def classify(cls, image: Image.Image) -> dict:
        """Run CLIP inference on a PIL Image and return a result dict.

        Return shape::

            {
                'predictions':        [{class, confidence, label_uk, raw_label}, …],
                'top_class':          str,   # one of the 14 official slugs
                'top_confidence':     float,
                'needs_human_review': bool,
                'inference_time_ms':  int,
                'model_version':      str,
            }
        """
        cls._load()

        img = image.convert('RGB')

        candidate_phrases = [phrase for phrase, _ in _CLIP_CANDIDATES]
        phrase_to_slug    = {phrase: slug for phrase, slug in _CLIP_CANDIDATES}

        t0 = time.monotonic()
        raw_results: list[dict] = cls._model(img, candidate_labels=candidate_phrases)
        inference_time_ms = int((time.monotonic() - t0) * 1000)

        model_version: str = (
            getattr(settings, 'MODEL_VERSION', 'clip-vit-base-v1') or 'clip-vit-base-v1'
        )

        # raw_results is already sorted by score descending
        top_slug = phrase_to_slug[raw_results[0]['label']]
        top_conf = float(raw_results[0]['score'])

        # OCR hazard override: warning text on the image beats visual similarity.
        # Runs after CLIP so it only pays the OCR cost once per request.
        if _ocr_hazard_check(img):
            logger.info("OCR hazard keyword detected — overriding to 'hazardous'")
            top_slug = 'hazardous'
            top_conf = max(top_conf, 0.95)

        # Human review: model has no confident match.
        if top_conf < _REVIEW_THRESHOLD:
            return {
                'predictions':        [],
                'top_class':          'unknown',
                'top_confidence':     round(top_conf, 6),
                'needs_human_review': True,
                'inference_time_ms':  inference_time_ms,
                'model_version':      model_version,
            }

        predictions = [
            _prediction(phrase_to_slug[r['label']], r['score'], r['label'])
            for r in raw_results
            if r['score'] >= _MIN_PRED_CONFIDENCE
        ]

        return {
            'predictions':        predictions,
            'top_class':          top_slug,
            'top_confidence':     round(top_conf, 6),
            'needs_human_review': False,
            'inference_time_ms':  inference_time_ms,
            'model_version':      model_version,
        }
