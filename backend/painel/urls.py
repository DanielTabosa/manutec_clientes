from django.contrib.auth import views as auth_views
from django.urls import path

from . import cadastros, importar, views

app_name = 'painel'

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('entrar/', views.Entrar.as_view(), name='entrar'),
    path('busca/', views.busca, name='busca'),
    path('contratos/resumo/', views.contratos_resumo, name='contratos_resumo'),
    path('sair/', auth_views.LogoutView.as_view(), name='sair'),
    path('consultas/cnpj/', cadastros.consulta_cnpj, name='consulta_cnpj'),
    path('consultas/cep/', cadastros.consulta_cep, name='consulta_cep'),
    path('clientes/', views.clientes, name='clientes'),
    path('clientes/novo/', cadastros.cliente_novo, name='cliente_novo'),
    path('clientes/<int:pk>/', views.cliente, name='cliente'),
    path('clientes/<int:pk>/editar/', cadastros.cliente_editar, name='cliente_editar'),
    path('clientes/<int:pk>/cnpj/', cadastros.cliente_cnpj, name='cliente_cnpj'),
    path('clientes/<int:pk>/administradora/', cadastros.cliente_administradora, name='cliente_administradora'),
    path('clientes/<int:pk>/destinatarios/', cadastros.cliente_destinatarios, name='cliente_destinatarios'),
    path('clientes/<int:cliente_pk>/contatos/novo/', cadastros.contato_novo, name='contato_novo'),
    path('contatos/<int:pk>/editar/', cadastros.contato_editar, name='contato_editar'),
    path('administradoras/', cadastros.administradoras, name='administradoras'),
    path('administradoras/nova/', cadastros.administradora_nova, name='administradora_nova'),
    path('administradoras/<int:pk>/', cadastros.administradora, name='administradora'),
    path('administradoras/<int:pk>/editar/', cadastros.administradora_editar, name='administradora_editar'),
    path('administradoras/<int:pk>/destinatarios/', cadastros.administradora_destinatarios, name='administradora_destinatarios'),
    path('administradoras/<int:adm_pk>/contatos/novo/', cadastros.contato_adm_novo, name='contato_adm_novo'),
    path('contatos-administradora/<int:pk>/editar/', cadastros.contato_adm_editar, name='contato_adm_editar'),
    path('contatos-administradora/<int:pk>/encerrar/', cadastros.contato_adm_encerrar, name='contato_adm_encerrar'),
    path('importar/', importar.inicio, name='importar'),
    path('importar/previa/', importar.previa, name='importar_previa'),
    path('importar/resultado/', importar.resultado, name='importar_resultado'),
    path('importar/modelo/<str:tipo>/', importar.modelo, name='importar_modelo'),
    path('preparacoes/', views.preparacoes, name='preparacoes'),
    path('preparacoes/nova/', views.nova_preparacao, name='nova_preparacao'),
    path('preparacoes/<int:pk>/', views.preparacao, name='preparacao'),
    path('preparacoes/<int:pk>/documento/<int:doc_pk>/', views.documento, name='documento'),
]
