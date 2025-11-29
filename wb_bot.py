import streamlit as st
import requests
import time
import datetime
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Gemini WB Bot", layout="wide")

# --- ИНИЦИАЛИЗАЦИЯ (SESSION STATE) ---
if 'history' not in st.session_state:
    st.session_state['history'] = []
if 'reviews' not in st.session_state:
    st.session_state['reviews'] = []
if 'generated_answers' not in st.session_state:
    st.session_state['generated_answers'] = {}

# --- ФУНКЦИИ ---
def get_unanswered_reviews(wb_token):
    if not wb_token: return []
    url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
    headers = {"Authorization": wb_token}
    params = {"isAnswered": "false", "take": 20, "skip": 0, "order": "dateDesc"}
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()['data']['feedbacks']
        return []
    except:
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

def generate_ai_response(api_key, review_text, rating, product_name, brand_signature):
    if not api_key: return "Ошибка: Нет ключа"
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        if rating >= 4:
            sentiment = "позитивный"
            goal = "поблагодарить."
        else:
            sentiment = "вежливый, извиняющийся"
            goal = "решить проблему."

        prompt = f"""
        Роль: Поддержка бренда.
        Товар: {product_name}
        Отзыв: "{review_text}" ({rating} звезд).
        Напиши ответ ({sentiment}, {goal}).
        В конце подпись: "{brand_signature}".
        Длина: 2-3 предложения.
        """
        
        safety = {HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE, 
                  HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE}
        
        response = model.generate_content(prompt, safety_settings=safety)
        return response.text
    except Exception as e:
        return f"Ошибка: {e}"

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
st.title("🤖 WB AI Reviews (Gemini)")

with st.sidebar:
    st.header("Настройки")
    
    # Загрузка ключей
    if hasattr(st, 'secrets') and 'GEMINI_API_KEY' in st.secrets:
        gemini_key = st.secrets["GEMINI_API_KEY"]
        wb_token = st.secrets.get("WB_API_TOKEN", "")
        if not wb_token: wb_token = st.text_input("WB Token", type="password")
        st.success("Gemini ключ найден в Secrets")
    else:
        wb_token = st.text_input("WB Token", type="password")
        gemini_key = st.text_input("Gemini Key", type="password")
        
    brand_sign = st.text_input("Подпись", value="С уважением, представитель бренда")
    
    st.divider()
    auto_mode = st.toggle("⚡ АВТО-РЕЖИМ", value=False)

if not wb_token or not gemini_key:
    st.warning("Введите ключи слева.")
    st.stop()

# Логика Авто-режима (вынесена из Tabs для стабильности)
if auto_mode:
    st.info("🔄 Авто-режим включен. Проверка отзывов...")
    status_box = st.empty()
    
    reviews = get_unanswered_reviews(wb_token)
    if reviews:
        for review in reviews:
            prod = review.get('productDetails', {}).get('productName', 'Товар')
            status_box.write(f"⏳ Обрабатываю: {prod}...")
            
            ans = generate_ai_response(gemini_key, review.get('text', ''), review['productValuation'], prod, brand_sign)
            
            if ans and "Ошибка" not in ans:
                if send_reply_to_wb(review['id'], ans, wb_token):
                    add_to_history(prod, review.get('text', ''), ans, review['productValuation'])
                    st.toast(f"✅ Ответил: {prod}")
                else:
                    st.error("Ошибка отправки WB")
            time.sleep(4) # Задержка
        
        status_box.success("Все отзывы обработаны! Жду 60 сек...")
        time.sleep(60)
        st.rerun()
    else:
        status_box.info("Новых отзывов нет. Жду 60 сек...")
        time.sleep(60)
        st.rerun()

else:
    # Ручной режим внутри вкладок
    tab1, tab2 = st.tabs(["Новые", "История"])
    
    with tab1:
        if st.button("Обновить список"):
            st.session_state['reviews'] = get_unanswered_reviews(wb_token)
            
        reviews = st.session_state['reviews']
        if not reviews:
            st.write("Нет загруженных отзывов.")
        else:
            for review in reviews:
                r_id = review['id']
                prod = review['productDetails']['productName']
                rating = review['productValuation']
                
                with st.expander(f"{'⭐'*rating} {prod}", expanded=True):
                    st.write(review.get('text', ''))
                    
                    if st.button("✨ Генерировать", key=f"g_{r_id}"):
                        ans = generate_ai_response(gemini_key, review.get('text', ''), rating, prod, brand_sign)
                        st.session_state['generated_answers'][r_id] = ans
                    
                    val = st.session_state['generated_answers'].get(r_id, "")
                    if val:
                        final = st.text_area("Ответ", val, key=f"t_{r_id}")
                        if st.button("Отправить", key=f"s_{r_id}"):
                            if send_reply_to_wb(r_id, final, wb_token):
                                st.success("Ушло!")
                                add_to_history(prod, review.get('text', ''), final, rating)
                                st.session_state['reviews'] = [r for r in st.session_state['reviews'] if r['id'] != r_id]
                                time.sleep(1)
                                st.rerun()

    with tab2:
        for item in st.session_state['history']:
            st.text(f"{item['time']} | {item['product']}")
            st.caption(item['answer'])
            st.divider()
