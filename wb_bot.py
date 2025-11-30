import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# ==========================================
# 1. НАСТРОЙКИ И PRO-ДИЗАЙН
# ==========================================
st.set_page_config(page_title="WB AI Pro v23", layout="wide", page_icon="🛍️")

# CSS стили для копирования дизайна со скриншота
st.markdown("""
    <style>
    .block-container {padding-top: 1rem; background-color: #f4f6f8;}
    
    /* Карточка отзыва */
    .review-card {
        background-color: white;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border: 1px solid #e1e4e8;
    }
    
    /* Заголовок товара */
    .product-title {
        font-size: 18px;
        font-weight: 600;
        color: #333;
        margin-bottom: 5px;
    }
    
    /* Артикул и бренд */
    .product-meta {
        font-size: 13px;
        color: #777;
        margin-bottom: 10px;
    }
    
    /* Звезды */
    .stars {
        color: #7c4dff; /* Фиолетовый как на скрине */
        font-size: 20px;
        letter-spacing: 2px;
    }
    
    /* Имя и дата */
    .user-meta {
        font-size: 14px;
        color: #999;
        margin-left: 10px;
    }
    
    /* Текст отзыва */
    .review-text {
        margin-top: 15px;
        font-size: 15px;
        line-height: 1.5;
        color: #222;
    }
    
    /* Кнопки */
    .stButton button {
        border-radius: 8px;
    }
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

# ==========================================
# 3. ИНИЦИАЛИЗАЦИЯ И НАСТРОЙКИ (КАК НА СКРИНЕ)
# ==========================================

if 'feedbacks' not in st.session_state: st.session_state['feedbacks'] = []
if 'questions' not in st.session_state: st.session_state['questions'] = []

# Ключи
default_wb = ""
default_groq = ""
if hasattr(st, 'secrets'):
    default_wb = st.secrets.get('WB_API_TOKEN', "")
    default_groq = st.secrets.get('GROQ_API_KEY', "")

with st.sidebar:
    st.header("⚙️ Настройки и фильтры")
    
    with st.expander("🔑 Доступы", expanded=True):
        wb_token = st.text_input("WB Token", value=default_wb, type="password")
        groq_key = st.text_input("Groq Key", value=default_groq, type="password")

    st.subheader("Фильтры отзывов")
    st.caption("На какие отзывы отвечать (вручную и авто):")
    
    # ФИЛЬТР ЗВЕЗД (Как на скрине)
    col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
    s1 = col_s1.checkbox("1", value=True)
    s2 = col_s2.checkbox("2", value=True)
    s3 = col_s3.checkbox("3", value=True)
    s4 = col_s4.checkbox("4", value=True)
    s5 = col_s5.checkbox("5", value=True)
    
    allowed_stars = []
    if s1: allowed_stars.append(1)
    if s2: allowed_stars.append(2)
    if s3: allowed_stars.append(3)
    if s4: allowed_stars.append(4)
    if s5: allowed_stars.append(5)
    
    # ФИЛЬТР ТЕКСТА
    filter_content = st.radio("Текст отзыва:", ["Не важно", "Только с текстом", "Только без текста"])
    
    st.divider()
    st.subheader("🤖 Автоответы")
    auto_reviews = st.toggle("Включить авто-отзывы")
    auto_questions = st.toggle("Включить авто-вопросы")
    
    with st.expander("Текст ответа (Промпт)"):
        prompt_rev = st.text_area("Для отзывов:", value="Благодари за покупку.", height=70)
        signature = st.text_input("Подпись:", value="С уважением, команда бренда")

if not wb_token or not groq_key:
    st.warning("Введите ключи.")
    st.stop()

# ==========================================
# 4. ГЛАВНЫЙ ЭКРАН (PRO DESIGN)
# ==========================================

st.title("Ответы на отзывы")

if st.button("🔄 Обновить список", type="primary"):
    with st.spinner("Загрузка..."):
        st.session_state['feedbacks'] = get_wb_data(wb_token, "feedbacks")
        st.session_state['questions'] = get_wb_data(wb_token, "questions")

tab_rev, tab_quest = st.tabs([f"⭐ Отзывы", f"❓ Вопросы"])

# --- ОТЗЫВЫ (ДИЗАЙН КАК НА СКРИНЕ) ---
with tab_rev:
    all_reviews = st.session_state.get('feedbacks', [])
    
    # ПРИМЕНЕНИЕ ФИЛЬТРОВ
    filtered_reviews = []
    for r in all_reviews:
        # Фильтр звезд
        if r['productValuation'] not in allowed_stars:
            continue
        # Фильтр текста
        has_text = bool(r.get('text'))
        if filter_content == "Только с текстом" and not has_text:
            continue
        if filter_content == "Только без текста" and has_text:
            continue
        filtered_reviews.append(r)
        
    if not filtered_reviews:
        st.info("Нет отзывов, подходящих под фильтры.")
    else:
        st.write(f"Показано: {len(filtered_reviews)} шт.")
        
        for rev in filtered_reviews:
            # ДАННЫЕ
            details = rev.get('productDetails', {})
            prod_name = details.get('productName', 'Товар')
            brand = details.get('brandName', '')
            nm_id = details.get('nmId', '')
            rating = rev.get('productValuation', 5)
            date_str = format_date(rev.get('createdDate'))
            user = rev.get('userName', 'Покупатель')
            text = rev.get('text', '')
            
            # --- ВИЗУАЛЬНАЯ КАРТОЧКА (HTML/CSS) ---
            with st.container():
                cols = st.columns([1, 5])
                
                # ЛЕВАЯ КОЛОНКА - ФОТО
                with cols[0]:
                    img_url = "https://static.wbstatic.net/i/blank/1.jpg" # Заглушка
                    if rev.get('photoLinks'):
                        img_url = rev['photoLinks'][0]['smallSize']
                    st.image(img_url, use_container_width=True)
                
                # ПРАВАЯ КОЛОНКА - КОНТЕНТ
                with cols[1]:
                    # Заголовок и звезды
                    stars_html = "★" * rating + "<span style='color:#ddd'>" + "★" * (5 - rating) + "</span>"
                    
                    st.markdown(f"""
                    <div style="margin-bottom: 5px;">
                        <span class="product-title">{prod_name}</span>
                    </div>
                    <div class="product-meta">
                        Бренд: {brand} | Арт: {nm_id}
                    </div>
                    <div>
                        <span class="stars">{stars_html}</span>
                        <span class="user-meta">{date_str} &nbsp; {user}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Текст отзыва
                    if text:
                        st.markdown(f"<div class='review-text'><b>Комментарий:</b><br>{text}</div>", unsafe_allow_html=True)
                    else:
                        st.caption("Без текста")
                    
                    st.markdown("---")
                    
                    # БЛОК ОТВЕТА
                    c1, c2 = st.columns([1, 4])
                    key = f"r_{rev['id']}"
                    
                    if c1.button("✨ Сгенерировать ответ", key=f"btn_{key}"):
                        ans = generate_ai(groq_key, text, prod_name, user, prompt_rev, signature)
                        st.session_state[key] = ans
                        st.rerun()
                        
                    response_text = st.text_area("Текст ответа:", value=st.session_state.get(key, ""), height=100, key=f"area_{key}", label_visibility="collapsed", placeholder="Здесь появится ответ...")
                    
                    if st.button("Отправить", key=f"snd_{key}"):
                        res = send_wb(rev['id'], response_text, wb_token, "feedbacks")
                        if res == "OK":
                            st.success("Ответ отправлен!")
                            st.session_state['feedbacks'].remove(rev)
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(res)
            
            st.markdown("<br>", unsafe_allow_html=True) # Отступ между карточками

# === ВОПРОСЫ (УПРОЩЕННО, НО В ТОМ ЖЕ СТИЛЕ) ===
with tab_quest:
    quests = st.session_state.get('questions', [])
    if not quests:
        st.info("Нет вопросов.")
    else:
        for q in quests:
            with st.container():
                cols = st.columns([1, 5])
                prod = q.get('productDetails', {}).get('productName', '')
                
                with cols[1]:
                    st.markdown(f"**{prod}**")
                    st.write(f"❓ {q.get('text', '')}")
                    
                    qk = f"q_{q['id']}"
                    if st.button("✨ Ответ", key=f"qb_{qk}"):
                        ans = generate_ai(groq_key, q.get('text',''), prod, "Покупатель", "Ответь на вопрос", signature)
                        st.session_state[qk] = ans
                        st.rerun()
                        
                    q_txt = st.text_area("Ответ:", value=st.session_state.get(qk, ""), key=f"qt_{qk}")
                    
                    if st.button("Отправить", key=f"qs_{qk}"):
                        res = send_wb(q['id'], q_txt, wb_token, "questions")
                        if res == "OK":
                            st.success("Ушло!")
                            st.session_state['questions'].remove(q)
                            time.sleep(1)
                            st.rerun()

# --- ЛОГИКА АВТО-РЕЖИМА С УЧЕТОМ ФИЛЬТРОВ ---
if auto_reviews and st.session_state.get('feedbacks'):
    st.toast("⚡ Авто-режим: Обработка...")
    count_ok = 0
    
    for rev in st.session_state['feedbacks'][:]: # Копия списка
        # 1. Проверка фильтров
        if rev['productValuation'] not in allowed_stars: continue
        has_text = bool(rev.get('text'))
        if filter_content == "Только с текстом" and not has_text: continue
        if filter_content == "Только без текста" and has_text: continue
        
        # 2. Генерация и отправка
        prod = rev['productDetails']['productName']
        ans = generate_ai(groq_key, rev.get('text',''), prod, rev.get('userName',''), prompt_rev, signature)
        
        if "Ошибка" not in ans:
            if send_wb(rev['id'], ans, wb_token, "feedbacks") == "OK":
                st.session_state['feedbacks'].remove(rev)
                count_ok += 1
                time.sleep(2)
    
    if count_ok > 0:
        st.success(f"Автоматически отвечено на {count_ok} отзывов!")
        time.sleep(2)
        st.rerun()
