from rest_framework.permissions import DjangoModelPermissions


class PermissoesCliente(DjangoModelPermissions):
    # DjangoModelPermissions nao exige view por padrao em consultas GET.
    perms_map = {
        **DjangoModelPermissions.perms_map,
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": ["%(app_label)s.view_%(model_name)s"],
    }

    def has_permission(self, request, view):
        if getattr(view, "action", None) == "administradora" and request.method == "POST":
            return bool(request.user and request.user.is_authenticated and request.user.has_perms(["clientes.change_cliente", "clientes.view_administradora"]))
        if getattr(view, "action", None) == "cnpj" and request.method == "POST":
            return bool(request.user and request.user.is_authenticated and request.user.has_perm("clientes.change_cliente"))
        return super().has_permission(request, view)
