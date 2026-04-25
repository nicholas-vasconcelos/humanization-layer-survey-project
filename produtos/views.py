import json
import logging
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Catalogue, Product, SessionResponse
from .recommendation import get_recommendations
from .serializers import ProdutoSerializer


logger = logging.getLogger(__name__)


ROBOTIC_PROMPT = """You are a recommendation engine.
Output exactly 3 products in this format:
1. [Product Name] — [one-line spec]
2. [Product Name] — [one-line spec]
3. [Product Name] — [one-line spec]
No additional text.
"""

HUMANIZED_PROMPT = """You are Maya, a friendly shopping assistant helping a university tech student.
Structure your response using exactly these components in order:
1. [Persona] — introduce yourself warmly by name
2. [Empathy Phrase] — acknowledge what the user has been browsing
3. [Recommendation] — suggest 3 products naturally in flowing text
4. [Social Proof] — mention that other students with similar interests liked these
5. [Call to Action] — close with a soft open-ended invitation
Do not use headers or labels. Write in short, conversational paragraphs.
Keep it concise: 4 to 6 short sentences, with a maximum of 90 words total.
Respond entirely in Brazilian Portuguese.
"""


class ProdutoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.select_related('catalogue').all()
    serializer_class = ProdutoSerializer

    @action(detail=True, methods=['get'])
    def recommend(self, request, pk=None):
        produto = self.get_object()

        try:
            top_n = int(request.query_params.get('top_n', 5))
        except (TypeError, ValueError):
            top_n = 5

        if top_n <= 0:
            top_n = 5

        recommendations = get_recommendations(product_id=produto.id, top_n=top_n)
        return Response(recommendations, status=status.HTTP_200_OK)


def build_user_content(catalogue_obj, selected_products):
    products_text = "\n".join(
        (
            f"- {product.name}: {product.description} "
            f"(brand={product.brand}, item_type={product.item_type}, price_tier={product.price_tier}, preco=R$ {product.price})"
        )
        for product in selected_products
    )
    return f"Catalogue: {catalogue_obj.name}\nSelected products:\n{products_text}"


def build_ranked_candidates(selected_products, catalogue_obj, top_n=8):
    selected_ids = {product.id for product in selected_products}
    aggregated = {}

    for product in selected_products:
        product_recommendations = get_recommendations(product_id=product.id, top_n=12)
        for candidate in product_recommendations:
            candidate_id = candidate.get('id')
            if not candidate_id or candidate_id in selected_ids:
                continue
            if candidate.get('catalogue_id') != catalogue_obj.id:
                continue

            if candidate_id not in aggregated:
                aggregated[candidate_id] = {
                    'id': candidate_id,
                    'nome': candidate.get('nome', ''),
                    'preco': candidate.get('preco', ''),
                    'brand': candidate.get('brand', ''),
                    'item_type': candidate.get('item_type', ''),
                    'price_tier': candidate.get('price_tier', ''),
                    'score_sum': 0.0,
                    'hits': 0,
                    'max_score': 0.0,
                }

            aggregated[candidate_id]['score_sum'] += float(candidate.get('score', 0.0))
            aggregated[candidate_id]['hits'] += 1
            aggregated[candidate_id]['max_score'] = max(
                aggregated[candidate_id]['max_score'],
                float(candidate.get('score', 0.0)),
            )

    ranked = []
    for candidate in aggregated.values():
        avg_score = candidate['score_sum'] / candidate['hits']
        final_score = (avg_score * 0.8) + (0.2 * candidate['max_score'])
        ranked.append(
            {
                'id': candidate['id'],
                'nome': candidate['nome'],
                'preco': candidate['preco'],
                'brand': candidate['brand'],
                'item_type': candidate['item_type'],
                'price_tier': candidate['price_tier'],
                'score': round(final_score, 4),
                'hits': candidate['hits'],
            }
        )

    ranked.sort(key=lambda item: (item['score'], item['hits']), reverse=True)
    return ranked[:top_n]


def append_ranked_candidates_to_content(base_content, ranked_candidates):
    if not ranked_candidates:
        return f"{base_content}\n\nRanked candidate products by attribute scoring:\n- No ranked candidates available."

    ranked_text = "\n".join(
        (
            f"- {candidate['nome']} | score={candidate['score']} | "
            f"brand={candidate['brand']} | item_type={candidate['item_type']} | "
            f"price_tier={candidate['price_tier']} | preco=R$ {candidate['preco']}"
        )
        for candidate in ranked_candidates
    )
    return f"{base_content}\n\nRanked candidate products by attribute scoring:\n{ranked_text}"


def normalize_name(value):
    normalized = unicodedata.normalize('NFD', (value or '').strip().lower())
    return ''.join(char for char in normalized if not unicodedata.combining(char))


