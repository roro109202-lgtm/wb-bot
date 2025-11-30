import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# ==========================================
# 1. НАСТРОЙКИ И WB-STYLE DESIGN
# ==========================================
st.set_page_config(page_title="WB AI Master v28", layout="wide", page_icon="🟣")

st.markdown("""
    <style>
    /* Основной фон и отступы */
    .block-container {padding-top: 1.5rem; background-color: #f6f6f9;}
    
    /* Стили кнопок (WB Purple) */
    .stButton > button {
        background-color: #cb11ab !important;
        color: white !important;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        transition: 0.3s;
    }
    .stButton > button:hover {
        background-color: #a80e8f !important;
        opacity: 0.9;
    }
    
    /* Карточки */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        background-color: white;
        border-radius: 16px;
        border: 1px solid #e6e6e6;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        padding: 20px;
    }
    
    /* Текстовые поля */
    .stTextArea textarea {
        font-size: 16px !important;
        border-radius: 10px;
        border: 1px solid #ddd;
    }
    
    /* Акценты в тексте */
    .wb-pros { color: #007a33; font-weight: 500; margin-bottom: 2px; }
    .wb-cons { color: #d92424; font-weight: 500; margin-bottom: 2px; }
    .wb-comment { color: #222; margin-top: 8px; line-height: 1.5; }
    .wb-header { font-size: 18px; font-weight: 700; color: #222; }
    .wb-meta { font-size: 13px; color: #999; }
    
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. ФУНКЦИИ
# ==========================================

def format_date(iso_date):
    if not iso_date: return ""
    try:
        dt = datetime.datetime.fromisoformat(str(iso_date).replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y в %H:%M")
    except:
        return str(iso_date)

# Генератор фото по артикулу (Работает и для вопросов, и для отзывов)
def get_main_photo_url(nm_id):
    try:
        vol = int(nm_id) // 100000
        part = int(nm_id) // 1000
        basket = "01"
        if 0 <= vol <= 143: basket = "01"
        elif 144 <= vol <= 287: basket = "02"
        elif 288 <= vol <= 431: basket = "03"
        elif 432 <= vol <= 719: basket = "04"
        elif 720 <= vol <= 1007: basket = "05"
        elif 1008 <= vol <= 1061: basket = "06"
        elif 1062 <= vol <= 1115: basket = "07"
        elif 1116 <= vol <= 1169: basket = "08"
        elif 1170 <= vol <= 1313: basket = "09"
        elif 1314 <= vol <= 1601: basket = "10"
        elif 1602 <= vol <= 1655: basket = "11"
        elif 1656 <= vol <= 1919: basket = "12"
        elif 1920 <= vol <= 2045: basket = "13"
        elif 2046 <= vol <= 2189: basket = "14"
        else: basket = "15"
        
        return f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/images/c246x328/1.jpg"
    except:
        return "https://static.wbstatic.net/i/blank/1.jpg" # Заглушка

def get_wb_data(wb_token, mode="feedbacks"):
    if not wb_token or len(wb_token) < 10: return []
    headers = {"Authorization": wb_token}
    params = {"isAnswered": "false", "take": 50, "skip": 0, "order": "dateDesc"}
    
    try:
        url = f"https://feedbacks-api.wildberries.ru/api/v1/{mode}"
        res = requests.get(url, headers=headers, params=params, timeout=15)
        if res.status_code == 200:
            json_data = res.json()
            if 'data' in json_data and mode in json_data['data']:
                return json_data['data'][mode]
        return []
    except:
        return []

def send_wb(review_id, text, wb_token, mode="feedbacks"):
    headers = {"Authorization": wb_token, "Content-Type": "application/json"}
    if not text or len(text) < 2: return "Текст пустой"
    
    try:
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
            payload = {"id": review_id, "text": text}
        else: 
            # Исправленная логика для вопросов
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions/answer"
            payload = {"id": review_id, "answer": {"text": text}, "state": "wbViewed"}
        
        res = requests.patch(url, headers=headers, json=payload, timeout=15)
        if res.status_code in [200, 204]: return "OK"
        return f"Ошибка WB {res.status_code}"
    except Exception as e:
        return f"Ошибка сети"

def generate_ai(api_key, text, item_name, user_name, instructions, signature):
    if not api_key: return "Нет ключа Groq"
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    safe_user = user_name if user_name else "Покупатель"
    greeting = f"Здравствуйте, {safe_user}!" if len(safe_user) > 2 and safe_user.lower() != "клиент" else "Здравствуйте!"
    user_msg = text if text else "Без текста."

    prompt = f"""
    Роль: Менеджер Wildberries.
    Товар: {item_name}
    Клиент пишет: "{user_msg}"
    Инструкция: {instructions}
    
    Формат ответа:
    1. {greeting}
    2. (Пустая строка)
    3. Ответ.
    4. (Пустая строка)
    5. {signature}
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка AI: {e}"

def log_event(message, type="info"):
    timestamp = datetime.datetime.now().strftime("%H:%M")
    icon = "✅" if type == "success" else "❌" if type == "error" else "ℹ️"
    entry = f"{timestamp} {icon} {message}"
    if 'action_log' in st.session_state:
        st.session_state['action_log'].insert(0, entry)

# ==========================================
# 3. ИНИЦИАЛИЗАЦИЯ И МАГАЗИНЫ
# ==========================================

if 'feedbacks' not in st.session_state: st.session_state['feedbacks'] = []
if 'questions' not in st.session_state: st.session_state['questions'] = []
if 'action_log' not in st.session_state: st.session_state['action_log'] = []
if 'history' not in st.session_state: st.session_state['history'] = []

# --- ЗАГРУЗКА МАГАЗИНОВ ---
if 'shops' not in st.session_state:
    st.session_state['shops'] = {}
    
    # Загрузка из Secrets (Вечное хранение)
    if hasattr(st, 'secrets') and 'shops' in st.secrets:
        for name, token in st.secrets['shops'].items():
            st.session_state['shops'][name] = token
    # Совместимость со старым форматом
    elif hasattr(st, 'secrets') and 'WB_API_TOKEN' in st.secrets:
        st.session_state['shops']['Основной'] = st.secrets['WB_API_TOKEN']

# Ключ Groq
default_groq = ""
if hasattr(st, 'secrets'):
    default_groq = st.secrets.get('GROQ_API_KEY', "")

# ==========================================
# 4. САЙДБАР (МЕНЕДЖЕР МАГАЗИНОВ)
# ==========================================

with st.sidebar:
    st.title("🎛️ Управление")
    
    # Выбор магазина
    shop_list = list(st.session_state['shops'].keys())
    
    if not shop_list:
        st.warning("Нет магазинов")
        current_wb_token = ""
        selected_shop = ""
        # Ввод первого магазина
        new_sh_name = st.text_input("Имя магазина")
        new_sh_token = st.text_input("Токен WB", type="password")
        if st.button("Сохранить"):
            st.session_state['shops'][new_sh_name] = new_sh_token
            st.rerun()
    else:
        selected_shop = st.selectbox("🏬 Выберите магазин:", shop_list)
        current_wb_token = st.session_state['shops'][selected_shop]
        
        # Кнопка добавления еще одного
        with st.expander("➕ Добавить еще магазин"):
            add_name = st.text_input("Название")
            add_token = st.text_input("API Токен", type="password")
            if st.button("Добавить в список"):
                if add_name and add_token:
                    st.session_state['shops'][add_name] = add_token
                    st.success("Магазин добавлен!")
                    time.sleep(1)
                    st.rerun()
        
        if st.button("🗑️ Удалить текущий"):
            del st.session_state['shops'][selected_shop]
            st.rerun()

    st.divider()
    groq_key = st.text_input("🔑 Groq Key", value=default_groq, type="password")
    
    with st.expander("📝 Инструкции нейросети"):
        prompt_rev = st.text_area("Для отзывов:", value="Благодари за покупку.", height=70)
        prompt_quest = st.text_area("Для вопросов:", value="Отвечай коротко и по делу.", height=70)
        signature = st.text_input("Подпись:", value="С уважением, команда бренда")
    
    st.divider()
    col1, col2 = st.columns(2)
    auto_reviews = col1.toggle("Авто Отзывы")
    auto_questions = col2.toggle("Авто Вопросы")
    
    st.markdown("---")
    if st.button("🔄 Сброс кэша"):
        st.session_state.clear()
        st.rerun()

if not current_wb_token or not groq_key:
    st.info("Введите ключи для работы.")
    st.stop()

# ==========================================
# 5. ГЛАВНЫЙ ЭКРАН
# ==========================================

st.markdown(f"## 🟣 {selected_shop}")

if st.button("⚡ СКАНИРОВАТЬ МАГАЗИН", type="primary", use_container_width=True):
    with st.spinner("Получаю данные с Wildberries..."):
        st.session_state['feedbacks'] = get_wb_data(current_wb_token, "feedbacks")
        st.session_state['questions'] = get_wb_data(current_wb_token, "questions")
        log_event(f"Обновление: {selected_shop}")

# Метрики
c1, c2, c3 = st.columns(3)
count_rev = len(st.session_state.get('feedbacks', []))
count_quest = len(st.session_state.get('questions', []))
c1.metric("Отзывов", count_rev)
c2.metric("Вопросов", count_quest)
c3.metric("Журнал", len(st.session_state['action_log']))

st.write("") # Отступ

tab_rev, tab_quest, tab_log, tab_arch = st.tabs([
    f"⭐ Отзывы ({count_rev})", 
    f"❓ Вопросы ({count_quest})", 
    "📜 Журнал",
    "🗄️ Архив"
])

# --- ОТЗЫВЫ ---
with tab_rev:
    reviews = st.session_state.get('feedbacks', [])
    if not reviews:
        st.info("Нет новых отзывов.")
    else:
        for rev in reviews:
            try:
                # Данные
                prod = rev.get('productDetails', {})
                prod_name = prod.get('productName', 'Товар')
                nm_id = prod.get('nmId', 0)
                brand = prod.get('brandName', '')
                rating = rev.get('productValuation', 5)
                user = rev.get('userName', 'Покупатель')
                
                # Текст
                pros = rev.get('pros', '')
                cons = rev.get('cons', '')
                comment = rev.get('text', '')
                
                full_text_ai = f"Плюсы: {pros}. Минусы: {cons}. Текст: {comment}"
                
                with st.container(border=True):
                    cols = st.columns([1, 4])
                    
                    # ФОТО
                    with cols[0]:
                        main_photo = get_main_photo_url(nm_id)
                        st.image(main_photo, use_container_width=True)
                    
                    # КОНТЕНТ
                    with cols[1]:
                        st.markdown(f"<div class='wb-header'>{prod_name}</div>", unsafe_allow_html=True)
                        st.caption(f"Арт: {nm_id} | {brand}")
                        
                        # Звезды
                        stars = "★" * rating
                        st.markdown(f"<span style='color:#7c4dff; font-size:18px;'>{stars}</span> &nbsp; **{user}** &nbsp; <span style='color:#999; font-size:12px;'>{format_date(rev.get('createdDate'))}</span>", unsafe_allow_html=True)
                        
                        st.markdown("---")
                        
                        # Контент отзыва
                        has_content = False
                        if pros:
                            st.markdown(f"<div class='wb-pros'>👍 Достоинства:</div>{pros}", unsafe_allow_html=True)
                            has_content = True
                        if cons:
                            st.markdown(f"<div class='wb-cons'>👎 Недостатки:</div>{cons}", unsafe_allow_html=True)
                            has_content = True
                        if comment:
                            st.markdown(f"<div class='wb-comment'>{comment}</div>", unsafe_allow_html=True)
                            has_content = True
                        
                        if not has_content:
                            st.caption("*(Оценка без текста)*")
                            
                        # ФОТО ПОКУПАТЕЛЯ
                        if rev.get('photoLinks'):
                            p_cols = st.columns(6)
                            for i, p in enumerate(rev['photoLinks'][:6]):
                                p_url = p.get('smallSize') or p.get('fullSize')
                                if p_url: p_cols[i].image(p_url)

                        st.markdown("---")
                        
                        # ГЕНЕРАЦИЯ
                        key = f"r_{rev['id']}"
                        c_gen, c_space = st.columns([1, 3])
                        
                        if c_gen.button("✨ Сгенерировать ответ", key=f"btn_{key}"):
                            text_for_ai = full_text_ai if has_content else "Оценка без текста"
                            ans = generate_ai(groq_key, text_for_ai, prod_name, user, prompt_rev, signature)
                            st.session_state[key] = ans
                            st.rerun()
                        
                        # ПОЛЕ ВВОДА
                        response_text = st.text_area("Ваш ответ:", value=st.session_state.get(key, ""), height=120, key=f"area_{key}")
                        
                        if st.button("🚀 Отправить", key=f"snd_{key}"):
                            res = send_wb(rev['id'], response_text, current_wb_token, "feedbacks")
                            if res == "OK":
                                st.success("Успешно!")
                                st.session_state['feedbacks'].remove(rev)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(res)
            except: pass

# === ВОПРОСЫ ===
with tab_quest:
    quests = st.session_state.get('questions', [])
    if not quests:
        st.info("Нет вопросов.")
    else:
        for q in quests:
            try:
                prod = q.get('productDetails', {})
                prod_name = prod.get('productName', 'Товар')
                nm_id = prod.get('nmId', 0)
                text = q.get('text', '')
                
                with st.container(border=True):
                    cols = st.columns([1, 4])
                    
                    with cols[0]:
                        main_photo = get_main_photo_url(nm_id)
                        st.image(main_photo, use_container_width=True)
                        
                    with cols[1]:
                        st.markdown(f"<div class='wb-header'>{prod_name}</div>", unsafe_allow_html=True)
                        st.caption(f"Арт: {nm_id} | {format_date(q.get('createdDate'))}")
                        
                        st.info(f"❓ {text}")
                        
                        # ГЕНЕРАЦИЯ
                        qk = f"q_{q['id']}"
                        if st.button("✨ Сгенерировать ответ", key=f"qbtn_{qk}"):
                            ans = generate_ai(groq_key, text, prod_name, "Покупатель", prompt_quest, signature)
                            st.session_state[qk] = ans
                            st.rerun()
                            
                        q_resp = st.text_area("Ваш ответ:", value=st.session_state.get(qk, ""), height=120, key=f"qarea_{qk}")
                        
                        if st.button("🚀 Отправить", key=f"qsnd_{qk}"):
                            res = send_wb(q['id'], q_resp, current_wb_token, "questions")
                            if res == "OK":
                                st.success("Успешно!")
                                st.session_state['questions'].remove(q)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(res)
            except: pass

# === ЛОГИ ===
with tab_log:
    for log in st.session_state['action_log']:
        st.write(log)

# === АРХИВ ===
with tab_arch:
    if st.button("📥 Загрузить историю"):
        st.session_state['history'] = get_wb_data(current_wb_token, "feedbacks", True)
    for item in st.session_state.get('history', []):
        try:
            with st.expander(f"{item['productDetails']['productName']} ({format_date(item.get('createdDate'))})"):
                st.write(item.get('text', ''))
                if item.get('answer'): st.info(item['answer']['text'])
        except: pass

# === АВТО-РЕЖИМ ===
if (auto_reviews or auto_questions) and (st.session_state.get('feedbacks') or st.session_state.get('questions')):
    st.toast(f"⚡ Авто-режим: {selected_shop}")
    
    if auto_reviews:
        for r in st.session_state['feedbacks'][:]:
            prod = r.get('productDetails', {}).get('productName', '')
            pros = r.get('pros', '')
            cons = r.get('cons', '')
            comm = r.get('text', '')
            full = f"Плюсы: {pros}. Минусы: {cons}. Текст: {comm}"
            if not full.strip(): full = "Оценка без текста"
            
            ans = generate_ai(groq_key, full, prod, r.get('userName',''), prompt_rev, signature)
            if "Ошибка" not in ans:
                if send_wb(r['id'], ans, current_wb_token, "feedbacks") == "OK":
                    st.session_state['feedbacks'].remove(r)
                    st.toast(f"Ответ: {prod}")
                    time.sleep(2)
                    st.rerun()

    if auto_questions:
        for q in st.session_state['questions'][:]:
            prod = q.get('productDetails', {}).get('productName', '')
            ans = generate_ai(groq_key, q.get('text',''), prod, "Покупатель", prompt_quest, signature)
            if "Ошибка" not in ans:
                if send_wb(q['id'], ans, current_wb_token, "questions") == "OK":
                    st.session_state['questions'].remove(q)
                    st.toast(f"Ответ: {prod}")
                    time.sleep(2)
                    st.rerun()
