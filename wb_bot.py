import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# ==========================================
# 1. НАСТРОЙКИ СТРАНИЦЫ
# ==========================================
st.set_page_config(page_title="WB AI Master v6 (Fix)", layout="wide", page_icon="🛍️")

st.markdown("""
    <style>
    .block-container {padding-top: 2rem;}
    .stTextArea textarea {font-size: 16px !important;}
    div[data-testid="stExpander"] div[role="button"] p {font-size: 16px; font-weight: 600;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. ФУНКЦИИ
# ==========================================

def format_date(iso_date):
    if not iso_date: return ""
    try:
        dt = datetime.datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return iso_date

def get_wb_data(wb_token, mode="feedbacks"):
    if len(wb_token) < 10: return []
    headers = {"Authorization": wb_token}
    params = {"isAnswered": "false", "take": 30, "skip": 0, "order": "dateDesc"}
    
    try:
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
            key = 'feedbacks'
        else:
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions"
            key = 'questions'
            
        res = requests.get(url, headers=headers, params=params, timeout=15)
        
        if res.status_code == 200:
            return res.json()['data'][key]
        return []
    except Exception as e:
        st.error(f"Ошибка WB: {e}")
        return []

def send_wb(review_id, text, wb_token, mode="feedbacks"):
    headers = {
        "Authorization": wb_token,
        "Content-Type": "application/json"
    }
    
    if not text or len(text) < 2: return "Текст пустой"
    
    try:
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
            payload = {"id": review_id, "text": text}
        else:
            # ДЛЯ ВОПРОСОВ: Добавил поле state и правильную структуру
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions/answer"
            payload = {
                "id": review_id,
                "answer": {"text": text},
                "state": "wbViewed" # Важно: помечаем как просмотренное
            }
        
        res = requests.patch(url, headers=headers, json=payload, timeout=15)
        
        # 200 и 204 - это успех
        if res.status_code in [200, 204]: 
            return "OK"
        else: 
            # ВОЗВРАЩАЕМ ПОЛНЫЙ ТЕКСТ ОШИБКИ ДЛЯ ДИАГНОСТИКИ
            return f"WB ERROR {res.status_code}: {res.text}"
            
    except Exception as e:
        return f"Сбой сети: {e}"

def generate_ai(api_key, text, item_name, user_name, instructions, signature):
    if not api_key: return "Нет ключа Groq"
    
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    greeting = "Здравствуйте!"
    if user_name and len(user_name) > 1 and user_name.lower() not in ["покупатель", "клиент"]:
        greeting = f"Здравствуйте, {user_name}!"
        
    prompt = f"""
    Роль: Поддержка Wildberries.
    Товар: {item_name}
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
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=600,
            timeout=20
        )
        res = response.choices[0].message.content
        if not res: return "ПУСТОЙ ОТВЕТ ОТ НЕЙРОСЕТИ"
        return res
        
    except Exception as e:
        return f"ОШИБКА: {e}"

# ==========================================
# 3. ИНТЕРФЕЙС
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
    custom_prompt = st.text_area("Инструкция:", value="Благодари за покупку. На вопросы отвечай конкретно.", height=70)
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

st.title("🛍️ WB AI Master v6")

tab1, tab2, tab3 = st.tabs(["⭐ Отзывы", "❓ Вопросы", "🗄️ Архив"])

# --- ОТЗЫВЫ ---
with tab1:
    if st.button("🔄 Обновить отзывы", type="primary"):
        with st.spinner("Загрузка..."):
            st.session_state['feedbacks'] = get_wb_data(wb_token, "feedbacks")
            
    reviews = st.session_state.get('feedbacks', [])
    if not reviews:
        st.info("Нет новых отзывов.")
    else:
        for rev in reviews:
            with st.container(border=True):
                prod_name = "Товар"
                if rev.get('productDetails'):
                    prod_name = rev['productDetails'].get('productName', 'Товар')
                
                st.markdown(f"**{prod_name}**")
                st.write(f"👤 {rev.get('text', '')}")
                
                area_key = f"area_rev_{rev['id']}"
                
                if st.button("✨ Сгенерировать", key=f"btn_{rev['id']}"):
                    with st.spinner("Пишу..."):
                        ans = generate_ai(groq_key, rev.get('text', ''), prod_name, rev.get('userName', ''), custom_prompt, signature)
                        st.session_state[area_key] = ans
                        st.rerun()
                
                final_txt = st.text_area("Ответ:", key=area_key)
                
                if st.button("🚀 Отправить", key=f"snd_{rev['id']}"):
                    res = send_wb(rev['id'], final_txt, wb_token, "feedbacks") # res содержит результат
                    if res == "OK":
                        st.success("Готово!")
                        time.sleep(1)
                        st.session_state['feedbacks'] = [r for r in st.session_state['feedbacks'] if r['id'] != rev['id']]
                        st.rerun()
                    else:
                        st.error(res) # ПОКАЗЫВАЕМ РЕАЛЬНУЮ ОШИБКУ

