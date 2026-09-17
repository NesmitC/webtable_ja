# main/urls.py
from django.urls import path
from django.contrib import admin
from django.views.generic.base import RedirectView
from . import views
from django.contrib.auth import views as auth_views
from django.contrib.admin.views.decorators import staff_member_required
from .forms import CustomUserCreationForm, CustomAuthenticationForm, ProfileForm



urlpatterns = [
    # Главная страница
    path('', views.index, name='index'),

    # === Аутентификация ===
    path('accounts/login/', views.EmailLoginView.as_view(), name='login'),
    path('accounts/logout/', views.custom_logout, name='logout'),
    path('accounts/register/', views.register, name='register'),
    # Страницы-цели Яндекс.Метрики. Отдельные URL нужны потому, что успешный
    # POST регистрации идёт на тот же /accounts/register/, а активация
    # редиректила на '/' — Метрика не могла отличить конверсию от визита.
    path('accounts/register/done/', views.register_done, name='register_done'),
    path('accounts/activated/', views.account_activated, name='account_activated'),
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
    path('planning/9/', views.planning_9kl, name='planning_9kl'),
    path('ege/', views.ege, name='ege'),
    path('oge/', views.oge, name='oge'),
    path('diagnostic/starting_oge/', views.starting_diagnostic_oge, name='starting_diagnostic_oge'),
    path('test-fix-ege/<str:test_code>/', views.test_fix_ege, name='test_fix_ege'),
    path('test-fixdemo-ege/<str:test_code>/', views.test_fixdemo_ege, name='test_fixdemo_ege'),
    path('targetn/', views.targetn, name='targetn'),
    path('api/check-exercise/', views.check_exercise, name='check_exercise'),
    path('api/orthogram/<str:orth_id>/letters/', views.get_orthogram_letters, name='orthogram_letters'),
    path('api/generate-exercise/', views.generate_exercise, name='generate_exercise'),
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
    path('orthoepy_trening/', views.orthoepy_trening, name='orthoepy_trening'),
    path('api/save-example/', views.save_example, name='save_example'),
    path('api/load-examples/', views.load_examples, name='load_examples'),
    path('api/update-example/', views.update_example, name='update_example'),
    path('api/delete-example/', views.delete_example, name='delete_example'),
    path('api/user-progress/', views.user_progress, name='user_progress'),
    path('api/weak-words/', views.user_weak_words, name='weak_words'),
    path('api/user-praise/', views.user_praise, name='user_praise'),
    path('api/get-orthoepy-pair/', views.get_orthoepy_pair, name='get_orthoepy_pair'),
    path('api/get-word-by-id/', views.get_word_by_id, name='get_word_by_id'),
    path('api/get-words-by-ids/', views.get_words_by_ids, name='get_words_by_ids'),
    path('statistic/', views.statistic, name='statistic'),
    path('paponim_trening/', views.paponim_trening, name='paponim_trening'),
    path('api/orthoepy-trening/check/', views.check_orthoepy_trening, name='check_orthoepy_trening_save'),
    path('api/track-lesson/', views.track_lesson_view, name='track_lesson_view'),
    path('api/track-paponim/', views.track_paponim_view, name='track_paponim_view'),

    path('api/vk/status/', views.vk_status),
    path('api/vk/generate-code/', views.vk_generate_code),
    path('api/health/', views.vk_health),
    path('api/site-daily-word/', views.site_daily_word, name='site_daily_word'),
    path('api/site-daily-answer/', views.site_daily_answer, name='site_daily_answer'),

    # === API для САЙТА (требуют авторизации) ===
    path('api/get-quiz/', views.get_quiz, name='get_quiz'),
    path('api/get-quiz-orthoepy-pair/', views.get_quiz_orthoepy_pair, name='get_quiz_orthoepy_pair'),
    path('api/log-quiz-answer-site/', views.log_quiz_answer_site, name='log_quiz_answer_site'),
    path('api/get-planning-quiz/', views.get_planning_quiz, name='get_planning_quiz'),
    path('api/quiz/hot-word/', views.get_hot_word_quiz, name='hot_word_quiz'),
    path('api/quiz/<str:quiz_type>/snippet/', views.quiz_snippet_api, name='quiz_snippet_api'),
    path('api/user-stats/', views.get_user_quiz_stats_site, name='user_stats_site'),
    path('api/stats-progress/', views.stats_progress_api, name='stats_progress_api'),

    # === Привязка ботов (сайт) ===
    path('vk/link/', views.vk_create_link, name='vk_create_link'),
    path('vk/unlink/', views.vk_unlink, name='vk_unlink'),
    path('max/link/', views.max_create_link, name='max_create_link'),
    path('max/unlink/', views.max_unlink, name='max_unlink'),

    # === Админка ===
    path('admin/planning-check/', views.admin_planning_check, name='admin_planning_check'),

    # === Подстраницы ЕГЭ ===
    path('ege/diagnostics/', views.diagnostics, name='diagnostics_ege'),
    path('ege/demo/', views.demo_ege, name='demo_ege'),
    path('ege/trainers/', views.trainers_ege, name='trainers_ege'),
    path('ege/quizzes/', views.quizzes_ege, name='quizzes_ege'),
    path('ege/lessons/', views.lessons_ege, name='lessons_ege'),
    path('ege/checkpoint/9/', views.checkpoint_test, name='checkpoint_test'),
    path('ege/checkpoint/9/result/<int:attempt_id>/', views.checkpoint_result,
         name='checkpoint_result'),

    # Входящая диагностика ЕГЭ (фиксированный вариант из фикстуры)
    path('diagnostic/fix-ege/', views.diagnostic_fix_ege, name='diagnostic_fix_ege'),
    path('diagnostic/result/<uuid:attempt_id>/', views.diagnostic_result, name='diagnostic_result',),
    path('api/callback-request/', views.callback_request, name='callback_request'),
    path('my/diagnostic/<uuid:attempt_id>/', views.student_review, name='student_review'),

    # Диагностики (универсальный маршрут)
    path('diagnostic/<str:diagnostic_type>/', views.diagnostic_starting, name='diagnostic_starting'),
    path('diagnostic/test/<str:diagnostic_type>/', views.start_diagnostic_test, name='start_diagnostic_test'),

    # ОГЭ
    path('diagnostic/oge/', views.oge_diagnostic_page, name='oge_diagnostic'),
    path('api/generate-oge-diagnostic/', views.generate_oge_diagnostic, name='generate_oge_diagnostic'),
    path('api/generate-oge-single-task/', views.generate_oge_single_task, name='generate_oge_single_task'),
    path('api/check-oge-diagnostic/', views.check_oge_diagnostic, name='check_oge_diagnostic'),
    
    # чат-бот
    path('api/chat/proactive/', views.chat_proactive, name='chat_proactive'),
    path('api/chat/', views.chat_api, name='chat_api'),
    path('api/chat-feedback/', views.chat_feedback, name='chat_feedback'),  # ✅ Должна быть
    path('api/assistant/', views.chat_api, name='assistant'),  # ✅ Или эта
    
    # Аналитика для преподавателя / админа
    path('tutor/activate/', views.activate_tutor_code, name='activate_tutor_code'),
    path('staff/diagnostics/', views.diagnostic_list, name='diagnostic_list'),
    path('staff/diagnostic/<uuid:attempt_id>/', views.diagnostic_review, name='diagnostic_review'),


    # оплата, вебхук, активация
    path('pay/buy/<str:plan_code>/', views.buy_plan, name='buy_plan'),
    path('pay/success/', views.pay_success, name='pay_success'),
    path('pay/fail/', views.pay_fail, name='pay_fail'),
    path('api/payments/yookassa/webhook/', views.yookassa_webhook, name='yookassa_webhook'),

    # Скачивание справочных материалов
    path('download/orthoepy-dict/', views.download_reference_file, 
         {'file_type': 'orthoepy-dict'}, name='download_orthoepy_dict'),
    
    path('download/paronyms-dict/', views.download_reference_file, 
         {'file_type': 'paronyms-dict'}, name='download_paronyms_dict'),
    
    # Фавиконка: браузер сам запрашивает /favicon.ico на каждой странице —
    # перенаправляем на наш SVG в статике (работает во всех шаблонах сразу)
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.svg', permanent=True)),
    # Политика обработки персональных данных
    path('privacy/', views.privacy, name='privacy'),
    path('terms/', views.terms, name='terms'),

    path('admin/', admin.site.urls),  # Django admin (должен быть в конце)
]
