from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from routeplanner.services.route_planner import RoutePlanner
from routeplanner.serializers import RouteParametersSerializer


class RouteAPIView(APIView):
    """
    API View to plan a route between two geographical points,
    identify optimal fuel stops, and estimate fuel cost.
    Expects 'start' and 'end' query parameters as 'longitude,latitude' strings.
    """
    def get(self, request):
        serializer = RouteParametersSerializer(data=request.query_params)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        start_coords = validated_data['start']
        end_coords = validated_data['end']

        try:
            planner = RoutePlanner(start_coords, end_coords)
            result = planner.plan()
            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