def build_product_spec(product):
    description = (product.description or '').strip()
    if not description:
        return f"Opcao da categoria {product.catalogue.name}."

    first_sentence = description.split('. ')[0].strip()
    sentence = first_sentence if first_sentence else description
    if len(sentence) > 105:
        sentence = f"{sentence[:102].rstrip()}..."
    return sentence


def sanitize_robotic_output(raw_text, allowed_products):
    if not allowed_products:
        return raw_text

    products_by_name = {normalize_name(product.name): product for product in allowed_products}
    used_ids = set()
    output_items = []

    for line in (raw_text or '').splitlines():
        cleaned_line = line.strip()
        if not cleaned_line:
            continue

        match = re.match(r'^\d+\.\s*(.+)$', cleaned_line)
        content = match.group(1).strip() if match else cleaned_line
        name_part, spec_part = re.split(r'\s+[—-]\s+', content, maxsplit=1) if re.search(r'\s+[—-]\s+', content) else (content, '')

        parsed_name = name_part.strip().strip('[]').strip()
        parsed_spec = spec_part.strip().strip('[]').strip()
        product = products_by_name.get(normalize_name(parsed_name))

        if not product or product.id in used_ids:
            continue

        used_ids.add(product.id)
        output_items.append((product, parsed_spec or build_product_spec(product)))

        if len(output_items) == 3:
            break

    for product in allowed_products:
        if len(output_items) == 3:
            break
        if product.id in used_ids:
            continue
        used_ids.add(product.id)
        output_items.append((product, build_product_spec(product)))

    return "\n".join(
        f"{index}. {product.name} — {spec}"
        for index, (product, spec) in enumerate(output_items, start=1)
    )


def select_products_for_humanized_output(raw_text, preferred_products, fallback_products, top_n=3):
    normalized_text = normalize_name(raw_text)

    merged_candidates = []
    seen_ids = set()
    for product in preferred_products + fallback_products:
        if product.id in seen_ids:
            continue
        seen_ids.add(product.id)
        merged_candidates.append(product)

    selected = []
    selected_ids = set()

    for product in merged_candidates:
        normalized_product_name = normalize_name(product.name)
        if normalized_product_name and normalized_product_name in normalized_text:
            selected.append(product)
            selected_ids.add(product.id)
            if len(selected) == top_n:
                return selected

    for product in merged_candidates:
        if product.id in selected_ids:
            continue
        selected.append(product)
        selected_ids.add(product.id)
        if len(selected) == top_n:
            break

    return selected


def all_products_mentioned(raw_text, products):
    normalized_text = normalize_name(raw_text)
    return all(normalize_name(product.name) in normalized_text for product in products)


def build_humanized_consistent_output(products):
    if not products:
        return 'Oi, eu sou a Maya. Posso te ajudar com novas opcoes quando voce quiser.'

    if len(products) == 1:
        recommendation_line = f"Eu recomendo o {products[0].name}."
    elif len(products) == 2:
        recommendation_line = f"Eu recomendo o {products[0].name} e o {products[1].name}."
    else:
        recommendation_line = (
            f"Eu recomendo o {products[0].name}, o {products[1].name} "
            f"e o {products[2].name}."
        )

    return " ".join(
        [
            'Oi, eu sou a Maya e adorei as suas escolhas.',
            'Pelo que voce explorou, voce parece buscar desempenho com bom custo-beneficio.',
            recommendation_line,
            'Outros estudantes com interesses parecidos curtiram bastante essas opcoes.',
            'Se quiser, eu te mostro qual delas combina melhor com o seu uso.',
        ]
    )


def call_groq(system_prompt, user_content):
    api_key = getattr(settings, 'GROQ_API_KEY', '')
    if not api_key:
        logger.warning('GROQ_API_KEY não configurada; retornando fallback.')
        return 'Não foi possível gerar recomendações no momento.'

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            max_tokens=1000,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_content},
            ],
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as exc:
        logger.error('Falha ao chamar Groq: %s', exc)
        return 'Não foi possível gerar recomendações no momento.'


def save_to_supabase(data):
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        logger.warning('Credenciais Supabase ausentes; espelhamento ignorado.')
        return

    try:
        from supabase import create_client

        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
        client.table('session_responses').insert(data).execute()
    except Exception as exc:
        # Loga erro sem interromper o fluxo do participante.
        logger.error('Supabase insert failed: %s', exc)


# ─────────────────────────────────────────────
# Step 1 — Landing page
# ─────────────────────────────────────────────
def landing(request):
    """
    Explains the research project and shows a single 'Começar' CTA.
    Also initialises a fresh session_id in the Django session.
    """
    # Wipe any leftover session data so each visit starts clean
    for key in ['interest_slug', 'selected_product_ids',
                'robotic_output', 'humanized_output']:
        request.session.pop(key, None)

    return render(request, 'landing.html')


