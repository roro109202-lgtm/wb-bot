# Было:
# WB_API_TOKEN = 'eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjUwOTA0djEiLCJ0eXAiOiJKV1QifQ.eyJlbnQiOjEsImV4cCI6MTc3NTc5MzE2NywiaWQiOiIwMTk5YzlhYy1jNTdlLTc3MjctYTQ0NC0xOThiNjIyZTY1NmMiLCJpaWQiOjQwMjYzOTk1LCJvaWQiOjI1MTk4MCwicyI6MTIwMzAsInNpZCI6IjFjNjg4NzgzLWI3MzktNDNjYy04YTdjLTA3MTAyODQwYTI1MSIsInQiOmZhbHNlLCJ1aWQiOjQwMjYzOTk1fQ.ZInCxk82rOSoeJODqVsb5VnSIVE5CS5hp3bK8rgxWFqmbFBJ4xl5nNn2Vk2K_t7Ylr1CDUr5b5gHq9vf8A-lKg'
# OPENAI_API_KEY = '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'

# Стало (для облака):
if 'WB_API_TOKEN' in st.secrets:
    WB_API_TOKEN = st.secrets["WB_API_TOKEN"]
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
else:
    # На случай, если вы всё же запустите локально
    WB_API_TOKEN = st.text_input("Введите WB Token", type="password")
    OPENAI_API_KEY = st.text_input("Введите OpenAI Key", type="password")