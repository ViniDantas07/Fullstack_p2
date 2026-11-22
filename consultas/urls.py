from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    # clínicas
    path("clinicas/", views.selecionar_clinica, name="selecionar_clinica"),
    path("clinicas/nova/", views.clinica_create, name="clinica_create"),
    path("clinicas/<int:clinica_pk>/entrar/", views.entrar_clinica, name="entrar_clinica"),
    path("clinicas/<int:clinica_pk>/ingressar/", views.clinica_ingressar, name="clinica_ingressar"),
    # gestão
    path("dashboard/", views.dashboard, name="dashboard"),
    path("agenda/", views.consulta_list, name="consulta_list"),
    path("equipe/", views.equipe, name="equipe"),
    path("equipe/<int:pk>/remover/", views.membro_remover, name="membro_remover"),
    # profissional
    path("disponibilidades/nova/", views.disponibilidade_create, name="disponibilidade_create"),
    path("disponibilidades/<int:pk>/excluir/", views.disponibilidade_delete, name="disponibilidade_delete"),
    # consultas
    path("profissionais/", views.profissional_list, name="profissional_list"),
    path("profissionais/<int:profissional_pk>/agendar/", views.consulta_create, name="consulta_create"),
    path("consultas/<int:pk>/cancelar/", views.consulta_cancelar, name="consulta_cancelar"),
    path("consultas/<int:pk>/realizar/", views.consulta_realizar, name="consulta_realizar"),
]
