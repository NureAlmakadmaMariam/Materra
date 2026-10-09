import uuid

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Analysis, AnalysisImage, AnalysisStatus, WasteClass
from .services import AnalysisService, ImageValidationError

_WASTE_LABELS_UK: dict[str, str] = {
    'concrete':     'Бетон',
    'brick':        'Цегла',
    'metal':        'Метал',
    'wood':         'Деревина',
    'glass':        'Скло',
    'plastic':      'Пластик',
    'ceramic_tile': 'Керамічна плитка',
    'asphalt':      'Асфальт',
    'gypsum':       'Гіпс/Гіпсокартон',
    'insulation':   'Утеплювач',
    'mixed_debris': 'Змішані відходи',
    'soil':         'Ґрунт',
    'hazardous':    'Небезпечні відходи',
    'unknown':      'Невизначено',
}


# ---------------------------------------------------------------------------
# Response-payload helpers
# ---------------------------------------------------------------------------

def _detail_payload(analysis: Analysis) -> dict:
    """
    Build the ``data`` dict for GET /api/v1/analyses/<pk>/.

    Shape varies by status, matching §8.3 of the context document:
      • pending / processing  → minimal: id, status, created_at
      • done                  → full AI results + ecological_score from WasteClass
      • review_needed         → base + needs_human_review flag
      • failed                → base only
    """
    base: dict = {
        'id': str(analysis.id),
        'status': analysis.status,
        'created_at': analysis.created_at,
    }

    if analysis.status == AnalysisStatus.DONE:
        ecological_score = None
        is_hazardous = False
        if analysis.top_class:
            wc = WasteClass.objects.filter(code=analysis.top_class).first()
            if wc is not None:
                ecological_score = wc.ecological_score
                is_hazardous = wc.is_hazardous

        return {
            **base,
            'top_class': analysis.top_class or None,
            'top_confidence': analysis.top_confidence,
            'predictions': analysis.predictions,
            'needs_human_review': analysis.needs_human_review,
            'model_version': analysis.model_version or None,
            'inference_time_ms': analysis.inference_time_ms,
            'report_url': f'/api/v1/reports/{analysis.id}/download/',
            'ecological_score': ecological_score,
            'is_hazardous':     is_hazardous,
        }

    if analysis.status == AnalysisStatus.REVIEW_NEEDED:
        return {**base, 'needs_human_review': True}

    # pending, processing, failed — return the base fields only
    return base


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class AnalysisCreateView(APIView):
    """
    POST /api/v1/analyses/

    Accept multipart/form-data with a single ``image`` field.
    Validates the file, persists it, creates a PENDING Analysis row, and
    returns 202 Accepted so the client can start polling.

    Permission is open so unauthenticated API calls still work; when a
    session cookie is present DRF's SessionAuthentication populates
    request.user so the analysis is linked to the correct owner.
    """

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request: Request) -> Response:
        image_file = request.FILES.get('image')

        if image_file is None:
            return Response(
                {
                    'error': {
                        'code': 'VALIDATION_ERROR',
                        'message': 'Поле "image" є обов\'язковим.',
                        'details': {'image': ['Файл не надано.']},
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user if request.user.is_authenticated else None
        try:
            analysis = AnalysisService.create_analysis(
                image_file=image_file,
                user=user,
            )
        except ImageValidationError as exc:
            return Response(
                {
                    'error': {
                        'code': 'INVALID_IMAGE',
                        'message': exc.message,
                        'details': {},
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                'data': {
                    'id': str(analysis.id),
                    'status': analysis.status,
                    'poll_url': f'/api/v1/analyses/{analysis.id}/',
                    'estimated_seconds': 5,
                }
            },
            status=status.HTTP_202_ACCEPTED,
        )


class AnalysisDetailView(APIView):
    """
    GET /api/v1/analyses/<uuid:pk>/

    Poll endpoint — returns the current state of an analysis job.

    Response shape follows §8.3:
      202 → 200 pending/processing  : {id, status, created_at}
            200 done                : full AI result payload + ecological_score
            200 review_needed       : base + needs_human_review
            200 failed              : base
            404                     : NOT_FOUND error envelope

    Permission is open; session auth populates request.user when present.
    """

    permission_classes = [AllowAny]

    def get(self, request: Request, pk: uuid.UUID) -> Response:
        try:
            analysis = AnalysisService.get_by_id(pk)
        except Analysis.DoesNotExist:
            return Response(
                {
                    'error': {
                        'code': 'NOT_FOUND',
                        'message': 'Аналіз не знайдено.',
                        'details': {},
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {'data': _detail_payload(analysis)},
            status=status.HTTP_200_OK,
        )

    def delete(self, request: Request, pk: uuid.UUID) -> Response:
        try:
            analysis = AnalysisService.get_by_id(pk)
        except Analysis.DoesNotExist:
            return Response(
                {
                    'error': {
                        'code': 'NOT_FOUND',
                        'message': 'Аналіз не знайдено.',
                        'details': {},
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        analysis.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    GET / and GET /dashboard/

    Analytics dashboard: KPI cards and a paginated history table of previous
    analyses with PDF download links.
    """

    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base_qs = Analysis.objects.filter(user=self.request.user)
        done_qs = base_qs.filter(status=AnalysisStatus.DONE)

        # ── Status counts (single GROUP BY query) ──────────────────────── #
        status_map = {
            r['status']: r['c']
            for r in base_qs.values('status').annotate(c=Count('id'))
        }
        total_count  = base_qs.count()
        done_count   = status_map.get(AnalysisStatus.DONE, 0)
        review_count = status_map.get(AnalysisStatus.REVIEW_NEEDED, 0)
        failed_count = status_map.get(AnalysisStatus.FAILED, 0)

        # ── WasteClass reference (14 rows — cheap to load all) ─────────── #
        wc_map = {wc.code: wc for wc in WasteClass.objects.all()}

        # ── Ecological score + hazardous count ────────────────────────────── #
        done_slugs = list(done_qs.values_list('top_class', flat=True))
        eco_scores = [
            wc_map[s].ecological_score
            for s in done_slugs
            if s in wc_map and wc_map[s].ecological_score is not None
        ]
        eco_count        = len(eco_scores)
        eco_sum          = float(sum(eco_scores)) if eco_scores else 0.0
        avg_eco_score    = round(eco_sum / eco_count, 1) if eco_count else None
        hazardous_count  = sum(1 for s in done_slugs if wc_map.get(s) and wc_map[s].is_hazardous)

        # ── All history rows — filtering/sorting handled client-side ────── #
        rows = []
        for a in base_qs.order_by('-created_at'):
            slug = a.top_class or ''
            wc   = wc_map.get(slug)
            rows.append({
                'obj':          a,
                'label_uk':     wc.label_uk if wc else _WASTE_LABELS_UK.get(slug, '—'),
                'img_url':      f'/api/v1/analyses/{a.id}/image/',
                'has_report':   a.status in (AnalysisStatus.DONE, AnalysisStatus.REVIEW_NEEDED),
                'is_hazardous': wc.is_hazardous if wc else False,
                'eco_score':    float(wc.ecological_score) if (wc and wc.ecological_score is not None and a.status == AnalysisStatus.DONE) else None,
            })

        ctx.update({
            'total_count':     total_count,
            'done_count':      done_count,
            'review_count':    review_count,
            'failed_count':    failed_count,
            'avg_eco_score':   avg_eco_score,
            'eco_count':       eco_count,
            'eco_sum':         eco_sum,
            'hazardous_count': hazardous_count,
            'rows':           rows,
            'waste_type_options': list(_WASTE_LABELS_UK.items()),
            'status_options': [
                ('done',          'Готово'),
                ('review_needed', 'На перевірці'),
                ('failed',        'Помилка'),
            ],
        })
        return ctx


class AnalysisImageView(APIView):
    """
    GET /api/v1/analyses/<uuid:pk>/image/

    Stream the original uploaded image bytes stored in the database.
    Returns 404 when no image record exists for the given analysis.
    """

    permission_classes = [AllowAny]

    def get(self, request: Request, pk: uuid.UUID) -> HttpResponse:
        try:
            img_record = AnalysisImage.objects.get(analysis_id=pk)
        except AnalysisImage.DoesNotExist:
            return Response(
                {
                    'error': {
                        'code': 'NOT_FOUND',
                        'message': 'Зображення не знайдено.',
                        'details': {},
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return HttpResponse(
            bytes(img_record.image_data),
            content_type=img_record.content_type,
        )


class LandingView(View):
    """
    GET /

    Public landing page. Authenticated users are redirected straight to the
    dashboard so they never see the marketing page on repeat visits.
    """

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return render(request, 'landing.html')


class DevUploadView(TemplateView):
    """
    GET /

    Developer-only upload tester.  Renders dev_upload.html which exposes
    a file picker, calls POST /api/v1/analyses/, and polls the returned
    poll_url every 2 s until the job reaches a terminal status.

    Remove (or guard with DEBUG check) before going to production.
    """

    template_name = 'dev_upload.html'