# --- ВОПРОСЫ ---
with tab2:
    if st.button("🔄 Обновить вопросы", type="primary"):
        with st.spinner("Загрузка..."):
            st.session_state['questions'] = get_wb_data(wb_token, "questions")
            
    quests = st.session_state.get('questions', [])
    if not quests:
        st.info("Нет вопросов.")
    else:
        for q in quests:
            with st.container(border=True):
                prod_name = "Товар"
                if q.get('productDetails'):
                    prod_name = q['productDetails'].get('productName', 'Товар')
                
                st.markdown(f"❓ **{prod_name}**")
                st.write(f"**Вопрос:** {q.get('text', '')}")
                
                area_q_key = f"area_quest_{q['id']}"
                
                if st.button("✨ Придумать ответ", key=f"btn_q_{q['id']}"):
                    with st.spinner("Генерирую..."):
                        ans = generate_ai(groq_key, q.get('text', ''), prod_name, "Покупатель", custom_prompt, signature)
                        st.session_state[area_q_key] = ans
                        st.rerun()

                final_q = st.text_area("Ответ:", key=area_q_key)
                
                if st.button("🚀 Отправить", key=f"snd_q_{q['id']}"):
                    res = send_wb(q['id'], final_q, wb_token, "questions")
                    if res == "OK":
                        st.success("Отправлено!")
                        time.sleep(1)
                        st.session_state['questions'] = [x for x in st.session_state['questions'] if x['id'] != q['id']]
                        st.rerun()
                    else:
                        st.error(res) # ПОКАЗЫВАЕМ РЕАЛЬНУЮ ОШИБКУ

# --- АРХИВ ---
with tab3:
    if st.button("📥 История"):
        st.session_state['history'] = get_wb_data(wb_token, "feedbacks", True)
    for item in st.session_state.get('history', []):
        with st.container(border=True):
            if item.get('productDetails'):
                st.write(f"**{item['productDetails'].get('productName','')}**")
            st.write(f"👤 {item.get('text', '')}")
            if item.get('answer'):
                st.info(item['answer']['text'])

# --- АВТО-РЕЖИМ ---
if auto_mode:
    st.info("Авто-режим активен...")
    ph = st.empty()
    
    # 1. Отзывы
    items = get_wb_data(wb_token, "feedbacks")
    for item in items:
        prod = item.get('productDetails', {}).get('productName', 'Товар')
        ans = generate_ai(groq_key, item.get('text',''), prod, "Клиент", custom_prompt, signature)
        if "ОШИБКА" not in ans and len(ans) > 5:
            res = send_wb(item['id'], ans, wb_token, "feedbacks")
            if res == "OK":
                st.toast(f"Отзыв закрыт: {item['id']}")
            else:
                st.error(f"Сбой отправки отзыва: {res}")
        time.sleep(2)
        
    # 2. Вопросы
    quests = get_wb_data(wb_token, "questions")
    for q in quests:
        prod = q.get('productDetails', {}).get('productName', 'Товар')
        ans = generate_ai(groq_key, q.get('text',''), prod, "Покупатель", custom_prompt, signature)
        if "ОШИБКА" not in ans and len(ans) > 5:
            res = send_wb(q['id'], ans, wb_token, "questions")
            if res == "OK":
                st.toast(f"Вопрос закрыт")
            else:
                st.error(f"Сбой отправки вопроса: {res}")
        time.sleep(2)
    
    st.success("Пауза 60 сек...")
    time.sleep(60)
    st.rerun()
