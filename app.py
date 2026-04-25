import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import math
import base64
from geopy.geocoders import Nominatim
from datetime import datetime
import json
import random
from google.oauth2 import service_account
from google.cloud import firestore
from PIL import Image
import io
import requests
from streamlit_geolocation import streamlit_geolocation
from streamlit_lottie import st_lottie

# --- 1. SAYFA AYARLARI VE MOBİL DESTEK (PWA) ---
st.set_page_config(page_title="Memur Emlak & Tayin Portalı", layout="wide", page_icon="🏢")

st.markdown('<link rel="manifest" href="/manifest.json">', unsafe_allow_html=True)
st.markdown('<meta name="apple-mobile-web-app-capable" content="yes">', unsafe_allow_html=True)

# --- SADECE ZORUNLU TEKNİK DÜZELTMELER (Tasarım Temizlendi) ---
st.markdown("""
    <style>
        /* Harita Çerçevesi Düzeltmesi */
        .main iframe { max-width: 100% !important; overflow: hidden !important; border-radius: 12px; }
        
        /* Sekme Tasarımı ve İmleç/Tıklama Düzeltmeleri */
        div[role="radiogroup"] { 
            flex-direction: row; 
            gap: 15px; 
            border-bottom: 2px solid #ddd; 
            padding-bottom: 10px; 
            outline: none !important; 
        }
        div[role="radiogroup"] label { 
            cursor: pointer !important; 
            caret-color: transparent !important; 
        }
        div[role="radiogroup"] * { outline: none !important; }
        
        /* GPS Butonu Devasa Boşluk Düzeltmesi */
        [data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(iframe) {
            height: 45px !important;
            min-height: 45px !important;
            max-height: 45px !important;
            margin-bottom: 0px !important;
            overflow: hidden !important;
        }
        [data-testid="stSidebar"] iframe {
            height: 45px !important;
            min-height: 45px !important;
            max-height: 45px !important;
        }
        
        /* Vurgulu Slogan Metni (Animasyon Altı) */
        .slogan-text {
            font-size: 24px !important;
            font-weight: 600;
            color: #2c3e50;
            text-align: center;
            margin-top: 10px;
            margin-bottom: 30px;
            font-style: italic;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. FIREBASE BAĞLANTISI ---
@st.cache_resource
def get_db():
    try:
        key_dict = json.loads(st.secrets["firebase_key"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
        return firestore.Client(credentials=creds)
    except Exception as e:
        st.error("Veritabanı bağlantı hatası. Secrets ayarlarını kontrol edin.")
        return None

db = get_db()

# --- 3. VERİ YÜKLEME VE ZİYARETÇİ SAYACI ---
def load_data():
    if db is None: return
    st.session_state.users = {doc.id: doc.to_dict() for doc in db.collection('users').stream()}
    
    if "misivi46" not in st.session_state.users:
        admin_data = {
            "sifre": "Elvinmelek46**", 
            "rol": "yonetici", 
            "ad": "Sinan",
            "email": "yonetici@sistem.com",
            "dogum_tarihi": "Belirtilmemiş",
            "meslek": "Mimar",
            "favorites": [],
            "tos_agreed": True,
            "tos_date": "Sistem Kurucusu"
        }
        db.collection('users').document("misivi46").set(admin_data)
        st.session_state.users["misivi46"] = admin_data

    st.session_state.houses = [doc.to_dict() for doc in db.collection('houses').stream()]
    st.session_state.messages = [doc.to_dict() for doc in db.collection('messages').stream()]

    # YENİ: Ziyaretçi Sayacı İşlemleri (Firebase üzerinden)
    stats_ref = db.collection('site_stats').document('visitors')
    stats_doc = stats_ref.get()
    
    if stats_doc.exists:
        current_count = stats_doc.to_dict().get('count', 0)
        new_count = current_count + 1
        stats_ref.update({'count': new_count})
        st.session_state.visitor_count = new_count
    else:
        stats_ref.set({'count': 1})
        st.session_state.visitor_count = 1

if 'data_loaded' not in st.session_state:
    st.session_state.users, st.session_state.houses, st.session_state.messages = {}, [], []
    st.session_state.visitor_count = 0
    load_data()
    st.session_state.data_loaded = True

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.session_state.user_role = None

# --- 4. YARDIMCI FONKSİYONLAR ---
YASAKLI_KELIMELER = ["aptal", "salak", "parti", "siyaset", "ırk", "defol", "lan"]

def icerik_uygun_mu(metin):
    return not any(kelime in metin.lower() for kelime in YASAKLI_KELIMELER)

def koordinati_adrese_cevir(lat, lon):
    try:
        loc = Nominatim(user_agent="memur_emlak_v30").reverse(f"{lat}, {lon}", timeout=3)
        return loc.address if loc else "Adres bulunamadı."
    except: return "Adres servisi meşgul."

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return round(R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a))), 2)

# YENİ: Lottie Animasyonu Yükleyici
def load_lottieurl(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

# --- 5. ŞEHİR BİLGİLERİ (PLAKA SIRALI) ---
PLAKA_SIRALI_ILLER = [
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya", "Ankara", "Antalya", "Artvin", "Aydın", "Balıkesir",
    "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum", "Denizli",
    "Diyarbakır", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir", "Gaziantep", "Giresun", "Gümüşhane", "Hakkari",
    "Hatay", "Isparta", "Mersin", "İstanbul", "İzmir", "Kars", "Kastamonu", "Kayseri", "Kırklareli", "Kırşehir",
    "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa", "Kahramanmaraş", "Mardin", "Muğla", "Muş", "Nevşehir",
    "Niğde", "Ordu", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas", "Tekirdağ", "Tokat",
    "Trabzon", "Tunceli", "Şanlıurfa", "Uşak", "Van", "Yozgat", "Zonguldak", "Aksaray", "Bayburt", "Karaman",
    "Kırıkkale", "Batman", "Şırnak", "Bartın", "Ardahan", "Iğdır", "Yalova", "Karabük", "Kilis", "Osmaniye", "Düzce"
]

TÜRKIYE_ILLERI_KOORDINATLAR = {
    "Adana": [37.0000, 35.3213], "Adıyaman": [37.7648, 38.2786], "Afyonkarahisar": [38.7507, 30.5567],
    "Ağrı": [39.7191, 43.0503], "Amasya": [40.6499, 35.8353], "Ankara": [39.9334, 32.8597],
    "Antalya": [36.8969, 30.7133], "Artvin": [41.1828, 41.8183], "Aydın": [37.8444, 27.8458],
    "Balıkesir": [39.6484, 27.8826], "Bilecik": [40.1451, 29.9798], "Bingöl": [38.8847, 40.4939],
    "Bitlis": [38.4006, 42.1095], "Bolu": [40.7392, 31.6111], "Burdur": [37.7204, 30.2805],
    "Bursa": [40.1824, 29.0665], "Çanakkale": [40.1553, 26.4127], "Çankırı": [40.6013, 33.6134],
    "Çorum": [40.5506, 34.9556], "Denizli": [37.7765, 29.0864], "Diyarbakır": [37.9144, 40.2306],
    "Edirne": [41.6771, 26.5557], "Elazığ": [38.6748, 39.2225], "Erzincan": [39.7500, 39.5000],
    "Erzurum": [39.9043, 41.2679], "Eskişehir": [39.7767, 30.5206], "Gaziantep": [37.0662, 37.3833],
    "Giresun": [40.9128, 38.3895], "Gümüşhane": [40.4608, 39.4816], "Hakkari": [37.5744, 43.7408],
    "Hatay": [36.2000, 36.1667], "Isparta": [37.7648, 30.5566], "Mersin": [36.8000, 34.6333],
    "İstanbul": [41.0082, 28.9784], "İzmir": [38.4192, 27.1287], "Kars": [40.6013, 43.0975],
    "Kastamonu": [41.3766, 33.7765], "Kayseri": [38.7312, 35.4787], "Kırklareli": [41.7333, 27.2167],
    "Kırşehir": [39.1425, 34.1709], "Kocaeli": [40.8533, 29.8815], "Konya": [37.8746, 32.4931],
    "Kütahya": [39.4167, 29.9833], "Malatya": [38.3552, 38.3095], "Manisa": [38.6191, 27.4289],
    "Kahramanmaraş": [37.5858, 36.9371], "Mardin": [37.3122, 40.7339], "Muğla": [37.2153, 28.3636],
    "Muş": [38.7366, 41.4938], "Nevşehir": [38.6244, 34.7144], "Niğde": [37.9667, 34.6833],
    "Ordu": [40.9839, 37.8764], "Rize": [41.0201, 40.5234], "Sakarya": [40.7569, 30.3783],
    "Samsun": [41.2867, 36.3300], "Siirt": [37.9333, 41.9500], "Sinop": [42.0231, 35.1531],
    "Sivas": [39.7477, 37.0179], "Tekirdağ": [40.9833, 27.5167], "Tokat": [40.3167, 36.5500],
    "Trabzon": [41.0015, 39.7178], "Tunceli": [39.1079, 39.5401], "Şanlıurfa": [37.1500, 38.8000],
    "Uşak": [38.6823, 29.4082], "Van": [38.4891, 43.3889], "Yozgat": [39.8181, 34.8147],
    "Zonguldak": [41.4564, 31.7762], "Aksaray": [38.3687, 34.0370], "Bayburt": [40.2552, 40.2249],
    "Karaman": [37.1759, 33.2287], "Kırıkkale": [39.8468, 33.5153], "Batman": [37.8812, 41.1351],
    "Şırnak": [37.5164, 42.4611], "Bartın": [41.6344, 32.3375], "Ardahan": [41.1105, 42.7022],
    "Iğdır": [39.9237, 44.0450], "Yalova": [40.6500, 29.2667], "Karabük": [41.2061, 32.6226],
    "Kilis": [36.7184, 37.1147], "Osmaniye": [37.0742, 36.2475], "Düzce": [40.8438, 31.1565]
}

CITIES = {}
for sehir in PLAKA_SIRALI_ILLER:
    coords = TÜRKIYE_ILLERI_KOORDINATLAR[sehir]
    CITIES[sehir] = {
        "center": coords,
        "institutions": [
            {"name": f"{sehir} Valiliği", "lat": coords[0] + 0.003, "lon": coords[1] + 0.003},
            {"name": f"{sehir} Adliyesi", "lat": coords[0] - 0.003, "lon": coords[1] - 0.003},
            {"name": f"İl Emniyet Müdürlüğü", "lat": coords[0] + 0.004, "lon": coords[1] - 0.002},
            {"name": f"{sehir} Devlet Hastanesi", "lat": coords[0] - 0.004, "lon": coords[1] + 0.002},
        ]
    }

CITIES["Elazığ"]["institutions"].extend([
    {"name": "Fethi Sekin Şehir Hastanesi", "lat": 38.6738, "lon": 39.1963},
    {"name": "Fırat Üniversitesi", "lat": 38.6756, "lon": 39.1970}
])
CITIES["Ankara"]["institutions"].append({"name": "ODTÜ", "lat": 39.8914, "lon": 32.7846})
CITIES["Konya"]["institutions"].append({"name": "Selçuk Üniversitesi", "lat": 38.0260, "lon": 32.5125})

TUM_KURUMLAR = [kurum for il_veri in CITIES.values() for kurum in il_veri["institutions"]]

# --- 6. SIDEBAR (AUTH, GPS & FİLTRE) ---
with st.sidebar:
    st.title("🏡 İşlemler")
    
    st.markdown("📍 **Mevcut Konumunuz**")
    user_location = streamlit_geolocation()
    
    sehir_secenekleri = ["Türkiye Geneli"] + PLAKA_SIRALI_ILLER
    
    if user_location and user_location.get('latitude') not in [None, 0.0] and user_location.get('longitude') not in [None, 0.0]:
        if "📍 Bulunduğum Konum" not in sehir_secenekleri:
            sehir_secenekleri.insert(1, "📍 Bulunduğum Konum")
        
        if st.session_state.get('last_gps_data') != user_location:
            st.session_state.last_gps_data = user_location
            st.session_state.secili_konum_state = "📍 Bulunduğum Konum"
            
    if "secili_konum_state" not in st.session_state:
        st.session_state.secili_konum_state = "Türkiye Geneli"
        
    mevcut_indeks = 0
    if st.session_state.secili_konum_state in sehir_secenekleri:
        mevcut_indeks = sehir_secenekleri.index(st.session_state.secili_konum_state)

    secilen_sehir = st.selectbox("🏙️ Konum Seçin:", sehir_secenekleri, index=mevcut_indeks)
    st.session_state.secili_konum_state = secilen_sehir

    if secilen_sehir == "Türkiye Geneli":
        aktif_merkez = [39.0, 35.0]
        harita_zoom = 6
        aktif_kurumlar = TUM_KURUMLAR
    elif secilen_sehir == "📍 Bulunduğum Konum":
        aktif_merkez = [user_location['latitude'], user_location['longitude']]
        harita_zoom = 16 
        aktif_kurumlar = [k for k in TUM_KURUMLAR if calculate_distance(aktif_merkez[0], aktif_merkez[1], k['lat'], k['lon']) <= 50]
    else:
        aktif_merkez = CITIES[secilen_sehir]["center"]
        harita_zoom = 12
        aktif_kurumlar = CITIES[secilen_sehir]["institutions"]

    max_fiyat, kurum_sec, max_mesafe = 50000, "Farketmez", 50.0
    oda_sec, esya_sec = "Farketmez", "Farketmez"

    if not st.session_state.logged_in:
        # Şifremi Unuttum Modu
        if st.session_state.get("forgot_password_mode", False):
            st.markdown("### 🔑 Şifremi Unuttum")
            
            if "reset_step" not in st.session_state:
                st.session_state.reset_step = 1
                
            if st.session_state.reset_step == 1:
                with st.form("forgot_f"):
                    f_u = st.text_input("Kullanıcı Adınız")
                    f_e = st.text_input("Kayıtlı E-Posta Adresiniz")
                    if st.form_submit_button("Doğrulama Kodu Gönder"):
                        if f_u in st.session_state.users and st.session_state.users[f_u].get("email") == f_e:
                            st.session_state.reset_code = str(random.randint(100000, 999999))
                            st.session_state.reset_user = f_u
                            st.session_state.reset_step = 2
                            st.rerun()
                        else:
                            st.error("Kullanıcı adı veya E-Posta adresi sistemde bulunamadı.")
                            
            elif st.session_state.reset_step == 2:
                st.info(f"📧 E-Posta adresinize bir doğrulama kodu gönderildi! \n\n*(Prototip Test Kodu: {st.session_state.reset_code})*")
                with st.form("reset_pass_f"):
                    entered_code = st.text_input("Doğrulama Kodunu Giriniz")
                    new_password = st.text_input("Yeni Şifreniz", type="password")
                    if st.form_submit_button("Şifreyi Yenile"):
                        if entered_code == st.session_state.reset_code:
                            db.collection('users').document(st.session_state.reset_user).update({
                                "sifre": new_password
                            })
                            st.success("Şifreniz başarıyla yenilendi! Şimdi giriş yapabilirsiniz.")
                            st.session_state.reset_step = 1 
                            st.session_state.forgot_password_mode = False
                            del st.session_state.reset_code
                            del st.session_state.reset_user
                            st.rerun()
                        else:
                            st.error("Hatalı doğrulama kodu!")
            
            st.markdown("---")
            if st.button("⬅️ Geri Dön"):
                st.session_state.forgot_password_mode = False
                st.session_state.reset_step = 1
                st.rerun()

        # Normal Giriş / Kayıt Modu
        else:
            auth = st.radio("Hesap İşlemleri:", ["Giriş Yap", "Üye Ol"], horizontal=True)
            
            if auth == "Giriş Yap":
                with st.form("l_f"):
                    u = st.text_input("Kullanıcı Adı")
                    p = st.text_input("Şifre", type="password")
                    if st.form_submit_button("Giriş Yap"):
                        load_data()
                        if u in st.session_state.users and st.session_state.users[u]["sifre"] == p:
                            st.session_state.logged_in = True
                            st.session_state.current_user = u
                            st.session_state.user_role = st.session_state.users[u]["rol"]
                            st.rerun()
                        else: st.error("Hatalı kullanıcı adı veya şifre!")
                
                if st.button("Şifremi Unuttum"):
                    st.session_state.forgot_password_mode = True
                    st.rerun()
            
            elif auth == "Üye Ol":
                with st.form("s_f"):
                    st.markdown("**Zorunlu Bilgiler**")
                    n_a = st.text_input("Ad Soyad")
                    n_u = st.text_input("Kullanıcı Adı")
                    n_e = st.text_input("E-Posta Adresi")
                    n_p = st.text_input("Şifre", type="password")
                    
                    st.markdown("**İsteğe Bağlı Bilgiler**")
                    c1, c2, c3 = st.columns(3)
                    n_gun = c1.selectbox("Gün", [""] + list(range(1, 32)))
                    n_ay = c2.selectbox("Ay", ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"])
                    n_yil = c3.selectbox("Yıl", [""] + list(range(1950, 2010)))
                    n_meslek = st.text_input("Meslek")
                    
                    st.markdown("---")
                    with st.expander("📄 Kullanıcı Sözleşmesi"):
                        st.write("""
                        **GENEL KULLANIM ŞARTLARI VE SORUMLULUK REDDİ**
                        1. Bu platform yalnızca tayinci memurlar arasında bilgi paylaşımı amacıyla kurulmuştur.
                        2. İlanların ve bilgilerin doğruluğu tamamen ilanı ekleyen kullanıcının sorumluluğundadır.
                        3. Yönetim, anlaşmazlıklardan veya oluşabilecek zararlardan sorumlu tutulamaz.
                        4. Türkiye Cumhuriyeti yasalarına uygun davranmayı, zararlı içerik paylaşmamayı peşinen kabul edersiniz.
                        5. Üyelik bilgileriniz (e-posta vb.) sistemde güvenle saklanır.
                        """)
                    tos_agreed = st.checkbox("Sözleşmeyi okudum ve kabul ediyorum.")
                    
                    if st.form_submit_button("Kayıt Ol"):
                        if n_a and n_u and n_p and n_e:
                            if not tos_agreed:
                                st.error("Kayıt olmak için Kullanıcı Sözleşmesini onaylamalısınız.")
                            elif n_u in st.session_state.users: 
                                st.error("Bu kullanıcı adı zaten alınmış.")
                            else:
                                dogum_t = f"{n_gun} {n_ay} {n_yil}".strip() if (n_gun and n_ay and n_yil) else "Belirtilmemiş"
                                u_data = {
                                    "sifre": n_p, 
                                    "rol": "kullanici", 
                                    "ad": n_a,
                                    "email": n_e,
                                    "dogum_tarihi": dogum_t,
                                    "meslek": n_meslek if n_meslek else "Belirtilmemiş",
                                    "favorites": [],
                                    "tos_agreed": True,
                                    "tos_date": datetime.now().strftime("%d.%m.%Y %H:%M")
                                }
                                db.collection('users').document(n_u).set(u_data)
                                st.success("Kayıt başarılı! Lütfen Giriş Yap sekmesinden sisteme girin.")
                        else:
                            st.error("Lütfen zorunlu alanların (Ad, Kullanıcı Adı, E-Posta, Şifre) tamamını doldurun.")
    else:
        st.success(f"Hoş geldin, {st.session_state.users[st.session_state.current_user]['ad']}")
        
        with st.expander("⚙️ Hesap İşlemleri"):
            if st.session_state.user_role == "yonetici":
                st.markdown("**Kullanıcı Şifresi Sıfırla**")
                target = st.selectbox("Üye Seç:", list(st.session_state.users.keys()))
                new_p_admin = st.text_input("Yeni Şifre Belirle", type="password", key="admin_pw_input")
                if st.button("Şifreyi Güncelle", key="admin_pw_btn"):
                    if new_p_admin:
                        st.session_state.users[target]["sifre"] = new_p_admin
                        db.collection('users').document(target).update({"sifre": new_p_admin})
                        st.success("Kullanıcının şifresi güncellendi.")
            else:
                st.markdown("**Şifre Değiştir**")
                old_p = st.text_input("Eski Şifre", type="password")
                new_p = st.text_input("Yeni Şifre", type="password")
                if st.button("Şifremi Kaydet"):
                    if old_p == st.session_state.users[st.session_state.current_user]["sifre"] and new_p:
                        st.session_state.users[st.session_state.current_user]["sifre"] = new_p
                        db.collection('users').document(st.session_state.current_user).update({"sifre": new_p})
                        st.success("Şifreniz başarıyla değiştirildi ve veritabanına işlendi.")
                    else:
                        st.error("Eski şifreniz hatalı veya yeni şifre alanı boş!")
                
                st.markdown("---")
                st.markdown("**❌ Hesabımı Sil**")
                st.warning("Dikkat: Hesabınızı sildiğinizde profiliniz, ilanlarınız ve sözleşme onaylarınız kalıcı olarak yok edilir.")
                del_confirm = st.checkbox("Ayrılmak istediğine emin misin?")
                
                if st.button("Üyelikten Ayrıl", type="primary"):
                    if del_confirm:
                        db.collection('users').document(st.session_state.current_user).delete()
                        st.session_state.logged_in = False
                        st.session_state.current_user = None
                        st.session_state.user_role = None
                        st.success("Hesabınız başarıyla silindi. Hoşça kalın!")
                        st.rerun()
                    else:
                        st.error("Lütfen ayrılmak istediğinizi onaylamak için kutucuğu işaretleyin.")

        with st.expander("🔍 Detaylı Filtrele"):
            max_fiyat = st.slider("Maks. Bütçe", 0, 50000, 50000, step=500)
            oda_sec = st.selectbox("Oda", ["Farketmez", "1+0", "1+1", "2+1", "3+1", "4+1 ve üzeri"])
            esya_sec = st.radio("Eşya", ["Farketmez", "Eşyalı", "Boş"], horizontal=True)
            
            if secilen_sehir not in ["Türkiye Geneli"]:
                kurum_sec = st.selectbox("Kuruma Yakınlık:", ["Farketmez"] + [i["name"] for i in aktif_kurumlar])
                if kurum_sec != "Farketmez": max_mesafe = st.slider("Mesafe (km)", 0.5, 30.0, 5.0)
            else:
                st.info("💡 Kurum filtresi için yukarıdan spesifik bir il seçin.")
                kurum_sec = "Farketmez"

        # YENİ: Ziyaretçi Sayacı Gösterimi (Sidebar'ın en altı)
        st.markdown("---")
        st.markdown(f"<p style='text-align:center; font-size:12px; color:gray;'>👁️ Toplam Ziyaretçi: <b>{st.session_state.visitor_count}</b></p>", unsafe_allow_html=True)

        if st.button("🚪 Çıkış Yap"):
            st.session_state.logged_in = False
            st.rerun()

# --- FİLTRELEME MANTIĞI ---
if secilen_sehir == "Türkiye Geneli":
    f_houses = st.session_state.houses
else:
    f_houses = [h for h in st.session_state.houses if calculate_distance(h["lat"], h["lon"], aktif_merkez[0], aktif_merkez[1]) <= 100]

f_houses = [h for h in f_houses if h["price"] <= max_fiyat]
if oda_sec != "Farketmez": f_houses = [h for h in f_houses if h.get("rooms", "Belirtilmemiş") == oda_sec]
if esya_sec != "Farketmez":
    esya_bool = True if esya_sec == "Eşyalı" else False
    f_houses = [h for h in f_houses if h.get("furnished", False) == esya_bool]
if kurum_sec != "Farketmez":
    inst = next(i for i in aktif_kurumlar if i["name"] == kurum_sec)
    f_houses = [h for h in f_houses if calculate_distance(h["lat"], h["lon"], inst["lat"], inst["lon"]) <= max_mesafe]

# --- 7. ANA PANEL VE SEKME YÖNETİMİ ---
tab_names = ["📍 Harita", "🏠 İlan Ekle", "📋 Tüm İlanlar", "⭐ Favoriler", "📩 Mesajlar", "ℹ️ Hakkında"]

if st.session_state.user_role == "yonetici": 
    tab_names.append("📊 Admin Paneli")

if "tab_index" not in st.session_state: 
    st.session_state.tab_index = 0
if st.session_state.tab_index >= len(tab_names): 
    st.session_state.tab_index = 0

aktif_sekme = st.radio("Menü", tab_names, index=st.session_state.tab_index, horizontal=True, label_visibility="collapsed")

# Sekme Geçiş Hızlandırıcısı
if tab_names.index(aktif_sekme) != st.session_state.tab_index:
    st.session_state.tab_index = tab_names.index(aktif_sekme)
    st.rerun()

if aktif_sekme == "📍 Harita":
    m = folium.Map(location=aktif_merkez, zoom_start=harita_zoom, tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google')
    
    for i in aktif_kurumlar: 
        folium.Marker([i["lat"], i["lon"]], popup=i["name"], icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)
    
    if secilen_sehir == "📍 Bulunduğum Konum":
        folium.Marker(aktif_merkez, popup="Sizin Konumunuz", icon=folium.Icon(color="cadetblue", icon="crosshairs", prefix="fa")).add_to(m)
    
    if st.session_state.logged_in:
        marker_cluster = MarkerCluster().add_to(m)
        for h in f_houses:
            yakindaki_kurumlar = sorted(TUM_KURUMLAR, key=lambda x: calculate_distance(h['lat'], h['lon'], x['lat'], x['lon']))[:5]
            dist_items = "".join([f"<li style='margin-bottom:2px;'><b>{i['name']}:</b> {calculate_distance(h['lat'], h['lon'], i['lat'], i['lon'])} km</li>" for i in yakindaki_kurumlar])
            
            img_b64 = h.get("image", "")
            img_tag = f'<img src="data:image/jpeg;base64,{img_b64}" style="width:100%; border-radius:8px; margin-bottom:8px;">' if img_b64 else ""
            nav_link = f"https://www.google.com/maps/dir/?api=1&destination={h['lat']},{h['lon']}"
            
            popup_html = f"""
            <div style='width:240px; font-family: sans-serif;'>
                {img_tag}
                <b style='font-size:14px;'>{h['title']}</b><br>
                <span style='color:#27ae60; font-size:16px; font-weight:bold;'>{h['price']} TL</span><br>
                <hr style='margin:8px 0;'>
                <a href="{nav_link}" target="_blank" style="display:block; text-align:center; background:#4285F4; color:white; text-decoration:none; padding:5px; border-radius:5px; font-size:12px; font-weight:bold;">📍 Yol Tarifi Al</a>
                <p style='font-size:11px; margin:8px 0 4px 0;'><b>En Yakın Kurumlar:</b></p>
                <div style='max-height: 90px; overflow-y: auto; border: 1px solid #ddd; border-radius: 4px; padding: 4px;'>
                    <ul style='margin:0; padding-left:15px; font-size:11px;'>{dist_items}</ul>
                </div>
            </div>"""
            folium.Marker([h["lat"], h["lon"]], popup=folium.Popup(popup_html, max_width=260), icon=folium.Icon(color="green", icon="home")).add_to(marker_cluster)
    else: st.info("İlanları görmek için giriş yapın.")
    
    m_res = st_folium(
        m, 
        center=aktif_merkez, 
        zoom=harita_zoom, 
        key="ana_harita", 
        use_container_width=True, 
        height=550, 
        returned_objects=["last_clicked"]
    )
    
    if m_res and m_res.get("last_clicked"):
        click_data = m_res["last_clicked"]
        if st.session_state.get("prev_click") != click_data:
            st.session_state.prev_click = click_data
            st.session_state.tab_index = tab_names.index("🏠 İlan Ekle")
            st.rerun()

    # --- YENİ: HARİTA ALTINDAKİ TAŞINMA ANİMASYONU VE SLOGAN ---
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Nakliye / Taşınma Kamyonu Animasyonu (LottieFiles)
        lottie_moving = load_lottieurl("https://assets10.lottiefiles.com/packages/lf20_t2bmt8yo.json")
        if lottie_moving:
            st_lottie(lottie_moving, height=200, key="moving_truck")
        
        st.markdown("<p class='slogan-text'>\"Tayininiz Çıktıysa Dert Etmeyin; Yeni Eviniz, Yeni Şehrinizde Sizi Bekliyor!\"<br><span style='font-size:16px; font-weight:400;'>Atama dönemlerinde kiralık ev bulmayı kolaylaştıran, taşınan ve ev arayan memurları güvenle buluşturan platform.</span></p>", unsafe_allow_html=True)

elif aktif_sekme == "🏠 İlan Ekle":
    if not st.session_state.logged_in: st.warning("Giriş yapınız.")
    else:
        l_n, o_n, a_n = aktif_merkez[0], aktif_merkez[1], ""
        if st.session_state.get("prev_click"):
            l_n, o_n = st.session_state.prev_click["lat"], st.session_state.prev_click["lng"]
            a_n = koordinati_adrese_cevir(l_n, o_n)
            st.success(f"📍 Haritadan Konum Seçildi: {a_n}")
            
        with st.form("add_f"):
            ti, pr = st.text_input("Başlık (*Zorunlu*)"), st.number_input("Kira (TL) (*Zorunlu*)", min_value=0, step=500)
            c1, c2 = st.columns(2)
            rm = c1.selectbox("Oda Sayısı", ["1+0", "1+1", "2+1", "3+1", "4+1 ve üzeri"])
            fr = c2.checkbox("Eşyalı")
            ad, co = st.text_area("Adres (*Zorunlu*)", value=a_n), st.text_area("Açıklama")
            fl = st.file_uploader("Fotoğraf Yükle", type=["jpg", "png"])
            if st.form_submit_button("İlanı Yayınla"):
                if not icerik_uygun_mu(ti) or not icerik_uygun_mu(co): st.error("Kurallara aykırı kelime!")
                elif not ti or not ad or pr <= 0: st.error("Zorunlu alanları doldurun.")
                else:
                    b64 = ""
                    if fl:
                        img = Image.open(fl).convert("RGB")
                        img.thumbnail((600, 600))
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG")
                        b64 = base64.b64encode(buf.getvalue()).decode()
                    h_id = str(int(datetime.now().timestamp()))
                    h_data = {"id": h_id, "title": ti, "price": pr, "rooms": rm, "furnished": fr, "address": ad, "comment": co, "lat": l_n, "lon": o_n, "image": b64, "owner": st.session_state.current_user}
                    db.collection('houses').document(h_id).set(h_data)
                    st.session_state.houses.append(h_data)
                    st.session_state.prev_click = None 
                    st.success("İlan kaydedildi!")
                    st.session_state.tab_index = tab_names.index("📋 Tüm İlanlar")
                    st.rerun()

elif aktif_sekme == "📋 Tüm İlanlar":
    if not st.session_state.logged_in: st.warning("Giriş yapın.")
    else:
        st.info(f"📍 Şu an **{secilen_sehir}** için sonuçlar listeleniyor.")
        for h in f_houses:
            esya_durumu = "Eşyalı" if h.get("furnished", False) else "Boş"
            oda_durumu = h.get("rooms", "Belirtilmemiş")
            with st.expander(f"🏠 {h['title']} - {h['price']} TL | {oda_durumu} - {esya_durumu}"):
                col1, col2 = st.columns([1, 2])
                if h.get("image"): col1.image(f"data:image/jpeg;base64,{h['image']}")
                col2.write(f"**Adres:** {h['address']}\n\n**Açıklama:** {h['comment']}")
                
                f_l = st.session_state.users[st.session_state.current_user].get("favorites", [])
                b1, b2, b3 = st.columns([1,1,2])
                with b1:
                    if st.button("❤️ Çıkar" if h["id"] in f_l else "🤍 Favorile", key=f"f_{h['id']}"):
                        if h["id"] in f_l: f_l.remove(h["id"])
                        else: f_l.append(h["id"])
                        db.collection('users').document(st.session_state.current_user).update({"favorites": f_l})
                        st.rerun()
                with b2:
                    if st.session_state.user_role == "yonetici" or h["owner"] == st.session_state.current_user:
                        if st.button("🗑️ Sil", key=f"s_{h['id']}"):
                            db.collection('houses').document(h["id"]).delete()
                            st.session_state.houses = [x for x in st.session_state.houses if x["id"] != h["id"]]
                            st.rerun()
                if h["owner"] != st.session_state.current_user:
                    st.markdown("---")
                    m_i = st.text_input("Mesajınız", key=f"m_{h['id']}")
                    if st.button("Gönder", key=f"b_{h['id']}"):
                        if m_i and icerik_uygun_mu(m_i):
                            msg = {"house": h["title"], "from": st.session_state.current_user, "to": h["owner"], "text": m_i, "date": datetime.now().strftime("%d.%m %H:%M")}
                            db.collection('messages').add(msg)
                            st.session_state.messages.append(msg)
                            st.success("İletildi.")

elif aktif_sekme == "⭐ Favoriler":
    if st.session_state.logged_in:
        f_l = st.session_state.users[st.session_state.current_user].get("favorites", [])
        for h in [x for x in st.session_state.houses if x["id"] in f_l]: 
            st.write(f"⭐ **{h['title']}** - {h['price']} TL (Adres: {h['address']})")

elif aktif_sekme == "📩 Mesajlar":
    if st.session_state.logged_in:
        my_m = [m for m in st.session_state.messages if m["from"] == st.session_state.current_user or m["to"] == st.session_state.current_user or st.session_state.user_role == "yonetici"]
        for m in my_m:
            with st.chat_message("user" if m["from"] == st.session_state.current_user else "assistant"):
                st.write(f"**{m['house']}** | {m['from']} ➔ {m['to']}\n{m['text']}")

elif aktif_sekme == "ℹ️ Hakkında":
    st.title("🏢 Memur Emlak & Tayin Portalı")
    st.markdown("---")
    st.markdown("""
    **Memurların atama ve tayin dönemlerinde kiralık ev bulmalarını kolaylaştırmak amacıyla tasarlanmıştır.** Yeni bir şehre taşınma süreci her zaman stresli bir süreçtir. Bu platform; tayini çıkan, yeni bir düzene adım atan ve güvenilir bir yuvaya ihtiyaç duyan memurlar ile, tayin sebebiyle evini devreden/kiralayan kişileri güvenli bir çatı altında buluşturur.

    ### ✨ Uygulamanın Başlıca Özellikleri:
    * **📍 Akıllı Harita Sistemi:** Evleri sadece bir liste olarak değil, doğrudan harita üzerinde konumlarıyla inceleyebilirsiniz.
    * **🏢 Kurumlara Yakınlık:** İlgilendiğiniz evin Valilik, Adliye, Hastane veya Emniyet Müdürlüğü gibi resmi kurumlara tam olarak kaç kilometre uzaklıkta olduğunu harita üzerinden otomatik hesaplar.
    * **💬 Güvenli İletişim:** İlan sahipleriyle sistem üzerinden doğrudan ve güvenle mesajlaşabilirsiniz.
    * **⭐ Favori İlanlar:** İlgilendiğiniz evleri favorilerinize ekleyerek daha sonra tek tıkla kolayca ulaşabilirsiniz.
    * **📍 GPS Destekli Arama:** "Bulunduğum Konum" özelliği ile etrafınızdaki müsait evleri ve kurumları anında harita üzerinde listeleyebilirsiniz.
    """)

elif aktif_sekme == "📊 Admin Paneli":
    if st.session_state.user_role == "yonetici":
        st.header("📊 Admin İstatistikleri")
        c1, c2, c3 = st.columns(3)
        c1.metric("Toplam Kullanıcı", len(st.session_state.users))
        c2.metric("Toplam İlan", len(st.session_state.houses))
        c3.metric("Toplam Mesaj", len(st.session_state.messages))
        
        st.markdown("---")
        st.subheader("👥 Detaylı Kullanıcı Veritabanı")
        
        for u_id, u_info in st.session_state.users.items():
            if u_info.get("rol") != "yonetici":
                with st.expander(f"👤 {u_info.get('ad')} (@{u_id})"):
                    st.write(f"**E-Posta:** {u_info.get('email', 'Belirtilmemiş')}")
                    st.write(f"**Doğum Tarihi:** {u_info.get('dogum_tarihi', 'Belirtilmemiş')}")
                    st.write(f"**Meslek:** {u_info.get('meslek', 'Belirtilmemiş')}")
                    
                    onay = "✅ Onaylı" if u_info.get("tos_agreed") else "❌ Onaylanmadı"
                    st.write(f"**Sözleşme Durumu:** {onay} ({u_info.get('tos_date', 'Tarih Yok')})")
