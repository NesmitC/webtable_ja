# main/assistants/teacher_analytics.py
"""
Нейро-аналитик для преподавателя/админа
Автоматические отчёты по ученикам
"""

from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
from main.models import UserWord, QuizHistory, OrthogramExample, UserProfile


class TeacherAnalytics:
    """Сбор аналитики для админа/преподавателя"""
    
    def get_overview(self, days=7):
        """Общая статистика за период"""
        since = timezone.now() - timedelta(days=days)
        
        return {
            'total_students': UserProfile.objects.filter(
                user__last_login__gte=since
            ).count(),
            'total_words_in_planning': UserWord.objects.filter(
                is_active=True
            ).count(),
            'unique_words_in_planning': UserWord.objects.filter(
                is_active=True
            ).values('text').distinct().count(),
            'total_quizzes': QuizHistory.objects.filter(
                answer_time__gte=since
            ).count(),
            'avg_success_rate': self._calculate_avg_success_rate(since),
            'words_without_explanation': self._count_missing_explanations(),
        }
    
    def get_student_details(self, user_id):
        """Детали по конкретному ученику"""
        from django.contrib.auth.models import User
        
        user = User.objects.get(id=user_id)
        
        # ✅ ИСПРАВЛЕНО: reference_word__orthogram (не 'orthogram'!)
        planning_words = UserWord.objects.filter(
            user=user,
            is_active=True
        ).select_related('reference_word__orthogram')
        
        # Проверка заполненности Explanation
        words_with_explanation = 0
        words_without_explanation = 0
        
        for pw in planning_words:
            # ✅ Используем reference_word из самого UserWord
            if pw.reference_word and pw.reference_word.explanation:
                words_with_explanation += 1
            else:
                words_without_explanation += 1
        
        # Квизы
        quizzes = QuizHistory.objects.filter(user=user)
        
        return {
            'username': user.username,
            'last_login': user.last_login,
            'planning_words_count': planning_words.count(),
            'words_with_explanation': words_with_explanation,
            'words_without_explanation': words_without_explanation,
            'explanation_rate': round(
                words_with_explanation / planning_words.count() * 100
            ) if planning_words.exists() else 0,
            'total_quizzes': quizzes.count(),
            'success_rate': round(
                quizzes.filter(was_correct=True).count() / quizzes.count() * 100
            ) if quizzes.exists() else 0,
            # ✅ ИСПРАВЛЕНО: доступ через reference_word
            'planning_words': [
                {
                    'text': pw.text,
                    'orthogram_name': (
                        pw.reference_word.orthogram.name 
                        if pw.reference_word and pw.reference_word.orthogram 
                        else None
                    ),
                    'created_at': pw.created_at
                }
                for pw in planning_words[:20]
            ],
        }
    
    def get_all_students_summary(self):
        """Сводка по всем ученикам"""
        from django.contrib.auth.models import User
        
        students = User.objects.filter(
            is_staff=False,
            last_login__isnull=False
        ).order_by('-last_login')
        
        result = []
        for student in students[:50]:
            details = self.get_student_details(student.id)
            result.append({
                'id': student.id,
                'username': details['username'],
                'last_login': details['last_login'],
                'planning_words': details['planning_words_count'],
                'explanation_rate': details['explanation_rate'],
                'quizzes_count': details['total_quizzes'],
                'success_rate': details['success_rate'],
            })
        
        return result
    
    def _calculate_avg_success_rate(self, since):
        """Средняя успешность по всем ученикам"""
        quizzes = QuizHistory.objects.filter(answer_time__gte=since)
        if not quizzes.exists():
            return 0
        correct = quizzes.filter(was_correct=True).count()
        return round(correct / quizzes.count() * 100)
    
    def _count_missing_explanations(self):
        """Сколько слов из планингов без объяснения в БД"""
        all_planning_words = UserWord.objects.filter(
            is_active=True
        ).values('text').distinct()
        
        missing_count = 0
        for pw in all_planning_words:
            exists = OrthogramExample.objects.filter(
                text=pw['text'],
                explanation__isnull=False
            ).exclude(explanation='').exists()
            if not exists:
                missing_count += 1
        return missing_count
    
    def get_missing_explanations_list(self, limit=50):
        """Список слов без объяснений"""
        from django.db.models import Count
        
        planning_words = UserWord.objects.filter(
            is_active=True
        ).values('text', 'reference_word__explanation').annotate(
            user_count=Count('user', distinct=True)
        ).order_by('-user_count')
        
        missing = []
        for pw in planning_words[:limit]:
            # ✅ Проверяем explanation через reference_word
            if not pw.get('reference_word__explanation'):
                missing.append({
                    'text': pw['text'],
                    'used_by_students': pw['user_count'],
                })
        
        return missing