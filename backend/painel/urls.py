from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'painel'

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('entrar/', views.Entrar.as_view(), name='entrar'),
    path('sair/', auth_views.LogoutView.as_view(), name='sair'),
    path('clientes/', views.clientes, name='clientes'),
    path('clientes/<int:pk>/', views.cliente, name='cliente'),
    path('preparacoes/', views.preparacoes, name='preparacoes'),
    path('preparacoes/nova/', views.nova_preparacao, name='nova_preparacao'),
    path('preparacoes/<int:pk>/', views.preparacao, name='preparacao'),
    path('preparacoes/<int:pk>/documento/<int:doc_pk>/', views.documento, name='documento'),
]
