from django.contrib import admin
from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter

from clientes.views import (ClienteViewSet, ContatoViewSet, EnderecoViewSet, AdministradoraViewSet,
                            ContatoAdministradoraViewSet, ResponsabilidadeViewSet)

router = DefaultRouter()
router.register("clientes", ClienteViewSet, basename="cliente")
router.register("contatos", ContatoViewSet, basename="contato")
router.register("enderecos", EnderecoViewSet, basename="endereco")
router.register("administradoras", AdministradoraViewSet, basename="administradora")
router.register("contatos-administradora", ContatoAdministradoraViewSet, basename="contatoadministradora")
router.register("responsabilidades", ResponsabilidadeViewSet, basename="responsabilidade")
from clientes.destinatarios_api import DestinatariosView, HistoricoDestinatariosView, EncerrarContatoAdministradoraView

from clientes import integracao

urlpatterns = [
    path('api/integracao/v1/clientes/', integracao.BuscaClientes.as_view()),
    path('api/integracao/v1/clientes/alteracoes/', integracao.AlteracoesClientes.as_view()),
    path('api/integracao/v1/clientes/<int:pk>/', integracao.DetalheCliente.as_view()),
    re_path(r'^api/integracao/', integracao.RotaInexistente.as_view()),
    path('api/v1/clientes/<int:pk>/destinatarios/', DestinatariosView.as_view(), {'escopo': 'cliente'}),
    path('api/v1/administradoras/<int:pk>/destinatarios/', DestinatariosView.as_view(), {'escopo': 'administradora'}),
    path('api/v1/clientes/<int:pk>/destinatarios/historico/', HistoricoDestinatariosView.as_view(), {'escopo': 'cliente'}),
    path('api/v1/administradoras/<int:pk>/destinatarios/historico/', HistoricoDestinatariosView.as_view(), {'escopo': 'administradora'}),
    path('api/v1/contatos-administradora/<int:pk>/encerrar/', EncerrarContatoAdministradoraView.as_view()),
    path("admin/", admin.site.urls),
    path("", include("painel.urls")),
    path("api/v1/", include(router.urls)),
    path("api-auth/", include("rest_framework.urls")),
]
