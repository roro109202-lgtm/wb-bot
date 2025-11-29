import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# ==========================================
# 1. НАСТРОЙКИ И СТИЛИ
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
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

def format_date(iso_date):
    if not iso_date: return ""
    try:
        dt = datetime.datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return iso_date

# ==========================================
# 3. ФУНКЦИИ WILDBERRIES API
# ==========================================

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
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
            key = 'feedbacks'
        else: # questions
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions"
            key = 'questions'
            
        res = requests.get(url, headers=headers, params=params, timeout=15)
        
        if res.status_code == 200:
            data = res.json()
            if 'data' in data and key in data['data']:
                return data['data'][key]
            return []
        
        if res.status_code == 401:
            st.error("Ошибка 401: Неверный токен WB (или истек).")
        return []
        
    except Exception as e:
        st.error(f"Ошибка соединения с WB: {e}")
        return []

def send_wb(review_id, text, wb_token, mode="feedbacks"):
    headers = {"Authorization": wb_token}
    
    if not text or len(text) < 2:
        return "Ошибка: Текст ответа пустой!"

    try:
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
            payload = {"id": review_id, "text": text}
        else: # questions
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions/answer"
            payload = {"id": review_id, "answer": {"text": text}}

        res = requests.patch(url, headers=headers, json=payload, timeout=15)

        if res.status_code == 200:
            return "OK"
        else:
            return f"Ошибка WB {res.status_code}: {res.text}"
            
    except Exception as e:
        return f"Сбой сети при отправке: {e}"

# ==========================================
# 4. ФУНКЦИЯ НЕЙРОСЕТИ (GROQ)
# ==========================================

