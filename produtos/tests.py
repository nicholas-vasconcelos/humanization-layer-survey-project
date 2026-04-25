from decimal import Decimal

from django.test import TestCase

from .models import Catalogue, Product
from .recommendation import get_recommendations


class RecommendationTests(TestCase):
	def _create_catalogue(self, name: str, slug: str) -> Catalogue:
		return Catalogue.objects.create(name=name, slug=slug, description='')

	def _create_product(
		self,
		*,
		catalogue: Catalogue,
		name: str,
		price: str,
		brand: str,
		item_type: str,
		price_tier: str,
		featured: bool = False,
	) -> Product:
		return Product.objects.create(
			catalogue=catalogue,
			name=name,
			description='descricao de teste',
			price=Decimal(price),
			image_url='https://example.com/item.jpg',
			featured=featured,
			brand=brand,
			item_type=item_type,
			price_tier=price_tier,
		)

	def test_mesmo_catalogo_e_mesmo_tipo_pontua_mais_que_cross_catalogo(self):
		catalogo_a = self._create_catalogue('A', 'a')
		catalogo_b = self._create_catalogue('B', 'b')

		base = self._create_product(
			catalogue=catalogo_a,
			name='Base Mouse',
			price='220.00',
			brand='Logitech',
			item_type='mouse',
			price_tier='mid',
		)
		same_catalog_same_type = self._create_product(
			catalogue=catalogo_a,
			name='Mouse Similar',
			price='230.00',
			brand='GenBrand',
			item_type='mouse',
			price_tier='mid',
		)
		cross_catalog = self._create_product(
			catalogue=catalogo_b,
			name='Monitor Distante',
			price='240.00',
			brand='OutraMarca',
			item_type='monitor',
			price_tier='mid',
		)

		recs = get_recommendations(base.id, top_n=10)
		score_map = {item['id']: item['score'] for item in recs}

		self.assertGreater(score_map[same_catalog_same_type.id], score_map[cross_catalog.id])

	def test_mesma_marca_pontua_mais_que_marca_diferente_no_mesmo_tier(self):
		catalogo = self._create_catalogue('A', 'a')

		base = self._create_product(
			catalogue=catalogo,
			name='Base Teclado',
			price='350.00',
			brand='Logitech',
			item_type='teclado',
			price_tier='mid',
		)
		mesma_marca = self._create_product(
			catalogue=catalogo,
			name='Teclado Mesma Marca',
			price='360.00',
			brand='logitech',
			item_type='teclado',
			price_tier='mid',
		)
		marca_diferente = self._create_product(
			catalogue=catalogo,
			name='Teclado Outra Marca',
			price='355.00',
			brand='Razer',
			item_type='teclado',
			price_tier='mid',
		)

		recs = get_recommendations(base.id, top_n=10)
		score_map = {item['id']: item['score'] for item in recs}

		self.assertGreater(score_map[mesma_marca.id], score_map[marca_diferente.id])

	def test_mesmo_price_tier_pontua_mais_que_tier_distante(self):
		catalogo = self._create_catalogue('A', 'a')

		base = self._create_product(
			catalogue=catalogo,
			name='Base Monitor',
			price='1800.00',
			brand='LG',
			item_type='monitor',
			price_tier='premium',
		)
		mesmo_tier = self._create_product(
			catalogue=catalogo,
			name='Monitor Premium',
			price='1900.00',
			brand='Asus',
			item_type='monitor',
			price_tier='premium',
		)
		tier_distante = self._create_product(
			catalogue=catalogo,
			name='Monitor Budget',
			price='320.00',
			brand='Asus',
			item_type='monitor',
			price_tier='budget',
		)

		recs = get_recommendations(base.id, top_n=10)
		score_map = {item['id']: item['score'] for item in recs}

		self.assertGreater(score_map[mesmo_tier.id], score_map[tier_distante.id])

	def test_endpoint_recommend_retorna_top_n_com_id_e_score(self):
		catalogo = self._create_catalogue('A', 'a')

		base = self._create_product(
			catalogue=catalogo,
			name='Base Headset',
			price='450.00',
			brand='HyperX',
			item_type='headset',
			price_tier='mid',
		)
		self._create_product(
			catalogue=catalogo,
			name='Headset 1',
			price='430.00',
			brand='HyperX',
			item_type='headset',
			price_tier='mid',
		)
		self._create_product(
			catalogue=catalogo,
			name='Headset 2',
			price='700.00',
			brand='Razer',
			item_type='headset',
			price_tier='premium',
		)
		self._create_product(
			catalogue=catalogo,
			name='Headset 3',
			price='180.00',
			brand='Sony',
			item_type='fone',
			price_tier='budget',
		)

		response = self.client.get(f'/api/produtos/{base.id}/recommend/?top_n=2')

		self.assertEqual(response.status_code, 200)
		body = response.json()
		self.assertIsInstance(body, list)
		self.assertEqual(len(body), 2)
		self.assertIn('id', body[0])
		self.assertIn('score', body[0])
