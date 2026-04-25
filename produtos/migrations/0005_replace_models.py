# Manually written migration.
# Drops the old Produto + Categoria tables and creates
# Catalogue, Product, and SessionResponse from scratch.

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        # Last migration in the existing chain
        ('produtos', '0004_produto_categoria_alter_produto_descricao'),
    ]

    operations = [
        # ── Remove old tables ────────────────────────────────────────────
        migrations.DeleteModel(name='Produto'),
        migrations.DeleteModel(name='Categoria'),

        # ── Catalogue ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Catalogue',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name',        models.CharField(max_length=100)),
                ('slug',        models.SlugField(unique=True)),
                ('description', models.TextField(blank=True)),
            ],
            options={'ordering': ['name']},
        ),

        # ── Product ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('catalogue',   models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='produtos.catalogue')),
                ('name',        models.CharField(max_length=100)),
                ('description', models.TextField(max_length=500)),
                ('price',       models.DecimalField(decimal_places=2, max_digits=10)),
                ('image_url',   models.URLField(blank=True, null=True)),
                ('featured',    models.BooleanField(default=False)),
            ],
            options={'ordering': ['-featured', 'name']},
        ),

        # ── SessionResponse ──────────────────────────────────────────────
        migrations.CreateModel(
            name='SessionResponse',
            fields=[
                ('id',                   models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id',           models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('interest_selected',    models.CharField(max_length=100)),
                ('products_selected',    models.JSONField()),
                ('robotic_output',       models.TextField()),
                ('humanized_output',     models.TextField()),
                ('preferred_overall',    models.CharField(max_length=1, choices=[('A', 'Recomendação A'), ('B', 'Recomendação B')])),
                ('preferred_trust',      models.CharField(max_length=1, choices=[('A', 'Recomendação A'), ('B', 'Recomendação B')])),
                ('preferred_purchase',   models.CharField(max_length=1, choices=[('A', 'Recomendação A'), ('B', 'Recomendação B')])),
                ('preferred_understood', models.CharField(max_length=1, choices=[('A', 'Recomendação A'), ('B', 'Recomendação B')])),
                ('uses_ai_shopping',     models.CharField(max_length=20, choices=[('sim', 'Sim'), ('nao', 'Não'), ('as_vezes', 'Às vezes')])),
                ('ai_familiarity',       models.CharField(max_length=20, choices=[('nenhuma', 'Nenhuma'), ('pouca', 'Pouca'), ('moderada', 'Moderada'), ('alta', 'Alta')])),
                ('timestamp',            models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-timestamp']},
        ),
    ]
