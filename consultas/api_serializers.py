from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Consulta, Disponibilidade, Paciente, Profissional, Vinculo, nome_usuario


class ProfissionalSerializer(serializers.ModelSerializer):
    nome = serializers.SerializerMethodField()

    class Meta:
        model = Profissional
        fields = ["id", "nome", "especialidade"]

    def get_nome(self, obj):
        return nome_usuario(obj.usuario)


class DisponibilidadeSerializer(serializers.ModelSerializer):
    profissional = serializers.PrimaryKeyRelatedField(
        queryset=Profissional.objects.all(), required=False
    )

    class Meta:
        model = Disponibilidade
        fields = ["id", "profissional", "data", "hora_inicio", "hora_fim"]

    def validate(self, attrs):
        ctx = self.context
        if ctx["papel"] == Vinculo.PROFISSIONAL:
            # profissional só cadastra a própria disponibilidade
            attrs["profissional"] = ctx["profissional_proprio"]
        else:
            profissional = attrs.get("profissional") or getattr(self.instance, "profissional", None)
            if profissional is None:
                raise serializers.ValidationError({"profissional": "Informe o profissional."})
            if profissional.clinica_id != ctx["clinica"].id:
                raise serializers.ValidationError({"profissional": "Profissional não pertence a esta clínica."})
            attrs["profissional"] = profissional

        hora_inicio = attrs.get("hora_inicio", getattr(self.instance, "hora_inicio", None))
        hora_fim = attrs.get("hora_fim", getattr(self.instance, "hora_fim", None))
        try:
            Disponibilidade(
                profissional=attrs["profissional"], hora_inicio=hora_inicio, hora_fim=hora_fim
            ).clean()
        except DjangoValidationError as erro:
            raise serializers.ValidationError(erro.messages)
        return attrs


class ConsultaSerializer(serializers.ModelSerializer):
    profissional = serializers.PrimaryKeyRelatedField(queryset=Profissional.objects.all())
    paciente = serializers.PrimaryKeyRelatedField(queryset=Paciente.objects.all(), required=False)
    profissional_nome = serializers.SerializerMethodField()
    paciente_nome = serializers.SerializerMethodField()

    class Meta:
        model = Consulta
        fields = [
            "id", "profissional", "profissional_nome", "paciente", "paciente_nome",
            "data", "hora_inicio", "hora_fim", "observacoes", "status",
        ]
        read_only_fields = ["status"]

    def get_profissional_nome(self, obj):
        return nome_usuario(obj.profissional.usuario)

    def get_paciente_nome(self, obj):
        return nome_usuario(obj.paciente.usuario)

    def validate(self, attrs):
        ctx = self.context
        clinica = ctx["clinica"]

        profissional = attrs["profissional"]
        if profissional.clinica_id != clinica.id:
            raise serializers.ValidationError({"profissional": "Profissional não pertence a esta clínica."})

        if ctx["papel"] == Vinculo.PACIENTE:
            # paciente só marca consulta para si mesmo
            attrs["paciente"] = ctx["paciente_proprio"]
        else:
            paciente = attrs.get("paciente")
            if paciente is None:
                raise serializers.ValidationError({"paciente": "Informe o paciente."})
            if paciente.clinica_id != clinica.id:
                raise serializers.ValidationError({"paciente": "Paciente não pertence a esta clínica."})

        # reaproveita a regra de negócio do modelo (disponibilidade real + conflito)
        try:
            Consulta(**attrs).clean()
        except DjangoValidationError as erro:
            raise serializers.ValidationError(erro.messages)
        return attrs
