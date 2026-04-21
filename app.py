import streamlit as st
import folium
from streamlit_folium import st_folium
import math
import base64
from geopy.geocoders import Nominatim # YENİ: Koordinatları adrese çeviren kütüphane
from geopy.exc import GeocoderTimedOut

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

# --- KOORDİNATI ADRESE ÇEVİRME FONKSİYONU ---
def koordinati_adrese_cevir(lat, lon):
    try:
        # Nominatim, OpenStreetMap'in ücretsiz adres servisidir.
        geolocator = Nominatim(user_agent="memur_emlak_app")
        location = geolocator.reverse(f"{lat}, {lon}", timeout=3)
        if location:
            return location.address
        return "Bu konum için tam adres bulunamadı."
    except GeocoderTimedOut:
        return "Adres servisine ulaşılamadı (Zaman Aşımı)."
    except Exception as e:
        return "Adres alınırken bir hata oluştu."

# --- 2. VERİ VE KULLANICI ALTYAPISI ---
institutions = [
    {"name": "Valilik", "lat": 38.6810, "lon": 39.2264},
    {"name": "Eğitim ve Araştırma Hastanesi", "lat": 38.6738, "lon": 39.1963},
    {"name": "Adliye", "lat": 38.6705, "lon": 39.2215}
]

if 'houses' not in st.session_state:
    st.session_state.houses = []
    
if 'users' not in st.session_state:
    st.session_state.users = {
        "misivi46": {"sifre": "Elvinmelek46**", "rol": "yonetici", "ad": "Sinan"}
    }

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


# --- 3. YAN MENÜ (KAYIT / GİRİŞ / PROFİL) ---
with st.sidebar:
    st.title("🔑 Kullanıcı İşlemleri")
    
    if not st.session_state.logged_in:
        if st.button("🌐 Google Hesabı ile Devam Et", use_container_width=True):
            st.info("💡 Bilgi: Gerçek Google entegrasyonu için uygulama canlıya alındığında API bağlantısı yapılacaktır.")
            
        st.markdown("<div style='text-align: center; color: gray; margin: 10px 0;'>— Veya —</div>", unsafe_allow_html=True)
        secim = st.radio("Ne yapmak istersiniz?", ["Giriş Yap", "Üye Ol"], label_visibility="collapsed")
        
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
                        st.error("Bu kullanıcı adı zaten kullanılıyor.")
                    else:
                        st.session_state.users[yeni_kullanici] = {"sifre": yeni_sifre, "rol": "kullanici", "ad": yeni_ad}
                        st.success("Hesabınız başarıyla oluşturuldu! 'Giriş Yap' sekmesinden girebilirsiniz.")

    else:
        st.success(f"Hoş geldin, {st.session_state.users[st.session_state.current_user]['ad']}")
        st.write(f"🛡️ **Yetki:** {st.session_state.user_role.upper()}")
        
        with st.expander("⚙️ Profil Ayarları (Şifre İşlemleri)"):
            if st.session_state.user_role == "yonetici":
                st.markdown("**Kullanıcı Şifresi Sıfırlama (Admin)**")
                hedef_kullanici = st.selectbox("İşlem Yapılacak Kullanıcı:", list(st.session_state.users.keys()))
                yeni_sifre_admin = st.text_input("Yeni Şifre Belirle", type="password", key="admin_pw")
                
                if st.button("Şifreyi Güncelle", key="btn_admin_pw"):
                    if len(yeni_sifre_admin) > 0:
                        st.session_state.users[hedef_kullanici]["sifre"] = yeni_sifre_admin
                        st.success(f"✅ {hedef_kullanici} şifresi değiştirildi!")
                    else:
                        st.error("Lütfen geçerli bir şifre girin.")
            else:
                st.markdown("**Kendi Şifreni Değiştir**")
                eski_sifre = st.text_input("Mevcut Şifreniz", type="password")
                yeni_sifre = st.text_input("Yeni Şifre", type="password")
                
                if st.button("Şifremi Güncelle"):
                    if eski_sifre == st.session_state.users[st.session_state.current_user]["sifre"]:
                        if len(yeni_sifre) > 0:
                            st.session_state.users[st.session_state.current_user]["sifre"] = yeni_sifre
                            st.success("✅ Şifreniz güncellendi!")
                        else:
                            st.error("Yeni şifre alanı boş bırakılamaz.")
                    else:
                        st.error("❌ Mevcut şifrenizi hatalı girdiniz.")
        
        st.markdown("---")
        if st.button("🚪 Çıkış Yap"):
            st.session_state.logged_in = False
            st.session_state.current_user = None
            st.session_state.user_role = None
            st.rerun()


# --- 4. ANA EKRAN (HARİTA VE SEKMELER) ---
st.title("🗺️ Memur Tayin & Emlak Uygulaması")

tab_harita, tab_ekle, tab_yonetim = st.tabs(["📍 Harita (Herkese Açık)", "🏠 Yeni İlan Ekle (Sadece Üyeler)", "⚙️ İlan Yönetimi (Sadece Üyeler)"])

