import os
import google.generativeai as genai

gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") 

try:
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-1.5-pro")
    
    prompt = "Choose a travel destination in India for nature lovers."
    response = model.generate_content(prompt)
    print("Response 1:", response.text)
    
except Exception as e:
    print("Error:", repr(e))
