import streamlit as st
import os
import datetime
import swisseph as swe
import pytz
import pandas as pd
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from lunar_python import Solar
# 引入 openai 套件來呼叫 Grok API
from openai import OpenAI

# 引入繪圖
try:
    from Astro_Drawer import draw_astrology_chart
except ImportError:
    st.error("找不到 Astro_Drawer.py")

# ================= 1. 初始化與計算工具 =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EPHE_PATH = os.path.join(BASE_DIR, 'ephe')
if os.path.exists(EPHE_PATH):
    swe.set_ephe_path(EPHE_PATH)

geolocator = Nominatim(user_agent="astro_web_app")
tf = TimezoneFinder()

ZODIAC = ['白羊座', '金牛座', '雙子座', '巨蟹座', '獅子座', '處女座', '天秤座', '天蠍座', '射手座', '摩羯座', '水瓶座', '雙魚座']
TRADITIONAL_RULERS = ['火星', '金星', '水星', '月亮', '太陽', '水星', '金星', '火星', '木星', '土星', '土星', '木星']
ZR_PERIODS = {0: 15, 1: 8, 2: 20, 3: 25, 4: 19, 5: 20, 6: 8, 7: 15, 8: 12, 9: 27, 10: 30, 11: 12}

def format_pos(lon):
    return f"{ZODIAC[int(lon // 30)]} {int(lon % 30):02d}°{int((lon % 1) * 60):02d}'"

def get_natal_house(lon, cusps):
    c = list(cusps)[1:] if len(list(cusps)) == 13 else list(cusps)
    for i in range(12):
        c1, c2 = c[i], c[(i + 1) % 12]
        if (c1 < c2 and c1 <= lon < c2) or (c1 > c2 and (lon >= c1 or lon < c2)): return i + 1
    return 1

