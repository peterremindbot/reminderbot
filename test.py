import google.generativeai as genai

genai.configure(api_key="AQ.Ab8RN6LhtlV-r5F12YWYrkKzR6aOTnKPRrUaFL8vrj1F_OsO9A")

for model in genai.list_models():
    print(model.name)