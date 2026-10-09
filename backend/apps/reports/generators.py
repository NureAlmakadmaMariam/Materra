"""
PDF report generator for completed waste-analysis jobs.

Uses ReportLab for pure-Python programmatic PDF generation — no system
libraries (GTK / cairo / Pango) required.

Usage:
    path = PDFReportGenerator(analysis).generate()
    # returns a path relative to MEDIA_ROOT, e.g.
    # 'reports/mock-user-123/2026/05/<uuid>.pdf'
"""
import base64
import io
import os
from typing import Optional

import matplotlib
matplotlib.use('Agg')  # headless backend — must be set before pyplot import
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from apps.analyses.models import AnalysisStatus, WasteClass

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, Image, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

# Register a Unicode-capable TrueType font so Cyrillic characters render
# correctly. Helvetica is Latin-only and raises a KeyError on any CJK/Cyrillic
# glyph. We try Arial (Windows) then DejaVu / Liberation (Linux/CI).
_FONT_CANDIDATES = [
    (
        'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/arialbd.ttf',
    ),
    (
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    ),
    (
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    ),
]

_FONT      = 'Helvetica'       # overwritten below when a TTF is found
_FONT_BOLD = 'Helvetica-Bold'

for _reg, _bold in _FONT_CANDIDATES:
    if os.path.isfile(_reg) and os.path.isfile(_bold):
        try:
            pdfmetrics.registerFont(TTFont('MaterraFont',      _reg))
            pdfmetrics.registerFont(TTFont('MaterraFont-Bold', _bold))
            _FONT      = 'MaterraFont'
            _FONT_BOLD = 'MaterraFont-Bold'
        except Exception:
            pass
        break

# ── Brand palette ──────────────────────────────────────────────────────── #
_C_DARK        = colors.HexColor('#1a1a2e')
_C_GREEN       = colors.HexColor('#2d6a4f')
_C_LIGHT_GREEN = colors.HexColor('#52b788')
_C_PALE_GREEN  = colors.HexColor('#f0faf4')
_C_AMBER       = colors.HexColor('#f4a261')
_C_RED         = colors.HexColor('#e63946')
_C_GREY        = colors.HexColor('#adb5bd')
_C_BG          = colors.HexColor('#f9f9f9')
_C_BORDER      = colors.HexColor('#dddddd')
_C_SECTION_HR  = colors.HexColor('#d8f3e5')
_C_TEXT        = colors.HexColor('#333333')
_C_MUTED       = colors.HexColor('#888888')
_C_WARN_BG     = colors.HexColor('#fff3cd')
_C_WARN_BORDER = colors.HexColor('#ffc107')
_C_WARN_TEXT   = colors.HexColor('#7b4f00')


def _ps(name: str, **kw) -> ParagraphStyle:
    """Construct a ParagraphStyle with explicit defaults."""
    s = ParagraphStyle(name)
    s.fontName   = kw.get('fontName', _FONT)
    s.fontSize   = kw.get('fontSize',  10)
    s.leading    = kw.get('leading',   kw.get('fontSize', 10) * 1.4)
    s.textColor  = kw.get('textColor', _C_TEXT)
    s.alignment  = kw.get('alignment', TA_LEFT)
    s.spaceAfter = kw.get('spaceAfter', 0)
    return s


