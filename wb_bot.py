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
            st.error("Ошибка 401: Неверный токен WB.")
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

        if res.status_code == 200 or res.status_code == 204:
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
    
    if user_name and user_name.lower() not in ["клиент", "покупатель
