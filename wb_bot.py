import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# ==========================================
# 1. НАСТРОЙКИ И ДИЗАЙН
# ==========================================
st.set_page_config(page_title="WB AI Master v20", layout="wide", page_icon="🛡️")

st.markdown("""
    <style>
    .block-container {padding-top: 1.5rem;}
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
    }
    .stTextArea textarea {font-size: 16px !important;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. ФУНКЦИИ (CORE)
# ==========================================

def format_date(iso_date):
    if not iso_date: return ""
    try:
        dt = datetime.datetime.fromisoformat(str(iso_date).replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return str(iso_date)

def get_wb_data(wb_token, mode="feedbacks", is_answered=False):
    if len(wb_token) < 10: return []
    headers = {"Authorization": wb_token}
    params = {"isAnswered": str(is_answered).lower(), "take": 50, "skip": 0, "order": "dateDesc"}
    
    try:
        url = f"https://feedbacks-api.wildberries.ru/api/v1/{mode}"
        res = requests.get(url, headers=headers, params=params, timeout=15)
        if res.status_code == 200:
            data = res.json()
            # Безопасное извлечение
            if 'data' in data and mode in data['data']:
                return data['data'][mode]
        return []
    except Exception:
        return []

def send_wb(review_id, text, wb_token, mode="feedbacks"):
    headers = {"Authorization": wb_token, "Content-Type": "application/json"}
    if not text or len(text) < 2: return "Текст пустой"
    
    try:
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
            payload = {"id": review_id, "text": text}
        else: # questions
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions/answer"
            payload = {"id": review_id, "answer": {"text": text}, "state": "wbViewed"}
        
        res = requests.patch(url, headers=headers, json=payload, timeout=15)
        
        if res.status_code in [200, 204]: return "OK"
        return f"Ошибка WB {res.status_code}"
    except Exception as e:
        return f"Сбой сети: {e}"

def generate_ai(api_key, text, item_name, user_name, instructions, signature):
    if not api_key: return "Нет ключа Groq"
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    safe_user = user_name if user_name else "Покупатель"
    greeting = f"Здравствуйте, {safe_user}!" if len(safe_user) > 2 and safe_user.lower() != "клиент" else "Здравствуйте!"
    
    prompt = f"""
    Роль: Менеджер Wildberries.
    Товар: {item_name}
    Клиент пишет: "{text}"
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
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка AI: {e}"

def log_event(message, type="info"):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    icon = "✅" if type == "success" else "❌" if type == "error" else "ℹ️"
    entry = f"{timestamp} {icon} {message}"
    if 'action_log' in st.session_state:
        st.session_state['action_log'].insert(0, entry)
        if len(st.session_state['action_log']) > 50:
            st.session_state['action_log'].pop()

# ==========================================
# 3. ИНИЦИАЛИЗАЦИЯ
# ==========================================

if 'feedbacks' not in st.session_state: st.session_state['feedbacks'] = []
if 'questions' not in st.session_state: st.session_state['questions'] = []
if 'action_log' not in st.session_state: st.session_state['action_log'] = []

# Ключи
default_wb = ""
default_groq = ""
if hasattr(st, 'secrets'):
    default_wb = st.secrets.get('WB_API_TOKEN', "")
    default_groq = st.secrets.get('GROQ_API_KEY', "")

with st.sidebar:
    st.title("🎛️ Панель управления")
    wb_token = st.text_input("WB Token", value=default_wb, type="password")
    groq_key = st.text_input("Groq Key", value=default_groq, type="password")
    
    with st.expander("📝 Инструкции"):
        prompt_rev = st.text_area("Отзывы:", value="Благодари за покупку.", height=70)
        prompt_quest = st.text_area("Вопросы:", value="Отвечай коротко и по делу.", height=70)
        signature = st.text_input("Подпись:", value="С уважением, команда бренда")
    
    st.divider()
    col_a1, col_a2 = st.columns(2)
    auto_reviews = col_a1.toggle("Авто Отзывы")
    auto_questions = col_a2.toggle("Авто Вопросы")
    
    st.markdown("---")
    if st.button("🧹 Очистить кэш"):
        st.session_state.clear()
        st.rerun()

if not wb_token or not groq_key:
    st.warning("Введите ключи.")
    st.stop()

# --- ГЛАВНЫЙ ЭКРАН ---

st.title("💎 WB AI Master v20 (Safe Mode)")

if st.button("🔄 Сканировать магазин", type="primary", use_container_width=True):
    with st.spinner("Загрузка..."):
        st.session_state['feedbacks'] = get_wb_data(wb_token, "feedbacks")
        st.session_state['questions'] = get_wb_data(wb_token, "questions")
        log_event("Данные обновлены вручную")

c1, c2, c3 = st.columns(3)
count_rev = len(st.session_state.get('feedbacks', []))
count_quest = len(st.session_state.get('questions', []))
c1.metric("Ждут отзывов", count_rev)
c2.metric("Ждут вопросов", count_quest)
c3.metric("Логи", len(st.session_state['action_log']))

st.markdown("<br>", unsafe_allow_html=True)

tab_rev, tab_quest, tab_log, tab_arch = st.tabs([
    f"⭐ Отзывы ({count_rev})", 
    f"❓ Вопросы ({count_quest})", 
    "📜 Журнал",
    "🗄️ Архив"
])

# === ОТЗЫВЫ (БЕЗОПАСНЫЙ РЕНДЕР) ===
with tab_rev:
    reviews = st.session_state.get('feedbacks', [])
    if not reviews:
        st.info("Нет отзывов.")
    else:
        for rev in reviews:
            try:
                # Безопасное получение данных (чтобы не было KeyError)
                prod_details = rev.get('productDetails', {})
                prod_name = prod_details.get('productName', 'Название не загрузилось')
                rating = rev.get('productValuation', 5)
                text = rev.get('text', '')
                user = rev.get('userName', 'Клиент')
                
                with st.container(border=True):
                    cols = st.columns([4, 1])
                    cols[0].markdown(f"**{prod_name}**")
                    cols[1].markdown(f"⭐ **{rating}**")
                    
                    c_img, c_txt = st.columns([1, 6])
                    
                    # БЕЗОПАСНАЯ ЗАГРУЗКА ФОТО
                    with c_img:
                        img_url = None
                        photos = rev.get('photoLinks')
                        if photos and isinstance(photos, list) and len(photos) > 0:
                            # Пытаемся найти хоть какую-то ссылку
                            p = photos[0]
                            img_url = p.get('smallSize') or p.get('fullSize') or p.get('miniSize')
                        
                        if img_url:
                            st.image(img_url, use_container_width=True)
                        else:
                            st.write("📦")
                    
                    with c_txt:
                        st.write(f"👤 **{user}:** {text}")
                        
                        area_key = f"rev_txt_{rev.get('id')}"
                        
                        if st.button("✨ Сгенерировать", key=f"gen_r_{rev.get('id')}"):
                            ans = generate_ai(groq_key, text, prod_name, user, prompt_rev, signature)
                            st.session_state[area_key] = ans
                            st.rerun()
                        
                        final_txt = st.text_area("Ответ:", key=area_key, label_visibility="collapsed")
                        
                        if st.button("Отправить", key=f"snd_r_{rev.get('id')}"):
                            res = send_wb(rev.get('id'), final_txt, wb_token, "feedbacks")
                            if res == "OK":
                                st.success("Отправлено!")
                                log_event(f"Ответ на отзыв: {prod_name}", "success")
                                st.session_state['feedbacks'].remove(rev)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(res)
            except Exception as e:
                st.error(f"Ошибка отображения отзыва: {e}")

# === ВОПРОСЫ (БЕЗОПАСНЫЙ РЕНДЕР) ===
with tab_quest:
    quests = st.session_state.get('questions', [])
    if not quests:
        st.info("Нет вопросов.")
    else:
        for q in quests:
            try:
                prod_details = q.get('productDetails', {})
                prod_name = prod_details.get('productName', 'Товар')
                text = q.get('text', '')
                date_str = format_date(q.get('createdDate'))
                
                with st.container(border=True):
                    st.markdown(f"❓ **{prod_name}**")
                    st.caption(date_str)
                    st.write(f"**Вопрос:** {text}")
                    
                    area_q_key = f"quest_txt_{q.get('id')}"
                    
                    if st.button("✨ Придумать ответ", key=f"gen_q_{q.get('id')}"):
                        ans = generate_ai(groq_key, text, prod_name, "Покупатель", prompt_quest, signature)
                        st.session_state[area_q_key] = ans
                        st.rerun()
                    
                    final_q = st.text_area("Ответ:", key=area_q_key, label_visibility="collapsed")
                    
                    if st.button("Отправить", key=f"snd_q_{q.get('id')}"):
                        res = send_wb(q.get('id'), final_q, wb_token, "questions")
                        if res == "OK":
                            st.success("Отправлено!")
                            log_event(f"Ответ на вопрос: {prod_name}", "success")
                            st.session_state['questions'].remove(q)
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(res)
            except Exception as e:
                st.error(f"Ошибка отображения вопроса: {e}")

# === ЖУРНАЛ ===
with tab_log:
    if not st.session_state['action_log']:
        st.caption("Пусто.")
    else:
        for log in st.session_state['action_log']:
            color = "#2e7d32" if "✅" in log else "#c62828" if "❌" in log else "#333"
            st.markdown(f"<div style='color:{color}; border-bottom:1px solid #eee; padding:5px;'>{log}</div>", unsafe_allow_html=True)

# === АРХИВ ===
with tab_arch:
    if st.button("📥 Загрузить историю"):
        with st.spinner("Загрузка..."):
            rv = get_wb_data(wb_token, "feedbacks", True)
            qs = get_wb_data(wb_token, "questions", True)
            st.session_state['history'] = rv + qs
            st.session_state['history'].sort(key=lambda x: x.get('createdDate', ''), reverse=True)
            
    for item in st.session_state.get('history', []):
        try:
            name = item.get('productDetails', {}).get('productName', 'Товар')
            txt = item.get('text', '')
            with st.expander(f"{name} ({format_date(item.get('createdDate'))})"):
                st.write(f"👤 {txt}")
                if item.get('answer'):
                    st.info(item['answer']['text'])
        except:
            pass

# === АВТОМАТИЗАЦИЯ ===
if auto_reviews or auto_questions:
    status_container = st.empty()
    
    if auto_reviews:
        items = get_wb_data(wb_token, "feedbacks")
        for item in items:
            p_name = item.get('productDetails', {}).get('productName', 'Товар')
            status_container.warning(f"🤖 Отзыв: {p_name}...")
            
            ans = generate_ai(groq_key, item.get('text', ''), p_name, item.get('userName', ''), prompt_rev, signature)
            
            if "Ошибка" not in ans:
                res = send_wb(item['id'], ans, wb_token, "feedbacks")
                if res == "OK":
                    log_event(f"Авто-отзыв: {p_name}", "success")
                    st.toast(f"✅ Отзыв закрыт")
            time.sleep(3)

    if auto_questions:
        quests = get_wb_data(wb_token, "questions")
        for q in quests:
            p_name = q.get('productDetails', {}).get('productName', 'Товар')
            status_container.warning(f"🤖 Вопрос: {p_name}...")
            
            ans = generate_ai(groq_key, q.get('text', ''), p_name, "Покупатель", prompt_quest, signature)
            
            if "Ошибка" not in ans:
                res = send_wb(q['id'], ans, wb_token, "questions")
                if res == "OK":
                    log_event(f"Авто-вопрос: {p_name}", "success")
                    st.toast(f"✅ Вопрос закрыт")
            time.sleep(3)
    
    status_container.success(f"✅ Жду 60 сек... {datetime.datetime.now().strftime('%H:%M:%S')}")
    time.sleep(60)
    st.rerun()
