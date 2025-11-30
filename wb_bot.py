import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# ==========================================
# 1. НАСТРОЙКИ
# ==========================================
st.set_page_config(page_title="WB AI Master v18", layout="wide", page_icon="🛡️")

st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    .stTextArea textarea {font-size: 16px !important;}
    div[data-testid="stExpander"] div[role="button"] p {font-size: 16px; font-weight: 600;}
    .chat-card {border: 1px solid #ddd; padding: 10px; border-radius: 8px; margin-bottom: 10px; background: #f8f9fa;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. ФУНКЦИИ WB (БЕЗОПАСНЫЕ)
# ==========================================

def format_date(iso_date):
    if not iso_date: return ""
    try:
        dt = datetime.datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return iso_date

def get_wb_data(wb_token, mode="feedbacks", is_answered=False):
    """
    Универсальная и БЕЗОПАСНАЯ функция получения данных.
    Не падает, если WB присылает ерунду.
    """
    if len(wb_token) < 10: return []
    headers = {"Authorization": wb_token}
    
    try:
        # --- 1. ЧАТЫ (Самые капризные) ---
        if mode == "chats":
            url = "https://buyer-chat-api.wildberries.ru/api/v1/seller/chats"
            params = {"limit": 20, "sort": "desc"}
            res = requests.get(url, headers=headers, params=params, timeout=10)
            
            if res.status_code == 200:
                json_data = res.json()
                # Проверка: есть ли ключ 'data' и не пустой ли он
                if 'data' in json_data and json_data['data'] is not None:
                    if 'chats' in json_data['data']:
                        return json_data['data']['chats']
                return [] # Если структуры нет, возвращаем пустой список, а не ошибку
            
            elif res.status_code == 401:
                st.error("Чаты: Ошибка 401. Проверьте галочку 'Чат с покупателями' в токене!")
                return []
            else:
                st.warning(f"Чаты не загрузились (код {res.status_code})")
                return []

        # --- 2. ОТЗЫВЫ И ВОПРОСЫ ---
        else:
            params = {
                "isAnswered": str(is_answered).lower(),
                "take": 30,
                "skip": 0,
                "order": "dateDesc"
            }
            
            if mode == "feedbacks":
                url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
                key = 'feedbacks'
            else: # questions
                url = "https://feedbacks-api.wildberries.ru/api/v1/questions"
                key = 'questions'
                
            res = requests.get(url, headers=headers, params=params, timeout=15)
            
            if res.status_code == 200:
                json_data = res.json()
                # Безопасная проверка вложенности
                if 'data' in json_data and json_data['data'] is not None:
                    if key in json_data['data'] and json_data['data'][key] is not None:
                        return json_data['data'][key]
                return []
            
            return []

    except Exception as e:
        # Пишем ошибку в консоль, но не ломаем приложение
        print(f"Global Error in get_wb_data ({mode}): {e}")
        return []

def send_wb(id_val, text, wb_token, mode="feedbacks"):
    headers = {"Authorization": wb_token, "Content-Type": "application/json"}
    if not text or len(text) < 2: return "Текст пустой"
    
    try:
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
            payload = {"id": id_val, "text": text}
            res = requests.patch(url, headers=headers, json=payload, timeout=15)

        elif mode == "questions":
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions/answer"
            # ВАЖНО: Используем wbViewed, это работает
            payload = {"id": id_val, "answer": {"text": text}, "state": "wbViewed"}
            res = requests.patch(url, headers=headers, json=payload, timeout=15)

        elif mode == "chats":
            url = "https://buyer-chat-api.wildberries.ru/api/v1/seller/message"
            payload = {"chatId": id_val, "text": text}
            res = requests.post(url, headers=headers, json=payload, timeout=15)

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
    Роль: Поддержка Wildberries.
    Контекст: {context}
    Текст клиента: "{text}"
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
            max_tokens=600,
            timeout=20
        )
        res = response.choices[0].message.content
        if not res: return "ПУСТОЙ ОТВЕТ"
        return res
    except Exception as e:
        return f"ОШИБКА: {e}"

# ==========================================
# 4. ИНТЕРФЕЙС
# ==========================================

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
    prompt_rev = st.text_area("Промпт (Отзывы):", value="Благодари за покупку.", height=60)
    prompt_chat = st.text_area("Промпт (Чаты/Вопросы):", value="Отвечай конкретно.", height=60)
    signature = st.text_input("Подпись:", value="С уважением, представитель бренда")
    
    st.divider()
    auto_mode = st.toggle("⚡ АВТО-РЕЖИМ", value=False)
    st.markdown("---")
    if st.button("🗑️ Сброс кэша"):
        st.session_state.clear()
        st.rerun()

if not wb_token or not groq_key:
    st.warning("Введите ключи.")
    st.stop()

st.title("🛍️ WB AI Master v18")

# Инициализация состояний
if 'chats' not in st.session_state: st.session_state['chats'] = []
if 'feedbacks' not in st.session_state: st.session_state['feedbacks'] = []
if 'questions' not in st.session_state: st.session_state['questions'] = []
if 'history' not in st.session_state: st.session_state['history'] = []

# Кнопка глобального обновления
if st.button("🔄 Обновить ВСЕ данные", type="primary"):
    with st.spinner("Загрузка данных с WB..."):
        st.session_state['chats'] = get_wb_data(wb_token, "chats")
        st.session_state['feedbacks'] = get_wb_data(wb_token, "feedbacks")
        st.session_state['questions'] = get_wb_data(wb_token, "questions")
        # Историю грузим отдельно по кнопке, чтобы не тормозить

# Счетчики
c_chat = len(st.session_state['chats'])
c_rev = len(st.session_state['feedbacks'])
c_quest = len(st.session_state['questions'])