# ─────────────────────────────────────────────
# Step 2 — Interest selection
# ─────────────────────────────────────────────
def select_interest(request):
    """
    Shows the four interest-area cards.
    On POST, saves the chosen slug to session and redirects to catalogue.
    """
    if request.method == 'POST':
        slug = request.POST.get('slug', '').strip()
        # Validate that the slug actually exists
        catalogue = get_object_or_404(Catalogue, slug=slug)
        request.session['interest_slug'] = catalogue.slug
        from django.shortcuts import redirect
        return redirect('catalogue')

    catalogues = Catalogue.objects.all()
    return render(request, 'select_interest.html', {'catalogues': catalogues})


# ─────────────────────────────────────────────
# Step 3 — Product catalogue
# ─────────────────────────────────────────────
def catalogue(request):
    """
    Displays the products for the interest area stored in session.
    On POST (AJAX), saves the selected product IDs to session.
    """
    slug = request.session.get('interest_slug')
    if not slug:
        from django.shortcuts import redirect
        return redirect('select_interest')

    catalogue_obj = get_object_or_404(Catalogue, slug=slug)
    products = catalogue_obj.products.all()

    return render(request, 'catalogue.html', {
        'catalogue': catalogue_obj,
        'products': products,
    })


def all_catalogue(request):
    """
    Public showcase page with all products across every catalogue.
    """
    products = Product.objects.select_related('catalogue').order_by(
        'catalogue__name', '-featured', 'name'
    )
    return render(request, 'all_catalogue.html', {
        'products': products,
        'total_products': products.count(),
    })


# ─────────────────────────────────────────────
# Step 3 → 4 — AJAX endpoint: save selected products
# ─────────────────────────────────────────────
@require_POST
@csrf_exempt  # CSRF handled via JS fetch with cookie later; safe for now
def save_selection(request):
    """
    Receives a JSON body: {"product_ids": [1, 3, 7]}
    Saves to session and returns 200 OK.
    """
    try:
        body = json.loads(request.body)
        ids = body.get('product_ids', [])
        if not ids:
            return JsonResponse({'error': 'Nenhum produto selecionado.'}, status=400)
        # Validate that the IDs belong to the correct catalogue
        slug = request.session.get('interest_slug')
        valid_ids = list(
            Product.objects.filter(
                id__in=ids, catalogue__slug=slug
            ).values_list('id', flat=True)
        )
        if not valid_ids:
            return JsonResponse({'error': 'Produtos inválidos.'}, status=400)
        request.session['selected_product_ids'] = valid_ids
        return JsonResponse({'ok': True})
    except (json.JSONDecodeError, Exception) as e:
        return JsonResponse({'error': str(e)}, status=400)


