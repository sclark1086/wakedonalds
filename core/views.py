from django.db import connection
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(['GET'])
def health_check(request):
    """
    Basic health-check endpoint for the Wakedonalds backend.

    Intended to be used by:
    - AWS Elastic Beanstalk's health monitoring (once deployed)
    - The team, to confirm the API + database connection are alive
    - The mobile app / frontend, as a quick "is the backend up" ping

    Returns database connectivity status so we know early if the
    cloud DB config is broken, rather than finding out from a
    confusing 500 error somewhere else in the app.
    """
    db_status = "unknown"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    return Response({
        "status": "ok",
        "service": "wakedonalds-backend",
        "database": db_status,
    })
