from django.db import models
import uuid


class Catalogue(models.Model):

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Product(models.Model):
    catalogue = models.ForeignKey(
        Catalogue,
        on_delete=models.CASCADE,
        related_name='products'
    )
    name = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField(max_length=500)
    description_en = models.TextField(max_length=500, blank=True, default='')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.URLField(blank=True, null=True)
    featured = models.BooleanField(default=False)
    brand = models.CharField(max_length=50, blank=True, default='')
    item_type = models.CharField(max_length=50, blank=True, default='')
    price_tier = models.CharField(max_length=20, blank=True, default='')

    def __str__(self):
        return f"{self.name} ({self.catalogue.name})"

    class Meta:
        ordering = ['-featured', 'name']


class SessionResponse(models.Model):

    AI_FAMILIARITY_CHOICES = [
        ('nenhuma',  'Nenhuma'),
        ('pouca',    'Pouca'),
        ('moderada', 'Moderada'),
        ('alta',     'Alta'),
    ]

    USES_AI_CHOICES = [
        ('sim',        'Sim'),
        ('nao',        'Não'),
        ('as_vezes',   'Às vezes'),
    ]

    AB_CHOICES = [
        ('A', 'Recomendação Robótica'),
        ('B', 'Recomendação Humanizada'),
    ]

    session_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    interest_selected = models.CharField(max_length=100)
    products_selected = models.JSONField()

    robotic_output   = models.TextField()
    humanized_output = models.TextField()

    preferred_overall    = models.CharField(max_length=1, choices=AB_CHOICES)
    preferred_trust      = models.CharField(max_length=1, choices=AB_CHOICES)
    preferred_purchase   = models.CharField(max_length=1, choices=AB_CHOICES)
    preferred_understood = models.CharField(max_length=1, choices=AB_CHOICES)
    uses_ai_shopping     = models.CharField(max_length=20, choices=USES_AI_CHOICES)
    ai_familiarity       = models.CharField(max_length=20, choices=AI_FAMILIARITY_CHOICES)
    participant_email    = models.EmailField(blank=True, default='')

    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Session {self.session_id} — {self.interest_selected} — {self.timestamp:%Y-%m-%d %H:%M}"

    class Meta:
        ordering = ['-timestamp']