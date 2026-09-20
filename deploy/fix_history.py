# -*- coding: utf-8 -*-
"""deploy/fix_history.py — лечение истории миграций прода.

Прод-БД мигрирована параллельной цепочкой файлов 0009–0022 (untracked),
которой нет в репозитории. Схема прода при этом = схема репозитория на 0087
(проверено сравнением колонок: не хватает только digest/test_data из 0088).
Лечение: бэкап → удалить параллельные файлы → переписать django_migrations
на репозиторную цепочку 0001–0087 как applied → migrate применяет 0088.
Данных не касается. Креды из .env.
"""
import io
import os

import paramiko

PROJ = r'C:\Users\alex\Jango\webtable_ja_project'
ROOT = '/home/neurostat'

ENV = {}
for line in io.open(os.path.join(PROJ, '.env'), encoding='utf-8'):
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        ENV[k.strip()] = v.strip().strip('"').strip("'")

# имена репозиторных миграций до 0088 включительно-1
mig_dir = os.path.join(PROJ, 'main', 'migrations')
names = sorted(f[:-3] for f in os.listdir(mig_dir)
               if f.endswith('.py') and f != '__init__.py')
names = [n for n in names if not n.startswith('0088_')]
print('репозиторных миграций для пометки applied:', len(names))

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(ENV['SSH_HOST'], username=ENV['SSH_USER'],
            password=ENV['SSH_PASSWORD'], timeout=25)


def run(cmd, timeout=300):
    _, so, se = cli.exec_command(cmd, timeout=timeout)
    out = so.read().decode('utf-8', 'replace')
    err = se.read().decode('utf-8', 'replace')
    code = so.channel.recv_exit_status()
    print(f'$ {cmd[:150]}')
    print(f'[{code}]', (out or err).strip()[:1500])
    return code, out, err


def owner(cmd):
    return f"sudo -u www-data bash -c {repr(cmd)}"


# 1. страховочный бэкап перед правкой истории
code, _, _ = run("sudo -u postgres pg_dump neurostat > /root/backup_pre_history_fix.sql "
                 "&& ls -lh /root/backup_pre_history_fix.sql")
if code != 0:
    raise SystemExit('бэкап не сделан — стоп')

# 2. удаляем параллельные файлы (только те, что реально лежат untracked)
code, out, _ = run(owner(f"git -C {ROOT} status --porcelain -- main/migrations"))
untracked = [ln[3:].strip().split('/')[-1] for ln in out.splitlines()
             if ln.startswith('?? main/migrations')]
print('untracked миграции на сервере:', untracked)
for f in untracked:
    run(f"rm -f {ROOT}/main/migrations/{f}")

# 3. переписываем историю: цепочка репозитория как applied
values = ', '.join(f"('main', '{n}', now())" for n in names)
sql = (f"BEGIN; DELETE FROM django_migrations WHERE app='main'; "
       f"INSERT INTO django_migrations (app, name, applied) VALUES {values}; COMMIT;")
code, out, err = run(f"sudo -u postgres psql neurostat -c {repr(sql)}")
if code != 0:
    raise SystemExit('перепись истории не прошла — стоп')

# 4. migrate применяет только 0088
code, out, _ = run(owner(f"cd {ROOT} && .venv/bin/python manage.py migrate main"))
if code != 0:
    raise SystemExit('migrate не прошёл — стоп, смотри вывод')

# 5. статика + graceful-перезагрузка
run(owner(f"cd {ROOT} && .venv/bin/python manage.py collectstatic --noinput"))
run("systemctl kill -s HUP gunicorn && sleep 4 && systemctl is-active gunicorn")

# 6. хвост истории и разница stash против HEAD (что было в ручных правках)
run(owner(f"cd {ROOT} && .venv/bin/python manage.py showmigrations main | tail -4"))
run(owner(f"git -C {ROOT} diff --stat stash@{{0}} HEAD | tail -5"))
cli.close()
print('ИСТОРИЯ ВЫЛЕЧЕНА')