tab1, tab2, tab3, tab4 = st.tabs([
    f"💬 Чаты ({c_chat})", 
    f"⭐ Отзывы ({c_rev})", 
    f"❓ Вопросы ({c_quest})", 
    "🗄️ Архив"
])

# === ЧАТЫ ===
with tab1:
    chats = st.session_state['chats']
    if not chats:
        st.info("Чатов нет или ошибка доступа (проверьте токен).")
    else:
        for chat in chats:
            client = chat.get('client', {}).get('name', 'Покупатель')
            msg = chat.get('lastMessage', {}).get('text', '')
            is_me = chat.get('lastMessage', {}).get('sender') == 'seller'
            
            with st.container():
                st.markdown(f"**{client}** (ID: {chat['id'][:6]}...)")
                if is_me:
                    st.caption(f"Вы: {msg}")
                else:
                    st.info(f"Клиент: {msg}")
                    
                    k = f"chat_{chat['id']}"
                    if st.button("✨ Ответ", key=f"b_{k}"):
                        ans = generate_ai(groq_key, msg, "Чат", client, prompt_chat, signature)
                        st.session_state[k] = ans
                        st.rerun()
                        
                    val = st.session_state.get(k, "")
                    txt = st.text_area("Текст:", value=val, key=f"t_{k}", height=100)
                    
                    if st.button("Отправить", key=f"s_{k}"):
                        res = send_wb(chat['id'], txt, wb_token, "chats")
                        if res == "OK":
                            st.success("Ушло!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(res)
            st.divider()

# === ОТЗЫВЫ ===
with tab2:
    for rev in st.session_state['feedbacks']:
        with st.container(border=True):
            prod = rev.get('productDetails', {}).get('productName', 'Товар')
            st.markdown(f"**{prod}** {'⭐'*rev['productValuation']}")
            st.write(rev.get('text', ''))
            
            k = f"rev_{rev['id']}"
            if st.button("✨ Сгенерировать", key=f"b_{k}"):
                ans = generate_ai(groq_key, rev.get('text',''), prod, rev.get('userName',''), prompt_rev, signature)
                st.session_state[k] = ans
                st.rerun()
            
            txt = st.text_area("Ответ:", key=k) # Прямая привязка
            if st.button("Отправить", key=f"s_{k}"):
                if send_wb(rev['id'], txt, wb_token, "feedbacks") == "OK":
                    st.success("Готово!")
                    st.session_state['feedbacks'] = [x for x in st.session_state['feedbacks'] if x['id'] != rev['id']]
                    st.rerun()
                else:
                    st.error("Ошибка")

# === ВОПРОСЫ ===
with tab3:
    for q in st.session_state['questions']:
        with st.container(border=True):
            prod = q.get('productDetails', {}).get('productName', 'Товар')
            st.markdown(f"❓ **{prod}**")
            st.write(q.get('text', ''))
            
            k = f"qst_{q['id']}"
            if st.button("✨ Сгенерировать", key=f"b_{k}"):
                ans = generate_ai(groq_key, q.get('text',''), prod, "Покупатель", prompt_chat, signature)
                st.session_state[k] = ans
                st.rerun()
            
            txt = st.text_area("Ответ:", key=k)
            if st.button("Отправить", key=f"s_{k}"):
                if send_wb(q['id'], txt, wb_token, "questions") == "OK":
                    st.success("Готово!")
                    st.session_state['questions'] = [x for x in st.session_state['questions'] if x['id'] != q['id']]
                    st.rerun()
                else:
                    st.error("Ошибка")

# === АРХИВ ===
with tab4:
    if st.button("📥 Загрузить Архив (Отзывы)"):
        with st.spinner("Грузим..."):
            st.session_state['history'] = get_wb_data(wb_token, "feedbacks", True)
            
    if not st.session_state['history']:
        st.write("Архив пуст или не загружен")
    else:
        for item in st.session_state['history']:
            with st.container(border=True):
                st.caption(format_date(item['createdDate']))
                st.write(f"👤 {item.get('text', '')}")
                if item.get('answer'):
                    st.info(item['answer']['text'])

# === АВТО-РЕЖИМ ===
if auto_mode:
    st.info("Авто-режим включен...")
    
    # Чаты
    chats = get_wb_data(wb_token, "chats")
    for chat in chats:
        msg = chat.get('lastMessage', {})
        if msg.get('sender') != 'seller': # Если последнее не от нас
            txt = msg.get('text','')
            ans = generate_ai(groq_key, txt, "Чат", "Покупатель", prompt_chat, signature)
            if "ОШИБКА" not in ans:
                send_wb(chat['id'], ans, wb_token, "chats")
                st.toast("Ответил в чат")
            time.sleep(2)

    # Вопросы
    qs = get_wb_data(wb_token, "questions")
    for q in qs:
        prod = q.get('productDetails', {}).get('productName', 'Товар')
        ans = generate_ai(groq_key, q.get('text',''), prod, "Покупатель", prompt_chat, signature)
        if "ОШИБКА" not in ans:
            if send_wb(q['id'], ans, wb_token, "questions") == "OK":
                st.toast("Закрыл вопрос")
        time.sleep(2)

    # Отзывы
    rs = get_wb_data(wb_token, "feedbacks")
    for r in rs:
        prod = r.get('productDetails', {}).get('productName', 'Товар')
        ans = generate_ai(groq_key, r.get('text',''), prod, "Клиент", prompt_rev, signature)
        if "ОШИБКА" not in ans and len(ans) > 5:
            if send_wb(r['id'], ans, wb_token, "feedbacks") == "OK":
                st.toast("Закрыл отзыв")
        time.sleep(2)
    
    st.success("Цикл завершен. Пауза 60 сек.")
    time.sleep(60)
    st.rerun()
