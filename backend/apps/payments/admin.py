from django.contrib import admin
from .models import Transaction, Contribution, Payout

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'user', 'amount', 'payment_method', 'status', 'created_at')
    list_filter = ('status', 'payment_method', 'transaction_type')
    search_fields = ('transaction_id', 'payhero_reference', 'user__username')
    readonly_fields = ('transaction_id', 'created_at', 'completed_at')
    fieldsets = (
        ('Transaction Info', {
            'fields': ('transaction_id', 'payhero_reference', 'payhero_checkout_id')
        }),
        ('Details', {
            'fields': ('transaction_type', 'status', 'payment_method', 'amount', 'currency')
        }),
        ('M-Pesa', {
            'fields': ('phone_number', 'mpesa_receipt'),
            'classes': ('collapse',)
        }),
        ('Related', {
            'fields': ('user', 'campaign', 'booking', 'organization')
        }),
        ('Metadata', {
            'fields': ('description', 'metadata')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'completed_at', 'updated_at')
        }),
    )

@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ('user', 'campaign', 'amount', 'is_anonymous', 'created_at')
    list_filter = ('is_anonymous', 'created_at')
    search_fields = ('user__username', 'campaign__title')
    readonly_fields = ('created_at',)

@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ('payout_id', 'organization', 'campaign', 'amount', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('payout_id', 'organization__name')
    readonly_fields = ('payout_id', 'created_at', 'processed_at')