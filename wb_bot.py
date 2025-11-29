import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# ==========================================
# 1. НАСТРОЙКИ СТРАНИЦЫ
# ==========================================
st.set_page_config(page_title="WB AI Master", layout="wide", page_icon="🛍️")

st.markdown("""
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 5rem;}
    .stTextArea textarea {font-size: 16px !important; line-height: 1.5;}
    div[data-testid="stExpander"] div[role="button"] p {font-size: 16px; font-weight: 600;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. ФУНКЦИИ WB
# ==========================================

def format_date(iso_date):
    if not iso_date: return ""
    try:
        dt = datetime.datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return iso_date

def get_wb_data(wb_token, mode="feedbacks", is_answered=False):
    if len(wb_token) < 10: return []
    headers = {"Authorization": wb_token}
    params = {"isAnswered": str(is_answered).lower(), "take": 30, "skip": 0, "order": "dateDesc"}
    
    try:
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
            key = 'feedbacks'
        else:
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions"
            key = 'questions'
            
        res = requests.get(url, headers=headers, params=params, timeout=15)
        if res.status_code == 200:
            data = res.json()
            if 'data' in data and key in data['data']:
                return data['data'][key]
        return []
    except Exception as e:
        st.error(f"Ошибка WB API: {e}")
        return []

def send_wb(review_id, text, wb_token, mode="feedbacks"):
    headers = {"Authorization": wb_token}
    if not text or len(text) < 2: return "Текст ответа пустой!"

    try:
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
            payload = {"id": review_id, "text": text}
        else:
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions/answer"
            payload = {"id": review_id, "answer": {"text": text}}

        res = requests.patch(url, headers=headers, json=payload, timeout=15)
        
        # Код 200 и 204 - это успех
        if res.status_code in [200, 204]:
            return "OK"
        else:
            return f"Ошибка WB {res.status_code}: {res.text}"
    except Exception as e:
        return f"Сбой сети: {e}"

# ==========================================
# 3. ФУНКЦИЯ НЕЙРОСЕТИ (GROQ)
# ==========================================

def generate_ai(api_key, text, item_name, user_name, instructions, signature):
    if not api_key: return "ОШИБКА: Нет ключа Groq"
    
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    greeting = f"Здравствуйте, {user_name}!" if user_name and len(user_name) > 1 else "Здравствуйте!"

    prompt = f"""
    Роль: Поддержка Wildberries.
    Товар: {item_name}
    Вопрос/Отзыв: "{text}"
    
    Инструкция: {instructions}
    
    Формат:
    1. {greeting}
    2. Текст ответа.
    3. {signature}
    """
    
    try:
        response = client.chat.completions.create(
            # СТАВИМ САМУЮ МОЩНУЮ И СТАБИЛЬНУЮ МОДЕЛЬ
            model="llama3-70b-8192", 
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=800
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"ОШИБКА ГЕНЕРАЦИИ: {e}"

# ==========================================
# 4. ИНТЕРФЕЙС
# ==========================================

if 'history' not in st.session_state: st.session_state['history'] = []
if 'feedbacks' not in st.session_state: st.session_state['feedbacks'] = []
if 'questions' not in st.session_state: st.session_state['questions'] = []

# Авто-ввод ключей
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
    # ТЕСТОВАЯ КНОПКА
    if st.button("📞 Тест нейросети"):
        if not groq_key:
            st.error("Нет ключа!")
        else:
            try:
                client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
                resp = client.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=[{"role": "user", "content": "Скажи: Привет"}],
                )
                st.success(f"Работает! Ответ: {resp.choices[0].message.content}")
            except Exception as e:
                st.error(f"Ошибка связи: {e}")

    st.divider()
    custom_prompt = st.text_area("Инструкция:", value="Благодари за покупку.", height=70)
    signature = st.text_input("Подпись:", value="С уважением, представитель бренда")
    
    st.divider()
    auto_mode = st.toggle("⚡ АВТО-РЕЖИМ (Фон)", value=False)
    
    st.markdown("---")
    if st.button("🗑️ Сброс всего"):
        st.session_state.clear()
        st.rerun()

if not wb_token or not groq_key:
    st.warning("👈 Введите ключи!")
    st.stop()

st.title("🛍️ WB AI Master (Stable)")

tab1, tab2, tab3 = st.tabs(["⭐ Отзывы", "❓ Вопросы", "🗄️ Архив"])

# === ОТЗЫВЫ ===
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
                st.markdown(f"**{rev['productDetails']['productName']}**")
                st.write(f"👤 {rev.get('text', '')}")
                
                gen_key = f"ans_{rev['id']}"
                
                # Кнопка генерации
                if st.button("✨ Сгенерировать", key=f"btn_{rev['id']}"):
                    with st.spinner("Пишу ответ..."):
                        ans = generate_ai(groq_key, rev.get('text', ''), rev['productDetails']['productName'], "Клиент", custom_prompt, signature)
                        st.session_state[gen_key] = ans
                        if "ОШИБКА" in ans: st.error(ans)
                        else: st.rerun()
                
                # Поле ввода
                val = st.session_state.get(gen_key, "")
                final_txt = st.text_area("Ответ:", value=val, key=f"area_{rev['id']}")
                
                # Отправка
                if st.button("🚀 Отправить", key=f"snd_{rev['id']}"):
                    if send_wb(rev['id'], final_txt, wb_token, "feedbacks") == "OK":
                        st.success("Готово!")
                        time.sleep(1)
                        st.session_state['feedbacks'] = [r for r in st.session_state['feedbacks'] if r['id'] != rev['id']]
                        st.rerun()
                    else:
                        st.error("Ошибка отправки")

# === ВОПРОСЫ ===
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
                st.markdown(f"❓ **{q['productDetails']['productName']}**")
                st.write(f"**Вопрос:** {q.get('text', '')}")
                
                q_key = f"q_ans_{q['id']}"
                
                if st.button("✨ Придумать ответ", key=f"btn_q_{q['id']}"):
                    with st.spinner("Думаю..."):
                        ans = generate_ai(groq_key, q.get('text', ''), q['productDetails']['productName'], "Покупатель", custom_prompt, signature)
                        st.session_state[q_key] = ans
                        if "ОШИБКА" in ans: st.error(ans)
                        else: st.rerun()

                val_q = st.session_state.get(q_key, "")
                final_q = st.text_area("Ответ:", value=val_q, key=f"area_q_{q['id']}")
                
                if st.button("🚀 Отправить", key=f"snd_q_{q['id']}"):
                    if send_wb(q['id'], final_q, wb_token, "questions") == "OK":
                        st.success("Отправлено!")
                        time.sleep(1)
                        st.session_state['questions'] = [x for x in st.session_state['questions'] if x['id'] != q['id']]
                        st.rerun()
                    else:
                        st.error("Ошибка отправки")

# === АРХИВ ===
with tab3:
    if st.button("📥 История"):
        with st.spinner("Загрузка..."):
            st.session_state['history'] = get_wb_data(wb_token, "feedbacks", True)
    
    history = st.session_state.get('history', [])
    if history:
        for item in history:
            with st.container(border=True):
                st.write(f"**Товар:** {item['productDetails']['productName']}")
                st.write(f"👤 {item.get('text', '')}")
                if item.get('answer'):
                    st.info(f"✅ {item['answer']['text']}")
                else:
                    st.warning("Нет текста ответа")

# === АВТО-РЕЖИМ ===
if auto_mode:
    st.info("Авто-режим работает...")
    progress = st.progress(0)
    
    # Отзывы
    items = get_wb_data(wb_token, "feedbacks", False)
    for i, item in enumerate(items):
        ans = generate_ai(groq_key, item.get('text',''), item['productDetails']['productName'], "Клиент", custom_prompt, signature)
        if ans and "ОШИБКА" not in ans:
            if send_wb(item['id'], ans, wb_token, "feedbacks") == "OK":
                st.toast(f"Отзыв закрыт: {item['id']}")
        progress.progress((i+1)/len(items))
        time.sleep(2)
        
    # Вопросы
    quests = get_wb_data(wb_token, "questions", False)
    for i, q in enumerate(quests):
        ans = generate_ai(groq_key, q.get('text',''), q['productDetails']['productName'], "Покупатель", custom_prompt, signature)
        if ans and "ОШИБКА" not in ans:
            if send_wb(q['id'], ans, wb_token, "questions") == "OK":
                st.toast(f"Вопрос закрыт")
        time.sleep(2)
        
    st.success("Цикл завершен. Пауза 60 сек.")
    time.sleep(60)
    st.rerun()
