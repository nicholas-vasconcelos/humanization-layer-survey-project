from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('produtos', '0006_product_brand_product_item_type_product_price_tier'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='name_en',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='product',
            name='description_en',
            field=models.TextField(blank=True, default='', max_length=500),
        ),
    ]
