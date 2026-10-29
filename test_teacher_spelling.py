# test_teacher_spelling.py — учитель русского отвечает из БД по ошибочному
# варианту слова («полисадник» → палисадник), без ЛЛМ и предупреждений.
# Запуск: python manage.py test test_teacher_spelling --settings=settings_test_sqlite
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from main.assistants import teacher_russian
from main.assistants.teacher_russian import TeacherRussian
from main.models import Orthogram, OrthogramExample


class TeacherSpellingFromDbTest(TestCase):
    """Слово из incorrect_variant находится в БД: ответ точный, без ЛЛМ."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('spell_pupil', 'spell@x.ru', 'pass12345')
        Orthogram.objects.get_or_create(
            id='2', defaults={'name': 'Непроверяемые гласные и согласные в корне',
                              'letters': 'а,о,е,и,я,э,ю'})
        OrthogramExample.objects.get_or_create(
            text='палисадник',
            defaults={
                'orthogram_id': '2',
                'masked_word': 'п*2*лисадник',
                'incorrect_variant': 'полисадник',
                'explanation': 'Происходит от фр. palissade «частокол», '
                               'от лат. palus «кол»: в корне — А.',
                'grades': '10,11',
                'is_active': True,
            })
        cls.teacher = TeacherRussian()

    def _answer(self, message: str) -> str:
        return self.teacher.handle(self.user, message, {})

    def test_wrong_variant_answered_from_db(self):
        resp = self._answer('полисадник')
        self.assertIn('Правильное написание — палисадник (через А)', resp)
        self.assertIn('и именно этот вариант нужно запомнить!', resp)
        self.assertIn('Этимология слова: Происходит от фр. palissade', resp)
        self.assertIn('Добавь слово палисадник в планинг — задание 9, орфограмма 2 —',
                      resp)
        self.assertIn('и тогда оно попадет в квизы и слово дня.', resp)
        # Ни следа ЛЛМ-ветки с предупреждением «слова нет в базе»
        self.assertNotIn('⚠️', resp)
        self.assertNotIn('нет в нашей базе', resp)

    def test_spelling_question_wrong_variant(self):
        resp = self._answer('как пишется полисадник')
        self.assertIn('Правильное написание — палисадник (через А)', resp)
        self.assertNotIn('⚠️', resp)

    def test_correct_word_still_from_db(self):
        resp = self._answer('палисадник')
        self.assertIn('📖 палисадник', resp)
        self.assertIn('Происходит от фр. palissade', resp)
        self.assertNotIn('⚠️', resp)

    def test_unknown_word_falls_through(self):
        # Слова нет ни в text, ни в incorrect_variant: прежний путь не сломан.
        # ЛЛМ глушим, чтобы тест не ходил в сеть.
        with mock.patch.object(teacher_russian, 'LLM_AVAILABLE', False):
            resp = self._answer('зыбунок')
        self.assertNotIn('Правильное написание — палисадник', resp)
        self.assertIn('пока нет в нашей базе', resp)
