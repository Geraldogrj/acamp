from datetime import datetime, timedelta

from django.utils import timezone

from .models import (
    Acampamento,
    AnexoCartao,
    Cartao,
    ChecklistCartao,
    EtiquetaQuadro,
    EventoCartao,
    ListaQuadro,
)


NOMES_DIAS = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)


def sincronizar_listas_acampamento(acampamento):
    if not acampamento.listas.filter(data__isnull=True).exists():
        acampamento.listas.create(nome="A fazer", ordem=0)

    ordem = 1
    for data in acampamento.dias_do_evento():
        lista, criada = acampamento.listas.get_or_create(
            data=data,
            defaults={
                "nome": nome_lista_dia(data),
                "ordem": ordem,
            },
        )
        if not criada and lista.ordem != ordem:
            lista.ordem = ordem
            lista.save(update_fields=("ordem",))
        ordem += 1


def registrar_evento(cartao, texto, usuario=None):
    return EventoCartao.objects.create(
        cartao=cartao,
        texto=texto,
        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
    )


def nome_lista_dia(data):
    return f"{NOMES_DIAS[data.weekday()].capitalize()} · {data:%d/%m}"


def copiar_cartao(cartao_origem, lista_destino, usuario=None, deslocamento_dias=0, etiquetas=None):
    prazo = cartao_origem.data_prazo
    if prazo and deslocamento_dias:
        prazo += timedelta(days=deslocamento_dias)
    cartao = Cartao.objects.create(
        lista=lista_destino,
        titulo=cartao_origem.titulo,
        descricao=cartao_origem.descricao,
        data_prazo=prazo,
        posicao=lista_destino.cartoes.count(),
        publico_alvo=cartao_origem.publico_alvo,
        passo_a_passo=cartao_origem.passo_a_passo,
        detalhes_adicionais=cartao_origem.detalhes_adicionais,
        observacoes=cartao_origem.observacoes,
        criado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
    )
    cartao.etiquetas.set(
        etiquetas
        if etiquetas is not None
        else cartao_origem.etiquetas.all()
    )
    cartao.membros.set(cartao_origem.membros.all())

    ChecklistCartao.objects.bulk_create(
        [
            ChecklistCartao(
                cartao=cartao,
                descricao=item.descricao,
                concluido=False,
                posicao=item.posicao,
            )
            for item in cartao_origem.checklist.all()
        ]
    )
    for anexo in cartao_origem.anexos.all():
        AnexoCartao.objects.create(
            cartao=cartao,
            arquivo=anexo.arquivo.name,
            nome=anexo.nome,
            enviado_por=anexo.enviado_por,
        )
    registrar_evento(cartao, f"Cartão copiado de “{cartao_origem.titulo}”.", usuario)
    return cartao


def copiar_lista(origem, destino, usuario=None):
    deslocamento = 0
    if origem.data and destino.data:
        deslocamento = (destino.data - origem.data).days
    return [
        copiar_cartao(
            cartao,
            destino,
            usuario=usuario,
            deslocamento_dias=deslocamento,
        )
        for cartao in origem.cartoes.prefetch_related(
            "etiquetas", "membros", "checklist", "anexos"
        )
    ]


def copiar_acampamento(origem, nome, nova_data_inicio, usuario=None):
    duracao = (origem.data_fim - origem.data_inicio).days
    deslocamento = (nova_data_inicio - origem.data_inicio).days
    destino = Acampamento.objects.create(
        nome=nome,
        data_inicio=nova_data_inicio,
        data_fim=nova_data_inicio + timedelta(days=duracao),
    )
    listas_map = {}
    for lista in origem.listas.all():
        nova_data = lista.data + timedelta(days=deslocamento) if lista.data else None
        nome = lista.nome
        if lista.data and lista.nome == nome_lista_dia(lista.data):
            nome = nome_lista_dia(nova_data)
        nova_lista = ListaQuadro.objects.create(
            acampamento=destino,
            nome=nome,
            data=nova_data,
            ordem=lista.ordem,
        )
        listas_map[lista.pk] = nova_lista

    etiquetas_map = {}
    for etiqueta in origem.etiquetas.all():
        nova_etiqueta = EtiquetaQuadro.objects.create(
            acampamento=destino,
            nome=etiqueta.nome,
            cor=etiqueta.cor,
        )
        etiquetas_map[etiqueta.pk] = nova_etiqueta

    for lista in origem.listas.prefetch_related(
        "cartoes__etiquetas",
        "cartoes__membros",
        "cartoes__checklist",
        "cartoes__anexos",
    ):
        for cartao in lista.cartoes.all():
            novas_etiquetas = [
                etiquetas_map[etiqueta.pk]
                for etiqueta in cartao.etiquetas.all()
                if etiqueta.pk in etiquetas_map
            ]
            copiar_cartao(
                cartao,
                listas_map[lista.pk],
                usuario=usuario,
                deslocamento_dias=deslocamento,
                etiquetas=novas_etiquetas,
            )
    return destino


def prazo_legado(data, horario):
    prazo = datetime.combine(data, horario)
    return timezone.make_aware(prazo, timezone.get_current_timezone())
