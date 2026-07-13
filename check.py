import requests
import itertools
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

# Discord username checker для 4-символьных ников
# Поддержка: a-z, 0-9, ., _
# Только прокси (http/s)
# Многопоточный, с ротацией прокси

# === НАСТРОЙКИ ===
PROXIES_FILE = "proxies.txt"  # Каждая строка: http://user:pass@ip:port или http://ip:port
THREADS = 50                  # Количество потоков
DELAY = 0.3                   # Задержка между запросами (сек)
TIMEOUT = 10
CHECK_ENDPOINT = "https://discord.com/api/v9/users"  # Базовый эндпоинт, будем проверять существование

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

# Глобальные переменные
available = []
checked = 0
lock = threading.Lock()

def load_proxies():
    """Загрузка прокси из файла"""
    try:
        with open(PROXIES_FILE, "r", encoding="utf-8") as f:
            proxies = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        print(f"[+] Загружено {len(proxies)} прокси")
        return proxies
    except FileNotFoundError:
        print("[-] Файл proxies.txt не найден. Создай его и положи прокси.")
        return []

def is_username_available(username, proxy):
    """Проверка доступности ника через Discord API"""
    global checked
    try:
        # Простой способ — попытка получить пользователя по имени (неофициально)
        # Discord может вернуть 404 если ник свободен или 200 если занят
        # Альтернатива: проверка через lookup
        proxy_dict = {"http": proxy, "https": proxy}
        
        # Один из рабочих методов — запрос к /users с поиском
        resp = requests.get(
            f"https://discord.com/api/v9/users/@{username}",
            headers=headers,
            proxies=proxy_dict,
            timeout=TIMEOUT
        )
        
        with lock:
            checked += 1
            if resp.status_code == 404:
                available.append(username)
                print(f"[+] СВОБОДЕН: {username} | Прокси: {proxy[:30]}...")
                return True
            elif resp.status_code == 200:
                print(f"[-] Занят: {username}")
                return False
            else:
                print(f"[?] Неизвестный код {resp.status_code} для {username}")
                return False
    except Exception as e:
        return False

def generate_combinations():
    """Генерация всех 4-символьных комбинаций"""
    chars = "abcdefghijklmnopqrstuvwxyz0123456789._"
    print(f"[+] Генерация комбинаций из {len(chars)} символов...")
    # 4 символа: ~ 40^4 = 2.56 млн — реально, но фильтруем
    for combo in itertools.product(chars, repeat=4):
        username = "".join(combo)
        # Discord правила: не начинать/заканчивать на . _ иногда, но пропускаем
        yield username

def worker(username, proxies):
    """Рабочий поток"""
    proxy = random.choice(proxies)
    is_username_available(username, proxy)
    time.sleep(DELAY + random.uniform(0, 0.2))

def main():
    proxies = load_proxies()
    if not proxies:
        return
    
    print("[*] Запуск чекера 4L Discord usernames...")
    print("[*] Символы: a-z 0-9 . _")
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = []
        for username in generate_combinations():
            futures.append(executor.submit(worker, username, proxies))
            # Ограничим для теста, но можно убрать
            if len(futures) > 10000:  # Пример лимита, убери для полного перебора
                break
        
        for future in as_completed(futures):
            pass  # Просто ждём
    
    print("\n[!] Проверка завершена!")
    print(f"Проверено: {checked} ников")
    print(f"Свободно: {len(available)}")
    
    if available:
        with open("available_usernames.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(available))
        print("[+] Свободные ники сохранены в available_usernames.txt")

if __name__ == "__main__":
    main()
