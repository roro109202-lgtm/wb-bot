import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# ==========================================
# 1. НАСТРОЙКИ
# ==========================================
st.set_page_config(page_title="WB AI Master v39", layout="wide", page_icon="🛍️")

st.markdown("""
    <style>
    .block-container {padding-top: 1.5rem;}
    .stTextArea textarea {font-size: 16px !important;}
    .wb-pros {color: #4CAF50; font-weight: 500;}
    .wb-cons {color: #FF5252; font-weight: 500;}
    
    /* Подсветка активного меню */
    div[data-testid="stRadio"] > div {
        background-color: rgba(255, 255, 255, 0.05);
        padding: 10px;
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
        elif 2190 <= vol <= 2405: basket = "15"
        else: basket = "16"
        return f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/images/c246x328/1.webp"
    except:
        return None

def get_wb_data(wb_token, mode="feedbacks"):
    if not wb_token: return []
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

def send_wb(review_id, text, wb_token, mode="feedbacks", question_method="wbViewed"):
    headers = {"Authorization": wb_token, "Content-Type": "application/json"}
    if not text or len(text) < 2: return "Текст пустой"
    
    try:
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
            payload = {"id": review_id, "text": text}
        else:
            # ЛОГИКА ОТПРАВКИ ВОПРОСОВ (ВЫБОР МЕТОДА)
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions" # Правильный URL
            
            if question_method == "wbViewed":
                payload = {"id": review_id, "answer": {"text": text}, "state": "wbViewed"}
            elif question_method == "none":
                payload = {"id": review_id, "answer": {"text": text}, "state": "none"}
            else: # Без поля state
                payload = {"id": review_id, "answer": {"text": text}}
        
        res = requests.patch(url, headers=headers, json=payload, timeout=15)
        
        if res.status_code in [200, 204]: return "OK"
        return f"Ошибка WB {res.status_code}: {res.text}"
    except Exception as e:
        return f"Ошибка сети: {e}"

def generate_ai(api_key, text, item_name, user_name, instructions, signature):
    if not api_key: return "Нет ключа Groq"
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    safe_user = user_name if user_name else "Покупатель"
    greeting = f"Здравствуйте, {safe_user}!" if len(safe_user) > 2 and safe_user.lower() != "клиент" else "Здравствуйте!"
    user_msg = text if text else "Без текста."

    prompt = f"""
    Ты менеджер Wildberries.
    ТОВАР: {item_name}
    СООБЩЕНИЕ: "{user_msg}"
    ИНСТРУКЦИЯ: "{instructions}"
    
    ПРАВИЛА:
    1. НЕ используй нумерацию.
    2. Начни с: "{greeting}"
    3. Разделяй абзацы пустой строкой.
    4. В конце: "{signature}"
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant", # Самая быстрая
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
# 3. ИНИЦИАЛИЗАЦИЯ
# ==========================================

if 'feedbacks' not in st.session_state: st.session_state['feedbacks'] = []
if 'questions' not in st.session_state: st.session_state['questions'] = []
if 'action_log' not in st.session_state: st.session_state['action_log'] = []
if 'history' not in st.session_state: st.session_state['history'] = []
if 'nav_selection' not in st.session_state: st.session_state['nav_selection'] = "⭐ Отзывы" # Для памяти меню

# Загрузка магазинов
if 'shops' not in st.session_state:
    st.session_state['shops'] = {}
    if hasattr(st, 'secrets') and 'shops' in st.secrets:
        for name, token in st.secrets['shops'].items():
            st.session_state['shops'][name] = token
    elif hasattr(st, 'secrets') and 'WB_API_TOKEN' in st.secrets:
        st.session_state['shops']['Основной'] = st.secrets['WB_API_TOKEN']

default_groq = ""
if hasattr(st, 'secrets'):
    default_groq = st.secrets.get('GROQ_API_KEY', "")

# ==========================================
# 4. САЙДБАР
# ==========================================

with st.sidebar:
    st.title("🎛️ Меню")
    
    # НАВИГАЦИЯ С ПАМЯТЬЮ
    # Используем callback, чтобы сохранять состояние
    def update_nav():
        st.session_state['nav_selection'] = st.session_state._nav
        
    nav_page = st.radio(
        "Раздел:", 
        ["⭐ Отзывы", "❓ Вопросы", "📜 Журнал", "🗄️ Архив"],
        key="_nav",
        on_change=update_nav,
        index=["⭐ Отзывы", "❓ Вопросы", "📜 Журнал", "🗄️ Архив"].index(st.session_state['nav_selection'])
    )
    
    st.divider()
    
    shop_list = list(st.session_state['shops'].keys())
    if not shop_list:
        st.warning("Нет магазинов")
        selected_shop = ""
        current_wb_token = ""
        new_sh = st.text_input("Имя")
        new_tk = st.text_input("Токен", type="password")
        if st.button("Сохранить"):
            st.session_state['shops'][new_sh] = new_tk
            st.rerun()
    else:
        # Сохраняем выбор магазина
        if 'selected_shop_index' not in st.session_state: st.session_state['selected_shop_index'] = 0
        selected_shop = st.selectbox("Магазин:", shop_list, index=st.session_state['selected_shop_index'], key='shop_selector')
        st.session_state['selected_shop_index'] = shop_list.index(selected_shop)
        current_wb_token = st.session_state['shops'][selected_shop]
        
        with st.expander("Добавить магазин"):
            add_n = st.text_input("Название")
            add_t = st.text_input("Токен", type="password")
            if st.button("ОК"):
                st.session_state['shops'][add_n] = add_t
                st.rerun()
        if st.button("Удалить магазин"):
            del st.session_state['shops'][selected_shop]
            st.rerun()

    st.divider()
    groq_key = st.text_input("Groq Key", value=default_groq, type="password")
    
    with st.expander("Настройки ИИ"):
        prompt_rev = st.text_area("Отзывы:", value="Благодари за покупку.", height=70)
        prompt_quest = st.text_area("Вопросы:", value="Отвечай коротко.", height=70)
        signature = st.text_input("Подпись:", value="С уважением, представитель бренда")
    
    # ВЫБОР МЕТОДА ДЛЯ ВОПРОСОВ (РЕШЕНИЕ ОШИБКИ 400)
    with st.expander("⚙️ Настройки отправки"):
        q_method = st.selectbox(
            "Тип отправки вопросов:", 
            ["wbViewed", "none", "Без статуса"],
            help="Если ошибка 400 'Unknown state', попробуйте другой вариант."
        )
        # Преобразуем выбор в код
        if q_method == "Без статуса": q_method_code = "null"
        else: q_method_code = q_method

    st.divider()
    col1, col2 = st.columns(2)
    auto_reviews = col1.toggle("Авто Отзывы")
    auto_questions = col2.toggle("Авто Вопросы")
    
    st.markdown("---")
    if st.button("Сброс кэша"):
        st.session_state.clear()
        st.rerun()

if not current_wb_token or not groq_key:
    st.info("Нужны ключи.")
    st.stop()

# ==========================================
# 5. ГЛАВНЫЙ ЭКРАН
# ==========================================

st.title(f"🛍️ {selected_shop}")

if st.button("🔄 Сканировать магазин", type="primary", use_container_width=True):
    with st.spinner("Загрузка..."):
        st.session_state['feedbacks'] = get_wb_data(current_wb_token, "feedbacks")
        st.session_state['questions'] = get_wb_data(current_wb_token, "questions")
        log_event(f"Обновление: {selected_shop}")

c1, c2, c3 = st.columns(3)
count_rev = len(st.session_state.get('feedbacks', []))
count_quest = len(st.session_state.get('questions', []))
c1.metric("Отзывы", count_rev)
c2.metric("Вопросы", count_quest)
c3.metric("Логи", len(st.session_state['action_log']))

st.write("")

# --- ОТЗЫВЫ ---
if st.session_state['nav_selection'] == "⭐ Отзывы":
    reviews = st.session_state.get('feedbacks', [])
    if not reviews:
        st.info("Нет отзывов.")
    else:
        for rev in reviews:
            try:
                prod_name = rev.get('productDetails', {}).get('productName', 'Товар')
                nm_id = rev.get('productDetails', {}).get('nmId', 0)
                brand = rev.get('productDetails', {}).get('brandName', '')
                rating = rev.get('productValuation', 5)
                user = rev.get('userName', 'Покупатель')
                
                pros = rev.get('pros', '')
                cons = rev.get('cons', '')
                comment = rev.get('text', '')
                full_text_ai = f"Плюсы: {pros}. Минусы: {cons}. Текст: {comment}"
                if not (pros or cons or comment): full_text_ai = ""
                
                with st.container(border=True):
                    cols = st.columns([1, 4])
                    
                    with cols[0]:
                        main_photo = get_main_photo_url(nm_id)
                        if main_photo: st.image(main_photo, use_container_width=True)
                        else: st.write("📦")
                    
                    with cols[1]:
                        st.markdown(f"**{prod_name}**")
                        st.caption(f"Арт: {nm_id} | {brand}")
                        st.write(f"{'⭐'*rating} | **{user}** | {format_date(rev.get('createdDate'))}")
                        st.markdown("---")
                        
                        if pros: st.markdown(f":green[**Достоинства:**] {pros}")
                        if cons: st.markdown(f":red[**Недостатки:**] {cons}")
                        if comment: st.markdown(f"**Комментарий:** {comment}")
                        if not (pros or cons or comment): st.caption("*(Оценка без текста)*")
                            
                        if rev.get('photoLinks'):
                            st.write("**Фото от клиента:**")
                            p_cols = st.columns(6)
                            for i, p in enumerate(rev['photoLinks'][:6]):
                                p_url = p.get('smallSize') or p.get('fullSize')
                                if p_url: p_cols[i].image(p_url)

                        st.markdown("---")
                        
                        key = f"r_{rev['id']}"
                        # Кнопка генерации
                        if st.button("✨ Сгенерировать ответ", key=f"btn_{key}"):
                            with st.spinner("Генерирую..."):
                                ans = generate_ai(groq_key, full_text_ai, prod_name, user, prompt_rev, signature)
                                st.session_state[key] = ans # Сохраняем в сессию по уникальному ключу
                                st.rerun() # Обновляем экран
                        
                        # Поле ввода берет значение из сессии
                        response_text = st.text_area("Ваш ответ:", value=st.session_state.get(key, ""), height=100, key=f"area_{key}")
                        
                        if st.button("Отправить", key=f"snd_{key}"):
                            res = send_wb(rev['id'], response_text, current_wb_token, "feedbacks")
                            if res == "OK":
                                st.success("Отправлено!")
                                st.session_state['feedbacks'].remove(rev)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(res)
            except: pass

# --- ВОПРОСЫ ---
elif st.session_state['nav_selection'] == "❓ Вопросы":
    quests = st.session_state.get('questions', [])
    if not quests:
        st.info("Нет вопросов.")
    else:
        for q in quests:
            try:
                prod_name = q.get('productDetails', {}).get('productName', 'Товар')
                nm_id = q.get('productDetails', {}).get('nmId', 0)
                text = q.get('text', '')
                
                with st.container(border=True):
                    cols = st.columns([1, 4])
                    
                    with cols[0]:
                        main_photo = get_main_photo_url(nm_id)
                        if main_photo: st.image(main_photo, use_container_width=True)
                        else: st.write("❓")
                    
                    with cols[1]:
                        st.markdown(f"**{prod_name}**")
                        st.caption(f"Арт: {nm_id}")
                        st.info(f"❓ {text}")
                        st.caption(format_date(q.get('createdDate')))
                        
                        qk = f"q_{q['id']}"
                        if st.button("✨ Сгенерировать ответ", key=f"qbtn_{qk}"):
                            with st.spinner("Генерирую..."):
                                ans = generate_ai(groq_key, text, prod_name, "Покупатель", prompt_quest, signature)
                                st.session_state[qk] = ans
                                st.rerun() # МГНОВЕННОЕ ОБНОВЛЕНИЕ
                            
                        q_resp = st.text_area("Ваш ответ:", value=st.session_state.get(qk, ""), height=100, key=f"qarea_{qk}")
                        
                        if st.button("Отправить", key=f"qsnd_{qk}"):
                            # ИСПОЛЬЗУЕМ ВЫБРАННЫЙ МЕТОД ОТПРАВКИ
                            res = send_wb(q['id'], q_resp, current_wb_token, "questions", question_method=q_method_code)
                            if res == "OK":
                                st.success("Успешно!")
                                st.session_state['questions'].remove(q)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(res)
            except: pass

# --- ЛОГИ ---
elif st.session_state['nav_selection'] == "📜 Журнал":
    for log in st.session_state['action_log']:
        st.write(log)

# --- АРХИВ ---
elif st.session_state['nav_selection'] == "🗄️ Архив":
    if st.button("📥 Загрузить историю"):
        st.session_state['history'] = get_wb_data(current_wb_token, "feedbacks", True)
    for item in st.session_state.get('history', []):
        try:
            name = item.get('productDetails', {}).get('productName', 'Товар')
            txt = item.get('text', '')
            with st.expander(f"{name} ({format_date(item.get('createdDate'))})"):
                st.write(txt if txt else "Без текста")
                if item.get('answer'): st.info(item['answer']['text'])
        except: pass

# === АВТО-РЕЖИМ ---
if (auto_reviews or auto_questions) and shop_list:
    st.toast(f"⚡ Авто-режим: {selected_shop}")
    
    if auto_reviews:
        for r in list(st.session_state.get('feedbacks', [])):
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
        for q in list(st.session_state.get('questions', [])):
            prod = q.get('productDetails', {}).get('productName', '')
            ans = generate_ai(groq_key, q.get('text',''), prod, "Покупатель", prompt_quest, signature)
            if "Ошибка" not in ans:
                # ИСПОЛЬЗУЕМ ТОТ ЖЕ МЕТОД ОТПРАВКИ, ЧТО И ВРУЧНУЮ
                if send_wb(q['id'], ans, current_wb_token, "questions", question_method=q_method_code) == "OK":
                    st.session_state['questions'].remove(q)
                    st.toast(f"Ответ: {prod}")
                    time.sleep(2)
                    st.rerun()
