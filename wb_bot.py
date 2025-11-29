import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# ==========================================
# 1. НАСТРОЙКИ СТРАНИЦЫ
# ==========================================
st.set_page_config(page_title="WB AI Master v17", layout="wide", page_icon="🛍️")

st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    .stTextArea textarea {font-size: 16px !important;}
    div[data-testid="stExpander"] div[role="button"] p {font-size: 16px; font-weight: 600;}
    
    /* Стили для чата */
    .chat-card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        background-color: #f9f9f9;
    }
    .chat-user {font-weight: bold; color: #2c3e50;}
    .chat-msg {background-color: #fff; padding: 10px; border-radius: 5px; border: 1px solid #eee; margin-top: 5px;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. ФУНКЦИИ WB (CORE)
# ==========================================

def format_date(iso_date):
    if not iso_date: return ""
    try:
        dt = datetime.datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return iso_date

def get_wb_data(wb_token, mode="feedbacks"):
    """Получение данных (Отзывы, Вопросы, Чаты)"""
    if len(wb_token) < 10: return []
    headers = {"Authorization": wb_token}
    
    try:
        # 1. ОТЗЫВЫ
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
            params = {"isAnswered": "false", "take": 30, "skip": 0, "order": "dateDesc"}
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code == 200: return res.json()['data']['feedbacks']

        # 2. ВОПРОСЫ
        elif mode == "questions":
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions"
            params = {"isAnswered": "false", "take": 30, "skip": 0, "order": "dateDesc"}
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code == 200: return res.json()['data']['questions']

        # 3. ЧАТЫ (Новый функционал)
        elif mode == "chats":
            url = "https://buyer-chat-api.wildberries.ru/api/v1/seller/chats"
            params = {"limit": 20, "sort": "desc"}
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code == 200:
                return res.json()['data']['chats']
            elif res.status_code == 401:
                st.error("WB API: Нет доступа к чатам (проверьте галочки в токене)")
                
        return []
    except Exception as e:
        st.error(f"Ошибка WB ({mode}): {e}")
        return []

def send_wb(id_val, text, wb_token, mode="feedbacks"):
    """Отправка ответа"""
    headers = {"Authorization": wb_token, "Content-Type": "application/json"}
    if not text or len(text) < 2: return "Текст пустой"
    
    try:
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
            payload = {"id": id_val, "text": text}
            res = requests.patch(url, headers=headers, json=payload, timeout=10)

        elif mode == "questions":
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions/answer"
            payload = {"id": id_val, "answer": {"text": text}, "state": "wbViewed"}
            res = requests.patch(url, headers=headers, json=payload, timeout=10)

        elif mode == "chats":
            # API Чатов отличается - там POST запрос
            url = "https://buyer-chat-api.wildberries.ru/api/v1/seller/message"
            payload = {"chatId": id_val, "text": text}
            res = requests.post(url, headers=headers, json=payload, timeout=10)

        # Обработка ответа
        if res.status_code in [200, 204]: return "OK"
        return f"Ошибка WB {res.status_code}: {res.text}"
            
    except Exception as e:
        return f"Сбой сети: {e}"

# ==========================================
# 3. НЕЙРОСЕТЬ (GROQ)
# ==========================================

def generate_ai(api_key, text, context, user_name, instructions, signature):
    if not api_key: return "Нет ключа Groq"
    
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    greeting = "Здравствуйте!"
    if user_name and len(user_name) > 1 and user_name.lower() not in ["покупатель", "клиент"]:
        greeting = f"Здравствуйте, {user_name}!"
        
    prompt = f"""
    Роль: Служба заботы о клиентах Wildberries.
    Контекст (Товар/Тема): {context}
    Сообщение клиента: "{text}"
    
    Твоя задача: Дать полезный, вежливый и человечный ответ на русском языке.
    Инструкция владельца: "{instructions}"
    
    ФОРМАТ:
    1. {greeting}
    2. (Пустая строка)
    3. Ответ по сути.
    4. (Пустая строка)
    5. {signature}
    """
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=600,
            timeout=15
        )
        res = response.choices[0].message.content
        if not res: return "ПУСТОЙ ОТВЕТ"
        return res
    except Exception as e:
        return f"ОШИБКА: {e}"

# ==========================================
# 4. ИНТЕРФЕЙС
# ==========================================

# Инициализация
if 'feedbacks' not in st.session_state: st.session_state['feedbacks'] = []
if 'questions' not in st.session_state: st.session_state['questions'] = []
if 'chats' not in st.session_state: st.session_state['chats'] = []

# Ключи
default_wb = ""
default_groq = ""
if hasattr(st, 'secrets'):
    default_wb = st.secrets.get('WB_API_TOKEN', "")
    default_groq = st.secrets.get('GROQ_API_KEY', "")

with st.sidebar:
    st.title("⚙️ Настройки")
    wb_token = st.text_input("WB Token", value=default_wb, type="password")
    groq_key = st.text_input("Groq Key", value=default_groq, type="password")
    
    st.divider()
    st.subheader("📝 Инструкции")
    prompt_rev = st.text_area("Для Отзывов:", value="Благодари за покупку.", height=60)
    prompt_chat = st.text_area("Для Чатов и Вопросов:", value="Отвечай коротко и по делу. Если проблема - проси фото или детали.", height=60)
    signature = st.text_input("Подпись:", value="С уважением, представитель бренда")
    
    st.divider()
    auto_mode = st.toggle("⚡ АВТО-РЕЖИМ (ВСЁ)", value=False)
    
    st.markdown("---")
    if st.button("🗑️ Сброс кэша"):
        st.session_state.clear()
        st.rerun()

if not wb_token or not groq_key:
    st.warning("Введите ключи.")
    st.stop()

st.title("🛍️ WB AI Master")

# Обновляем счетчики для табов
count_chats = len(st.session_state.get('chats', []))
count_rev = len(st.session_state.get('feedbacks', []))
count_quest = len(st.session_state.get('questions', []))

tab_chats, tab_rev, tab_quest, tab_hist = st.tabs([
    f"💬 Чаты ({count_chats})", 
    f"⭐ Отзывы ({count_rev})", 
    f"❓ Вопросы ({count_quest})", 
    "🗄️ Архив"
])

# === ВКЛАДКА 1: ЧАТЫ ===
with tab_chats:
    if st.button("🔄 Обновить чаты", type="primary"):
        with st.spinner("Проверяю сообщения..."):
            st.session_state['chats'] = get_wb_data(wb_token, "chats")
            st.rerun()
            
    chats = st.session_state.get('chats', [])
    if not chats:
        st.info("Нет активных диалогов.")
    else:
        for chat in chats:
            # Логика определения непрочитанных
            client_name = chat.get('client', {}).get('name', 'Покупатель')
            last_msg = chat.get('lastMessage', {})
            msg_text = last_msg.get('text', '')
            is_our_msg = last_msg.get('sender') == 'seller'
            
            # Если последнее сообщение наше - помечаем серым, если клиента - выделяем
            bg_color = "#e3f2fd" if not is_our_msg else "#f0f2f6"
            
            with st.container():
                st.markdown(f"""
                <div style="padding:10px; border-radius:10px; background-color:{bg_color}; border:1px solid #ddd; margin-bottom:10px;">
                    <b>👤 {client_name}</b> <span style="color:#888; font-size:12px;">(ID: {chat['id'][:8]}...)</span><br>
                    <div style="margin-top:5px; font-size:15px;">{msg_text}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Если последнее сообщение от клиента - даем ответить
                if not is_our_msg:
                    c1, c2 = st.columns([1, 1])
                    
                    key_gen = f"chat_gen_{chat['id']}"
                    
                    if c1.button("✨ Придумать ответ", key=f"btn_c_{chat['id']}"):
                        with st.spinner("Думаю..."):
                            ans = generate_ai(groq_key, msg_text, "Чат поддержки", client_name, prompt_chat, signature)
                            st.session_state[key_gen] = ans
                            st.rerun()
                            
                    val = st.session_state.get(key_gen, "")
                    final_txt = st.text_area("Ответ:", value=val, key=f"area_c_{chat['id']}", height=100)
                    
                    if c2.button("✉️ Отправить", key=f"snd_c_{chat['id']}"):
                        res = send_wb(chat['id'], final_txt, wb_token, "chats")
                        if res == "OK":
                            st.success("Сообщение отправлено!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(res)
                else:
                    st.caption("✅ Вы уже ответили на это сообщение")

# === ВКЛАДКА 2: ОТЗЫВЫ ===
with tab_rev:
    if st.button("🔄 Обновить отзывы"):
        st.session_state['feedbacks'] = get_wb_data(wb_token, "feedbacks")
        st.rerun()
    
    reviews = st.session_state.get('feedbacks', [])
    if not reviews:
        st.write("Пусто.")
    else:
        for rev in reviews:
            with st.expander(f"{'⭐'*rev['productValuation']} {rev['productDetails']['productName']}", expanded=True):
                st.write(rev.get('text', ''))
                
                k = f"r_{rev['id']}"
                if st.button("✨ Авто-ответ", key=f"b_{k}"):
                    ans = generate_ai(groq_key, rev.get('text',''), rev['productDetails']['productName'], rev.get('userName',''), prompt_rev, signature)
                    st.session_state[k] = ans
                    st.rerun()
                
                txt = st.text_area("Текст:", value=st.session_state.get(k, ""), key=f"t_{k}")
                if st.button("Отправить", key=f"s_{k}"):
                    if send_wb(rev['id'], txt, wb_token, "feedbacks") == "OK":
                        st.success("Ушло!")
                        st.session_state['feedbacks'].remove(rev)
                        time.sleep(1)
                        st.rerun()

# === ВКЛАДКА 3: ВОПРОСЫ ===
with tab_quest:
    if st.button("🔄 Обновить вопросы"):
        st.session_state['questions'] = get_wb_data(wb_token, "questions")
        st.rerun()
        
    quests = st.session_state.get('questions', [])
    if not quests:
        st.write("Пусто.")
    else:
        for q in quests:
            with st.expander(f"❓ {q['productDetails']['productName']}", expanded=True):
                st.write(q.get('text', ''))
                
                k = f"q_{q['id']}"
                if st.button("✨ Авто-ответ", key=f"b_{k}"):
                    ans = generate_ai(groq_key, q.get('text',''), q['productDetails']['productName'], "Покупатель", prompt_chat, signature)
                    st.session_state[k] = ans
                    st.rerun()
                
                txt = st.text_area("Текст:", value=st.session_state.get(k, ""), key=f"t_{k}")
                if st.button("Отправить", key=f"s_{k}"):
                    if send_wb(q['id'], txt, wb_token, "questions") == "OK":
                        st.success("Ушло!")
                        st.session_state['questions'].remove(q)
                        time.sleep(1)
                        st.rerun()

# === АРХИВ ===
with tab_hist:
    if st.button("📥 Загрузить историю (Отзывы)"):
        st.session_state['history'] = get_wb_data(wb_token, "feedbacks")
    
    for item in st.session_state.get('history', []):
        st.text(f"{item['createdDate']} - {item['text']}")

# === АВТО-РЕЖИМ (ФОНОВЫЙ) ===
if auto_mode:
    st.info("🤖 Бот работает... (Не закрывайте вкладку)")
    progress_bar = st.progress(0)
    
    # 1. ЧАТЫ (Новое!)
    chats = get_wb_data(wb_token, "chats")
    for chat in chats:
        last_msg = chat.get('lastMessage', {})
        # Если последнее сообщение НЕ от нас -> надо отвечать
        if last_msg.get('sender') != 'seller':
            client_name = chat.get('client', {}).get('name', 'Покупатель')
            text = last_msg.get('text', '')
            st.toast(f"Чат: сообщение от {client_name}")
            
            # Генерируем
            ans = generate_ai(groq_key, text, "Чат поддержки", client_name, prompt_chat, signature)
            if "ОШИБКА" not in ans:
                # Отправляем
                send_wb(chat['id'], ans, wb_token, "chats")
                st.toast(f"✅ Ответил в чат")
            time.sleep(2)

    # 2. ВОПРОСЫ
    qs = get_wb_data(wb_token, "questions")
    for q in qs:
        ans = generate_ai(groq_key, q.get('text',''), "Товар", "Покупатель", prompt_chat, signature)
        if "ОШИБКА" not in ans:
            send_wb(q['id'], ans, wb_token, "questions")
            st.toast("✅ Ответил на вопрос")
        time.sleep(2)

    # 3. ОТЗЫВЫ
    rs = get_wb_data(wb_token, "feedbacks")
    for r in rs:
        ans = generate_ai(groq_key, r.get('text',''), "Товар", "Клиент", prompt_rev, signature)
        if "ОШИБКА" not in ans:
            send_wb(r['id'], ans, wb_token, "feedbacks")
            st.toast("✅ Ответил на отзыв")
        time.sleep(2)
    
    st.success("Круг завершен. Жду 60 сек...")
    time.sleep(60)
    st.rerun()
