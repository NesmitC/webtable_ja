Deployment guide (Ubuntu/Debian + Nginx + Gunicorn + PostgreSQL)

1) Server prepare
- sudo apt update && sudo apt upgrade -y
- sudo apt install -y git python3-venv python3-pip nginx postgresql

2) Database
- sudo -u postgres psql -c "CREATE USER myuser WITH PASSWORD 'mypassword';"
- sudo -u postgres psql -c "CREATE DATABASE neurostat OWNER myuser;"

3) App setup
- sudo mkdir -p /srv/webtable && sudo chown $USER:$USER /srv/webtable
- cd /srv/webtable
- python3 -m venv .venv && source .venv/bin/activate
- git clone <YOUR_REPO_URL> .
- pip install -r requirements.txt
- cp deploy/.env.example .env    # then edit values
- python manage.py collectstatic --noinput
- python manage.py migrate

4) Gunicorn (temporary run)
- .venv/bin/gunicorn main.wsgi:application --bind 127.0.0.1:8000

5) Nginx
- sudo cp deploy/nginx.conf /etc/nginx/sites-available/webtable
- sudo ln -s /etc/nginx/sites-available/webtable /etc/nginx/sites-enabled/webtable
- sudo nginx -t && sudo systemctl reload nginx

6) Systemd service
- sudo cp deploy/gunicorn.service /etc/systemd/system/gunicorn-webtable.service
- sudo systemctl daemon-reload
- sudo systemctl enable --now gunicorn-webtable

7) TLS (optional but recommended)
- sudo apt install -y certbot python3-certbot-nginx
- sudo certbot --nginx -d your.domain

Troubleshooting
- Check logs: journalctl -u gunicorn-webtable -e
- Nginx: sudo tail -f /var/log/nginx/error.log

