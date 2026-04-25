# Humanizing Choice - Anthropomorphic AI in Recommendations

**Academic research project — IBMEC Rio de Janeiro, 2026**
Supervised by Prof. Rigel Fernandes

🌐 **Live app:** [humanizing-catalogue-survey-env.eba-kg3w4fxe.us-east-1.elasticbeanstalk.com](http://humanizing-catalogue-survey-env.eba-kg3w4fxe.us-east-1.elasticbeanstalk.com/)

---

## Overview

*Humanizing Choice* is a web application built to support the academic paper **"Humanizing Choice — Anthropomorphic AI in Recommendations"**. The study investigates how anthropomorphic prompt engineering influences trust, purchase intent, and perceived understanding among technology university students.

Participants browse a product catalogue, select items of interest, and are then shown two AI-generated recommendations side by side — one robotic, one humanized — before completing a short survey. All data is collected anonymously.

---

## Research Contribution

The core contribution is a **five-component humanization prompt framework**:

| # | Component | Role |
|---|-----------|------|
| 1 | **Persona** (Maya) | Gives the AI a named, relatable identity |
| 2 | **Empathy Phrase** | Acknowledges what the user has been browsing |
| 3 | **Recommendation** | Suggests products in flowing, natural language |
| 4 | **Social Proof** | References similar users to build trust |
| 5 | **Call to Action** | Closes with a soft, open-ended invitation |

Each component is grounded in referenced theoretical constructs (Mariani et al. 2022, Beyari & Hashem 2025, Ribeiro et al. 2025, Srivastava & Gurme 2026, Moussawi et al. 2021, Kim et al. 2019, Kumar et al. 2025).

The experiment produces two outputs from the same product input — **Recommendation A** (robotic, rule-based) and **Recommendation B** (humanized, via a single Groq LLM call) — and measures user preference across four dimensions: overall preference, trust, purchase intention, and feeling understood.

---

## User Flow

```
Landing → Select Interest → Product Catalogue → Recommendations (A/B) → Survey → Thank You
```

1. **Landing** — explains the research context; collects no data yet.
2. **Select Interest** — four technology areas (Dev, Gaming, Productivity, Audio).
3. **Catalogue** — user taps products they find interesting.
4. **Recommendations** — two outputs rendered side by side with a 5-second forced reading delay before the preference buttons appear.
5. **Survey** — six tap-only questions (four comparison + two profile).
6. **Thank You** — reveals the research design, including which output was robotic and which was humanized.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Web framework | Django 4.2 (no DRF for page views; DRF only for the product API) |
| LLM API | Groq (`llama-3.1-8b-instant`) — single call for the humanized output |
| Local database | SQLite (development) |
| Remote database | Supabase (PostgreSQL) — response mirroring |
| Deployment | AWS Elastic Beanstalk (Python 3.12, Amazon Linux 2023) |
| Static files | EB proxy static file mapping |
| Fonts | Cormorant Garamond + Source Sans 3 (Google Fonts) |

---

## Project Structure

```
humanizing-choice/
├── catalogo/               # Django project settings, URLs, WSGI
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── produtos/               # Main Django app
│   ├── models.py           # Catalogue, Product, SessionResponse
│   ├── views.py            # All page views + AJAX endpoints
│   ├── urls.py
│   ├── serializers.py      # DRF serializers for the product API
│   ├── recommendation.py   # Attribute-based scoring engine
│   ├── admin.py
│   ├── tests.py
│   └── migrations/
├── templates/              # Django HTML templates
│   ├── base.html
│   ├── landing.html
│   ├── select_interest.html
│   ├── catalogue.html
│   ├── recommendations.html
│   ├── survey.html
│   └── thank_you.html
├── initial_data.json       # Seed fixture: 4 catalogues, 52 products
├── requirements.txt
├── Procfile                # gunicorn --bind 127.0.0.1:8000
├── .ebextensions/
│   └── django.config       # EB container commands (collectstatic, etc.)
└── manage.py
```

---

## Data Models

### `Catalogue`
Represents one of the four interest areas. Fields: `name`, `slug`, `description`.

### `Product`
Belongs to a `Catalogue`. Fields: `name`, `description`, `price`, `image_url`, `featured`, `brand`, `item_type`, `price_tier`.

### `SessionResponse`
One row per completed survey. Fields: `session_id` (UUID), `interest_selected`, `products_selected` (JSON), `robotic_output`, `humanized_output`, `preferred_overall`, `preferred_trust`, `preferred_purchase`, `preferred_understood`, `uses_ai_shopping`, `ai_familiarity`, `timestamp`.

---

## Recommendation Engine

`produtos/recommendation.py` implements an **attribute-based scoring** function used to rank candidate products:

- **Type score** (40%) — exact item-type match or shared type-group (peripherals, audio, compute, etc.)
- **Brand score** (35%) — exact brand match
- **Price tier score** (25%) — same tier = 1.0, adjacent = 0.5, distant = 0.0

Results are aggregated across all selected products and the top candidates are injected into the LLM prompt.

---

## LLM Prompt

**Humanized prompt** — a single Groq API call instructs the model to embody "Maya", a friendly assistant, and respond using the five framework components in conversational Brazilian Portuguese (max 90 words). The ranked candidate list is included in the prompt context.

---

## Local Setup

```bash
# 1. Clone and create virtual environment
git clone https://github.com/<your-org>/humanizing-choice.git
cd humanizing-choice
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variables
export GROQ_API_KEY=your_key_here
export SUPABASE_URL=your_supabase_url
export SUPABASE_ANON_KEY=your_supabase_anon_key

# 4. Run migrations
python manage.py migrate

# 5. Load seed data
python manage.py loaddata initial_data.json

# 6. Start the development server
python manage.py runserver
```

---
---

# Humanizing Choice - Anthropomorphic AI in Recommendations

**Projeto de pesquisa acadêmica — IBMEC Rio de Janeiro, 2026**
Orientador: Prof. Rigel Fernandes

🌐 **App em produção:** [humanizing-catalogue-survey-env.eba-kg3w4fxe.us-east-1.elasticbeanstalk.com](http://humanizing-catalogue-survey-env.eba-kg3w4fxe.us-east-1.elasticbeanstalk.com/)

---

## Visão Geral

*Humanizing Choice* é uma aplicação web desenvolvida para apoiar o artigo acadêmico **"Humanizing Choice — Anthropomorphic AI in Recommendations"**. O estudo investiga como a engenharia de prompts antropomórficos influencia confiança, intenção de compra e percepção de compreensão em estudantes universitários de tecnologia.

Os participantes navegam por um catálogo de produtos, selecionam itens de interesse e, em seguida, visualizam duas recomendações geradas por IA lado a lado — uma robótica, outra humanizada — antes de responder uma pesquisa rápida. Todos os dados são coletados de forma anônima.

---

## Contribuição da Pesquisa

A principal contribuição é um **framework de humanização com cinco componentes**:

| # | Componente | Função |
|---|------------|--------|
| 1 | **Persona** (Maya) | Dá à IA uma identidade nomeada e identificável |
| 2 | **Frase de Empatia** | Reconhece o que o usuário esteve explorando |
| 3 | **Recomendação** | Sugere produtos em linguagem natural e fluida |
| 4 | **Prova Social** | Referencia usuários similares para gerar confiança |
| 5 | **Chamada à Ação** | Encerra com um convite aberto e suave |

Cada componente é fundamentado em construtos teóricos referenciados (Mariani et al. 2022, Beyari & Hashem 2025, Ribeiro et al. 2025, Srivastava & Gurme 2026, Moussawi et al. 2021, Kim et al. 2019, Kumar et al. 2025).

O experimento produz dois outputs a partir do mesmo input de produtos — **Recomendação A** (robótica, baseada em regras) e **Recomendação B** (humanizada, via uma única chamada ao LLM Groq) — e mede a preferência do usuário em quatro dimensões: preferência geral, confiança, intenção de compra e sentir-se compreendido.

---

## Fluxo do Usuário

```
Landing → Selecionar Interesse → Catálogo → Recomendações (A/B) → Pesquisa → Obrigado
```

1. **Landing** — explica o contexto da pesquisa; nenhum dado é coletado ainda.
2. **Selecionar Interesse** — quatro áreas de tecnologia (Dev, Games, Produtividade, Áudio).
3. **Catálogo** — o participante toca nos produtos que lhe interessam.
4. **Recomendações** — dois outputs renderizados lado a lado, com delay forçado de 5 segundos antes dos botões de preferência aparecerem.
5. **Pesquisa** — seis perguntas de toque (quatro comparativas + dois de perfil).
6. **Obrigado** — revela o design da pesquisa, incluindo qual output era robótico e qual era humanizado.

---

## Stack Tecnológica

| Camada | Tecnologia |
|--------|------------|
| Framework web | Django 4.2 (sem DRF para views de página; DRF apenas para a API de produtos) |
| API de LLM | Groq (`llama-3.1-8b-instant`) — chamada única para o output humanizado |
| Banco local | SQLite (desenvolvimento) |
| Banco remoto | Supabase (PostgreSQL) — espelhamento de respostas |
| Deploy | AWS Elastic Beanstalk (Python 3.12, Amazon Linux 2023) |
| Arquivos estáticos | Mapeamento via proxy do EB |
| Fontes | Cormorant Garamond + Source Sans 3 (Google Fonts) |

---

## Estrutura do Projeto

```
humanizing-choice/
├── catalogo/               # Configurações Django, URLs, WSGI
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── produtos/               # App Django principal
│   ├── models.py           # Catalogue, Product, SessionResponse
│   ├── views.py            # Todas as views de página + endpoints AJAX
│   ├── urls.py
│   ├── serializers.py      # Serializers DRF para a API de produtos
│   ├── recommendation.py   # Motor de pontuação por atributos
│   ├── admin.py
│   ├── tests.py
│   └── migrations/
├── templates/              # Templates HTML Django
│   ├── base.html
│   ├── landing.html
│   ├── select_interest.html
│   ├── catalogue.html
│   ├── recommendations.html
│   ├── survey.html
│   └── thank_you.html
├── initial_data.json       # Fixture de seed: 4 catálogos, 52 produtos
├── requirements.txt
├── Procfile                # gunicorn --bind 127.0.0.1:8000
├── .ebextensions/
│   └── django.config       # Comandos do container EB (collectstatic, etc.)
└── manage.py
```

---

## Modelos de Dados

### `Catalogue`
Representa uma das quatro áreas de interesse. Campos: `name`, `slug`, `description`.

### `Product`
Pertence a um `Catalogue`. Campos: `name`, `description`, `price`, `image_url`, `featured`, `brand`, `item_type`, `price_tier`.

### `SessionResponse`
Um registro por pesquisa concluída. Campos: `session_id` (UUID), `interest_selected`, `products_selected` (JSON), `robotic_output`, `humanized_output`, `preferred_overall`, `preferred_trust`, `preferred_purchase`, `preferred_understood`, `uses_ai_shopping`, `ai_familiarity`, `timestamp`.

---

## Motor de Recomendação

`produtos/recommendation.py` implementa uma **pontuação por atributos** usada para ranquear produtos candidatos:

- **Score de tipo** (40%) — correspondência exata de `item_type` ou grupo de tipo compartilhado (periféricos, áudio, computação, etc.)
- **Score de marca** (35%) — correspondência exata de marca
- **Score de faixa de preço** (25%) — mesma faixa = 1,0 | adjacente = 0,5 | distante = 0,0

Os resultados são agregados para todos os produtos selecionados e os melhores candidatos são injetados no prompt do LLM.

---

## Prompt do LLM

**Prompt humanizado** — uma única chamada à API do Groq instrui o modelo a incorporar "Maya", uma assistente amigável, e responder usando os cinco componentes do framework em português brasileiro conversacional (máximo 90 palavras). A lista de candidatos ranqueados é incluída no contexto do prompt.

---

## Configuração Local

```bash
# 1. Clonar e criar ambiente virtual
git clone https://github.com/<seu-org>/humanizing-choice.git
cd humanizing-choice
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Configurar variáveis de ambiente
export GROQ_API_KEY=sua_chave_aqui
export SUPABASE_URL=sua_url_supabase
export SUPABASE_ANON_KEY=sua_chave_anon_supabase

# 4. Executar migrações
python manage.py migrate

# 5. Carregar dados de seed
python manage.py loaddata initial_data.json

# 6. Iniciar o servidor de desenvolvimento
python manage.py runserver
```
