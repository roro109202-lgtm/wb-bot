import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# ==========================================
# 1. НАСТРОЙКИ
# ==========================================
st.set_page_config(page_title="WB AI Master v40", layout="wide", page_icon="🛍️")

st.markdown("""
    <style>
    .block-container {padding-top: 1.5rem;}
    .stTextArea textarea {font-size: 16px !important;}
    
    .wb-pros {color: #4CAF50; font-weight: 500; margin-bottom: 2px;}
    .wb-cons {color: #FF5252; font-weight: 500; margin-bottom: 2px;}
    .wb-comment {margin-top: 8px; font-size: 16px;}
    
    /* Подсветка кнопок */
    .stButton>button {
        border-radius: 8px;
        font-weight: bold;
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

def send_wb_smart(review_id, text, wb_token, mode="feedbacks"):
    """Умная отправка с перебором вариантов"""
    headers = {"Authorization": wb_token, "Content-Type": "application/json"}
    if not text or len(text) < 2: return "Текст пустой"
    
    try:
        if mode == "feedbacks":
            # Для отзывов всё просто
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
            payload = {"id": review_id, "text": text}
            res = requests.patch(url, headers=headers, json=payload, timeout=15)
            if res.status_code in [200, 204]: return "OK"
            return f"Ошибка {res.status_code}: {res.text}"
            
        else:
            # ДЛЯ ВОПРОСОВ - ПЕРЕБОР СТАТУСОВ
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions"
            
            # Вариант 1: wbViewed (Стандарт)
            payload1 = {"id": review_id, "answer": {"text": text}, "state": "wbViewed"}
            res1 = requests.patch(url, headers=headers, json=payload1, timeout=10)
            if res1.status_code in [200, 204]: return "OK"
            
            # Вариант 2: none (Если первый не прошел)
            payload2 = {"id": review_id, "answer": {"text": text}, "state": "none"}
            res2 = requests.patch(url, headers=headers, json=payload2, timeout=10)
            if res2.status_code in [200, 204]: return "OK"

            return f"Не ушло. Ошибка: {res1.text}"

    except Exception as e:
        return f"Сбой сети: {e}"

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
    entry = f"{timestamp} | {message}"
    if 'action_log' in st.session_state:
        st.session_state['action_log'].insert(0, entry)

# ==========================================
# 3. ИНИЦИАЛИЗАЦИЯ
# ==========================================

if 'feedbacks' not in st.session_state: st.session_state['feedbacks'] = []
if 'questions' not in st.session_state: st.session_state['questions'] = []
if 'action_log' not in st.session_state: st.session_state['action_log'] = []
if 'history' not in st.session_state: st.session_state['history'] = []

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
        selected_shop = st.selectbox("Магазин:", shop_list, key='shop_select')
        current_wb_token = st.session_state['shops'][selected_shop]
        
        with st.expander("Добавить еще"):
            add_n = st.text_input("Название")
            add_t = st.text_input("Токен", type="password")
            if st.button("ОК"):
                st.session_state['shops'][add_n] = add_t
                st.rerun()
        
        if st.button("Удалить текущий"):
            del st.session_state['shops'][selected_shop]
            st.rerun()

    st.divider()
    groq_key = st.text_input("Groq Key", value=default_groq, type="password")
    
    with st.expander("Настройки ИИ"):
        prompt_rev = st.text_area("Отзывы:", value="Благодари за покупку.", height=70)
        prompt_quest = st.text_area("Вопросы:", value="Отвечай коротко.", height=70)
        signature = st.text_input("Подпись:", value="С уважением, представитель бренда")
    
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

st.title(f"🛍️ {st.session_state.shop_select}")

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
                        
                        # КНОПКИ И ПОЛЕ (ИСПРАВЛЕННАЯ СИНХРОНИЗАЦИЯ)
                        area_key = f"area_rev_{rev['id']}"
                        
                        if st.button("✨ Сгенерировать ответ", key=f"btn_{rev['id']}"):
                            with st.spinner("Пишу..."):
                                ans = generate_ai(groq_key, full_text_ai, prod_name, user, prompt_rev, signature)
                                st.session_state[area_key] = ans # Записываем в ключ поля
                                st.rerun() # ОБНОВЛЯЕМ ЭКРАН МГНОВЕННО
                        
                        # Поле ввода без value, но с key
                        final_txt = st.text_area("Ваш ответ:", key=area_key)
                        
                        if st.button("Отправить", key=f"snd_{rev['id']}"):
                            res = send_wb_smart(rev['id'], final_txt, current_wb_token, "feedbacks")
                            if res == "OK":
                                st.success("Отправлено!")
                                st.session_state['feedbacks'].remove(rev)
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error(res)
            except: pass

# --- ВОПРОСЫ ---
with tab_quest:
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
                        
                        # КНОПКИ И ПОЛЕ (ИСПРАВЛЕННАЯ СИНХРОНИЗАЦИЯ)
                        area_q_key = f"area_q_{q['id']}"
                        
                        if st.button("✨ Ответ", key=f"qbtn_{q['id']}"):
                            with st.spinner("Пишу..."):
                                ans = generate_ai(groq_key, text, prod_name, "Покупатель", prompt_quest, signature)
                                st.session_state[area_q_key] = ans # Записываем в ключ поля
                                st.rerun() # ОБНОВЛЯЕМ ЭКРАН МГНОВЕННО
                            
                        final_q = st.text_area("Ваш ответ:", key=area_q_key)
                        
                        if st.button("Отправить", key=f"qsnd_{q['id']}"):
                            res = send_wb_smart(q['id'], final_q, current_wb_token, "questions")
                            if res == "OK":
                                st.success("Успешно!")
                                st.session_state['questions'].remove(q)
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error(res)
            except: pass

# --- ЛОГИ ---
with tab_log:
    for log in st.session_state['action_log']:
        st.write(log)

# --- АРХИВ ---
with tab_arch:
    if st.button("📥 История"):
        st.session_state['history'] = get_wb_data(current_wb_token, "feedbacks", True)
    for item in st.session_state.get('history', []):
        try:
            name = item.get('productDetails', {}).get('productName', 'Товар')
            txt = item.get('text', '')
            with st.expander(f"{name} ({format_date(item.get('createdDate'))})"):
                st.write(txt if txt else "Без текста")
                if item.get('answer'): st.info(item['answer']['text'])
        except: pass

# --- АВТО-РЕЖИМ ---
if (auto_reviews or auto_questions) and shop_list:
    st.toast(f"⚡ Авто-режим: {selected_shop}")
    
    # Перебор всех магазинов
    for sh_name, sh_token in st.session_state['shops'].items():
        if auto_reviews:
            items = get_wb_data(sh_token, "feedbacks")
            for item in items:
                prod = item.get('productDetails', {}).get('productName', '')
                pros = item.get('pros', '')
                cons = item.get('cons', '')
                comm = item.get('text', '')
                full = f"Плюсы: {pros}. Минусы: {cons}. Текст: {comm}"
                if not full.strip(): full = "Оценка без текста"
                
                ans = generate_ai(groq_key, full, prod, item.get('userName',''), prompt_rev, signature)
                if "Ошибка" not in ans:
                    if send_wb_smart(item['id'], ans, sh_token, "feedbacks") == "OK":
                        log_event(f"[{sh_name}] Отзыв: {prod}", "success")
                        time.sleep(2)

        if auto_questions:
            quests = get_wb_data(sh_token, "questions")
            for q in quests:
                prod = q.get('productDetails', {}).get('productName', '')
                ans = generate_ai(groq_key, q.get('text',''), prod, "Покупатель", prompt_quest, signature)
                if "Ошибка" not in ans:
                    if send_wb_smart(q['id'], ans, sh_token, "questions") == "OK":
                        log_event(f"[{sh_name}] Вопрос: {prod}", "success")
                        time.sleep(2)
        
        time.sleep(1)
    
    time.sleep(600)
    st.rerun()
