from django.contrib import admin

from apps.accounts.admin import secure_admin_site

from .models import Block, Favorite, HelpfulVote, Report, Review, Suspension

for model in (Block, Favorite, HelpfulVote, Report, Review, Suspension):
    secure_admin_site.register(model)
