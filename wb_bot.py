import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="WB AI Center", layout="wide", page_icon="🛍️")

# Убираем лишние отступы и делаем красиво
st.markdown("""
    <style>
    .block-container {padding-top: 2rem;}
    div[data-testid="stExpander"] div[role="button"] p {font-size: 16px; font-weight: 600;}
    .stTextArea textarea {font-size: 16px !important;}
    </style>
""", unsafe_allow_html=True)

# --- 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def format_date(iso_date):
    try:
        dt = datetime.datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return iso_date

# --- 3. ФУНКЦИИ WB ---

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
            
        res = requests.get(url, headers=headers, params=params, timeout=10)
        if res.status_code == 200:
            return res.json()['data'][key]
        return []
    except Exception as e:
        st.error(f"Ошибка WB: {e}")
        return []

def send_wb(review_id, text, wb_token, mode="feedbacks"):
    headers = {"Authorization": wb_token}
    if not text or len(text) < 2: return "Пустой текст"

    try:
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
            payload = {"id": review_id, "text": text}
        else:
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions/answer"
            payload = {"id": review_id, "answer": {"text": text}}

        res = requests.patch(url, headers=headers, json=payload)
        return "OK" if res.status_code == 200 else f"Ошибка WB {res.status_code}: {res.text}"
    except Exception as e:
        return f"Ошибка сети: {e}"

# --- 4. НЕЙРОСЕТЬ (GROQ) ---

def generate_ai(api_key, text, item_name, user_name, instructions, signature):
    if not api_key: return "Ошибка: Нет ключа Groq"
    
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    # Логика приветствия
    greeting = "Здравствуйте!"
    if user_name and user_name.lower() not in ["клиент", "покупатель", "none"] and len(user_name) > 1:
        greeting = f"Здравствуйте, {user_name}!"

    prompt = f"""
    Ты менеджер Wildberries.
    Товар: {item_name}
    Сообщение от: {user_name}
    Текст: "{text}"
    
    Инструкция: {instructions}
    
    ПРАВИЛА:
    1. Начни ответ с: "{greeting}"
    2. Используй двойной перенос строки между абзацами.
    3. В конце подпись: "{signature}".
    4. Язык: Русский.
    """
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=800
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка AI: {e}"

# --- 5. ИНТЕРФЕЙС ---

# Авто-загрузка ключей из Secrets
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
    custom_prompt = st.text_area("Инструкция:", value="Будь вежлив, благодари за покупку.", height=70)
    signature = st.text_input("Подпись:", value="С уважением, представитель бренда")
    
    st.divider()
    auto_mode = st.toggle("⚡ АВТО-РЕЖИМ", value=False)
    if auto_mode:
        st.info("Бот работает в фоне...")

if not wb_token or not groq_key:
    st.warning("⚠️ Введите ключи (или сохраните их в Secrets).")
    st.stop()

# --- ОСНОВНАЯ ЧАСТЬ ---
st.title("🛍️ WB AI Center")

tab_rev, tab_quest, tab_hist = st.tabs(["⭐ Отзывы", "❓ Вопросы", "🗄️ Архив"])

# === ВКЛАДКА ОТЗЫВЫ ===
with tab_rev:
    col_r1, col_r2 = st.columns([1, 4])
    if col_r1.button("🔄 Обновить отзывы"):
        st.session_state['feedbacks'] = get_wb_data(wb_token, "feedbacks", False)
    
    reviews = st.session_state.get('feedbacks', [])
    if not reviews:
        st.info("Нет новых отзывов")
    else:
        for rev in reviews:
            with st.container(border=True):
                # Заголовок карточки
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{rev['productDetails']['productName']}**")
                c1.write(f"{'⭐'*rev['productValuation']}")
                c2.caption(format_date(rev['createdDate']))
                
                # Контент
                col_img, col_txt = st.columns([1, 5])
                with col_img:
                    if rev.get('photoLinks'):
                        st.image(rev['photoLinks'][0]['smallSize'], use_container_width=True)
                    else:
                        st.write("🖼️")
                
                with col_txt:
                    user = rev.get('userName', 'Клиент')
                    st.write(f"👤 **{user}:** {rev.get('text', '')}")
                    
                    # Генерация
                    gen_key = f"ans_{rev['id']}"
                    
                    if st.button("✨ Сгенерировать ответ", key=f"btn_{rev['id']}"):
                        with st.spinner("Пишу..."):
                            ans = generate_ai(groq_key, rev.get('text', ''), rev['productDetails']['productName'], user, custom_prompt, signature)
                            st.session_state[gen_key] = ans
                            st.rerun() # ВАЖНО: Обновляем экран сразу
                    
                    # Поле ввода (читает из памяти)
                    val = st.session_state.get(gen_key, "")
                    final_txt = st.text_area("Ваш ответ:", value=val, key=f"area_{rev['id']}")
                    
                    if st.button("🚀 Отправить", key=f"snd_{rev['id']}"):
                        res = send_wb(rev['id'], final_txt, wb_token, "feedbacks")
                        if res == "OK":
                            st.success("Отправлено!")
                            time.sleep(1)
                            # Удаляем из списка локально
                            st.session_state['feedbacks'] = [r for r in st.session_state['feedbacks'] if r['id'] != rev['id']]
                            st.rerun()
                        else:
                            st.error(res)

