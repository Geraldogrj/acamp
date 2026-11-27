from django.contrib import admin

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


class ChecklistCartaoInline(admin.TabularInline):
    model = ChecklistCartao
    extra = 1


class AnexoCartaoInline(admin.TabularInline):
    model = AnexoCartao
    extra = 0


@admin.register(Acampamento)
class AcampamentoAdmin(admin.ModelAdmin):
    list_display = ("nome", "data_inicio", "data_fim")
    list_filter = ("data_inicio",)


@admin.register(ListaQuadro)
class ListaQuadroAdmin(admin.ModelAdmin):
    list_display = ("nome", "acampamento", "data", "ordem")
    list_filter = ("acampamento", "data")


@admin.register(Cartao)
class CartaoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "lista", "data_prazo", "criado_por", "atualizado_em")
    list_filter = ("lista__acampamento", "data_prazo")
    search_fields = ("titulo", "descricao")
    inlines = (ChecklistCartaoInline, AnexoCartaoInline)


@admin.register(EtiquetaQuadro)
class EtiquetaQuadroAdmin(admin.ModelAdmin):
    list_display = ("nome", "acampamento", "cor")


admin.site.register(AnexoCartao)
admin.site.register(ChecklistCartao)
admin.site.register(ComentarioCartao)
admin.site.register(EventoCartao)
