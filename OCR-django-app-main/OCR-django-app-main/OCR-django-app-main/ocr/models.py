# models.py

from django.db import models

class ExtractedText(models.Model):
    text = models.TextField()
    date_created = models.DateTimeField(auto_now_add=True)
