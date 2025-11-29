import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="WB AI Manager", layout="wide", page_icon="🛍️")

# Стиль для областей текста
st.markdown("""
    <style>
    .stTextArea textarea {font-size: 16px !important;}
    div[data-testid="stExpander"] div[role="button"] p {font-size: 16px; font-weight: 500;}
    </style>
""", unsafe_allow_html=True)

# --- 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def format_date(iso_date):
    """Превращает дату в человеческий вид"""
    try:
        dt = datetime.datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return iso_date

# --- 3. ФУНКЦИИ API WILDBERRIES ---

def get_wb_data(wb_token, mode="feedbacks", is_answered=False):
    if len(wb_token) < 10: return []
    
    headers = {"Authorization": wb_token}
    params = {
        "isAnswered": str(is_answered).lower(),
        "take": 30,
        "skip": 0,
        "order": "dateDesc"
    }
    
    try:
        # Единый адрес для API (WB обновили документацию)
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
            key = 'feedbacks'
        else: # questions
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions" 
            key = 'questions'
            
        res = requests.get(url, headers=headers, params=params, timeout=10)
        
        if res.status_code == 200:
            return res.json()['data'][key]
        return []
    except Exception as e:
        st.error(f"Ошибка соединения (WB): {e}")
        return []

def send_wb(review_id, text, wb_token, mode="feedbacks"):
    headers = {"Authorization": wb_token}
    
    if not text or len(text) < 2:
        return "Текст пустой!"

    try:
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
            payload = {"id": review_id, "text": text}
        else: # questions
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions/answer"
            payload = {"id": review_id, "answer": {"text": text}}

        res = requests.patch(url, headers=headers, json=payload)

        if res.status_code == 200:
            return "OK"
        else:
            return f"Ошибка WB {res.status_code}: {res.text}"
    except Exception as e:
        return f"Сбой сети: {e}"

# --- 4. НЕЙРОСЕТЬ (GROQ) ---

def generate_ai(api_key, text, item_name, user_name, instructions, signature):
    if not api_key: return "Ошибка: Нет ключа Groq"
    
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    # Формируем приветствие
    greeting_instruction = ""
    if user_name and user_name.lower() != "клиент" and len(user_name) > 1:
        greeting_instruction = f"ОБЯЗАТЕЛЬНО начни ответ с приветствия по имени: 'Здравствуйте, {user_name}!'."
    else:
        greeting_instruction = "Начни с 'Здравствуйте!'."

    prompt = f"""
    Ты менеджер поддержки на Wildberries.
    Товар: {item_name}
    Сообщение от клиента ({user_name}): "{text}"
    
    Твоя инструкция: {instructions}
    
    СТРОГИЕ ПРАВИЛА:
    1. {greeting_instruction}
    2. Ответ должен быть на русском языке.
    3. Разделяй абзацы пустой строкой.
    4. В конце подпись: "{signature}".
    """
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=600
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка AI: {e}"

# --- 5. ИНТЕРФЕЙС ---

with st.sidebar:
    st.title("⚙️ Настройки")
    
    # Кэш ключей
    if 'wb_key' not in st.session_state: st.session_state['wb_key'] = ""
    if 'groq_key' not in st.session_state: st.session_state['groq_key'] = ""
    
    if hasattr(st, 'secrets'):
        st.session_state['wb_key'] = st.secrets.get('WB_API_TOKEN', st.session_state['wb_key'])
        st.session_state['groq_key'] = st.secrets.get('GROQ_API_KEY', st.session_state['groq_key'])

    wb_token = st.text_input("WB Token", value=st.session_state['wb_key'], type="password")
    groq_key = st.text_input("Groq Key", value=st.session_state['groq_key'], type="password")
    
    st.divider()
    custom_prompt = st.text_area("Инструкция:", value="Отвечай вежливо, благодари за выбор.", height=80)
    signature = st.text_input("Подпись:", value="С уважением, представитель бренда")
    
    st.divider()
    auto_mode = st.toggle("⚡ АВТО-РЕЖИМ", value=False)
    if auto_mode:
        st.info("Бот работает с отзывами и вопросами.")

if not wb_token or not groq_key:
    st.warning("Введите ключи.")
    st.stop()

st.title("🛍️ WB AI Manager")

tab_reviews, tab_questions, tab_history = st.tabs(["⭐ Отзывы", "❓ Вопросы", "🗄️ Архив (История)"])

# === ОТЗЫВЫ ===
with tab_reviews:
    if st.button("🔄 Обновить отзывы"):
        st.session_state['feedbacks'] = get_wb_data(wb_token, "feedbacks", False)
    
    reviews = st.session_state.get('feedbacks', [])
    if not reviews:
        st.info("Нет новых отзывов.")
    else:
        for rev in reviews:
            with st.expander(f"{'⭐'*rev['productValuation']} | {rev['productDetails']['productName']}", expanded=True):
                col1, col2 = st.columns([1, 2])
                
                # Данные отзыва
                user_name = rev.get('userName', 'Клиент')
                text = rev.get('text', '')
                
                with col1:
                    st.write(f"👤 **{user_name}**")
                    st.info(text if text else "Без текста")
                    if rev.get('photoLinks'):
                        st.image(rev['photoLinks'][0]['fullSize'], width=100)
                
                with col2:
                    gen_key = f"gen_rev_{rev['id']}"
                    
                    # КНОПКА ГЕНЕРАЦИИ
                    if st.button("✨ Генерировать", key=f"btn_{rev['id']}"):
                        with st.spinner("Думаю..."):
                            ans = generate_ai(groq_key, text, rev['productDetails']['productName'], user_name, custom_prompt, signature)
                            st.session_state[gen_key] = ans
                            st.rerun() # ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ
                    
                    # ПОЛЕ ВВОДА (Берет значение из session_state)
                    val = st.session_state.get(gen_key, "")
                    final_text = st.text_area("Ответ:", value=val, height=200, key=f"txt_{rev['id']}")
                    
                    if st.button("🚀 Отправить", key=f"snd_{rev['id']}"):
                        if send_wb(rev['id'], final_text, wb_token, "feedbacks") == "OK":
                            st.success("Отправлено!")
                            # Удаляем из списка визуально
                            st.session_state['feedbacks'] = [r for r in st.session_state['feedbacks'] if r['id'] != rev['id']]
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Ошибка отправки")