# ─────────────────────────────────────────────
# Step 4 — Recommendations
# ─────────────────────────────────────────────
def recommendations(request):
    """
    Reads session data, calls Groq API in parallel,
    and renders both A/B outputs side by side.
    """
    slug = request.session.get('interest_slug')
    ids  = request.session.get('selected_product_ids')

    if not slug or not ids:
        from django.shortcuts import redirect
        return redirect('select_interest')

    catalogue_obj = get_object_or_404(Catalogue, slug=slug)
    selected_products = list(
        Product.objects.filter(id__in=ids, catalogue=catalogue_obj)
    )
    if not selected_products:
        from django.shortcuts import redirect
        return redirect('catalogue')

    user_content = build_user_content(catalogue_obj, selected_products)
    ranked_candidates = build_ranked_candidates(selected_products, catalogue_obj, top_n=8)
    user_content = append_ranked_candidates_to_content(user_content, ranked_candidates)

    selected_ids = {product.id for product in selected_products}
    candidate_pool = list(
        Product.objects.filter(catalogue=catalogue_obj)
        .exclude(id__in=selected_ids)
        .order_by('-featured', 'name')
    )
    pool_by_id = {product.id: product for product in candidate_pool}
    robotic_allowed_products = []
    used_allowed_ids = set()

    for candidate in ranked_candidates:
        candidate_id = candidate.get('id')
        product = pool_by_id.get(candidate_id)
        if not product or product.id in used_allowed_ids:
            continue
        used_allowed_ids.add(product.id)
        robotic_allowed_products.append(product)

    for product in candidate_pool:
        if product.id in used_allowed_ids:
            continue
        used_allowed_ids.add(product.id)
        robotic_allowed_products.append(product)

    if not robotic_allowed_products:
        robotic_allowed_products = selected_products[:]

    top_humanized_ids = [candidate['id'] for candidate in ranked_candidates[:3]]
    top_humanized_map = {
        product.id: product
        for product in Product.objects.filter(id__in=top_humanized_ids)
    }
    humanized_card_products = [
        top_humanized_map[product_id]
        for product_id in top_humanized_ids
        if product_id in top_humanized_map
    ]

    if len(humanized_card_products) < 3:
        already_ids = {product.id for product in humanized_card_products}
        selected_ids = {product.id for product in selected_products}

        fallback_products = Product.objects.filter(
            catalogue=catalogue_obj,
        ).exclude(
            id__in=already_ids.union(selected_ids),
        ).order_by('-featured', 'name')[:3]

        for product in fallback_products:
            if len(humanized_card_products) >= 3:
                break
            humanized_card_products.append(product)
            already_ids.add(product.id)

        if len(humanized_card_products) < 3:
            selected_fill = (
                Product.objects.filter(id__in=selected_ids)
                .order_by('-featured', 'name')
            )
            for product in selected_fill:
                if len(humanized_card_products) >= 3:
                    break
                if product.id in already_ids:
                    continue
                humanized_card_products.append(product)
                already_ids.add(product.id)

    robotic_products_payload = list(
        Product.objects.filter(catalogue=catalogue_obj)
        .values('name', 'price', 'image_url')
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_robotic = executor.submit(call_groq, ROBOTIC_PROMPT, user_content)
        f_humanized = executor.submit(call_groq, HUMANIZED_PROMPT, user_content)
        robotic_output_raw = f_robotic.result()
        humanized_output_raw = f_humanized.result()

    robotic_output = sanitize_robotic_output(robotic_output_raw, robotic_allowed_products)

    humanized_card_products = select_products_for_humanized_output(
        humanized_output_raw,
        preferred_products=humanized_card_products,
        fallback_products=robotic_allowed_products,
        top_n=3,
    )
    if all_products_mentioned(humanized_output_raw, humanized_card_products):
        humanized_output = humanized_output_raw
    else:
        humanized_output = build_humanized_consistent_output(humanized_card_products)

    humanized_products_payload = [
        {
            'name': product.name,
            'image_url': product.image_url or '',
        }
        for product in humanized_card_products[:3]
    ]

    # Persist outputs to session so the survey can reference them
    request.session['robotic_output']   = robotic_output
    request.session['humanized_output'] = humanized_output

    return render(request, 'recommendations.html', {
        'catalogue':          catalogue_obj,
        'selected_products':  selected_products,
        'robotic_output':     robotic_output,
        'humanized_output':   humanized_output,
        'humanized_card_products': humanized_card_products,
        'humanized_products_payload': humanized_products_payload,
        'robotic_products_payload': robotic_products_payload,
    })


# ─────────────────────────────────────────────
# Step 5 — Survey
# ─────────────────────────────────────────────
def survey(request):
    """
    On GET: shows the survey form.
    On POST: saves a SessionResponse and redirects to thank-you.
    """
    if request.method == 'POST':
        from django.shortcuts import redirect

        slug     = request.session.get('interest_slug', '')
        ids      = request.session.get('selected_product_ids', [])
        robotic  = request.session.get('robotic_output', '')
        humanized = request.session.get('humanized_output', '')

        response_obj = SessionResponse.objects.create(
            interest_selected    = slug,
            products_selected    = ids,
            robotic_output       = robotic,
            humanized_output     = humanized,
            preferred_overall    = request.POST.get('preferred_overall',    ''),
            preferred_trust      = request.POST.get('preferred_trust',      ''),
            preferred_purchase   = request.POST.get('preferred_purchase',   ''),
            preferred_understood = request.POST.get('preferred_understood', ''),
            uses_ai_shopping     = request.POST.get('uses_ai_shopping',     ''),
            ai_familiarity       = request.POST.get('ai_familiarity',       ''),
        )

        save_to_supabase({
            'session_id': str(response_obj.session_id),
            'interest_selected': response_obj.interest_selected,
            'products_selected': response_obj.products_selected,
            'robotic_output': response_obj.robotic_output,
            'humanized_output': response_obj.humanized_output,
            'preferred_overall': response_obj.preferred_overall,
            'preferred_trust': response_obj.preferred_trust,
            'preferred_purchase': response_obj.preferred_purchase,
            'preferred_understood': response_obj.preferred_understood,
            'uses_ai_shopping': response_obj.uses_ai_shopping,
            'ai_familiarity': response_obj.ai_familiarity,
            'timestamp': response_obj.timestamp.isoformat(),
        })

        # Clear session after saving
        for key in ['interest_slug', 'selected_product_ids',
                    'robotic_output', 'humanized_output']:
            request.session.pop(key, None)

        return redirect('thank_you')

    # GET — did the user reach here with valid session data?
    preferred = request.POST.get('preferred_overall') or \
                request.GET.get('preferred')  # passed as query param from JS

    return render(request, 'survey.html', {
        'preferred_initial': preferred,
    })


# ─────────────────────────────────────────────
# Step 6 — Thank you
# ─────────────────────────────────────────────
def thank_you(request):
    return render(request, 'thank_you.html')