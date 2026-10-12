#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄学 4D 号码推演工具(五行 + 梅花易数八卦 + 二十八星宿)
仅供娱乐与编程学习。4D 开奖是随机事件,任何算法都无法提高中奖概率。

用法:
    python 4d_predictor.py                      # 今天、当前时辰
    python 4d_predictor.py -d 2026-10-12        # 指定公历日期
    python 4d_predictor.py -d 2026-10-12 -H 15  # 指定日期和小时(0-23)
    python 4d_predictor.py -n 5                 # 输出 5 组号码
    python 4d_predictor.py --offset 11          # 调整二十八星宿校准偏移(见下方说明)
"""
import argparse
import hashlib
import random
from datetime import date, datetime

# ============================ 基础数据表 ============================
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEM_WX = dict(zip(STEMS, "木木火火土土金金水水"))
BRANCH_WX = dict(zip(BRANCHES, "水土木木土火火土金金土水"))

# 五行相生:木生火 火生土 土生金 金生水 水生木;相克:木克土 土克水 水克火 火克金 金克木
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

# 河图数:1,6水 2,7火 3,8木 4,9金 5,0土  -> 数字 0-9 对应的五行
DIGIT_WX = {1: "水", 6: "水", 2: "火", 7: "火", 3: "木", 8: "木", 4: "金", 9: "金", 5: "土", 0: "土"}

# 先天八卦数 乾1兑2离3震4巽5坎6艮7坤8;线条自下而上,1=阳 0=阴
TRIGRAMS = {
    1: ("乾", "金", (1, 1, 1)),
    2: ("兑", "金", (1, 1, 0)),
    3: ("离", "火", (1, 0, 1)),
    4: ("震", "木", (1, 0, 0)),
    5: ("巽", "木", (0, 1, 1)),
    6: ("坎", "水", (0, 1, 0)),
    7: ("艮", "土", (0, 0, 1)),
    8: ("坤", "土", (0, 0, 0)),
}
LINES_TO_NUM = {v[2]: k for k, v in TRIGRAMS.items()}

# 二十八星宿(自角宿起),(名称, 吉凶)。吉凶采用通行的择日口诀。
MANSIONS = [
    ("角", "吉"), ("亢", "凶"), ("氐", "凶"), ("房", "吉"), ("心", "凶"), ("尾", "吉"), ("箕", "吉"),
    ("斗", "吉"), ("牛", "凶"), ("女", "凶"), ("虚", "凶"), ("危", "凶"), ("室", "吉"), ("壁", "吉"),
    ("奎", "凶"), ("娄", "吉"), ("胃", "吉"), ("昴", "凶"), ("毕", "吉"), ("觜", "凶"), ("参", "吉"),
    ("井", "吉"), ("鬼", "凶"), ("柳", "凶"), ("星", "凶"), ("张", "吉"), ("翼", "凶"), ("轸", "吉"),
]
# 七曜轮值:星宿序号 % 7 -> 七曜(角木 亢金 氐土 房日 心月 尾火 箕水)
QIYAO = ["木", "金", "土", "日", "月", "火", "水"]
QIYAO_WX = {"木": "木", "金": "金", "土": "土", "日": "火", "月": "水", "火": "火", "水": "水"}
DIRECTIONS = ["东方青龙", "北方玄武", "西方白虎", "南方朱雀"]  # 每 7 宿一象

# 月令(节)大致日期:(公历月, 日, 月支序号)。采用固定日期近似,误差约 ±1 天。
JIE_TERMS = [(1, 5, 1), (2, 4, 2), (3, 6, 3), (4, 5, 4), (5, 5, 5), (6, 6, 6),
             (7, 7, 7), (8, 7, 8), (9, 8, 9), (10, 8, 10), (11, 7, 11), (12, 7, 0)]
# 月支 -> 当令(旺)五行
SEASON_WX = {2: "木", 3: "木", 5: "火", 6: "火", 8: "金", 9: "金", 11: "水", 0: "水",
             1: "土", 4: "土", 7: "土", 10: "土"}


# ============================ 干支历法 ============================
def jdn(d: date) -> int:
    """公历日期 -> 儒略日数(整数)。"""
    return d.toordinal() + 1721425


def ganzhi_str(idx: int) -> str:
    return STEMS[idx % 10] + BRANCHES[idx % 12]


def day_ganzhi_index(d: date) -> int:
    """日柱:(JDN+49) % 60,甲子=0。校验:2000-01-01 为戊午。"""
    return (jdn(d) + 49) % 60


def year_ganzhi_index(d: date) -> int:
    """年柱:以立春(约2月4日)为界。"""
    y = d.year if (d.month, d.day) >= (2, 4) else d.year - 1
    return (y - 4) % 60


def month_branch(d: date) -> int:
    """月支序号(子=0)。找到当日或之前最近的一个"节"。"""
    cur = None
    for m, day, br in JIE_TERMS:
        if (d.month, d.day) >= (m, day):
            cur = br
    return cur if cur is not None else 0  # 1月5日前仍属上年子月


def month_ganzhi_index(d: date) -> int:
    """月柱:五虎遁。甲己起丙寅,乙庚起戊寅,丙辛起庚寅,丁壬起壬寅,戊癸起甲寅。"""
    br = month_branch(d)
    year_stem = year_ganzhi_index(d) % 10
    start = {0: 2, 5: 2, 1: 4, 6: 4, 2: 6, 7: 6, 3: 8, 8: 8, 4: 0, 9: 0}[year_stem]
    n = (br - 2) % 12  # 寅月为 0
    stem = (start + n) % 10
    # 由天干地支求 60 甲子序号
    for i in range(60):
        if i % 10 == stem and i % 12 == br:
            return i
    raise ValueError("月柱计算失败")


def hour_branch(hour: int) -> int:
    """时辰地支序号:23-1点子时,1-3点丑时……"""
    return ((hour + 1) // 2) % 12


def mansion_index(d: date, offset: int) -> int:
    """二十八星宿值日:每日一宿,28 天一循环,与星期严格对应(七曜)。
    offset 为校准常数;默认 4 时 2000-01-01(周六)为女宿。
    若与你熟悉的万年历不一致,可用 --offset 以 7 的倍数调整(保持七曜与星期对应)。"""
    return (jdn(d) + offset) % 28


# ============================ 梅花易数起卦 ============================
def build_hexagram(d: date, hour: int):
    """梅花易数时间起卦(简化:用公历月日代替农历月日)。
    上卦 = (年支数+月+日) % 8;下卦 = (年支数+月+日+时支数) % 8;动爻 = 总数 % 6。"""
    ybr = year_ganzhi_index(d) % 12 + 1   # 子=1 ... 亥=12
    hbr = hour_branch(hour) + 1
    s_up = ybr + d.month + d.day
    s_all = s_up + hbr
    up = s_up % 8 or 8
    low = s_all % 8 or 8
    move = s_all % 6 or 6
    lines = list(TRIGRAMS[low][2]) + list(TRIGRAMS[up][2])  # 自下而上 6 爻
    mid_lines = lines[:]
    changed = lines[:]
    changed[move - 1] ^= 1
    c_low = LINES_TO_NUM[tuple(changed[:3])]
    c_up = LINES_TO_NUM[tuple(changed[3:])]
    # 互卦:2-3-4 爻为下互,3-4-5 爻为上互
    h_low = LINES_TO_NUM[tuple(mid_lines[1:4])]
    h_up = LINES_TO_NUM[tuple(mid_lines[2:5])]
    return {"up": up, "low": low, "move": move, "c_up": c_up, "c_low": c_low,
            "h_up": h_up, "h_low": h_low}


# ============================ 五行旺衰与喜用 ============================
def strength(day_wx: str, season_wx: str) -> str:
    """旺相休囚死:以月令当令五行判断日主五行状态。"""
    if day_wx == season_wx:
        return "旺"
    if SHENG[season_wx] == day_wx:
        return "相"
    if SHENG[day_wx] == season_wx:
        return "休"
    if KE[day_wx] == season_wx:
        return "囚"
    return "死"  # 当令五行克日主


def favored_elements(day_wx: str, state: str):
    """身强(旺/相)宜泄耗克;身弱(休/囚/死)宜生扶。返回 {五行: 权重加成}。"""
    resource = [k for k, v in SHENG.items() if v == day_wx][0]   # 生我者(印)
    output = SHENG[day_wx]                                         # 我生者(食伤)
    wealth = KE[day_wx]                                            # 我克者(财)
    officer = [k for k, v in KE.items() if v == day_wx][0]         # 克我者(官杀)
    if state in ("旺", "相"):
        return {output: 1.8, wealth: 1.6, officer: 1.3, day_wx: 0.8, resource: 0.7}, \
               f"日主偏强,喜泄耗克:{output}(食伤)、{wealth}(财)、{officer}(官杀)"
    return {resource: 1.8, day_wx: 1.6, output: 0.8, wealth: 0.7, officer: 0.6}, \
           f"日主偏弱,喜生扶:{resource}(印)、{day_wx}(比劫)"


# ============================ 核心:生成 4D ============================
def digits_of_element(wx: str):
    return [d for d, w in DIGIT_WX.items() if w == wx]


def predict(d: date, hour: int, n_sets: int, offset: int):
    dgz = day_ganzhi_index(d)
    mgz = month_ganzhi_index(d)
    ygz = year_ganzhi_index(d)
    day_stem, day_branch = STEMS[dgz % 10], BRANCHES[dgz % 12]
    day_wx = STEM_WX[day_stem]
    season = SEASON_WX[month_branch(d)]
    state = strength(day_wx, season)
    fav, fav_text = favored_elements(day_wx, state)

    gua = build_hexagram(d, hour)
    mi = mansion_index(d, offset)
    m_name, m_luck = MANSIONS[mi]
    m_qiyao = QIYAO[mi % 7]
    m_wx = QIYAO_WX[m_qiyao]
    m_digit = (mi + 1) % 10                  # 星宿灵动数:序号(1-28) 取个位
    m_dir = DIRECTIONS[mi // 7]

    # 四个数位的"来源数字":千=主卦上卦数,百=主卦下卦数,十=变卦(变爻所在卦)数,个=星宿灵动数
    changed_num = gua["c_up"] if gua["move"] > 3 else gua["c_low"]
    anchors = [gua["up"] % 10, gua["low"] % 10, changed_num % 10, m_digit]
    pos_names = ["千位", "百位", "十位", "个位"]

    # 种子:干支 + 卦象 + 星宿 + 日期时辰,保证同一时空结果可复现
    seed_str = f"{ygz}-{mgz}-{dgz}-{hour_branch(hour)}-{gua}-{mi}-{d.isoformat()}"
    seed = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16)
    rng = random.Random(seed)

    # 星宿吉凶调节:吉则喜用加成放大,凶则收敛
    luck_factor = 1.15 if m_luck == "吉" else 0.9

    results = []
    for k in range(n_sets):
        digits = []
        for pos in range(4):
            weights = []
            for dg in range(10):
                w = 1.0
                w *= 1 + (fav.get(DIGIT_WX[dg], 1.0) - 1) * luck_factor   # 五行喜用
                if dg == anchors[pos]:
                    w *= 3.0                                              # 本位锚点数
                if dg in anchors:
                    w *= 1.4                                              # 卦/宿共同数
                if DIGIT_WX[dg] == m_wx:
                    w *= 1.2                                              # 星宿五行
                weights.append(w)
            digits.append(rng.choices(range(10), weights=weights)[0])
        results.append("".join(map(str, digits)))

    return {
        "date": d, "hour": hour,
        "ganzhi": (ganzhi_str(ygz), ganzhi_str(mgz), ganzhi_str(dgz), BRANCHES[hour_branch(hour)] + "时"),
        "day_master": day_stem, "day_wx": day_wx, "season": season, "state": state,
        "fav": fav, "fav_text": fav_text, "gua": gua,
        "mansion": (m_name, m_luck, m_qiyao, m_wx, m_dir, mi), "anchors": anchors,
        "pos_names": pos_names, "results": results,
    }


def trigram_name(n):
    return TRIGRAMS[n][0]


def report(r) -> str:
    g = r["gua"]
    y, m, dd, h = r["ganzhi"]
    mn, ml, qy, mwx, mdir, mi = r["mansion"]
    top = sorted(r["fav"].items(), key=lambda x: -x[1])[:2]
    lucky_digits = sorted({dg for wx, _ in top for dg in digits_of_element(wx)})
    lines = [
        "=" * 56,
        f" 玄学 4D 推演  公历 {r['date']}  {r['hour']:02d}时",
        "=" * 56,
        f"【四柱】年 {y}  月 {m}  日 {dd}  时 {h}",
        f"【日主】{r['day_master']}({r['day_wx']}),月令当令 {r['season']},日主 {r['state']}",
        f"【喜用】{r['fav_text']}",
        f"【起卦】上卦 {trigram_name(g['up'])}({g['up']})  下卦 {trigram_name(g['low'])}({g['low']})  动爻 第{g['move']}爻",
        f"        变卦 上 {trigram_name(g['c_up'])} 下 {trigram_name(g['c_low'])};"
        f" 互卦 上 {trigram_name(g['h_up'])} 下 {trigram_name(g['h_low'])}",
        f"【值宿】{mn}宿(第{mi + 1}宿,{qy}曜,属{mwx},{mdir}),吉凶:{ml}",
        f"【四位锚点数】" + "、".join(f"{p}={a}" for p, a in zip(r["pos_names"], r["anchors"])),
        "",
        "【推荐号码】",
    ]
    for i, num in enumerate(r["results"], 1):
        tag = "主推" if i == 1 else f"备选{i - 1}"
        lines.append(f"  {tag}:  {num}")
    lines += [
        "",
        "【解读】",
        f"  1) 今日日主为{r['day_master']}{r['day_wx']},处于月令「{r['state']}」,故以{r['fav_text'].split(',')[1]}为用神,"
        f"对应河图数 {lucky_digits} 在各数位的权重被提高。",
        f"  2) 梅花易数得「{trigram_name(g['up'])}上{trigram_name(g['low'])}下」,第{g['move']}爻动,"
        f"变出「{trigram_name(g['c_up'])}上{trigram_name(g['c_low'])}下」,"
        f"卦数 {g['up']}/{g['low']}/{g['c_up'] if g['move'] > 3 else g['c_low']} 作为千百十位的锚点。",
        f"  3) 值日星宿{mn}({ml}),灵动数 {r['anchors'][3]} 作为个位锚点;"
        + ("吉宿放大喜用倾向。" if ml == "吉" else "凶宿则收敛喜用倾向,宜保守。"),
        "",
        "声明:4D 开奖为纯随机,以上仅为玄学趣味推演与编程示例,不构成任何投注建议。请理性娱乐。",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="五行八卦二十八星宿 4D 号码推演")
    ap.add_argument("-d", "--date", help="公历日期 YYYY-MM-DD,默认今天")
    ap.add_argument("-H", "--hour", type=int, help="小时 0-23,默认当前小时")
    ap.add_argument("-n", "--num", type=int, default=3, help="生成组数,默认 3")
    ap.add_argument("--offset", type=int, default=4, help="二十八星宿校准偏移,默认 4")
    a = ap.parse_args()
    now = datetime.now()
    d = datetime.strptime(a.date, "%Y-%m-%d").date() if a.date else now.date()
    hour = a.hour if a.hour is not None else now.hour
    print(report(predict(d, hour, a.num, a.offset)))


if __name__ == "__main__":
    main()
