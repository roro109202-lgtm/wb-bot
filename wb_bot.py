import streamlit as st
import requests
import time
import datetime
from openai import OpenAI

# ==========================================
# 1. НАСТРОЙКИ (DARK THEME FRIENDLY)
# ==========================================
st.set_page_config(page_title="WB AI Master v27", layout="wide", page_icon="🛍️")

st.markdown("""
    <style>
    .block-container {padding-top: 1.5rem;}
    .stTextArea textarea {font-size: 16px !important;}
    
    /* Стили для текста, адаптированные под темную тему */
    .wb-pros {
        color: #4CAF50; /* Зеленый для достоинств */
        margin-bottom: 4px;
        font-weight: 500;
    }
    .wb-cons {
        color: #FF5252; /* Красный для недостатков */
        margin-bottom: 4px;
        font-weight: 500;
    }
    .wb-comment {
        margin-top: 8px;
        font-size: 16px;
        /* Цвет текста наследуется от темы Streamlit (белый на темном) */
    }
    .wb-label {
        font-weight: bold;
        opacity: 0.8;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. ФУНКЦИИ
# ==========================================

def format_date(iso_date):
    if not iso_date: return ""
    try:
        dt = datetime.datetime.fromisoformat(str(iso_date).replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y в %H:%M")
    except:
        return str(iso_date)

# ПРАВИЛЬНЫЙ ГЕНЕРАТОР ССЫЛОК НА ФОТО (2025)
def get_main_photo_url(nm_id):
    try:
        vol = int(nm_id) // 100000
        part = int(nm_id) // 1000
        
        # Определение хоста (basket)
        if 0 <= vol <= 143: host = "01"
        elif 144 <= vol <= 287: host = "02"
        elif 288 <= vol <= 431: host = "03"
        elif 432 <= vol <= 719: host = "04"
        elif 720 <= vol <= 1007: host = "05"
        elif 1008 <= vol <= 1061: host = "06"
        elif 1062 <= vol <= 1115: host = "07"
        elif 1116 <= vol <= 1169: host = "08"
        elif 1170 <= vol <= 1313: host = "09"
        elif 1314 <= vol <= 1601: host = "10"
        elif 1602 <= vol <= 1655: host = "11"
        elif 1656 <= vol <= 1919: host = "12"
        elif 1920 <= vol <= 2045: host = "13"
        elif 2046 <= vol <= 2189: host = "14"
        elif 2190 <= vol <= 2405: host = "15"
        else: host = "16" # Запасной

        # Используем /images/big/1.webp (или .jpg) - это главное фото
        return f"https://basket-{host}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/images/big/1.webp"
    except:
        return None

def get_wb_data(wb_token, mode="feedbacks"):
    if not wb_token or len(wb_token) < 10: return []
    headers = {"Authorization": wb_token}
    params = {"isAnswered": "false", "take": 50, "skip": 0, "order": "dateDesc"}
    try:
        url = f"https://feedbacks-api.wildberries.ru/api/v1/{mode}"
        res = requests.get(url, headers=headers, params=params, timeout=15)
        if res.status_code == 200:
            json_data = res.json()
            if 'data' in json_data and mode in json_data['data']:
                return json_data['data'][mode]
        return []
    except:
        return []

def send_wb(review_id, text, wb_token, mode="feedbacks"):
    headers = {"Authorization": wb_token, "Content-Type": "application/json"}
    if not text or len(text) < 2: return "Текст пустой"
    try:
        if mode == "feedbacks":
            url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer"
            payload = {"id": review_id, "text": text}
        else: 
            url = "https://feedbacks-api.wildberries.ru/api/v1/questions/answer"
            payload = {"id": review_id, "answer": {"text": text}, "state": "wbViewed"}
        
        res = requests.patch(url, headers=headers, json=payload, timeout=15)
        if res.status_code in [200, 204]: return "OK"
        return f"Ошибка WB {res.status_code}"
    except Exception as e:
        return f"Ошибка сети"

def generate_ai(api_key, full_text, item_name, user_name, instructions, signature):
    if not api_key: return "Нет ключа Groq"
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    safe_user = user_name if user_name else "Покупатель"
    greeting = f"Здравствуйте, {safe_user}!" if len(safe_user) > 2 and safe_user.lower() != "клиент" else "Здравствуйте!"
    
    prompt = f"""
    Роль: Менеджер Wildberries.
    Товар: {item_name}
    Полный текст отзыва:
    "{full_text}"
    
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

# ==========================================
# 3. ИНИЦИАЛИЗАЦИЯ
# ==========================================

if 'feedbacks' not in st.session_state: st.session_state['feedbacks'] = []
if 'questions' not in st.session_state: st.session_state['questions'] = []
if 'action_log' not in st.session_state: st.session_state['action_log'] = []
if 'history' not in st.session_state: st.session_state['history'] = []

# Ключи
default_wb = ""
default_groq = ""
if hasattr(st, 'secrets'):
    default_wb = st.secrets.get('WB_API_TOKEN', "")
    default_groq = st.secrets.get('GROQ_API_KEY', "")

if hasattr(st, 'secrets') and 'shops' in st.secrets:
    if 'shops' not in st.session_state: st.session_state['shops'] = {}
    for name, token in st.secrets['shops'].items():
        st.session_state['shops'][name] = token

# ==========================================
# 4. САЙДБАР
# ==========================================

with st.sidebar:
    st.title("🎛️ Панель управления")
    
    # Магазины
    shops = st.session_state.get('shops', {})
    if shops:
        selected_shop = st.selectbox("Магазин:", list(shops.keys()))
        wb_token = shops[selected_shop]
    else:
        wb_token = st.text_input("WB Token", value=default_wb, type="password")
        selected_shop = "Магазин"

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
    if st.button("🗑️ Очистить кэш"):
        st.session_state.clear()
        st.rerun()

if not wb_token or not groq_key:
    st.warning("Введите ключи.")
    st.stop()

# --- ГЛАВНЫЙ ЭКРАН ---

st.title(f"💎 {selected_shop}")

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

# === ОТЗЫВЫ ===
with tab_rev:
    reviews = st.session_state.get('feedbacks', [])
    if not reviews:
        st.info("Нет отзывов.")
    else:
        for rev in reviews:
            try:
                # Данные
                prod_name = rev.get('productDetails', {}).get('productName', 'Товар')
                nm_id = rev.get('productDetails', {}).get('nmId', 0)
                brand = rev.get('productDetails', {}).get('brandName', '')
                rating = rev.get('productValuation', 5)
                user = rev.get('userName', 'Покупатель')
                
                # Текст
                pros = rev.get('pros', '')
                cons = rev.get('cons', '')
                comment = rev.get('text', '')
                full_text_for_ai = f"Достоинства: {pros}\nНедостатки: {cons}\nКомментарий: {comment}"
                
                with st.container(border=True):
                    cols = st.columns([1, 5])
                    
                    # 1. ГЛАВНОЕ ФОТО ТОВАРА (ЛЕВАЯ КОЛОНКА)
                    with cols[0]:
                        main_photo = get_main_photo_url(nm_id)
                        if main_photo:
                            st.image(main_photo, use_container_width=True)
                        else:
                            st.write("📦")
                    
                    # 2. КОНТЕНТ (ПРАВАЯ КОЛОНКА)
                    with cols[1]:
                        st.markdown(f"**{prod_name}**")
                        st.caption(f"Арт: {nm_id} | Бренд: {brand}")
                        st.markdown(f"⭐ **{rating}** | {user} | {format_date(rev.get('createdDate'))}")
                        
                        st.markdown("---")
                        
                        # ВЫВОД ТЕКСТА (БЕЗ ЧЕРНОГО ЦВЕТА)
                        has_content = False
                        if pros:
                            st.markdown(f"<div class='wb-pros'>👍 Достоинства:</div>{pros}", unsafe_allow_html=True)
                            has_content = True
                        if cons:
                            st.markdown(f"<div class='wb-cons'>👎 Недостатки:</div>{cons}", unsafe_allow_html=True)
                            has_content = True
                        if comment:
                            st.markdown(f"<div class='wb-label'>💬 Комментарий:</div><div class='wb-comment'>{comment}</div>", unsafe_allow_html=True)
                            has_content = True
                            
                        if not has_content:
                            st.caption("*(Оценка без текста)*")
                        
                        # ВЫВОД ФОТО ПОКУПАТЕЛЯ (ЕСЛИ ЕСТЬ)
                        if rev.get('photoLinks'):
                            st.markdown("**Фото клиента:**")
                            # Показываем все фото в ряд
                            p_cols = st.columns(len(rev['photoLinks']))
                            for i, p in enumerate(rev['photoLinks']):
                                p_url = p.get('smallSize') or p.get('fullSize')
                                if p_url and i < 5: # Ограничим 5 фото
                                    p_cols[i].image(p_url, width=100)

                        st.markdown("---")

                        # Блок ответа
                        area_key = f"rev_txt_{rev.get('id')}"
                        
                        if st.button("✨ Сгенерировать", key=f"gen_r_{rev.get('id')}"):
                            text_to_send = full_text_for_ai if has_content else "Оценка без текста"
                            ans = generate_ai(groq_key, text_to_send, prod_name, user, prompt_rev, signature)
                            st.session_state[area_key] = ans
                            st.rerun()
                        
                        final_txt = st.text_area("Ответ:", key=area_key, label_visibility="collapsed")
                        
                        if st.button("Отправить", key=f"snd_r_{rev.get('id')}"):
                            res = send_wb(rev.get('id'), final_txt, wb_token, "feedbacks")
                            if res == "OK":
                                st.success("Отправлено!")
                                st.session_state['feedbacks'].remove(rev)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(res)
            except Exception as e:
                # Если ошибка в одном отзыве, не ломаем остальные
                st.error(f"Ошибка карточки: {e}")

# === ВОПРОСЫ ===
with tab_quest:
    quests = st.session_state.get('questions', [])
    if not quests:
        st.info("Нет вопросов.")
    else:
        for q in quests:
            try:
                prod_name = q.get('productDetails', {}).get('productName', 'Товар')
                nm_id = q.get('productDetails', {}).get('nmId', 0)
                text = q.get('text', '')
                
                with st.container(border=True):
                    cols = st.columns([1, 5])
                    with cols[0]:
                        prod_img = get_main_photo_url(nm_id)
                        if prod_img: st.image(prod_img, use_container_width=True)
                        else: st.write("❓")
                    
                    with cols[1]:
                        st.markdown(f"**{prod_name}**")
                        st.caption(f"Арт: {nm_id}")
                        st.markdown(f"**Вопрос:** {text}")
                        st.caption(format_date(q.get('createdDate')))
                        
                        area_q_key = f"quest_txt_{q.get('id')}"
                        
                        if st.button("✨ Ответ", key=f"gen_q_{q.get('id')}"):
                            ans = generate_ai(groq_key, text, prod_name, "Покупатель", prompt_quest, signature)
                            st.session_state[area_q_key] = ans
                            st.rerun()
                        
                        final_q = st.text_area("Ответ:", key=area_q_key, label_visibility="collapsed")
                        
                        if st.button("Отправить", key=f"snd_q_{q.get('id')}"):
                            res = send_wb(q.get('id'), final_q, wb_token, "questions")
                            if res == "OK":
                                st.success("Отправлено!")
                                st.session_state['questions'].remove(q)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(res)
            except: pass

# === ЛОГИ ===
with tab_log:
    for log in st.session_state['action_log']:
        st.write(log)

# === АРХИВ ===
with tab_arch:
    if st.button("📥 История"):
        st.session_state['history'] = get_wb_data(wb_token, "feedbacks", True)
    for item in st.session_state.get('history', []):
        try:
            name = item.get('productDetails', {}).get('productName', 'Товар')
            txt = item.get('text', '')
            with st.expander(f"{name} ({format_date(item.get('createdDate'))})"):
                st.write(txt if txt else "Без текста")
                if item.get('answer'): st.info(item['answer']['text'])
        except: pass

# === АВТОМАТИЗАЦИЯ ===
if auto_reviews or auto_questions:
    status_container = st.empty()
    
    if auto_reviews:
        items = get_wb_data(wb_token, "feedbacks")
        for item in items:
            p_name = item.get('productDetails', {}).get('productName', 'Товар')
            status_container.warning(f"🤖 Отзыв: {p_name}...")
            
            # Сбор текста
            pros = item.get('pros', '')
            cons = item.get('cons', '')
            comment = item.get('text', '')
            full_txt = f"Плюсы: {pros}. Минусы: {cons}. Текст: {comment}"
            if not full_txt.strip(): full_txt = "Оценка без текста"

            ans = generate_ai(groq_key, full_txt, p_name, item.get('userName', ''), prompt_rev, signature)
            
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
