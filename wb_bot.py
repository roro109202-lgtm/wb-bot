import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# ==========================================
# 1. НАСТРОЙКИ (DARK MODE FRIENDLY)
# ==========================================
st.set_page_config(page_title="WB AI Master v29 (Global)", layout="wide", page_icon="🌐")

st.markdown("""
    <style>
    .block-container {padding-top: 1.5rem;}
    .stTextArea textarea {font-size: 16px !important;}
    
    /* Цвета для текста */
    .pros-text {color: #66BB6A; font-weight: bold;}
    .cons-text {color: #EF5350; font-weight: bold;}
    
    /* Стиль логов мониторинга */
    .monitor-log {
        font-family: monospace;
        padding: 5px;
        border-bottom: 1px solid #333;
        font-size: 14px;
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
        res = requests.get(url, headers=headers, params=params, timeout=10)
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
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    icon = "✅" if type == "success" else "❌" if type == "error" else "⚡"
    entry = f"{timestamp} {icon} {message}"
    if 'action_log' in st.session_state:
        st.session_state['action_log'].insert(0, entry)
        # Ограничиваем размер лога
        if len(st.session_state['action_log']) > 100:
            st.session_state['action_log'].pop()

# ==========================================
# 3. ИНИЦИАЛИЗАЦИЯ
# ==========================================

if 'feedbacks' not in st.session_state: st.session_state['feedbacks'] = []
if 'questions' not in st.session_state: st.session_state['questions'] = []
if 'action_log' not in st.session_state: st.session_state['action_log'] = []
if 'history' not in st.session_state: st.session_state['history'] = []

# --- ЗАГРУЗКА МАГАЗИНОВ ---
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
    st.title("🎛️ Управление")
    
    # 1. Секция магазинов
    shop_list = list(st.session_state['shops'].keys())
    if not shop_list:
        st.warning("Добавьте магазин!")
        current_wb_token = ""
        selected_shop = ""
    else:
        # Если включен авто-режим, выбор магазина блокируется визуально (но не технически)
        selected_shop = st.selectbox("Текущий магазин (для ручного):", shop_list)
        current_wb_token = st.session_state['shops'][selected_shop]
        
        with st.expander("Добавить еще магазин"):
            add_name = st.text_input("Название")
            add_token = st.text_input("Токен", type="password")
            if st.button("Сохранить"):
                st.session_state['shops'][add_name] = add_token
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
    st.header("🤖 ГЛОБАЛЬНЫЙ АВТО-РЕЖИМ")
    st.info("Бот будет проверять ВСЕ магазины по очереди.")
    auto_reviews = st.toggle("Авто Отзывы (Все магазины)")
    auto_questions = st.toggle("Авто Вопросы (Все магазины)")
    
    st.markdown("---")
    if st.button("Сброс кэша"):
        st.session_state.clear()
        st.rerun()

if not groq_key:
    st.error("Нужен Groq Key")
    st.stop()

# ==========================================
# 5. ЛОГИКА АВТОМАТИЗАЦИИ (ГЛОБАЛЬНАЯ)
# ==========================================

if (auto_reviews or auto_questions) and shop_list:
    st.title("🌐 Центр мониторинга")
    st.caption("Бот работает в фоне. Не закрывайте вкладку.")
    
    status_box = st.empty() # Контейнер для текущего статуса
    log_box = st.container() # Контейнер для истории логов
    
    # Цикл по всем магазинам
    for sh_name, sh_token in st.session_state['shops'].items():
        status_box.info(f"🔍 Сканирую магазин: **{sh_name}**...")
        
        # 1. ОТЗЫВЫ
        if auto_reviews:
            try:
                items = get_wb_data(sh_token, "feedbacks")
                if items:
                    for item in items:
                        # Фильтры можно добавить сюда, пока отвечаем на все
                        prod = item.get('productDetails', {}).get('productName', 'Товар')
                        
                        # Текст
                        pros = item.get('pros', '')
                        cons = item.get('cons', '')
                        comm = item.get('text', '')
                        full = f"Плюсы: {pros}. Минусы: {cons}. Текст: {comm}"
                        if not full.strip(): full = "Оценка без текста"
                        
                        ans = generate_ai(groq_key, full, prod, item.get('userName',''), prompt_rev, signature)
                        
                        if "Ошибка" not in ans:
                            if send_wb(item['id'], ans, sh_token, "feedbacks") == "OK":
                                log_event(f"[{sh_name}] Отзыв: {prod}", "success")
                                st.toast(f"[{sh_name}] Отзыв закрыт")
                                time.sleep(2)
            except Exception as e:
                log_event(f"[{sh_name}] Ошибка отзывов: {e}", "error")

        # 2. ВОПРОСЫ
        if auto_questions:
            try:
                quests = get_wb_data(sh_token, "questions")
                if quests:
                    for q in quests:
                        prod = q.get('productDetails', {}).get('productName', 'Товар')
                        ans = generate_ai(groq_key, q.get('text',''), prod, "Покупатель", prompt_quest, signature)
                        
                        if "Ошибка" not in ans:
                            if send_wb(q['id'], ans, sh_token, "questions") == "OK":
                                log_event(f"[{sh_name}] Вопрос: {prod}", "success")
                                st.toast(f"[{sh_name}] Вопрос закрыт")
                                time.sleep(2)
            except Exception as e:
                log_event(f"[{sh_name}] Ошибка вопросов: {e}", "error")
        
        time.sleep(1) # Пауза между магазинами

    status_box.success(f"✅ Круг завершен {datetime.datetime.now().strftime('%H:%M:%S')}. Жду 60 сек...")
    
    # Вывод логов
    with log_box:
        st.write("Последние действия:")
        for log in st.session_state['action_log'][:20]: # Показываем последние 20
            st.code(log, language="text")

    time.sleep(60)
    st.rerun()

# ==========================================
# 6. РУЧНОЙ РЕЖИМ (ЕСЛИ АВТО ВЫКЛЮЧЕН)
# ==========================================
else:
    if not shop_list:
        st.title("Добро пожаловать!")
        st.info("Добавьте магазины в меню слева.")
    else:
        st.title(f"🛍️ {selected_shop}")
        
        if st.button("🔄 Обновить данные текущего магазина", type="primary", use_container_width=True):
            with st.spinner("Загрузка..."):
                st.session_state['feedbacks'] = get_wb_data(current_wb_token, "feedbacks")
                st.session_state['questions'] = get_wb_data(current_wb_token, "questions")
        
        c1, c2 = st.columns(2)
        c1.metric("Отзывы", len(st.session_state.get('feedbacks', [])))
        c2.metric("Вопросы", len(st.session_state.get('questions', [])))
        
        st.write("")
        
        tab_rev, tab_quest, tab_arch = st.tabs(["⭐ Отзывы", "❓ Вопросы", "🗄️ Архив"])
        
        # --- Вкладка Отзывов (Ручная) ---
        with tab_rev:
            for rev in st.session_state.get('feedbacks', []):
                try:
                    prod_name = rev.get('productDetails', {}).get('productName', 'Товар')
                    nm_id = rev.get('productDetails', {}).get('nmId', 0)
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
                            st.caption(f"Арт: {nm_id}")
                            st.write(f"{'⭐'*rating} | **{user}**")
                            st.markdown("---")
                            
                            if pros: st.markdown(f":green[**Достоинства:**] {pros}")
                            if cons: st.markdown(f":red[**Недостатки:**] {cons}")
                            if comment: st.markdown(f"**Комментарий:** {comment}")
                            if not (pros or cons or comment): st.caption("*(Оценка без текста)*")
                            
                            # Фото клиента
                            if rev.get('photoLinks'):
                                p_cols = st.columns(6)
                                for i, p in enumerate(rev['photoLinks'][:6]):
                                    p_url = p.get('smallSize') or p.get('fullSize')
                                    if p_url: p_cols[i].image(p_url)
                            
                            st.markdown("---")
                            
                            key = f"r_{rev['id']}"
                            if st.button("✨ Сгенерировать", key=f"btn_{key}"):
                                ans = generate_ai(groq_key, full_text_ai if full_text_ai else "Оценка без текста", prod_name, user, prompt_rev, signature)
                                st.session_state[key] = ans
                                st.rerun()
                            
                            resp = st.text_area("Ответ:", value=st.session_state.get(key, ""), height=100, key=f"area_{key}")
                            
                            if st.button("Отправить", key=f"snd_{key}"):
                                res = send_wb(rev['id'], resp, current_wb_token, "feedbacks")
                                if res == "OK":
                                    st.success("Готово!")
                                    st.session_state['feedbacks'].remove(rev)
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(res)
                except: pass

        # --- Вкладка Вопросов (Ручная) ---
        with tab_quest:
            for q in st.session_state.get('questions', []):
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
                            
                            qk = f"q_{q['id']}"
                            if st.button("✨ Ответ", key=f"qbtn_{qk}"):
                                ans = generate_ai(groq_key, text, prod_name, "Покупатель", prompt_quest, signature)
                                st.session_state[qk] = ans
                                st.rerun()
                                
                            q_resp = st.text_area("Ответ:", value=st.session_state.get(qk, ""), height=100, key=f"qarea_{qk}")
                            
                            if st.button("Отправить", key=f"qsnd_{qk}"):
                                res = send_wb(q['id'], q_resp, current_wb_token, "questions")
                                if res == "OK":
                                    st.success("Готово!")
                                    st.session_state['questions'].remove(q)
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(res)
                except: pass

        # --- Вкладка Архива ---
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
