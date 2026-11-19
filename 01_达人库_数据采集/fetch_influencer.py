"""单达人抓取 v2：URL → node nuxt_parse.js → 全字段入库 + 相似达人 BFS

用法:
  python3 fetch_influencer.py --queue-id 3        # 抓 crawl_queue 里指定 id
  python3 fetch_influencer.py --url <authorRankUrl>  # 直接抓 URL（也入队）

数据来源: 蝉妈妈开放收录页（open/authorRank/xxx.html）
字段: NUXT authorInfo 113 字段 + 页面文本提取（水平/视频带货力/直播带货力）
BFS: 收录页 similarAuthorsData 里的 author_id 会自动写入 crawl_queue（source=bfs）
"""
import sqlite3, os, sys, json, argparse, subprocess

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception: pass

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "influencers.db")
NODE = "node"
PARSER = os.path.join(HERE, "nuxt_parse.js")

GENDER_MAP = {1: '男', 2: '女'}

FIELD_MAP = {
    'nickname': 'nickname',
    'unique_id': 'account_id',
    'web_url': 'profile_url',
    'follower_count': 'fans_count',
    'total_favorited': 'likes_count',
    'aweme_count': 'works_count',
    'following_count': 'follows_count',
    'fans_group': 'fans_group',
    'province': 'region',
    'signature': 'bio',
    'aweme_count_30': 'week_works',       # 近30天作品
    'follower_incr': 'week_fans_gain',    # 粉丝增量
    'digg_incr': 'week_likes',            # 点赞增量
    'active_fans': None,                  # 活跃粉丝（有独立字段）
    'reputation': 'rank_score',           # 口碑分（对象，需提取 score）
    'aweme_rank_score': None,             # 备用口碑分
    'bring_product_ability_level': 'rank_level',  # 带货能力等级
    'aweme_bring_level': None,            # 备用等级
    'mcn_name': None,                     # MCN
    'author_mcn_name': None,
    'age': None,                          # 年龄
    'gender': 'gender',
    'live_room_id': None,
    'is_live_author': None,
    'live_count_30': None,
    'fans_club_total': None,
    'single_tags': 'fit_tags',            # 达人标签（时尚>穿搭>女装）
    'is_shop_author': 'is_shop_author',
    'is_brand_self_author': 'is_brand_self_author',
    'is_self_author': 'is_self_author',
    'is_aweme_bring_product_author': 'is_aweme_bring_product_author',
    'author_type': 'author_type',
    'author_way_type': 'author_way_type',
    'product_label': None,
    'spread_category': None,
    'main_bring_product_type': None,
    'take_product_price_range': None,
    'price_band': None,
}

def parse_author_url(url):
    import re
    m = re.search(r'/authorRank/([A-Za-z0-9_-]{10,})\.html', url)
    return m.group(1) if m else ''

def run_parser(url):
    r = subprocess.run([NODE, PARSER, url], capture_output=True, timeout=60, cwd=HERE)
    out = r.stdout.decode('utf-8', errors='replace').strip()
    if not out:
        return {'ok': False, 'error': 'no output: ' + r.stderr.decode('utf-8', errors='replace')[:200]}
    try:
        return json.loads(out)
    except Exception as e:
        return {'ok': False, 'error': f'json parse fail: {e}, raw={out[:200]}'}

def enqueue_similar(conn, sim_list):
    n = 0
    for s in sim_list:
        aid = s.get('author_id') or s.get('id') or ''
        if not aid:
            continue
        url = f"https://www.chanmama.com/open/authorRank/{aid}.html"
        nickname = s.get('nickname') or ''
        cur = conn.execute("INSERT OR IGNORE INTO crawl_queue (url, author_id, nickname, source, category) VALUES (?,?,?,?,?)",
                           (url, aid, nickname, 'bfs', ''))
        n += cur.rowcount
    return n

