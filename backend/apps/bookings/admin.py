from django.contrib import admin
from .models import Booking, BookingHistory

class BookingHistoryInline(admin.TabularInline):
    model = BookingHistory
    readonly_fields = ('action', 'performed_by', 'timestamp', 'notes')
    extra = 0
    can_delete = False

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_id', 'item', 'borrower', 'start_date', 'end_date', 'status')
    list_filter = ('status', 'start_date')
    search_fields = ('booking_id', 'item__name', 'borrower__username')
    readonly_fields = ('booking_id', 'created_at', 'updated_at')
    inlines = [BookingHistoryInline]
    fieldsets = (
        ('Booking Info', {
            'fields': ('booking_id', 'item', 'borrower', 'steward')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'pickup_time', 'return_time')
        }),
        ('Status', {
            'fields': ('status', 'checked_out_at', 'returned_at', 'approved_at')
        }),
        ('Details', {
            'fields': ('purpose', 'notes', 'borrower_notes')
        }),
        ('Financial', {
            'fields': ('total_fee', 'deposit_paid', 'deposit_refunded')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(BookingHistory)
class BookingHistoryAdmin(admin.ModelAdmin):
    list_display = ('booking', 'action', 'performed_by', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('booking__booking_id', 'performed_by__username')
    readonly_fields = ('booking', 'action', 'performed_by', 'timestamp', 'notes')