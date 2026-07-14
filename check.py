#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discord Pomelo Username Checker (unauthenticated)
Checks ALL 3‑ and 4‑character usernames using the allowed charset: a‑z, 0‑9, . , _
Uses a proxy pool (supports Webshare format: ip:port:user:pass).
"""

import requests
import threading
import queue
import time
import random
import sys
import itertools
from datetime import datetime

# ============ CONFIGURATION ============
CONFIG = {
    "proxy_file": "proxies.txt",          # your proxies, one per line
    "threads": 8,                         # adjust to proxy count * 2
    "delay_per_proxy": 6.0,               # seconds between requests on same proxy
    "jitter": 0.5,
    "timeout": 12,
    "max_retries": 3,
    
    # Username generation settings
    "min_length": 3,
    "max_length": 4,
    "charset": "abcdefghijklmnopqrstuvwxyz0123456789._",  # includes . and _
    "excluded_words": ["discord", "admin", "system", "support", "null", "undefined", "test"],
    
    "output_file": "available.txt",
    "log_file": "checker.log",
    "user_agents": [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
}

# ============ PROXY LOADING ============
def load_proxies(filename):
    """Load proxies; supports ip:port:user:pass (Webshare style)"""
    proxies = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '://' in line:
                    proxies.append(line)
                    continue
                parts = line.split(':')
                if len(parts) == 4:
                    ip, port, user, password = parts
                    proxies.append(f"http://{user}:{password}@{ip}:{port}")
                elif len(parts) == 2:
                    ip, port = parts
                    proxies.append(f"http://{ip}:{port}")
                else:
                    print(f"[!] Skipping invalid proxy: {line}")
    except FileNotFoundError:
        print(f"[!] File {filename} not found.")
        sys.exit(1)
    return proxies

def test_proxy(proxy):
    """Check if proxy responds."""
    try:
        r = requests.get("https://discord.com/api/v9/unique-username/username-attempt-unauthed/test",
                         proxies={"http": proxy, "https": proxy}, timeout=10)
        return r.status_code in (200, 429, 403, 404)
    except:
        return False

# ============ USERNAME GENERATOR (BRUTE‑FORCE) ============
def username_generator():
    """Generate all valid usernames of length 3 and 4 from the charset."""
    chars = CONFIG["charset"]
    forbidden_start_end = "._"
    excluded = set(CONFIG["excluded_words"])
    
    for length in range(CONFIG["min_length"], CONFIG["max_length"] + 1):
        for combo in itertools.product(chars, repeat=length):
            name = ''.join(combo)
            # Basic Discord rules
            if name[0] in forbidden_start_end or name[-1] in forbidden_start_end:
                continue
            if '..' in name or '._' in name or '_.' in name or '__' in name:
                continue
            if name.lower() in excluded:
                continue
            yield name

# ============ CHECK USERNAME ============
def check_username(username, proxy, user_agent):
    """Return True (available), False (taken), 'rate_limit', 'blocked', or None."""
    url = f"https://discord.com/api/v9/unique-username/username-attempt-unauthed/{username}"
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive"
    }
    proxies = {"http": proxy, "https": proxy}
    
    for attempt in range(CONFIG["max_retries"]):
        try:
            resp = requests.get(url, headers=headers, proxies=proxies, timeout=CONFIG["timeout"])
            status = resp.status_code
            
            if status == 200:
                data = resp.json()
                check_status = data.get("check", {}).get("status")
                if check_status == 2:
                    return True
                elif check_status == 3:
                    return False
                else:
                    return None
            elif status == 429:
                return "rate_limit"
            elif status in (403, 401):
                return "blocked"
            elif status == 400:
                # This often happens for short usernames (unauthenticated limitation)
                print(f"[!] 400 Bad Request for '{username}' – likely too short for unauthenticated endpoint")
                return None
            else:
                if attempt < CONFIG["max_retries"] - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
        except Exception:
            if attempt < CONFIG["max_retries"] - 1:
                time.sleep(1)
                continue
            return None
    return None

# ============ WORKER ============
def worker(proxy_pool, username_queue, stats, lock, stop_event):
    local_proxy = None
    while not stop_event.is_set():
        if local_proxy is None:
            with lock:
                if proxy_pool:
                    local_proxy = random.choice(proxy_pool)
                else:
                    time.sleep(1)
                    continue
        
        try:
            username = username_queue.get(timeout=2)
        except queue.Empty:
            break
        
        user_agent = random.choice(CONFIG["user_agents"])
        result = check_username(username, local_proxy, user_agent)
        
        with lock:
            stats["total"] += 1
            if result is True:
                stats["found"] += 1
                with open(CONFIG["output_file"], "a") as f:
                    f.write(f"{username}\n")
                print(f"[+] {username} → AVAILABLE")
            elif result is False:
                stats["taken"] += 1
                if stats["total"] % 50 == 0:
                    print(f"[-] {username} → taken")
            elif result == "rate_limit":
                stats["rate_limits"] += 1
                print(f"[!] Rate limit on {local_proxy[:30]}, sleeping 10s")
                time.sleep(10)
                local_proxy = None
            elif result == "blocked":
                stats["blocked"] += 1
                print(f"[X] Proxy {local_proxy[:30]} blocked, switching")
                local_proxy = None
            else:
                stats["errors"] += 1
                # if 400, we might still want to continue but maybe switch proxy
                local_proxy = None
        
        delay = CONFIG["delay_per_proxy"] + random.uniform(-CONFIG["jitter"], CONFIG["jitter"])
        if delay < 1:
            delay = 1
        time.sleep(delay)
        username_queue.task_done()

# ============ MAIN ============
def main():
    print("=" * 60)
    print("  Discord 3‑4 char Username Brute‑Forcer (unauthenticated)")
    print("=" * 60)
    
    # Load proxies
    proxies = load_proxies(CONFIG["proxy_file"])
    print(f"[*] Loaded proxies: {len(proxies)}")
    
    # Validate
    print("[*] Testing proxies...")
    working_proxies = []
    for p in proxies:
        if test_proxy(p):
            working_proxies.append(p)
            print(f"  ✓ {p[:30]}... alive")
        else:
            print(f"  ✗ {p[:30]}... dead")
    if not working_proxies:
        print("[!] No working proxies. Exiting.")
        sys.exit(1)
    print(f"[*] Working proxies: {len(working_proxies)}")
    
    # Estimate speed
    speed = len(working_proxies) * (60 / CONFIG["delay_per_proxy"])
    print(f"[*] Estimated speed: ~{speed:.0f} checks/min")
    
    # Generate all usernames (as generator) and fill queue
    username_queue = queue.Queue()
    total_names = 0
    print("[*] Generating all 3‑ and 4‑character usernames...")
    for name in username_generator():
        username_queue.put(name)
        total_names += 1
        if total_names % 100000 == 0:
            print(f"  Generated {total_names} names...")
    print(f"[*] Total usernames to check: {total_names}")
    
    # Stats and threads
    stats = {"total": 0, "found": 0, "taken": 0, "rate_limits": 0, "blocked": 0, "errors": 0}
    lock = threading.Lock()
    stop_event = threading.Event()
    
    threads = []
    for _ in range(CONFIG["threads"]):
        t = threading.Thread(target=worker,
                             args=(working_proxies, username_queue, stats, lock, stop_event),
                             daemon=True)
        t.start()
        threads.append(t)
    
    print(f"[*] Started {len(threads)} threads")
    print("[*] Press Ctrl+C to stop\n")
    
    start = time.time()
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(5)
            with lock:
                total = stats["total"]
                found = stats["found"]
                elapsed = (time.time() - start) / 60
                rate = total / elapsed if elapsed > 0 else 0
                remaining = username_queue.qsize()
            print(f"[{elapsed:.1f} min] Checked: {total} | Found: {found} | Speed: {rate:.1f}/min | Remaining: {remaining}")
    except KeyboardInterrupt:
        print("\n[!] Stopping...")
        stop_event.set()
    
    for t in threads:
        t.join(timeout=2)
    
    elapsed = (time.time() - start) / 60
    print("\n" + "=" * 60)
    print("  FINAL STATISTICS")
    print("=" * 60)
    print(f"  Total checked:      {stats['total']}")
    print(f"  Available found:    {stats['found']}")
    print(f"  Taken:              {stats['taken']}")
    print(f"  Rate limits:        {stats['rate_limits']}")
    print(f"  Blocked proxies:    {stats['blocked']}")
    print(f"  Errors:             {stats['errors']}")
    print(f"  Runtime:            {elapsed:.1f} min")
    print(f"  Avg speed:          {stats['total']/elapsed:.1f}/min")
    print(f"  Results:            {CONFIG['output_file']}")
    print("=" * 60)

if __name__ == "__main__":
    main()
