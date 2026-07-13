import requests
import random
import string
import time
import threading
import queue
import json
import base64

# ==========================================
# axz Final Proxy+Token Checker (9-letter test)
# ==========================================
TOKEN = "MTUxOTYyODIzNjc1MjAyNzY0OQ.GDOlaA.PHZxiOAe5I7w_75U0YGxcsjjb1GgS5cJh2C3_U"

CONC = 10
DELAY = 0.5
# ТЕСТИРУЕМ 9 БУКВ
MIN_LEN = 9
MAX_LEN = 9
CHARSET = string.ascii_lowercase + string.digits

URL = "https://discord.com/api/v9/users/unique-username/username-unavailable?q={}"
PROXY_FILE = "proxies.txt"

Q = queue.Queue()
tc = 0
ac = 0
lk = threading.Lock()
proxies = []

# Обязательные заголовки
try:
    uid = base64.b64decode(TOKEN.split('.')[0] + "==").decode()
    ctx = base64.b64encode(json.dumps({"location":"User Settings","location_user_id":uid}).encode()).decode()
except:
    ctx = ""
SP = "eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiRGlzY29yZCBDbGllbnQiLCJyZWxlYXNlX2NoYW5uZWwiOiJzdGFibGUiLCJ2ZXJzaW9uIjoxMjY1MjUsIm9zX3ZlcnNpb24iOiIxMC4wLjE5MDQ1Iiwib3NfYXJjaCI6Ing2NCIsInN5c3RlbV9sb2NhbGUiOiJlbi1VUyIsImJ1aWxkX251bWJlciI6MjYwMDA1fQ=="

HEADERS = {
    "Authorization": TOKEN,
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) discord/1.0.9050",
    "X-Super-Properties": SP,
    "X-Context-Properties": ctx,
    "Origin": "https://discord.com",
    "Referer": "https://discord.com/channels/@me"
}

def load_proxies():
    global proxies
    try:
        with open(PROXY_FILE, "r") as f:
            raw = [line.strip() for line in f if line.strip()]
        for p in raw:
            p = p.replace("https://", "").replace("socks4://", "").replace("socks5://", "")
            if not p.startswith("http://"):
                p = "http://" + p
            proxies.append(p)
        if not proxies:
            print("[!] proxies.txt is empty! Running on your IP.")
        else:
            print(f"[*] Loaded {len(proxies)} proxies.")
    except FileNotFoundError:
        print("[!] proxies.txt not found! Running on your IP.")

def get_proxy():
    if not proxies:
        return None
    p = proxies.pop(0)
    proxies.append(p)
    return {"http": p, "https": p}

def gen():
    return ''.join(random.choices(CHARSET, k=random.randint(MIN_LEN, MAX_LEN)))

def chk(u):
    proxy_dict = get_proxy()
    try:
        r = requests.get(URL.format(u), headers=HEADERS, proxies=proxy_dict, timeout=5)
        
        if r.status_code == 200:
            d = r.json()
            if d is True:
                return False
            elif d is False:
                print(f"\033[92m[+]\033[0m {u} - AVAILABLE!")
                with open("available_axz.txt", "a") as f:
                    f.write(f"{u}\n")
                return True
            return None

        elif r.status_code == 401:
            print(f"\033[91m[X]\033[0m 401 Token is DEAD!")
            return None
            
        elif r.status_code == 429:
            wait = r.json().get("retry_after", 5)
            print(f"\033[93m[!]\033[0m RL. Sleeping {wait}s")
            time.sleep(wait)
            return None
            
        elif r.status_code == 403:
            print(f"\033[91m[!]\033[0m 403 Proxy banned by Cloudflare")
            return None
            
        else:
            print(f"[!] HTTP {r.status_code}")
            return None

    except requests.exceptions.ProxyError:
        return None
    except Exception:
        return None

def wk():
    global tc, ac
    while True:
        u = Q.get()
        if u is None:
            break
        with lk:
            tc += 1
        r = chk(u)
        if r is True:
            with lk:
                ac += 1
        time.sleep(DELAY)
        Q.task_done()

load_proxies()
print("""
========================================
   axz Final Proxy+Token Checker
   TESTING 9-LETTER USERNAMES
========================================
""")

ts = []
for _ in range(CONC):
    t = threading.Thread(target=wk, daemon=True)
    t.start()
    ts.append(t)

try:
    while True:
        for _ in range(50):
            Q.put(gen())
        time.sleep(2)
        with lk:
            print(f"[*] {tc} checked | {ac} available")
except KeyboardInterrupt:
    pass

for _ in range(CONC):
    Q.put(None)
for t in ts:
    t.join()
print("Done.")
