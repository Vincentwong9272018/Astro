import streamlit as st
import os
import datetime
import swisseph as swe
import pytz
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

# 導入你原本嘅繪圖模組 (如果有)
try:
    from Astro_Drawer import calculate_natal_data, draw_astrology_chart
except ImportError:
    st.warning("找不到 Astro_Drawer.py，將不會顯示星盤圖片")

# ================= 設定區 =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EPHE_PATH = os.path.join(BASE_DIR, 'ephe')

if os.path.exists(EPHE_PATH):
    swe.set_ephe_path(EPHE_PATH)

geolocator = Nominatim(user_agent="astro_web_app")
tf = TimezoneFinder()

# ================= 網頁介面設計 =================
st.set_page_config(page_title="AI 占星系統", page_icon="🔮")
st.title("🔮 AI 古典占星與卜卦系統")

st.markdown("歡迎使用網頁版占星系統！請在下方輸入你的資料：")

# 建立輸入表格
with st.form("natal_form"):
    col1, col2 = st.columns(2)
    with col1:
        date_input = st.text_input("出生日期 (YYYYMMDD)", placeholder="例如: 19900101")
    with col2:
        time_input = st.text_input("出生時間 (HHMM)", placeholder="例如: 1230")
    
    loc_input = st.text_input("出生地點", placeholder="例如: Hong Kong")
    
    # 提交按鈕
    submitted = st.form_submit_button("📊 生成本命盤")

# 當撳咗按鈕之後嘅動作
if submitted:
    if not date_input or not time_input or not loc_input:
        st.error("請填寫所有資料！")
    else:
        with st.spinner("正在計算星盤數據..."):
            try:
                # 處理時間
                y, m, d = int(date_input[:4]), int(date_input[4:6]), int(date_input[6:8])
                h, mi = int(time_input[:2]), int(time_input[2:])
                
                # 處理地點與時區
                loc = geolocator.geocode(loc_input)
                if not loc:
                    st.error("找不到該地點，請輸入更準確的城市名稱。")
                else:
                    tz = tf.timezone_at(lng=loc.longitude, lat=loc.latitude)
                    utc = pytz.timezone(tz).localize(datetime.datetime(y, m, d, h, mi)).astimezone(pytz.utc)
                    jd_utc = swe.julday(utc.year, utc.month, utc.day, utc.hour + utc.minute/60.0)
                    
                    st.success(f"成功定位：{loc_input} (緯度: {loc.latitude:.2f}, 經度: {loc.longitude:.2f})")
                    
                    # === 呢度係畫圖 (如有) ===
                    try:
                        pos, asc, cusps, mc = calculate_natal_data(utc.year, utc.month, utc.day, utc.hour, utc.minute, loc.latitude, loc.longitude)
                        img = draw_astrology_chart(pos, asc, cusps, mc)
                        st.image(img, caption=f"📍 {loc_input} 星盤")
                    except Exception as e:
                        st.error(f"畫圖失敗：{e}")

                    # === 呢度可以放你原本嘅 build_chart_text 函數 ===
                    # 暫時印出 Julian Day 做測試，證明行得通
                    st.info(f"Julian Day (UTC): {jd_utc}")
                    
            except Exception as e:
                st.error(f"計算過程發生錯誤: {e}")