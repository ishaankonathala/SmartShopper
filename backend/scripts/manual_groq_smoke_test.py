
from dotenv import load_dotenv
from groq import Groq

# Load variables from backend/.env
load_dotenv()

client = Groq()

completion = client.chat.completions.create(
    model="openai/gpt-oss-20b",
    messages=[
        {
            "role": "user",
            "content": "I need comfortable headphones under 5000 rupees. Return the category and budget as JSON."
        }
    ],
    temperature=0,
    max_completion_tokens=256,
    response_format={"type": "json_object"},
)

print(completion.choices[0].message.content)
