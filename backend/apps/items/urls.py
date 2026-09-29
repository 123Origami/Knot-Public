from django.urls import path
from . import views

urlpatterns = [
    # API endpoints
    path('items/', views.ItemListView.as_view(), name='item-list'),
    path('items/<slug:slug>/', views.ItemDetailView.as_view(), name='item-detail-api'),
    path('items/<int:item_id>/availability/', views.ItemAvailabilityView.as_view(), name='item-availability'),
    path('items/<int:item_id>/delete/', views.ItemDeleteView.as_view(), name='item-delete'),
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('stats/', views.ItemStatsView.as_view(), name='item-stats'),
    path('suggestions/', views.SuggestionListCreateView.as_view(), name='suggestion-list-create'),
    path('suggestions/<int:suggestion_id>/vote/', views.SuggestionVoteToggleView.as_view(), name='suggestion-vote-toggle'),
    path('suggestions/<int:suggestion_id>/approve/', views.SuggestionApproveView.as_view(), name='suggestion-approve'),
    path('suggestions/<int:suggestion_id>/reject/', views.SuggestionRejectView.as_view(), name='suggestion-reject'),
    path('suggestions/<int:suggestion_id>/delete/', views.SuggestionDeleteView.as_view(), name='suggestion-delete'),
    
    # HTML template views
    path('detail/<slug:slug>/', views.item_detail_page, name='item-detail'),

    path('<slug:slug>/book/', views.book_item_page, name='book-item'),
]