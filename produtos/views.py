import json
import logging
import unicodedata

from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Catalogue, Product, SessionResponse
from .recommendation import get_recommendations
from .serializers import ProdutoSerializer


logger = logging.getLogger(__name__)


def build_lang_url(request, target_lang):
    params = request.GET.copy()
    params['lang'] = target_lang
    return f"{request.path}?{params.urlencode()}"


def get_lang_context(request):
    requested = request.GET.get('lang')
    if requested in {'pt', 'en'}:
        request.session['lang'] = requested

    lang = request.session.get('lang', 'pt')
    return {
        'lang': lang,
        'lang_url_pt': build_lang_url(request, 'pt'),
        'lang_url_en': build_lang_url(request, 'en'),
    }


def with_lang(request, context=None):
    payload = {} if context is None else dict(context)
    payload.update(get_lang_context(request))
    return payload


HUMANIZED_PROMPT_EN = """You are Maya, a friendly shopping assistant helping a university tech student.
Use the provided catalogue and selected products to form your recommendations.
Write exactly five lines, one per item, in this order:
Persona Name (Social Presence), Empathy Phrase (Perceived Warmth), Recommendation (Functional Value), Social Proof (Information-Seeking/UGT), Call to Action (Customer Engagement).
Do NOT include numbering, bullets, or labels. Just the five lines of content.
Do not add extra text before or after the five lines.
Keep it concise and natural. Respond entirely in English.

Example format (do not copy the content, only the structure of five plain lines):
Hi, I'm Maya, your shopping assistant today.
I can see you've been exploring options for your setup and studying needs.
I recommend [Product A], [Product B], and [Product C] because they match your priorities.
Other students with similar interests have been happy with these picks.
Would you like me to help you choose which one fits you best?
"""

HUMANIZED_PROMPT_PT = """Voce e a Maya, uma assistente de compras amigavel que ajuda um estudante universitario de tecnologia.
Use o catalogo e os produtos selecionados fornecidos para formar suas recomendacoes.
Escreva exatamente cinco linhas, uma por item, nesta ordem:
Nome da Persona (Presenca Social), Frase de Empatia (Calor Percebido), Recomendacao (Valor Funcional), Prova Social (Busca de Informacao/UGT), Chamada a Acao (Engajamento do Cliente).
Nao inclua numeracao, marcadores ou rotulos. Apenas as cinco linhas de conteudo.
Nao adicione texto antes ou depois das cinco linhas.
Seja concisa e natural. Responda inteiramente em portugues brasileiro.

Exemplo de formato (nao copie o conteudo, apenas a estrutura de cinco linhas simples):
Oi, eu sou a Maya, sua assistente de compras hoje.
Vejo que voce explorou opcoes para seu setup e estudos.
Eu recomendo [Produto A], [Produto B] e [Produto C] porque combinam com o que voce busca.
Outros estudantes com interesses parecidos ficaram satisfeitos com essas escolhas.
Quer que eu te ajude a decidir qual combina melhor com voce?
"""


def validate_humanized_output(text, lang):
    if not text:
        return False

    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if len(lines) != 5:
        return False

    disallowed_tokens = (
        'persona',
        'empathy phrase',
        'recommendation',
        'social proof',
        'call to action',
        'frase de empatia',
        'recomendacao',
        'prova social',
        'chamada a acao',
    )

    for line in lines:
        lower = line.lower()
        if lower.startswith(tuple(str(i) for i in range(1, 6))):
            return False
        if any(token in lower for token in disallowed_tokens):
            return False
    return True


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


def get_product_name(product, lang):
    if lang == 'en' and getattr(product, 'name_en', ''):
        return product.name_en
    return product.name


def get_product_description(product, lang):
    if lang == 'en' and getattr(product, 'description_en', ''):
        return product.description_en
    return product.description


def build_user_content(catalogue_obj, selected_products, lang):
    catalogue_label = 'Catalogue' if lang == 'en' else 'Catalogo'
    selected_label = 'Selected products' if lang == 'en' else 'Produtos selecionados'
    price_label = 'price=BRL' if lang == 'en' else 'preco=R$'

    products_text = "\n".join(
        (
            f"- {get_product_name(product, lang)}: {get_product_description(product, lang)} "
            f"(brand={product.brand}, item_type={product.item_type}, price_tier={product.price_tier}, {price_label} {product.price})"
        )
        for product in selected_products
    )
    return f"{catalogue_label}: {catalogue_obj.name}\n{selected_label}:\n{products_text}"


