from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def validate_half_hour_duration(value):
    if value % 30:
        raise ValidationError("A duração deve ser múltipla de 30 minutos.")


class Acampamento(models.Model):
    nome = models.CharField(max_length=150)
    data_inicio = models.DateField()
    data_fim = models.DateField()

    class Meta:
        ordering = ("data_inicio", "nome")

    def __str__(self):
        return self.nome

    def dias_do_evento(self):
        dias = []
        data_atual = self.data_inicio
        while data_atual <= self.data_fim:
            dias.append(data_atual)
            data_atual += timedelta(days=1)
        return dias


class ListaQuadro(models.Model):
    acampamento = models.ForeignKey(
        Acampamento, related_name="listas", on_delete=models.CASCADE
    )
    nome = models.CharField(max_length=100)
    data = models.DateField(blank=True, null=True)
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("ordem", "id")
        verbose_name = "lista do quadro"
        verbose_name_plural = "listas do quadro"

    def __str__(self):
        return f"{self.acampamento}: {self.nome}"


class EtiquetaQuadro(models.Model):
    acampamento = models.ForeignKey(
        Acampamento, related_name="etiquetas", on_delete=models.CASCADE
    )
    nome = models.CharField(max_length=40)
    cor = models.CharField(max_length=7, default="#198754")

    class Meta:
        ordering = ("nome",)
        unique_together = (("acampamento", "nome"),)
        verbose_name = "etiqueta"
        verbose_name_plural = "etiquetas"

    def __str__(self):
        return self.nome


class Cartao(models.Model):
    lista = models.ForeignKey(
        ListaQuadro, related_name="cartoes", on_delete=models.CASCADE
    )
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    data_prazo = models.DateTimeField(blank=True, null=True)
    posicao = models.PositiveSmallIntegerField(default=0)
    publico_alvo = models.CharField(max_length=30, blank=True)
    passo_a_passo = models.TextField(blank=True)
    detalhes_adicionais = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)
    etiquetas = models.ManyToManyField(EtiquetaQuadro, blank=True, related_name="cartoes")
    membros = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="cartoes_acampamento"
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        related_name="cartoes_criados",
        on_delete=models.SET_NULL,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("posicao", "id")
        verbose_name = "cartão"
        verbose_name_plural = "cartões"

    def __str__(self):
        return self.titulo


class ChecklistCartao(models.Model):
    cartao = models.ForeignKey(
        Cartao, related_name="checklist", on_delete=models.CASCADE
    )
    descricao = models.CharField(max_length=200)
    concluido = models.BooleanField(default=False)
    posicao = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("posicao", "id")
        verbose_name = "item do checklist"
        verbose_name_plural = "itens do checklist"

    def __str__(self):
        return self.descricao


class AnexoCartao(models.Model):
    cartao = models.ForeignKey(
        Cartao, related_name="anexos", on_delete=models.CASCADE
    )
    arquivo = models.FileField(upload_to="anexos/%Y/%m/")
    nome = models.CharField(max_length=255)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("enviado_em", "id")
        verbose_name = "anexo"
        verbose_name_plural = "anexos"

    def __str__(self):
        return self.nome


class ComentarioCartao(models.Model):
    cartao = models.ForeignKey(
        Cartao, related_name="comentarios", on_delete=models.CASCADE
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    texto = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("criado_em", "id")
        verbose_name = "comentário"
        verbose_name_plural = "comentários"

    def __str__(self):
        return f"{self.autor}: {self.texto[:40]}"


class EventoCartao(models.Model):
    cartao = models.ForeignKey(
        Cartao, related_name="eventos", on_delete=models.CASCADE
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    texto = models.CharField(max_length=255)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("criado_em", "id")
        verbose_name = "atividade do cartão"
        verbose_name_plural = "atividades do cartão"

    def __str__(self):
        return self.texto


from .legacy_models import (  # noqa: E402,F401
    Atividade,
    CampoAtividade,
    CampoProgramacao,
    ChecklistProgramacao,
    ItemChecklist,
    ProgramacaoDiaria,
)
