from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_serializers import ConsultaSerializer, DisponibilidadeSerializer, ProfissionalSerializer
from .dashboard import metricas_clinica
from .models import Consulta, Disponibilidade, Paciente, Profissional, Vinculo
from .permissoes import PAPEIS_GESTAO, pode_gerir_consulta, pode_realizar_consulta


class ClinicaMixin:
    """
    Todas as rotas ficam sob /api/clinicas/<clinica_pk>/...
    O mixin descobre o papel do usuário naquela clínica e restringe as ações.

    papeis_padrao: papéis aceitos quando a ação não está em papeis_por_acao
                   (None = qualquer membro da clínica).
    """

    papeis_padrao = None
    papeis_por_acao = {}

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)  # autenticação + IsAuthenticated
        vinculo = (
            Vinculo.objects.select_related("clinica")
            .filter(usuario=request.user, clinica_id=kwargs["clinica_pk"])
            .first()
        )
        if vinculo is None:
            raise PermissionDenied("Você não faz parte desta clínica.")

        self.vinculo = vinculo
        self.clinica = vinculo.clinica
        self.papel = vinculo.papel

        nome_acao = getattr(self, "action", None)
        permitidos = self.papeis_por_acao.get(nome_acao, self.papeis_padrao)
        if permitidos is not None and self.papel not in permitidos:
            raise PermissionDenied("Seu papel nesta clínica não permite esta ação.")

    def get_serializer_context(self):
        contexto = super().get_serializer_context()
        contexto.update({"clinica": self.clinica, "papel": self.papel})
        if self.papel == Vinculo.PROFISSIONAL:
            contexto["profissional_proprio"] = get_object_or_404(
                Profissional, usuario=self.request.user, clinica=self.clinica
            )
        if self.papel == Vinculo.PACIENTE:
            contexto["paciente_proprio"] = get_object_or_404(
                Paciente, usuario=self.request.user, clinica=self.clinica
            )
        return contexto


class MinhasClinicasView(APIView):
    """GET /api/clinicas/ — clínicas do usuário e o papel dele em cada uma."""

    def get(self, request):
        vinculos = Vinculo.objects.filter(usuario=request.user).select_related("clinica")
        return Response(
            [
                {"id": v.clinica_id, "nome": v.clinica.nome, "papel": v.papel}
                for v in vinculos
            ]
        )


class ProfissionalViewSet(ClinicaMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ProfissionalSerializer

    def get_queryset(self):
        return Profissional.objects.filter(clinica=self.clinica).select_related("usuario")


class DisponibilidadeViewSet(ClinicaMixin, viewsets.ModelViewSet):
    serializer_class = DisponibilidadeSerializer
    papeis_por_acao = {
        "create": (Vinculo.PROFISSIONAL, Vinculo.ADMIN),
        "update": (Vinculo.PROFISSIONAL, Vinculo.ADMIN),
        "partial_update": (Vinculo.PROFISSIONAL, Vinculo.ADMIN),
        "destroy": (Vinculo.PROFISSIONAL, Vinculo.ADMIN),
    }

    def get_queryset(self):
        queryset = Disponibilidade.objects.filter(profissional__clinica=self.clinica)
        escrita = self.action not in ("list", "retrieve")
        if escrita and self.papel == Vinculo.PROFISSIONAL:
            queryset = queryset.filter(profissional__usuario=self.request.user)
        profissional = self.request.query_params.get("profissional")
        if profissional and profissional.isdigit():
            queryset = queryset.filter(profissional_id=profissional)
        return queryset


class ConsultaViewSet(
    ClinicaMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ConsultaSerializer
    papeis_por_acao = {
        "create": (Vinculo.PACIENTE, Vinculo.RECEPCAO, Vinculo.ADMIN),
        "realizar": (Vinculo.PROFISSIONAL, Vinculo.ADMIN),
    }

    def get_queryset(self):
        queryset = Consulta.objects.filter(profissional__clinica=self.clinica).select_related(
            "paciente__usuario", "profissional__usuario"
        )
        # cada papel enxerga apenas o que lhe diz respeito
        if self.papel == Vinculo.PROFISSIONAL:
            queryset = queryset.filter(profissional__usuario=self.request.user)
        elif self.papel == Vinculo.PACIENTE:
            queryset = queryset.filter(paciente__usuario=self.request.user)

        params = self.request.query_params
        if params.get("status") in dict(Consulta.STATUS_CHOICES):
            queryset = queryset.filter(status=params["status"])
        if params.get("data"):
            queryset = queryset.filter(data=params["data"])
        if params.get("profissional", "").isdigit():
            queryset = queryset.filter(profissional_id=params["profissional"])
        return queryset

    @action(detail=True, methods=["post"])
    def cancelar(self, request, clinica_pk=None, pk=None):
        consulta = self.get_object()
        if not pode_gerir_consulta(self.papel, request.user, consulta):
            raise PermissionDenied("Você não pode cancelar esta consulta.")
        if consulta.status != Consulta.STATUS_AGENDADA:
            return Response(
                {"detail": "Só é possível cancelar consultas agendadas."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        consulta.cancelar()
        return Response(self.get_serializer(consulta).data)

    @action(detail=True, methods=["post"])
    def realizar(self, request, clinica_pk=None, pk=None):
        consulta = self.get_object()
        if not pode_realizar_consulta(self.papel, request.user, consulta):
            raise PermissionDenied("Você não pode marcar esta consulta como realizada.")
        if consulta.status != Consulta.STATUS_AGENDADA:
            return Response(
                {"detail": "Só consultas agendadas podem ser marcadas como realizadas."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        consulta.marcar_realizada()
        return Response(self.get_serializer(consulta).data)


class DashboardView(ClinicaMixin, APIView):
    """GET /api/clinicas/<id>/dashboard/ — apenas administração e recepção."""

    papeis_padrao = PAPEIS_GESTAO

    def get(self, request, clinica_pk=None):
        return Response(metricas_clinica(self.clinica))