def build_ranked_candidates(selected_products, catalogue_obj, top_n=8):
    selected_ids = {product.id for product in selected_products}
    aggregated = {}

    for product in selected_products:
        product_recommendations = get_recommendations(
            product_id=product.id,
            top_n=12,
            exclude_ids=selected_ids,
            exclude_catalogue_id=catalogue_obj.id,
        )
        for candidate in product_recommendations:
            candidate_id = candidate.get('id')
            if not candidate_id or candidate_id in selected_ids:
                continue
            if candidate.get('catalogue_id') == catalogue_obj.id:
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


def append_ranked_candidates_to_content(base_content, ranked_candidates, lang):
    heading = (
        'Ranked candidate products by attribute scoring'
        if lang == 'en'
        else 'Produtos candidatos ranqueados por pontuacao de atributos'
    )
    empty_line = (
        '- No ranked candidates available.'
        if lang == 'en'
        else '- Nenhum candidato ranqueado disponivel.'
    )

    if not ranked_candidates:
        return f"{base_content}\n\n{heading}:\n{empty_line}"

    ranked_text = "\n".join(
        (
            f"- {candidate['nome']} | score={candidate['score']} | "
            f"brand={candidate['brand']} | item_type={candidate['item_type']} | "
            f"price_tier={candidate['price_tier']} | preco=R$ {candidate['preco']}"
        )
        for candidate in ranked_candidates
    )
    return f"{base_content}\n\n{heading}:\n{ranked_text}"


def normalize_name(value):
    normalized = unicodedata.normalize('NFD', (value or '').strip().lower())
    return ''.join(char for char in normalized if not unicodedata.combining(char))


def build_product_spec(product, lang):
    description = (get_product_description(product, lang) or '').strip()
    if not description:
        if lang == 'en':
            return f"Option from the {product.catalogue.name} catalogue."
        return f"Opcao da categoria {product.catalogue.name}."

    first_sentence = description.split('. ')[0].strip()
    sentence = first_sentence if first_sentence else description
    if len(sentence) > 105:
        sentence = f"{sentence[:102].rstrip()}..."
    return sentence


def build_robotic_output(products, lang, max_items=3):
    if not products:
        return ''

    output_items = []
    for product in products:
        output_items.append((product, build_product_spec(product, lang)))
        if len(output_items) >= max_items:
            break

    return "\n".join(
        f"{index}. {get_product_name(product, lang)} — {spec}"
        for index, (product, spec) in enumerate(output_items, start=1)
    )


def select_products_for_humanized_output(raw_text, preferred_products, fallback_products, top_n=3, lang='pt'):
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
        normalized_product_name = normalize_name(get_product_name(product, lang))
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


def all_products_mentioned(raw_text, products, lang):
    normalized_text = normalize_name(raw_text)
    return all(normalize_name(get_product_name(product, lang)) in normalized_text for product in products)


def any_products_mentioned(raw_text, products, lang):
    normalized_text = normalize_name(raw_text)
    return any(normalize_name(get_product_name(product, lang)) in normalized_text for product in products)


def build_humanized_consistent_output(products, lang):
    if not products:
        if lang == 'en':
            return 'Hi, I am Maya. I can help you with new options whenever you want.'
        return 'Oi, eu sou a Maya. Posso te ajudar com novas opcoes quando voce quiser.'

    names = [get_product_name(product, lang) for product in products]

    if lang == 'en':
        if len(names) == 1:
            recommendation_line = f"I recommend the {names[0]}."
        elif len(names) == 2:
            recommendation_line = f"I recommend the {names[0]} and the {names[1]}."
        else:
            recommendation_line = f"I recommend the {names[0]}, the {names[1]}, and the {names[2]}."

        return " ".join(
            [
                'Hi, I am Maya and I loved your picks.',
                'From what you explored, you seem to be looking for strong performance at a fair price.',
                recommendation_line,
                'Other students with similar interests really liked these options.',
                'If you want, I can show which one fits your use best.',
            ]
        )

    if len(names) == 1:
        recommendation_line = f"Eu recomendo o {names[0]}."
    elif len(names) == 2:
        recommendation_line = f"Eu recomendo o {names[0]} e o {names[1]}."
    else:
        recommendation_line = f"Eu recomendo o {names[0]}, o {names[1]} e o {names[2]}."

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
        logger.warning('GROQ_API_KEY não configurada; Groq indisponível.')
        return None

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
        return None


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

    return render(request, 'landing.html', with_lang(request))


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
    return render(request, 'select_interest.html', with_lang(request, {
        'catalogues': catalogues,
    }))


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
    primary_products = list(catalogue_obj.products.order_by('?'))
    if len(primary_products) >= 18:
        products = primary_products[:18]
    else:
        needed = 18 - len(primary_products)
        filler_products = list(
            Product.objects.exclude(catalogue=catalogue_obj)
            .order_by('?')[:needed]
        )
        products = primary_products + filler_products

    return render(request, 'catalogue.html', with_lang(request, {
        'catalogue': catalogue_obj,
        'products': products,
    }))


