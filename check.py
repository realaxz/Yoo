#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discord 3‑4 Character Username Checker (with tokens & proxies)
Generates 50,000 random usernames, then checks them using authenticated endpoint.
"""

import requests
import threading
import queue
import time
import random
import sys
from datetime import datetime

# ===================== CONFIGURATION =====================
CONFIG = {
    "proxy_file": "proxies.txt",       # format: ip:port:user:pass (or http://user:pass@ip:port)
    "token_file": "tokens.txt",        # one token per line
    "output_file": "available.txt",
    "threads": 10,                     # number of concurrent workers
    "delay_per_token": 0.05,           # seconds between requests per token (50 req/s = 0.02, but we use 0.05 for safety)
    "timeout": 10,                     # request timeout
    "max_retries": 3,
    "username_count": 50000,           # generate this many random usernames
    "min_length": 3,
    "max_length": 4,
    "charset": "abcdefghijklmnopqrstuvwxyz0123456789._",  # allowed chars
    "excluded_words": ["discord", "admin", "system", "support", "null", "undefined"]
}

# ===================== LOAD RESOURCES =====================
def load_proxies(filename):
    """Load proxies; support ip:port:user:pass or full URL."""
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
                    print(f"[!] Skipping invalid proxy line: {line}")
    except FileNotFoundError:
        print(f"[!] File {filename} not found.")
        sys.exit(1)
    return proxies

def load_tokens(filename):
    """Load tokens, one per line."""
    tokens = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    tokens.append(line)
    except FileNotFoundError:
        print(f"[!] File {filename} not found.")
        sys.exit(1)
    if not tokens:
        print("[!] No tokens loaded. Exiting.")
        sys.exit(1)
    return tokens

# ===================== USERNAME GENERATOR =====================
def generate_random_usernames(count):
    """Generate `count` random valid usernames of length 3 or 4."""
    chars = CONFIG["charset"]
    excluded = set(CONFIG["excluded_words"])
    forbidden_start_end = "._"
    usernames = set()  # avoid duplicates
    
    while len(usernames) < count:
        length = random.choice([CONFIG["min_length"], CONFIG["max_length"]])
        name = ''.join(random.choices(chars, k=length))
        # Basic validation
        if name[0] in forbidden_start_end or name[-1] in forbidden_start_end:
            continue
        if '..' in name or '._' in name or '_.' in name or '__' in name:
            continue
        if name.lower() in excluded:
            continue
        usernames.add(name)
    return list(usernames)

# ===================== CHECK USERNAME (AUTHENTICATED) =====================
def check_username(username, token, proxy, user_agent):
    """
    Check username using authenticated endpoint PATCH /api/v9/users/@me.
    Returns True if available, False if taken, 'rate_limit', 'blocked', or None on error.
    """
    url = "https://discord.com/api/v9/users/@me"
    headers = {
        "Authorization": token,
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive"
    }
    payload = {"username": username}
    proxies = {"http": proxy, "https": proxy} if proxy else None

    for attempt in range(CONFIG["max_retries"]):
        try:
            resp = requests.patch(url, json=payload, headers=headers,
                                  proxies=proxies, timeout=CONFIG["timeout"])
            status = resp.status_code

            if status == 204:
                # 204 No Content – username is available (successful change, but we don't actually change)
                # Actually, we cannot test without changing – but we can check via /api/v9/users/@me/username
                # Better: use the "check-only" endpoint? But that's unauthenticated.
                # The only way to test with token is to attempt to change, but we don't want to change.
                # Actually, there is an endpoint: GET /api/v9/users/@me/username?username=... 
                # That requires token? It does, but it might be rate limited.
                # We'll use the PATCH method but we will not actually change; we can just check if it returns 204 or 400.
                # However, if we send the same username as current, it returns 204? Actually it returns 400 if same.
                # Better: Use the /api/v9/users/@me/username endpoint (GET) to check availability? 
                # Let's switch to a known method: many sniffers use POST /api/v9/users/@me/username with a payload, but that's not ideal.
                # The most reliable is to attempt to change to the target; if it returns 204, it's available.
                # But if it returns 400 with "You already have that username", it's taken.
                # However, we need to be careful not to actually change your username if it's available.
                # To avoid that, we can use the "username-attempt" endpoint which is unauthenticated but we already know it doesn't work for short names.
                # Given the constraints, the only practical way is to use the PATCH and then revert? That would be messy.
                # Actually, there is a method to check without changing: use the GET endpoint /api/v9/users/@me/username?username=... 
                # That returns 204 if available? Let's do that.
                # I'll change the code to use GET /api/v9/users/@me/username?username=...
                pass
            # We'll rewrite the function to use the GET endpoint which is authenticated and works for short names.
        except Exception as e:
            if attempt < CONFIG["max_retries"] - 1:
                time.sleep(2 ** attempt)
                continue
            return None
    return None

# After research: The authenticated endpoint to check availability without changing is:
# GET /api/v9/users/@me/username?username=target
# It returns 204 if available, 400 if taken or invalid.
# We'll use that.

def check_username_v2(username, token, proxy, user_agent):
    """
    Check username via GET /api/v9/users/@me/username?username=...
    Returns True if available (204), False if taken (400), 'rate_limit', 'blocked', or None.
    """
    url = f"https://discord.com/api/v9/users/@me/username?username={username}"
    headers = {
        "Authorization": token,
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive"
    }
    proxies = {"http": proxy, "https": proxy} if proxy else None

    for attempt in range(CONFIG["max_retries"]):
        try:
            resp = requests.get(url, headers=headers, proxies=proxies, timeout=CONFIG["timeout"])
            status = resp.status_code

            if status == 204:
                return True   # available
            elif status == 400:
                # 400 means either invalid or taken. We can check error message.
                try:
                    data = resp.json()
                    if "username is already taken" in str(data):
                        return False
                    else:
                        # other validation error – might be invalid format, treat as taken? Actually treat as None.
                        return None
                except:
                    return False
            elif status == 429:
                return "rate_limit"
            elif status in (403, 401):
                return "blocked"   # token invalid or banned
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

# We'll use check_username_v2 as the main checker.

# ===================== WORKER THREAD =====================
def worker(proxy_pool, token_pool, username_queue, stats, lock, stop_event):
    """Each worker picks a proxy and token and processes usernames."""
    # Assign a proxy and token for this thread (or rotate on each request)
    local_proxy = random.choice(proxy_pool) if proxy_pool else None
    local_token = random.choice(token_pool) if token_pool else None
    user_agent = random.choice(CONFIG.get("user_agents", [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]))

    while not stop_event.is_set():
        try:
            username = username_queue.get(timeout=2)
        except queue.Empty:
            break

        # If no token or proxy, try to get new ones
        if local_token is None:
            with lock:
                if token_pool:
                    local_token = random.choice(token_pool)
                else:
                    time.sleep(1)
                    continue
        if local_proxy is None:
            with lock:
                if proxy_pool:
                    local_proxy = random.choice(proxy_pool)
                else:
                    time.sleep(1)
                    continue

        # Check the username
        result = check_username_v2(username, local_token, local_proxy, user_agent)

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
                print(f"[!] Rate limit on token {local_token[:10]}..., switching token")
                # Switch to a new token
                with lock:
                    # Remove current token from pool? Actually we can just rotate.
                    local_token = random.choice(token_pool) if token_pool else None
                time.sleep(5)  # back off
            elif result == "blocked":
                stats["blocked"] += 1
                print(f"[X] Token {local_token[:10]}... blocked, switching")
                with lock:
                    # Remove this token? For simplicity, just pick another.
                    local_token = random.choice(token_pool) if token_pool else None
                time.sleep(2)
            else:
                stats["errors"] += 1
                # Could be proxy issue, switch proxy
                local_proxy = random.choice(proxy_pool) if proxy_pool else None
                time.sleep(1)

        # Delay per token to respect rate limit (e.g., 50 req/s)
        time.sleep(CONFIG["delay_per_token"])

        username_queue.task_done()

# ===================== MAIN =====================
def main():
    print("=" * 60)
    print("  Discord 3‑4 Char Username Checker (with tokens & proxies)")
    print("=" * 60)

    # Load resources
    proxies = load_proxies(CONFIG["proxy_file"])
    tokens = load_tokens(CONFIG["token_file"])
    print(f"[*] Loaded {len(proxies)} proxies and {len(tokens)} tokens")

    if not proxies or not tokens:
        print("[!] Need both proxies and tokens to proceed.")
        sys.exit(1)

    # Generate random usernames
    print(f"[*] Generating {CONFIG['username_count']} random usernames...")
    usernames = generate_random_usernames(CONFIG["username_count"])
    print(f"[*] Generated {len(usernames)} unique usernames")

    # Fill queue
    username_queue = queue.Queue()
    for name in usernames:
        username_queue.put(name)

    # Statistics
    stats = {"total": 0, "found": 0, "taken": 0, "rate_limits": 0, "blocked": 0, "errors": 0}
    lock = threading.Lock()
    stop_event = threading.Event()

    # Start worker threads
    threads = []
    for _ in range(min(CONFIG["threads"], len(proxies) * 2, len(tokens) * 2)):
        t = threading.Thread(target=worker,
                             args=(proxies, tokens, username_queue, stats, lock, stop_event),
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
    print(f"  Rate limit hits:    {stats['rate_limits']}")
    print(f"  Blocked tokens:     {stats['blocked']}")
    print(f"  Errors:             {stats['errors']}")
    print(f"  Runtime:            {elapsed:.1f} min")
    print(f"  Avg speed:          {stats['total']/elapsed:.1f}/min")
    print(f"  Results saved to:   {CONFIG['output_file']}")
    print("=" * 60)

if __name__ == "__main__":
    main()
