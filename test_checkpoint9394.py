# -*- coding: utf-8 -*-
"""Тест рубежей cp93 (4–9.1, 9.2, 9.3; открывает 9.4) и cp94 (финал задания 9).
Гейты цепочки, состав строк (15 и 20), разведение подзаданий 9/92/93/94
по орфограммам букв, рекомендации, карточки уроков 9.4 и рубежей.
Изоляция: test_settings_isolated (SQLite в памяти). Боевая БД не трогается.

Запуск: .\\.venv\\Scripts\\python.exe test_checkpoint9394.py
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
                         OrthogramExample, OrthoepyWord, TaskPaponim,
                         UserProfile, WordOk)

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
Orthogram.objects.create(id=12, name='Лаг/лож', letters='а,о')
Orthogram.objects.create(id=24, name='Бер/бир', letters='е,и')
Orthogram.objects.create(id=14, name='Ё-О после шипящих', letters='ё,о')
Orthogram.objects.create(id=15, name='И-Ы после Ц', letters='и,ы')

for text, masked in [('вода', 'в*1*да'), ('гора', 'г*1*ра'), ('трава', 'тр*1*ва'),
                     ('воды', 'в*1*ды'), ('горы', 'г*1*ры'), ('травы', 'тр*1*вы'),
                     ('водой', 'в*1*дой'), ('горой', 'г*1*рой'),
                     ('водяной', 'в*1*дяной'), ('гористый', 'г*1*ристый'),
                     ('река', 'р*1*ка'), ('реки', 'р*1*ки'),
                     ('земля', 'з*1*мля'), ('земли', 'з*1*мли'),
                     ('сосна', 'с*1*сна'), ('сосны', 'с*1*сны')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id=1, grades='10,11',
                                    is_active=True)
for text, masked in [('палисадник', 'п*2*лисадник'), ('семафор', 'с*2*мафор'),
                     ('вокзал', 'в*2*кзал'), ('компания', 'к*2*мпания'),
                     ('палисадника', 'п*2*лисадника'), ('семафора', 'с*2*мафора'),
                     ('вокзала', 'в*2*кзала'), ('компании', 'к*2*мпании'),
                     ('палисаднику', 'п*2*лисаднику'), ('семафоры', 'с*2*мафоры'),
                     ('вокзалы', 'в*2*кзалы'), ('компанию', 'к*2*мпанию'),
                     ('палисадником', 'п*2*лисадником'), ('семафором', 'с*2*мафором'),
                     ('вокзалу', 'в*2*кзалу'), ('компанией', 'к*2*мпанией')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id=2, grades='10,11',
                                    is_active=True)
for text, masked in [('излагать', 'изл*12*гать'), ('изложить', 'изл*12*жить'),
                     ('предложение', 'пр*12*дложение'), ('лагерный', 'л*12*герный'),
                     ('изложение', 'изл*12*жение'), ('полагать', 'пол*12*гать'),
                     ('сложить', 'сл*12*жить'), ('отрасль', 'отр*12*сль')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id=12, grades='10,11',
                                    is_active=True)
for text, masked in [('собирать', 'соб*24*рать'), ('соберёт', 'соб*24*рёт'),
                     ('замирать', 'зам*24*рать'), ('замереть', 'зам*24*реть'),
                     ('обдирать', 'обд*24*рать'), ('обдерёт', 'обд*24*рёт'),
                     ('блистать', 'бл*24*стать'), ('блестеть', 'бл*24*стеть')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id=24, grades='10,11',
                                    is_active=True)
for text, masked in [('шов', 'ш*14*в'), ('шёл', 'ш*14*л'),
                     ('жёлудь', 'ж*14*лудь'), ('шёпот', 'ш*14*пот'),
                     ('чёрный', 'ч*14*рный'), ('щётка', 'щ*14*тка'),
                     ('чёткий', 'ч*14*ткий'), ('крыжовник', 'крыж*14*вник')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id=14, grades='10,11',
                                    is_active=True)
for text, masked in [('цирк', 'ц*15*рк'), ('цыган', 'ц*15*ган'),
                     ('станция', 'станц*15*я'), ('огурцы', 'огурц*15*'),
                     ('цифра', 'ц*15*фра'), ('панцирь', 'панц*15*рь'),
                     ('цыпочки', 'ц*15*почки'), ('секция', 'секц*15*я')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id=15, grades='10,11',
                                    is_active=True)

CHERED = {'12', '13', '24', '26', '27', '271', '272', '273', '274', '275'}


def pass_code(user, code):
    CheckpointAttempt.objects.create(
        user=user, checkpoint_code=code, passed=True, total_tasks=8,
        correct_count=8, error_count=0, results_data={}, words_data=[])


def good_answers(sess):
    answers = {}
    for k in ('4', '7'):
        if f'answer_{k}' in sess:
            answers[k] = sess[f'answer_{k}']
    if 'answer_5' in sess:
        answers['5'] = 'НАДЕТЬ'
    if 'answer_6' in sess:
        answers['6'] = sess['answer_6'].split(',')[0].strip()
    return answers


u = make_user('pupil')
c = Client()
c.force_login(u)

print('1. Гейты цепочки')
r = c.get('/ege/checkpoint/9-3/')
check(r.status_code == 302, f'cp93 без cp92 -> редирект (факт: {r.status_code})')
r = c.get('/ege/checkpoint/9-4/')
check(r.status_code == 302, f'cp94 без cp93 -> редирект (факт: {r.status_code})')
pass_code(u, 'cp91')
pass_code(u, 'cp92')
r = c.get('/ege/checkpoint/9-3/')
check(r.status_code == 200, f'cp93 после cp92 -> 200 (факт: {r.status_code})')
body = r.content.decode('utf-8')
check('задания 4–9.1, 9.2, 9.3' in body, 'шапка рубежа 9.3')
check('Чтобы открылся урок 9.4' in body, 'обещание открыть урок 9.4')
r = c.get('/ege/checkpoint/9-4/')
check(r.status_code == 302, f'cp94 всё ещё закрыт без cp93 (факт: {r.status_code})')

print('2. Состав cp93: 15 строк = 9.1+9.2+9.3')
sess = c.session['checkpoint_93']
orths = sess['task9_orths']
check(len(sess['task9_correct']) == 45, f'45 букв (факт: {len(sess["task9_correct"])})')
check(orths.count('1') == 15 and orths.count('2') == 15,
      f'по 15 букв 9.1 и 9.2 (факт: {orths.count("1")}/{orths.count("2")})')
check(sum(1 for o in orths if o in CHERED) == 15,
      f'15 букв 9.3 (факт: {sum(1 for o in orths if o in CHERED)})')

print('3. cp93 сдан целиком -> урок 9.4 открыт')
answers = good_answers(sess)
for i, letter in enumerate(sess['task9_correct'], 1):
    answers[f'9-{i}'] = letter
r = c.post('/ege/checkpoint/9-3/', data=json.dumps({'answers': answers}),
           content_type='application/json')
res = r.json()
check(res['passed'] and res['error_count'] == 0,
      f'сдан, ошибок 0 (факт: passed={res["passed"]}, err={res["error_count"]})')
lb = c.get('/ege/lessons/').content.decode('utf-8')
i94 = lb.find('Задание 9.4 (корни: Ё-О после шипящих, И-Ы после Ц)')
check(i94 != -1 and 'lesson-card--active' in lb[max(0, i94 - 900):i94],
      'карточка урока 9.4 активна после сдачи cp93')
check('kinescope.io/embed/osLWDdyKH4yYp41TaVJHuE' in lb,
      'видео 9.4 в карточке')
check('Рубежный тест: задания 4–9.1, 9.2, 9.3, 9.4' in lb,
      'карточка рубежа cp94 видна после cp93')
i93 = lb.find('Задание 9.3 (корни: гласные ЧЕРЕДУЮЩИЕСЯ)')
check('kinescope.io/embed/qASZrA5QRCLWoyu3DuVnhp' in lb[i93:i93 + 2500],
      'видео 9.3 в карточке урока 9.3')

print('4. Состав cp94: 20 строк = +9.4')
r = c.get('/ege/checkpoint/9-4/')
check(r.status_code == 200, f'cp94 после cp93 -> 200 (факт: {r.status_code})')
sess4 = c.session['checkpoint_94']
orths4 = sess4['task9_orths']
check(len(sess4['task9_correct']) == 60, f'60 букв (факт: {len(sess4["task9_correct"])})')
check(sum(1 for o in orths4 if o in ('14', '15')) == 15,
      f'15 букв 9.4 (факт: {sum(1 for o in orths4 if o in ("14", "15"))})')
check('Чтобы открылся урок 10' in r.content.decode('utf-8'),
      'cp94 открывает урок 10')

print('5. Разведение подзаданий: ошибки только в 9.3 и 9.4')
answers = good_answers(sess4)
wrong93 = wrong94 = None
for i, o in enumerate(orths4, 1):
    if o in CHERED and wrong93 is None:
        wrong93 = i
    if o in ('14', '15') and wrong94 is None:
        wrong94 = i
for i, letter in enumerate(sess4['task9_correct'], 1):
    answers[f'9-{i}'] = letter
for i in (wrong93, wrong94):
    good = answers[f'9-{i}']
    answers[f'9-{i}'] = 'я' if good != 'я' else 'у'
r = c.post('/ege/checkpoint/9-4/', data=json.dumps({'answers': answers}),
           content_type='application/json')
res = r.json()
check(res['results']['9']['is_correct'] and res['results']['92']['is_correct'],
      '9.1 и 9.2 верны')
check(not res['results']['93']['is_correct'] and not res['results']['94']['is_correct'],
      '9.3 и 9.4 помечены ошибочными')
check(res['error_count'] == 2 and res['passed'],
      f'2 ошибки = 2 подзадания, сдан с допуском (факт: {res["error_count"]})')
rb = c.get(res['result_url']).content.decode('utf-8')
check('chereduyushchiesya-glasnye' in rb, 'рекомендация 9.3 ведёт в раздел чередований')
check('Задание 9.4: корни 14-15' in rb, 'рекомендация 9.4 на месте')
check('Урок 10 открыт' in rb, 'вердикт cp94: урок 10 открыт')
lb2 = c.get('/ege/lessons/').content.decode('utf-8')
i10 = lb2.find('Задание 10 (орфография, приставки)')
check('lesson-card--active' in lb2[max(0, i10 - 900):i10],
      'карточка урока 10 активна после cp94')
check('Рубежный тест: задания 4–10' in lb2,
      'карточка рубежа cp10 видна после cp94')

print('6. Ошибка в 9.1 ловится отдельно')
u2 = make_user('pupil2')
c2 = Client()
c2.force_login(u2)
pass_code(u2, 'cp91')
pass_code(u2, 'cp92')
pass_code(u2, 'cp93')
c2.get('/ege/checkpoint/9-4/')
s2 = c2.session['checkpoint_94']
a2 = good_answers(s2)
for i, letter in enumerate(s2['task9_correct'], 1):
    a2[f'9-{i}'] = letter
i91 = s2['task9_orths'].index('1') + 1
good = a2[f'9-{i91}']
a2[f'9-{i91}'] = 'я' if good != 'я' else 'у'
r = c2.post('/ege/checkpoint/9-4/', data=json.dumps({'answers': a2}),
            content_type='application/json')
res2 = r.json()
check(not res2['results']['9']['is_correct'] and res2['results']['93']['is_correct'],
      'ошибка 9.1 не смазывает 9.3')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ РУБЕЖЕЙ 9.3/9.4 ПРОЙДЕНЫ')