def _safe_float(value, default: float = 0.0) -> float:
    """Coerce *value* to float, returning *default* on any failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _norm_predictions(raw) -> list[dict]:
    """
    Normalise any predictions payload into ``[{'label': str, 'confidence': float}, …]``.

    Handles every known payload variation without raising:
    - ``None`` or non-list root value         → empty list
    - Non-dict items inside the list          → skipped
    - Missing ``label_uk`` / ``class`` keys   → falls back through raw_label → '?'
    - Missing or ``None`` confidence          → 0.0
    - Confidence stored as a string ('0.87')  → coerced via float()
    - Confidence outside [0, 1]               → clamped
    """
    if not isinstance(raw, list):
        return []
    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(
            item.get('label_uk') or
            item.get('raw_label') or
            item.get('class') or
            '?'
        )
        confidence = _safe_float(item.get('confidence'), 0.0)
        confidence = max(0.0, min(1.0, confidence))
        result.append({'label': label, 'confidence': confidence})
    return result


def _warning_box(text: str, width: float) -> Table:
    """Return a Table styled as a coloured warning notice."""
    tbl = Table(
        [[Paragraph(text, _ps('wt', fontName=_FONT_BOLD, fontSize=9,
                               textColor=_C_WARN_TEXT))]],
        colWidths=[width],
    )
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), _C_WARN_BG),
        ('BOX',           (0, 0), (-1, -1), 0.5, _C_WARN_BORDER),
        ('LEFTPADDING',   (0, 0), (-1, -1), 10),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    return tbl


class PDFReportGenerator:
    """Generate a ReportLab PDF report for a single Analysis in DONE/REVIEW_NEEDED state."""

    def __init__(self, analysis) -> None:
        """
        Parameters
        ----------
        analysis:
            An ``apps.analyses.models.Analysis`` instance whose status is
            ``'done'`` or ``'review_needed'``.

        Raises
        ------
        ValueError
            If the analysis has not yet reached a terminal classification state.
        """
        if analysis.status not in (AnalysisStatus.DONE, AnalysisStatus.REVIEW_NEEDED):
            raise ValueError(
                f'PDFReportGenerator requires a terminal analysis; '
                f'got status={analysis.status!r} for id={analysis.id}'
            )
        self.analysis = analysis

    def generate(self) -> io.BytesIO:
        """Run the full pipeline and return an in-memory PDF buffer."""
        waste_class = self._fetch_waste_class()
        chart_b64   = self._build_chart()
        return self._write_pdf(waste_class, chart_b64)

    # ------------------------------------------------------------------ #
    # Private pipeline steps                                               #
    # ------------------------------------------------------------------ #

    def _fetch_waste_class(self) -> Optional[WasteClass]:
        """Return the WasteClass ORM instance for the top predicted slug."""
        code = self.analysis.top_class
        if not code:
            return None
        try:
            return WasteClass.objects.get(code=code)
        except WasteClass.DoesNotExist:
            return None

    def _build_chart(self) -> str:
        """
        Render a horizontal bar chart of the top-5 classification probabilities.

        Returns
        -------
        str
            Base64-encoded PNG string, or empty string when no usable predictions exist.
        """
        top5 = _norm_predictions(self.analysis.predictions)[:5]
        if not top5:
            return ''

        labels = [p['label'] for p in top5]
        values = [round(p['confidence'] * 100, 2) for p in top5]

        # Highest-confidence bar at the top
        labels = labels[::-1]
        values = values[::-1]

        # 8.5 in wide gives long Ukrainian labels comfortable room;
        # 0.75 in per bar keeps rows readable without crowding.
        fig, ax = plt.subplots(figsize=(8.5, max(2.4, len(labels) * 0.75)))
        bar_colors = ['#2d6a4f' if v == max(values) else '#74c69d' for v in values]
        bars = ax.barh(labels, values, color=bar_colors, edgecolor='none', height=0.52)

        for bar, val in zip(bars, values):
            ax.text(
                bar.get_width() + 0.8,
                bar.get_y() + bar.get_height() / 2,
                f'{val:.1f}%',
                va='center', ha='left',
                fontsize=8.5, color='#333333',
            )

        # Extra headroom on the right keeps end-of-bar percentage labels inside the frame.
        ax.set_xlim(0, 112)
        ax.set_xlabel('Впевненість (%)', fontsize=8.5)

        # pad=10 pushes y-axis text away from the bars so labels never overlap them.
        ax.tick_params(axis='y', labelsize=8.5, pad=10)

        # Clean integer-percentage ticks instead of raw floats.
        ax.set_xticks([0, 20, 40, 60, 80, 100])
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{int(x)}%'))
        ax.tick_params(axis='x', labelsize=8)

        for spine in ('top', 'right', 'left'):
            ax.spines[spine].set_visible(False)
        ax.spines['bottom'].set_color('#cccccc')
        ax.set_facecolor('#fafafa')
        fig.patch.set_facecolor('#fafafa')

        # tight_layout recalculates all margins (including the widened left margin
        # needed for longer label strings); bbox_inches='tight' re-applies at save
        # time to guarantee nothing is clipped in the output buffer.
        fig.tight_layout(pad=1.0)

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#fafafa')
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')

    def _write_pdf(self, waste_class, chart_b64: str) -> io.BytesIO:
        """
        Build ReportLab flowables, compile to PDF, and return an in-memory buffer.

        Returns
        -------
        io.BytesIO
            Seeked-to-zero buffer ready for streaming.
        """
        analysis = self.analysis

        # ── derived display values ──────────────────────────────── #
        from apps.reports.translation import translate_to_uk

        short_id     = str(analysis.id).replace('-', '')[-8:].upper()
        report_id    = f'MAT-{analysis.created_at.strftime("%Y%m%d")}-{short_id}'
        report_date  = analysis.created_at.strftime('%d.%m.%Y')
        report_time  = analysis.created_at.strftime('%H:%M')
        top_conf_pct = f'{(analysis.top_confidence or 0.0) * 100:.1f}'
        eco_score    = getattr(waste_class, 'ecological_score', None)
        label_uk     = getattr(waste_class, 'label_uk', None) or analysis.top_class or '—'
        recycling    = (getattr(waste_class, 'recycling_method', '') or '').strip() or (
            'Рекомендації для даного типу матеріалу відсутні. '
            'Зверніться до місцевого підприємства з утилізації будівельних відходів.'
        )
        is_hazardous = getattr(waste_class, 'is_hazardous', False)

        raw_label_en = ''
        raw_label_uk = ''
        if analysis.predictions:
            raw_label_en = analysis.predictions[0].get('raw_label', '')
        if raw_label_en:
            raw_label_uk = translate_to_uk(raw_label_en)

        # ── document setup ──────────────────────────────────────── #
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=20 * mm, rightMargin=20 * mm,
            topMargin=18 * mm,  bottomMargin=18 * mm,
        )
        page_w = A4[0] - 40 * mm  # usable content width

        story: list = []

        def _section(title: str) -> None:
            story.append(Spacer(1, 8))
            story.append(Paragraph(
                title,
                _ps('sec_ttl', fontSize=7.5, fontName=_FONT_BOLD,
                    textColor=_C_GREEN, spaceAfter=3),
            ))
            story.append(HRFlowable(width='100%', thickness=0.5, color=_C_SECTION_HR))
            story.append(Spacer(1, 4))

        # ── 1. Header ───────────────────────────────────────────── #
        hdr = Table(
            [[
                [
                    Paragraph(
                        '<font color="#ffffff"><b>MATERRA.</b></font>',
                        _ps('hbr', fontSize=18, fontName=_FONT_BOLD,
                            textColor=colors.white, leading=22),
                    ),
                    Paragraph(
                        '<font color="#a8dadc">Аналітичний звіт про будівельні відходи</font>',
                        _ps('hsu', fontSize=8, textColor=colors.HexColor('#a8dadc'), leading=11),
                    ),
                ],
                [
                    Paragraph(
                        f'<font color="#ffffff"><b>{report_id}</b></font>',
                        _ps('hid', fontSize=9, fontName=_FONT_BOLD,
                            textColor=colors.white, alignment=TA_RIGHT, leading=13),
                    ),
                    Paragraph(
                        f'<font color="#a8dadc">{report_date} о {report_time}</font>',
                        _ps('hdt', fontSize=8, textColor=colors.HexColor('#a8dadc'),
                            alignment=TA_RIGHT, leading=11),
                    ),
                ],
            ]],
            colWidths=[page_w * 0.55, page_w * 0.45],
        )
        hdr.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), _C_DARK),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING',   (0, 0), (0, -1),  10),
            ('RIGHTPADDING',  (-1, 0), (-1, -1), 10),
            ('TOPPADDING',    (0, 0), (-1, -1),  10),
            ('BOTTOMPADDING', (0, 0), (-1, -1),  10),
        ]))
        story.append(hdr)

        # ── 2. Metadata row ─────────────────────────────────────── #
        story.append(Spacer(1, 1))
        inf_ms   = f'{analysis.inference_time_ms} мс' if analysis.inference_time_ms else '—'
        short_uuid = str(analysis.id)[:8].upper() + '…'
        meta = Table(
            [[
                [Paragraph('Ідентифікатор', _ps('mk0', fontSize=7, textColor=_C_MUTED)),
                 Paragraph(short_uuid, _ps('mv0', fontSize=8, fontName=_FONT_BOLD,
                                           textColor=_C_DARK))],
                [Paragraph('Дата створення', _ps('mk1', fontSize=7, textColor=_C_MUTED)),
                 Paragraph(report_date, _ps('mv1', fontSize=9, fontName=_FONT_BOLD,
                                            textColor=_C_DARK))],
                [Paragraph('Версія моделі', _ps('mk2', fontSize=7, textColor=_C_MUTED)),
                 Paragraph(analysis.model_version or '—',
                           _ps('mv2', fontSize=9, fontName=_FONT_BOLD, textColor=_C_DARK))],
                [Paragraph('Час обробки', _ps('mk3', fontSize=7, textColor=_C_MUTED)),
                 Paragraph(inf_ms, _ps('mv3', fontSize=9, fontName=_FONT_BOLD,
                                       textColor=_C_DARK))],
            ]],
            colWidths=[page_w / 4] * 4,
        )
        meta.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 6),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
            ('TOPPADDING',    (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('BOX',           (0, 0), (-1, -1), 0.5, _C_BORDER),
            ('INNERGRID',     (0, 0), (-1, -1), 0.5, _C_BORDER),
        ]))
        story.append(meta)

        # ── 3. Classification result ─────────────────────────────── #
        _section('Результати розпізнавання')

        if is_hazardous:
            story.append(_warning_box(
                'НЕБЕЗПЕЧНІ ВІДХОДИ — потребує спеціальної утилізації', page_w,
            ))
            story.append(Spacer(1, 5))

        res_cells = [
            Paragraph('Основний тип відходів',
                      _ps('rl', fontSize=8, textColor=colors.HexColor('#555555'))),
            Paragraph(label_uk,
                      _ps('rv', fontSize=15, fontName=_FONT_BOLD,
                          textColor=_C_DARK, leading=18)),
        ]
        if raw_label_uk and raw_label_en:
            display = (
                f'Розпізнано як: {raw_label_uk} / {raw_label_en}'
                if raw_label_uk.lower() != raw_label_en.lower()
                else f'Розпізнано як: {raw_label_en}'
            )
            res_cells.append(Paragraph(
                display,
                _ps('rraw', fontSize=8.5, textColor=_C_MUTED),
            ))
        res_cells.append(Paragraph(
            f'Впевненість: {top_conf_pct}%',
            _ps('rc', fontSize=10, fontName=_FONT_BOLD, textColor=_C_GREEN),
        ))

        res = Table(
            [[res_cells]],
            colWidths=[page_w],
        )
        res.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), _C_PALE_GREEN),
            ('LINEBEFORE',    (0, 0), (0, -1),  3, _C_LIGHT_GREEN),
            ('LEFTPADDING',   (0, 0), (-1, -1), 10),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
            ('TOPPADDING',    (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(res)

        if analysis.needs_human_review:
            story.append(Spacer(1, 6))
            story.append(_warning_box(
                'Результат потребує перевірки фахівцем. '
                'Рівень впевненості нижчий за порогове значення.',
                page_w,
            ))

        # ── 4. Recycling recommendation ──────────────────────────── #
        _section('Рекомендації з утилізації')
        rec = Table(
            [[Paragraph(recycling, _ps('rt', fontSize=9.5, textColor=_C_TEXT, leading=15))]],
            colWidths=[page_w],
        )
        rec.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), _C_BG),
            ('LEFTPADDING',   (0, 0), (-1, -1), 10),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
            ('TOPPADDING',    (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(rec)

        # ── 5. Ecological score ──────────────────────────────────── #
        _section('Екологічний вплив')

        if eco_score is not None:
            badge_bg = (
                _C_GREEN if eco_score >= 7
                else _C_AMBER if eco_score >= 4
                else _C_RED
            )
            badge_txt = f'{eco_score}/10'
            if eco_score >= 8:
                eco_desc = (
                    'Матеріал має <b>високий потенціал переробки</b>. '
                    'При правильній утилізації мінімальний негативний вплив '
                    'на навколишнє середовище.'
                )
            elif eco_score >= 6:
                eco_desc = (
                    'Матеріал має <b>середній потенціал переробки</b>. '
                    'Рекомендується дотримуватись вказаного методу утилізації '
                    'для зменшення екологічного сліду.'
                )
            elif eco_score >= 4:
                eco_desc = (
                    'Матеріал має <b>обмежений потенціал переробки</b>. '
                    'Необхідне попереднє сортування для підвищення ефективності утилізації.'
                )
            else:
                eco_desc = (
                    'Матеріал має <b>негативний екологічний вплив</b>. '
                    "Суворе дотримання спеціальних вимог утилізації є обов'язковим."
                )
        else:
            badge_bg  = _C_GREY
            badge_txt = '—'
            eco_desc  = (
                'Екологічний бал не може бути розрахований — '
                'тип матеріалу не визначено.'
            )

        eco = Table(
            [[
                Paragraph(
                    f'<font color="white"><b>{badge_txt}</b></font>',
                    _ps('bdg', fontSize=12, fontName=_FONT_BOLD,
                        textColor=colors.white, alignment=TA_CENTER),
                ),
                Paragraph(
                    eco_desc,
                    _ps('ecd', fontSize=9, textColor=colors.HexColor('#444444'), leading=14),
                ),
            ]],
            colWidths=[16 * mm, page_w - 16 * mm - 12],
        )
        eco.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (0, -1),  badge_bg),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',   (0, 0), (0, -1),  4),
            ('RIGHTPADDING',  (0, 0), (0, -1),  4),
            ('TOPPADDING',    (0, 0), (-1, -1),  8),
            ('BOTTOMPADDING', (0, 0), (-1, -1),  8),
            ('LEFTPADDING',   (1, 0), (1, -1),  12),
        ]))
        story.append(eco)

        # ── 6. Confidence chart ──────────────────────────────────── #
        if chart_b64:
            _section('Розподіл впевненості моделі (Топ-5 класів)')
            chart_buf = io.BytesIO(base64.b64decode(chart_b64))
            story.append(Image(chart_buf, width=page_w, height=58 * mm))

        # ── 7. Footer ────────────────────────────────────────────── #
        story.append(Spacer(1, 8))
        status_txt   = (
            'Потребує перевірки фахівцем'
            if analysis.needs_human_review
            else 'Автоматичний аналіз завершено успішно'
        )
        status_color = (
            colors.HexColor('#b08800')
            if analysis.needs_human_review
            else _C_GREEN
        )
        footer = Table(
            [[
                Paragraph(status_txt,
                          _ps('fst', fontSize=8.5, fontName=_FONT_BOLD,
                              textColor=status_color)),
                Paragraph(
                    f'Materra AI · {analysis.model_version or ""} · {report_id}',
                    _ps('frt', fontSize=8, textColor=colors.HexColor('#666666'),
                        alignment=TA_RIGHT),
                ),
            ]],
            colWidths=[page_w * 0.55, page_w * 0.45],
        )
        footer.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
            ('TOPPADDING',    (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BOX',           (0, 0), (-1, -1), 0.5, _C_BORDER),
        ]))
        story.append(footer)

        doc.build(story)
        buf.seek(0)
        return buf
