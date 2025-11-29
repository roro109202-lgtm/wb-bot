import streamlit as st
import requests
import time
import datetime
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Gemini WB Auto-Reply", layout="wide")

# --- ИНИЦИАЛИЗАЦИЯ ПЕРЕМЕННЫХ ---
if 'history' not in st.session_state:
    st.session_state['history'] = []
if 'reviews' not in st.session_state:
    st.session_state['reviews'] = []
if 'generated_answers' not in st.session_state:
    st.session_state['generated_answers'] = {}

# --- ФУНКЦИИ WB ---

def get_unanswered_reviews(wb_token):
    url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
    headers = {"Authorization": wb_token}
    params = {"isAnswered": "false", "take": 20, "skip": 0, "order": "dateDesc"}
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()['data']['feedbacks']
        st.error(f"Ошибка WB API: {response.status_code}")
        return []
    except Exception as e:
        st.error(f"Ошибка соединения с WB: {e}")
        return []

def send_reply_to_wb(review_id, text, wb_token):
    url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
    headers = {"Authorization": wb_token}
    payload = {"id": review_id, "text": text}
    try:
        res = requests.patch(url, headers=headers, json=payload)
        return res.status_code == 200
    except:
        return False

# --- ФУНКЦИИ GEMINI ---

def configure_gemini(api_key):
    try:
        genai.configure(api_key=api_key)
        return True
    except:
        return False

def generate_ai_response(api_key, review_text, rating, product_name, brand_signature):
    if not api_key:
        return "Ошибка: Нет ключа Gemini"

    # Настройка модели
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash') # Используем быструю модель Flash

    if rating >= 4:
        sentiment = "положительный, благодарный, теплый"
        goal = "поблагодарить за выбор товара, пожелать приятного пользования."
    else:
        sentiment = "вежливый, эмпатичный, деловой"
        goal = "извиниться за неудобства, показать заботу о клиенте."

    prompt = f"""
    Ты менеджер поддержки.
    Товар: {product_name}
    Отзыв клиента: "{review_text}"
    Оценка: {rating} звезд.
    
    Задача: Напиши ответ на русском языке.
    Тон: {sentiment}. Цель: {goal}.
    Правила:
    1. Не используй шаблоны вроде "Ваш отзыв очень важен для нас". Пиши по-человечески.
    2. Длина: 2-4 предложения.
    3. В конце обязательно добавь подпись: "{brand_signature}"
    """
    
    try:
        # Настройки безопасности (чтобы не блокировал обычные ответы)
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        response = model.generate_content(prompt, safety_settings=safety_settings)
        return response.text
    except Exception as e:
        return f"Ошибка Gemini: {e}"

def add_to_history(product, review_text, answer_text, rating):
    entry = {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "product": product,
        "review": review_text,
        "answer": answer_text,
        "rating": rating
    }
    st.session_state['history'].insert(0, entry)

# --- ИНТЕРФЕЙС ---

st.title("🤖 WB AI Reviews Manager (Gemini Edition)")

# === SIDEBAR ===
with st.sidebar:
    st.header("⚙️ Настройки")
    
    # Ключи
    if hasattr(st, 'secrets') and 'WB_API_TOKEN' in st.secrets:
        wb_token = st.secrets["WB_API_TOKEN"]
        gemini_key = st.secrets["GEMINI_API_KEY"] # Ищем новый ключ
        st.success("🔑 Ключи из облака активны")
    else:
        wb_token = st.text_input("WB API Token", type="password")
        gemini_key = st.text_input("Gemini API Key", type="password")
        
    brand_sign = st.text_input("Подпись в конце", value="С уважением, команда Бренда")
    
    st.divider()
    
    if st.button("✅ Проверить Gemini"):
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content("Привет")
            if response.text:
                st.success("Gemini работает! 🚀")
        except Exception as e:
            st.error(f"Ошибка ключа: {e}")
            
    st.divider()
    auto_mode = st.toggle("⚡ АВТО-РЕЖИМ (Каждую минуту)", value=False)

# === ЛОГИКА ===

if not wb_token or not gemini_key:
    st.warning("Введите API ключи в настройках слева.")
    st.stop()

# ВКЛАДКИ
tab1, tab2 = st.tabs(["📝 Новые отзывы", "📜 История ответов"])

with tab1:
    if auto_mode:
        st.info("Включен авто-режим. Бот работает с Google Gemini. Не закрывайте вкладку.")
        placeholder = st.empty()
        
        reviews = get_unanswered_reviews(wb_token)
        if reviews:
            for review in reviews:
                prod = review.get('productDetails', {}).get('productName', 'Товар')
                placeholder.warning(f"Gemini думает над ответом для: {prod}...")
                
                ans = generate_ai_response(gemini_key, review.get('text', ''), review['productValuation'], prod, brand_sign)
                
                if ans and "Ошибка" not in ans:
                    if send_reply_to_wb(review['id'], ans, wb_token):
                        add_to_history(prod, review.get('text', ''), ans, review['productValuation'])
                        st.toast(f"Отправлено: {prod}")
                    else:
                        st.error(f"Ошибка WB при отправке: {prod}")
                else:
                    st.error(f"Не удалось сгенерировать: {ans}")
                    
                time.sleep(5) 
            
            st.success("Готово! Жду новые отзывы...")
            time.sleep(60)
            st.rerun()
        else:
            placeholder.info("Нет новых отзывов. Жду 60 сек...")
            time.sleep(60)
            st.rerun()

    else:
        # РУЧНОЙ РЕЖИМ
        col_btn, col_stat = st.columns([1, 3])
        if col_btn.button("🔄 Обновить список"):
            with st.spinner("Загружаю с Wildberries..."):
                st.session_state['reviews'] = get_unanswered_reviews(wb_token)
        
        reviews = st.session_state['reviews']
        
        if not reviews:
            st.info("Нет загруженных отзывов.")
        else:
            for review in reviews:
                r_id = review['id']
                prod_name = review['productDetails']['productName']
                rating = review['productValuation']
                text = review.get('text', '')
                
                with st.expander(f"{'⭐'*rating} | {prod_name}", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**Отзыв клиента:**")
                        st.info(text if text else "(Без текста)")
                        st.caption(f"Дата: {review['createdDate']}")

                    with c2:
                        if st.button("✨ Gemini ответ", key=f"gen_btn_{r_id}"):
                            with st.spinner("Gemini пишет..."):
                                ai_ans = generate_ai_response(gemini_key, text, rating, prod_name, brand_sign)
                                st.session_state['generated_answers'][r_id] = ai_ans
                        
                        current_ans = st.session_state['generated_answers'].get(r_id, "")
                        
                        if current_ans:
                            final_text = st.text_area("Текст ответа:", value=current_ans, height=150, key=f"area_{r_id}")
                            if st.button("🚀 Отправить", key=f"send_{r_id}"):
                                if send_reply_to_wb(r_id, final_text, wb_token):
                                    st.success("Отправлено!")
                                    add_to_history(prod_name, text, final_text, rating)
                                    st.session_state['reviews'] = [r for r in st.session_state['reviews'] if r['id'] != r_id]
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Ошибка отправки.")

with tab2:
    if not st.session_state['history']:
        st.write("История пуста.")
    else:
        for item in st.session_state['history']:
            with st.container(border=True):
                h1, h2 = st.columns([1, 4])
                with h1:
                    st.write(item['time'])
                    st.write(f"{'⭐' * item['rating']}")
                with h2:
                    st.markdown(f"**Товар:** {item['product']}")
                    st.markdown(f"**Ответ:** {item['answer']}")
