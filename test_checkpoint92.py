# -*- coding: utf-8 -*-
"""Тест рубежного теста cp92 (задания 4–9.1, 9.2; открывает урок 9.3).
Изоляция: test_settings_isolated (SQLite в памяти). Боевая БД не трогается.

Запуск: .\\.venv\\Scripts\\python.exe test_checkpoint92.py
"""
import json
import os
import sys
from datetime import timedelta

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings
from django.core.management import call_command
from django.test import Client
from django.test.utils import setup_test_environment
from django.utils import timezone

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from django.contrib.auth import get_user_model

from main.models import (CheckpointAttempt, CorrectionExercise, Orthogram,
                         OrthogramExample, OrthoepyWord, TaskPaponim, UserProfile,
                         WordOk)

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()


def make_user(name):
    u = User.objects.create_user(username=name, email=f'{name}@example.com',
                                 password='Zk9mQ2vLp7xR')
    prof, _ = UserProfile.objects.get_or_create(user=u)
    prof.trial_until = timezone.now() + timedelta(days=5)
    prof.save()
    return u


# ===== Контент БД =====
for word, lemma, ok in [
        ('звонИт', 'звонить', True), ('тОрты', 'торт', True),
        ('бАнты', 'бант', True), ('дОговор', 'договор', False),
        ('каталОг', 'каталог', False), ('свЁкла', 'свекла', False)]:
    OrthoepyWord.objects.create(word=word, lemma=lemma, is_correct=ok,
                                is_active=True)
TaskPaponim.objects.create(text='Он решил **одеть** очки и вышел на улицу.',
                           correct_word='надеть', root='дет',
                           is_active=True, is_for_quiz=True)
for sent, root in [
        ('Это было **гарантийное** обслуживание.', 'гарант'),
        ('Она **адресовала** письмо подруге.', 'адрес'),
        ('Мы **оплатили** проезд.', 'оплат'),
        ('**Дипломатичный** ответ устроил всех.', 'диплом')]:
    TaskPaponim.objects.create(text=sent, correct_word='', root=root,
                               is_active=True, is_for_quiz=True)
WordOk.objects.create(text='Мы **оплатили** за проезд.', task_type='6100',
                      correct_variants='за, заплатили', is_active=True)
for i, (bad, good) in enumerate([
        ('сожгет', 'сожжёт'), ('чулков', 'чулок'), ('замзрнул', 'замёрз'),
        ('ихний', 'их'), ('ездию', 'езжу')]):
    CorrectionExercise.objects.create(incorrect_text=bad, correct_text=good,
                                      is_active=True, exercise_id=f'71{i}')

Orthogram.objects.create(id=1, name='Проверяемая безударная гласная',
                         letters='а,о,е,и,я,у,ю')
Orthogram.objects.create(id=2, name='Непроверяемые безударные гласные',
                         letters='а,о,е,и,я,у,ю')
for text, masked in [('вода', 'в*1*да'), ('гора', 'г*1*ра'), ('трава', 'тр*1*ва'),
                     ('воды', 'в*1*ды'), ('горы', 'г*1*ры'), ('травы', 'тр*1*вы'),
                     ('водой', 'в*1*дой'), ('горой', 'г*1*рой'),
                     ('водяной', 'в*1*дяной'), ('гористый', 'г*1*ристый')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id=1, grades='10,11',
                                    is_active=True)
for text, masked in [('палисадник', 'п*2*лисадник'), ('семафор', 'с*2*мафор'),
                     ('вокзал', 'в*2*кзал'), ('компания', 'к*2*мпания'),
                     ('палисадника', 'п*2*лисадника'), ('семафора', 'с*2*мафора'),
                     ('вокзала', 'в*2*кзала'), ('компании', 'к*2*мпании'),
                     ('палисаднику', 'п*2*лисаднику'), ('семафоры', 'с*2*мафоры')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id=2, grades='10,11',
                                    is_active=True)


def pass_cp91(user):
    CheckpointAttempt.objects.create(
        user=user, checkpoint_code='cp91', passed=True, total_tasks=6,
        correct_count=6, error_count=0, results_data={}, words_data=[])


def good_answers(sess):
    answers = {}
    for k in ('4', '7'):
        if f'answer_{k}' in sess:
            answers[k] = sess[f'answer_{k}']
    if 'answer_5' in sess:
        answers['5'] = 'НАДЕТЬ'
    if 'answer_6' in sess:
        answers['6'] = sess['answer_6'].split(',')[0].strip()
    for i, letter in enumerate(sess['task9_correct'], 1):
        answers[f'9-{i}'] = letter
    return answers


print('1. Гейт: без сдачи 4–9.1 рубеж 9.2 недоступен')
u0 = make_user('p92_gate')
c0 = Client()
c0.force_login(u0)
r0 = c0.get('/ege/checkpoint/9-2/')
check(r0.status_code == 302, f'GET без cp91 -> редирект ({r0.status_code})')

