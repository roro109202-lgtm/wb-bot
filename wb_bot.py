import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="WB DeepSeek Bot", layout="wide")

# --- 2. ПАМЯТЬ ---
if 'history' not in st.session_state: st.session_state['history'] = []
if 'reviews' not in st.session_state: st.session_state['reviews'] = []
if 'generated_answers' not in st.session_state: st.session_state['generated_answers'] = {}

# --- 3. ФУНКЦИИ ---

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

# --- ФУНКЦИИ DEEPSEEK ---
def generate_deepseek(api_key, text, rating, product, signature):
    if not api_key: return "Ошибка: Нет ключа"

    # Подключаемся к DeepSeek через библиотеку OpenAI
    client = OpenAI(
        api_key=api_key, 
        base_url="https://api.deepseek.com"  # Важный адрес!
    )

    if rating >= 4:
        tone = "позитивный, благодарный"
        goal = "поблагодарить клиента"
    else:
        tone = "вежливый, извиняющийся"
        goal = "отработать негатив"

    prompt = f"""
    Роль: Сотрудник поддержки Wildberries.
    Товар: {product}
    Отзыв: "{text}" ({rating} звезд).
    Задача: Напиши ответ ({tone}, {goal}).
    Обязательно добавь подпись: "{signature}".
    Ответ должен быть кратким (2-3 предложения), без лишней воды.
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat", # Используем их основную модель
            messages=[
                {"role": "system", "content": "Ты помощник селлера."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            timeout=15
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка DeepSeek: {e}"

def add_history(prod, rev, ans, rate):
    st.session_state['history'].insert(0, {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "product": prod, "review": rev, "answer": ans, "rating": rate
    })

# --- 4. ИНТЕРФЕЙС ---

st.title("🐳 WB DeepSeek Manager")

with st.sidebar:
    st.header("Настройки")
    
    # Ключи
    my_wb = ""
    my_ds = ""
    if hasattr(st, 'secrets'):
        my_wb = st.secrets.get('WB_API_TOKEN', "")
        # Ищем любой ключ, похожий на дипсик или опенаи
        my_ds = st.secrets.get('DEEPSEEK_API_KEY', st.secrets.get('OPENAI_API_KEY', ""))
            
    wb_token = st.text_input("WB Token", value=my_wb, type="password")
    deepseek_key = st.text_input("DeepSeek Key (sk-...)", value=my_ds, type="password")
    brand_sign = st.text_input("Подпись", value="С уважением, представитель бренда")
    
    st.divider()
    auto_mode = st.toggle("⚡ АВТО-РЕЖИМ", value=False)

if not wb_token or not deepseek_key:
    st.warning("Введите ключи слева.")
    st.stop()

# --- 5. ЛОГИКА ---

if auto_mode:
    status = st.empty()
    reviews = get_wb_reviews(wb_token)
    
    if not reviews:
        status.success("Нет отзывов. Жду...")
        time.sleep(60)
        st.rerun()
    
    for i, review in enumerate(reviews):
        prod = review.get('productDetails', {}).get('productName', 'Товар')
        text = review.get('text', '')
        rating = review['productValuation']
        
        status.warning(f"DeepSeek пишет: {prod}...")
        
        # Генерация
        ans = generate_deepseek(deepseek_key, text, rating, prod, brand_sign)
        
        if ans and "Ошибка" not in ans:
            if send_wb_reply(review['id'], ans, wb_token):
                add_history(prod, text, ans, rating)
                st.toast(f"Отправлено: {prod}")
            else:
                st.error("Ошибка WB")
        else:
            st.error(f"{ans}")
            
        time.sleep(5)
        
    st.success("Готово! Перезапуск...")
    time.sleep(60)
    st.rerun()

else:
    # Ручной режим
    tab1, tab2 = st.tabs(["Новые", "История"])
    with tab1:
        if st.button("Обновить список"):
            st.session_state['reviews'] = get_wb_reviews(wb_token)
        
        reviews = st.session_state['reviews']
        if not reviews:
            st.write("Нет отзывов")
        else:
            for review in reviews:
                rid = review['id']
                prod = review['productDetails']['productName']
                rating = review['productValuation']
                txt = review.get('text', '')
                
                with st.expander(f"{'⭐'*rating} {prod}", expanded=True):
                    st.write(txt)
                    if st.button("✨ DeepSeek Генерировать", key=f"g_{rid}"):
                        ans = generate_deepseek(deepseek_key, txt, rating, prod, brand_sign)
                        st.session_state['generated_answers'][rid] = ans
                    
                    val = st.session_state['generated_answers'].get(rid, "")
                    final = st.text_area("Ответ", val, key=f"t_{rid}")
                    
                    if st.button("Отправить", key=f"s_{rid}"):
                        if send_wb_reply(rid, final, wb_token):
                            st.success("Ушло!")
                            add_history(prod, txt, final, rating)
                            st.session_state['reviews'] = [r for r in st.session_state['reviews'] if r['id'] != rid]
                            time.sleep(1)
                            st.rerun()

    with tab2:
        for h in st.session_state['history']:
            st.text(f"{h['time']} | {h['product']}")
            st.caption(h['answer'])
            st.divider()
