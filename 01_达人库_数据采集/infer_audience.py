"""从已有数据推断达人消费群体画像（免费渠道，标注推断置信度）
信号源：fit_tags（内容标签）+ bio + hot_products + 带货品类
"""
import sqlite3, json, sys, csv, re, os

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception: pass

# 示例数据放在脚本同目录的 data/ 下，路径可用环境变量覆盖；仓库内不含真实业务数据
DATA_DIR = os.getenv("SAMPLE_DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
DB = os.path.join(DATA_DIR, "influencers.db")
SRC_CSV = os.path.join(DATA_DIR, "sample_matched.csv")
OUT_CSV = os.path.join(DATA_DIR, "audience_inferred.csv")
OUT_XLSX = os.path.join(DATA_DIR, "audience_inferred.xlsx")

TAG_AUDIENCE = {
    '亲子': ('宝妈/年轻父母', 0.9), '母婴': ('宝妈/年轻父母', 0.9), '孕产好物': ('宝妈/孕妈', 0.95),
    '颜值萌娃': ('宝妈/年轻父母', 0.85), '亲子日常': ('宝妈/年轻父母', 0.9),
    '美食': ('家庭主妇/吃货', 0.7), '美食展示': ('家庭主妇/吃货', 0.7),
    '居家': ('家庭用户/主妇', 0.7), '家具家电': ('家庭用户', 0.7), '家纺': ('家庭用户/主妇', 0.75),
    '时尚': ('年轻女性(18-35)', 0.65), '穿搭': ('年轻女性(18-35)', 0.65),
    '女装': ('年轻女性(18-35)', 0.7), '女士鞋靴': ('女性(25-45)', 0.7),
    '护肤': ('年轻女性(18-35)', 0.8), '面部护肤': ('年轻女性(18-35)', 0.8),
    '彩妆': ('年轻女性(18-35)', 0.85), '美妆': ('年轻女性(18-35)', 0.85),
    '男士穿搭': ('男性(20-40)', 0.75),
    '萌宠': ('年轻养宠人群', 0.6),
    '游戏': ('年轻男性(18-30)', 0.8), '科技': ('年轻男性(20-40)', 0.75),
    '手机': ('年轻男性(20-40)', 0.7),
    '二次元': ('Z世代(15-25)', 0.8),
    '学生宿舍': ('学生(18-24)', 0.9),
}

BIO_AUDIENCE = [
    ('宝妈', '宝妈/年轻父母', 0.9), ('妈妈', '宝妈/年轻父母', 0.85), ('妈咪', '宝妈', 0.9),
    ('宿舍', '学生(18-24)', 0.85), ('大学生', '学生(18-24)', 0.9), ('学生', '学生群体', 0.6),
    ('上班族', '职场人群(22-40)', 0.7), ('白领', '职场人群(22-40)', 0.7), ('打工人', '职场人群(22-40)', 0.8),
    ('阿姨', '中老年女性(45+)', 0.7), ('奶奶', '中老年女性(50+)', 0.8), ('老人', '中老年人群', 0.6),
    ('胖', '大码人群', 0.8), ('大码', '大码人群', 0.9), ('微胖', '大码人群', 0.8),
    ('小个子', '小个子人群', 0.9), ('矮个子', '小个子人群', 0.8),
    ('情侣', '情侣/年轻男女', 0.8), ('夫妻', '已婚人群', 0.7),
    ('男款', '男性', 0.6), ('男鞋', '男性', 0.7),
]

def infer_audience(r):
    tags = []
    try:
        tags = json.loads(r['fit_tags'] or '[]')
    except Exception:
        pass
    bio = (r['bio'] or '')
    hp = (r['hot_products'] or '')
    text = bio + hp

    signals = []
    for t in tags:
        if t in TAG_AUDIENCE:
            aud, conf = TAG_AUDIENCE[t]
            signals.append((aud, conf, f"标签:{t}"))
    for kw, aud, conf in BIO_AUDIENCE:
        if kw in text:
            signals.append((aud, conf, f"bio含'{kw}'"))

    if not signals:
        return ('泛人群(待验证)', 0.3, '无强信号')

    signals.sort(key=lambda x: -x[1])
    main_aud, main_conf, main_src = signals[0]
    others = []
    seen = set()
    for aud, conf, src in signals[1:]:
        if aud != main_aud and aud not in seen:
            others.append(aud)
            seen.add(aud)
    desc = main_aud
    if others:
        desc += f"+{'/'.join(others[:3])}"
    conf = main_conf
    return (desc, conf, main_src + ';' + ';'.join(s for _, _, s in signals[1:4]))

os.makedirs(DATA_DIR, exist_ok=True)

with open(SRC_CSV, encoding='utf-8-sig') as f:
    matched = list(csv.DictReader(f))
print(f"匹配名单 {len(matched)} 条，开始推断消费群体\n")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

rows_out = []
for m in matched:
    r = conn.execute("SELECT * FROM influencers WHERE id = ?", (int(m['id']),)).fetchone()
    if not r:
        continue
    aud, conf, src = infer_audience(r)
    rows_out.append({
        '排名': len(rows_out) + 1,
        '昵称': m['nickname'],
        '抖音号': m['account'],
        '粉丝数': m['fans'],
        '带货水平': m['tier'],
        '推断消费群体': aud,
        '置信度': f"{conf:.0%}",
        '推断依据': src,
        '主播所在地': m['region'],
        '商品价格带': (r['price_band'] or '未知'),
        '主页链接': m['url'],
    })
    print(f"{rows_out[-1]['排名']:>3} {m['nickname'][:16]:<18} {aud:<30} 置信{conf:.0%} | {src[:40]}")

rows_out.sort(key=lambda x: -float(x['置信度'].rstrip('%'))/100)

with open(OUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
    w.writeheader()
    w.writerows(rows_out)
print(f"\n✅ CSV: {OUT_CSV}")

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "消费群体推断"
    headers = list(rows_out[0].keys())
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="70AD47")
        c.alignment = Alignment(horizontal="center", vertical="center")
    for row in rows_out:
        ws.append([row[h] for h in headers])
    widths = [6, 20, 14, 10, 8, 28, 8, 40, 12, 12, 40]
    for i, wdt in enumerate(widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = wdt
    ws.freeze_panes = "A2"
    wb.save(OUT_XLSX)
    print(f"✅ Excel: {OUT_XLSX}")
except ImportError:
    pass
conn.close()