print('2. Состав: 6 строк смайликов = 9.1 + 9.2')
u1 = make_user('p92_ok')
pass_cp91(u1)
c = Client()
c.force_login(u1)
r = c.get('/ege/checkpoint/9-2/')
check(r.status_code == 200, f'GET -> {r.status_code}')
body = r.content.decode('utf-8')
check('Рубежный тест: задания 4–9.1, 9.2' in body, 'заголовок рубежа')
check('открылся урок 9.3' in body, 'обещание открыть урок 9.3')
check('9.1–9.2. Выберите правильную букву' in body, 'подпись блока 9.1–9.2')
sess = c.session['checkpoint_92']
orths = sess.get('task9_orths', [])
check(len(sess['task9_correct']) == 18,
      f'18 букв (6 строк): факт {len(sess["task9_correct"])}')
check(orths.count('1') == 9 and orths.count('2') == 9,
      f'разметка 9.1/9.2 поровну: {orths.count("1")}/{orths.count("2")}')

print('3. Всё верно: сдан, урок 9.3 открыт')
r = c.post('/ege/checkpoint/9-2/', data=json.dumps({'answers': good_answers(sess)}),
           content_type='application/json')
a = CheckpointAttempt.objects.filter(user=u1, checkpoint_code='cp92').first()
check(a and a.passed and a.error_count == 0, 'попытка passed, 0 ошибок')
vb = c.get(r.json()['result_url']).content.decode('utf-8')
check('Урок 9.3 открыт' in vb, 'вердикт: урок 9.3 открыт')
lb = c.get('/ege/lessons/').content.decode('utf-8')
i93 = lb.find('Задание 9.3 (корни: гласные ЧЕРЕДУЮЩИЕСЯ)')
check('lesson-card--active' in lb[max(0, i93 - 900):i93],
      'карточка 9.3 активна после сдачи')
check('Открыт · видео скоро' in lb, 'статус 9.3: открыт, видео скоро')
check('Сдан: урок 9.3 открыт' in lb, 'статус карточки рубежа: сдан')

print('4. Провал: 9.3 закрыт, рекомендации по 9.1 и 9.2')
u2 = make_user('p92_fail')
pass_cp91(u2)
c2 = Client()
c2.force_login(u2)
c2.get('/ege/checkpoint/9-2/')
bad = {'4': ['чушь'], '5': 'чушь', '6': 'чушь', '7': 'чушь'}
n = len(c2.session['checkpoint_92']['task9_correct'])
for i in range(1, n + 1):
    bad[f'9-{i}'] = 'я'
r2 = c2.post('/ege/checkpoint/9-2/', data=json.dumps({'answers': bad}),
             content_type='application/json')
a2 = CheckpointAttempt.objects.filter(user=u2, checkpoint_code='cp92').first()
check(a2 and not a2.passed, 'попытка не сдана')
vb2 = c2.get(r2.json()['result_url']).content.decode('utf-8')
check('proveryaemye-glasnye' in vb2 and 'neproveryaemye-glasnye' in vb2,
      'рекомендации ведут в оба раздела гласных')
check('9.1' in vb2 and '9.2' in vb2, 'в разборе строки 9.1 и 9.2')
lb2 = c2.get('/ege/lessons/').content.decode('utf-8')
i93b = lb2.find('Задание 9.3 (корни: гласные ЧЕРЕДУЮЩИЕСЯ)')
check('lesson-card--locked' in lb2[max(0, i93b - 900):i93b],
      '9.3 закрыт после провала')

print('5. Смешанно: 9.1 верно, 9.2 неверно -> сдан с 1 ошибкой')
u3 = make_user('p92_mix')
pass_cp91(u3)
c3 = Client()
c3.force_login(u3)
c3.get('/ege/checkpoint/9-2/')
s3 = c3.session['checkpoint_92']
ans = good_answers(s3)
for i, o in enumerate(s3['task9_orths'], 1):
    if o == '2':
        ans[f'9-{i}'] = 'я'
r3 = c3.post('/ege/checkpoint/9-2/', data=json.dumps({'answers': ans}),
             content_type='application/json')
a3 = CheckpointAttempt.objects.filter(user=u3, checkpoint_code='cp92').first()
res3 = a3.results_data
check(a3.passed and a3.error_count == 1,
      f'1 ошибка (только 9.2): факт {a3.error_count}, passed={a3.passed}')
check(res3.get('9', {}).get('correct') is True
      and res3.get('92', {}).get('correct') is False,
      'зачёт раздельный: 9.1 верно, 9.2 ошибка')
vb3 = c3.get(r3.json()['result_url']).content.decode('utf-8')
check('zadanie-9/neproveryaemye-glasnye' in vb3
      and 'zadanie-9/proveryaemye-glasnye' not in vb3,
      'рекомендация только по 9.2')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ РУБЕЖА 4–9.1, 9.2 ПРОЙДЕНЫ')
