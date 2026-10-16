# test_task9_seo.py — открытые SEO-страницы задания 9, seo-режим тренажёров
# и отчёт «Работа над ошибками» + «История прохождений».
# Запуск: python manage.py test test_task9_seo --settings=settings_test_sqlite
import json
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase

from main.models import Orthogram, OrthogramExample, Task9Attempt

ROOT = Path(__file__).resolve().parent

SECTIONS = [
    'proveryaemye-glasnye',
    'neproveryaemye-glasnye',
    'chereduyushchiesya-glasnye',
]


def seed_examples() -> None:
    """Минимальная база слов: тестовая БД пустая, генератору нужны примеры."""
    Orthogram.objects.get_or_create(
        id='1', defaults={'name': 'Проверяемые', 'letters': 'а,о,е,и,я,у,ю'})
    Orthogram.objects.get_or_create(
        id='24', defaults={'name': 'Чередования е/и', 'letters': 'е,и,я'})
    Orthogram.objects.get_or_create(
        id='12', defaults={'name': 'Чередования лаг/лож', 'letters': 'а,о'})
    Orthogram.objects.get_or_create(
        id='13', defaults={'name': 'Чередования раст/рос', 'letters': 'а,о'})
    Orthogram.objects.get_or_create(
        id='271', defaults={'name': 'Чередования клан/клон', 'letters': 'а,о'})
    Orthogram.objects.get_or_create(
        id='275', defaults={'name': 'Чередования равн/ровн', 'letters': 'а,о,е'})
    for text, masked in [('вода', 'в*1*да'), ('гора', 'г*1*ра'), ('трава', 'тр*1*ва')]:
        OrthogramExample.objects.get_or_create(
            text=text, defaults={
                'orthogram_id': '1', 'masked_word': masked,
                'grades': '10,11', 'is_active': True})
    for text, masked in [('собирать', 'соб*24*рать'), ('запирать', 'зап*24*рать')]:
        OrthogramExample.objects.get_or_create(
            text=text, defaults={
                'orthogram_id': '24', 'masked_word': masked,
                'grades': '10,11', 'is_active': True})
    for text, masked in [('положить', 'пол*12*жить'), ('прилагать', 'прил*12*гать')]:
        OrthogramExample.objects.get_or_create(
            text=text, defaults={
                'orthogram_id': '12', 'masked_word': masked,
                'grades': '5,10,11', 'is_active': True})
    for text, masked in [('вырастать', 'выр*13*стать'), ('возросший', 'возр*13*сший')]:
        OrthogramExample.objects.get_or_create(
            text=text, defaults={
                'orthogram_id': '13', 'masked_word': masked,
                'grades': '5,10,11', 'is_active': True})
    for text, masked in [('клон', 'кл*271*н'), ('поклон', 'покл*271*н')]:
        OrthogramExample.objects.get_or_create(
            text=text, defaults={
                'orthogram_id': '271', 'masked_word': masked,
                'grades': '6,10,11', 'is_active': True})
    for text, masked in [('равный', 'р*275*вный'), ('уравнение', 'ур*275*внение')]:
        OrthogramExample.objects.get_or_create(
            text=text, defaults={
                'orthogram_id': '275', 'masked_word': masked,
                'grades': '6,10,11', 'is_active': True})


