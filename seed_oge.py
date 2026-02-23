import os
import subprocess
import sys

scripts = [
    'seed_oge_1_3.py',
    'seed_oge_4.py',
    'seed_oge_5.py',
    'seed_oge_6.py',
    'seed_oge_7_8.py',
    'seed_oge_9_11.py'
]

print("Начинаем загрузку всех заданий ОГЭ...")
for script in scripts:
    print(f"Выполняю {script}...")
    res = subprocess.run([sys.executable, script])
    if res.returncode != 0:
        print(f"Ошибка при выполнении {script}!")
        sys.exit(1)

print("✅ Все задания ОГЭ успешно загружены в базу данных!")
