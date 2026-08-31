import paramiko
import os
from dotenv import load_dotenv

load_dotenv()

# Настройки из переменных окружения
hostname = os.getenv('SSH_HOST', '91.197.96.233')  # Второе значение — дефолт
username = os.getenv('SSH_USER', 'root')
password = os.getenv('SSH_PASSWORD')  # 🔴 Обязательно из .env!
remote_file = os.getenv('SSH_REMOTE_FILE', '/home/neurostat/ortho_examples.json')
local_file = os.getenv('SSH_LOCAL_FILE', 'C:/Users/alex/Jango/webtable_ja_project/ortho_examples.json')

# Проверка: если пароль не задан — ошибка
if not password:
    raise ValueError("❌ SSH_PASSWORD не задан в переменных окружения! Проверьте файл .env")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, username=username, password=password)

sftp = ssh.open_sftp()
sftp.get(remote_file, local_file)
sftp.close()
ssh.close()

print(f"✅ Файл скачан: {local_file}")
