import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# ==========================================
# 1. НАСТРОЙКИ И ДИЗАЙН
# ==========================================
st.set_page_config(page_title="WB AI PRO v19", layout="wide", page_icon="💎")

# Профессиональный CSS
st.markdown("""
    <style>
    .block-container {padding-top: 1.5rem;}
    
    /* Карточки метрик */
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Карточка отзыва */
    .wb-card {
        border: 1px solid #eee;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 15px;
        background: white;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    
    /* Логи */
    .log-entry {
        font-family: monospace;
        font-size: 13px;
        padding: 5px;
        border-bottom: 1px solid #eee;
    }
    .log-success {color: #2e7d32;}
    .log-error {color: #c62828;}
    
    .stTextArea textarea {font-size: 16px !important;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. ФУНКЦИИ (CORE)
# ==========================================

def format_date(iso_date):
    if not iso_date: return ""
    try:
        dt = datetime.datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return iso_date

def get_wb_data(wb_token, mode="feedbacks", is_answered=False):
    if len(wb_token) < 10: return []
    headers = {"Authorization": wb_token}
    params = {"isAnswered": str(is_answered).lower(), "take": 50, "skip": 0, "order": "dateDesc"}
    
    try:
        url = f"https://feedbacks-api.wildberries.ru/api/v1/{mode}"
        res = requests.get(url, headers=headers, params=params, timeout=10)
        if res.status_code == 200:
            return res.json()['data'][mode]
        return []
    except Exception as e:
        return []

def send_wb(review_id, text, wb_token, mode="feedbacks"):
    headers = {"Authorization": wb_token, "Content-Type": "application/json"}
    if not text or len(text) < 2: return "Текст пустой"
    
    try:
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
            payload = {"id": review_id, "text": text}
        else: # questions
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions/answer"
            payload = {"id": review_id, "answer": {"text": text}, "state": "wbViewed"}
        
        res = requests.patch(url, headers=headers, json=payload, timeout=10)
        
        if res.status_code in [200, 204]: return "OK"
        return f"Ошибка WB {res.status_code}"
    except Exception as e:
        return f"Сбой сети: {e}"

def generate_ai(api_key, text, item_name, user_name, instructions, signature):
    if not api_key: return "Нет ключа Groq"
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    greeting = f"Здравствуйте, {user_name}!" if user_name and len(user_name) > 2 and user_name.lower() != "клиент" else "Здравствуйте!"
    
    prompt = f"""
    Роль: Менеджер Wildberries.
    Товар: {item_name}
    Клиент пишет: "{text}"
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
    """Запись в журнал событий"""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    icon = "✅" if type == "success" else "❌" if type == "error" else "ℹ️"
    entry = f"{timestamp} {icon} {message}"
    st.session_state['action_log'].insert(0, entry)
    # Храним только последние 50 записей
    if len(st.session_state['action_log']) > 50:
        st.session_state['action_log'].pop()

# ==========================================
# 3. ИНИЦИАЛИЗАЦИЯ И ИНТЕРФЕЙС
# ==========================================

if 'feedbacks' not in st.session_state: st.session_state['feedbacks'] = []
if 'questions' not in st.session_state: st.session_state['questions'] = []
if 'history' not in st.session_state: st.session_state['history'] = []
if 'action_log' not in st.session_state: st.session_state['action_log'] = []

# Ключи
default_wb = ""
default_groq = ""
if hasattr(st, 'secrets'):
    default_wb = st.secrets.get('WB_API_TOKEN', "")
    default_groq = st.secrets.get('GROQ_API_KEY', "")

with st.sidebar:
    st.title("🎛️ Панель управления")
    
    with st.expander("🔑 API Ключи", expanded=True):
        wb_token = st.text_input("WB Token", value=default_wb, type="password")
        groq_key = st.text_input("Groq Key", value=default_groq, type="password")
    
    with st.expander("📝 Инструкции (Промпты)"):
        prompt_rev = st.text_area("Для отзывов:", value="Благодари за покупку. Если 5 звезд - призывай добавить в любимые бренды.", height=80)
        prompt_quest = st.text_area("Для вопросов:", value="Отвечай коротко и по делу. Будь экспертом.", height=80)
        signature = st.text_input("Подпись:", value="С уважением, команда бренда")
    
    st.divider()
    st.subheader("🤖 Автопилот")
    col_auto1, col_auto2 = st.columns(2)
    auto_reviews = col_auto1.toggle("Авто Отзывы")
    auto_questions = col_auto2.toggle("Авто Вопросы")
    
    if auto_reviews or auto_questions:
        st.info("Авто-режим активен. Не закрывайте вкладку.")
    
    st.markdown("---")
    if st.button("🧹 Очистить кэш"):
        st.session_state.clear()
        st.rerun()

if not wb_token or not groq_key:
    st.warning("Введите ключи для старта.")
    st.stop()

# --- ГЛАВНЫЙ ЭКРАН ---

st.title("💎 WB AI PRO Interface")

# Кнопка обновления данных (одна на всё)
if st.button("🔄 Сканировать магазин", type="primary", use_container_width=True):
    with st.spinner("Связь с Wildberries..."):
        st.session_state['feedbacks'] = get_wb_data(wb_token, "feedbacks")
        st.session_state['questions'] = get_wb_data(wb_token, "questions")
        log_event("Данные обновлены вручную")

# --- ДАШБОРД МЕТРИК ---
c1, c2, c3 = st.columns(3)
count_rev = len(st.session_state.get('feedbacks', []))
count_quest = len(st.session_state.get('questions', []))

c1.metric("Ждут отзывов", count_rev, border=True)
c2.metric("Ждут вопросов", count_quest, border=True)
c3.metric("Обработано (сессия)", len(st.session_state['action_log']), border=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- ТАБЫ ---
tab_rev, tab_quest, tab_log, tab_arch = st.tabs([
    f"⭐ Отзывы ({count_rev})", 
    f"❓ Вопросы ({count_quest})", 
    "📜 Журнал действий",
    "🗄️ Архив"
])

# === ВКЛАДКА 1: ОТЗЫВЫ ===
with tab_rev:
    reviews = st.session_state.get('feedbacks', [])
    if not reviews:
        st.info("Нет неотвеченных отзывов.")
    else:
        for rev in reviews:
            with st.container(border=True):
                # Шапка
                cols = st.columns([4, 1])
                cols[0].markdown(f"**{rev['productDetails']['productName']}**")
                cols[1].markdown(f"⭐ **{rev['productValuation']}**")
                
                # Контент
                c_img, c_txt = st.columns([1, 6])
                with c_img:
                    if rev.get('photoLinks'):
                        st.image(rev['photoLinks'][0]['smallSize'], use_container_width=True)
                    else:
                        st.write("📦")
                
                with c_txt:
                    user = rev.get('userName', 'Клиент')
                    st.write(f"👤 **{user}:** {rev.get('text', '')}")
                    
                    # Уникальные ключи
                    area_key = f"rev_txt_{rev['id']}"
                    
                    # Генерация
                    if st.button("✨ Сгенерировать", key=f"gen_r_{rev['id']}"):
                        ans = generate_ai(groq_key, rev.get('text', ''), rev['productDetails']['productName'], user, prompt_rev, signature)
                        st.session_state[area_key] = ans
                        st.rerun()
                    
                    val = st.session_state.get(area_key, "")
                    final_txt = st.text_area("Ответ:", key=area_key, label_visibility="collapsed", placeholder="Здесь будет ответ нейросети...")
                    
                    if st.button("Отправить", key=f"snd_r_{rev['id']}"):
                        res = send_wb(rev['id'], final_txt, wb_token, "feedbacks")
                        if res == "OK":
                            st.success("Отправлено!")
                            log_event(f"Ручной ответ на отзыв: {rev['productDetails']['productName']}", "success")
                            st.session_state['feedbacks'].remove(rev)
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(res)

# === ВКЛАДКА 2: ВОПРОСЫ ===
with tab_quest:
    quests = st.session_state.get('questions', [])
    if not quests:
        st.info("Нет неотвеченных вопросов.")
    else:
        for q in quests:
            with st.container(border=True):
                st.markdown(f"❓ **{q['productDetails']['productName']}**")
                st.caption(format_date(q['createdDate']))
                st.write(f"**Вопрос:** {q.get('text', '')}")
                
                area_q_key = f"quest_txt_{q['id']}"
                
                if st.button("✨ Придумать ответ", key=f"gen_q_{q['id']}"):
                    ans = generate_ai(groq_key, q.get('text', ''), q['productDetails']['productName'], "Покупатель", prompt_quest, signature)
                    st.session_state[area_q_key] = ans
                    st.rerun()
                
                val_q = st.session_state.get(area_q_key, "")
                final_q = st.text_area("Ответ:", key=area_q_key, label_visibility="collapsed", placeholder="Ответ на вопрос...")
                
                if st.button("Отправить", key=f"snd_q_{q['id']}"):
                    res = send_wb(q['id'], final_q, wb_token, "questions")
                    if res == "OK":
                        st.success("Отправлено!")
                        log_event(f"Ручной ответ на вопрос: {q['productDetails']['productName']}", "success")
                        st.session_state['questions'].remove(q)
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(res)

# === ВКЛАДКА 3: ЖУРНАЛ (ЛОГИ) ===
with tab_log:
    st.markdown("### 📜 История действий бота")
    if not st.session_state['action_log']:
        st.caption("Пока действий не было.")
    else:
        for log in st.session_state['action_log']:
            color = "#2e7d32" if "✅" in log else "#c62828" if "❌" in log else "#333"
            st.markdown(f"<div style='color:{color}; border-bottom:1px solid #eee; padding:5px;'>{log}</div>", unsafe_allow_html=True)

# === ВКЛАДКА 4: АРХИВ ===
with tab_arch:
    if st.button("📥 Загрузить историю с WB"):
        with st.spinner("Загрузка..."):
            rv = get_wb_data(wb_token, "feedbacks", True)
            qs = get_wb_data(wb_token, "questions", True)
            st.session_state['history'] = rv + qs
            # Сортировка
            st.session_state['history'].sort(key=lambda x: x['createdDate'], reverse=True)
            
    for item in st.session_state.get('history', []):
        with st.expander(f"{item['productDetails']['productName']} ({format_date(item['createdDate'])})"):
            st.write(f"👤 {item.get('text', '')}")
            if item.get('answer'):
                st.info(item['answer']['text'])

# ==========================================
# ЛОГИКА АВТОМАТИЗАЦИИ
# ==========================================

if auto_reviews or auto_questions:
    status_container = st.empty()
    
    # 1. АВТО-ОТЗЫВЫ
    if auto_reviews:
        items = get_wb_data(wb_token, "feedbacks")
        for item in items:
            status_container.warning(f"🤖 Обрабатываю отзыв: {item['productDetails']['productName']}...")
            
            user = item.get('userName', 'Клиент')
            ans = generate_ai(groq_key, item.get('text', ''), item['productDetails']['productName'], user, prompt_rev, signature)
            
            if "Ошибка" not in ans:
                res = send_wb(item['id'], ans, wb_token, "feedbacks")
                if res == "OK":
                    log_event(f"Авто-ответ на отзыв: {item['productDetails']['productName']}", "success")
                    st.toast(f"✅ Отзыв закрыт")
                else:
                    log_event(f"Ошибка отправки отзыва: {res}", "error")
            else:
                log_event(f"Ошибка генерации: {ans}", "error")
            
            time.sleep(3)

    # 2. АВТО-ВОПРОСЫ
    if auto_questions:
        quests = get_wb_data(wb_token, "questions")
        for q in quests:
            status_container.warning(f"🤖 Обрабатываю вопрос: {q['productDetails']['productName']}...")
            
            ans = generate_ai(groq_key, q.get('text', ''), q['productDetails']['productName'], "Покупатель", prompt_quest, signature)
            
            if "Ошибка" not in ans:
                res = send_wb(q['id'], ans, wb_token, "questions")
                if res == "OK":
                    log_event(f"Авто-ответ на вопрос: {q['productDetails']['productName']}", "success")
                    st.toast(f"✅ Вопрос закрыт")
                else:
                    log_event(f"Ошибка отправки вопроса: {res}", "error")
            time.sleep(3)
    
    status_container.success(f"✅ Проверка завершена {datetime.datetime.now().strftime('%H:%M:%S')}. Жду 60 сек...")
    time.sleep(60)
    st.rerun()
