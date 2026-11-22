from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import SimpleRouter

from . import api_views

router = SimpleRouter()
router.register("profissionais", api_views.ProfissionalViewSet, basename="api-profissional")
router.register("disponibilidades", api_views.DisponibilidadeViewSet, basename="api-disponibilidade")
router.register("consultas", api_views.ConsultaViewSet, basename="api-consulta")

urlpatterns = [
    path("token/", obtain_auth_token, name="api-token"),
    path("clinicas/", api_views.MinhasClinicasView.as_view(), name="api-clinicas"),
    path("clinicas/<int:clinica_pk>/dashboard/", api_views.DashboardView.as_view(), name="api-dashboard"),
    path("clinicas/<int:clinica_pk>/", include(router.urls)),
]
