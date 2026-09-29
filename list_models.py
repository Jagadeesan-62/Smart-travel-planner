import os
import google.generativeai as genai

gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "AIzaSyCsehVYbggmlA-HE76XbUaIT0GnEDVgzfE"

genai.configure(api_key=gemini_key)
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)