# === ВКЛАДКА ВОПРОСЫ ===
with tab_quest:
    if st.button("🔄 Обновить вопросы"):
        st.session_state['questions'] = get_wb_data(wb_token, "questions", False)
        
    quests = st.session_state.get('questions', [])
    if not quests:
        st.info("Нет новых вопросов")
    else:
        for q in quests:
            with st.container(border=True):
                st.markdown(f"❓ **{q['productDetails']['productName']}**")
                st.write(f"**Вопрос:** {q.get('text', '')}")
                
                q_key = f"q_ans_{q['id']}"
                if st.button("✨ Придумать ответ", key=f"btn_q_{q['id']}"):
                    with st.spinner("Пишу..."):
                        q_prompt = custom_prompt + " Это ВОПРОС. Ответь конкретно."
                        ans = generate_ai(groq_key, q.get('text', ''), q['productDetails']['productName'], "Клиент", q_prompt, signature)
                        st.session_state[q_key] = ans
                        st.rerun()

                val_q = st.session_state.get(q_key, "")
                final_q = st.text_area("Ответ:", value=val_q, key=f"area_q_{q['id']}")
                
                if st.button("🚀 Отправить", key=f"snd_q_{q['id']}"):
                    res = send_wb(q['id'], final_q, wb_token, "questions")
                    if res == "OK":
                        st.success("Отправлено!")
                        time.sleep(1)
                        st.session_state['questions'] = [x for x in st.session_state['questions'] if x['id'] != q['id']]
                        st.rerun()
                    else:
                        st.error(res)

# === ВКЛАДКА АРХИВ (ИСПРАВЛЕННАЯ) ===
with tab_hist:
    if st.button("📥 Загрузить историю с WB"):
        with st.spinner("Загружаю..."):
            st.session_state['history'] = get_wb_data(wb_token, "feedbacks", True)
    
    history = st.session_state.get('history', [])
    if history:
        for item in history:
            # Используем надежный контейнер вместо HTML
            with st.container(border=True):
                col1, col2 = st.columns([1, 5])
                
                with col1:
                    if item.get('photoLinks'):
                        st.image(item['photoLinks'][0]['smallSize'], use_container_width=True)
                    else:
                        st.write("📦")
                
                with col2:
                    # Дата и товар
                    st.caption(format_date(item['createdDate']))
                    st.markdown(f"**{item['productDetails']['productName']}**")
                    st.write(f"{'⭐' * item['productValuation']}")
                    
                    # Отзыв
                    user = item.get('userName', 'Клиент')
                    st.write(f"👤 **{user}:** {item.get('text', '')}")
                    
                    st.divider()
                    
                    # Ответ (Безопасное получение)
                    answer_block = item.get('answer')
                    if answer_block and 'text' in answer_block:
                        st.info(f"✅ **Ответ:**\n\n{answer_block['text']}")
                    else:
                        st.warning("⚠️ Ответ отправлен, но текст не загрузился или пуст.")
    else:
        st.info("История пуста или не загружена.")

# === АВТО-РЕЖИМ ===
if auto_mode:
    status = st.empty()
    # 1. Отзывы
    revs = get_wb_data(wb_token, "feedbacks", False)
    for r in revs:
        status.warning(f"Отзыв: {r['productDetails']['productName']}")
        user = r.get('userName', 'Клиент')
        ans = generate_ai(groq_key, r.get('text',''), r['productDetails']['productName'], user, custom_prompt, signature)
        if ans and "Ошибка" not in ans:
            if send_wb(r['id'], ans, wb_token, "feedbacks") == "OK":
                st.toast(f"Готово: {r['id']}")
        time.sleep(3)
        
    # 2. Вопросы
    qs = get_wb_data(wb_token, "questions", False)
    for q in qs:
        status.warning("Обрабатываю вопрос...")
        ans = generate_ai(groq_key, q.get('text',''), q['productDetails']['productName'], "Клиент", custom_prompt, signature)
        if ans and "Ошибка" not in ans:
            if send_wb(q['id'], ans, wb_token, "questions") == "OK":
                st.toast(f"Вопрос закрыт")
        time.sleep(3)
    
    status.success("Ожидание...")
    time.sleep(60)
    st.rerun()
