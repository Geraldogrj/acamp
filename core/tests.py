from datetime import date, datetime
from tempfile import TemporaryDirectory

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import AcampamentoForm
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
from .services import sincronizar_listas_acampamento


class BoardFixtureMixin:
    def setUp(self):
        self.acampamento = Acampamento.objects.create(
            nome="Retiro", data_inicio=date(2026, 1, 2), data_fim=date(2026, 1, 3)
        )
        sincronizar_listas_acampamento(self.acampamento)
        self.backlog = self.acampamento.listas.get(data__isnull=True)
        self.dia_1 = self.acampamento.listas.get(data=date(2026, 1, 2))
        self.dia_2 = self.acampamento.listas.get(data=date(2026, 1, 3))


class AcampamentoTests(BoardFixtureMixin, TestCase):
    def test_form_rejeita_fim_anterior_ao_inicio(self):
        form = AcampamentoForm(
            data={
                "nome": "Retiro",
                "data_inicio": "2026-01-05",
                "data_fim": "2026-01-04",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("data_fim", form.errors)

    def test_criar_acampamento_prepara_listas_por_dia(self):
        response = self.client.post(
            reverse("core:acampamento_create"),
            {
                "nome": "Novo retiro",
                "data_inicio": "2026-06-10",
                "data_fim": "2026-06-11",
            },
        )
        novo = Acampamento.objects.get(nome="Novo retiro")
        self.assertRedirects(
            response, reverse("core:acampamento_detail", args=[novo.pk])
        )
        self.assertEqual(novo.listas.count(), 3)
        self.assertTrue(novo.listas.filter(data__isnull=True).exists())
        self.assertEqual(
            list(novo.listas.exclude(data__isnull=True).values_list("data", flat=True)),
            [date(2026, 6, 10), date(2026, 6, 11)],
        )

    def test_quadro_permite_criar_e_renomear_listas_e_cartoes(self):
        response = self.client.post(
            reverse("core:lista_create", args=[self.acampamento.pk]),
            {"nome": "Antes do evento"},
        )
        self.assertRedirects(
            response, reverse("core:acampamento_detail", args=[self.acampamento.pk])
        )
        lista = self.acampamento.listas.get(nome="Antes do evento")

        response = self.client.post(
            reverse("core:lista_update", args=[lista.pk]), {"nome": "Preparação"}
        )
        lista.refresh_from_db()
        self.assertRedirects(
            response, reverse("core:acampamento_detail", args=[self.acampamento.pk])
        )
        self.assertEqual(lista.nome, "Preparação")

        response = self.client.post(
            reverse("core:cartao_create", args=[lista.pk]), {"titulo": "Separar materiais"}
        )
        cartao = Cartao.objects.get(titulo="Separar materiais")
        self.assertRedirects(response, reverse("core:cartao_detail", args=[cartao.pk]))
        self.assertEqual(cartao.lista, lista)

    def test_quadro_exibe_listas_e_opcoes_de_impressao(self):
        cartao = Cartao.objects.create(
            lista=self.dia_1,
            titulo="Cartão de teste",
            descricao="Descrição para a equipe",
            passo_a_passo="Preparar o espaço",
        )
        ChecklistCartao.objects.create(cartao=cartao, descricao="Levar materiais")
        response = self.client.get(
            reverse("core:acampamento_detail", args=[self.acampamento.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.acampamento.nome)
        self.assertContains(response, self.dia_1.nome)
        self.assertContains(response, "Imprimir")
        self.assertContains(response, "draggable=\"true\"", html=False)
        self.assertContains(response, "Descrição para a equipe")
        self.assertContains(response, "Preparar o espaço")
        self.assertContains(response, "Levar materiais")


class CartaoTests(BoardFixtureMixin, TestCase):
    def criar_cartao(self, lista=None, titulo="Louvor"):
        return Cartao.objects.create(
            lista=lista or self.dia_1,
            titulo=titulo,
            posicao=(lista or self.dia_1).cartoes.count(),
        )

    def test_edita_cartao_detalhes_checklist_etiquetas_e_membros(self):
        cartao = self.criar_cartao()
        etiqueta = EtiquetaQuadro.objects.create(
            acampamento=self.acampamento, nome="Culto", cor="#336699"
        )
        membro = get_user_model().objects.create_user(
            username="lider", password="senha-forte"
        )

        response = self.client.post(
            reverse("core:cartao_detail", args=[cartao.pk]),
            {
                "titulo": "Culto matinal",
                "descricao": "Celebração da manhã",
                "data_prazo": "2026-01-02T09:30",
                "publico_alvo": "Geral",
                "passo_a_passo": "Preparar o salão",
                "detalhes_adicionais": "Tema: Esperança",
                "observacoes": "Levar microfone",
                "etiquetas": [str(etiqueta.pk)],
                "membros": [str(membro.pk)],
                "checklist-TOTAL_FORMS": "1",
                "checklist-INITIAL_FORMS": "0",
                "checklist-MIN_NUM_FORMS": "0",
                "checklist-MAX_NUM_FORMS": "1000",
                "checklist-0-descricao": "Testar o som",
            },
        )
        self.assertRedirects(response, reverse("core:cartao_detail", args=[cartao.pk]))
        cartao.refresh_from_db()
        self.assertEqual(cartao.titulo, "Culto matinal")
        self.assertEqual(cartao.data_prazo.date(), date(2026, 1, 2))
        self.assertEqual(cartao.detalhes_adicionais, "Tema: Esperança")
        self.assertEqual(list(cartao.etiquetas.all()), [etiqueta])
        self.assertEqual(list(cartao.membros.all()), [membro])
        self.assertEqual(cartao.checklist.get().descricao, "Testar o som")

    def test_checklist_alternar_pelo_endpoint_e_rejeitar_estado_invalido(self):
        cartao = self.criar_cartao()
        item = ChecklistCartao.objects.create(cartao=cartao, descricao="Separar som")
        url = reverse("core:checklist_toggle", args=[item.pk])

        response = self.client.post(url, {"concluido": "true"})
        item.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(item.concluido)
        self.assertEqual(EventoCartao.objects.count(), 1)

        response = self.client.post(url, {"concluido": "talvez"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(EventoCartao.objects.count(), 1)

    def test_mover_reordena_cartao_e_impede_mudanca_para_outro_acampamento(self):
        primeiro = self.criar_cartao(self.dia_1, "Primeiro")
        segundo = self.criar_cartao(self.dia_1, "Segundo")
        response = self.client.post(
            reverse("core:cartao_move", args=[segundo.pk]),
            {"lista_id": self.dia_1.pk, "posicao": 0},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(self.dia_1.cartoes.values_list("titulo", flat=True)),
            ["Segundo", "Primeiro"],
        )

        outro = Acampamento.objects.create(
            nome="Outro", data_inicio=date(2026, 2, 1), data_fim=date(2026, 2, 1)
        )
        sincronizar_listas_acampamento(outro)
        lista_alheia = outro.listas.get(data=date(2026, 2, 1))
        response = self.client.post(
            reverse("core:cartao_move", args=[primeiro.pk]),
            {"lista_id": lista_alheia.pk, "posicao": 0},
        )
        self.assertEqual(response.status_code, 400)

    def test_copiar_cartao_reinicia_checklist(self):
        cartao = self.criar_cartao()
        item = ChecklistCartao.objects.create(
            cartao=cartao, descricao="Preparar sala", concluido=True
        )
        response = self.client.post(reverse("core:cartao_copy", args=[cartao.pk]))
        copia = Cartao.objects.exclude(pk=cartao.pk).get()

        self.assertRedirects(response, reverse("core:cartao_detail", args=[copia.pk]))
        self.assertEqual(copia.titulo, cartao.titulo)
        self.assertEqual(copia.lista, cartao.lista)
        self.assertEqual(copia.checklist.get().descricao, item.descricao)
        self.assertFalse(copia.checklist.get().concluido)

    def test_copiar_dia_desloca_prazo_e_reinicia_checklist(self):
        cartao = self.criar_cartao(self.dia_1)
        cartao.data_prazo = timezone.make_aware(datetime(2026, 1, 2, 9, 0))
        cartao.save()
        ChecklistCartao.objects.create(
            cartao=cartao, descricao="Confirmar escala", concluido=True
        )

        response = self.client.post(
            reverse("core:lista_copy", args=[self.dia_1.pk]),
            {"destino": self.dia_2.pk},
        )
        copia = self.dia_2.cartoes.get()

        self.assertRedirects(
            response, reverse("core:acampamento_detail", args=[self.acampamento.pk])
        )
        self.assertEqual(timezone.localtime(copia.data_prazo).date(), self.dia_2.data)
        self.assertFalse(copia.checklist.get().concluido)

    def test_copiar_acampamento_preserva_customizacao_e_desloca_dias(self):
        etiqueta = EtiquetaQuadro.objects.create(
            acampamento=self.acampamento, nome="Equipe", cor="#336699"
        )
        membro = get_user_model().objects.create_user(
            username="membro", password="senha-forte"
        )
        cartao = self.criar_cartao(self.dia_1)
        cartao.data_prazo = timezone.make_aware(datetime(2026, 1, 2, 9, 0))
        cartao.save()
        cartao.etiquetas.add(etiqueta)
        cartao.membros.add(membro)
        ChecklistCartao.objects.create(
            cartao=cartao, descricao="Confirmar presença", concluido=True
        )
        ListaQuadro.objects.create(
            acampamento=self.acampamento, nome="Backlog personalizado", ordem=4
        )

        response = self.client.post(
            reverse("core:acampamento_copy", args=[self.acampamento.pk]),
            {"nome": "Retiro de fevereiro", "data_inicio": "2026-02-01"},
        )
        copia = Acampamento.objects.get(nome="Retiro de fevereiro")
        cartao_copiado = Cartao.objects.get(
            lista__acampamento=copia, titulo=cartao.titulo
        )
        lista_dia = cartao_copiado.lista

        self.assertRedirects(
            response, reverse("core:acampamento_detail", args=[copia.pk])
        )
        self.assertEqual(copia.data_fim, date(2026, 2, 2))
        self.assertEqual(lista_dia.data, date(2026, 2, 1))
        self.assertEqual(lista_dia.nome, "Domingo · 01/02")
        self.assertTrue(copia.listas.filter(nome="Backlog personalizado").exists())
        self.assertEqual(timezone.localtime(cartao_copiado.data_prazo).date(), date(2026, 2, 1))
        self.assertFalse(cartao_copiado.checklist.get().concluido)
        self.assertEqual(cartao_copiado.etiquetas.get().nome, etiqueta.nome)
        self.assertEqual(list(cartao_copiado.membros.all()), [membro])

    def test_comentario_requer_login_e_registra_autor(self):
        cartao = self.criar_cartao()
        url = reverse("core:comentario_create", args=[cartao.pk])

        response = self.client.post(url, {"texto": "Confirmado."})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ComentarioCartao.objects.count(), 0)

        membro = get_user_model().objects.create_user(
            username="lider", password="senha-forte"
        )
        self.client.force_login(membro)
        response = self.client.post(url, {"texto": "Confirmado."})
        self.assertRedirects(response, reverse("core:cartao_detail", args=[cartao.pk]))
        self.assertEqual(ComentarioCartao.objects.get().autor, membro)

    def test_admin_registra_modelos_do_quadro(self):
        for model in (
            Acampamento,
            ListaQuadro,
            Cartao,
            ChecklistCartao,
            AnexoCartao,
            EtiquetaQuadro,
            ComentarioCartao,
            EventoCartao,
        ):
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)


class AnexoTests(BoardFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.temp_media = TemporaryDirectory()
        self.addCleanup(self.temp_media.cleanup)
        media_override = override_settings(MEDIA_ROOT=self.temp_media.name)
        media_override.enable()
        self.addCleanup(media_override.disable)

    def test_anexos_compartilhados_na_copia_so_sao_excluidos_sem_referencias(self):
        cartao = Cartao.objects.create(lista=self.dia_1, titulo="Roteiro")
        arquivo = SimpleUploadedFile("roteiro.txt", b"texto do roteiro")
        response = self.client.post(
            reverse("core:anexo_create", args=[cartao.pk]),
            {"arquivos": [arquivo]},
        )
        self.assertRedirects(response, reverse("core:cartao_detail", args=[cartao.pk]))
        anexo = AnexoCartao.objects.get()
        caminho_arquivo = anexo.arquivo.path
        self.assertTrue(anexo.arquivo.storage.exists(anexo.arquivo.name))

        self.client.post(reverse("core:cartao_copy", args=[cartao.pk]))
        copia = Cartao.objects.exclude(pk=cartao.pk).get()
        self.assertEqual(copia.anexos.get().arquivo.name, anexo.arquivo.name)

        self.client.post(reverse("core:cartao_delete", args=[cartao.pk]))
        self.assertTrue(anexo.arquivo.storage.exists(anexo.arquivo.name))
        self.client.post(reverse("core:cartao_delete", args=[copia.pk]))
        self.assertFalse(anexo.arquivo.storage.exists(anexo.arquivo.name))
