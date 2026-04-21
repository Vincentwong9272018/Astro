import swisseph as swe
import numpy as np
import matplotlib.pyplot as plt
import io

# ================= 設定區 =================
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

ZODIAC_SYMBOLS = ['♈', '♉', '♊', '♋', '♌', '♍', '♎', '♏', '♐', '♑', '♒', '♓']

# 【重點修正】加入咗 '上升' 同 '中天' 嘅專屬符號與顏色
PLANET_SYMBOLS = {
    '太陽': {'sym': '☉', 'color': '#e67e22'}, '月亮': {'sym': '☽', 'color': '#7f8c8d'},
    '水星': {'sym': '☿', 'color': '#27ae60'}, '金星': {'sym': '♀', 'color': '#2ecc71'},
    '火星': {'sym': '♂', 'color': '#e74c3c'}, '木星': {'sym': '♃', 'color': '#d35400'},
    '土星': {'sym': '♄', 'color': '#2c3e50'}, '天王星': {'sym': '♅', 'color': '#8e44ad'},
    '海王星': {'sym': '♆', 'color': '#2980b9'}, '冥王星': {'sym': '♇', 'color': '#34495e'},
    '北交點': {'sym': '☊', 'color': '#000000'},
    '上升': {'sym': 'ASC', 'color': '#c0392b'}, '中天': {'sym': 'MC', 'color': '#2980b9'}
}

def get_aspects(positions, orb_map):
    aspects = []
    specs = [(0, "合相", '#95a5a6'), (180, "對相", '#2980b9'), (120, "三分", '#27ae60'), (90, "四分", '#e74c3c'), (60, "六分", '#2ecc71')]
    p_names = list(positions.keys())
    for i in range(len(p_names)):
        for j in range(i+1, len(p_names)):
            p1, p2 = p_names[i], p_names[j]
            diff = abs(positions[p1] - positions[p2])
            if diff > 180: diff = 360 - diff
            for angle, name, color in specs:
                current_orb = orb_map.get(name, 8.0)
                if abs(diff - angle) <= current_orb:
                    aspects.append((p1, p2, color))
                    break
    return aspects

def draw_astrology_chart(positions, asc_degree, cusps, mc_degree, focus_planet="顯示全部", orb_map=None):
    all_aspects = get_aspects(positions, orb_map or {})
    
    if focus_planet != "顯示全部":
        related_planets = {focus_planet}
        filtered_aspects = []
        for p1, p2, color in all_aspects:
            if p1 == focus_planet or p2 == focus_planet:
                related_planets.add(p1); related_planets.add(p2)
                filtered_aspects.append((p1, p2, color))
        planets_to_draw = list(related_planets)
        aspects_to_draw = filtered_aspects
    else:
        planets_to_draw = list(positions.keys())
        aspects_to_draw = all_aspects

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={'projection': 'polar'})
    ax.set_theta_zero_location("W") 
    ax.set_theta_direction(-1)      
    def get_canvas_angle(zodiac_degree): return np.deg2rad(asc_degree - zodiac_degree)
    ax.axis('off')

    # 繪製圓環
    ax.add_artist(plt.Circle((0, 0), 1.0, transform=ax.transData._b, fill=False, color='#333', lw=1.2))
    ax.add_artist(plt.Circle((0, 0), 0.82, transform=ax.transData._b, fill=False, color='#333', lw=1.2))
    ax.add_artist(plt.Circle((0, 0), 0.45, transform=ax.transData._b, fill=False, color='#ccc', lw=0.8))

    # 十二星座符號
    for i in range(12):
        angle = get_canvas_angle(i * 30)
        ax.plot([angle, angle], [0.82, 1.0], color='#888', lw=0.8)
        mid_angle = get_canvas_angle(i * 30 + 15)
        ax.text(mid_angle, 0.91, ZODIAC_SYMBOLS[i], fontsize=16, ha='center', va='center')

    # 宮位界線
    c_list = list(cusps)[1:] if len(cusps) == 13 else list(cusps)
    for i, deg in enumerate(c_list):
        angle = get_canvas_angle(deg)
        color = 'red' if i == 0 else ('blue' if i == 9 else '#666')
        ax.plot([angle, angle], [0.45, 0.82], color=color, lw=1.5 if i in [0,9] else 0.7)

    # 相位連線
    for p1, p2, color in aspects_to_draw:
        a1, a2 = get_canvas_angle(positions[p1]), get_canvas_angle(positions[p2])
        ax.plot([a1, a2], [0.45, 0.45], color=color, lw=1.2, alpha=0.4)

    # 行星圖示
    for planet in planets_to_draw:
        if planet not in positions: continue
        deg = positions[planet]
        angle = get_canvas_angle(deg)
        sym = PLANET_SYMBOLS.get(planet, {'sym': '?', 'color': '#000'})
        
        # 【重點修正】因為 ASC 同 MC 係英文字，所以將字體縮小啲同加粗，等佢排版靚啲
        f_size = 13 if planet in ['上升', '中天'] else 20
        f_weight = 'bold' if planet in ['上升', '中天'] else 'normal'
        
        ax.text(angle, 0.70, sym['sym'], fontsize=f_size, ha='center', va='center', color=sym['color'], fontweight=f_weight)
        deg_txt = f"{int(deg % 30)}°"
        ax.text(angle, 0.55, deg_txt, fontsize=9, ha='center', va='center', color='#444')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=140)
    buf.seek(0)
    plt.close()
    return buf
