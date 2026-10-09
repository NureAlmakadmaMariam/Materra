from django.contrib import admin

from .models import Analysis, WasteClass


@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    list_display = ['id', 'status', 'user', 'top_class', 'created_at']
    list_filter = ['status']
    search_fields = ['id', 'user__email', 'image_filename']
    readonly_fields = [
        'id', 'created_at', 'updated_at',
        'predictions', 'top_class', 'top_confidence',
        'model_version', 'inference_time_ms',
    ]
    fieldsets = [
        ('Identity', {
            'fields': ['id', 'user', 'status', 'needs_human_review'],
        }),
        ('Image', {
            'fields': ['image_filename', 'image_size_bytes'],
        }),
        ('AI Results', {
            'fields': [
                'predictions', 'top_class', 'top_confidence',
                'model_version', 'inference_time_ms',
            ],
            'classes': ['collapse'],
        }),
        ('Metadata', {
            'fields': ['notes', 'created_at', 'updated_at'],
        }),
    ]


@admin.register(WasteClass)
class WasteClassAdmin(admin.ModelAdmin):
    list_display = ['code', 'label_uk', 'label_en', 'ecological_score', 'is_hazardous']
    list_filter = ['is_hazardous']
    search_fields = ['code', 'label_uk', 'label_en']
    readonly_fields = ['id', 'created_at']
    ordering = ['code']
