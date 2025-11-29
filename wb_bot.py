import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="WB AI Manager", layout="wide", page_icon="🛍️")

st.markdown("""
    <style>
    .stTextArea textarea {font-size: 16px !important;}
    div[data-testid="stExpander"] div[role="button"] p {font-size: 16px; font-weight: 500;}
    .wb-card {
        background-color: #ffffff;
        padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; margin-bottom: 15px;
    }
    .wb-reply {
        background-color: #f0f2f6; padding: 15px; border-radius: 8px; margin-top: 10px; color: #333;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ ---
if 'feedbacks' not in st.session_state: st.session_state['feedbacks'] = []
if 'questions' not in st.session_state: st.session_state['questions'] = []
# Словарь для хранения текстов ответов {id_отзыва: текст}
if 'answers_map' not in st.session_state: st.session_state['answers_map'] = {}

# --- 3. ФУНКЦИИ WB ---
def format_date(iso_date):
    try:
        dt = datetime.datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except: return iso_date

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
        if res.status_code == 200: return res.json()['data'][key]
        return []
    except Exception as e:
        st.error(f"Ошибка WB: {e}"); return []

def send_wb(id, text, wb_token, mode="feedbacks"):
    headers = {"Authorization": wb_token}
    if not text or len(text) < 2: return "Текст пустой!"
    try:
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
            payload = {"id": id, "text": text}
        else:
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions/answer"
            payload = {"id": id, "answer": {"text": text}}
        res = requests.patch(url, headers=headers, json=payload)
        return "OK" if res.status_code == 200 else f"Ошибка {res.status_code}: {res.text}"
    except Exception as e: return f"Сбой: {e}"

# --- 4. ФУНКЦИЯ ГЕНЕРАЦИИ (CALLBACK) ---
# Эта функция запускается ПРИ нажатии кнопки, ДО обновления экрана
def generate_callback(item_id, text_content, item_name, user_name, instructions, signature, groq_key, mode="review"):
    if not groq_key:
        st.session_state['answers_map'][item_id] = "Ошибка: Нет ключа Groq"
        return

    client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
    
    # Разные промпты для отзывов и вопросов
    if mode == "question":
        context = "Это ВОПРОС покупателя о товаре. Ответь конкретно, коротко и помоги."
    else:
        context = "Это ОТЗЫВ покупателя. Поблагодари за покупку."

    if user_name and user_name.lower() != "клиент":
        greeting = f"Обязательно начни с 'Здравствуйте, {user_name}!'."
    else:
        greeting = "Начни с 'Здравствуйте!'."

    prompt = f"""
    Ты менеджер Wildberries. Товар: {item_name}.
    Сообщение клиента: "{text_content}"
    
    Задача: {context}
    Твоя инструкция по тону: {instructions}
    
    ПРАВИЛА:
    1. {greeting}
    2. Разделяй абзацы пустой строкой.
    3. Подпись в конце: "{signature}".
    4. Язык: Русский.
    """
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6, max_tokens=600
        )
        result = response.choices[0].message.content
        # ЗАПИСЫВАЕМ В ПАМЯТЬ ПРЯМО СЮДА
        st.session_state['answers_map'][item_id] = result
    except Exception as e:
        st.session_state['answers_map'][item_id] = f"Ошибка генерации: {e}"

# --- 5. ИНТЕРФЕЙС ---
with st.sidebar:
    st.title("⚙️ Настройки")
    if hasattr(st, 'secrets'):
        default_wb = st.secrets.get('WB_API_TOKEN', "")
        default_groq = st.secrets.get('GROQ_API_KEY', "")
    else: default_wb, default_groq = "", ""

    wb_token = st.text_input("WB Token", value=default_wb, type="password")
    groq_key = st.text_input("Groq Key", value=default_groq, type="password")
    
    st.divider()
    custom_prompt = st.text_area("Инструкция ИИ:", value="Будь вежливым, используй смайлики умеренно.", height=70)
    signature = st.text_input("Подпись:", value="С уважением, представитель бренда")
    st.divider()
    auto_mode = st.toggle("⚡ АВТО-РЕЖИМ")

if not wb_token or not groq_key:
    st.warning("Введите ключи."); st.stop()

st.title("🛍️ WB AI Center")
tab1, tab2, tab3 = st.tabs(["⭐ Отзывы", "❓ Вопросы", "🗄️ Архив"])

# === ВКЛАДКА ОТЗЫВЫ ===
with tab1:
    if st.button("🔄 Обновить отзывы"):
        st.session_state['feedbacks'] = get_wb_data(wb_token, "feedbacks", False)
    
    if not st.session_state['feedbacks']: st.info("Нет новых отзывов.")
    
    for rev in st.session_state['feedbacks']:
        rid = rev['id']
        # Инициализируем поле, если пусто
        if rid not in st.session_state['answers_map']: st.session_state['answers_map'][rid] = ""
        
        with st.expander(f"⭐ {rev['productDetails']['productName']}", expanded=True):
            c1, c2 = st.columns([1, 2])
            with c1:
                st.write(f"👤 **{rev.get('userName', 'Клиент')}**")
                st.info(rev.get('text', 'Без текста'))
            with c2:
                # МАГИЯ ЗДЕСЬ: on_click вызывает функцию генерации ДО обновления экрана
                st.button("✨ Генерировать", key=f"btn_{rid}", 
                          on_click=generate_callback,
                          args=(rid, rev.get('text',''), rev['productDetails']['productName'], rev.get('userName',''), custom_prompt, signature, groq_key, "review"))
                
                # Текст читается напрямую из session_state
                final = st.text_area("Ответ:", key=f"area_{rid}", 
                                     value=st.session_state['answers_map'][rid], height=180)
                
                if st.button("🚀 Отправить", key=f"snd_{rid}"):
                    if send_wb(rid, final, wb_token, "feedbacks") == "OK":
                        st.success("Ушло!")
                        st.session_state['feedbacks'] = [r for r in st.session_state['feedbacks'] if r['id'] != rid]
                        time.sleep(0.5); st.rerun()
                    else: st.error("Ошибка WB")

# === ВКЛАДКА ВОПРОСЫ ===
with tab2:
    if st.button("🔄 Обновить вопросы"):
        st.session_state['questions'] = get_wb_data(wb_token, "questions", False)
        
    if not st.session_state['questions']: st.info("Нет новых вопросов.")
    
    for q in st.session_state['questions']:
        qid = q['id']
        if qid not in st.session_state['answers_map']: st.session_state['answers_map'][qid] = ""
        
        with st.expander(f"❓ {q['productDetails']['productName']}", expanded=True):
            st.write(f"**Вопрос:** {q.get('text', '')}")
            
            # Кнопка тоже через on_click
            st.button("✨ Придумать ответ", key=f"btn_q_{qid}",
                      on_click=generate_callback,
                      args=(qid, q.get('text',''), q['productDetails']['productName'], "Клиент", custom_prompt, signature, groq_key, "question"))
            
            final_q = st.text_area("Ответ:", key=f"area_q_{qid}", 
                                   value=st.session_state['answers_map'][qid], height=150)
            
            if st.button("🚀 Отправить", key=f"snd_q_{qid}"):
                if send_wb(qid, final_q, wb_token, "questions") == "OK":
                    st.success("Ушло!"); time.sleep(0.5); st.rerun()
                else: st.error("Ошибка WB")

# === ВКЛАДКА АРХИВ ===
with tab3:
    if st.button("📥 Загрузить историю"):
        st.session_state['history_data'] = get_wb_data(wb_token, "feedbacks", True)
    
    for item in st.session_state.get('history_data', []):
        img_html = ""
        # Пробуем найти фото в разных полях WB API
        photos = item.get('photoLinks') or item.get('photos')
        if photos:
            # Берем ссылку, проверяем структура ли это или строка
            link = photos[0]
            if isinstance(link, dict): link = link.get('smallSize') or link.get('min')
            if link:
                img_html = f'<img src="{link}" style="width: 70px; border-radius: 5px; margin-right: 15px;">'
        
        reply = item.get('answer', {}).get('text', 'Нет текста ответа').replace('\n', '<br>')
        
        st.markdown(f"""
        <div class="wb-card">
            <div style="display: flex; align-items: flex-start;">
                {img_html}
                <div style="width: 100%;">
                    <div style="color: #888; font-size: 13px;">{format_date(item['createdDate'])}</div>
                    <div style="font-weight: bold; margin-bottom: 5px;">{item['productDetails']['productName']}</div>
                    <div>{'⭐' * item['productValuation']}</div>
                    <div style="margin: 5px 0;">{item.get('text', '')}</div>
                    <div class="wb-reply"><b>Представитель бренда:</b><br>{reply}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# === АВТО-РЕЖИМ (ФОНОВЫЙ) ===
if auto_mode:
    status = st.empty()
    # Логика авто-режима упрощена для стабильности
    feedbacks = get_wb_data(wb_token, "feedbacks", False)
    for f in feedbacks:
        status.warning(f"Обрабатываю отзыв: {f['id']}...")
        generate_callback(f['id'], f.get('text',''), f['productDetails']['productName'], f.get('userName',''), custom_prompt, signature, groq_key, "review")
        ans = st.session_state['answers_map'][f['id']]
        if "Ошибка" not in ans:
            if send_wb(f['id'], ans, wb_token, "feedbacks") == "OK":
                st.toast(f"✅ Отзыв закрыт: {f['id']}")
        time.sleep(3)
    
    quests = get_wb_data(wb_token, "questions", False)
    for q in quests:
        status.warning(f"Обрабатываю вопрос: {q['id']}...")
        generate_callback(q['id'], q.get('text',''), q['productDetails']['productName'], "Клиент", custom_prompt, signature, groq_key, "question")
        ans = st.session_state['answers_map'][q['id']]
        if "Ошибка" not in ans:
            if send_wb(q['id'], ans, wb_token, "questions") == "OK":
                st.toast(f"✅ Вопрос закрыт: {q['id']}")
        time.sleep(3)
        
    status.success("Проверка завершена. Пауза 60 сек."); time.sleep(60); st.rerun()