# === ВОПРОСЫ ===
with tab_questions:
    if st.button("🔄 Обновить вопросы"):
        st.session_state['questions'] = get_wb_data(wb_token, "questions", False)
        
    questions = st.session_state.get('questions', [])
    if not questions:
        st.info("Нет новых вопросов.")
    else:
        st.success(f"Вопросов: {len(questions)}")
        for quest in questions:
            # Данные вопроса (тут структура может отличаться, берем аккуратно)
            user_name = "Клиент" # В вопросах часто нет имени в явном виде в этом API
            text = quest.get('text', '')
            
            with st.expander(f"❓ {quest['productDetails']['productName']}", expanded=True):
                st.write(f"**Вопрос:** {text}")
                st.caption(f"Дата: {format_date(quest['createdDate'])}")
                
                gen_key = f"gen_qst_{quest['id']}"
                
                if st.button("✨ Придумать ответ", key=f"btn_q_{quest['id']}"):
                    with st.spinner("Генерирую..."):
                        q_prompt = custom_prompt + " Это ВОПРОС о товаре. Ответь конкретно."
                        ans = generate_ai(groq_key, text, quest['productDetails']['productName'], user_name, q_prompt, signature)
                        st.session_state[gen_key] = ans
                        st.rerun() # ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ
                
                val = st.session_state.get(gen_key, "")
                final_text = st.text_area("Ответ:", value=val, height=150, key=f"txt_q_{quest['id']}")
                
                if st.button("🚀 Отправить", key=f"snd_q_{quest['id']}"):
                    if send_wb(quest['id'], final_text, wb_token, "questions") == "OK":
                        st.success("Отправлено!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Ошибка отправки")

# === АРХИВ (ИСТОРИЯ) - ИСПРАВЛЕННЫЙ ===
with tab_history:
    if st.button("📥 Скачать историю с WB"):
        with st.spinner("Загружаю..."):
            st.session_state['history_data'] = get_wb_data(wb_token, "feedbacks", True)
    
    hist = st.session_state.get('history_data', [])
    if hist:
        for item in hist:
            # Карточка истории (Native Streamlit)
            with st.container(border=True):
                top_col1, top_col2 = st.columns([1, 4])
                
                # Фото
                with top_col1:
                    if item.get('photoLinks'):
                        st.image(item['photoLinks'][0]['smallSize'], use_container_width=True)
                    else:
                        st.write("🖼️ Нет фото")
                
                # Текст
                with top_col2:
                    st.caption(format_date(item['createdDate']))
                    st.markdown(f"**{item['productDetails']['productName']}**")
                    st.write(f"⭐" * item['productValuation'])
                    st.write(f"👤 **{item.get('userName', 'Клиент')}:** {item.get('text', '')}")
                    
                    # Ответ в серой плашке
                    if item.get('answer'):
                        st.info(f"🤖 **Ответ:**\n\n{item['answer']['text']}")
                    else:
                        st.warning("Ответ не загрузился")
    else:
        st.info("Нажмите кнопку выше, чтобы загрузить архив.")

# === АВТО-РЕЖИМ ===
if auto_mode:
    status = st.empty()
    
    # 1. Отзывы
    reviews = get_wb_data(wb_token, "feedbacks", False)
    for rev in reviews:
        user_name = rev.get('userName', 'Клиент')
        status.warning(f"Обрабатываю отзыв от {user_name}...")
        
        ans = generate_ai(groq_key, rev.get('text', ''), rev['productDetails']['productName'], user_name, custom_prompt, signature)
        
        if ans and "Ошибка" not in ans:
            if send_wb(rev['id'], ans, wb_token, "feedbacks") == "OK":
                st.toast(f"✅ Отзыв закрыт: {rev['id']}")
        time.sleep(3)
        
    # 2. Вопросы
    questions = get_wb_data(wb_token, "questions", False)
    for quest in questions:
        status.warning(f"Обрабатываю вопрос...")
        q_prompt = custom_prompt + " Это вопрос. Ответь полезно."
        ans = generate_ai(groq_key, quest['text'], quest['productDetails']['productName'], "Клиент", q_prompt, signature)
        
        if ans and "Ошибка" not in ans:
            if send_wb(quest['id'], ans, wb_token, "questions") == "OK":
                st.toast(f"✅ Вопрос закрыт: {quest['id']}")
        time.sleep(3)
    
    status.success("Цикл завершен. Жду 60 сек...")
    time.sleep(60)
    st.rerun()
