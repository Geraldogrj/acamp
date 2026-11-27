from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    AcampamentoForm,
    CartaoChecklistFormSet,
    CartaoForm,
    ComentarioForm,
    CopiarAcampamentoForm,
    CopiarDiaForm,
    CriarCartaoRapidoForm,
    EtiquetaForm,
    ListaQuadroForm,
)
from .models import (
    Acampamento,
    AnexoCartao,
    Cartao,
    ChecklistCartao,
    ComentarioCartao,
    EtiquetaQuadro,
    EventoCartao,
    ListaQuadro,
)
from .services import (
    copiar_acampamento,
    copiar_cartao,
    copiar_lista,
    registrar_evento,
    sincronizar_listas_acampamento,
)


def acampamento_list(request):
    acampamentos = Acampamento.objects.all()
    return render(request, "core/acampamento_list.html", {"acampamentos": acampamentos})


def acampamento_create(request):
    form = AcampamentoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            acampamento = form.save()
            sincronizar_listas_acampamento(acampamento)
        messages.success(request, "Acampamento criado. O quadro já está pronto.")
        return redirect("core:acampamento_detail", pk=acampamento.pk)
    return render(
        request,
        "core/acampamento_form.html",
        {"form": form, "titulo": "Novo acampamento"},
    )


def acampamento_update(request, pk):
    acampamento = get_object_or_404(Acampamento, pk=pk)
    form = AcampamentoForm(request.POST or None, instance=acampamento)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            sincronizar_listas_acampamento(acampamento)
        messages.success(request, "Acampamento atualizado.")
        return redirect("core:acampamento_detail", pk=acampamento.pk)
    return render(
        request,
        "core/acampamento_form.html",
        {"form": form, "titulo": "Editar acampamento", "acampamento": acampamento},
    )


def acampamento_delete(request, pk):
    acampamento = get_object_or_404(Acampamento, pk=pk)
    if request.method == "POST":
        arquivos = list(
            AnexoCartao.objects.filter(cartao__lista__acampamento=acampamento)
            .values_list("arquivo", flat=True)
            .distinct()
        )
        acampamento.delete()
        for nome_arquivo in arquivos:
            if nome_arquivo and not AnexoCartao.objects.filter(arquivo=nome_arquivo).exists():
                default_storage.delete(nome_arquivo)
        messages.success(request, "Acampamento excluído.")
        return redirect("core:acampamento_list")
    return render(
        request,
        "core/confirm_delete.html",
        {
            "objeto": acampamento,
            "cancel_href": reverse("core:acampamento_detail", args=[acampamento.pk]),
        },
    )


def acampamento_detail(request, pk):
    acampamento = get_object_or_404(Acampamento, pk=pk)
    listas = (
        acampamento.listas.all()
        .prefetch_related(
            "cartoes__etiquetas",
            "cartoes__membros",
            "cartoes__checklist",
            "cartoes__anexos",
        )
    )
    hoje = timezone.localdate()
    for lista in listas:
        for cartao in lista.cartoes.all():
            itens = list(cartao.checklist.all())
            cartao.checklist_total = len(itens)
            cartao.checklist_concluido = sum(item.concluido for item in itens)
            cartao.anexos_total = len(cartao.anexos.all())
            cartao.membros_lista = list(cartao.membros.all())
            cartao.prazo_atrasado = bool(
                cartao.data_prazo
                and timezone.localtime(cartao.data_prazo).date() < hoje
            )
    return render(
        request,
        "core/acampamento_detail.html",
        {
            "acampamento": acampamento,
            "listas": listas,
            "lista_form": ListaQuadroForm(),
            "cartao_form": CriarCartaoRapidoForm(),
            "etiquetas": acampamento.etiquetas.all(),
            "today": hoje,
        },
    )


