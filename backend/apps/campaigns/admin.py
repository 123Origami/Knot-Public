from django.contrib import admin
from .models import Organization, Campaign

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_email', 'contact_phone', 'is_verified', 'is_active')
    list_filter = ('is_verified', 'is_active')
    search_fields = ('name', 'contact_email', 'address')
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ('stewards',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'logo')
        }),
        ('Contact', {
            'fields': ('address', 'contact_email', 'contact_phone', 'website')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude')
        }),
        ('Payment Details', {
            'fields': ('payhero_merchant_id', 'bank_name', 'account_name', 
                      'account_number_encrypted', 'bank_code'),
            'classes': ('collapse',)
        }),
        ('Staff & Status', {
            'fields': ('stewards', 'is_verified', 'is_active')
        }),
    )

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('title', 'host_organization', 'target_amount', 'funds_raised', 
                   'get_progress_percentage', 'status', 'end_date')
    list_filter = ('status', 'category', 'host_organization')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('funds_raised', 'contributor_count', 'funded_date', 'created_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'description', 'image', 'category')
        }),
        ('Financial', {
            'fields': ('target_amount', 'funds_raised', 'min_contribution')
        }),
        ('Related', {
            'fields': ('suggested_item', 'created_by', 'host_organization')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'funded_date')
        }),
        ('Status', {
            'fields': ('status', 'contributor_count')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )