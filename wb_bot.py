import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="WB AI Ultimate", layout="wide", page_icon="🛍️")

# --- 2. CSS СТИЛИ (ДЛЯ КРАСОТЫ) ---
st.markdown("""
    <style>
    .stTextArea textarea {font-size: 16px !important;}
    .reportview-container {background: #f0f2f6;}
    div[data-testid="stExpander"] div[role="button"] p {font-size: 18px; font-weight: bold;}
    </style>
""", unsafe_allow_html=True)

# --- 3. ФУНКЦИИ API WILDBERRIES ---

def get_wb_data(wb_token, mode="feedbacks", is_answered=False):
    """Универсальная функция для получения Отзывов или Вопросов"""
    if len(wb_token) < 10: return []
    
    headers = {"Authorization": wb_token}
    params = {
        "isAnswered": str(is_answered).lower(),
        "take": 30,
        "skip": 0,
        "order": "dateDesc"
    }
    
    try:
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code == 200: return res.json()['data']['feedbacks']
            
        elif mode == "questions":
            # У WB отдельный API для вопросов
            url = "https://questions-api.wildberries.ru/api/v1/questions"
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code == 200: return res.json()['data']['questions']
            
        return []
    except Exception as e:
        st.error(f"Ошибка соединения (WB): {e}")
        return []

def send_wb(review_id, text, wb_token, mode="feedbacks"):
    """Отправка ответа"""
    headers = {"Authorization": wb_token}
    
    # Проверка на пустоту
    if not text or len(text) < 5:
        return "Error: Текст слишком короткий или пустой"

    try:
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
            payload = {"id": review_id, "text": text}
            res = requests.patch(url, headers=headers, json=payload)
        else: # questions
            url = "https://questions-api.wildberries.ru/api/v1/questions/answer"
            payload = {"id": review_id, "answer": {"text": text}} # Структура чуть другая
            res = requests.patch(url, headers=headers, json=payload)

        if res.status_code == 200:
            return "OK"
        else:
            return f"Ошибка WB {res.status_code}: {res.text}"
    except Exception as e:
        return f"Сбой сети: {e}"

# --- 4. ФУНКЦИЯ НЕЙРОСЕТИ (GROQ) ---

def generate_ai(api_key, text, item_name, instructions, signature):
    if not api_key: return "Ошибка: Нет ключа Groq"
    
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    prompt = f"""
    Твоя роль: Опытный менеджер Wildberries.
    Товар: {item_name}
    Сообщение клиента: "{text}"
    
    Твоя инструкция: {instructions}
    
    ВАЖНО:
    1. Используй переносы строк (Enter) между приветствием, основной частью и прощанием.
    2. Ответ должен быть на русском языке.
    3. В конце добавь подпись: "{signature}".
    4. Если это вопрос про товар - ответь на него конкретно. Если отзыв - поблагодари.
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

# --- 5. ИНТЕРФЕЙС ---

# Сайдбар с настройками
with st.sidebar:
    st.title("⚙️ Настройки")
    
    # Ключи (с кэшированием, чтобы не вводить каждый раз)
    if 'wb_key' not in st.session_state: st.session_state['wb_key'] = ""
    if 'groq_key' not in st.session_state: st.session_state['groq_key'] = ""
    
    # Попытка взять из secrets
    if hasattr(st, 'secrets'):
        st.session_state['wb_key'] = st.secrets.get('WB_API_TOKEN', st.session_state['wb_key'])
        st.session_state['groq_key'] = st.secrets.get('GROQ_API_KEY', st.session_state['groq_key'])

    wb_token = st.text_input("WB Token (Стандартный)", value=st.session_state['wb_key'], type="password")
    groq_key = st.text_input("Groq API Key", value=st.session_state['groq_key'], type="password")
    
    st.divider()
    
    st.subheader("🎭 Характер бота")
    custom_prompt = st.text_area("Инструкция для ИИ:", value="Отвечай вежливо, с заботой о клиенте. Благодари за выбор. Используй эмодзи умеренно.", height=100)
    signature = st.text_input("Подпись:", value="С уважением, представитель бренда")
    
    st.divider()
    auto_mode = st.toggle("⚡ АВТО-РЕЖИМ", value=False)
    if auto_mode:
        st.info("Бот обрабатывает и отзывы, и вопросы.")

if not wb_token or not groq_key:
    st.warning("👈 Введите ключи в меню слева, чтобы начать.")
    st.stop()

# Основной экран
st.title("🛍️ WB AI Center")

# Вкладки
tab_reviews, tab_questions, tab_history = st.tabs(["⭐ Отзывы", "❓ Вопросы", "🗄️ Архив (История)"])

# === ЛОГИКА: ОТЗЫВЫ ===
with tab_reviews:
    if st.button("🔄 Обновить отзывы"):
        st.session_state['feedbacks'] = get_wb_data(wb_token, "feedbacks", False)
    
    reviews = st.session_state.get('feedbacks', [])
    
    if not reviews:
        st.info("Нет новых отзывов.")
    else:
        st.success(f"Найдено отзывов: {len(reviews)}")
        for rev in reviews:
            with st.expander(f"{'⭐'*rev['productValuation']} | {rev['productDetails']['productName']}", expanded=True):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.markdown("### Клиент:")
                    st.info(rev.get('text', 'Без текста'))
                    if rev.get('photoLinks'):
                        st.image(rev['photoLinks'][0]['fullSize'], width=100)
                
                with col2:
                    st.markdown("### Ответ:")
                    gen_key = f"gen_rev_{rev['id']}"
                    
                    if st.button("✨ Генерировать", key=f"btn_{rev['id']}"):
                        ans = generate_ai(groq_key, rev.get('text', ''), rev['productDetails']['productName'], custom_prompt, signature)
                        st.session_state[gen_key] = ans
                    
                    # Поле ответа
                    current_ans = st.session_state.get(gen_key, "")
                    final_text = st.text_area("Текст:", value=current_ans, height=200, key=f"txt_{rev['id']}")
                    
                    if st.button("🚀 Отправить", key=f"snd_{rev['id']}"):
                        res = send_wb(rev['id'], final_text, wb_token, "feedbacks")
                        if res == "OK":
                            st.success("Ответ опубликован!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(res)

# === ЛОГИКА: ВОПРОСЫ ===
with tab_questions:
    if st.button("🔄 Обновить вопросы"):
        st.session_state['questions'] = get_wb_data(wb_token, "questions", False)
        
    questions = st.session_state.get('questions', [])
    
    if not questions:
        st.info("Нет новых вопросов.")
    else:
        st.warning(f"Найдено вопросов: {len(questions)}")
        for quest in questions:
            with st.expander(f"❓ {quest['productDetails']['productName']}", expanded=True):
                st.write(f"**Вопрос:** {quest['text']}")
                
                gen_key = f"gen_qst_{quest['id']}"
                if st.button("✨ Придумать ответ", key=f"btn_q_{quest['id']}"):
                    # Для вопросов меняем контекст в инструкции
                    q_prompt = custom_prompt + " Это ВОПРОС покупателя. Дай точный и полезный ответ."
                    ans = generate_ai(groq_key, quest['text'], quest['productDetails']['productName'], q_prompt, signature)
                    st.session_state[gen_key] = ans
                
                current_ans = st.session_state.get(gen_key, "")
                final_text = st.text_area("Текст ответа:", value=current_ans, height=150, key=f"txt_q_{quest['id']}")
                
                if st.button("🚀 Отправить ответ", key=f"snd_q_{quest['id']}"):
                    res = send_wb(quest['id'], final_text, wb_token, "questions")
                    if res == "OK":
                        st.success("Ответ на вопрос отправлен!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(res)

# === ЛОГИКА: АРХИВ (ИСТОРИЯ) ===
with tab_history:
    st.markdown("Здесь загружаются последние отвеченные отзывы прямо с WB.")
    if st.button("📥 Загрузить историю с WB"):
        with st.spinner("Скачиваю архив..."):
            history = get_wb_data(wb_token, "feedbacks", True) # True = отвеченные
            st.session_state['history_data'] = history
    
    hist_data = st.session_state.get('history_data', [])
    if hist_data:
        for item in hist_data:
            with st.container():
                st.markdown(f"**{item['productDetails']['productName']}** ({'⭐'*item['productValuation']})")
                st.info(f"👤 Клиент: {item.get('text', '')}")
                # Пытаемся найти ответ (структура WB может меняться)
                if 'answer' in item and item['answer']:
                     st.success(f"🤖 Ответ: {item['answer']['text']}")
                else:
                     st.warning("Ответ был отправлен, но текст не подгрузился.")
                st.divider()

# === ЛОГИКА: АВТО-РЕЖИМ ===
if auto_mode:
    status = st.empty()
    
    # 1. Проверяем отзывы
    reviews = get_wb_data(wb_token, "feedbacks", False)
    for rev in reviews:
        status.warning(f"Обрабатываю отзыв: {rev['productDetails']['productName']}")
        ans = generate_ai(groq_key, rev.get('text', ''), rev['productDetails']['productName'], custom_prompt, signature)
        if ans and "Ошибка" not in ans:
            if send_wb(rev['id'], ans, wb_token, "feedbacks") == "OK":
                st.toast(f"✅ Отзыв закрыт: {rev['id']}")
        time.sleep(3)
        
    # 2. Проверяем вопросы
    questions = get_wb_data(wb_token, "questions", False)
    for quest in questions:
        status.warning(f"Обрабатываю вопрос: {quest['productDetails']['productName']}")
        q_prompt = custom_prompt + " Это вопрос. Ответь конкретно."
        ans = generate_ai(groq_key, quest['text'], quest['productDetails']['productName'], q_prompt, signature)
        if ans and "Ошибка" not in ans:
            if send_wb(quest['id'], ans, wb_token, "questions") == "OK":
                st.toast(f"✅ Вопрос закрыт: {quest['id']}")
        time.sleep(3)
    
    status.success("Цикл завершен. Жду 60 сек...")
    time.sleep(60)
    st.rerun()
