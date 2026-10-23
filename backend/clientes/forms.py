from django import forms
from .models import HistoricoCNPJ, Cliente, Administradora, Endereco
from .cnpj import normalizar_cnpj
from .services import ENDERECO_CAMPOS, ENDERECO_OBRIGATORIO
from .cpf import normalizar_cpf
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


class CepMixin:
    def clean_cep(self):
        valor = self.cleaned_data["cep"]
        return normalizar_cep(valor) if valor else valor


class ClienteForm(forms.ModelForm):
    """Edição do cadastro. Tipo de pessoa e CNPJ têm regras próprias; endereços têm formulário próprio."""
    cpf = forms.CharField(label="CPF", max_length=14, required=False,
                          help_text="Corrija somente em caso de erro de digitação.")

    class Meta:
        model = Cliente
        fields = ["razao_social", "nome_fantasia", "cpf", "ativo", "observacoes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not (self.instance and self.instance.pessoa_fisica):
            self.fields.pop("cpf", None)
        else:
            self.fields["cpf"].required = True
            self.fields["razao_social"].label = "Nome completo"
            self.fields["razao_social"].rotulo_fixo = True
            self.fields.pop("nome_fantasia", None)
        if "ativo" in self.fields:
            self.fields["ativo"].help_text = "Cliente inativo deixa de aparecer nas sugestões do Jiraya; o cadastro e o histórico são mantidos."

    def clean_cpf(self):
        return normalizar_cpf(self.cleaned_data["cpf"])


class EnderecoForm(CepMixin, forms.ModelForm):
    cep = forms.CharField(label="CEP", max_length=9, required=True,
                          help_text="Digite o CEP para consultar o endereço. Aceita formato 00000-000.")

    class Meta:
        model = Endereco
        fields = ["descricao", "principal", "ativo", "cep", "logradouro", "numero", "complemento", "bairro", "cidade", "estado"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ENDERECO_OBRIGATORIO:
            self.fields[campo].required = True
        self.fields["numero"].help_text = "Se não houver número, informe S/N."
        self.fields["complemento"].help_text = "Bloco, torre ou apartamento ficam aqui; não são outro endereço."
        self.fields["principal"].help_text = "Marcar este desmarca o principal anterior."
        if self.instance.pk and self.instance.principal:
            # O principal só deixa de ser principal quando outro é marcado.
            for campo in ("principal", "ativo"):
                self.fields[campo].disabled = True
            self.fields["principal"].help_text = "Para trocar, marque outro endereço como principal."


class CadastroClienteForm(CepMixin, forms.ModelForm):
    tipo_pessoa = forms.ChoiceField(label="Tipo de cliente", choices=Cliente.TIPOS_PESSOA, initial=Cliente.PJ, required=False,
                                    help_text="Condomínio ou empresa: CNPJ. Residência: CPF. Não muda depois do cadastro.")
    cnpj = forms.CharField(label="CNPJ", max_length=18, required=False,
                           help_text="Ao completar o CNPJ, os dados serão consultados automaticamente.")
    cpf = forms.CharField(label="CPF", max_length=14, required=False, help_text="Aceita com ou sem pontos e traço.")
    data_inicio = forms.DateField(label="CNPJ utilizado desde", initial=lambda: timezone.now().date(), required=False,
                                 widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    cep = forms.CharField(label="CEP", max_length=9, required=True,
                          help_text="Digite o CEP para consultar o endereço. Aceita formato 00000-000.")

    class Meta:
        model = Cliente
        fields = ["tipo_pessoa", "razao_social", "nome_fantasia", "observacoes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome, campo in forms.fields_for_model(Endereco, fields=ENDERECO_CAMPOS).items():
            self.fields.setdefault(nome, campo)
        for campo in ENDERECO_OBRIGATORIO:
            self.fields[campo].required = True
        self.fields["numero"].help_text = "Se não houver número, informe S/N."
        self.fields["complemento"].help_text = "Bloco, torre ou apartamento ficam aqui."
        self.fields["razao_social"].label = "Razão social ou nome completo"
        self.fields["razao_social"].rotulo_fixo = True
        for campo in ("tipo_pessoa", "cnpj", "cpf", "data_inicio"):
            self.fields[campo].obrigatorio_conforme_tipo = True  # não exibir "(opcional)" no painel
        self.order_fields(["tipo_pessoa", "cnpj", "cpf", "razao_social", "nome_fantasia", *ENDERECO_CAMPOS,
                           "data_inicio", "observacoes"])

    def clean_tipo_pessoa(self):
        return self.cleaned_data["tipo_pessoa"] or Cliente.PJ

    def clean(self):
        dados = super().clean()
        if dados.get("tipo_pessoa") == Cliente.PF:
            dados["cnpj"] = dados["data_inicio"] = None
            try:
                dados["cpf"] = normalizar_cpf(dados.get("cpf") or "")
            except forms.ValidationError as exc:
                self.add_error("cpf", exc)
            else:
                if Cliente.objects.filter(cpf=dados["cpf"]).exists():
                    self.add_error("cpf", "Este CPF já pertence a um cliente cadastrado.")
        elif dados.get("tipo_pessoa") == Cliente.PJ:
            dados["cpf"] = None
            try:
                dados["cnpj"] = normalizar_cnpj(dados.get("cnpj") or "")
            except forms.ValidationError as exc:
                self.add_error("cnpj", exc if dados.get("cnpj") else "Informe o CNPJ.")
            else:
                if HistoricoCNPJ.objects.filter(cnpj=dados["cnpj"]).exists():
                    self.add_error("cnpj", "Este CNPJ já está cadastrado no histórico de um cliente.")
            if not dados.get("data_inicio"):
                self.add_error("data_inicio", "Informe desde quando o CNPJ é utilizado.")
        return dados

    def _post_clean(self):
        # O CPF validado vai para a instância antes da validação do modelo.
        self.instance.cpf = self.cleaned_data.get("cpf")
        super()._post_clean()
