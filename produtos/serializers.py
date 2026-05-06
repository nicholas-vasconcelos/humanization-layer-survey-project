from rest_framework import serializers

from .models import Catalogue, Product


class CategoriaSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source='name', read_only=True)

    class Meta:
        model = Catalogue
        fields = ['id', 'nome']


class ProdutoSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source='name', read_only=True)
    descricao = serializers.CharField(source='description', read_only=True)
    nome_en = serializers.CharField(source='name_en', read_only=True)
    descricao_en = serializers.CharField(source='description_en', read_only=True)
    preco = serializers.DecimalField(source='price', max_digits=10, decimal_places=2, read_only=True)
    imagem = serializers.URLField(source='image_url', read_only=True)
    categoria = CategoriaSerializer(source='catalogue', read_only=True)
    categoria_id = serializers.IntegerField(source='catalogue_id', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'nome',
            'descricao',
            'nome_en',
            'descricao_en',
            'preco',
            'imagem',
            'featured',
            'categoria',
            'categoria_id',
            'brand',
            'item_type',
            'price_tier',
        ]