import streamlit as st
import requests
import time
from openai import OpenAI

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="AI WB Auto-Reply", layout="wide")

# --- ФУНКЦИИ ВАЛИДАЦИИ И РАБОТЫ ---

def validate_keys(wb_token, openai_key):
    """Проверяет работоспособность ключей"""
    errors = []
    
    # 1. Проверка WB
    try:
        url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
        headers = {"Authorization": wb_token}
        params = {"isAnswered": "false", "take": 1, "skip": 0}
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 401:
            errors.append("❌ WB Token неверный (Ошибка 401)")
        elif resp.status_code != 200:
            errors.append(f"❌ Ошибка WB API: {resp.status_code}")
    except Exception as e:
        errors.append(f"❌ Ошибка соединения с WB: {e}")

    # 2. Проверка OpenAI
    try:
        client = OpenAI(api_key=openai_key)
        # Делаем дешевый запрос к списку моделей для проверки ключа
        client.models.list()
    except Exception as e:
        errors.append("❌ OpenAI Key неверный или закончился баланс")

    return errors

def get_unanswered_reviews(wb_token):
    url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
    headers = {"Authorization": wb_token}
    params = {"isAnswered": "false", "take": 20, "skip": 0}
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
    res = requests.patch(url, headers=headers, json=payload)
    return res.status_code == 200

def generate_ai_response(client, review_text, rating, product_name):
    if rating >= 4:
        sentiment = "положительный, благодарный"
        goal = "поблагодарить за покупку, пригласить снова."
    else:
        sentiment = "вежливый, извиняющийся, профессиональный"
        goal = "снять негатив, предложить написать в поддержку."

    prompt = f"""
    Товар: {product_name}
    Отзыв: "{review_text}"
    Оценка: {rating} звезд.
    Напиши ответ в тоне: {sentiment}. Цель: {goal}.
    Длина: 2-3 предложения. Без воды.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return None

# --- ИНТЕРФЕЙС ---

st.title("🤖 WB AI Reviews Manager")

# === БОКОВАЯ ПАНЕЛЬ (НАСТРОЙКИ) ===
with st.sidebar:
    st.header("⚙️ Настройки")
    
    # Получаем ключи из Secrets или полей ввода
    if hasattr(st, 'secrets') and 'WB_API_TOKEN' in st.secrets:
        wb_token = st.secrets["WB_API_TOKEN"]
        openai_key = st.secrets["OPENAI_API_KEY"]
        st.success("Ключи загружены из облака ☁️")
    else:
        wb_token = st.text_input("WB API Token", type="password")
        openai_key = st.text_input("OpenAI API Key", type="password")

    # Кнопка проверки ключей
    if st.button("✅ Проверить ключи"):
        if not wb_token or not openai_key:
            st.error("Введите оба ключа!")
        else:
            errors = validate_keys(wb_token, openai_key)
            if errors:
                for err in errors:
                    st.error(err)
            else:
                st.success("Все ключи работают! 🚀")
                st.session_state['keys_valid'] = True

    st.divider()
    
    # Переключатель Авто-режима
    auto_mode = st.toggle("⚡ АВТОМАТИЧЕСКИЙ РЕЖИМ", value=False)
    if auto_mode:
        st.warning("Бот будет отвечать на отзывы каждые 60 секунд.")

# === ОСНОВНАЯ ЛОГИКА ===

if not wb_token or not openai_key:
    st.info("👈 Введите ключи в меню слева для начала работы.")
    st.stop()

client = OpenAI(api_key=openai_key)

# ЛОГИКА АВТОМАТИЧЕСКОГО РЕЖИМА
if auto_mode:
    status_placeholder = st.empty()
    log_placeholder = st.empty()
    
    status_placeholder.info("⏳ Запуск цикла проверки...")
    
    reviews = get_unanswered_reviews(wb_token)
    
    if not reviews:
        status_placeholder.success("🎉 Нет новых отзывов. Ожидание...")
        time.sleep(60) # Ждем 1 минуту перед повтором
        st.rerun()
    else:
        logs = []
        progress_bar = st.progress(0)
        
        for i, review in enumerate(reviews):
            prod_name = review.get('productDetails', {}).get('productName', 'Товар')
            rating = review.get('productValuation', 0)
            text = review.get('text', '')
            
            status_placeholder.warning(f"Обрабатываю отзыв {i+1}/{len(reviews)}: {prod_name}")
            
            # 1. Генерация
            answer = generate_ai_response(client, text, rating, prod_name)
            if answer:
                # 2. Отправка
                if send_reply_to_wb(review['id'], answer, wb_token):
                    logs.append(f"✅ Ответил на: {prod_name} ({rating}⭐)")
                else:
                    logs.append(f"❌ Ошибка отправки: {prod_name}")
            else:
                logs.append(f"⚠️ Ошибка генерации: {prod_name}")
            
            # Обновляем лог на экране
            log_placeholder.code("\n".join(logs))
            progress_bar.progress((i + 1) / len(reviews))
            
            # Важная задержка, чтобы WB не забанил за скорость
            time.sleep(5) 
        
        status_placeholder.success("Цикл завершен! Жду 5 минут перед следующей проверкой...")
        time.sleep(300) # 5 минут ожидания
        st.rerun()

# ЛОГИКА РУЧНОГО РЕЖИМА (если авто выключен)
else:
    if st.button("🔄 Обновить список отзывов"):
        st.session_state['reviews'] = get_unanswered_reviews(wb_token)

    if 'reviews' not in st.session_state:
        st.session_state['reviews'] = []
    
    reviews = st.session_state['reviews']

    if not reviews:
        st.info("Нет загруженных отзывов. Нажмите кнопку обновить.")
    else:
        st.write(f"Найдено отзывов: {len(reviews)}")
        for review in reviews:
            with st.expander(f"{'⭐'*review['productValuation']} | {review['productDetails']['productName']}", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.caption("Отзыв:")
                    st.text(review.get('text', 'Без текста'))
                with col2:
                    gen_key = f"gen_{review['id']}"
                    if st.button("🪄 Генерировать", key=f"btn_{review['id']}"):
                        ans = generate_ai_response(client, review.get('text', ''), review['productValuation'], review['productDetails']['productName'])
                        st.session_state[gen_key] = ans
                        st.rerun()
                    
                    if gen_key in st.session_state:
                        final = st.text_area("Ответ:", st.session_state[gen_key], key=f"txt_{review['id']}")
                        if st.button("🚀 Отправить", key=f"snd_{review['id']}"):
                            if send_reply_to_wb(review['id'], final, wb_token):
                                st.success("Отправлено!")
                                time.sleep(1)
                                st.rerun()
