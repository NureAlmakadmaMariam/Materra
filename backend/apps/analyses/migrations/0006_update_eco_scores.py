"""
Data migration — update ecological_score values based on EU research data.

Sources: JRC CDW Report JRC134500, Eurostat cei_wm040, EAPA Circular Economy 2022,
EU C&D Waste Protocol 2016, EuRIC Metal Recycling Factsheet, EN 15978 / ISO 14040.

Scoring criteria (weighted):
  40% — actual EU material recycling rate (Eurostat / JRC)
  35% — CO2 / energy savings vs. virgin production or landfill (LCA)
  25% — ease and safety of recycling (contamination, hazard, infrastructure maturity)
"""
from django.db import migrations

_SCORES = {
    'metal':        9,  # 85-95% collection; 58-92% CO2 savings; commodity market pull
    'asphalt':      9,  # ~95% EU recovery (EAPA); only 5% to landfill; +1 from 8
    'glass':        8,  # 97% recyclable; closed-loop tech mature; CDW collection gap only
    'brick':        7,  # quality recycling 30-50%; rest is backfill; -1 from 8
    'wood':         7,  # only ~37% material-recycled; rest energy recovery; -1 from 8
    'concrete':     7,  # largest CDW fraction; good LCA; high-quality RCA uptake still marginal
    'ceramic_tile': 6,  # no closed-loop pathway; <20% actual recycling; -1 from 7
    'soil':         6,  # clean soil neutral (not genuine recycling); contaminated soil costly; -1 from 7
    'gypsum':       5,  # 87% EU landfill rate; only 13% recycled; H2S toxicity; -2 from 7
    'plastic':      5,  # ~26% material recycling; polymer complexity; flame retardants; -1 from 6
    'insulation':   4,  # mineral wool <15% recycled; legacy HBCD flame retardants; -2 from 6
    'mixed_debris': 3,  # unsorted = contamination risk + mandatory secondary sorting; -1 from 4
    'hazardous':    1,  # containment-only; no recycling pathway; confirmed
    'unknown':      None,
}


def _apply(apps, schema_editor):
    WasteClass = apps.get_model('analyses', 'WasteClass')
    for code, score in _SCORES.items():
        WasteClass.objects.filter(code=code).update(ecological_score=score)


def _revert(apps, schema_editor):
    _PREVIOUS = {
        'metal': 9, 'asphalt': 8, 'glass': 8, 'brick': 8, 'wood': 8,
        'concrete': 7, 'ceramic_tile': 7, 'soil': 7, 'gypsum': 7,
        'plastic': 6, 'insulation': 6, 'mixed_debris': 4,
        'hazardous': 1, 'unknown': None,
    }
    WasteClass = apps.get_model('analyses', 'WasteClass')
    for code, score in _PREVIOUS.items():
        WasteClass.objects.filter(code=code).update(ecological_score=score)


class Migration(migrations.Migration):

    dependencies = [
        ('analyses', '0005_db_image_storage'),
    ]

    operations = [
        migrations.RunPython(_apply, reverse_code=_revert),
    ]
