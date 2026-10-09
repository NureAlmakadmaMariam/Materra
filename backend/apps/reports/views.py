import uuid

from django.http import FileResponse, JsonResponse
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.analyses.models import Analysis, AnalysisStatus, WasteClass
from apps.reports.generators import PDFReportGenerator


class ReportDownloadView(APIView):
    """
    GET /api/v1/reports/<uuid:pk>/download/

    Dual-mode endpoint:

    PDF mode (default)
        Generates the PDF on demand and streams it directly — nothing is written
        to disk.  ``Content-Disposition: inline`` — browser opens an in-app
        preview.  Add ``?download=1`` to flip to ``attachment``.

    JSON mode
        Triggered by ``?format=json`` or ``Accept: application/json``.
        Returns the full parsed analysis payload.

    Error responses (always JSON)
        400 REPORT_NOT_READY — analysis is still pending / processing / failed.
        404 NOT_FOUND        — no Analysis row with that pk.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request: Request, pk: uuid.UUID) -> JsonResponse | FileResponse:
        # ── 1. Fetch the Analysis ───────────────────────────────────────── #
        try:
            analysis = Analysis.objects.get(pk=pk)
        except Analysis.DoesNotExist:
            return _err(404, 'NOT_FOUND', 'Аналіз не знайдено.')

        # ── 2. Status guard ─────────────────────────────────────────────── #
        terminal = (AnalysisStatus.DONE, AnalysisStatus.REVIEW_NEEDED)
        if analysis.status not in terminal:
            return _err(
                400,
                'REPORT_NOT_READY',
                'Звіт недоступний — аналіз ще не завершено.',
                {'status': analysis.status},
            )

        # ── 3. JSON mode ────────────────────────────────────────────────── #
        wants_json = (
            request.GET.get('format') == 'json'
            or 'application/json' in request.META.get('HTTP_ACCEPT', '')
        )
        if wants_json:
            return _json_payload(analysis)

        # ── 4. PDF mode — generate on demand, stream from memory ────────── #
        buf = PDFReportGenerator(analysis).generate()

        disposition = 'attachment' if request.GET.get('download') == '1' else 'inline'
        filename = f'materra-report-{str(analysis.id)[:8].upper()}.pdf'

        response = FileResponse(buf, content_type='application/pdf')
        response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
        response['X-Frame-Options'] = 'SAMEORIGIN'
        return response


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _err(http_status: int, code: str, message: str, details: dict | None = None) -> JsonResponse:
    """Return a uniform error envelope as a JsonResponse."""
    return JsonResponse(
        {'error': {'code': code, 'message': message, 'details': details or {}}},
        status=http_status,
        json_dumps_params={'ensure_ascii': False},
    )


def _json_payload(analysis: Analysis) -> JsonResponse:
    """
    Build the developer-facing JSON payload for a terminal analysis.

    Includes the ecological_score looked up from the WasteClass reference
    table, mirroring the shape of GET /api/v1/analyses/<pk>/.
    """
    ecological_score = None
    if analysis.top_class:
        wc = WasteClass.objects.filter(code=analysis.top_class).first()
        if wc is not None:
            ecological_score = wc.ecological_score

    return JsonResponse(
        {
            'data': {
                'id': str(analysis.id),
                'status': analysis.status,
                'top_class': analysis.top_class or None,
                'top_confidence': analysis.top_confidence,
                'predictions': analysis.predictions,
                'ecological_score': ecological_score,
                'needs_human_review': analysis.needs_human_review,
                'model_version': analysis.model_version or None,
                'inference_time_ms': analysis.inference_time_ms,
                'created_at': analysis.created_at,
            }
        },
        json_dumps_params={'ensure_ascii': False},
    )
