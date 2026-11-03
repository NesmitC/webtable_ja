# -*- coding: utf-8 -*-
"""Тест рубежа cp10 (задания 4–10; открывает урок 11): гейт по cp94,
25 строк (9.1-9.4 + приставки), разведение подзадания 10, рекомендации,
карточка урока 11. Изоляция: test_settings_isolated (SQLite в памяти).

Запуск: .\\.venv\\Scripts\\python.exe test_checkpoint10.py
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
Orthogram.objects.create(id=14, name='Ё-О после шипящих', letters='ё,о')
Orthogram.objects.create(id=11, name='Приставки на з/с', letters='з,с')
Orthogram.objects.create(id=28, name='Ы-И после приставок', letters='ы,и')
Orthogram.objects.create(id=29, name='Пре/при', letters='е,и')
Orthogram.objects.create(id=6, name='Разделительные ъ и ь', letters='ъ,ь')

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
                     ('сложить', 'сл*12*жить'), ('излагал', 'изл*12*гал')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id=12, grades='10,11',
                                    is_active=True)
for text, masked in [('шов', 'ш*14*в'), ('шёл', 'ш*14*л'),
                     ('жёлудь', 'ж*14*лудь'), ('шёпот', 'ш*14*пот'),
                     ('чёрный', 'ч*14*рный'), ('щётка', 'щ*14*тка'),
                     ('чёткий', 'ч*14*ткий'), ('крыжовник', 'крыж*14*вник')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id=14, grades='10,11',
                                    is_active=True)
for text, masked in [('разбег', 'ра*11*бег'), ('раскат', 'ра*11*кат'),
                     ('низвергнуть', 'ни*11*звергнуть'), ('испуг', 'и*11*пуг'),
                     ('бездарный', 'бе*11*здарный'), ('восход', 'во*11*сход'),
                     ('разлив', 'ра*11*лив'), ('список', 'с*11*писок')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id=11, grades='10,11',
                                    is_active=True)
for text, masked in [('предыстория', 'пред*28*история'), ('сыграть', 'с*28*грать'),
                     ('взыскать', 'вз*28*искать'), ('изымать', 'из*28*имать'),
                     ('межинститутский', 'меж*28*институтский'),
                     ('сверхинтересный', 'сверх*28*интересный'),
                     ('контригра', 'контр*28*игра'), ('панисламизм', 'пан*28*исламизм')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id=28, grades='10,11',
                                    is_active=True)
for text, masked in [('приехать', 'пр*29*иехать'), ('преграда', 'пр*29*града'),
                     ('пришить', 'пр*29*шить'), ('прекрасный', 'пр*29*красный'),
                     ('приоткрыть', 'пр*29*открыть'), ('прервать', 'пр*29*рвать'),
                     ('придумать', 'пр*29*думать'), ('преувеличить', 'пр*29*увеличить')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id=29, grades='10,11',
                                    is_active=True)
for text, masked in [('подъезд', 'под*6*езд'), ('отъезд', 'от*6*езд'),
                     ('съел', 'с*6*ел'), ('вьюга', 'в*6*юга'),
                     ('подъём', 'под*6*ём'), ('объём', 'об*6*ём'),
                     ('сьезд', 'с*6*езд'), ('пью', 'п*6*ю')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id=6, grades='10,11',
                                    is_active=True)

PREFIX = {'11', '28', '29', '6'}


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

print('1. Гейт: cp10 только после cp94')
r = c.get('/ege/checkpoint/10/')
check(r.status_code == 302, f'без cp94 -> редирект (факт: {r.status_code})')
for code in ('cp91', 'cp92', 'cp93', 'cp94'):
    pass_code(u, code)
r = c.get('/ege/checkpoint/10/')
check(r.status_code == 200, f'после cp94 -> 200 (факт: {r.status_code})')
body = r.content.decode('utf-8')
check('Рубежный тест: задания 4–10' in body, 'шапка рубежа 4–10')
check('Чтобы открылся урок 11' in body, 'обещание открыть урок 11')

print('2. Состав: 25 строк = 9.1-9.4 + приставки')
sess = c.session['checkpoint_10']
orths = sess['task9_orths']
check(len(sess['task9_correct']) == 75, f'75 букв (факт: {len(sess["task9_correct"])})')
check(sum(1 for o in orths if o in PREFIX) == 15,
      f'15 букв задания 10 (факт: {sum(1 for o in orths if o in PREFIX)})')

print('3. Сдан целиком -> урок 11 открыт')
answers = good_answers(sess)
for i, letter in enumerate(sess['task9_correct'], 1):
    answers[f'9-{i}'] = letter
r = c.post('/ege/checkpoint/10/', data=json.dumps({'answers': answers}),
           content_type='application/json')
res = r.json()
check(res['passed'] and res['error_count'] == 0,
      f'сдан, ошибок 0 (факт: {res["passed"]}, {res["error_count"]})')
lb = c.get('/ege/lessons/').content.decode('utf-8')
i11 = lb.find('Задание 11 (орфография, суффиксы)')
j11 = lb.rfind('<div class="lesson-card lesson-card--', 0, i11)
check('lesson-card--active' in lb[j11:i11],
      'карточка урока 11 активна после cp10')

print('4. Ошибка только в приставках: подзадание 10 отдельно')
u2 = make_user('pupil2')
c2 = Client()
c2.force_login(u2)
for code in ('cp91', 'cp92', 'cp93', 'cp94'):
    pass_code(u2, code)
c2.get('/ege/checkpoint/10/')
s2 = c2.session['checkpoint_10']
a2 = good_answers(s2)
for i, letter in enumerate(s2['task9_correct'], 1):
    a2[f'9-{i}'] = letter
i10 = next(i for i, o in enumerate(s2['task9_orths'], 1) if o in PREFIX)
good = a2[f'9-{i10}']
a2[f'9-{i10}'] = 'я' if good != 'я' else 'у'
r = c2.post('/ege/checkpoint/10/', data=json.dumps({'answers': a2}),
            content_type='application/json')
res2 = r.json()
check(res2['results']['9']['is_correct'] and res2['results']['94']['is_correct'],
      '9.1 и 9.4 верны')
check(not res2['results']['10']['is_correct'], 'подзадание 10 помечено ошибкой')
check(res2['error_count'] == 1 and res2['passed'],
      f'1 ошибка, сдан (факт: {res2["error_count"]})')
rb = c2.get(res2['result_url']).content.decode('utf-8')
check('/ege/zadanie-10/' in rb, 'рекомендация 10 ведёт на страницу приставок')
check('Урок 11 открыт' in rb, 'вердикт: урок 11 открыт')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ РУБЕЖА 4–10 ПРОЙДЕНЫ')
