# apps/core/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import connection
import logging

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def health_check(request):
    """
    Health check endpoint for load balancers and monitoring.
    """
    health_status = {
        'status': 'healthy',
        'services': {}
    }
    
    # Check database connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_status['services']['database'] = 'healthy'
    except Exception as e:
        health_status['services']['database'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    status_code = 200 if health_status['status'] == 'healthy' else 503
    return JsonResponse(health_status, status=status_code)


def custom_404(request, exception):
    """Custom 404 error handler."""
    return JsonResponse({
        'error': 'Not Found',
        'message': 'The requested resource was not found.',
        'status_code': 404
    }, status=404)


def custom_500(request):
    """Custom 500 error handler."""
    return JsonResponse({
        'error': 'Internal Server Error',
        'message': 'An internal server error occurred.',
        'status_code': 500
    }, status=500)

