import uuid

from django.conf import settings
from django.db import models


class AnalysisStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    DONE = 'done', 'Done'
    FAILED = 'failed', 'Failed'
    REVIEW_NEEDED = 'review_needed', 'Review Needed'


class WasteClass(models.Model):
    """
    Reference table of recognisable construction-waste categories.

    Seed data lives in WASTE_CLASS_SEED_DATA below and is loaded via a
    data migration; the 14-class list matches the ONNX model's output layer.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    label_uk = models.CharField(max_length=100)
    label_en = models.CharField(max_length=100)
    recycling_method = models.TextField(blank=True)
    # Ecological impact score: 1 (worst) – 10 (best) for correct disposal.
    ecological_score = models.IntegerField(null=True, blank=True)
    is_hazardous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Клас відходів'
        verbose_name_plural = 'Класи відходів'
        ordering = ['code']

    def __str__(self) -> str:
        return f'{self.code} ({self.label_uk})'


class Analysis(models.Model):
    """Single image-analysis job. Lifecycle: PENDING → PROCESSING → DONE | FAILED | REVIEW_NEEDED."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # --- owner ---
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='analyses',
    )

    # --- status ---
    status = models.CharField(
        max_length=20,
        choices=AnalysisStatus.choices,
        default=AnalysisStatus.PENDING,
    )

    # --- uploaded image metadata (bytes stored in AnalysisImage) ---
    image_filename = models.CharField(max_length=255, blank=True)
    image_size_bytes = models.IntegerField(null=True, blank=True)

    # --- AI results ---
    # Stored as JSONB on PostgreSQL, JSON text on SQLite.
    # Shape: [{"class": "concrete", "confidence": 0.87, "label_uk": "Бетон"}, …]
    predictions = models.JSONField(null=True, blank=True)
    top_class = models.CharField(max_length=100, blank=True)
    top_confidence = models.FloatField(null=True, blank=True)
    model_version = models.CharField(max_length=50, blank=True)
    inference_time_ms = models.IntegerField(null=True, blank=True)
    needs_human_review = models.BooleanField(default=False)

    # --- metadata ---
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Аналіз'
        verbose_name_plural = 'Аналізи'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user'], name='idx_analyses_user'),
            models.Index(fields=['status'], name='idx_analyses_status'),
            models.Index(fields=['-created_at'], name='idx_analyses_created_at'),
        ]

    def __str__(self) -> str:
        return f'Analysis {self.id} [{self.status}]'

    @property
    def is_complete(self) -> bool:
        return self.status == AnalysisStatus.DONE

    @property
    def is_failed(self) -> bool:
        return self.status == AnalysisStatus.FAILED


class AnalysisImage(models.Model):
    """
    Binary image data for a single analysis, kept in a separate table so that
    list queries on Analysis never load blob bytes unless explicitly requested.
    """

    analysis = models.OneToOneField(
        Analysis,
        on_delete=models.CASCADE,
        related_name='image',
        primary_key=True,
    )
    image_data = models.BinaryField()
    content_type = models.CharField(max_length=50, default='image/jpeg')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Зображення аналізу'
        verbose_name_plural = 'Зображення аналізів'


# ---------------------------------------------------------------------------
# Seed data — used by the data migration to populate waste_classes.
# Matches the 14-class output layer of the ONNX model (materra-v1.x).
# ---------------------------------------------------------------------------

WASTE_CLASS_SEED_DATA: list[dict] = [
    {'code': 'concrete',     'label_uk': 'Бетон',              'label_en': 'Concrete'},
    {'code': 'brick',        'label_uk': 'Цегла',              'label_en': 'Brick'},
    {'code': 'metal',        'label_uk': 'Метал',              'label_en': 'Metal'},
    {'code': 'wood',         'label_uk': 'Деревина',           'label_en': 'Wood'},
    {'code': 'glass',        'label_uk': 'Скло',               'label_en': 'Glass'},
    {'code': 'plastic',      'label_uk': 'Пластик',            'label_en': 'Plastic'},
    {'code': 'ceramic_tile', 'label_uk': 'Керамічна плитка',   'label_en': 'Ceramic Tile'},
    {'code': 'asphalt',      'label_uk': 'Асфальт',            'label_en': 'Asphalt'},
    {'code': 'gypsum',       'label_uk': 'Гіпс/Гіпсокартон',  'label_en': 'Gypsum/Drywall'},
    {'code': 'insulation',   'label_uk': 'Утеплювач',          'label_en': 'Insulation'},
    {'code': 'mixed_debris', 'label_uk': 'Змішані відходи',    'label_en': 'Mixed Debris'},
    {'code': 'soil',         'label_uk': 'Ґрунт',              'label_en': 'Soil/Earth'},
    {'code': 'hazardous',    'label_uk': 'Небезпечні відходи', 'label_en': 'Hazardous',
     'is_hazardous': True},
    {'code': 'unknown',      'label_uk': 'Невизначено',        'label_en': 'Unknown'},
]
