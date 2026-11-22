from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from consultas import views as consultas_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("consultas.api_urls")),
    path("login/", auth_views.LoginView.as_view(template_name="consultas/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("cadastro/", consultas_views.cadastro, name="cadastro"),
    path("", include("consultas.urls")),
]