@require_POST
def lista_create(request, acampamento_pk):
    acampamento = get_object_or_404(Acampamento, pk=acampamento_pk)
    form = ListaQuadroForm(request.POST)
    if form.is_valid():
        lista = form.save(commit=False)
        lista.acampamento = acampamento
        lista.ordem = (acampamento.listas.order_by("-ordem").values_list("ordem", flat=True).first() or 0) + 1
        lista.save()
        messages.success(request, "Lista adicionada ao quadro.")
    else:
        messages.error(request, "Informe um nome para a lista.")
    return redirect("core:acampamento_detail", pk=acampamento.pk)


@require_POST
def lista_update(request, pk):
    lista = get_object_or_404(ListaQuadro.objects.select_related("acampamento"), pk=pk)
    form = ListaQuadroForm(request.POST, instance=lista)
    if form.is_valid():
        form.save()
        messages.success(request, "Nome da lista atualizado.")
    else:
        messages.error(request, "O nome da lista não pode ficar vazio.")
    return redirect("core:acampamento_detail", pk=lista.acampamento_id)


@require_POST
def lista_delete(request, pk):
    lista = get_object_or_404(ListaQuadro.objects.select_related("acampamento"), pk=pk)
    if lista.data:
        messages.error(request, "As listas de dias do acampamento não podem ser excluídas.")
    elif lista.cartoes.exists():
        messages.error(request, "Mova ou exclua os cartões antes de excluir esta lista.")
    else:
        acampamento_pk = lista.acampamento_id
        lista.delete()
        messages.success(request, "Lista excluída.")
        return redirect("core:acampamento_detail", pk=acampamento_pk)
    return redirect("core:acampamento_detail", pk=lista.acampamento_id)


@require_POST
def cartao_create(request, lista_pk):
    lista = get_object_or_404(ListaQuadro.objects.select_related("acampamento"), pk=lista_pk)
    form = CriarCartaoRapidoForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Digite um título para o cartão.")
        return redirect("core:acampamento_detail", pk=lista.acampamento_id)
    with transaction.atomic():
        cartao = Cartao.objects.create(
            lista=lista,
            titulo=form.cleaned_data["titulo"],
            posicao=lista.cartoes.count(),
            criado_por=request.user if request.user.is_authenticated else None,
        )
        registrar_evento(
            cartao,
            f"Cartão adicionado à lista “{lista.nome}”.",
            request.user,
        )
    return redirect("core:cartao_detail", pk=cartao.pk)


def cartao_detail(request, pk):
    cartao = get_object_or_404(
        Cartao.objects.select_related("lista__acampamento", "criado_por").prefetch_related(
            "etiquetas",
            "membros",
            "checklist",
            "anexos",
        ),
        pk=pk,
    )
    acampamento = cartao.lista.acampamento
    form = CartaoForm(
        request.POST or None,
        instance=cartao,
        acampamento=acampamento,
    )
    checklist_formset = CartaoChecklistFormSet(
        request.POST or None,
        instance=cartao,
        prefix="checklist",
    )
    if request.method == "POST" and form.is_valid() and checklist_formset.is_valid():
        with transaction.atomic():
            card = form.save()
            checklist_formset.instance = card
            checklist_formset.save()
            registrar_evento(card, "Cartão atualizado.", request.user)
        messages.success(request, "Cartão atualizado.")
        return redirect("core:cartao_detail", pk=cartao.pk)

    feed = [
        (evento.criado_em, "evento", evento)
        for evento in cartao.eventos.select_related("usuario")
    ]
    feed.extend(
        (comentario.criado_em, "comentario", comentario)
        for comentario in cartao.comentarios.select_related("autor")
    )
    feed.sort(key=lambda item: item[0])

    return render(
        request,
        "core/cartao_detail.html",
        {
            "cartao": cartao,
            "form": form,
            "checklist_formset": checklist_formset,
            "comentario_form": ComentarioForm(),
            "feed": feed,
            "today": timezone.localdate(),
            "etiquetas_disponiveis": acampamento.etiquetas.all(),
        },
    )


