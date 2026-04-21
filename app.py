import streamlit as st
import folium
from streamlit_folium import st_folium
import math
import base64

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Memur Emlak & Tayin Haritası", layout="wide")

# --- 1. ZARARLI İÇERİK FİLTRESİ ---
YASAKLI_KELIMELER = ["aptal", "salak", "parti", "siyaset", "ırk", "defol", "lan"]

def icerik_uygun_mu(metin):
    metin_kucuk = metin.lower()
    for kelime in YASAKLI_KELIMELER:
        if kelime in metin_kucuk:
            return False
    return True

# --- 2. VERİ VE KULLANICI ALTYAPISI ---
institutions = [
    {"name": "Valilik", "lat": 38.6810, "lon": 39.2264},
    {"name": "Eğitim ve Araştırma Hastanesi", "lat": 38.6738, "lon": 39.1963},
    {"name": "Adliye", "lat": 38.6705, "lon": 39.2215}
]

# Hafızadaki Evler
if 'houses' not in st.session_state:
    st.session_state.houses = []
    
# Kullanıcı Veritabanı (Admin hesabı varsayılan olarak var)
if 'users' not in st.session_state:
    st.session_state.users = {
        "admin": {"sifre": "admin123", "rol": "yonetici", "ad": "Sistem Yöneticisi"}
    }

# Oturum Durumu
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.session_state.user_role = None

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return round(R * c, 2)


# --- 3. YAN MENÜ (KAYIT / GİRİŞ / PROFİL KONTROLÜ) ---
with st.sidebar:
    st.title("🔑 Kullanıcı İşlemleri")
    
    # EĞER GİRİŞ YAPILMAMIŞSA
    if not st.session_state.logged_in:
        # Sekmeli yapı yerine radyo butonu ile Giriş/Kayıt geçişi
        secim = st.radio("Ne yapmak istersiniz?", ["Giriş Yap", "Üye Ol"])
        
        if secim == "Giriş Yap":
            st.markdown("### Sisteme Giriş")
            with st.form("login_form"):
                kullanici_adi = st.text_input("Kullanıcı Adı")
                sifre = st.text_input("Şifre", type="password")
                giris_yap_btn = st.form_submit_button("Giriş Yap")
                
                if giris_yap_btn:
                    if kullanici_adi in st.session_state.users and st.session_state.users[kullanici_adi]["sifre"] == sifre:
                        st.session_state.logged_in = True
                        st.session_state.current_user = kullanici_adi
                        st.session_state.user_role = st.session_state.users[kullanici_adi]["rol"]
                        st.success("Giriş başarılı!")
                        st.rerun()
                    else:
                        st.error("Hatalı kullanıcı adı veya şifre!")
                        
        elif secim == "Üye Ol":
            st.markdown("### Yeni Hesap Oluştur")
            with st.form("signup_form"):
                yeni_ad = st.text_input("Adınız ve Soyadınız*")
                yeni_kullanici = st.text_input("Kullanıcı Adı Belirleyin*")
                yeni_sifre = st.text_input("Şifre Belirleyin*", type="password")
                kayit_ol_btn = st.form_submit_button("Kayıt Ol")
                
                if kayit_ol_btn:
                    if not yeni_ad or not yeni_kullanici or not yeni_sifre:
                        st.error("Lütfen tüm alanları doldurun.")
                    elif yeni_kullanici in st.session_state.users:
                        st.error("Bu kullanıcı adı zaten kullanılıyor. Lütfen başka bir tane seçin.")
                    else:
                        # Yeni kullanıcıyı sisteme ekle (Varsayılan rol: kullanici)
                        st.session_state.users[yeni_kullanici] = {"sifre": yeni_sifre, "rol": "kullanici", "ad": yeni_ad}
                        st.success("Hesabınız başarıyla oluşturuldu! Yukarıdan 'Giriş Yap' sekmesine geçerek girebilirsiniz.")

        st.markdown("---")
        st.caption("Not: Test Yönetici Hesabı -> Kullanıcı Adı: `admin` | Şifre: `admin123`")

    # EĞER GİRİŞ YAPILMIŞSA
    else:
        st.success(f"Hoş geldin, {st.session_state.users[st.session_state.current_user]['ad']}")
        st.write(f"🛡️ **Yetki:** {st.session_state.user_role.upper()}")
        
        my_houses = [h for h in st.session_state.houses if h.get("owner") == st.session_state.current_user]
        st.write(f"Eklediğiniz İlan Sayısı: **{len(my_houses)}**")
        
        if st.button("🚪 Çıkış Yap"):
            st.session_state.logged_in = False
            st.session_state.current_user = None
            st.session_state.user_role = None
            st.rerun()


# --- 4. ANA EKRAN (HARİTA VE SEKMELER) ---
st.title("🗺️ Memur Tayin & Emlak Uygulaması")

tab_harita, tab_ekle, tab_yonetim = st.tabs(["📍 Harita (Herkese Açık)", "🏠 Yeni İlan Ekle (Sadece Üyeler)", "⚙️ İlan Yönetimi (Sadece Üyeler)"])

