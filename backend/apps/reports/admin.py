from django.contrib import admin

from .models import LabelTranslation


@admin.register(LabelTranslation)
class LabelTranslationAdmin(admin.ModelAdmin):
    list_display = ['raw_label_en', 'translated_uk', 'is_manual', 'updated_at']
    list_editable = ['translated_uk', 'is_manual']
    search_fields = ['raw_label_en', 'translated_uk']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['raw_label_en']
