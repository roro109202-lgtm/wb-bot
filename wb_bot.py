import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# ==========================================
# 1. НАСТРОЙКИ (NATIVE DARK MODE SUPPORT)
# ==========================================
st.set_page_config(page_title="WB AI System v25", layout="wide", page_icon="🛍️")

# Минимальный CSS, чтобы не ломать темную тему, а дополнять её
st.markdown("""
    <style>
    .block-container {padding-top: 1.5rem;}
    .stTextArea textarea {font-size: 16px !important;}
    
    /* Убираем лишние отступы у кнопок */
    div[data-testid="column"] {gap: 0.5rem;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. ФУНКЦИИ
# ==========================================

def format_date(iso_date):
    if not iso_date: return ""
    try:
        dt = datetime.datetime.fromisoformat(str(iso_date).replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return str(iso_date)

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
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions/answer"
            payload = {"id": review_id, "answer": {"text": text}, "state": "wbViewed"}
        
        res = requests.patch(url, headers=headers, json=payload, timeout=15)
        if res.status_code in [200, 204]: return "OK"
        return f"Ошибка {res.status_code}"
    except Exception as e:
        return f"Ошибка сети"

def generate_ai(api_key, text, item_name, user_name, instructions, signature):
    if not api_key: return "Нет ключа Groq"
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    safe_user = user_name if user_name else "Покупатель"
    greeting = f"Здравствуйте, {safe_user}!" if len(safe_user) > 2 and safe_user.lower() != "клиент" else "Здравствуйте!"
    user_msg = text if text else "Оценка без текста."

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

# Безопасное получение фото
def get_photo_url(review_item):
    try:
        if not review_item.get('photoLinks'): return None
        # Пробуем по очереди разные размеры
        photo = review_item['photoLinks'][0]
        return photo.get('smallSize') or photo.get('fullSize') or photo.get('miniSize')
    except:
        return None

# ==========================================
# 3. ИНИЦИАЛИЗАЦИЯ И МАГАЗИНЫ
# ==========================================

if 'shops' not in st.session_state:
    st.session_state['shops'] = {}
    if hasattr(st, 'secrets') and 'WB_API_TOKEN' in st.secrets:
        st.session_state['shops']['Основной'] = st.secrets['WB_API_TOKEN']

if 'feedbacks' not in st.session_state: st.session_state['feedbacks'] = []
if 'questions' not in st.session_state: st.session_state['questions'] = []

# Ключ Groq
default_groq = ""
if hasattr(st, 'secrets'):
    default_groq = st.secrets.get('GROQ_API_KEY', "")

# ==========================================
# 4. САЙДБАР
# ==========================================

with st.sidebar:
    st.title("🎛️ Управление")
    
    # Выбор магазина
    shop_names = list(st.session_state['shops'].keys())
    if not shop_names:
        st.warning("Добавьте магазин!")
        current_wb_token = ""
        selected_shop = ""
    else:
        selected_shop = st.selectbox("Магазин:", shop_names)
        current_wb_token = st.session_state['shops'][selected_shop]

    with st.expander("➕ Добавить магазин"):
        new_name = st.text_input("Название")
        new_token = st.text_input("WB Token", type="password")
        if st.button("Добавить"):
            if new_name and new_token:
                st.session_state['shops'][new_name] = new_token
                st.rerun()
    
    if selected_shop and st.button("🗑️ Удалить магазин"):
        del st.session_state['shops'][selected_shop]
        st.rerun()

    st.divider()
    
    groq_key = st.text_input("Groq Key", value=default_groq, type="password")
    
    # Фильтры
    st.caption("Фильтры:")
    stars_filter = st.multiselect("Звезды", [1, 2, 3, 4, 5], default=[1, 2, 3, 4, 5])
    content_filter = st.radio("Содержание", ["Все", "С текстом", "Без текста"])
    
    st.divider()
    
    # Авто-режим
    auto_rev = st.toggle("Авто-Отзывы")
    auto_quest = st.toggle("Авто-Вопросы")
    
    with st.expander("Настройки ответов"):
        prompt_rev = st.text_area("Отзывы:", value="Благодари за покупку.", height=70)
        prompt_quest = st.text_area("Вопросы:", value="Отвечай коротко.", height=70)
        signature = st.text_input("Подпись:", value="С уважением, представитель бренда")

if not current_wb_token or not groq_key:
    st.info("Настройте ключи слева.")
    st.stop()

# ==========================================
# 5. ГЛАВНЫЙ ЭКРАН
# ==========================================

st.title(f"Магазин: {selected_shop}")

if st.button("🔄 Обновить данные", type="primary", use_container_width=True):
    with st.spinner("Загрузка..."):
        st.session_state['feedbacks'] = get_wb_data(current_wb_token, "feedbacks")
        st.session_state['questions'] = get_wb_data(current_wb_token, "questions")

tab1, tab2 = st.tabs(["⭐ Отзывы", "❓ Вопросы"])

# --- ОТЗЫВЫ ---
with tab1:
    raw_reviews = st.session_state.get('feedbacks', [])
    
    # Фильтрация
    filtered = []
    for r in raw_reviews:
        if r['productValuation'] not in stars_filter: continue
        has_text = bool(r.get('text'))
        if content_filter == "С текстом" and not has_text: continue
        if content_filter == "Без текста" and has_text: continue
        filtered.append(r)
    
    if not filtered:
        st.info("Нет отзывов.")
    else:
        st.caption(f"Показано: {len(filtered)}")
        for rev in filtered:
            try:
                # Используем нативный контейнер для идеальной темы
                with st.container(border=True):
                    # Верхняя часть
                    col_img, col_info = st.columns([1, 5])
                    
                    with col_img:
                        img_url = get_photo_url(rev)
                        if img_url:
                            st.image(img_url, use_container_width=True)
                        else:
                            st.markdown("🖼️") # Иконка если нет фото
                    
                    with col_info:
                        # Заголовок
                        prod = rev.get('productDetails', {}).get('productName', 'Товар')
                        brand = rev.get('productDetails', {}).get('brandName', '')
                        rating = rev.get('productValuation', 5)
                        date = format_date(rev.get('createdDate'))
                        user = rev.get('userName', 'Покупатель')
                        
                        st.markdown(f"**{prod}**")
                        st.caption(f"{brand} | {date}")
                        st.write(f"{'⭐'*rating} | **{user}**")
                        
                        # Текст отзыва
                        review_text = rev.get('text', '')
                        if review_text:
                            st.info(review_text)
                        else:
                            # Пустой отзыв - просто ничего не показываем или маленькую пометку
                            st.caption("*(Оценка без текста)*")
                        
                        # Зона ответа
                        c_gen, c_send = st.columns([1, 4])
                        key = f"r_{rev['id']}"
                        
                        if c_gen.button("✨ Ответ", key=f"btn_{key}"):
                            ans = generate_ai(groq_key, review_text, prod, user, prompt_rev, signature)
                            st.session_state[key] = ans
                            st.rerun()
                        
                        # Поле ввода ответа
                        resp = st.text_area("Ваш ответ:", value=st.session_state.get(key, ""), key=f"area_{key}", height=100)
                        
                        if st.button("Отправить", key=f"snd_{key}"):
                            res = send_wb(rev['id'], resp, current_wb_token, "feedbacks")
                            if res == "OK":
                                st.success("Отправлено!")
                                st.session_state['feedbacks'].remove(rev)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(res)
            except Exception as e:
                st.error(f"Ошибка отображения: {e}")

# --- ВОПРОСЫ ---
with tab2:
    quests = st.session_state.get('questions', [])
    if not quests:
        st.info("Нет вопросов.")
    else:
        for q in quests:
            try:
                with st.container(border=True):
                    prod = q.get('productDetails', {}).get('productName', 'Товар')
                    text = q.get('text', '')
                    date = format_date(q.get('createdDate'))
                    
                    st.markdown(f"❓ **{prod}**")
                    st.caption(date)
                    st.info(text)
                    
                    qk = f"q_{q['id']}"
                    if st.button("✨ Ответ", key=f"btn_{qk}"):
                        ans = generate_ai(groq_key, text, prod, "Покупатель", prompt_quest, signature)
                        st.session_state[qk] = ans
                        st.rerun()
                        
                    resp = st.text_area("Ваш ответ:", value=st.session_state.get(qk, ""), key=f"area_{qk}")
                    
                    if st.button("Отправить", key=f"snd_{qk}"):
                        res = send_wb(q['id'], resp, current_wb_token, "questions")
                        if res == "OK":
                            st.success("Отправлено!")
                            st.session_state['questions'].remove(q)
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(res)
            except: pass

# --- АВТО-РЕЖИМ ---
if (auto_rev or auto_quest) and (st.session_state.get('feedbacks') or st.session_state.get('questions')):
    st.toast("⚡ Авто-режим активен")
    
    # Авто Отзывы
    if auto_rev:
        for r in st.session_state['feedbacks'][:]:
            # Фильтры
            if r['productValuation'] not in stars_filter: continue
            has_t = bool(r.get('text'))
            if content_filter == "С текстом" and not has_t: continue
            if content_filter == "Без текста" and has_t: continue
            
            prod = r.get('productDetails', {}).get('productName', '')
            ans = generate_ai(groq_key, r.get('text',''), prod, r.get('userName',''), prompt_rev, signature)
            
            if "Ошибка" not in ans:
                if send_wb(r['id'], ans, current_wb_token, "feedbacks") == "OK":
                    st.session_state['feedbacks'].remove(r)
                    st.toast(f"Авто-отзыв: {prod}")
                    time.sleep(2)
                    st.rerun()

    # Авто Вопросы
    if auto_quest:
        for q in st.session_state['questions'][:]:
            prod = q.get('productDetails', {}).get('productName', '')
            ans = generate_ai(groq_key, q.get('text',''), prod, "Покупатель", prompt_quest, signature)
            
            if "Ошибка" not in ans:
                if send_wb(q['id'], ans, current_wb_token, "questions") == "OK":
                    st.session_state['questions'].remove(q)
                    st.toast(f"Авто-вопрос: {prod}")
                    time.sleep(2)
                    st.rerun()
