import os
import subprocess
import sys

scripts = [
    'seed_oge_2_4.py',
    'seed_oge_5.py',
    'seed_oge_6.py',
    'seed_oge_7.py',
    'seed_oge_8_9.py',
    'seed_oge_10_12.py'
]

print("Начинаем загрузку всех заданий ОГЭ...")
for script in scripts:
    print(f"Выполняю {script}...")
    res = subprocess.run([sys.executable, script])
    if res.returncode != 0:
        print(f"Ошибка при выполнении {script}!")
        sys.exit(1)

print("✅ Все задания ОГЭ успешно загружены в базу данных!")
