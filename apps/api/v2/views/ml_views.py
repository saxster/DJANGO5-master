"""API v2 ML Views."""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.ml.services.conflict_predictor import conflict_predictor


class ConflictPredictionView(APIView):
    """ML-powered conflict prediction."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Predict conflict probability."""
        prediction = conflict_predictor.predict_conflict(request.data)

        return Response(prediction)