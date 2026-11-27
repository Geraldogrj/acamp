from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .models import Acampamento, validate_half_hour_duration


class Atividade(models.Model):
    PUBLICOS = [
        ("Geral", "Geral"),
        ("Jovens", "Jovens"),
        ("Crianças", "Crianças"),
        ("Liderança", "Liderança"),
    ]

    nome = models.CharField(max_length=150)
    descricao = models.TextField(blank=True)
    horario_padrao = models.TimeField(blank=True, null=True)
    publico_alvo = models.CharField(max_length=30, choices=PUBLICOS, default="Geral")
    passo_a_passo = models.TextField(blank=True)

    class Meta:
        ordering = ("nome",)
        verbose_name_plural = "atividades"

    def __str__(self):
        return self.nome


class CampoAtividade(models.Model):
    TIPOS = [
        ("texto", "Texto curto"),
        ("texto_longo", "Texto longo"),
    ]

    atividade = models.ForeignKey(
        Atividade, related_name="campos", on_delete=models.CASCADE
    )
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPOS, default="texto")
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("ordem", "id")
        verbose_name = "campo personalizado"
        verbose_name_plural = "campos personalizados"


class ItemChecklist(models.Model):
    atividade = models.ForeignKey(
        Atividade, related_name="checklist", on_delete=models.CASCADE
    )
    descricao = models.CharField(max_length=200)

    class Meta:
        ordering = ("id",)
        verbose_name = "item do checklist"
        verbose_name_plural = "itens do checklist"

    def __str__(self):
        return self.descricao


class ProgramacaoDiaria(models.Model):
    acampamento = models.ForeignKey(
        Acampamento, related_name="programacoes", on_delete=models.CASCADE
    )
    atividade = models.ForeignKey(
        Atividade,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        verbose_name="modelo da Pool",
    )
    nome = models.CharField(max_length=150)
    descricao = models.TextField(blank=True)
    publico_alvo = models.CharField(
        max_length=30, choices=Atividade.PUBLICOS, default="Geral"
    )
    passo_a_passo = models.TextField(blank=True)
    data = models.DateField()
    horario = models.TimeField()
    duracao_minutos = models.PositiveSmallIntegerField(
        default=30,
        validators=[
            MinValueValidator(30),
            MaxValueValidator(1440),
            validate_half_hour_duration,
        ],
    )
    observacoes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("data", "horario")
        verbose_name = "programação diária"
        verbose_name_plural = "programações diárias"

    def __str__(self):
        return f"{self.data:%d/%m/%Y} {self.horario:%H:%M} - {self.nome}"


class ChecklistProgramacao(models.Model):
    programacao = models.ForeignKey(
        ProgramacaoDiaria, related_name="checklist", on_delete=models.CASCADE
    )
    descricao = models.CharField(max_length=200)
    concluido = models.BooleanField(default=False)

    class Meta:
        ordering = ("id",)
        verbose_name = "item do checklist da programação"
        verbose_name_plural = "itens do checklist da programação"

    def __str__(self):
        return self.descricao


class CampoProgramacao(models.Model):
    programacao = models.ForeignKey(
        ProgramacaoDiaria, related_name="campos_personalizados", on_delete=models.CASCADE
    )
    campo_modelo = models.ForeignKey(
        CampoAtividade,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=CampoAtividade.TIPOS)
    ordem = models.PositiveSmallIntegerField(default=0)
    valor = models.TextField(blank=True)

    class Meta:
        ordering = ("ordem", "id")
        verbose_name = "valor de campo da programação"
        verbose_name_plural = "valores de campos da programação"
