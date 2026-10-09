import io
import logging
import traceback
import uuid

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from PIL import Image

from .models import Analysis, AnalysisImage, AnalysisStatus

logger = logging.getLogger(__name__)


class ImageValidationError(ValidationError):
    """Raised when an uploaded file fails any image validation check."""


_ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset({
    'image/jpeg',
    'image/png',
    'image/webp',
})

_MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB


def _check_magic_bytes(header: bytes) -> bool:
    """Return True when the first bytes match JPEG, PNG, or WebP signatures."""
    if header[:3] == b'\xff\xd8\xff':
        return True
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return True
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return True
    return False


class AnalysisService:
    @staticmethod
    def get_by_id(pk: uuid.UUID) -> Analysis:
        """Return a single Analysis by primary key. Raises Analysis.DoesNotExist if absent."""
        return Analysis.objects.get(pk=pk)

    @staticmethod
    def create_analysis(image_file: UploadedFile, user=None) -> Analysis:
        """Validate the uploaded image, persist it to the DB, run inference, and return the Analysis."""
        AnalysisService._validate_image(image_file)

        image_bytes = image_file.read()
        image_file.seek(0)

        analysis = Analysis.objects.create(
            user=user,
            image_filename=image_file.name or '',
            image_size_bytes=image_file.size,
            status=AnalysisStatus.PENDING,
        )

        AnalysisImage.objects.create(
            analysis=analysis,
            image_data=image_bytes,
            content_type=getattr(image_file, 'content_type', 'image/jpeg') or 'image/jpeg',
        )

        AnalysisService._run_inference(analysis)
        return analysis

    @staticmethod
    def _run_inference(analysis: Analysis) -> None:
        """Run local AI classification on *analysis* and persist all result fields."""
        from apps.ai.local_ai_service import LocalAIService

        analysis.status = AnalysisStatus.PROCESSING
        analysis.save(update_fields=['status', 'updated_at'])

        try:
            img_record = analysis.image
            buf = io.BytesIO(bytes(img_record.image_data))
            pil_image = Image.open(buf).convert('RGB')

            result = LocalAIService.classify(pil_image)

            analysis.predictions = result['predictions']
            analysis.top_class = result['top_class']
            analysis.top_confidence = result['top_confidence']
            analysis.needs_human_review = result['needs_human_review']
            analysis.inference_time_ms = result['inference_time_ms']
            analysis.model_version = result['model_version']
            analysis.status = (
                AnalysisStatus.REVIEW_NEEDED
                if result['needs_human_review']
                else AnalysisStatus.DONE
            )
            analysis.save(update_fields=[
                'status', 'predictions', 'top_class', 'top_confidence',
                'needs_human_review', 'inference_time_ms', 'model_version',
                'updated_at',
            ])

        except Exception:
            traceback.print_exc()
            analysis.status = AnalysisStatus.FAILED
            analysis.save(update_fields=['status', 'updated_at'])

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _validate_image(image_file: UploadedFile) -> None:
        """
        Run four independent checks on the upload.

        Order matters for fail-fast: cheap checks first, Pillow last.
        """
        content_type: str = getattr(image_file, 'content_type', '') or ''

        if content_type not in _ALLOWED_CONTENT_TYPES:
            allowed = ', '.join(sorted(_ALLOWED_CONTENT_TYPES))
            raise ImageValidationError(
                f'Непідтримуваний тип файлу. Дозволено: {allowed}.'
            )

        if image_file.size > _MAX_UPLOAD_SIZE:
            max_mb = _MAX_UPLOAD_SIZE // (1024 * 1024)
            raise ImageValidationError(
                f'Файл занадто великий. Максимальний розмір: {max_mb} МБ.'
            )

        header = image_file.read(12)
        image_file.seek(0)
        if not _check_magic_bytes(header):
            raise ImageValidationError(
                'Вміст файлу не відповідає оголошеному формату зображення.'
            )

        try:
            img = Image.open(image_file)
            img.verify()
        except Exception as exc:
            raise ImageValidationError(
                'Зображення пошкоджено або має невірний формат.'
            ) from exc
        finally:
            image_file.seek(0)
