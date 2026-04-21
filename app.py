import streamlit as st
import folium
from streamlit_folium import st_folium
import math

# Sayfa ayarları
st.set_page_config(page_title="Memur Emlak & Tayin Haritası", layout="wide")
st.title("🗺️ Memur Tayin & Emlak Uygulaması")

# --- 1. MESAFE HESAPLAMA FONKSİYONU (Haversine) ---
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Dünya yarıçapı (km)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return round(R * c, 2)

# --- 2. VERİ ALTYAPISI (Kurumlar ve Evler) ---
# Örnek Kurumlar
institutions = [
    {"name": "Valilik", "lat": 38.6810, "lon": 39.2264},
    {"name": "Eğitim ve Araştırma Hastanesi", "lat": 38.6738, "lon": 39.1963},
    {"name": "Adliye", "lat": 38.6705, "lon": 39.2215}
]

# Kullanıcıların eklediği evleri tutmak için Session State
if 'houses' not in st.session_state:
    st.session_state.houses = []

# --- 3. ARAYÜZ VE HARİTA BÖLÜMÜ ---
col1, col2 = st.columns([2, 1]) # Harita geniş, form dar olsun

with col1:
    st.markdown("### 📍 İlan Haritası")
    st.info("Haritada bir yere tıklayarak koordinatları sağdaki forma otomatik alabilirsiniz.")
    
    # Haritayı oluştur (Başlangıç koordinatı)
    m = folium.Map(location=[38.6748, 39.2225], zoom_start=13)

    # Kurumları haritaya ekle (Mavi ikon)
    for inst in institutions:
        folium.Marker(
            [inst["lat"], inst["lon"]],
            popup=f"<b>🏢 {inst['name']}</b>",
            tooltip=inst["name"],
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)

    # Kullanıcı evlerini haritaya ekle (Yeşil ikon)
    for house in st.session_state.houses:
        # Kurumlara olan mesafeleri hesapla ve popup içine yaz
        distances_html = "<ul>"
        for inst in institutions:
            dist = calculate_distance(house["lat"], house["lon"], inst["lat"], inst["lon"])
            distances_html += f"<li>{inst['name']}: {dist} km</li>"
        distances_html += "</ul>"

        popup_content = f"""
        <div style="width:200px">
            <h4>{house['title']}</h4>
            <p><b>Kira:</b> {house['price']} TL</p>
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

    # Haritayı Streamlit'te göster ve tıklama verilerini al
    map_data = st_folium(m, width=800, height=500)

with col2:
    st.markdown("### 🏠 Yeni Ev İlanı Ekle")
    
    # Haritaya tıklandıysa koordinatları otomatik al
    clicked_lat = 38.6748
    clicked_lon = 39.2225
    if map_data and map_data.get("last_clicked"):
        clicked_lat = map_data["last_clicked"]["lat"]
        clicked_lon = map_data["last_clicked"]["lng"]
        st.success("Koordinatlar haritadan alındı!")

    # İlan Ekleme Formu
    with st.form("add_house_form"):
        title = st.text_input("İlan Başlığı (Örn: Hastaneye yakın 3+1)")
        price = st.number_input("Kira Ücreti (TL)", min_value=0, step=500)
        
        # Haritadan gelen değerleri varsayılan olarak göster
        lat = st.number_input("Enlem (Haritadan tıklayabilirsiniz)", value=clicked_lat, format="%.6f")
        lon = st.number_input("Boylam (Haritadan tıklayabilirsiniz)", value=clicked_lon, format="%.6f")
        
        comment = st.text_area("Ev hakkında yorumlar ve detaylar")
        image_url = st.text_input("Görsel Linki (İsteğe bağlı url)")
        
        submitted = st.form_submit_button("İlanı Haritaya Ekle")
        
        if submitted:
            if title and price > 0:
                new_house = {
                    "title": title,
                    "price": price,
                    "lat": lat,
                    "lon": lon,
                    "comment": comment,
                    "image_url": image_url
                }
                st.session_state.houses.append(new_house)
                st.success("Ev başarıyla eklendi! Haritayı güncellemek için sayfada herhangi bir yere tıklayın veya yenileyin.")
                st.rerun() # Form gönderildikten sonra haritanın güncellenmesi için sayfayı yeniler
            else:
                st.error("Lütfen başlık ve geçerli bir fiyat girin.")

# --- 4. LİSTE GÖRÜNÜMÜ ---
if len(st.session_state.houses) > 0:
    st.markdown("---")
    st.markdown("### 📋 Eklenen İlanlar Listesi")
    for idx, house in enumerate(st.session_state.houses):
        with st.expander(f"{house['title']} - {house['price']} TL"):
            st.write(f"**Açıklama:** {house['comment']}")
            if house['image_url']:
                st.image(house['image_url'], width=300)
