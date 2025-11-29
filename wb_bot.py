import streamlit as st
import requests
import time
import datetime
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- 1. НАСТРОЙКИ СТРАНИЦЫ (Должно быть первой строкой) ---
st.set_page_config(page_title="WB AI Manager", layout="wide")

# --- 2. ИНИЦИАЛИЗАЦИЯ ПАМЯТИ ---
if 'history' not in st.session_state:
    st.session_state['history'] = []
if 'reviews' not in st.session_state:
    st.session_state['reviews'] = []
if 'generated_answers' not in st.session_state:
    st.session_state['generated_answers'] = {}

# --- 3. ФУНКЦИИ ЛОГИКИ ---

def get_wb_reviews(wb_token):
    if len(wb_token) < 10: return []
    url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
    headers = {"Authorization": wb_token}
    params = {"isAnswered": "false", "take": 20, "skip": 0, "order": "dateDesc"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()['data']['feedbacks']
        return []
    except:
        return []

def send_wb_reply(review_id, text, wb_token):
    url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
    headers = {"Authorization": wb_token}
    payload = {"id": review_id, "text": text}
    try:
        res = requests.patch(url, headers=headers, json=payload, timeout=10)
        return res.status_code == 200
    except:
        return False

def generate_gemini(api_key, text, rating, product, signature):
    if not api_key: return "Ошибка: Нет ключа Gemini"
    
    genai.configure(api_key=api_key)
    
    # Пытаемся взять быструю модель, если нет - обычную
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
    except:
        model = genai.GenerativeModel('gemini-pro')

    if rating >= 4:
        tone = "позитивный, благодарный"
        goal = "поблагодарить клиента"
    else:
        tone = "вежливый, извиняющийся"
        goal = "отработать негатив"

    prompt = f"""
    Роль: Поддержка магазина на Wildberries.
    Товар: {product}
    Отзыв: "{text}" ({rating} звезд).
    Напиши ответ ({tone}, {goal}).
    В конце подпись: "{signature}".
    Ответ должен быть кратким (2-3 предложения).
    """
    
    try:
        safe = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE
        }
        response = model.generate_content(prompt, safety_settings=safe)
        return response.text
    except Exception as e:
        return f"Ошибка генерации: {e}"

def add_history(prod, rev, ans, rate):
    st.session_state['history'].insert(0, {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "product": prod, "review": rev, "answer": ans, "rating": rate
    })

# --- 4. ИНТЕРФЕЙС ---

st.title("🤖 WB AI Reviews (Gemini)")

# Сайдбар (Всегда виден)
with st.sidebar:
    st.header("Настройки")
    
    # Попытка достать ключи из Secrets
    my_wb_token = ""
    my_gemini_key = ""
    
    if hasattr(st, 'secrets'):
        if 'WB_API_TOKEN' in st.secrets:
            my_wb_token = st.secrets['WB_API_TOKEN']
        if 'GEMINI_API_KEY' in st.secrets:
            my_gemini_key = st.secrets['GEMINI_API_KEY']
            
    # Если в Secrets пусто, даем поля ввода
    wb_token = st.text_input("WB Token", value=my_wb_token, type="password")
    gemini_key = st.text_input("Gemini Key", value=my_gemini_key, type="password")
    
    brand_sign = st.text_input("Подпись", value="С уважением, команда Бренда")
    st.divider()
    auto_mode = st.toggle("⚡ АВТО-РЕЖИМ", value=False)
    
    if auto_mode:
        st.info("Бот будет проверять отзывы каждую минуту.")

# ПРОВЕРКА КЛЮЧЕЙ (Чтобы не было пустого экрана)
if not wb_token or not gemini_key:
    st.warning("👈 Пожалуйста, введите API ключи в меню слева (или добавьте их в Secrets).")
    st.info("Без ключей программа не может работать.")
    st.stop() # Останавливаем только ПОСЛЕ отрисовки предупреждения

# --- 5. ОСНОВНАЯ ЛОГИКА ---

# Если включен авто-режим
if auto_mode:
    status = st.empty()
    reviews = get_wb_reviews(wb_token)
    
    if not reviews:
        status.success("🎉 Нет новых отзывов. Жду 60 секунд...")
        time.sleep(60)
        st.rerun()
    
    for i, review in enumerate(reviews):
        prod = review.get('productDetails', {}).get('productName', 'Товар')
        text = review.get('text', '')
        rating = review['productValuation']
        
        status.warning(f"🤖 Обрабатываю ({i+1}/{len(reviews)}): {prod}")
        
        # Генерация
        ans = generate_gemini(gemini_key, text, rating, prod, brand_sign)
        
        if ans and "Ошибка" not in ans:
            # Отправка
            if send_wb_reply(review['id'], ans, wb_token):
                add_history(prod, text, ans, rating)
                st.toast(f"Отправлено: {prod}")
            else:
                st.error(f"Сбой отправки WB: {prod}")
        else:
            st.error(f"Сбой генерации: {prod} -> {ans}")
            
        time.sleep(5) # Пауза чтобы не забанили
        
    st.success("Цикл завершен! Перезапуск через минуту...")
    time.sleep(60)
    st.rerun()

# Если ручной режим
else:
    tab1, tab2 = st.tabs(["📝 Новые отзывы", "📜 История"])
    
    with tab1:
        if st.button("🔄 Обновить список отзывов"):
            st.session_state['reviews'] = get_wb_reviews(wb_token)
            
        reviews = st.session_state['reviews']
        
        if not reviews:
            st.info("Нажмите кнопку обновления выше.")
        else:
            for review in reviews:
                rid = review['id']
                prod = review['productDetails']['productName']
                rating = review['productValuation']
                txt = review.get('text', '')
                
                with st.expander(f"{'⭐'*rating} {prod}", expanded=True):
                    st.write(f"**Клиент:** {txt}")
                    
                    # Кнопка генерации
                    if st.button("✨ Генерировать", key=f"g_{rid}"):
                        val = generate_gemini(gemini_key, txt, rating, prod, brand_sign)
                        st.session_state['generated_answers'][rid] = val
                    
                    # Поле ответа
                    val = st.session_state['generated_answers'].get(rid, "")
                    final_txt = st.text_area("Ответ", value=val, key=f"t_{rid}")
                    
                    if st.button("🚀 Отправить", key=f"s_{rid}"):
                        if send_wb_reply(rid, final_txt, wb_token):
                            st.success("Отправлено!")
                            add_history(prod, txt, final_txt, rating)
                            # Удаляем из списка
                            st.session_state['reviews'] = [r for r in st.session_state['reviews'] if r['id'] != rid]
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("Ошибка WB")

    with tab2:
        if not st.session_state['history']:
            st.write("История пуста.")
        for h in st.session_state['history']:
            st.text(f"{h['time']} | {'⭐'*h['rating']} | {h['product']}")
            st.caption(h['answer'])
            st.divider()