@require_POST
def cartao_move(request, pk):
    cartao = get_object_or_404(
        Cartao.objects.select_related("lista__acampamento"), pk=pk
    )
    try:
        lista_destino = ListaQuadro.objects.get(
            pk=int(request.POST.get("lista_id", "")),
            acampamento=cartao.lista.acampamento,
        )
        nova_posicao = max(0, int(request.POST.get("posicao", "0")))
    except (ValueError, ListaQuadro.DoesNotExist):
        return JsonResponse({"erro": "Destino do cartão inválido."}, status=400)

    lista_origem = cartao.lista
    mesma_lista = lista_origem.pk == lista_destino.pk
    with transaction.atomic():
        if mesma_lista:
            cartoes = list(lista_origem.cartoes.exclude(pk=cartao.pk))
            posicao = min(nova_posicao, len(cartoes))
            cartoes.insert(posicao, cartao)
            registrar_evento(cartao, f"Cartão reordenado em “{lista_destino.nome}”.", request.user)
        else:
            cartoes_origem = list(lista_origem.cartoes.exclude(pk=cartao.pk))
            cartoes_destino = list(lista_destino.cartoes.exclude(pk=cartao.pk))
            posicao = min(nova_posicao, len(cartoes_destino))
            cartao.lista = lista_destino
            cartoes_destino.insert(posicao, cartao)
            registrar_evento(cartao, f"Movido para “{lista_destino.nome}”.", request.user)
            for indice, item in enumerate(cartoes_origem):
                item.posicao = indice
            Cartao.objects.bulk_update(cartoes_origem, ("posicao",))
            cartoes = cartoes_destino
        for indice, item in enumerate(cartoes):
            item.posicao = indice
        Cartao.objects.bulk_update(cartoes, ("lista", "posicao"))
    return JsonResponse({"lista": lista_destino.pk, "posicao": posicao})


@require_POST
def cartao_copy(request, pk):
    cartao = get_object_or_404(
        Cartao.objects.select_related("lista").prefetch_related(
            "etiquetas", "membros", "checklist", "anexos"
        ),
        pk=pk,
    )
    with transaction.atomic():
        copia = copiar_cartao(cartao, cartao.lista, usuario=request.user)
    messages.success(request, "Cartão copiado; itens do checklist foram reiniciados.")
    return redirect("core:cartao_detail", pk=copia.pk)


@require_POST
def cartao_delete(request, pk):
    cartao = get_object_or_404(
        Cartao.objects.select_related("lista").prefetch_related("anexos"), pk=pk
    )
    acampamento_pk = cartao.lista.acampamento_id
    arquivos = [anexo.arquivo.name for anexo in cartao.anexos.all()]
    cartao.delete()
    for nome_arquivo in arquivos:
        if nome_arquivo and not AnexoCartao.objects.filter(arquivo=nome_arquivo).exists():
            default_storage.delete(nome_arquivo)
    messages.success(request, "Cartão excluído.")
    return redirect("core:acampamento_detail", pk=acampamento_pk)


@require_POST
def checklist_toggle(request, pk):
    item = get_object_or_404(
        ChecklistCartao.objects.select_related("cartao"), pk=pk
    )
    concluido = request.POST.get("concluido")
    if concluido not in {"true", "false"}:
        return JsonResponse({"erro": "Estado do checklist inválido."}, status=400)
    item.concluido = concluido == "true"
    item.save(update_fields=("concluido",))
    registrar_evento(
        item.cartao,
        f"Checklist “{item.descricao}” "
        f"{'marcado como concluído' if item.concluido else 'reaberto'}.",
        request.user,
    )
    return JsonResponse({"concluido": item.concluido})