class Task9SeoPagesTest(TestCase):
    """Страницы доступны анониму и несут SEO-атрибуты."""

    def test_hub_available_anonymous(self):
        resp = self.client.get('/ege/zadanie-9/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('rel="canonical"', body)
        self.assertIn('https://neurostat.ru/ege/zadanie-9/', body)
        for slug in SECTIONS:
            self.assertIn(f'/ege/zadanie-9/{slug}/', body)

    def test_sections_available_anonymous(self):
        for slug in SECTIONS:
            resp = self.client.get(f'/ege/zadanie-9/{slug}/')
            self.assertEqual(resp.status_code, 200, slug)
            body = resp.content.decode('utf-8')
            self.assertIn(f'canonical" href="https://neurostat.ru/ege/zadanie-9/{slug}/"', body)
            self.assertIn('task9-seo-content', body)
            self.assertIn('BreadcrumbList', body)
            self.assertIn('task9_report.js', body)

    def test_unknown_section_404(self):
        resp = self.client.get('/ege/zadanie-9/net-takogo/')
        self.assertEqual(resp.status_code, 404)

    def test_chered_trainer_title_and_buttons(self):
        body = self.client.get(
            '/ege/zadanie-9/chereduyushchiesya-glasnye/').content.decode('utf-8')
        self.assertIn('Тренажёр: выберите корни', body)
        self.assertIn('лаг / лож', body)
        self.assertIn('равн / ровн, мак / мок', body)
        # pending-кнопок больше нет: все группы грузятся боевым range
        self.assertNotIn('task9-root-btn', body)
        self.assertIn('data-range="CHERED"', body)
        self.assertIn('data-range="RAVN"', body)
        # остальные разделы — прежний заголовок
        body1 = self.client.get(
            '/ege/zadanie-9/proveryaemye-glasnye/').content.decode('utf-8')
        self.assertIn('Тренажёр: выберите диапазон букв', body1)

    def test_sitemap_updated(self):
        sitemap = (ROOT / 'sitemap.xml').read_text(encoding='utf-8')
        self.assertIn('https://neurostat.ru/ege/zadanie-9/', sitemap)
        self.assertIn('https://neurostat.ru/ege/zadanie-9/proveryaemye-glasnye/', sitemap)
        # Закрытая логином страница тренажёров не должна манить краулеров
        self.assertNotIn('https://neurostat.ru/ege/trainers/', sitemap)


class Task9SeoTrainerTest(TestCase):
    """Тренажёр на SEO-страницах: анонимно, сессионный отчёт, лимит."""

    @classmethod
    def setUpTestData(cls):
        seed_examples()

    def _generate(self, mode='seo'):
        body = {'orthogram_id': '1', 'range': 'A-O'}
        if mode:
            body['mode'] = mode
        return self.client.post(
            '/api/generate-alphabetical-exercise/',
            data=json.dumps(body),
            content_type='application/json',
        )

    def _check(self, letters):
        return self.client.post(
            '/api/check-alphabetical-exercise/',
            data=json.dumps({'selected_letters': letters}),
            content_type='application/json',
        )

    def test_anonymous_generate_seo(self):
        resp = self._generate('seo')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('article-practice', data['html'])
        # Пустой сессионный отчёт: история появится после первой проверки
        self.assertEqual(data['report']['attempts'], [])
        self.assertEqual(data['report']['correction'], [])

    def test_anonymous_without_mode_forbidden(self):
        resp = self._generate(None)
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_check_session_report_no_db(self):
        self._generate('seo')
        resp = self._check(['о', 'о'])
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        report = data['report']
        self.assertEqual(len(report['attempts']), 1)
        self.assertEqual(report['attempts'][0]['chosen'], data['total_count'])
        # Ошибки попали в блоки «Работа над ошибками» с датой
        wrong = [c for c, ok in zip(report['correction'], data['results']) if not ok]
        self.assertEqual(len(wrong), data['total_count'] - data['correct_count'])
        for item in wrong:
            self.assertRegex(item['correction_since'], r'\d{2}\.\d{2}\.\d{4}')
            self.assertIn('word', item)
        # В БД анонима нет: летопись — только для аккаунтов
        self.assertEqual(Task9Attempt.objects.count(), 0)

        # Вторая попытка: история растёт, исправленное слово уходит из коррекции
        self._generate('seo')
        resp2 = self._check(['а', 'о', 'а'])
        report2 = resp2.json()['report']
        self.assertEqual(len(report2['attempts']), 2)
        if resp2.json()['results'][0]:
            words2 = {c['word'] for c in report2['correction']}
            self.assertNotIn('в*1*да', words2)

    def test_logged_user_seo_writes_chronicle(self):
        user = User.objects.create_user('seo_pupil', 'seo@x.ru', 'pass12345')
        self.client.force_login(user)
        self._generate('seo')
        resp = self._check(['о', 'о'])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Task9Attempt.objects.filter(user=user).count(), 1)
        self.assertIsNotNone(resp.json()['report'])

    def test_logged_user_old_flow_keeps_chronicle(self):
        user = User.objects.create_user('old_pupil', 'old@x.ru', 'pass12345')
        self.client.force_login(user)
        resp = self._generate(None)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('report', resp.json())
        resp = self._check(['а', 'о'])
        if resp.status_code != 200:
            print('CHECK BODY:', resp.content.decode('utf-8')[:3000])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Task9Attempt.objects.filter(user=user).count(), 1)

    def test_chered_seo_anonymous(self):
        resp = self.client.post(
            '/api/generate-chered-exercise/',
            data=json.dumps({'mode': 'seo'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('report', resp.json())
        # Смешанный набор без выбора группы — заголовок не показываем
        self.assertNotIn('task9-exercise-title', resp.json()['html'])

    def test_chered_lag_group_exercise(self):
        # «лаг / лож» грузит пул орфограммы 12 — как на странице 5 класса
        resp = self.client.post(
            '/api/generate-chered-exercise/',
            data=json.dumps({'mode': 'seo', 'range': 'LAG'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Сервер отдаёт маски; смайлики собирает task9.js на фронте
        self.assertIn('*12*гать', data['html'])
        self.assertIn('*12*жить', data['html'])
        self.assertNotIn('*24*', data['html'])
        self.assertIn('report', data)
        # Динамический заголовок: орфограмма 12 и ссылка на страницу 5 класса,
        # без точки в конце (как заголовок тренажёра)
        self.assertIn('task9-exercise-title', data['html'])
        self.assertIn('Орфограмма № 12 (лаг / лож) изучается в 5 классе', data['html'])
        self.assertNotIn('изучается в 5 классе.', data['html'])
        self.assertIn('href="/planning/5/"', data['html'])
        self.assertIn('См. правило', data['html'])
        # Проверка штатным эндпоинтом: сессия с корректными буквами на месте
        chk = self.client.post(
            '/api/check-alphabetical-exercise/',
            data=json.dumps({'selected_letters': ['о', 'а']}),
            content_type='application/json',
        )
        self.assertEqual(chk.status_code, 200)
        self.assertEqual(len(chk.json()['results']), 2)

    def _chered(self, code):
        return self.client.post(
            '/api/generate-chered-exercise/',
            data=json.dumps({'mode': 'seo', 'range': code}),
            content_type='application/json',
        )

    def test_chered_group_rast(self):
        data = self._chered('RAST').json()
        self.assertIn('*13*стать', data['html'])
        self.assertIn('Орфограмма № 13 (раст / рос) изучается в 5 классе', data['html'])
        self.assertIn('href="/planning/5/"', data['html'])

    def test_chered_group_ber_uses_db_orthogram_24(self):
        # Заголовок № 24 (слова бер/бир лежат под орфограммой 24)
        data = self._chered('BER').json()
        self.assertIn('*24*рать', data['html'])
        self.assertIn('Орфограмма № 24 (бер / бир) изучается в 5 классе', data['html'])

    def test_chered_group_ravn(self):
        data = self._chered('RAVN').json()
        self.assertIn('*275*вный', data['html'])
        self.assertIn('Орфограмма № 27.5 (равн / ровн, мак / мок) изучается в 6 классе',
                      data['html'])
        self.assertIn('href="/planning/6/"', data['html'])

    def test_chered_group_klon(self):
        data = self._chered('KLON').json()
        self.assertIn('*271*н', data['html'])
        self.assertIn('Орфограмма № 27.1 (клан / клон) изучается в 6 классе', data['html'])
        self.assertIn('href="/planning/6/"', data['html'])

    def test_generate_rate_limit(self):
        last = None
        # 22 hits: the 1st one counts on the IP key (no session key yet),
        # the session key reaches the limit of 20 on the 22nd request.
        for _ in range(22):
            last = self._generate('seo')
        self.assertEqual(last.status_code, 429)


class Task9TrainersPageLinksTest(TestCase):
    """На странице тренажёров блок заменён карточками-ссылками."""

    def test_trainers_still_login_required(self):
        resp = self.client.get('/ege/trainers/')
        self.assertEqual(resp.status_code, 302)

    def test_trainers_template_links_only(self):
        template = (ROOT / 'main' / 'templates' / 'trainers_ege.html').read_text(encoding='utf-8')
        # Блок-карточки убран: разделы доступны ссылками после упражнения
        self.assertNotIn('task9-card', template)
        self.assertNotIn('По навигатору ФИПИ</h2>', template)
        self.assertIn('task9_report.js', template)
        self.assertIn('class="block-answer"', template)
        planning = (ROOT / 'main' / 'static' / 'js' / 'planning.js').read_text(encoding='utf-8')
        self.assertIn('insertTask9Nav', planning)
        self.assertIn('orthoepy-dictionary-link', planning)
        self.assertNotIn('task9-nav-title', planning)
