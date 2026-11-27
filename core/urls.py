from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.acampamento_list, name="acampamento_list"),
    path("acampamentos/novo/", views.acampamento_create, name="acampamento_create"),
    path("acampamentos/<int:pk>/", views.acampamento_detail, name="acampamento_detail"),
    path("acampamentos/<int:pk>/editar/", views.acampamento_update, name="acampamento_update"),
    path("acampamentos/<int:pk>/excluir/", views.acampamento_delete, name="acampamento_delete"),
    path("acampamentos/<int:pk>/copiar/", views.copiar_acampamento_view, name="acampamento_copy"),
    path("acampamentos/<int:acampamento_pk>/listas/nova/", views.lista_create, name="lista_create"),
    path("acampamentos/<int:acampamento_pk>/etiquetas/", views.etiqueta_manage, name="etiqueta_manage"),
    path("acampamentos/<int:acampamento_pk>/etiquetas/nova/", views.etiqueta_create, name="etiqueta_create"),
    path("listas/<int:pk>/renomear/", views.lista_update, name="lista_update"),
    path("listas/<int:pk>/excluir/", views.lista_delete, name="lista_delete"),
    path("listas/<int:lista_pk>/cartoes/novo/", views.cartao_create, name="cartao_create"),
    path("listas/<int:lista_pk>/copiar/", views.copiar_dia, name="lista_copy"),
    path("cartoes/<int:pk>/", views.cartao_detail, name="cartao_detail"),
    path("cartoes/<int:pk>/mover/", views.cartao_move, name="cartao_move"),
    path("cartoes/<int:pk>/copiar/", views.cartao_copy, name="cartao_copy"),
    path("cartoes/<int:pk>/excluir/", views.cartao_delete, name="cartao_delete"),
    path("cartoes/<int:cartao_pk>/anexos/", views.anexo_create, name="anexo_create"),
    path("anexos/<int:pk>/excluir/", views.anexo_delete, name="anexo_delete"),
    path("cartoes/<int:cartao_pk>/comentarios/", views.comentario_create, name="comentario_create"),
    path("checklist/<int:pk>/alternar/", views.checklist_toggle, name="checklist_toggle"),
    path(
        "contas/entrar/",
        auth_views.LoginView.as_view(template_name="core/login.html"),
        name="login",
    ),
    path(
        "contas/sair/",
        auth_views.LogoutView.as_view(next_page="core:acampamento_list"),
        name="logout",
    ),
]
