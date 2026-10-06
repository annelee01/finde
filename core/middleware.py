from django.utils.deprecation import MiddlewareMixin

class CacheControlMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if response.status_code == 200 and request.path.startswith('/media/'):
            response['Cache-Control'] = 'max-age=86400'  # Cache for one day
        return response