# -- SEKME 1: HARİTA (HER ZAMAN GÖRÜNÜR) --
with tab_harita:
    if not st.session_state.logged_in:
        st.info("👋 Haritadaki kurumları görebilirsiniz. İlanları görmek ve ev eklemek için lütfen sol menüden giriş yapın veya üye olun.")
    else:
        st.success("Haritadaki kurumlara tıklayarak detayları, yeşil ev ikonlarına tıklayarak ilan detaylarını görebilirsiniz.")

    # Haritayı oluştur
    m = folium.Map(location=[38.6748, 39.2225], zoom_start=13, tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google Hybrid')

    # Kurumları haritaya ekle (HER ZAMAN ÇALIŞIR)
    for inst in institutions:
        folium.Marker(
            [inst["lat"], inst["lon"]],
            popup=f"<b>🏢 {inst['name']}</b>",
            tooltip=inst["name"],
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)

    # Evleri haritaya ekle (SADECE GİRİŞ YAPILDIYSA ÇALIŞIR)
    if st.session_state.logged_in:
        for house in st.session_state.houses:
            distances_html = "<ul>"
            for inst in institutions:
                dist = calculate_distance(house["lat"], house["lon"], inst["lat"], inst["lon"])
                distances_html += f"<li>{inst['name']}: {dist} km</li>"
            distances_html += "</ul>"

            image_html = ""
            if house.get('image_b64'):
                image_html = f'<img src="data:image/jpeg;base64,{house.get("image_b64")}" style="width:100%; border-radius:8px; margin-bottom:10px;">'

            # Güvenli sahip çağırma (Eski eklenmiş sahipsiz evler hata vermesin diye)
            owner_username = house.get('owner', 'Bilinmiyor')
            owner_name = st.session_state.users.get(owner_username, {}).get('ad', 'Bilinmiyor')

            popup_content = f"""
            <div style="width:220px">
                {image_html}
                <h4>{house['title']}</h4>
                <p style="color:green; font-size:16px;"><b>Kira:</b> {house['price']} TL</p>
                <p><b>Açıklama:</b> {house['comment']}</p>
                <p><small><b>Ekleyen:</b> {owner_name}</small></p>
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

    # Haritayı ekrana bas (Tıklama verisini alabilmek için)
    map_data = st_folium(m, width="100%", height=500)


# -- SEKME 2: İLAN EKLEME (SADECE GİRİŞ YAPANLARA AÇIK) --
with tab_ekle:
    if not st.session_state.logged_in:
        st.warning("🔒 Yeni bir emlak ilanı ekleyebilmek için sol menüden sisteme üye olmalı veya giriş yapmalısınız.")
    else:
        st.markdown("### Yeni İlan Oluştur")
        st.info("İpucu: Harita üzerinden bir yere tıkladığınızda enlem ve boylam buraya otomatik gelir.")
        
        clicked_lat = 38.6748
        clicked_lon = 39.2225
        if map_data and map_data.get("last_clicked"):
            clicked_lat = map_data["last_clicked"]["lat"]
            clicked_lon = map_data["last_clicked"]["lng"]

        with st.form("add_house_form"):
            title = st.text_input("İlan Başlığı (Örn: Adliyeye 5dk yürüme mesafesinde)")
            price = st.number_input("Kira Ücreti (TL)", min_value=0, step=500)
            lat = st.number_input("Enlem", value=clicked_lat, format="%.6f")
            lon = st.number_input("Boylam", value=clicked_lon, format="%.6f")
            comment = st.text_area("Açıklama (Kurallara aykırı kelimeler filtrelenir)")
            uploaded_file = st.file_uploader("Ev Fotoğrafı Yükle", type=["png", "jpg", "jpeg"])
            
            submitted = st.form_submit_button("İlanı Haritaya Ekle")
            
            if submitted:
                if not icerik_uygun_mu(title) or not icerik_uygun_mu(comment):
                    st.error("❌ Hata: İlan başlığı veya açıklamasında sistem kurallarına aykırı kelimeler tespit edildi. Lütfen düzenleyip tekrar deneyin.")
                elif title and price > 0:
                    image_b64 = ""
                    if uploaded_file is not None:
                        image_b64 = base64.b64encode(uploaded_file.read()).decode()

                    new_house = {
                        "id": len(st.session_state.houses) + 1,
                        "title": title,
                        "price": price,
                        "lat": lat,
                        "lon": lon,
                        "comment": comment,
                        "image_b64": image_b64,
                        "owner": st.session_state.current_user 
                    }
                    st.session_state.houses.append(new_house)
                    st.success("✅ İlanınız başarıyla eklendi! Haritadan kontrol edebilirsiniz.")
                    st.rerun()
                else:
                    st.error("Lütfen başlık ve fiyat bilgilerini eksiksiz girin.")

# -- SEKME 3: YÖNETİM PANELİ (SADECE GİRİŞ YAPANLARA AÇIK) --
with tab_yonetim:
    if not st.session_state.logged_in:
        st.warning("🔒 İlanları yönetmek veya silmek için sol menüden sisteme giriş yapmalısınız.")
    else:
        st.markdown("### İlan Yönetimi")
        
        if len(st.session_state.houses) == 0:
            st.info("Sistemde henüz kayıtlı ilan bulunmuyor.")
        else:
            for idx, house in enumerate(st.session_state.houses):
                # Admin her şeyi görür, normal kullanıcı sadece kendi ilanını görür
                if st.session_state.user_role == "yonetici" or house.get("owner") == st.session_state.current_user:
                    owner_username = house.get('owner', 'Bilinmiyor')
                    owner_name = st.session_state.users.get(owner_username, {}).get('ad', 'Bilinmiyor')
                    
                    with st.expander(f"📌 {house['title']} - {house['price']} TL (Ekleyen: {owner_name})"):
                        st.write(f"**Açıklama:** {house['comment']}")
                        
                        # Resmi varsa yönetim panelinde de göster
                        if house.get('image_b64'):
                            st.markdown(f'<img src="data:image/jpeg;base64,{house.get("image_b64")}" width="150" style="border-radius:10px;">', unsafe_allow_html=True)
                        
                        if st.button(f"🗑️ Bu İlanı Sil", key=f"delete_{idx}"):
                            st.session_state.houses.pop(idx)
                            st.success("İlan başarıyla sistemden silindi!")
                            st.rerun()
