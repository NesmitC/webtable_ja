import logging
import threading
from zoneinfo import ZoneInfo
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from .models import DiagnosticAttempt, UserWord

log = logging.getLogger(__name__)

@receiver(post_save, sender=UserWord)
def notify_incomplete_planning_word(sender, instance, created, **kwargs):
    """
    Отправляет письмо, если:
    1. Создано НОВОЕ слово в планинге (created=True)
    2. У слова есть эталон (reference_word), НО он не готов к квизу
    """
    # 🔹 Уведомляем только при создании, чтобы не спамить при каждом сохранении
    if not created:
        return

    ref = instance.reference_word
    
    # 🔹 Если нет эталона — это отдельный кейс (админ увидит в отчёте)
    if not ref:
        return

    # 🔹 Проверяем, готово ли слово к квизу
    has_exp = bool(ref.explanation and ref.explanation.strip())
    has_inc = bool(ref.incorrect_variant and ref.incorrect_variant.strip())
    
    # 🔹 Если всё заполнено и активно — письмо НЕ нужно (по ТЗ)
    if ref.is_active and has_exp and has_inc:
        return

    # 🔹 Собираем список проблем
    missing = []
    if not has_exp:
        missing.append("отсутствует правило (explanation)")
    if not has_inc:
        missing.append("нет ошибочного варианта (incorrect_variant)")
    if not ref.is_active:
        missing.append("эталон отключён (is_active=False)")

    # 🔹 Формируем письмо
    subject = f"⚠️ Новое слово в планинге: '{instance.text}' не готово к квизу"
    
    edit_link = f"{settings.SITE_URL}/admin/main/orthogramexample/{ref.id}/change/"
    
    message = (
        f"Пользователь добавил слово в планинг, но эталон требует доработки.\n\n"
        f"📝 Слово: {instance.text}\n"
        f"👤 Пользователь: {instance.user.username} (ID: {instance.user_id})\n"
        f"🔗 Эталон: #{ref.id}\n\n"
        f"❌ Не заполнено:\n" + "\n".join(f"   • {m}" for m in missing) + "\n\n"
        f"✏️ Исправить в админке: {edit_link}\n\n"
        f"📊 Все слова, требующие внимания: {settings.SITE_URL}/admin/planning-check/"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.OWNER_NOTIFY_EMAIL],
            fail_silently=True,  # Не ломать сохранение, если почта упала
        )
        log.info(f"✅ Email отправлен для слова '{instance.text}' (UserWord #{instance.id})")
    except Exception as e:
        log.error(f"❌ Ошибка отправки email для '{instance.text}': {e}")


@receiver(post_save, sender=get_user_model())
def notify_new_user_registration(sender, instance, created, **kwargs):
    """Письмо владельцу о каждой новой регистрации на платформе."""
    if not created:
        return

    try:
        total = get_user_model().objects.count()
        subject = f"🎈 Новый пользователь: {instance.username}"
        message = (
            f"Новая регистрация на платформе.\n\n"
            f"👤 Ник: {instance.username}\n"
            f"📧 Email: {instance.email or '—'}\n"
            f"🕒 Дата: {instance.date_joined:%d.%m.%Y %H:%M} UTC\n"
            f"👥 Всего пользователей теперь: {total}\n\n"
            f"🔗 Карточка в админке: {settings.SITE_URL}/admin/auth/user/{instance.id}/change/"
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.OWNER_NOTIFY_EMAIL],
            fail_silently=True,
        )
    except Exception as e:
        log.error(f"❌ Ошибка письма о регистрации: {e}")


# ========== УВЕДОМЛЕНИЕ ВЛАДЕЛЬЦА О ПРОЙДЕННОЙ ДИАГНОСТИКЕ ==================
MSK = ZoneInfo('Europe/Moscow')  # TIME_ZONE в настройках — UTC, а в письме нужно МСК

# diagnostic_type -> название в винительном падеже для фразы «прошёл ... диагностику»
DIAG_TYPE_ACCUSATIVE = {
    'starting': 'входящую',
    'current': 'промежуточную',
    'final': 'итоговую',
}


def _send_owner_mail(subject: str, message: str) -> None:
    """Отправляет письмо владельцу. Работает в фоновом потоке."""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.OWNER_NOTIFY_EMAIL],
            fail_silently=False,
        )
        log.info("✅ Письмо о пройденной диагностике отправлено владельцу")
    except Exception as e:  # noqa: BLE001
        log.error(f"❌ Не удалось отправить письмо о диагностике: {e}")


@receiver(post_save, sender=DiagnosticAttempt)
def notify_owner_about_completed_diagnostic(
    sender: type[DiagnosticAttempt],
    instance: DiagnosticAttempt,
    created: bool,
    **kwargs,
) -> None:
    """
    Письмо владельцу о каждой завершённой диагностике — анонимной и авторизованной.

    Попытка создаётся сразу с is_completed=True (views.check_exercise), поэтому
    срабатываем только на created: повторные save() не должны дублировать письмо.
    """
    if not created or not instance.is_completed:
        return

    # Данные собираем в основном потоке: соединения с БД между потоками не
    # разделяются, а SMTP-ответ может занять секунды и задержать вывод
    # результата ученику. В поток передаём только готовые строки.
    if instance.user_id:
        owner = instance.user
        who_short = f"Пользователь {owner.username}"
        who = (
            "👤 Зарегистрированный пользователь\n"
            f"   Логин: {owner.username}\n"
            f"   E-mail: {owner.email or '—'}"
        )
    else:
        who_short = "Незарегистрированный пользователь"
        who = (
            "👤 Незарегистрированный пользователь (аноним)\n"
            f"   Код доступа к результату: {instance.access_code or '—'}"
        )

    when = timezone.localtime(instance.created_at, MSK)
    diag_acc = DIAG_TYPE_ACCUSATIVE.get(instance.diagnostic_type)
    phrase = f"{diag_acc} диагностику" if diag_acc else "диагностику"

    primary = instance.primary_score if instance.primary_score is not None else '—'
    secondary = instance.score if instance.score is not None else '—'
    weak = ', '.join(str(t) for t in (instance.weak_topics or [])) or '—'

    review_url = f"{settings.SITE_URL}{reverse('diagnostic_review', args=[instance.id])}"
    registry_url = f"{settings.SITE_URL}{reverse('diagnostic_list')}"

    subject = (
        f"🩺 Диагностика пройдена [{instance.diagnostic_type or 'тип не указан'}]: "
        f"{primary}/{instance.max_primary_score}"
    )
    message = (
        f"{who_short} прошёл {phrase} {when:%d.%m.%Y в %H:%M} по московскому времени.\n"
        f"Результаты тестирования можно посмотреть по ссылке в конце письма.\n\n"
        f"{who}\n\n"
        f"🩺 Тип диагностики: {instance.diagnostic_type or '—'}\n"
        f"📊 Первичный балл: {primary} из {instance.max_primary_score}\n"
        f"📈 Тестовый балл: {secondary} из {instance.max_score}\n"
        f"🧩 Слабые задания: {weak}\n"
        f"🧪 Код теста: {instance.test_code}\n"
        f"🆔 ID попытки: {instance.id}\n\n"
        f"🔗 Результаты и ответы ученика:\n{review_url}\n\n"
        f"🗂 Реестр всех диагностик:\n{registry_url}\n"
    )

    threading.Thread(
        target=_send_owner_mail, args=(subject, message), daemon=True,
    ).start()