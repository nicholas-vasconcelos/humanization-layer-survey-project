from __future__ import annotations

from .models import Product


PRICE_TIER_ORDER = {
    'budget': 0,
    'mid': 1,
    'premium': 2,
    'high-end': 3,
}

TYPE_GROUPS = {
    'peripherals': {'mouse', 'teclado', 'headset', 'mousepad', 'controle'},
    'audio': {
        'fone',
        'microfone',
        'headset',
        'audio_interface',
        'caixa_de_som',
        'studio_monitor',
        'dac',
        'mixer',
        'gravador',
    },
    'compute': {
        'ssd',
        'processador',
        'gpu',
        'memoria',
        'cooling',
        'microcomputer',
        'notebook',
        'console',
        'smartphone',
        'tablet',
    },
    'display_visual': {'monitor', 'webcam', 'lighting', 'luminaria'},
    'workspace': {
        'cadeira',
        'suporte',
        'hub',
        'carregador',
        'mochila',
        'digitizer',
        'ereader',
    },
}


def _normalized(value: str) -> str:
    return (value or '').strip().lower()


def _price_score(base_tier: str, candidate_tier: str) -> float:
    base_index = PRICE_TIER_ORDER.get(_normalized(base_tier))
    candidate_index = PRICE_TIER_ORDER.get(_normalized(candidate_tier))
    if base_index is None or candidate_index is None:
        return 0.0

    diff = abs(base_index - candidate_index)
    if diff == 0:
        return 1.0
    if diff == 1:
        return 0.5
    return 0.0


def _brand_score(base_brand: str, candidate_brand: str) -> float:
    if not base_brand or not candidate_brand:
        return 0.0
    return 1.0 if _normalized(base_brand) == _normalized(candidate_brand) else 0.0


def _type_to_groups() -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for group_name, item_types in TYPE_GROUPS.items():
        for item_type in item_types:
            mapping.setdefault(item_type, set()).add(group_name)
    return mapping


def _type_score(base_type: str, candidate_type: str, type_group_map: dict[str, set[str]]) -> float:
    base_type_norm = _normalized(base_type)
    candidate_type_norm = _normalized(candidate_type)
    if not base_type_norm or not candidate_type_norm:
        return 0.0

    if base_type_norm == candidate_type_norm:
        return 1.0

    base_groups = type_group_map.get(base_type_norm, set())
    candidate_groups = type_group_map.get(candidate_type_norm, set())
    if base_groups.intersection(candidate_groups):
        return 0.5
    return 0.0


def get_recommendations(
    product_id: int,
    top_n: int = 5,
    *,
    exclude_ids: set[int] | list[int] | None = None,
    exclude_catalogue_id: int | None = None,
) -> list[dict]:
    base_product = Product.objects.get(id=product_id)
    candidates = Product.objects.select_related('catalogue').exclude(id=product_id)
    if exclude_catalogue_id is None:
        exclude_catalogue_id = base_product.catalogue_id
    if exclude_catalogue_id is not None:
        candidates = candidates.exclude(catalogue_id=exclude_catalogue_id)
    if exclude_ids:
        candidates = candidates.exclude(id__in=set(exclude_ids))

    type_group_map = _type_to_groups()
    results: list[dict] = []

    for candidate in candidates:
        price_score = _price_score(base_product.price_tier, candidate.price_tier)
        brand_score = _brand_score(base_product.brand, candidate.brand)
        type_score = _type_score(base_product.item_type, candidate.item_type, type_group_map)

        final_score = (0.25 * price_score) + (0.35 * brand_score) + (0.40 * type_score)

        results.append(
            {
                'id': candidate.id,
                'nome': candidate.name,
                'preco': str(candidate.price),
                'brand': candidate.brand,
                'item_type': candidate.item_type,
                'price_tier': candidate.price_tier,
                'score': round(final_score, 4),
                'catalogue_id': candidate.catalogue_id,
                '_featured': candidate.featured,
            }
        )

    results.sort(key=lambda item: (item['score'], item['_featured']), reverse=True)

    for item in results:
        item.pop('_featured', None)

    return results[:top_n]
