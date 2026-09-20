# -*- coding: utf-8 -*-
"""deploy/probe.py — быстрое состояние прода: HEAD, чистота дерева, миграции,
gunicorn, статика. Креды из .env, ничего не меняет."""
import io
import sys

import paramiko

ENV = {}
for line in io.open('.env', encoding='utf-8'):
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        ENV[k.strip()] = v.strip().strip('"').strip("'")

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(ENV['SSH_HOST'], username=ENV['SSH_USER'],
            password=ENV['SSH_PASSWORD'], timeout=25)


def run(cmd):
    _, so, se = cli.exec_command(cmd, timeout=120)
    out = so.read().decode('utf-8', 'replace')
    code = so.channel.recv_exit_status()
    return code, (out or se.read().decode('utf-8', 'replace')).strip()


def git(cmd):
    return run(f"sudo -u www-data bash -c {repr(cmd)}")[1]


print('HEAD:', git('git -C /home/neurostat rev-parse --short HEAD'))
print('dirty-строк:', len(git('git -C /home/neurostat status --porcelain').splitlines()))
print('stash:', git('git -C /home/neurostat stash list | head -3'))
print('миграции (хвост):')
print(run("sudo -u www-data bash -c 'cd /home/neurostat && .venv/bin/python manage.py "
          "showmigrations main | tail -6'")[1])
print('gunicorn:', run('systemctl is-active gunicorn')[1])
print('collectstatic-файл checkpoint.js:',
      run('ls -la /home/neurostat/staticfiles/js/checkpoint.js 2>/dev/null | wc -l')[1])
cli.close()
