from django.contrib import admin
from .models import Conversation, Message

class MessageInline(admin.TabularInline):
    model = Message
    readonly_fields = ('sender', 'content', 'created_at', 'is_read')
    extra = 0
    can_delete = False

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'created_at', 'updated_at', 'is_active')
    list_filter = ('is_active', 'created_at')
    filter_horizontal = ('participants',)
    inlines = [MessageInline]
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender', 'content_preview', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('content', 'sender__username')
    readonly_fields = ('created_at', 'read_at')
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Message'