@require_POST
def anexo_create(request, cartao_pk):
    cartao = get_object_or_404(Cartao, pk=cartao_pk)
    arquivos = request.FILES.getlist("arquivos")
    if not arquivos:
        messages.error(request, "Selecione ao menos um arquivo.")
    for arquivo in arquivos:
        if arquivo.size > 50 * 1024 * 1024:
            messages.error(request, f"{arquivo.name}: o arquivo excede 50 MB.")
            continue
        AnexoCartao.objects.create(
            cartao=cartao,
            arquivo=arquivo,
            nome=arquivo.name,
            enviado_por=request.user if request.user.is_authenticated else None,
        )
        registrar_evento(cartao, f"Anexo “{arquivo.name}” adicionado.", request.user)
    return redirect("core:cartao_detail", pk=cartao.pk)


@require_POST
def anexo_delete(request, pk):
    anexo = get_object_or_404(AnexoCartao.objects.select_related("cartao__lista"), pk=pk)
    cartao_pk = anexo.cartao_id
    nome_arquivo = anexo.arquivo.name
    anexo.delete()
    if nome_arquivo and not AnexoCartao.objects.filter(arquivo=nome_arquivo).exists():
        default_storage.delete(nome_arquivo)
    messages.success(request, "Anexo removido.")
    return redirect("core:cartao_detail", pk=cartao_pk)


@login_required
@require_POST
def comentario_create(request, cartao_pk):
    cartao = get_object_or_404(Cartao, pk=cartao_pk)
    form = ComentarioForm(request.POST)
    if form.is_valid():
        comentario = form.save(commit=False)
        comentario.cartao = cartao
        comentario.autor = request.user
        comentario.save()
    else:
        messages.error(request, "Escreva um comentário antes de enviar.")
    return redirect("core:cartao_detail", pk=cartao.pk)


@require_POST
def etiqueta_create(request, acampamento_pk):
    acampamento = get_object_or_404(Acampamento, pk=acampamento_pk)
    form = EtiquetaForm(request.POST)
    if form.is_valid():
        etiqueta = form.save(commit=False)
        etiqueta.acampamento = acampamento
        etiqueta.save()
        messages.success(request, "Etiqueta criada.")
        return redirect("core:acampamento_detail", pk=acampamento.pk)
    messages.error(request, "Preencha corretamente os campos da etiqueta.")
    return redirect("core:acampamento_detail", pk=acampamento.pk)


def copiar_dia(request, lista_pk):
    origem = get_object_or_404(ListaQuadro.objects.select_related("acampamento"), pk=lista_pk)
    form = CopiarDiaForm(
        request.POST or None,
        acampamento=origem.acampamento,
        origem=origem,
    )
    if request.method == "POST" and form.is_valid():
        destino = form.cleaned_data["destino"]
        with transaction.atomic():
            copiar_lista(origem, destino, usuario=request.user)
        messages.success(
            request,
            f"Cartões copiados para “{destino.nome}”; checklists reiniciados.",
        )
        return redirect("core:acampamento_detail", pk=origem.acampamento_id)
    return render(
        request,
        "core/copiar_dia.html",
        {"origem": origem, "form": form},
    )


def copiar_acampamento_view(request, pk):
    origem = get_object_or_404(Acampamento, pk=pk)
    form = CopiarAcampamentoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            copia = copiar_acampamento(
                origem,
                form.cleaned_data["nome"],
                form.cleaned_data["data_inicio"],
                usuario=request.user,
            )
        messages.success(
            request,
            "Acampamento copiado com checklists reiniciados e prazos ajustados.",
        )
        return redirect("core:acampamento_detail", pk=copia.pk)
    return render(
        request,
        "core/copiar_acampamento.html",
        {"origem": origem, "form": form},
    )


def etiqueta_manage(request, acampamento_pk):
    acampamento = get_object_or_404(Acampamento, pk=acampamento_pk)
    return render(
        request,
        "core/etiquetas.html",
        {
            "acampamento": acampamento,
            "form": EtiquetaForm(),
            "etiquetas": acampamento.etiquetas.all(),
        },
    )