def generate_ai(api_key, text, item_name, user_name, instructions, signature):
    if not api_key: return "Ошибка: Нет ключа Groq"
    
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    # Логика приветствия
    if user_name and user_name.lower() not in ["клиент", "покупатель", "none"] and len(user_name) > 1:
        greeting = f"Здравствуйте, {user_name}!"
    else:
        greeting = "Здравствуйте!"

    prompt = f"""
    Роль: Ты профессиональный менеджер поддержки бренда на Wildberries.
    Товар: {item_name}
    Сообщение от клиента: "{text}"
    
    Твоя задача: Написать вежливый и полезный ответ на русском языке.
    
    Инструкция от владельца магазина:
    "{instructions}"
    
    СТРОГИЕ ТРЕБОВАНИЯ К ФОРМАТУ:
    1. Начни ответ с: "{greeting}"
    2. Обязательно делай пустую строку между абзацами (двойной Enter).
    3. В конце добавь подпись: "{signature}".
    4. Не используй markdown (жирный шрифт и т.д.), только простой текст и эмодзи.
    """
    
    try:
        response = client.chat.completions.create(
            # !!! ВОТ ТУТ МЫ ПОСТАВИЛИ САМУЮ НОВУЮ МОДЕЛЬ !!!
            model="llama-3.1-8b-instant", 
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=600,
            timeout=10
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"ОШИБКА ГЕНЕРАЦИИ: {e}"

# ==========================================
# 5. ИНТЕРФЕЙС И НАСТРОЙКИ
# ==========================================

if 'history' not in st.session_state: st.session_state['history'] = []
if 'feedbacks' not in st.session_state: st.session_state['feedbacks'] = []
if 'questions' not in st.session_state: st.session_state['questions'] = []

# Загрузка ключей
default_wb = ""
default_groq = ""
if hasattr(st, 'secrets'):
    default_wb = st.secrets.get('WB_API_TOKEN', "")
    default_groq = st.secrets.get('GROQ_API_KEY', "")

with st.sidebar:
    st.title("⚙️ Настройки")
    
    wb_token = st.text_input("WB API Token", value=default_wb, type="password")
    groq_key = st.text_input("Groq API Key", value=default_groq, type="password")
    
    st.divider()
    
    st.subheader("🎭 Поведение бота")
    custom_prompt = st.text_area("Инструкция:", value="Благодари за покупку. Если есть негатив - извиняйся и предлагай связаться с поддержкой.", height=100)
    signature = st.text_input("Подпись:", value="С уважением, представитель бренда")
    
    st.divider()
    
    auto_mode = st.toggle("⚡ АВТО-РЕЖИМ (Фон)", value=False)
    
    st.markdown("---")
    if st.button("🗑️ Сброс кэша"):
        st.session_state.clear()
        st.rerun()

if not wb_token or not groq_key:
    st.warning("👈 Пожалуйста, введите ключи в меню слева для начала работы.")
    st.stop()

# --- ОСНОВНАЯ ЧАСТЬ ---
st.title("🛍️ WB AI Master")

tab1, tab2, tab3 = st.tabs(["⭐ Отзывы", "❓ Вопросы", "🗄️ Архив ответов"])

# ==========================================
# Вкл 1: ОТЗЫВЫ
# ==========================================
with tab1:
    col_btn, col_info = st.columns([1, 4])
    if col_btn.button("🔄 Обновить отзывы", type="primary"):
        with st.spinner("Загружаю отзывы..."):
            st.session_state['feedbacks'] = get_wb_data(wb_token, "feedbacks", False)
            
    reviews = st.session_state['feedbacks']
    
    if not reviews:
        st.info("Новых отзывов нет! 🎉")
    else:
        st.write(f"Очередь: {len(reviews)} шт.")
        for rev in reviews:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{rev['productDetails']['productName']}**")
                c1.write(f"{'⭐'*rev['productValuation']}")
                c2.caption(format_date(rev['createdDate']))
                
                col_img, col_content = st.columns([1, 5])
                
                with col_img:
                    if rev.get('photoLinks'):
                        st.image(rev['photoLinks'][0]['smallSize'], use_container_width=True)
                    else:
                        st.markdown("📷 *Нет фото*")
                
                with col_content:
                    user_name = rev.get('userName', 'Клиент')
                    st.write(f"👤 **{user_name}:**")
                    st.info(rev.get('text') if rev.get('text') else "*(Без текста)*")
                    
                    gen_key = f"ans_{rev['id']}"
                    
                    if st.button(f"✨ Сгенерировать ответ", key=f"btn_{rev['id']}"):
                        with st.spinner("Думаю..."):
                            ans = generate_ai(groq_key, rev.get('text', ''), rev['productDetails']['productName'], user_name, custom_prompt, signature)
                            
                            if "ОШИБКА" in ans:
                                st.error(ans)
                            else:
                                st.session_state[gen_key] = ans
                                st.rerun()
                    
                    val = st.session_state.get(gen_key, "")
                    final_txt = st.text_area("Текст ответа:", value=val, height=150, key=f"area_{rev['id']}")
                    
                    if st.button("🚀 Отправить на WB", key=f"snd_{rev['id']}"):
                        res = send_wb(rev['id'], final_txt, wb_token, "feedbacks")
                        if res == "OK":
                            st.success("Ответ опубликован!")
                            time.sleep(1)
                            st.session_state['feedbacks'] = [r for r in st.session_state['feedbacks'] if r['id'] != rev['id']]
                            st.rerun()
                        else:
                            st.error(res)

# ==========================================
# Вкл 2: ВОПРОСЫ
# ==========================================
with tab2:
    if st.button("🔄 Обновить вопросы", type="primary"):
        with st.spinner("Загружаю вопросы..."):
            st.session_state['questions'] = get_wb_data(wb_token, "questions", False)
            
    quests = st.session_state['questions']
    
    if not quests:
        st.info("Вопросов нет! 🎉")
    else:
        st.write(f"Очередь: {len(quests)} шт.")
        for q in quests:
            with st.container(border=True):
                st.markdown(f"❓ **{q['productDetails']['productName']}**")
                st.caption(format_date(q['createdDate']))
                st.write(f"**Вопрос:** {q.get('text', '')}")
                
                q_key = f"q_ans_{q['id']}"
                
                if st.button("✨ Придумать ответ", key=f"btn_q_{q['id']}"):
                    with st.spinner("Генерирую..."):
                        q_prompt = custom_prompt + " Это ВОПРОС ПОКУПАТЕЛЯ О ТОВАРЕ. Дай конкретный и полезный ответ."
                        ans = generate_ai(groq_key, q.get('text', ''), q['productDetails']['productName'], "Покупатель", q_prompt, signature)
                        
                        if "ОШИБКА" in ans:
                            st.error(ans)
                        else:
                            st.session_state[q_key] = ans
                            st.rerun()

                val_q = st.session_state.get(q_key, "")
                final_q = st.text_area("Ответ:", value=val_q, height=150, key=f"area_q_{q['id']}")
                
                if st.button("🚀 Отправить", key=f"snd_q_{q['id']}"):
                    res = send_wb(q['id'], final_q, wb_token, "questions")
                    if res == "OK":
                        st.success("Отправлено!")
                        time.sleep(1)
                        st.session_state['questions'] = [x for x in st.session_state['questions'] if x['id'] != q['id']]
                        st.rerun()
                    else:
                        st.error(res)

# ==========================================
# Вкл 3: АРХИВ (ИСТОРИЯ)
# ==========================================
with tab3:
    col_h1, col_h2 = st.columns([1, 4])
    if col_h1.button("📥 Скачать историю с WB"):
        with st.spinner("Загружаю архив отвеченных..."):
            st.session_state['history'] = get_wb_data(wb_token, "feedbacks", True)
    
    history = st.session_state.get('history', [])
    
    if not history:
        st.info("История пуста или не загружена. Нажмите кнопку выше.")
    else:
        for item in history:
            with st.container(border=True):
                col1, col2 = st.columns([1, 6])
                with col1:
                    if item.get('photoLinks'):
                        st.image(item['photoLinks'][0]['smallSize'], use_container_width=True)
                    else:
                        st.write("📦")
                with col2:
                    st.caption(format_date(item['createdDate']))
                    st.markdown(f"**{item['productDetails']['productName']}** {'⭐'*item['productValuation']}")
                    
                    user = item.get('userName', 'Клиент')
                    st.write(f"👤 **{user}:** {item.get('text', '')}")
                    
                    st.divider()
                    
                    ans_data = item.get('answer')
                    if ans_data and 'text' in ans_data:
                        st.markdown(f"✅ **Ответ:**")
                        st.caption(ans_data['text'])
                    else:
                        st.warning("⚠️ Ответ есть в системе, но текст не загрузился.")

# ==========================================
# АВТОМАТИЧЕСКИЙ РЕЖИМ
# ==========================================
if auto_mode:
    st.markdown("---")
    st.subheader("⚡ Авто-режим активен")
    
    status_log = st.empty()
    progress = st.progress(0)
    
    # 1. Отзывы
    revs = get_wb_data(wb_token, "feedbacks", False)
    total = len(revs)
    
    for i, r in enumerate(revs):
        prod = r['productDetails']['productName']
        user = r.get('userName', 'Клиент')
        
        status_log.write(f"🔄 [Отзыв {i+1}/{total}] {prod}...")
        
        ans = generate_ai(groq_key, r.get('text',''), prod, user, custom_prompt, signature)
        
        if ans and "ОШИБКА" not in ans:
            res = send_wb(r['id'], ans, wb_token, "feedbacks")
            if res == "OK":
                st.toast(f"✅ Отзыв {i+1} закрыт!")
            else:
                st.error(f"Сбой отправки: {res}")
        
        progress.progress((i + 1) / (total + 1) if total > 0 else 100)
        time.sleep(3)
        
    # 2. Вопросы
    qs = get_wb_data(wb_token, "questions", False)
    total_q = len(qs)
    
    for i, q in enumerate(qs):
        prod = q['productDetails']['productName']
        status_log.write(f"🔄 [Вопрос {i+1}/{total_q}] {prod}...")
        
        q_prompt = custom_prompt + " Это вопрос. Ответь полезно."
        ans = generate_ai(groq_key, q.get('text',''), prod, "Клиент", q_prompt, signature)
        
        if ans and "ОШИБКА" not in ans:
            res = send_wb(q['id'], ans, wb_token, "questions")
            if res == "OK":
                st.toast(f"✅ Вопрос {i+1} закрыт!")
                
        time.sleep(3)

    status_log.success("🎉 Цикл завершен! Следующая проверка через 60 секунд...")
    time.sleep(60)
    st.rerun()
