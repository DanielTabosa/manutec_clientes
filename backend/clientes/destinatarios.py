from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import (Cliente, Administradora, Contato, ContatoAdministradora,
                     ClienteAdministradora, ConfiguracaoDestinatarios, RevisaoDestinatarios, ItemDestinatario)
from .destinatarios_models import CATEGORIAS


def atual(**titular):
    return RevisaoDestinatarios.objects.filter(configuracao__in=ConfiguracaoDestinatarios.objects.filter(**titular)).first()


def itens_da_revisao(revisao):
    if not revisao:
        return []
    return list(revisao.itens.order_by('contato_id', 'contato_administradora_id').values('contato_id', 'contato_administradora_id', 'encerrado_local', *CATEGORIAS))


def normalizar(itens):
    resultado = []
    vistos = set()
    for item in itens:
        item = dict(item)
        cid, aid = item.get('contato_id'), item.get('contato_administradora_id')
        if bool(cid) == bool(aid):
            raise ValidationError({'itens': 'Selecione exatamente um contato por item.'})
        chave = ('cliente' if cid else 'administradora', cid or aid)
        if chave in vistos:
            raise ValidationError({'itens': 'Contato repetido na configuração.'})
        vistos.add(chave)
        registro = dict(contato_id=cid, contato_administradora_id=aid, encerrado_local=item.get('encerrado_local', False))
        registro.update({c: item.get(c, False) for c in CATEGORIAS})
        if any(type(registro[c]) is not bool for c in (*CATEGORIAS, 'encerrado_local')):
            raise ValidationError({'itens': 'Categorias e encerramento devem ser booleanos.'})
        categorias = any(registro[c] for c in CATEGORIAS)
        if (registro['encerrado_local'] and (cid or categorias)) or (not registro['encerrado_local'] and not categorias):
            raise ValidationError({'itens': 'Selecione categorias ou encerre o contato da administradora neste condomínio.'})
        resultado.append(registro)
    return sorted(resultado, key=lambda i: (i['contato_id'] or 0, i['contato_administradora_id'] or 0))


@transaction.atomic
def salvar(*, cliente_id=None, administradora_id=None, numero, itens, modo='usar', vinculo_id=None, autor=None, motivo='Configuração alterada'):
    if bool(cliente_id) == bool(administradora_id):
        raise ValidationError({'titular': 'Informe um titular.'})
    if not cliente_id and vinculo_id is not None:
        raise ValidationError({'vinculo_id': 'O padrão da empresa não recebe vínculo de condomínio.'})
    titular = {'cliente_id': cliente_id} if cliente_id else {'administradora_id': administradora_id}
    vinculo = None
    if cliente_id:
        Cliente.objects.select_for_update().get(pk=cliente_id)
        vinculo = ClienteAdministradora.objects.filter(cliente_id=cliente_id, data_fim__isnull=True).first()
        if vinculo_id != (vinculo.pk if vinculo else None):
            raise ValidationError({'vinculo_id': 'A administradora mudou. Recarregue a configuração.'})
        administradora_id = vinculo.administradora_id if vinculo else None
    if administradora_id:
        Administradora.objects.select_for_update().get(pk=administradora_id)
    config, _ = ConfiguracaoDestinatarios.objects.get_or_create(**titular)
    anterior = config.revisoes.first()
    if numero != (anterior.numero if anterior else 0):
        raise ValidationError({'numero': 'Configuração alterada por outro operador. Recarregue.'})
    if modo not in ('usar', 'complementar', 'substituir') or (not cliente_id and modo != 'usar'):
        raise ValidationError({'modo': 'Modo inválido para esta configuração.'})
    dados = normalizar(itens)
    for item in dados:
        if item['contato_id']:
            if not cliente_id or not Contato.objects.filter(pk=item['contato_id'], cliente_id=cliente_id, data_fim__isnull=True).exists():
                raise ValidationError({'itens': 'Contato do condomínio inválido ou encerrado.'})
        else:
            if not administradora_id or not ContatoAdministradora.objects.filter(pk=item['contato_administradora_id'], administradora_id=administradora_id, encerrado_em__isnull=True).exists():
                raise ValidationError({'itens': 'Contato da administradora inválido ou encerrado.'})
            if item['encerrado_local'] and not cliente_id:
                raise ValidationError({'itens': 'Encerramento local exige um condomínio.'})
            if cliente_id and modo == 'usar' and not item['encerrado_local']:
                raise ValidationError({'modo': 'Para contatos específicos, escolha complementar ou substituir.'})
    # Supressões locais não desaparecem ao editar outra seleção.
    if anterior and anterior.vinculo_id == vinculo_id:
        novos_ids = {i['contato_administradora_id']: i for i in dados if i['contato_administradora_id']}
        for antigo in itens_da_revisao(anterior):
            if antigo['encerrado_local']:
                novo = novos_ids.get(antigo['contato_administradora_id'])
                if novo and not novo['encerrado_local']:
                    raise ValidationError({'itens': 'Contato encerrado neste condomínio.'})
                if not novo:
                    dados.append(antigo)
    dados = normalizar(dados)
    if anterior and anterior.modo == modo and anterior.vinculo_id == vinculo_id and normalizar(itens_da_revisao(anterior)) == dados:
        return anterior
    revisao = config.revisoes.create(numero=numero + 1, modo=modo, vinculo=vinculo, autor=autor, motivo=motivo)
    ItemDestinatario.objects.bulk_create([ItemDestinatario(revisao=revisao, **item) for item in dados])
    return revisao


