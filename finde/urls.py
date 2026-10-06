"""
URL configuration for ebay project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include, reverse_lazy
from django.contrib.auth import views as auth_views
from core.views import display_search_results, capture_email, CustomPasswordResetView
from core.admin import admin_site  # Import from core.admin instead

urlpatterns = [
    path('search_results/', display_search_results, name='search_results'),
    path('admin/', admin_site.urls),  # Use our custom admin site
    path('accounts/', include('allauth.urls')),  
    path('capture-email/', capture_email, name='capture_email'),
    
    # Password reset URLs
    path('password-reset/', CustomPasswordResetView.as_view(
        html_email_template_name='registration/password_reset_email.html'
    ), name='password_reset'),


    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='account/password_reset_done.html'
    ), name='password_reset_done'),

    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='account/password_reset_confirm.html',
        success_url=reverse_lazy('password_reset_complete')
    ), name='password_reset_confirm'),

    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='account/password_reset_complete.html'
    ), name='password_reset_complete'),

    # Core URLs MUST come after specific patterns to avoid the <str:username>/ pattern catching everything
    path('', include('core.urls')),
]