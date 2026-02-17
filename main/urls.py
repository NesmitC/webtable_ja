# main/urls.py
from django.urls import path
from django.contrib import admin
from . import views
from django.contrib.auth import views as auth_views


urlpatterns = [
    # Главная страница
    path('', views.index, name='index'),
    # Админка
    path('admin/', admin.site.urls),  # ← ЭТА СТРОКА ОБЯЗАТЕЛЬНА!
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
    path('planning/8/', views.planning_8kl, name='planning_8kl'),
    path('ege/', views.ege, name='ege'),
    path('diagnostic/starting/', views.starting_diagnostic, name='starting_diagnostic'),
    path('targetn/', views.targetn, name='targetn'),
    path('save-example/', views.save_example, name='save_example'),
    path('load-examples/', views.load_examples, name='load_examples'),
    path('api/check-exercise/', views.check_exercise, name='check_exercise'),
    path('api/assistant/', views.get_assistant_data, name='assistant'),
    path('api/orthogram/<str:orth_id>/letters/', views.get_orthogram_letters, name='orthogram_letters'),
    path('api/get-advice/', views.get_advice, name='get_advice'),
    path('api/daily-quiz/', views.get_daily_quiz, name='daily_quiz'),
    path('telegram-link/', views.telegram_link, name='telegram_link'),
    path('api/generate-exercise/', views.generate_exercise, name='generate_exercise'),
    path('api/weekly-report/', views.weekly_report, name='weekly_report'),
    path('api/generate-alphabetical-exercise/', views.generate_alphabetical_exercise, name='generate_alphabetical_exercise'),
    path('api/my-weekly-report/', views.get_weekly_report, name='my_weekly_report'),
    path('api/generate-exercise-multi/', views.generate_exercise_multi, name='generate_exercise_multi'),
    path('api/generate-punktum-exercise-multi/', views.generate_punktum_exercise_multi, name='generate_punktum_exercise_multi'),
    path('api/generate-text-analysis/', views.generate_text_analysis, name='generate_text_analysis'),
    path('api/check-text-analysis/', views.check_text_analysis, name='check_text_analysis'),
    path('api/generate-text-analysis-23-24/', views.generate_text_analysis_23_24, name='generate_text_analysis_23_24'),
    path('api/check-text-analysis-23-24/', views.check_text_analysis_23_24, name='check_text_analysis_23_24'),
    path('api/generate-orthoepy-test/', views.generate_orthoepy_test, name='generate_orthoepy_test'),
    path('api/check-orthoepy-test/', views.check_orthoepy_test, name='check_orthoepy_test'),
    path('api/generate-correction-test/', views.generate_correction_test_view, name='generate_correction_test'),
    path('api/check-correction/', views.check_correction_view, name='check_correction'),
    path('api/generate-task-eight-test/', views.generate_task_eight_test_view, name='generate_task_eight_test'),
    path('api/check-task-eight-test/', views.check_task_eight_test, name='check_task_eight_test'),
    path('api/generate-task-twotwo-test/', views.generate_task_twotwo_test_view, name='generate_task_twotwo_test'),
    path('api/check-task-twotwo-test/', views.check_task_twotwo_test, name='check_task_twotwo_test'),
    path('api/generate-task-paponim-test/', views.generate_task_paponim_test_view, name='generate_task_paponim_test'),
    path('api/check-task-paponim-test/', views.check_task_paponim_test_view, name='check_task_paponim_test'),
    path('api/generate-task-wordok-test/', views.generate_task_wordok_test_view, name='generate_task_wordok_test'),
    path('api/check-task-wordok-test/', views.check_task_wordok_test_view, name='check_task_wordok_test'),
    path('api/generate-text-analysis-23-26/', views.generate_text_analysis_23_26, name='generate_text_analysis_23_26'),
    path('api/check-text-analysis-23-26/', views.check_text_analysis_23_26, name='check_text_analysis_23_26'),
    path('api/generate-starting-diagnostic/', views.generate_starting_diagnostic, name='generate_starting_diagnostic'),
    path('api/check-starting-diagnostic/', views.check_starting_diagnostic, name='check_starting_diagnostic'),
    path('api/check-alphabetical-exercise/', views.check_alphabetical_exercise, name='check_alphabetical_exercise'),
    path('api/generate-task9-exercise/', views.generate_task9_exercise, name='generate_task9_exercise'),
    path('api/generate-chered-exercise/', views.generate_chered_exercise, name='generate_chered_exercise'),
]
