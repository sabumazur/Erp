from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve


def health(request):
    return HttpResponse("ok")


urlpatterns = [
    path("health/", health),
    path("admin/", admin.site.urls),
    path("auth/", include("allauth.urls")),
    path("", include("apps.accounts.urls", namespace="accounts")),
    path("items/", include("apps.items.urls", namespace="items")),
    path("core/",  include("apps.core.urls",  namespace="core")),
    path("", include("apps.sales.urls", namespace="sales")),
    path("", include("apps.purchases.urls", namespace="purchases")),
]

# Serve user-uploaded media files in all environments.
# static() returns [] when DEBUG=False in Django 6+, so we register directly.
# For local production this is acceptable; replace with a dedicated nginx
# location block if the deployment grows beyond a few concurrent users.
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]
