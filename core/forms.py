from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory

from .models import (
    Acampamento,
    Cartao,
    ChecklistCartao,
    ComentarioCartao,
    EtiquetaQuadro,
    ListaQuadro,
)


class AcampamentoForm(forms.ModelForm):
    class Meta:
        model = Acampamento
        fields = ("nome", "data_inicio", "data_fim")
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "data_inicio": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"class": "form-control", "type": "date"},
            ),
            "data_fim": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"class": "form-control", "type": "date"},
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        inicio = cleaned_data.get("data_inicio")
        fim = cleaned_data.get("data_fim")
        if inicio and fim and fim < inicio:
            self.add_error("data_fim", "A data de término deve ser igual ou posterior ao início.")
        return cleaned_data


class CopiarAcampamentoForm(forms.Form):
    nome = forms.CharField(
        max_length=150,
        label="Nome do novo acampamento",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    data_inicio = forms.DateField(
        label="Nova data de início",
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={"class": "form-control", "type": "date"},
        ),
    )


class ListaQuadroForm(forms.ModelForm):
    class Meta:
        model = ListaQuadro
        fields = ("nome",)
        widgets = {"nome": forms.TextInput(attrs={"class": "form-control"})}


class CriarCartaoRapidoForm(forms.Form):
    titulo = forms.CharField(
        max_length=200,
        label="",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Título do cartão...",
                "aria-label": "Título do cartão",
            }
        ),
    )


class CartaoForm(forms.ModelForm):
    class Meta:
        model = Cartao
        fields = (
            "titulo",
            "descricao",
            "data_prazo",
            "publico_alvo",
            "passo_a_passo",
            "detalhes_adicionais",
            "observacoes",
            "etiquetas",
            "membros",
        )
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "descricao": forms.Textarea(
                attrs={"class": "form-control", "rows": 4, "placeholder": "Adicione uma descrição mais detalhada..."}
            ),
            "data_prazo": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"class": "form-control", "type": "datetime-local"},
            ),
            "publico_alvo": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Opcional"}
            ),
            "passo_a_passo": forms.Textarea(
                attrs={"class": "form-control", "rows": 4}
            ),
            "detalhes_adicionais": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "observacoes": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "etiquetas": forms.CheckboxSelectMultiple(),
            "membros": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, acampamento, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["etiquetas"].queryset = acampamento.etiquetas.all()
        self.fields["membros"].queryset = get_user_model().objects.filter(
            is_active=True
        ).order_by("username")


CartaoChecklistFormSet = inlineformset_factory(
    Cartao,
    ChecklistCartao,
    fields=("descricao", "concluido"),
    extra=1,
    can_delete=True,
    widgets={
        "descricao": forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Item do checklist"}
        ),
        "concluido": forms.CheckboxInput(attrs={"class": "form-check-input"}),
    },
)


class ComentarioForm(forms.ModelForm):
    class Meta:
        model = ComentarioCartao
        fields = ("texto",)
        widgets = {
            "texto": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Escreva um comentário...",
                }
            )
        }


class EtiquetaForm(forms.ModelForm):
    class Meta:
        model = EtiquetaQuadro
        fields = ("nome", "cor")
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "cor": forms.TextInput(attrs={"class": "form-control form-control-color", "type": "color"}),
        }


class CopiarDiaForm(forms.Form):
    destino = forms.ModelChoiceField(
        queryset=ListaQuadro.objects.none(),
        label="Copiar para",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, acampamento, origem, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destino"].queryset = (
            acampamento.listas.filter(data__isnull=False)
            .exclude(pk=origem.pk)
            .order_by("data")
        )
