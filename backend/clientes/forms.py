from django import forms
from .models import HistoricoCNPJ, Cliente, Administradora
from .cnpj import normalizar_cnpj
from .services import ENDERECO_OBRIGATORIO
from django.utils import timezone
from .consulta import normalizar_cep


class AdministradoraForm(forms.ModelForm):
    cnpj = forms.CharField(label="CNPJ", max_length=18, required=False,
                          help_text="Opcional para administradoras; aceita máscara.")

    class Meta:
        model = Administradora
        fields = ["cnpj", "razao_social", "nome_fantasia", "telefone", "email"]

    def clean_cnpj(self):
        valor = self.cleaned_data["cnpj"]
        return normalizar_cnpj(valor) if valor else None


class VinculoAdministradoraForm(forms.Form):
    acao = forms.ChoiceField(label="Operação", choices=[("vincular", "Vincular / trocar administradora"), ("encerrar", "Encerrar vínculo atual")])
    administradora = forms.ModelChoiceField(queryset=Administradora.objects.all(), required=False,
        help_text="Selecione para vincular ou trocar. Para encerrar, deixe em branco.")
    data = forms.DateField(label="Data", initial=lambda: timezone.now().date(),
        help_text="Início do novo vínculo ou encerramento do atual, conforme a operação.",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))


class TrocaCNPJForm(forms.Form):
    cnpj = forms.CharField(label="Novo CNPJ", max_length=18, help_text="CNPJ numérico ou alfanumérico, com ou sem máscara.")
    data_inicio = forms.DateField(label="Data de início", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))

    def clean_cnpj(self):
        return normalizar_cnpj(self.cleaned_data["cnpj"])


class ClienteEnderecoForm(forms.ModelForm):
    cep = forms.CharField(label="CEP", max_length=9, required=False,
                          help_text="Digite o CEP para consultar o endereço. Aceita formato 00000-000.")

    class Meta:
        model = Cliente
        fields = "__all__"

    def clean_cep(self):
        valor = self.cleaned_data["cep"]
        return normalizar_cep(valor) if valor else valor


class CadastroClienteForm(ClienteEnderecoForm):
    cnpj = forms.CharField(label="CNPJ", max_length=18, help_text="Ao completar o CNPJ, os dados serão consultados automaticamente.")
    data_inicio = forms.DateField(label="CNPJ utilizado desde", initial=lambda: timezone.now().date(),
                                 widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))

    class Meta:
        model = Cliente
        fields = ["cnpj", "razao_social", "nome_fantasia", "cep", "logradouro", "numero", "complemento",
                  "bairro", "cidade", "estado", "data_inicio", "observacoes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ENDERECO_OBRIGATORIO:
            self.fields[campo].required = True
        self.fields["numero"].help_text = "Se não houver número, informe S/N."

    def clean_cnpj(self):
        cnpj = normalizar_cnpj(self.cleaned_data["cnpj"])
        if HistoricoCNPJ.objects.filter(cnpj=cnpj).exists():
            raise forms.ValidationError("Este CNPJ já está cadastrado no histórico de um cliente.")
        return cnpj
