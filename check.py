import requests
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

# УЛУЧШЕННЫЙ Discord 4L Username Checker
# Только рандом генерация + прокси
# Быстрее, стабильнее, меньше нагрузки

# === НАСТРОЙКИ ===
PROXIES_FILE = "proxies.txt"
THREADS = 30
REQUESTS_PER_PROXY = 5      # Сколько запросов на один прокси перед сменой
TIMEOUT = 8
DELAY = 0.25

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

available = []
checked = 0
lock = threading.Lock()

def load_proxies():
    try:
        with open(PROXIES_FILE, "r", encoding="utf-8") as f:
            proxies = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        print(f"[+] Загружено {len(proxies)} прокси")
        return proxies
    except:
        print("[-] proxies.txt не найден")
        return []

def check_username(username, proxy):
    global checked
    try:
        proxy_dict = {"http": proxy, "https": proxy}
        
        # Более надёжный метод проверки
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
                print(f"[+] СВОБОДЕН → @{username}")
                return True
            elif resp.status_code in (200, 204):
                print(f"[-] Занят → @{username}")
            else:
                print(f"[?] {resp.status_code} | {username}")
    except:
        pass
    return False

def random_username():
    chars = "abcdefghijklmnopqrstuvwxyz0123456789._"
    return ''.join(random.choice(chars) for _ in range(4))

def worker(proxies):
    while True:  # Бесконечный режим — останови Ctrl+C
        proxy = random.choice(proxies)
        for _ in range(REQUESTS_PER_PROXY):
            username = random_username()
            check_username(username, proxy)
            time.sleep(DELAY + random.uniform(0, 0.15))

def main():
    proxies = load_proxies()
    if not proxies:
        return
    
    print("[*] Запуск улучшенного 4L Discord checker...")
    print("[*] Режим: случайная генерация + ротация прокси")
    
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = [executor.submit(worker, proxies) for _ in range(THREADS)]
        try:
            for future in as_completed(futures):
                future.result()
        except KeyboardInterrupt:
            print("\n[!] Остановлено пользователем")

    print(f"\nПроверено: {checked} | Найдено свободных: {len(available)}")
    if available:
        with open("free_usernames.txt", "a", encoding="utf-8") as f:
            f.write("\n".join(available) + "\n")
        print("[+] Свободные ники дописаны в free_usernames.txt")

if __name__ == "__main__":
    main()