# -- SEKME 1: HARİTA --
with tab_harita:
    if not st.session_state.logged_in:
        st.info("👋 İlanları görmek ve ev eklemek için lütfen giriş yapın veya üye olun.")

    m = folium.Map(location=[38.6748, 39.2225], zoom_start=13, tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google Hybrid')

    for inst in institutions:
        folium.Marker(
            [inst["lat"], inst["lon"]],
            popup=f"<b>🏢 {inst['name']}</b>",
            tooltip=inst["name"],
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)

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

            owner_username = house.get('owner', 'Bilinmiyor')
            owner_name = st.session_state.users.get(owner_username, {}).get('ad', 'Bilinmiyor')
            adres_metni = house.get('address', 'Adres girilmemiş')

            popup_content = f"""
            <div style="width:220px">
                {image_html}
                <h4>{house['title']}</h4>
                <p style="color:green; font-size:16px;"><b>Kira:</b> {house['price']} TL</p>
                <p><b>Adres:</b> <small>{adres_metni}</small></p>
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

    map_data = st_folium(m, width="100%", height=500)


# -- SEKME 2: İLAN EKLEME (ENLEM BOYLAM YERİNE ADRES EKLENDİ) --
with tab_ekle:
    if not st.session_state.logged_in:
        st.warning("🔒 Yeni bir emlak ilanı ekleyebilmek için giriş yapmalısınız.")
    else:
        st.markdown("### Yeni İlan Oluştur")
        st.info("İpucu: Harita üzerinden bir yere tıkladığınızda o noktanın açık adresi otomatik olarak aşağıya gelecektir.")
        
        # Varsayılan başlangıç noktası (Elazığ Merkez)
        clicked_lat = 38.6748
        clicked_lon = 39.2225
        otomatik_adres = ""

        # Haritaya tıklandığında koordinatları al ve adrese çevir
        if map_data and map_data.get("last_clicked"):
            clicked_lat = map_data["last_clicked"]["lat"]
            clicked_lon = map_data["last_clicked"]["lng"]
            # Koordinatları adrese dönüştürüyoruz
            otomatik_adres = koordinati_adrese_cevir(clicked_lat, clicked_lon)
            st.success(f"📍 Tıklanan Konum: {otomatik_adres}")

        with st.form("add_house_form"):
            title = st.text_input("İlan Başlığı (Örn: Adliyeye 5dk mesafede)")
            price = st.number_input("Kira Ücreti (TL)", min_value=0, step=500)
            
            # Enlem ve boylam girişleri KALDIRILDI. Yerine Adres eklendi.
            # Adres kutusu otomatik dolar ama eksik bina no varsa kullanıcı elle tamamlayabilir.
            adres = st.text_area("Açık Adres (Haritadan otomatik alınır, eksikse düzenleyebilirsiniz)", value=otomatik_adres)
            
            comment = st.text_area("Açıklama (Kurallara aykırı kelimeler filtrelenir)")
            uploaded_file = st.file_uploader("Ev Fotoğrafı Yükle", type=["png", "jpg", "jpeg"])
            
            submitted = st.form_submit_button("İlanı Haritaya Ekle")
            
            if submitted:
                if not icerik_uygun_mu(title) or not icerik_uygun_mu(comment):
                    st.error("❌ Hata: İlan başlığı veya açıklamasında sistem kurallarına aykırı kelimeler tespit edildi.")
                elif not adres:
                    st.error("Lütfen haritadan bir konum seçin veya adres alanını doldurun.")
                elif title and price > 0:
                    image_b64 = ""
                    if uploaded_file is not None:
                        image_b64 = base64.b64encode(uploaded_file.read()).decode()

                    new_house = {
                        "id": len(st.session_state.houses) + 1,
                        "title": title,
                        "price": price,
                        "lat": clicked_lat, # Koordinatları arka planda hesaplama için hala tutuyoruz
                        "lon": clicked_lon,
                        "address": adres,   # Yeni eklenen adres verisi
                        "comment": comment,
                        "image_b64": image_b64,
                        "owner": st.session_state.current_user 
                    }
                    st.session_state.houses.append(new_house)
                    st.success("✅ İlanınız başarıyla eklendi! Haritadan kontrol edebilirsiniz.")
                    st.rerun()
                else:
                    st.error("Lütfen başlık ve fiyat bilgilerini eksiksiz girin.")

# -- SEKME 3: YÖNETİM PANELİ --
with tab_yonetim:
    if not st.session_state.logged_in:
        st.warning("🔒 İlanları yönetmek veya silmek için giriş yapmalısınız.")
    else:
        st.markdown("### İlan Yönetimi")
        
        if len(st.session_state.houses) == 0:
            st.info("Sistemde henüz kayıtlı ilan bulunmuyor.")
        else:
            for idx, house in enumerate(st.session_state.houses):
                if st.session_state.user_role == "yonetici" or house.get("owner") == st.session_state.current_user:
                    owner_username = house.get('owner', 'Bilinmiyor')
                    owner_name = st.session_state.users.get(owner_username, {}).get('ad', 'Bilinmiyor')
                    
                    with st.expander(f"📌 {house['title']} - {house['price']} TL (Ekleyen: {owner_name})"):
                        st.write(f"**Açık Adres:** {house.get('address', 'Belirtilmemiş')}")
                        st.write(f"**Açıklama:** {house['comment']}")
                        
                        if house.get('image_b64'):
                            st.markdown(f'<img src="data:image/jpeg;base64,{house.get("image_b64")}" width="150" style="border-radius:10px;">', unsafe_allow_html=True)
                        
                        if st.button(f"🗑️ Bu İlanı Sil", key=f"delete_{idx}"):
                            st.session_state.houses.pop(idx)
                            st.success("İlan başarıyla sistemden silindi!")
                            st.rerun()