def upsert_influencer(conn, ai, tier, video_power, live_power):
    account_id = ai.get('unique_id') or ''
    nickname = ai.get('nickname') or ''
    if not account_id and not nickname:
        return False

    existing = None
    if account_id:
        existing = conn.execute("SELECT id FROM influencers WHERE account_id=?", (account_id,)).fetchone()
    if not existing:
        existing = conn.execute("SELECT id FROM influencers WHERE nickname=?", (nickname,)).fetchone()

    data = {}
    for src, dst in FIELD_MAP.items():
        if dst and ai.get(src) not in (None, '', 0):
            data[dst] = ai[src]
    rep = ai.get('reputation')
    if isinstance(rep, dict) and rep.get('score'):
        data['rank_score'] = rep['score']
    elif rep and not isinstance(rep, dict):
        data['rank_score'] = rep
    bpa = ai.get('bring_product_ability_level')
    if isinstance(bpa, dict) and bpa.get('level'):
        data['rank_level'] = str(bpa['level'])
    if not data.get('region') and ai.get('city'):
        data['region'] = ai['city']
    if 'fit_tags' in data:
        st = data['fit_tags']
        if isinstance(st, dict):
            parts = []
            for k in ['first', 'second', 'third']:
                v = st.get(k)
                if isinstance(v, list):
                    parts.extend(v)
                elif v and v is not True:
                    parts.append(v)
            data['fit_tags'] = json.dumps(list(dict.fromkeys(parts)), ensure_ascii=False)
        elif isinstance(st, list):
            data['fit_tags'] = json.dumps(st, ensure_ascii=False)
        elif isinstance(st, str):
            data['fit_tags'] = json.dumps([st], ensure_ascii=False)
    if ai.get('gender') in GENDER_MAP:
        data['gender'] = GENDER_MAP[ai['gender']]
    elif ai.get('gender') is not None:
        data['gender'] = str(ai['gender'])
    if tier:
        data['rank_tier'] = tier
    if video_power:
        data['video_power'] = video_power
    if live_power:
        data['live_power'] = live_power
    if ai.get('active_fans'):
        data['fans_group'] = ai['active_fans'] if not data.get('fans_group') else data['fans_group']
    bp = ai.get('bring_products_30')
    if bp:
        data['hot_products'] = json.dumps(bp, ensure_ascii=False)
    data['data_source'] = '蝉妈妈'
    data['portrait_source'] = '无'
    data['fetch_status'] = '成功'
    data['fetched_at'] = "datetime('now','localtime')"

    if existing:
        sets = []
        vals = []
        for k, v in data.items():
            if k in ('fetched_at',):
                sets.append(f"{k}=datetime('now','localtime')")
            else:
                sets.append(f"{k}=?")
                vals.append(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
        sets.append("updated_at=datetime('now','localtime')")
        conn.execute(f"UPDATE influencers SET {', '.join(sets)} WHERE id=?", vals + [existing[0]])
        return True
    else:
        cols = list(data.keys())
        vals = [json.dumps(data[c], ensure_ascii=False) if isinstance(data[c], (dict, list)) else data[c] for c in cols]
        conn.execute(f"INSERT INTO influencers ({', '.join(cols)}, created_at, updated_at) VALUES ({', '.join('?' * len(cols))}, datetime('now','localtime'), datetime('now','localtime'))", vals)
        return True

def fetch_url(url, enqueue_bfs=False):
    """抓取单个 URL，返回 (ok, msg, similar_count)
    enqueue_bfs 默认关闭：相似达人推荐位需要登录态，未启用时不入队，
    避免污染队列。"""
    conn = sqlite3.connect(DB)
    aid = parse_author_url(url)
    conn.execute("UPDATE crawl_queue SET status='抓取中', fetch_count=fetch_count+1, updated_at=datetime('now','localtime') WHERE url=?", (url,))
    conn.commit()
    conn.close()

    res = run_parser(url)
    if not res.get('ok'):
        conn = sqlite3.connect(DB)
        conn.execute("UPDATE crawl_queue SET status='失败', error=?, updated_at=datetime('now','localtime') WHERE url=?",
                     (str(res.get('error', ''))[:200], url))
        conn.commit()
        conn.close()
        return False, f"解析失败: {res.get('error', '')}", 0

    ai = res.get('authorInfo') or {}
    sim = res.get('similarAuthors') or []
    tier = res.get('tier') or ''
    vp = res.get('videoPower') or 0
    lp = res.get('livePower') or 0

    conn = sqlite3.connect(DB)
    ok = upsert_influencer(conn, ai, tier, vp, lp)
    n_sim = enqueue_similar(conn, sim) if enqueue_bfs else 0
    conn.execute("UPDATE crawl_queue SET status='成功', fetched_at=datetime('now','localtime'), updated_at=datetime('now','localtime') WHERE url=?", (url,))
    conn.commit()
    name = ai.get('nickname') or '?'
    conn.close()
    return ok, f"✅ {name} (粉丝 {ai.get('follower_count', 0)}) 相似扩展 {n_sim} 个", n_sim

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue-id", type=int, help="抓 crawl_queue 指定 id")
    ap.add_argument("--url", help="直接抓 URL")
    args = ap.parse_args()
    if args.url:
        ok, msg, n = fetch_url(args.url)
        print(msg)
    elif args.queue_id:
        conn = sqlite3.connect(DB)
        r = conn.execute("SELECT url FROM crawl_queue WHERE id=?", (args.queue_id,)).fetchone()
        conn.close()
        if not r:
            print(f"❌ 队列无 id={args.queue_id}")
        else:
            ok, msg, n = fetch_url(r[0])
            print(msg)
    else:
        print("用法: fetch_influencer.py --queue-id 3 或 --url <url>")
