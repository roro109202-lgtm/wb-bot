def generate_ai_response(api_key, review_text, rating, product_name, brand_signature):
    if not api_key: return "Ошибка: Нет ключа"
    
    try:
        genai.configure(api_key=api_key)
        # Используем самую новую и быструю модель
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        if rating >= 4:
            sentiment = "позитивный"
            goal = "поблагодарить."
        else:
            sentiment = "вежливый, извиняющийся"
            goal = "решить проблему."

        prompt = f"""
        Роль: Поддержка бренда.
        Товар: {product_name}
        Отзыв: "{review_text}" ({rating} звезд).
        Напиши ответ ({sentiment}, {goal}).
        В конце подпись: "{brand_signature}".
        Длина: 2-3 предложения.
        """
        
        safety = {HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE, 
                  HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE}
        
        response = model.generate_content(prompt, safety_settings=safety)
        return response.text
    except Exception as e:
        return f"Ошибка: {e}"
