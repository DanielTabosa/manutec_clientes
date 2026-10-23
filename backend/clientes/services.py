from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Cliente, Endereco, HistoricoCNPJ, Administradora, ClienteAdministradora, Responsabilidade
from .cnpj import normalizar_cnpj
from .cpf import normalizar_cpf

ENDERECO_OBRIGATORIO = ("logradouro", "numero", "bairro", "cidade", "estado", "cep")
ENDERECO_CAMPOS = ("cep", "logradouro", "numero", "complemento", "bairro", "cidade", "estado")


def alterar_administradora(cliente_id, *, acao, data, administradora=None):
    if acao not in ("vincular", "encerrar"):
        raise ValidationError({"acao": "Escolha vincular ou encerrar."})
    if data > timezone.now().date():
        raise ValidationError({"data": "A data não pode estar no futuro."})
    try:
        with transaction.atomic():
            cliente = Cliente.objects.select_for_update().get(pk=cliente_id)
            atual = cliente.historico_administradoras.filter(data_fim__isnull=True).first()
            if acao == "encerrar":
                if administradora is not None:
                    raise ValidationError({"administradora": "Não selecione administradora para encerrar o vínculo atual."})
                if atual is None:
                    raise ValidationError({"acao": "Este cliente não possui administradora atual."})
                if data < atual.data_inicio:
                    raise ValidationError({"data": "O encerramento não pode ser anterior ao início."})
                encerrar_responsabilidades(atual, data)
                atual.data_fim = data
                atual.save(update_fields=["data_fim"])
                resultado = atual
            else:
                if administradora is None or not Administradora.objects.filter(pk=administradora.pk).exists():
                    raise ValidationError({"administradora": "Escolha uma administradora cadastrada."})
                if atual and atual.administradora_id == administradora.pk:
                    raise ValidationError({"administradora": "Esta já é a administradora atual."})
                ultimo = cliente.historico_administradoras.first()
                if ultimo and data <= (ultimo.data_fim or ultimo.data_inicio):
                    raise ValidationError({"data": "Use uma data posterior ao último período registrado."})
                if atual:
                    encerrar_responsabilidades(atual, data - timedelta(days=1))
                    atual.data_fim = data - timedelta(days=1)
                    atual.save(update_fields=["data_fim"])
                resultado = ClienteAdministradora.objects.create(cliente=cliente, administradora=administradora, data_inicio=data)
            from .destinatarios import registrar_troca
            registrar_troca(cliente_id)
            cliente.save(update_fields=["atualizado_em"])
            return resultado
    except IntegrityError as exc:
        raise ValidationError({"administradora": "Não foi possível alterar o vínculo. Atualize a página e tente novamente."}) from exc


def cadastrar_cliente(*, tipo_pessoa=Cliente.PJ, cnpj=None, cpf=None, data_inicio=None, exigir_endereco=True, **dados):
    """Cadastra o cliente com o documento (CNPJ no histórico ou CPF fixo) e o endereço principal.

    Cadastro manual exige endereço completo; a importação em lote aceita incompleto (aparece como pendência)."""
    endereco = {campo: dados.pop(campo, None) for campo in ENDERECO_CAMPOS}
    errors = {campo: "Este campo é obrigatório." for campo in ENDERECO_OBRIGATORIO
              if exigir_endereco and not str(endereco.get(campo) or "").strip()}
    if tipo_pessoa == Cliente.PJ:
        if not cnpj:
            errors["cnpj"] = "Informe o CNPJ."
        else:
            cnpj = normalizar_cnpj(cnpj)
    elif tipo_pessoa == Cliente.PF:
        try:
            cpf = normalizar_cpf(cpf or "")
        except ValidationError as exc:
            errors["cpf"] = exc.messages
        else:
            if Cliente.objects.filter(cpf=cpf).exists():
                errors["cpf"] = "Este CPF já pertence a um cliente cadastrado."
    else:
        errors["tipo_pessoa"] = "Escolha pessoa jurídica ou física."
    if errors:
        raise ValidationError(errors)
    with transaction.atomic():
        cliente = Cliente(tipo_pessoa=tipo_pessoa, cpf=cpf if tipo_pessoa == Cliente.PF else None, **dados)
        cliente.full_clean()
        cliente.save()
        if tipo_pessoa == Cliente.PJ:
            trocar_cnpj(cliente.pk, cnpj, data_inicio or timezone.now().date())
        if any(str(v or "").strip() for v in endereco.values()):
            Endereco(cliente=cliente, descricao="Principal", principal=True, **endereco).save()
        return cliente


def trocar_cnpj(cliente_id, cnpj, data_inicio):
    """Serializa trocas por cliente; encerra e cria dentro da mesma transação."""
    cnpj = normalizar_cnpj(cnpj)
    try:
        with transaction.atomic():
            cliente = Cliente.objects.select_for_update().get(pk=cliente_id)
            if cliente.pessoa_fisica:
                raise ValidationError({"cnpj": "Cliente pessoa física não tem CNPJ; o documento é o CPF do cadastro."})
            novo = HistoricoCNPJ(cliente=cliente, cnpj=cnpj, data_inicio=data_inicio)
            novo.clean_fields()
            if data_inicio > timezone.now().date():
                raise ValidationError({"data_inicio": "A data não pode estar no futuro para um CNPJ atual."})
            anterior = cliente.historico_cnpj.first()
            if anterior and data_inicio <= (anterior.data_fim or anterior.data_inicio):
                raise ValidationError({"data_inicio": "Use uma data posterior ao último período registrado."})
            if HistoricoCNPJ.objects.filter(cnpj=cnpj).exists():
                raise ValidationError({"cnpj": "Este CNPJ já consta no histórico de um cliente."})
            cliente.historico_cnpj.filter(data_fim__isnull=True).update(
                data_fim=data_inicio - timedelta(days=1)
            )
            novo.save()
            cliente.save(update_fields=["atualizado_em"])
            return novo
    except IntegrityError as exc:
        raise ValidationError({"cnpj": "Não foi possível registrar: CNPJ ou vínculo atual já existente. Atualize a página."}) from exc


def encerrar_responsabilidades(vinculo, data):
    """Chamado sob transação e bloqueio do cliente por alterar_administradora."""
    registros = Responsabilidade.objects.filter(
        cliente_id=vinculo.cliente_id,
        contato_administradora__administradora_id=vinculo.administradora_id,
    )
    # Períodos antigos permanecem intocados; não truncar históricos encerrados.
    if registros.filter(data_inicio__lte=data, data_fim__gt=data).exists() or registros.filter(data_inicio__gt=data).exists():
        raise ValidationError({"data": "A data deixaria responsabilidades fora do vínculo da administradora."})
    registros.filter(data_fim__isnull=True).update(data_fim=data)