def all_catalogue(request):
    """
    Public showcase page with all products across every catalogue.
    """
    products = Product.objects.select_related('catalogue').order_by(
        'catalogue__name', '-featured', 'name'
    )
    return render(request, 'all_catalogue.html', with_lang(request, {
        'products': products,
        'total_products': products.count(),
    }))


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
        valid_ids = list(
            Product.objects.filter(id__in=ids).values_list('id', flat=True)
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
    Reads session data, calls Groq for the humanized output,
    and renders robotic/humanized outputs side by side.
    """
    slug = request.session.get('interest_slug')
    ids  = request.session.get('selected_product_ids')

    if not slug or not ids:
        from django.shortcuts import redirect
        return redirect('select_interest')

    catalogue_obj = get_object_or_404(Catalogue, slug=slug)
    selected_products = list(Product.objects.filter(id__in=ids))
    if not selected_products:
        from django.shortcuts import redirect
        return redirect('catalogue')

    lang = get_lang_context(request)['lang']
    user_content = build_user_content(catalogue_obj, selected_products, lang)
    ranked_candidates = build_ranked_candidates(selected_products, catalogue_obj, top_n=8)
    if ranked_candidates:
        ranked_ids = [candidate['id'] for candidate in ranked_candidates if candidate.get('id')]
        ranked_products = {
            product.id: product
            for product in Product.objects.filter(id__in=ranked_ids)
        }
        for candidate in ranked_candidates:
            product = ranked_products.get(candidate.get('id'))
            if product:
                candidate['nome'] = get_product_name(product, lang)
    user_content = append_ranked_candidates_to_content(user_content, ranked_candidates, lang)

    selected_ids = {product.id for product in selected_products}
    candidate_pool = list(
        Product.objects.exclude(catalogue=catalogue_obj)
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
        robotic_allowed_products = []

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
        return render(request, 'humanized_unavailable.html', with_lang(request), status=503)



    robotic_products_payload = [
        {
            'name': get_product_name(product, lang),
            'price': product.price,
            'image_url': product.image_url,
        }
        for product in Product.objects.exclude(catalogue=catalogue_obj)
    ]

    humanized_prompt = HUMANIZED_PROMPT_EN if lang == 'en' else HUMANIZED_PROMPT_PT
    recommended_names = [get_product_name(product, lang) for product in humanized_card_products]
    selected_names = [get_product_name(product, lang) for product in selected_products]
    recommendations_hint = "\n".join(f"- {name}" for name in recommended_names)
    humanized_user_content = (
        f"{user_content}\n\n"
        f"Recommended products to include (use exactly these names):\n{recommendations_hint}"
    )
    humanized_output_raw = call_groq(humanized_prompt, humanized_user_content)
    if (
        not validate_humanized_output(humanized_output_raw, lang)
        or not all_products_mentioned(humanized_output_raw, humanized_card_products, lang)
        or any_products_mentioned(humanized_output_raw, selected_products, lang)
    ):
        return render(request, 'humanized_unavailable.html', with_lang(request), status=503)
    robotic_output = build_robotic_output(robotic_allowed_products, lang)
    humanized_output = humanized_output_raw

    humanized_products_payload = [
        {
            'name': get_product_name(product, lang),
            'image_url': product.image_url or '',
        }
        for product in humanized_card_products[:3]
    ]

    # Persist outputs to session so the survey can reference them
    request.session['robotic_output']   = robotic_output
    request.session['humanized_output'] = humanized_output

    return render(request, 'recommendations.html', with_lang(request, {
        'catalogue':          catalogue_obj,
        'selected_products':  selected_products,
        'robotic_output':     robotic_output,
        'humanized_output':   humanized_output,
        'humanized_card_products': humanized_card_products,
        'humanized_products_payload': humanized_products_payload,
        'robotic_products_payload': robotic_products_payload,
    }))


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
            participant_email    = request.POST.get('participant_email',    '').strip(),
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
            'participant_email': response_obj.participant_email,
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

    return render(request, 'survey.html', with_lang(request, {
        'preferred_initial': preferred,
    }))


# ─────────────────────────────────────────────
# Step 6 — Thank you
# ─────────────────────────────────────────────
def thank_you(request):
    return render(request, 'thank_you.html', with_lang(request))