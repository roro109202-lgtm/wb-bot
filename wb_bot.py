import streamlit as st
import requests
import json
from openai import OpenAI

# --- КОНФИГУРАЦИЯ ---
# Проверяем, есть ли секреты в облаке. Если нет - просим ввести вручную (для локального запуска)
if hasattr(st, 'secrets') and 'WB_API_TOKEN' in st.secrets:
    WB_API_TOKEN = st.secrets["WB_API_TOKEN"]
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
else:
    st.warning("⚠️ Ключи не найдены в настройках. Введите их вручную.")
    WB_API_TOKEN = st.text_input("Введите WB API Token", type="password")
    OPENAI_API_KEY = st.text_input("Введите OpenAI API Key", type="password")

# Инициализация клиента OpenAI (только если ключ есть)
client = None
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)

# --- ФУНКЦИИ WB ---
def get_unanswered_reviews():
    if not WB_API_TOKEN:
        return []
    url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
    headers = {"Authorization": WB_API_TOKEN}
    params = {"isAnswered": "false", "take": 20, "skip": 0}
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()['data']['feedbacks']
        else:
            st.error(f"Ошибка WB API: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"Ошибка соединения: {e}")
        return []

def send_reply_to_wb(review_id, text):
    url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
    headers = {"Authorization": WB_API_TOKEN}
    payload = {"id": review_id, "text": text}
    res = requests.patch(url, headers=headers, json=payload)
    return res.status_code == 200

# --- ФУНКЦИИ ИИ ---
def generate_ai_response(review_text, rating, product_name):
    if not client:
        return "Ошибка: Не введен API ключ OpenAI"
        
    if rating >= 4:
        sentiment = "положительный, благодарный, дружелюбный"
        goal = "поблагодарить за покупку и пригласить купить снова."
    else:
        sentiment = "эмпатичный, профессиональный, извиняющийся"
        goal = "мягко отработать негатив, извиниться за неудобства."

    prompt = f"""
    Ты - менеджер поддержки бренда на Wildberries.
    Напиши ответ на отзыв клиента.
    Товар: {product_name}
    Текст отзыва: "{review_text}"
    Оценка клиента: {rating} звезд.
    Тон: {sentiment}. Цель: {goal}.
    Кратко (3-4 предложения).
    """
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка генерации: {e}"

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="AI WB Auto-Reply", layout="wide")
st.title("🤖 WB AI Reviews Manager")

if 'reviews' not in st.session_state:
    st.session_state['reviews'] = []

# Кнопка обновления
if st.button("🔄 Обновить список отзывов"):
    with st.spinner("Загружаю отзывы..."):
        st.session_state['reviews'] = get_unanswered_reviews()

reviews = st.session_state['reviews']

if not reviews:
    st.info("Нажмите кнопку выше, чтобы загрузить отзывы.")
else:
    for review in reviews:
        product_name = review.get('productDetails', {}).get('productName', 'Товар')
        rating = review.get('productValuation', 0)
        
        with st.expander(f"{'⭐'*rating} | {product_name}", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Отзыв:**")
                st.info(review.get('text', 'Без текста'))
            with col2:
                gen_key = f"gen_{review['id']}"
                if st.button("🪄 Генерировать ответ", key=f"btn_{review['id']}"):
                    ans = generate_ai_response(review.get('text', ''), rating, product_name)
                    st.session_state[gen_key] = ans
                    st.rerun()
                
                if gen_key in st.session_state:
                    final_text = st.text_area("Ответ:", st.session_state[gen_key], key=f"txt_{review['id']}")
                    if st.button("🚀 Отправить", key=f"snd_{review['id']}"):
                        if send_reply_to_wb(review['id'], final_text):
                            st.success("Отправлено!")
                        else:
                            st.error("Ошибка отправки")
