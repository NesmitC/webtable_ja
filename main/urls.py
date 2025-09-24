# main/urls.py
from django.urls import path
from django.contrib import admin
from . import views
from django.contrib.auth import views as auth_views


urlpatterns = [
    # Главная страница
    path('', views.index, name='index'),
    # Админка
    path('admin/', admin.site.urls),
    path(
        'accounts/login/',
        auth_views.LoginView.as_view(template_name='registration/login.html'),
        name='login',
    ),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/register/', views.register, name='register'),
    path(
        'accounts/confirm/<uidb64>/<token>/',
        views.confirm_email,
        name='confirm_email',
    ),
    path('profile/', views.profile, name='profile'),
    path('planning/5/', views.planning_5kl, name='planning_5kl'),
    path('planning/6/', views.planning_6kl, name='planning_6kl'),
    path('planning/7/', views.planning_7kl, name='planning_7kl'),
    path('save-example/', views.save_example, name='save_example'),
    path('load-examples/', views.load_examples, name='load_examples'),
    path('api/check-answers/', views.check_answers, name='check_answers'),
]
