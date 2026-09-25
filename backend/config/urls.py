from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from clientes.views import ClienteViewSet, ContatoViewSet, AdministradoraViewSet

router = DefaultRouter()
router.register("clientes", ClienteViewSet, basename="cliente")
router.register("contatos", ContatoViewSet, basename="contato")
router.register("administradoras", AdministradoraViewSet, basename="administradora")
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(router.urls)),
    path("api-auth/", include("rest_framework.urls")),
]
