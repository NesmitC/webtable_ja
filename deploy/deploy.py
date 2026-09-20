# -*- coding: utf-8 -*-
r"""deploy/deploy.py — деплой Нейростата на прод через SSH (paramiko).

Креды читаются из локального .env (SSH_HOST/SSH_USER/SSH_PASSWORD) и НИКОГДА
не печатаются. Последовательность: бэкап БД → git pull от владельца репозитория
→ проверка HEAD → migrate main → collectstatic → graceful-перезагрузка
gunicorn (HUP: текущие запросы и идущие уроки не рвутся). Данные скрипт не
пишет никогда. Запуск: .venv\Scripts\python.exe deploy\deploy.py
Режим инспекции грязного дерева: ... deploy.py inspect
"""
import io
import sys

import paramiko

ENV = {}
for line in io.open('.env', encoding='utf-8'):
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        ENV[k.strip()] = v.strip().strip('"').strip("'")

HOST = ENV.get('SSH_HOST')
USER = ENV.get('SSH_USER')
PWD = ENV.get('SSH_PASSWORD')
if not (HOST and USER and PWD):
    print('ОТМЕНА: в .env нет SSH_HOST/SSH_USER/SSH_PASSWORD')
    sys.exit(1)

EXPECTED_HEAD = '3eff54d'
ROOT = '/home/neurostat'

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=25)
print(f'подключено: {USER}@{HOST}')


def run(cmd, timeout=240, quiet=False):
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'replace')
    err = stderr.read().decode('utf-8', 'replace')
    code = stdout.channel.recv_exit_status()
    if not quiet:
        print(f'$ {cmd}')
        print(f'[{code}]', (out.strip() or err.strip())[:1200])
    return code, out, err


def su(cmd):
    """Команда от root (бэкап, systemd)."""
    return cmd if USER == 'root' else 'sudo ' + cmd


# 0. владелец репозитория — от него дёргаем git/python, чтобы не сломать права
_, owner, _ = run(f"stat -c '%U' {ROOT}", quiet=True)
owner = owner.strip()
print('владелец репозитория:', owner)


def as_owner(cmd):
    if USER == owner:
        return cmd
    return f"sudo -u {owner} bash -c {repr(cmd)}"


if len(sys.argv) > 1 and sys.argv[1] == 'inspect':
    for f in ['main/settings.py', 'deploy/nginx.conf', 'deploy/gunicorn.service',
              '.gitignore', 'main/models.py', 'main/migrations/0001_initial.py']:
        print('=' * 20, f)
        run(as_owner(f"git -C {ROOT} diff -- {f} | head -25"))
    cli.close()
    sys.exit(0)


# 1. бэкап живой БД ДО любых изменений
code, out, _ = run(su(
    f"sudo -u postgres pg_dump neurostat > /root/backup_$(date +%F_%H%M).sql "
    f"&& ls -lh /root/backup_*.sql | tail -1"))
if code != 0:
    print('ОТМЕНА: бэкап не сделан')
    sys.exit(2)

# 2. серверный git может отставать: fetch + страховочный stash ручных правок
#    + reset к origin/main (рабочие файлы заменяются репозиторными)
code, out, err = run(as_owner(f"git -C {ROOT} fetch origin"), timeout=180)
if code != 0:
    print('ОТМЕНА: fetch не прошёл (нет доступа к origin с сервера?)')
    sys.exit(3)

code, out, _ = run(as_owner(f"git -C {ROOT} status --porcelain"))
if out.strip():
    import time as _t
    tag = _t.strftime('pre-deploy-%Y%m%d-%H%M%S')
    code, out2, _ = run(as_owner(f"git -C {ROOT} stash push -m {tag}"),
                        timeout=180)
    if code != 0:
        print('ОТМЕНА: не удалось застраховать ручные правки в stash')
        sys.exit(3)
    print('ручные правки сервера сохранены в stash:', tag)

code, out, _ = run(as_owner(f"git -C {ROOT} reset --hard origin/main"), timeout=180)
if code != 0:
    print('ОТМЕНА: reset --hard не прошёл')
    sys.exit(4)

# 4. HEAD совпал с ожидаемым
code, head, _ = run(as_owner(f"git -C {ROOT} rev-parse --short HEAD"), quiet=True)
head = head.strip()
print('HEAD на сервере:', head, '| ожидаем:', EXPECTED_HEAD)
if head != EXPECTED_HEAD:
    print('ОТМЕНА: HEAD не совпал — проверь, что запушено в origin')
    sys.exit(5)

# 5. интерпретатор: venv проекта, иначе системный python3
code, _, _ = run(f"test -x {ROOT}/.venv/bin/python", quiet=True)
PY = f'{ROOT}/.venv/bin/python' if code == 0 else 'python3'

# 6. миграции (аддитивные, данных не трогают)
code, out, _ = run(as_owner(f"cd {ROOT} && {PY} manage.py migrate main"), timeout=300)
if code != 0:
    print('ОТМЕНА: migrate упал — gunicorn НЕ перезагружаем')
    sys.exit(6)

# 7. статика
code, out, _ = run(as_owner(f"cd {ROOT} && {PY} manage.py collectstatic --noinput"),
                   timeout=300)
if code != 0:
    print('ОТМЕНА: collectstatic упал — gunicorn НЕ перезагружаем')
    sys.exit(7)

# 8. graceful-перезагрузка: мастер дожидается текущих запросов
code, out, _ = run(su("systemctl kill -s HUP gunicorn && sleep 4 "
                      "&& systemctl is-active gunicorn"))
if 'active' not in out:
    print('ВНИМАНИЕ: gunicorn не отрапортовал active — смотри systemctl status')
    sys.exit(8)

print('ДЕПЛОЙ ЗАВЕРШЁН УСПЕШНО')
cli.close()
