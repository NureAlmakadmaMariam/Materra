from django.db import models


class LabelTranslation(models.Model):
    """
    Cached Ukrainian translations for raw ImageNet labels.

    Auto-populated on first encounter via MyMemory API.
    Admin can correct any entry by editing translated_uk and
    setting is_manual=True — manual entries are never overwritten
    by the API.
    """

    raw_label_en = models.CharField(max_length=200, unique=True)
    translated_uk = models.CharField(max_length=200)
    is_manual = models.BooleanField(
        default=False,
        help_text='Якщо позначено, цей переклад не буде перезаписаний автоматично.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Переклад мітки'
        verbose_name_plural = 'Переклади міток'
        ordering = ['raw_label_en']

    def __str__(self) -> str:
        manual = ' ✎' if self.is_manual else ''
        return f'{self.raw_label_en} → {self.translated_uk}{manual}'
