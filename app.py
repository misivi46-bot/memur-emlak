import streamlit as st
import folium
from streamlit_folium import st_folium
import math
import base64

# Sayfa ayarları
st.set_page_config(page_title="Memur Emlak & Tayin Haritası", layout="wide")
st.title("🗺️ Memur Tayin & Emlak Uygulaması")

# --- 1. MESAFE HESAPLAMA FONKSİYONU ---
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return round(R * c, 2)

# --- 2. VERİ ALTYAPISI ---
institutions = [
    {"name": "Valilik", "lat": 38.6810, "lon": 39.2264},
    {"name": "Eğitim ve Araştırma Hastanesi", "lat": 38.6738, "lon": 39.1963},
    {"name": "Adliye", "lat": 38.6705, "lon": 39.2215}
]

if 'houses' not in st.session_state:
    st.session_state.houses = []

# --- 3. ARAYÜZ VE HARİTA BÖLÜMÜ ---
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("### 📍 İlan Haritası")
    st.info("Haritada bir yere tıklayarak koordinatları sağdaki forma otomatik alabilirsiniz.")
    
    # Haritayı oluştur (Google Hibrit Görünüm)
    m = folium.Map(
        location=[38.6748, 39.2225], 
        zoom_start=13,
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google Hybrid'
    )

    for inst in institutions:
        folium.Marker(
            [inst["lat"], inst["lon"]],
            popup=f"<b>🏢 {inst['name']}</b>",
            tooltip=inst["name"],
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)

    for house in st.session_state.houses:
        distances_html = "<ul>"
        for inst in institutions:
            dist = calculate_distance(house["lat"], house["lon"], inst["lat"], inst["lon"])
            distances_html += f"<li>{inst['name']}: {dist} km</li>"
        distances_html += "</ul>"

        # ÇÖZÜM UYGULANAN KISIM 1: .get() metodu ile güvenli sorgulama
        image_html = ""
        if house.get('image_b64'): 
            image_html = f'<img src="data:image/jpeg;base64,{house.get("image_b64")}" style="width:100%; border-radius:8px; margin-bottom:10px;">'

        popup_content = f"""
        <div style="width:220px">
            {image_html}
            <h4>{house['title']}</h4>
            <p style="color:green; font-size:16px;"><b>Kira:</b> {house['price']} TL</p>
            <p><b>Açıklama:</b> {house['comment']}</p>
            <b>Kurumlara Uzaklık:</b>
            {distances_html}
        </div>
        """
        
        folium.Marker(
            [house["lat"], house["lon"]],
            popup=folium.Popup(popup_content, max_width=300),
            tooltip=house["title"],
            icon=folium.Icon(color="green", icon="home")
        ).add_to(m)

    map_data = st_folium(m, width=800, height=500)

with col2:
    st.markdown("### 🏠 Yeni Ev İlanı Ekle")
    
    clicked_lat = 38.6748
    clicked_lon = 39.2225
    if map_data and map_data.get("last_clicked"):
        clicked_lat = map_data["last_clicked"]["lat"]
        clicked_lon = map_data["last_clicked"]["lng"]

    with st.form("add_house_form"):
        title = st.text_input("İlan Başlığı (Örn: Hastaneye yakın 3+1)")
        price = st.number_input("Kira Ücreti (TL)", min_value=0, step=500)
        
        lat = st.number_input("Enlem (Haritadan tıklayın)", value=clicked_lat, format="%.6f")
        lon = st.number_input("Boylam (Haritadan tıklayın)", value=clicked_lon, format="%.6f")
        
        comment = st.text_area("Ev hakkında yorumlar ve detaylar")
        
        uploaded_file = st.file_uploader("Ev Fotoğrafı Yükle", type=["png", "jpg", "jpeg"])
        
        submitted = st.form_submit_button("İlanı Haritaya Ekle")
        
        if submitted:
            if title and price > 0:
                image_b64 = ""
                if uploaded_file is not None:
                    image_b64 = base64.b64encode(uploaded_file.read()).decode()

                new_house = {
                    "title": title,
                    "price": price,
                    "lat": lat,
                    "lon": lon,
                    "comment": comment,
                    "image_b64": image_b64
                }
                st.session_state.houses.append(new_house)
                st.success("Ev başarıyla eklendi!")
                st.rerun()
            else:
                st.error("Lütfen başlık ve geçerli bir fiyat girin.")

# --- 4. LİSTE GÖRÜNÜMÜ ---
if len(st.session_state.houses) > 0:
    st.markdown("---")
    st.markdown("### 📋 Eklenen İlanlar Listesi")
    for house in st.session_state.houses:
        with st.expander(f"{house['title']} - {house['price']} TL"):
            st.write(f"**Açıklama:** {house['comment']}")
            # ÇÖZÜM UYGULANAN KISIM 2: .get() metodu ile güvenli sorgulama
            if house.get('image_b64'):
                st.markdown(f'<img src="data:image/jpeg;base64,{house.get("image_b64")}" width="300" style="border-radius:10px;">', unsafe_allow_html=True)
