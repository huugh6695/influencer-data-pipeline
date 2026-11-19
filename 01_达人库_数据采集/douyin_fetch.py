"""抖音侧数据抓取（第二数据源，iesdouyin 官方 web API）

用法:
  python3 douyin_fetch.py --all               # 给所有有 sec_uid 的达人补抖音数据
  python3 douyin_fetch.py --ids 7,8,9         # 指定 id
  python3 douyin_fetch.py --dry-run           # 统计待补数量

数据来源: https://www.iesdouyin.com/web/api/v2/user/info/?sec_uid=xxx
字段: nickname/signature/aweme_count/follower_count/total_favorited/following_count/
      city/province/country/gender/unique_id/custom_verify 等 26 个

用途: 与蝉妈妈数据互为校验 + 补充抖音侧独有字段（如 verified_reason 认证信息）
"""
import sqlite3, os, sys, json, time, argparse, urllib.request, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception: pass

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "influencers.db")

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
API = "https://www.iesdouyin.com/web/api/v2/user/info/?sec_uid={}"

stats_lock = threading.Lock()
STATS = {'ok': 0, 'fail': 0, 'skip': 0}

def fetch_user(sec_uid, timeout=12):
    url = API.format(sec_uid)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8", errors="ignore"))
    ui = data.get("user_info") or {}
    if not ui:
        return None
    return ui

def process_one(rid, sec_uid, delay=0):
    if delay:
        time.sleep(delay)
    try:
        ui = fetch_user(sec_uid)
    except Exception as e:
        with stats_lock:
            STATS['fail'] += 1
        return rid, False, str(e)[:80]

    if not ui:
        with stats_lock:
            STATS['skip'] += 1
        return rid, False, "无数据"

    data = {}
    m = {
        'nickname': 'nickname',
        'signature': 'bio',
        'aweme_count': 'works_count',
        'following_count': 'follows_count',
        'total_favorited': 'likes_count',
        'unique_id': 'account_id',
        'custom_verify': None,
    }
    for src, dst in m.items():
        if dst and ui.get(src) not in (None, '', 0):
            data[dst] = ui[src]
    mfc = ui.get('mplatform_followers_count')
    if mfc:
        data['fans_count'] = mfc
    g = ui.get('gender')
    if g == 1:
        data['gender'] = '男'
    elif g == 2:
        data['gender'] = '女'
    reason = ui.get('enterprise_verify_reason') or ui.get('verified_reason') or ''
    if reason:
        data['fit_note'] = reason[:200]

    conn = sqlite3.connect(DB)
    if data:
        sets = []
        vals = []
        for k, v in data.items():
            sets.append(f"{k}=?")
            vals.append(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
        sets.append("updated_at=datetime('now','localtime')")
        conn.execute(f"UPDATE influencers SET {', '.join(sets)} WHERE id=?", vals + [rid])
        conn.commit()
    conn.close()
    with stats_lock:
        STATS['ok'] += 1
    return rid, True, ""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="全部有 sec_uid 的达人")
    ap.add_argument("--ids", help="指定 id 列表")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=3, help="并发数（控制请求频率，默认3）")
    ap.add_argument("--delay", type=float, default=0.3, help="每条间隔秒（默认0.3）")
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    if args.ids:
        ids = [int(x) for x in args.ids.split(',') if x.strip()]
        ph = ','.join('?' * len(ids))
        rows = conn.execute(f"SELECT id, sec_uid, profile_url FROM influencers WHERE id IN ({ph})", ids).fetchall()
    else:
        rows = conn.execute("SELECT id, sec_uid, profile_url FROM influencers WHERE profile_url LIKE '%douyin.com/user/%' OR (sec_uid IS NOT NULL AND sec_uid != '')").fetchall()
    conn.close()

    import re
    rows2 = []
    for rid, sec_uid, profile_url in rows:
        if not sec_uid and profile_url:
            m = re.search(r'/user/([^/?]+)', profile_url)
            sec_uid = m.group(1) if m else ''
        rows2.append((rid, sec_uid))
    rows = [r for r in rows2 if r[1]]

    if args.dry_run:
        print(f"有 sec_uid 的达人: {len(rows)} 条，可补抖音数据")
        return

    if not rows:
        print("没有可补的达人")
        return

    print(f"📋 待补抖音数据: {len(rows)} 条 | 并发 {args.workers}")
    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(process_one, rid, sec, args.delay): (rid, sec) for rid, sec in rows}
        for fut in as_completed(futs):
            rid, sec = futs[fut]
            try:
                _, ok, msg = fut.result()
                done += 1
                if done % 50 == 0 or not ok:
                    print(f"[{done}/{len(rows)}] {'✅' if ok else '❌'} id={rid} {msg[:50]}")
            except Exception as e:
                done += 1
                print(f"[{done}/{len(rows)}] 💥 id={rid} {e}")

    dt = time.time() - t0
    print(f"\n=== 抖音补数据完成: 成功 {STATS['ok']} | 失败 {STATS['fail']} | 跳过 {STATS['skip']} | 耗时 {dt:.0f}s ===")

if __name__ == "__main__":
    main()
