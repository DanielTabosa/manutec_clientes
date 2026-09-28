from .destinatarios_admin import DestinatariosAdminMixin
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from .models import ContatoAdministradora, Responsabilidade
from .models import Cliente, HistoricoCNPJ, Contato
from .forms import TrocaCNPJForm, CadastroClienteForm, ClienteEnderecoForm
from .services import trocar_cnpj, cadastrar_cliente
from .consulta import consultar_cnpj, consultar_cep, ErroConsulta
from .models import Administradora, ClienteAdministradora
from .forms import AdministradoraForm, VinculoAdministradoraForm
from .services import alterar_administradora


class HistoricoAdministradoraInline(admin.TabularInline):
    template = "admin/clientes/inline_com_acoes.html"
    secao = "administradora"
    verbose_name_plural = "Administradora e histórico de vínculos"
    model = ClienteAdministradora
    fields = ["administradora", "data_inicio", "data_fim"]
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("clientes.view_cliente")


@admin.register(Administradora)
class AdministradoraAdmin(DestinatariosAdminMixin, admin.ModelAdmin):
    form = AdministradoraForm
    change_form_template = "admin/clientes/editar_administradora.html"
    list_display = ["razao_social", "nome_fantasia", "cnpj", "telefone", "email"]
    search_fields = ["razao_social", "nome_fantasia", "cnpj"]
    readonly_fields = ["criado_em", "atualizado_em", "gerenciar_destinatarios"]

    def get_urls(self):
        return [path("consultar-cnpj/", self.admin_site.admin_view(self.consulta_cnpj_view), name="clientes_administradora_consultar_cnpj")] + super().get_urls()

    def consulta_cnpj_view(self, request):
        if not (self.has_add_permission(request) or self.has_change_permission(request)):
            raise PermissionDenied
        try:
            return JsonResponse(consultar_cnpj(request.GET.get("cnpj", "")))
        except ValidationError as exc:
            return JsonResponse({"erro": " ".join(exc.messages)}, status=400)
        except ErroConsulta as exc:
            return JsonResponse({"erro": str(exc)}, status=503)

    def has_delete_permission(self, request, obj=None):
        return False


class HistoricoCNPJInline(admin.TabularInline):
    template = "admin/clientes/inline_com_acoes.html"
    secao = "cnpj"
    verbose_name_plural = "CNPJ e histórico"
    model = HistoricoCNPJ
    fields = ["cnpj", "data_inicio", "data_fim"]
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("clientes.view_cliente")


class ContatoInline(admin.TabularInline):
    template = "admin/clientes/inline_com_acoes.html"
    secao = "contatos"
    verbose_name_plural = "Contatos do condomínio"
    model = Contato
    fields = ["nome", "funcao", "telefone", "email", "data_inicio", "data_fim"]
    readonly_fields = fields
    show_change_link = True
    can_delete = False
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class VigenciaContatoFilter(admin.SimpleListFilter):
    title = "vigência"
    parameter_name = "vigente"

    def lookups(self, request, model_admin):
        return [("true", "Atuais"), ("false", "Encerrados")]

    def queryset(self, request, queryset):
        if self.value() in ("true", "false"):
            return queryset.filter(data_fim__isnull=self.value() == "true")
        return queryset


