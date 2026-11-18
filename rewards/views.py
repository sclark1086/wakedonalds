from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import RewardOption, RewardsSettings
from .serializers import RewardOptionSerializer, RewardsProgramSerializer


@api_view(["GET"])
@permission_classes([AllowAny])
def rewards_program(request):
    """
    The current rewards rules and the rewards customers can choose from.

    Public so the menu, checkout, and account pages can show how points
    work. Admins change everything here in /admin/ (Rewards program).
    """
    settings = RewardsSettings.load()
    data = RewardsProgramSerializer(settings).data
    if settings.program_enabled:
        options = RewardOption.objects.filter(active=True).select_related("product")
        data["rewards"] = RewardOptionSerializer(options, many=True).data
    else:
        data["rewards"] = []
    return Response(data)
