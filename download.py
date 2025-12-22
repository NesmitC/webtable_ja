import paramiko
import os

# Настройки
hostname = '91.197.96.233'  # или IP адрес сервера
username = 'root'
password = 'i6a6amjM7MyODBGY'
remote_file = '/home/neurostat/ortho_examples.json'
local_file = 'C:/Users/alex/Jango/webtable_ja_project/ortho_examples.json'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, username=username, password=password)

sftp = ssh.open_sftp()
sftp.get(remote_file, local_file)
sftp.close()
ssh.close()

print(f"Файл скачан: {local_file}")