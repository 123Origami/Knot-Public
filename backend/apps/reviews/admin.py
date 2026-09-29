from django.contrib import admin
from .models import Review

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'reviewer', 'reviewee', 'booking', 'rating', 'created_at')
    list_filter = ('rating', 'review_type', 'created_at')
    search_fields = ('reviewer__username', 'reviewee__username', 'comment')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Review Info', {
            'fields': ('booking', 'review_type', 'rating')
        }),
        ('Users', {
            'fields': ('reviewer', 'reviewee')
        }),
        ('Content', {
            'fields': ('comment', 'response')
        }),
        ('Ratings', {
            'fields': ('communication_rating', 'item_condition_rating', 'timeliness_rating'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'responded_at'),
            'classes': ('collapse',)
        }),
    )