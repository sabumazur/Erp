from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


def health(request):
    return HttpResponse("ok")


urlpatterns = [
    path("health/", health),
    path("admin/", admin.site.urls),
    path("auth/", include("allauth.urls")),
    path("", include("apps.accounts.urls", namespace="accounts")),
    path("items/", include("apps.items.urls", namespace="items")),
    path("", include("apps.invoices.urls", namespace="invoices")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
