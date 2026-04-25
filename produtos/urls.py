from django.urls import path
from django.urls import include
from rest_framework.routers import DefaultRouter

from . import views


router = DefaultRouter()
router.register(r'produtos', views.ProdutoViewSet, basename='produto')

urlpatterns = [
    path('api/', include(router.urls)),

    # Step 1 — Landing
    path('', views.landing, name='landing'),

    # Presentation page with all products
    path('all-catalogue', views.all_catalogue, name='all_catalogue'),

    # Step 2 — Interest selection
    path('interesse/', views.select_interest, name='select_interest'),

    # Step 3 — Product catalogue
    path('catalogo/', views.catalogue, name='catalogue'),

    # Step 3 → 4 — AJAX: save selected products to session
    path('selecionar/', views.save_selection, name='save_selection'),

    # Step 4 — AI recommendations
    path('recomendacoes/', views.recommendations, name='recommendations'),

    # Step 5 — Survey
    path('pesquisa/', views.survey, name='survey'),

    # Step 6 — Thank you
    path('obrigado/', views.thank_you, name='thank_you'),
]