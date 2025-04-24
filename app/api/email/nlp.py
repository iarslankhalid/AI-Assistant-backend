import openai
from os import getenv
from dotenv import load_dotenv
# from app.api.email.routes import get_email_threads, get_thread_emails

load_dotenv()
client = openai.OpenAI(api_key=getenv("OPENAI_API_KEY"))

def ask_openai(prompt: str, model: str = "gpt-4-turbo", temperature: float = 0.7) -> str:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful email assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[OpenAI ERROR]: {e}")
        return "AI response unavailable."


import json
from openai import OpenAI
from os import getenv
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=getenv("OPENAI_API_KEY"))

def analyze_email_for_ai_fields(email_body: str, subject: str = "") -> dict:
    prompt = f"""
You are an email assistant. Analyze the email below and return a JSON object with:
1. summary: A concise summary of the email.
2. quick_replies: A list of 2-3 short suggested replies.
3. topic: What is the main topic? (e.g., work, personal, project update)
4. priority_score: An integer from 1-5 (1 = low, 5 = urgent).
5. extracted_tasks: A list of any tasks mentioned in the email.

Email Subject: {subject}
Email Body:
{email_body}

Return JSON like:
{{
  "summary": "...",
  "quick_replies": ["...", "..."],
  "topic": "...",
  "priority_score": 3,
  "extracted_tasks": ["...", "..."]
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that always responds with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
        )
        ai_response = response.choices[0].message.content.strip()

        return json.loads(ai_response)

    except Exception as e:
        print(f"❌ Error: {e}")
        return {
            "summary": None,
            "quick_replies": None,
            "topic": None,
            "priority_score": None,
            "extracted_tasks": None
        }


if __name__ == "__main__":
    email_body = "Hey team, just a reminder to send the weekly report by EOD. Let me know if anyone needs help. Thanks!"
    subject = "Weekly report reminder"
    result = analyze_email_for_ai_fields(email_body, subject)
    print(result)
