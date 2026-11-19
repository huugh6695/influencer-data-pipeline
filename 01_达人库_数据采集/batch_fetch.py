"""批量抓取 v2：并发消费 crawl_queue，断点续跑，可长时间运行

用法:
  python3 batch_fetch.py --workers 8            # 8 并发抓全部待抓
  python3 batch_fetch.py --workers 8 --limit 50 # 试跑 50 条
  python3 batch_fetch.py --category xiexuexiangbao  # 只抓指定分类
  python3 batch_fetch.py --retry                # 重试失败的
  python3 batch_fetch.py --max-fetch 3          # 每条最多尝试 3 次（默认）

设计要点:
  - 队列状态机: 待抓 → 抓取中 → 成功/失败（失败可重试）
  - 断点续跑: 中途 Ctrl+C 退出，重跑自动跳过已成功的
  - 并发: ThreadPoolExecutor，每个 worker 独立调用 node 子进程
  - 需登录态的页面标记 status='跳过'，不重试不阻塞
"""
import sqlite3, os, sys, time, argparse, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception: pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DB = os.path.join(HERE, "influencers.db")

import fetch_influencer as fi

stats_lock = threading.Lock()
STATS = {'ok': 0, 'fail': 0, 'skip': 0, 'sim': 0}

def process_one(url):
    ok, msg, n_sim = fi.fetch_url(url)
    with stats_lock:
        if ok:
            STATS['ok'] += 1
        else:
            if '登录' in msg or 'no nuxt' in msg:
                STATS['skip'] += 1
            else:
                STATS['fail'] += 1
        STATS['sim'] += n_sim
    return url, ok, msg

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8, help="并发数（默认8）")
    ap.add_argument("--limit", type=int, default=0, help="本次最多抓 N 条（0=不限）")
    ap.add_argument("--category", help="只抓指定分类 slug 的队列")
    ap.add_argument("--source", help="只抓指定来源：list/category/bfs")
    ap.add_argument("--retry", action="store_true", help="包含失败的（重试）")
    ap.add_argument("--max-fetch", type=int, default=3, help="每条最多尝试次数")
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    where = ["status='待抓'"]
    vals = []
    if args.category:
        where.append("category=?")
        vals.append(args.category)
    if args.source:
        where.append("source=?")
        vals.append(args.source)
    if args.retry:
        where = ["status IN ('待抓','失败')", "fetch_count < ?"]
        vals = [args.max_fetch]
        if args.category:
            where.append("category=?"); vals.append(args.category)
        if args.source:
            where.append("source=?"); vals.append(args.source)
    sql = f"SELECT id, url FROM crawl_queue WHERE {' AND '.join(where)} ORDER BY id"
    rows = conn.execute(sql, vals).fetchall()
    total_q = conn.execute("SELECT COUNT(*) FROM crawl_queue").fetchone()[0]
    conn.close()

    if args.limit > 0:
        rows = rows[:args.limit]

    if not rows:
        print("没有待抓取的链接 ✅")
        return

    print(f"📋 队列总计 {total_q} | 本次待抓 {len(rows)} | 并发 {args.workers}")
    print(f"⏱️  估算: 单条 ~1.5s（含解析），{len(rows)} 条 × {args.workers} 并发 ≈ {len(rows)*1.5/args.workers:.0f}s\n")

    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(process_one, url): (qid, url) for qid, url in rows}
        for fut in as_completed(futs):
            qid, url = futs[fut]
            try:
                _, ok, msg = fut.result()
                done += 1
                tag = '✅' if ok else ('⏭️' if '登录' in msg or 'no nuxt' in msg else '❌')
                if done % 5 == 0 or not ok:
                    print(f"[{done}/{len(rows)}] {tag} q{qid} {msg[:70]}")
            except Exception as e:
                done += 1
                print(f"[{done}/{len(rows)}] 💥 q{qid} 异常: {e}")

    dt = time.time() - t0
    print(f"\n=== 完成: 成功 {STATS['ok']} | 跳过(需登录) {STATS['skip']} | 失败 {STATS['fail']} | 相似扩展 {STATS['sim']} | 耗时 {dt:.0f}s ===")

if __name__ == "__main__":
    main()
