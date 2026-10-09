"""
Data migration — seed the 14 canonical WasteClass rows.

Uses apps.get_model() (not a direct import) so the historical model state is
respected and the migration remains stable even if models.py changes later.
"""
from django.db import migrations

# Inline copy of the seed data so this migration is self-contained.
# Matches WASTE_CLASS_SEED_DATA in models.py and the ONNX model output layer.
_WASTE_CLASSES = [
    {'code': 'asphalt',      'label_uk': 'Асфальт',             'label_en': 'Asphalt',       'is_hazardous': False},
    {'code': 'brick',        'label_uk': 'Цегла',               'label_en': 'Brick',         'is_hazardous': False},
    {'code': 'ceramic_tile', 'label_uk': 'Керамічна плитка',    'label_en': 'Ceramic Tile',  'is_hazardous': False},
    {'code': 'concrete',     'label_uk': 'Бетон',               'label_en': 'Concrete',      'is_hazardous': False},
    {'code': 'glass',        'label_uk': 'Скло',                'label_en': 'Glass',         'is_hazardous': False},
    {'code': 'gypsum',       'label_uk': 'Гіпс/Гіпсокартон',   'label_en': 'Gypsum/Drywall','is_hazardous': False},
    {'code': 'hazardous',    'label_uk': 'Небезпечні відходи',  'label_en': 'Hazardous',     'is_hazardous': True},
    {'code': 'insulation',   'label_uk': 'Утеплювач',           'label_en': 'Insulation',    'is_hazardous': False},
    {'code': 'metal',        'label_uk': 'Метал',               'label_en': 'Metal',         'is_hazardous': False},
    {'code': 'mixed_debris', 'label_uk': 'Змішані відходи',     'label_en': 'Mixed Debris',  'is_hazardous': False},
    {'code': 'plastic',      'label_uk': 'Пластик',             'label_en': 'Plastic',       'is_hazardous': False},
    {'code': 'soil',         'label_uk': 'Ґрунт',               'label_en': 'Soil/Earth',    'is_hazardous': False},
    {'code': 'unknown',      'label_uk': 'Невизначено',         'label_en': 'Unknown',       'is_hazardous': False},
    {'code': 'wood',         'label_uk': 'Деревина',            'label_en': 'Wood',          'is_hazardous': False},
]

_CODES = [r['code'] for r in _WASTE_CLASSES]


def _seed(apps, schema_editor):
    WasteClass = apps.get_model('analyses', 'WasteClass')
    for row in _WASTE_CLASSES:
        WasteClass.objects.get_or_create(code=row['code'], defaults=row)


def _unseed(apps, schema_editor):
    WasteClass = apps.get_model('analyses', 'WasteClass')
    WasteClass.objects.filter(code__in=_CODES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('analyses', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(_seed, reverse_code=_unseed),
    ]