def efetivos(cliente_id):
    revisao = atual(cliente_id=cliente_id)
    vinculo = ClienteAdministradora.objects.filter(cliente_id=cliente_id, data_fim__isnull=True).first()
    locais = itens_da_revisao(revisao)
    mesmo = bool(revisao and vinculo and revisao.vinculo_id == vinculo.pk)
    modo = revisao.modo if mesmo else 'usar'
    padrao = atual(administradora_id=vinculo.administradora_id) if vinculo and modo != 'substituir' else None
    entradas = [(i, 'condominio') for i in locais if i['contato_id']]
    entradas += [(i, 'padrao') for i in itens_da_revisao(padrao)]
    if mesmo and modo != 'usar':
        entradas += [(i, 'especifico') for i in locais if i['contato_administradora_id'] and not i['encerrado_local']]
    excluidos = {i['contato_administradora_id'] for i in locais if mesmo and i['encerrado_local']}
    resultado = {}
    for item, origem in entradas:
        cid, aid = item['contato_id'], item['contato_administradora_id']
        if cid:
            contato = Contato.objects.filter(pk=cid, cliente_id=cliente_id, data_fim__isnull=True).first()
        else:
            contato = ContatoAdministradora.objects.filter(pk=aid, administradora_id=vinculo.administradora_id, encerrado_em__isnull=True).first() if vinculo and aid not in excluidos else None
        if not contato:
            continue
        chave = ('cliente' if cid else 'administradora', contato.pk)
        registro = resultado.setdefault(chave, dict(contato_id=cid, contato_administradora_id=aid, nome=contato.nome, email=contato.email, telefone=contato.telefone, categorias=[], origens=[]))
        registro['categorias'] = [c for c in CATEGORIAS if c in registro['categorias'] or item[c]]
        if origem not in registro['origens']:
            registro['origens'].append(origem)
    return list(resultado.values())


@transaction.atomic
def encerrar_global(contato_id):
    contato = ContatoAdministradora.objects.get(pk=contato_id)
    Administradora.objects.select_for_update().get(pk=contato.administradora_id)
    contato.refresh_from_db()
    if contato.encerrado_em is None:
        contato.encerrado_em = timezone.now()
        contato.save(update_fields=['encerrado_em'])
    return contato


def registrar_troca(cliente_id):
    anterior = atual(cliente_id=cliente_id)
    if not anterior:
        return
    vinculo = ClienteAdministradora.objects.filter(cliente_id=cliente_id, data_fim__isnull=True).first()
    salvar(cliente_id=cliente_id, numero=anterior.numero, vinculo_id=vinculo.pk if vinculo else None,
           itens=[i for i in itens_da_revisao(anterior) if i['contato_id'] and Contato.objects.filter(pk=i['contato_id'], data_fim__isnull=True).exists()],
           motivo='Vínculo de administradora alterado')

def registrar_encerramento_direto(contato):
    anterior = atual(cliente_id=contato.cliente_id)
    if not anterior or not anterior.itens.filter(contato=contato).exists():
        return
    nova = anterior.configuracao.revisoes.create(numero=anterior.numero + 1, modo=anterior.modo,
                                                vinculo=anterior.vinculo, motivo='Contato do condomínio encerrado')
    ItemDestinatario.objects.bulk_create([ItemDestinatario(revisao=nova, **i) for i in itens_da_revisao(anterior) if i['contato_id'] != contato.pk])