def get_whole_sign_rulerships(asc_deg):
    asc_sign_idx = int(asc_deg // 30)
    ruler_to_houses = {r: [] for r in set(TRADITIONAL_RULERS)}
    for i in range(12):
        house_sign_idx = (asc_sign_idx + i) % 12
        ruler = TRADITIONAL_RULERS[house_sign_idx]
        ruler_to_houses[ruler].append(str(i+1))
    return {r: (f"{'/'.join(h)}R" if h else "") for r, h in ruler_to_houses.items()}

def get_aspect_detail(p1, p2, p_pos, p_spd, orb_map):
    specs = [(0, "合相"), (180, "對相"), (120, "三分"), (90, "四分"), (60, "六分")]
    diff = abs(p_pos[p1] - p_pos[p2])
    if diff > 180: diff = 360 - diff
    for angle, name in specs:
        limit = orb_map.get(name, 8.0)
        err = abs(diff - angle)
        if err <= limit:
            dt = 0.001
            diff_next = abs((p_pos[p1] + p_spd[p1]*dt) - (p_pos[p2] + p_spd[p2]*dt))
            if diff_next > 180: diff_next = 360 - diff_next
            state = "入相" if abs(diff_next - angle) < err else "出相"
            return {"相位": name, "狀態": state, "容許度": f"{err:.2f}°"}
    return None

def calc_date(base_dt, age_float):
    return (base_dt + datetime.timedelta(days=age_float * 365.2422)).strftime("%Y-%m-%d")

def calculate_chart_pack(jd, lat, lon, orb_map):
    cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P')
    r_labels = get_whole_sign_rulerships(ascmc[0])
    planets_id = {"太陽": swe.SUN, "月亮": swe.MOON, "水星": swe.MERCURY, "金星": swe.VENUS, "火星": swe.MARS, "木星": swe.JUPITER, "土星": swe.SATURN, "天王星": swe.URANUS, "海王星": swe.NEPTUNE, "冥王星": swe.PLUTO, "上升": -1, "中天": -2, "北交點": swe.TRUE_NODE}
    p_pos, p_spd, p_data = {}, {}, []
    for name, pid in planets_id.items():
        if pid == -1: pos, spd = ascmc[0], 0
        elif pid == -2: pos, spd = ascmc[1], 0
        else: res, _ = swe.calc_ut(jd, pid); pos, spd = res[0], res[3]
        p_pos[name], p_spd[name] = pos, spd
        if name not in ["上升", "中天"]:
            h_num = get_natal_house(pos, cusps)
            p_data.append({"宮主星": r_labels.get(name, ""), "星體": name, "星座": format_pos(pos), "宮位": f"第 {h_num} 宮"})
    all_asps = []
    names = [k for k in planets_id.keys() if k not in ["上升", "中天", "北交點"]]
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            p1, p2 = names[i], names[j]
            asp = get_aspect_detail(p1, p2, p_pos, p_spd, orb_map)
            if asp: all_asps.append({"宮主星A": r_labels.get(p1, ""), "行星A": p1, "相位": asp['相位'], "宮主星B": r_labels.get(p2, ""), "行星B": p2, "出/入相": asp['狀態'], "容許度": asp['容許度']})
    return p_data, all_asps, p_pos, p_spd, ascmc, n_cusps if 'n_cusps' in globals() else cusps, r_labels

def get_solar_arc_aspects(jd_natal, jd_transit, natal_p_pos, r_labels):
    age_years = (jd_transit - jd_natal) / 365.2422
    jd_prog = jd_natal + age_years
    sun_n, _ = swe.calc_ut(jd_natal, swe.SUN); sun_p, _ = swe.calc_ut(jd_prog, swe.SUN)
    arc = sun_p[0] - sun_n[0]; sa_aspects = []
    specs = [(0, "合相"), (45, "半四分"), (90, "四分"), (135, "補八分"), (180, "對相")]
    names = [k for k in natal_p_pos.keys() if k not in ["上升", "中天", "北交點"]]
    for p1 in names:
        pos1 = natal_p_pos[p1]; sa_pos = (pos1 + arc) % 360
        for p2 in names:
            if p1 == p2: continue 
            pos2 = natal_p_pos[p2]; diff = abs(sa_pos - pos2)
            if diff > 180: diff = 360 - diff
            for angle, name in specs:
                err = abs(diff - angle)
                if err <= 1.0: 
                    sa_next = (pos1 + arc + 0.001) % 360; diff_next = abs(sa_next - pos2)
                    if diff_next > 180: diff_next = 360 - diff_next
                    state = "入相" if abs(diff_next - angle) < err else "出相"
                    sa_aspects.append({"宮主星A": r_labels.get(p1, ""), "行星A": f"SA {p1}", "相位": name, "宮主星B": r_labels.get(p2, ""), "行星B": f"本命 {p2}", "出/入相": state, "容許度": f"{err:.2f}°"})
    return sa_aspects

def calculate_lots(p_pos, asc, cusps):
    sun_h = get_natal_house(p_pos['太陽'], cusps); is_day = sun_h >= 7
    def calc_lot(base, p1, p2): return (base + p1 - p2) % 360 if is_day else (base + p2 - p1) % 360
    lots = {"福點 (Fortune)": calc_lot(asc, p_pos['月亮'], p_pos['太陽']), "精神點 (Spirit)": calc_lot(asc, p_pos['太陽'], p_pos['月亮'])}
    lots["必然點 (Necessity)"] = calc_lot(asc, lots["福點 (Fortune)"], p_pos['水星'])
    lots["愛神點 (Eros)"] = calc_lot(asc, p_pos['金星'], lots["精神點 (Spirit)"])
    lots["膽識點 (Courage)"] = calc_lot(asc, lots["福點 (Fortune)"], p_pos['火星'])
    lots["勝利點 (Victory)"] = calc_lot(asc, p_pos['木星'], lots["精神點 (Spirit)"])
    lots["復仇點 (Nemesis)"] = calc_lot(asc, lots["福點 (Fortune)"], p_pos['土星'])
    res = []
    for name, pos in lots.items(): h = get_natal_house(pos, cusps); res.append({"希臘點": name, "位置": format_pos(pos), "宮位": f"第 {h} 宮"})
    return res, lots

def get_midpoint_trees(p_pos, orb_limit):
    keys = ["太陽", "月亮", "水星", "金星", "火星", "木星", "土星", "天王星", "海王星", "冥王星"]
    trees = {k: [] for k in keys}
    for i in range(len(keys)):
        for j in range(i+1, len(keys)):
            p1, p2 = keys[i], keys[j]; mid = (p_pos[p1] + p_pos[p2]) / 2
            if abs(p_pos[p1] - p_pos[p2]) > 180: mid = (mid + 180) % 360
            for pA in keys:
                if pA == p1 or pA == p2: continue
                diff = abs(p_pos[pA] - mid) % 90
                if diff <= orb_limit or diff >= (90 - orb_limit): trees[pA].append(f"{p1}/{p2}")
    return [{"星體 (A)": pA, "中點組合 (B/C)": "、".join(c)} for pA, c in trees.items() if c]

def get_solar_return_jd(jd_natal, transit_year, natal_sun_lon):
    ry, rm, rd, rh_float = swe.revjul(jd_natal)
    if rm == 2 and rd == 29: rd = 28
    dt_guess = datetime.datetime(transit_year, rm, rd, 12, 0, tzinfo=datetime.timezone.utc)
    jd_guess = swe.julday(dt_guess.year, dt_guess.month, dt_guess.day, 12.0)
    for _ in range(15):
        sun_pos, _ = swe.calc_ut(jd_guess, swe.SUN); diff = (natal_sun_lon - sun_pos[0])
        if diff > 180: diff -= 360
        elif diff < -180: diff += 360
        if abs(diff) < 0.00001: break
        jd_guess += diff / 0.9856 
    return jd_guess

def get_firdaria_table(is_day, birth_dt):
    diurnal = [('太陽', 10), ('金星', 8), ('水星', 13), ('月亮', 9), ('土星', 11), ('木星', 12), ('火星', 7), ('北交點', 3), ('南交點', 2)]
    nocturnal = [('月亮', 9), ('土星', 11), ('木星', 12), ('火星', 7), ('太陽', 10), ('金星', 8), ('水星', 13), ('北交點', 3), ('南交點', 2)]
    order = diurnal if is_day else nocturnal; table = []; curr_age = 0.0
    for major, length in order:
        if major in ['北交點', '南交點']: table.append({"大運": major, "副運": "-", "開始日期": calc_date(birth_dt, curr_age), "結束日期": calc_date(birth_dt, curr_age + length)})
        else:
            sub_len = length / 7.0; planets_only = [x[0] for x in order if x[0] not in ['北交點', '南交點']]; start_idx = planets_only.index(major)
            for i in range(7): sub = planets_only[(start_idx + i) % 7]; table.append({"大運": major, "副運": sub, "開始日期": calc_date(birth_dt, curr_age + i*sub_len), "結束日期": calc_date(birth_dt, curr_age + (i+1)*sub_len)})
        curr_age += length
    return table

def get_zr_table(start_deg, birth_dt, target_age):
    start_idx = int(start_deg // 30); periods, curr_age, curr_sign = [], 0.0, start_idx; active_l1, active_l2 = "", ""
    for _ in range(8):
        l1_len = ZR_PERIODS[curr_sign]; l2_periods, l2_age, l2_sign = [], curr_age, curr_sign; accumulated_years = 0.0
        while accumulated_years < l1_len - 0.001:
            l2_len_years = ZR_PERIODS[l2_sign] / 12.0; s_date = calc_date(birth_dt, l2_age)
            if accumulated_years + l2_len_years > l1_len:
                e_date = calc_date(birth_dt, curr_age + l1_len); l2_name = f"{TRADITIONAL_RULERS[l2_sign]} ({ZODIAC[l2_sign]})"
                l2_periods.append({"副運 (L2)": l2_name, "開始日期": s_date, "結束日期": e_date})
                if l2_age <= target_age < curr_age + l1_len: active_l2 = l2_name
                break
            else:
                e_date = calc_date(birth_dt, l2_age + l2_len_years); l2_name = f"{TRADITIONAL_RULERS[l2_sign]} ({ZODIAC[l2_sign]})"
                l2_periods.append({"副運 (L2)": l2_name, "開始日期": s_date, "結束日期": e_date})
                if l2_age <= target_age < l2_age + l2_len_years: active_l2 = l2_name
            accumulated_years += l2_len_years; l2_age += l2_len_years; l2_sign = (l2_sign + 1) % 12
        l1_name = f"{TRADITIONAL_RULERS[curr_sign]} ({ZODIAC[curr_sign]})"
        if curr_age <= target_age < curr_age + l1_len: active_l1 = l1_name
        periods.append({"Level 1 (大運)": l1_name, "開始日期": calc_date(birth_dt, curr_age), "結束日期": calc_date(birth_dt, curr_age + l1_len), "L2_data": l2_periods})
        curr_age += l1_len; curr_sign = (curr_sign + 1) % 12
    return periods, active_l1, active_l2

def get_forecasting_data(jd_natal, jd_transit, asc_deg, is_day):
    age_exact = (jd_transit - jd_natal) / 365.2422; age_int = int(age_exact if age_exact > 0 else 0)
    asc_sign_idx = int(asc_deg // 30); prof_sign_idx = (asc_sign_idx + age_int) % 12; prof_sign = ZODIAC[prof_sign_idx]; prof_ruler = TRADITIONAL_RULERS[prof_sign_idx]
    diurnal = [('太陽', 10), ('金星', 8), ('水星', 13), ('月亮', 9), ('土星', 11), ('木星', 12), ('火星', 7), ('北交點', 3), ('南交點', 2)]
    nocturnal = [('月亮', 9), ('土星', 11), ('木星', 12), ('火星', 7), ('太陽', 10), ('金星', 8), ('水星', 13), ('北交點', 3), ('南交點', 2)]
    order = diurnal if is_day else nocturnal; age_mod = age_exact % 75; curr_y = 0; major, major_len = "", 0
    for p, y in order:
        if curr_y <= age_mod < curr_y + y: major, major_len = p, y; break
        curr_y += y
    sub_lord = major
    if major not in ['北交點', '南交點']:
        planets_only = [x[0] for x in order if x[0] not in ['北交點', '南交點']]; start_idx = planets_only.index(major); sub_idx = int((age_mod - curr_y) / (major_len / 7.0)); sub_lord = planets_only[(start_idx + sub_idx) % 7]
    return age_int, age_exact, prof_sign, prof_ruler, major, sub_lord

# ================= 2. 佈局設定 =================
st.set_page_config(page_title="專業占星數據查詢", layout="wide")
now_dt = datetime.datetime.now()

with st.sidebar:
    st.title("⚙️ 參數設定")
    st.subheader("🔑 AI 設定 (Grok)")
    grok_key = st.text_input("Grok API Key", type="password", help="請輸入你的 xAI Grok API Key")
    
    st.divider()
    st.subheader("👶 本命資料")
    gender_in = st.radio("性別", ["男", "女"], horizontal=True)
    date_in = st.text_input("出生日期 (YYYYMMDD)", "19900101")
    time_in = st.text_input("出生時間 (HHMM)", "1200")
    loc_in = st.text_input("出生地點", "Hong Kong")
    
    st.divider()
    st.subheader("🗓️ 流運與太陽返照")
    t_date_in = st.text_input("流運日期 (YYYYMMDD)", now_dt.strftime("%Y%m%d"))
    t_time_in = st.text_input("流運時間 (HHMM)", now_dt.strftime("%H%M"))
    t_loc_in = st.text_input("流運地點", "Hong Kong")
    focus_p = st.selectbox("重點觀察星體", ["顯示全部", "太陽", "月亮", "水星", "金星", "火星", "木星", "土星", "天王星", "海王星", "冥王星"])

try:
    y, m, d = int(date_in[:4]), int(date_in[4:6]), int(date_in[6:8])
    h, mi = int(time_in[:2]), int(time_in[2:])
    ty = int(t_date_in[:4])
    base_birth_dt = datetime.datetime(y, m, d)
    loc = geolocator.geocode(loc_in); t_loc = geolocator.geocode(t_loc_in)
    
    if loc and t_loc:
        tz = tf.timezone_at(lng=loc.longitude, lat=loc.latitude)
        utc = pytz.timezone(tz).localize(datetime.datetime(y, m, d, h, mi)).astimezone(pytz.utc)
        jd_natal = swe.julday(utc.year, utc.month, utc.day, utc.hour + utc.minute/60.0)
        t_tz = tf.timezone_at(lng=t_loc.longitude, lat=t_loc.latitude)
        t_utc = pytz.timezone(t_tz).localize(datetime.datetime(int(t_date_in[:4]), int(t_date_in[4:6]), int(t_date_in[6:8]), int(t_time_in[:2]), int(t_time_in[2:]))).astimezone(pytz.utc)
        jd_transit = swe.julday(t_utc.year, t_utc.month, t_utc.day, t_utc.hour + t_utc.minute/60.0)

        main_col1, main_col2, main_col3 = st.columns([1, 1, 0.4])
        with main_col3:
            st.subheader("📐 容許度")
            orb_h = st.slider("合/對相 Orb", 1.0, 12.0, 8.0, 0.5)
            orb_t = st.slider("三分/四分 Orb", 1.0, 10.0, 7.0, 0.5)
            orb_s = st.slider("六分相 Orb", 0.5, 8.0, 6.0, 0.5)
            orb_mid = st.slider("🌳 中點 Orb", 0.5, 3.0, 1.5, 0.5)
            current_orbs = {"合相": orb_h, "對相": orb_h, "三分": orb_t, "四分": orb_t, "六分": orb_s}

        n_p_data, n_asps, n_draw_pos, n_p_spd, n_ascmc, n_cusps, n_r_labels = calculate_chart_pack(jd_natal, loc.latitude, loc.longitude, current_orbs)
        jd_sr = get_solar_return_jd(jd_natal, ty, n_draw_pos['太陽'])
        sr_p_data, sr_asps, sr_draw_pos, sr_p_spd, sr_ascmc, sr_cusps, sr_r_labels = calculate_chart_pack(jd_sr, t_loc.latitude, t_loc.longitude, current_orbs)
        sa_aspects = get_solar_arc_aspects(jd_natal, jd_transit, n_draw_pos, n_r_labels)
        sun_h = get_natal_house(n_draw_pos['太陽'], n_cusps); is_day = sun_h >= 7
        age_int, age_exact, prof_sign, prof_ruler, f_maj, f_sub = get_forecasting_data(jd_natal, jd_transit, n_ascmc[0], is_day)
        lots_table, lots_raw = calculate_lots(n_draw_pos, n_ascmc[0], n_cusps)
        trees = get_midpoint_trees(n_draw_pos, orb_limit=orb_mid)

        with main_col1:
            st.subheader(f"📍 本命盤 ({loc_in})")
            st.image(draw_astrology_chart(n_draw_pos, n_ascmc[0], n_cusps, n_ascmc[1], focus_planet=focus_p, orb_map=current_orbs), use_container_width=True)
        with main_col2:
            st.subheader(f"☀️ {ty}年 日返盤 ({t_loc_in})")
            st.image(draw_astrology_chart(sr_draw_pos, sr_ascmc[0], sr_cusps, sr_ascmc[1], focus_planet="顯示全部", orb_map=current_orbs), use_container_width=True)

        st.divider()
        tabs = st.tabs(["🪐 本命數據", "⏳ 預測與流運", "☯️ 八字排盤", "🤖 AI 命理分析", "📋 複製給 AI"])
        
        # --- 本命數據分頁 ---
        with tabs[0]:
            c1, c2, c3 = st.columns([1, 1.5, 1])
            with c1: st.dataframe(pd.DataFrame(n_p_data), use_container_width=True, hide_index=True)
            with c2: st.dataframe(pd.DataFrame(n_asps), use_container_width=True, hide_index=True)
            with c3: st.dataframe(pd.DataFrame(lots_table), use_container_width=True, hide_index=True)

        # --- 預測與流運分頁 ---
        with tabs[1]:
            st.markdown(f"### 🎯 {t_date_in} 運勢主軸 (小限：{prof_sign} | 法達：{f_maj}-{f_sub})")
            c1, c2 = st.columns(2)
            with c1: st.subheader("☀️ 流運日弧 (Solar Arc)"); st.dataframe(pd.DataFrame(sa_aspects), use_container_width=True, hide_index=True)
            with c2: st.subheader("🌳 中點樹 (Midpoints)"); st.dataframe(pd.DataFrame(trees), use_container_width=True, hide_index=True)
            st.subheader("⏳ 法達星限全表 (Firdaria)"); st.dataframe(pd.DataFrame(get_firdaria_table(is_day, base_birth_dt)), use_container_width=True, hide_index=True)

        # --- 八字排盤分頁 ---
        with tabs[2]:
            solar_birth = Solar.fromYmdHms(y, m, d, h, mi, 0); bazi = solar_birth.getLunar().getEightChar(); yun = bazi.getYun(1 if gender_in == "男" else 0)
            st.markdown(f"### ☯️ 本命八字：{bazi.getYear()} {bazi.getMonth()} {bazi.getDay()} {bazi.getTime()}")
            da_yuns = yun.getDaYun(); dy_list = []
            for dy in da_yuns[1:9]:
                lns = "、".join([f"{ln.getYear()}({ln.getGanZhi()})" for ln in dy.getLiuNian()[:10]])
                dy_list.append({"大運": dy.getGanZhi(), "起運歲數": f"{dy.getStartAge()}歲", "起運年份": f"{dy.getStartYear()}年", "流年": lns})
            st.dataframe(pd.DataFrame(dy_list), use_container_width=True, hide_index=True)

        # ================= 核心邏輯修正區：數據字串化 (安全換行版) =================
        def get_data_string(mode):
            # mode: 1 (本命), 2 (全部)
            txt = f"【基本資料】\n性別：{gender_in}\n出生時間：{y}年{m}月{d}日 {h:02d}:{mi:02d}\n出生地點：{loc_in}\n"
            
            try:
                sb = Solar.fromYmdHms(y, m, d, h, mi, 0)
                bz = sb.getLunar().getEightChar()
                txt += f"【八字命理】{bz.getYear()}年 {bz.getMonth()}月 {bz.getDay()}日 {bz.getTime()}時\n\n"
            except: 
                pass
            
            txt += "【占星本命盤】\n"
            for p in n_p_data: 
                txt += f"{p['星體']}：{p['星座'].split(' ')[0]} {p['宮位']}\n"
                
            for a in n_asps: 
                txt += f"{a['行星A']}{a['相位']}{a['行星B']} {a['出/入相']}{a['容許度']}\n"
                
            txt += "\n【中點樹】\n"
            for t in trees: 
                txt += f"{t['星體 (A)']}={t['中點組合 (B/C)']}\n"
            
            if mode == 2:
                _, zr_l1, zr_l2 = get_zr_table(lots_raw['精神點 (Spirit)'], base_birth_dt, age_exact)
                txt += "\n【流運與預測】\n"
                txt += f"流運日期：{t_date_in}\n"
                txt += f"小限：{prof_sign}年，主星 {prof_ruler}\n"
                txt += f"法達：{f_maj}-{f_sub}\n"
                txt += f"黃道釋放(Spirit)：L1-{zr_l1}, L2-{zr_l2}\n"
                
                txt += "\n【日返盤】\n"
                for p in sr_p_data: 
                    txt += f"{p['星體']}：{p['星座'].split(' ')[0]} {p['宮位']}\n"
                    
                txt += "\n【流運日弧】\n"
                for a in sa_aspects: 
                    txt += f"{a['行星A']}{a['相位']}{a['行星B']} {a['出/入相']}\n"
                    
                txt += "\n【八字大運流年】\n"
                dy_now = [dy for dy in da_yuns if dy.getStartYear() <= int(t_date_in[:4]) < dy.getStartYear()+10]
                if dy_now: 
                    txt += f"目前大運：{dy_now[0].getGanZhi()}\n"
                    txt += f"流年：{t_date_in[:4]}年\n"
                    
            return txt

        # --- 📋 複製給 AI 分頁 ---
        with tabs[4]:
            ai_copy_mode = st.radio("複製模式", ["僅限本命盤數據", "包含占星及八字數據"], horizontal=True)
            st.code(get_data_string(1 if ai_copy_mode == "僅限本命盤數據" else 2), language="plaintext")

        # --- 🤖 AI 命理分析分頁 (Grok 版) ---
        with tabs[3]:
            st.markdown("### 🤖 AI 智慧命理諮詢 (Powered by Grok)")
            if not grok_key:
                st.warning("請先在側邊欄輸入 Grok API Key 才能使用 AI 分析功能。")
            else:
                ai_option = st.radio("請選擇分析類型", ["1. 本命全方位格局分析", "2. 年度決策精算報告"], horizontal=True)
                
                if st.button("🚀 開始 AI 分析"):
                    with st.spinner("Grok 正在研讀你的命盤數據，請稍候..."):
                        try:
                            # 初始化 xAI 的 Grok 客戶端
                            client = OpenAI(
                                api_key=grok_key,
                                base_url="https://api.xai.com/v1",
                            )
                            
                            if ai_option == "1. 本命全方位格局分析":
                                system_prompt = "你是一位精通東方傳統「子平八字」與西方「現代占星學」的資深命理大師。你擅長揉合東西方命理精髓，透過八字的五行能量與占星的行星相位，為客戶提供既有哲學深度又具備實際指導意義的人生解讀。"
                                user_prompt = (
                                    "**任務 (Task)：** 請根據以下提供的客戶出生資訊，進行一次全方位的「一生整體格局解讀」。你需要識別命盤中的核心矛盾、天賦潛能、以及人生各階段的重要轉折點。\n\n"
                                    "**情境與細節 (Context)：**\n"
                                    "1. 解讀對象為我的客戶，請保持專業、中立且富有同理心的口吻。\n"
                                    "2. 分析須兼顧八字的格局與占星的重要配置。\n"
                                    "3. 若八字與占星的結論一致，請加強說明；若有衝突，請以專業角度解釋能量的拉扯與應對建議。\n\n"
                                    "**輸出格式 (Format)：**\n"
                                    "請以「結構化報告」形式呈現，並嚴格包含以下五個章節：\n"
                                    "1. **核心格局：** 簡述八字日元特質及占星命主星影響（定調人生底色）。\n"
                                    "2. **事業與財富：** 分析一生事業高度、適合行業及財庫狀況。\n"
                                    "3. **感情與人際：** 解讀正緣特徵、感情模式及與他人互動的盲點。\n"
                                    "4. **人生大運/長期趨勢：** 概括一生中重要的起伏階段與轉折年份建議。\n"
                                    "5. **開運建議：** 提供五行調整或心理層面的轉念建議。\n\n"
                                    f"**數據資訊：**\n{get_data_string(1)}"
                                )
                            else:
                                system_prompt = "你是一位精通東西方運算邏輯的「現代決策精算師」。你的任務是將複雜的古典波斯占星與八字數據，轉化為一份零術語、純結果的現代生活運勢報告。"
                                user_prompt = (
                                    "**任務 (Task)：** 請根據以下提供的「本命與流年數據」，直接輸出年度運勢結果。\n\n"
                                    "**嚴格要求：**\n"
                                    "1. 禁止 出現任何術數名詞（例如：法達、小限、傷官、偏印、宮位、相位等）。\n"
                                    "2. 禁止 解釋推導過程，只需要給出最終的趨勢判斷與建議。\n"
                                    "3. 語氣 必須專業、果斷、具備現代感，像是一份商業決策摘要。\n\n"
                                    "**輸出格式 (Format)：**\n"
                                    "請統一使用以下模塊進行輸出：\n"
                                    "📊 年度核心摘要（一句話總結）\n"
                                    "1. 事業職場 (Career) - 核心走向 / 關鍵機會 / 競爭力\n"
                                    "2. 財運表現 (Wealth) - 收入預測 / 投資與偏財 / 財務預警\n"
                                    "3. 家庭關係 (Family) - 內部氛圍 / 家庭事務\n"
                                    "4. 愛情對象 (Relationship) - 現狀預測 / 溝通焦點\n"
                                    "5. 健康狀態 (Health) - 身心預測 / 生活建議\n"
                                    "6. 意外與風險 (Risks) - 風險預警 / 高風險時段\n"
                                    "💡 最終行動指南 - 條列式提供 3 個建議\n\n"
                                    f"**數據資訊：**\n{get_data_string(2)}"
                                )
                            
                            # 呼叫 Grok API
                            response = client.chat.completions.create(
                                model="grok-2-latest", 
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_prompt}
                                ]
                            )
                            
                            st.markdown(response.choices[0].message.content)
                        except Exception as e:
                            st.error(f"Grok API 分析發生錯誤：{e}")

    else: st.error("請在側邊欄輸入正確的地點名稱。")
except Exception as e: st.info(f"請在側邊欄輸入完整的出生及流運資料。")
