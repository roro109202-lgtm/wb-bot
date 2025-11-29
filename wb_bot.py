import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# --- 1. НАСТРОЙКИ СТРАНИЦЫ И СТИЛИ ---
st.set_page_config(page_title="WB AI Center", layout="wide", page_icon="🛍️")

# CSS чтобы было красиво, как на WB
st.markdown("""
    <style>
    .wb-card {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        margin-bottom: 15px;
    }
    .wb-reply {
        background-color: #f6f6f9; /* Серый фон как на WB */
        padding: 15px;
        border-radius: 8px;
        margin-top: 10px;
        color: #333;
        font-size: 15px;
    }
    .wb-client-text {
        font-size: 16px;
        margin-bottom: 10px;
        font-weight: 500;
    }
    .stTextArea textarea {font-size: 16px !important;}
    </style>
""", unsafe_allow_html=True)

# --- 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def format_date(iso_date):
    """Превращает дату из '2025-11-29T10:00:00Z' в '29.11.2025 10:00'"""
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
        # ИСПРАВЛЕНИЕ: Вопросы теперь живут на том же домене, что и отзывы
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

def generate_ai(api_key, text, item_name, instructions, signature):
    if not api_key: return "Ошибка: Нет ключа Groq"
    
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    prompt = f"""
    Ты менеджер Wildberries.
    Товар: {item_name}
    Сообщение клиента: "{text}"
    
    Твоя инструкция: {instructions}
    
    ВАЖНО ПО ФОРМАТИРОВАНИЮ:
    1. Ответ должен быть на русском.
    2. Обязательно разделяй абзацы двойным переносом строки (пустая строка между абзацами).
    3. Приветствие - отдельно. Основная часть - отдельно. Подпись - отдельно.
    4. Подпись в конце: "{signature}".
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

st.title("🛍️ WB AI Center")

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
                with col1:
                    st.write("**Клиент:**")
                    st.info(rev.get('text', 'Без текста'))
                    if rev.get('photoLinks'):
                        st.image(rev['photoLinks'][0]['fullSize'], width=100)
                with col2:
                    gen_key = f"gen_rev_{rev['id']}"
                    if st.button("✨ Генерировать", key=f"btn_{rev['id']}"):
                        ans = generate_ai(groq_key, rev.get('text', ''), rev['productDetails']['productName'], custom_prompt, signature)
                        st.session_state[gen_key] = ans
                    
                    final_text = st.text_area("Ответ:", value=st.session_state.get(gen_key, ""), height=150, key=f"txt_{rev['id']}")
                    
                    if st.button("🚀 Отправить", key=f"snd_{rev['id']}"):
                        if send_wb(rev['id'], final_text, wb_token, "feedbacks") == "OK":
                            st.success("Отправлено!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Ошибка отправки")

# === ВОПРОСЫ ===
with tab_questions:
    if st.button("🔄 Обновить вопросы"):
        # Теперь адрес правильный, должно работать
        st.session_state['questions'] = get_wb_data(wb_token, "questions", False)
        
    questions = st.session_state.get('questions', [])
    if not questions:
        st.info("Нет новых вопросов.")
    else:
        st.success(f"Вопросов: {len(questions)}")
        for quest in questions:
            with st.expander(f"❓ {quest['productDetails']['productName']}", expanded=True):
                st.write(f"**Вопрос клиента:** {quest['text']}")
                st.caption(f"Дата: {format_date(quest['createdDate'])}")
                
                gen_key = f"gen_qst_{quest['id']}"
                if st.button("✨ Придумать ответ", key=f"btn_q_{quest['id']}"):
                    q_prompt = custom_prompt + " Это ВОПРОС о товаре. Ответь конкретно и помоги клиенту."
                    ans = generate_ai(groq_key, quest['text'], quest['productDetails']['productName'], q_prompt, signature)
                    st.session_state[gen_key] = ans
                
                final_text = st.text_area("Ответ:", value=st.session_state.get(gen_key, ""), height=150, key=f"txt_q_{quest['id']}")
                
                if st.button("🚀 Отправить", key=f"snd_q_{quest['id']}"):
                    if send_wb(quest['id'], final_text, wb_token, "questions") == "OK":
                        st.success("Отправлено!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Ошибка отправки")

# === АРХИВ (ИСТОРИЯ) - КРАСИВЫЙ ДИЗАЙН ===
with tab_history:
    if st.button("📥 Скачать историю с WB"):
        with st.spinner("Загружаю..."):
            st.session_state['history_data'] = get_wb_data(wb_token, "feedbacks", True)
    
    hist = st.session_state.get('history_data', [])
    if hist:
        for item in hist:
            # HTML КАРТОЧКА
            product_name = item['productDetails']['productName']
            stars = "⭐" * item['productValuation']
            date_str = format_date(item['createdDate'])
            client_text = item.get('text', '')
            
            # Достаем фото, если есть
            img_html = ""
            if item.get('photoLinks'):
                img_url = item['photoLinks'][0]['smallSize'] # Берем маленькую картинку
                img_html = f'<img src="{img_url}" style="width: 80px; border-radius: 5px; margin-right: 15px;">'
            
            # Достаем ответ
            reply_text = "Ответ не загрузился"
            if item.get('answer'):
                reply_text = item['answer']['text']
                # Превращаем переносы строк в HTML <br>
                reply_text = reply_text.replace('\n', '<br>')

            # Рендерим красивый блок
            st.markdown(f"""
            <div class="wb-card">
                <div style="display: flex; align-items: flex-start;">
                    {img_html}
                    <div style="width: 100%;">
                        <div style="font-weight: bold; font-size: 14px; color: #888;">{date_str}</div>
                        <div style="font-size: 16px; font-weight: bold; margin-bottom: 5px;">{product_name} <span style="color: #ffaa00;">{stars}</span></div>
                        <div class="wb-client-text">{client_text}</div>
                        <div class="wb-reply">
                            <b>Представитель бренда:</b><br>
                            {reply_text}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    else:
        st.info("Нажмите кнопку выше, чтобы загрузить архив.")

# === АВТО-РЕЖИМ ===
if auto_mode:
    status = st.empty()
    # 1. Отзывы
    reviews = get_wb_data(wb_token, "feedbacks", False)
    for rev in reviews:
        status.warning(f"Отзыв: {rev['productDetails']['productName']}")
        ans = generate_ai(groq_key, rev.get('text', ''), rev['productDetails']['productName'], custom_prompt, signature)
        if ans and "Ошибка" not in ans:
            if send_wb(rev['id'], ans, wb_token, "feedbacks") == "OK":
                st.toast(f"✅ Отзыв готов")
        time.sleep(3)
        
    # 2. Вопросы
    questions = get_wb_data(wb_token, "questions", False)
    for quest in questions:
        status.warning(f"Вопрос: {quest['productDetails']['productName']}")
        q_prompt = custom_prompt + " Это вопрос. Ответь полезно."
        ans = generate_ai(groq_key, quest['text'], quest['productDetails']['productName'], q_prompt, signature)
        if ans and "Ошибка" not in ans:
            if send_wb(quest['id'], ans, wb_token, "questions") == "OK":
                st.toast(f"✅ Вопрос готов")
        time.sleep(3)
    
    status.success("Цикл завершен. Жду 60 сек...")
    time.sleep(60)
    st.rerun()
