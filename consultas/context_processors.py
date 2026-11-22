from .permissoes import vinculo_ativo


def clinica_ativa(request):
    """Disponibiliza a clínica/papel ativos para todos os templates."""
    return {"vinculo_ativo": vinculo_ativo(request)}
