from django.db import migrations, models
import django.db.models.deletion


def copy_activity_templates_to_programs(apps, schema_editor):
    ProgramacaoDiaria = apps.get_model("core", "ProgramacaoDiaria")
    ItemChecklist = apps.get_model("core", "ItemChecklist")
    ChecklistProgramacao = apps.get_model("core", "ChecklistProgramacao")
    database = schema_editor.connection.alias

    for programacao in (
        ProgramacaoDiaria.objects.using(database)
        .select_related("atividade")
        .iterator()
    ):
        modelo = programacao.atividade
        if modelo is None:
            continue
        programacao.nome = modelo.nome
        programacao.descricao = modelo.descricao
        programacao.publico_alvo = modelo.publico_alvo
        programacao.passo_a_passo = modelo.passo_a_passo
        programacao.save(
            using=database,
            update_fields=("nome", "descricao", "publico_alvo", "passo_a_passo"),
        )
        ChecklistProgramacao.objects.using(database).bulk_create(
            [
                ChecklistProgramacao(
                    programacao_id=programacao.pk,
                    descricao=item.descricao,
                    concluido=item.concluido,
                )
                for item in ItemChecklist.objects.using(database).filter(
                    atividade_id=modelo.pk
                )
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="programacaodiaria",
            name="nome",
            field=models.CharField(default="", max_length=150),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="programacaodiaria",
            name="descricao",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="programacaodiaria",
            name="publico_alvo",
            field=models.CharField(
                choices=[
                    ("Geral", "Geral"),
                    ("Jovens", "Jovens"),
                    ("Crianças", "Crianças"),
                    ("Liderança", "Liderança"),
                ],
                default="Geral",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="programacaodiaria",
            name="passo_a_passo",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="programacaodiaria",
            name="atividade",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="core.atividade",
                verbose_name="modelo da Pool",
            ),
        ),
        migrations.CreateModel(
            name="ChecklistProgramacao",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("descricao", models.CharField(max_length=200)),
                ("concluido", models.BooleanField(default=False)),
                (
                    "programacao",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="checklist",
                        to="core.programacaodiaria",
                    ),
                ),
            ],
            options={
                "verbose_name": "item do checklist da programação",
                "verbose_name_plural": "itens do checklist da programação",
                "ordering": ("id",),
            },
        ),
        migrations.RunPython(
            copy_activity_templates_to_programs,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="itemchecklist",
            name="concluido",
        ),
    ]
