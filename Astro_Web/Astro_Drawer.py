import swisseph as swe
import datetime
import numpy as np
import matplotlib.pyplot as plt
import io

# ================= 設定區 =================
# 確保字體支援占星符號
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

ZODIAC_SYMBOLS = ['♈', '♉', '♊', '♋', '♌', '♍', '♎', '♏', '♐', '♑', '♒', '♓']
PLANET_SYMBOLS = {
    '太陽': {'sym': '☉', 'color': '#e67e22'}, '月亮': {'sym': '☽', 'color': '#7f8c8d'},
    '水星': {'sym': '☿', 'color': '#27ae60'}, '金星': {'sym': '♀', 'color': '#2ecc71'},
    '火星': {'sym': '♂', 'color': '#e74c3c'}, '木星': {'sym': '♃', 'color': '#d35400'},
    '土星': {'sym': '♄', 'color': '#2c3e50'}, '天王星': {'sym': '♅', 'color': '#8e44ad'},
    '海王星': {'sym': '♆', 'color': '#2980b9'}, '冥王星': {'sym': '♇', 'color': '#34495e'},
    '北交點': {'sym': '☊', 'color': '#000000'}
}

# ================= 1. 核心計算 =================
def calculate_natal_data(year, month, day, hour, minute, lat, lon):
    jd_utc = swe.julday(year, month, day, hour + minute/60.0)
    
    planets_to_calc = {
        "太陽": swe.SUN, "月亮": swe.MOON, "水星": swe.MERCURY, "金星": swe.VENUS,
        "火星": swe.MARS, "木星": swe.JUPITER, "土星": swe.SATURN, "天王星": swe.URANUS,
        "海王星": swe.NEPTUNE, "冥王星": swe.PLUTO, "北交點": swe.TRUE_NODE
    }
    
    positions = {}
    for name, p_id in planets_to_calc.items():
        res, _ = swe.calc_ut(jd_utc, p_id)
        positions[name] = res[0]
        
    cusps, ascmc = swe.houses(jd_utc, lat, lon, b'P')
    asc_degree = ascmc[0]
    mc_degree = ascmc[1] # 取得中天度數
    
    return positions, asc_degree, cusps, mc_degree

def get_aspects(positions):
    aspects = []
    specs = [
        (0, "合相", 8, '#95a5a6', 2), 
        (180, "對相", 8, '#2980b9', 1.5), 
        (120, "三分", 7, '#27ae60', 1.5), 
        (90, "四分", 7, '#e74c3c', 1.5), 
        (60, "六分", 6, '#2ecc71', 1)
    ]
    p_names = list(positions.keys())
    for i in range(len(p_names)):
        for j in range(i+1, len(p_names)):
            p1, p2 = p_names[i], p_names[j]
            deg1, deg2 = positions[p1], positions[p2]
            diff = abs(deg1 - deg2)
            if diff > 180: diff = 360 - diff
            
            for angle, name, orb, color, lw in specs:
                if abs(diff - angle) <= orb:
                    aspects.append((p1, p2, color, lw))
                    break
    return aspects

# ================= 2. 畫圖模組 =================
def draw_astrology_chart(positions, asc_degree, cusps, mc_degree):
    aspects = get_aspects(positions)
    
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={'projection': 'polar'})
    ax.set_theta_zero_location("W") 
    ax.set_theta_direction(-1)      
    
    def get_canvas_angle(zodiac_degree):
        angle_deg = (asc_degree - zodiac_degree)
        return np.deg2rad(angle_deg)

    ax.axis('off')

    # 畫同心圓
    ax.add_artist(plt.Circle((0, 0), 1.0, transform=ax.transData._b, fill=False, color='#333', lw=1.5))
    ax.add_artist(plt.Circle((0, 0), 0.85, transform=ax.transData._b, fill=False, color='#333', lw=1.5))
    ax.add_artist(plt.Circle((0, 0), 0.5, transform=ax.transData._b, fill=False, color='#ccc', lw=1))

    # 1. 十二星座
    for i in range(12):
        sign_start_deg = i * 30
        angle_rad = get_canvas_angle(sign_start_deg)
        ax.plot([angle_rad, angle_rad], [0.85, 1.0], color='#888', lw=1)
        mid_angle_rad = get_canvas_angle(sign_start_deg + 15)
        ax.text(mid_angle_rad, 0.925, ZODIAC_SYMBOLS[i], fontsize=18, ha='center', va='center', color='#555')

    # 2. 宮位界線及 ASC/MC 度數
    c_list = list(cusps)[1:] if len(cusps) == 13 else list(cusps)
    for i, cusp_deg in enumerate(c_list):
        angle_rad = get_canvas_angle(cusp_deg)
        is_angle = (i in [0, 3, 6, 9]) # 1, 4, 7, 10 宮
        
        lw = 2 if is_angle else 1
        ls = '-' if is_angle else '--'
        color = 'red' if i == 0 else ('blue' if i == 9 else '#666')
        
        ax.plot([angle_rad, angle_rad], [0.5, 0.85], color=color, lw=lw, linestyle=ls)
        
        # 顯示 ASC 和 MC 的精確度數
        if i == 0: # ASC
            deg_txt = f"{int(cusp_deg % 30)}°"
            ax.text(angle_rad, 0.45, f"ASC\n{deg_txt}", fontsize=10, color='red', fontweight='bold', ha='center')
        elif i == 9: # MC
            deg_txt = f"{int(cusp_deg % 30)}°"
            ax.text(angle_rad, 0.45, f"MC\n{deg_txt}", fontsize=10, color='blue', fontweight='bold', ha='center')

    # 3. 相位連線
    for p1, p2, color, lw in aspects:
        a1, a2 = get_canvas_angle(positions[p1]), get_canvas_angle(positions[p2])
        ax.plot([a1, a2], [0.5, 0.5], color=color, lw=lw, alpha=0.4)

    # 4. 行星及其度數
    drawn_angles = []
    for planet, deg in positions.items():
        angle_rad = get_canvas_angle(deg)
        radius = 0.72
        for drawn_a in drawn_angles:
            if abs(angle_rad - drawn_a) < 0.15: radius += 0.08
        drawn_angles.append(angle_rad)
        
        sym_info = PLANET_SYMBOLS.get(planet, {'sym': '?', 'color': '#000'})
        
        # 畫符號
        ax.text(angle_rad, radius, sym_info['sym'], fontsize=20, ha='center', va='center', color=sym_info['color'])
        
        # 畫度數 (顯示在符號下方)
        deg_str = f"{int(deg % 30)}°"
        ax.text(angle_rad, radius - 0.06, deg_str, fontsize=9, ha='center', va='center', color='#555')
        
        ax.plot([angle_rad, angle_rad], [0.5, radius - 0.08], color='#eee', lw=0.5)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    buf.seek(0)
    plt.close()
    return buf