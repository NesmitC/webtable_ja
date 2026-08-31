import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from .models import UserWord

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