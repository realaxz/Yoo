#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discord Username Checker с пулом прокси
Достигает 100+ проверок/минуту за счёт распределения нагрузки
"""

import requests
import threading
import time
import random
import json
from queue import Queue
from datetime import datetime

# ============ КОНФИГУРАЦИЯ ============
CONFIG = {
    # Список прокси (формат: protocol://user:pass@ip:port или protocol://ip:port)
    "proxies": [
        "socks5://67.201.58.190:4145",
        "socks5://72.207.113.97:4145",
        # Добавьте свои прокси здесь
    ],
    
    # Количество потоков (не больше количества прокси * 2)
    "threads": 10,
    
    # Задержка между запросами на один прокси (сек)
    # 5.5 секунд = ~10.9 запросов/мин на прокси
    "delay_per_proxy": 5.5,
    
    # Таймаут запроса (сек)
    "timeout": 10,
    
    # Имена для проверки (или генератор)
    "usernames": [],  # пустой список = генерация случайных
    
    # Генерация случайных имён
    "generate_random": True,
    "min_length": 5,
    "max_length": 8,
    
    # Файл для результатов
    "output_file": "available.txt"
}

# ============ ГЕНЕРАТОР ИМЁН ============
def generate_username():
    """Генерация случайного имени"""
    import string
    chars = string.ascii_lowercase + string.digits
    length = random.randint(CONFIG["min_length"], CONFIG["max_length"])
    name = ''.join(random.choices(chars, k=length))
    # Имя не должно начинаться с цифры
    if name[0].isdigit():
        name = 'a' + name[1:]
    return name

# ============ ПРОВЕРКА ЧЕРЕЗ ПРОКСИ ============
def check_username(username, proxy):
    """Проверка имени через указанный прокси"""
    url = f"https://discord.com/api/v9/unique-username/username-attempt-unauthed/{username}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "ru-RU,ru;q=0.9"
    }
    
    proxies = {
        "http": proxy,
        "https": proxy
    }
    
    try:
        response = requests.get(
            url,
            headers=headers,
            proxies=proxies,
            timeout=CONFIG["timeout"]
        )
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("check", {}).get("status")
            
            if status == 2:  # Доступен
                return True
            elif status == 3:  # Занят
                return False
            else:
                return None
                
        elif response.status_code == 429:
            # Rate limit на этом прокси
            return "rate_limit"
        else:
            return None
            
    except Exception as e:
        return None

# ============ ПОТОК-ВОРКЕР ============
def worker(proxy, username_queue, results, stats, lock):
    """Поток, проверяющий имена через один прокси"""
    local_count = 0
    
    while not username_queue.empty():
        try:
            username = username_queue.get(timeout=1)
        except:
            break
        
        # Проверка
        result = check_username(username, proxy)
        local_count += 1
        
        with lock:
            stats["total"] += 1
            
            if result is True:
                stats["found"] += 1
                results.append(username)
                # Сохранение в реальном времени
                with open(CONFIG["output_file"], "a") as f:
                    f.write(f"{username}\n")
                print(f"[+] НАЙДЕН: {username} (через {proxy[:30]}...)")
            elif result == "rate_limit":
                stats["rate_limits"] += 1
                print(f"[!] Rate limit на {proxy[:30]}, пауза...")
                time.sleep(10)  # Дополнительная пауза
            else:
                stats["taken"] += 1
        
        # Задержка между запросами на этом прокси
        time.sleep(CONFIG["delay_per_proxy"] + random.uniform(-0.5, 0.5))
        
        username_queue.task_done()

# ============ ОСНОВНАЯ ФУНКЦИЯ ============
def main():
    print("=" * 50)
    print("Discord Username Checker (с прокси)")
    print(f"Прокси: {len(CONFIG['proxies'])}")
    print(f"Потоков: {CONFIG['threads']}")
    print(f"Скорость: ~{len(CONFIG['proxies']) * 60 / CONFIG['delay_per_proxy']:.0f} проверок/мин")
    print("=" * 50)
    
    # Создание очереди имён
    username_queue = Queue()
    
    if CONFIG["generate_random"]:
        # Генерация 10000 случайных имён
        for _ in range(10000):
            username_queue.put(generate_username())
    else:
        for name in CONFIG["usernames"]:
            username_queue.put(name)
    
    print(f"Всего имён в очереди: {username_queue.qsize()}")
    
    # Статистика
    stats = {"total": 0, "found": 0, "taken": 0, "rate_limits": 0}
    results = []
    lock = threading.Lock()
    
    # Запуск потоков
    threads = []
    for i in range(CONFIG["threads"]):
        proxy = CONFIG["proxies"][i % len(CONFIG["proxies"])]
        t = threading.Thread(
            target=worker,
            args=(proxy, username_queue, results, stats, lock),
            daemon=True
        )
        t.start()
        threads.append(t)
    
    # Мониторинг прогресса
    start_time = time.time()
    try:
        while any(t.is_alive() for t in threads):
            with lock:
                total = stats["total"]
                found = stats["found"]
                rate = total / ((time.time() - start_time) / 60) if total > 0 else 0
            
            print(f"\rПроверено: {total} | Найдено: {found} | Скорость: {rate:.1f}/мин", end="")
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n[!] Остановка...")
    
    # Ожидание завершения
    for t in threads:
        t.join(timeout=2)
    
    # Финальная статистика
    elapsed = (time.time() - start_time) / 60
    print("\n" + "=" * 50)
    print(f"ГОТОВО!")
    print(f"  Проверено: {stats['total']}")
    print(f"  Найдено: {stats['found']}")
    print(f"  Занято: {stats['taken']}")
    print(f"  Rate Limit: {stats['rate_limits']}")
    print(f"  Время: {elapsed:.1f} мин")
    print(f"  Средняя скорость: {stats['total']/elapsed:.1f}/мин")
    print(f"  Результаты: {CONFIG['output_file']}")
    print("=" * 50)

if __name__ == "__main__":
    main()