@admin.register(Contato)
class ContatoAdmin(admin.ModelAdmin):
    fields = ["cliente", "nome", "funcao", "telefone", "email", "data_inicio", "data_fim"]
    list_display = ["nome", "funcao", "cliente", "telefone", "email", "data_inicio", "data_fim", "vigente"]
    list_filter = [VigenciaContatoFilter]
    search_fields = ["nome", "funcao", "cliente__razao_social"]
    list_select_related = ["cliente"]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "cliente" in form.base_fields:
            # O cadastro de cliente tem fluxo próprio, fora do popup do Django.
            form.base_fields["cliente"].widget.can_add_related = False
        return form

    def response_add(self, request, obj, post_url_continue=None):
        if (request.GET.get("cliente") == str(obj.cliente_id)
                and "_save" in request.POST and "_popup" not in request.POST):
            response = super().response_add(request, obj, post_url_continue)
            response["Location"] = reverse("admin:clientes_cliente_change", args=[obj.cliente_id]) + "#contatos-group"
            return response
        return super().response_add(request, obj, post_url_continue)

    @admin.display(boolean=True, description="Vigente")
    def vigente(self, obj):
        return obj.data_fim is None

    def get_readonly_fields(self, request, obj=None):
        return ["cliente"] if obj else []

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Cliente)
class ClienteAdmin(DestinatariosAdminMixin, admin.ModelAdmin):
    form = ClienteEnderecoForm
    change_form_template = "admin/clientes/editar_cliente.html"
    fields = ["razao_social", "nome_fantasia", "cep", "logradouro", "numero", "complemento",
              "bairro", "cidade", "estado", "observacoes", "gerenciar_destinatarios", "id", "criado_em", "atualizado_em"]
    list_display = ["id", "razao_social", "nome_fantasia", "cidade", "estado"]
    search_fields = ["razao_social", "nome_fantasia", "cidade"]
    readonly_fields = ["id", "criado_em", "atualizado_em", "gerenciar_destinatarios"]
    inlines = [HistoricoCNPJInline, ContatoInline, HistoricoAdministradoraInline]

    def administradora_view(self, request, cliente_id):
        obj = self.get_object(request, cliente_id)
        if obj is None:
            raise Http404
        if not self.has_change_permission(request, obj) or not request.user.has_perm("clientes.view_administradora"):
            raise PermissionDenied
        form = VinculoAdministradoraForm(request.POST if request.method == "POST" else None)
        if request.method == "POST" and form.is_valid():
            try:
                alterar_administradora(obj.pk, **form.cleaned_data)
            except ValidationError as exc:
                for field, errors in exc.message_dict.items():
                    for error in errors:
                        form.add_error(field, error)
            else:
                self.log_change(request, obj, "Vínculo de administradora: " + form.cleaned_data["acao"])
                self.message_user(request, "Vínculo atualizado. O histórico foi preservado.")
                return redirect(reverse("admin:clientes_cliente_change", args=[obj.pk]) + "#historico_administradoras-group")
        atual = obj.historico_administradoras.filter(data_fim__isnull=True).select_related("administradora").first()
        return TemplateResponse(request, "admin/clientes/administradora.html", {
            **self.admin_site.each_context(request), "title": "Administradora do cliente",
            "opts": self.model._meta, "original": obj, "form": form, "atual": atual,
        })

    def get_urls(self):
        return [path("consultar-cnpj/", self.admin_site.admin_view(self.consulta_view), name="clientes_consultar_cnpj"),
                path("<int:cliente_id>/administradora/", self.admin_site.admin_view(self.administradora_view), name="clientes_cliente_administradora"),
                path("consultar-cep/", self.admin_site.admin_view(self.consulta_cep_view), name="clientes_consultar_cep"),
                path("<int:cliente_id>/cnpj/", self.admin_site.admin_view(self.cnpj_view), name="clientes_cliente_cnpj")] + super().get_urls()

    def consulta_cep_view(self, request):
        if not (self.has_add_permission(request) or self.has_change_permission(request)):
            raise PermissionDenied
        try:
            return JsonResponse(consultar_cep(request.GET.get("cep", "")))
        except ValidationError as exc:
            return JsonResponse({"erro": " ".join(exc.messages)}, status=400)
        except ErroConsulta as exc:
            return JsonResponse({"erro": str(exc)}, status=503)

    def consulta_view(self, request):
        if not (self.has_add_permission(request) or self.has_change_permission(request)):
            raise PermissionDenied
        try:
            return JsonResponse(consultar_cnpj(request.GET.get("cnpj", "")))
        except ValidationError as exc:
            return JsonResponse({"erro": " ".join(exc.messages)}, status=400)
        except ErroConsulta as exc:
            return JsonResponse({"erro": str(exc)}, status=503)

    def add_view(self, request, form_url="", extra_context=None):
        if not self.has_add_permission(request):
            raise PermissionDenied
        form = CadastroClienteForm(request.POST if request.method == "POST" else None)
        if request.method == "POST" and form.is_valid():
            try:
                obj = cadastrar_cliente(**form.cleaned_data)
            except ValidationError as exc:
                if hasattr(exc, "message_dict"):
                    for field, errors in exc.message_dict.items():
                        for error in errors:
                            form.add_error(field if field in form.fields else None, error)
                else:
                    form.add_error("cnpj", exc)
            else:
                self.log_addition(request, obj, "Cliente e CNPJ cadastrados juntos.")
                self.message_user(request, "Cliente cadastrado com CNPJ e endereço.")
                return redirect("admin:clientes_cliente_changelist")
        return TemplateResponse(request, "admin/clientes/cadastrar_cliente.html", {
            **self.admin_site.each_context(request), "title": "Cadastrar cliente",
            "opts": self.model._meta, "form": form,
        })

    def cnpj_view(self, request, cliente_id):
        obj = self.get_object(request, cliente_id)
        if obj is None:
            raise Http404
        if not self.has_change_permission(request, obj):
            raise PermissionDenied
        form = TrocaCNPJForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            try:
                trocar_cnpj(obj.pk, **form.cleaned_data)
            except ValidationError as exc:
                for field, errors in exc.message_dict.items():
                    for error in errors:
                        form.add_error(field, error)
            else:
                self.message_user(request, "CNPJ registrado. O histórico anterior foi preservado.")
                return redirect(reverse("admin:clientes_cliente_change", args=[obj.pk]) + "#historico_cnpj-group")
        return TemplateResponse(request, "admin/clientes/trocar_cnpj.html", {
            **self.admin_site.each_context(request), "title": "Cadastrar / trocar CNPJ",
            "opts": self.model._meta, "original": obj, "form": form,
        })

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ContatoAdministradora)
class ContatoAdministradoraAdmin(admin.ModelAdmin):
    actions = ['encerrar_destinatario']

    @admin.action(description='Encerrar contato na empresa inteira (todos os destinatários)')
    def encerrar_destinatario(self, request, queryset):
        if not request.user.has_perms(['clientes.change_contatoadministradora', 'clientes.change_configuracaodestinatarios']):
            raise PermissionDenied
        from .destinatarios import encerrar_global
        for pk in queryset.values_list('pk', flat=True):
            encerrar_global(pk)
        self.message_user(request, 'Contatos encerrados para todas as comunicações da empresa.')

    list_display = ["nome", "administradora", "telefone", "email"]
    search_fields = ["nome", "administradora__razao_social"]
    list_filter = ["administradora"]
    list_select_related = ["administradora"]
    readonly_fields = ["criado_em"]

    def get_readonly_fields(self, request, obj=None):
        return ["criado_em", "encerrado_em", "administradora"] if obj else ["criado_em", "encerrado_em"]

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Responsabilidade)
class ResponsabilidadeAdmin(admin.ModelAdmin):
    list_display = ["contato_administradora", "cliente", "funcao", "data_inicio", "data_fim"]
    search_fields = ["contato_administradora__nome", "cliente__razao_social", "funcao"]
    list_filter = [VigenciaContatoFilter, "contato_administradora__administradora"]
    list_select_related = ["cliente", "contato_administradora__administradora"]
    autocomplete_fields = ["cliente", "contato_administradora"]

    def get_readonly_fields(self, request, obj=None):
        return ["cliente", "contato_administradora"] if obj else []

    def has_delete_permission(self, request, obj=None):
        return False
