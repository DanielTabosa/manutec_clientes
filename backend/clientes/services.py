from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Cliente, HistoricoCNPJ, Administradora, ClienteAdministradora, Responsabilidade
from .cnpj import normalizar_cnpj

ENDERECO_OBRIGATORIO = ("logradouro", "numero", "bairro", "cidade", "estado", "cep")


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


def cadastrar_cliente(*, cnpj, data_inicio=None, **dados):
    cnpj = normalizar_cnpj(cnpj)
    errors = {campo: "Este campo é obrigatório." for campo in ENDERECO_OBRIGATORIO if not str(dados.get(campo) or "").strip()}
    if errors:
        raise ValidationError(errors)
    with transaction.atomic():
        cliente = Cliente(**dados)
        cliente.full_clean()
        cliente.save()
        trocar_cnpj(cliente.pk, cnpj, data_inicio or timezone.now().date())
        return cliente


def trocar_cnpj(cliente_id, cnpj, data_inicio):
    """Serializa trocas por cliente; encerra e cria dentro da mesma transação."""
    cnpj = normalizar_cnpj(cnpj)
    try:
        with transaction.atomic():
            cliente = Cliente.objects.select_for_update().get(pk=cliente_id)
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
