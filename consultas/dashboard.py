from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from .models import Consulta, Paciente, Profissional


def metricas_clinica(clinica):
    """Métricas do dashboard de uma clínica (usadas na tela e na API)."""
    hoje = timezone.localdate()
    consultas = Consulta.objects.filter(profissional__clinica=clinica)
    total = consultas.count()

    por_status = {valor: 0 for valor, _ in Consulta.STATUS_CHOICES}
    for linha in consultas.values("status").annotate(n=Count("id")):
        por_status[linha["status"]] = linha["n"]

    taxa_cancelamento = 0.0
    if total:
        taxa_cancelamento = round(por_status[Consulta.STATUS_CANCELADA] / total * 100, 1)

    agendadas = consultas.filter(status=Consulta.STATUS_AGENDADA)

    profissionais = (
        Profissional.objects.filter(clinica=clinica)
        .select_related("usuario")
        .annotate(
            n_agendadas=Count("consultas", filter=Q(consultas__status=Consulta.STATUS_AGENDADA)),
            n_realizadas=Count("consultas", filter=Q(consultas__status=Consulta.STATUS_REALIZADA)),
            n_canceladas=Count("consultas", filter=Q(consultas__status=Consulta.STATUS_CANCELADA)),
        )
        .order_by("-n_agendadas", "id")
    )

    return {
        "clinica": clinica.nome,
        "total_consultas": total,
        "consultas_hoje": agendadas.filter(data=hoje).count(),
        "proximos_7_dias": agendadas.filter(data__gte=hoje, data__lte=hoje + timedelta(days=7)).count(),
        "por_status": por_status,
        "taxa_cancelamento": taxa_cancelamento,
        "total_profissionais": profissionais.count(),
        "total_pacientes": Paciente.objects.filter(clinica=clinica).count(),
        "por_profissional": [
            {
                "profissional": str(p),
                "agendadas": p.n_agendadas,
                "realizadas": p.n_realizadas,
                "canceladas": p.n_canceladas,
            }
            for p in profissionais
        ],
    }
