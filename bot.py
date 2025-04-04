import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

openai_api_key=os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=openai_api_key)

conversation_history = []

system_prompt = {
    "role": "system",
    "content": (
        "Ты специалист по распаковке личности. "
        "Твоя задача — получить от пользователя максимум информации о нём, его ценностях, отношении к профессии, хобби, сообщениях аудитории, желаемом образе. "
        "Задавай по одному вопросу, дожидайся ответа, и только после — следующий. "
        "Задай как минимум 10 вопросов"
        "Когда узнаешь достаточно, вызови функцию summarize_user_profile для финального описания."
    )
}

functions = [
    {
        "name": "summarize_user_profile",
        "description": "Создать краткое описание личности эксперта на основе истории общения",
        "parameters": {
            "type": "object",
            "properties": {
                "qa_pairs": {
                    "type": "array",
                    "description": "Список вопросов и ответов, полученных в ходе интервью",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "answer": {"type": "string"}
                        },
                        "required": ["question", "answer"]
                    }
                }
            },
            "required": ["qa_pairs"]
        }
    }
]

def call_gpt(messages):
    response = client.chat.completions.create(model="gpt-4",
    messages=messages,
    functions=functions,
    function_call="auto")
    return response

messages = [system_prompt]

print("👋 GPT-Интервьюер начал работу. Отвечай на вопросы!\n")

while True:
    response = call_gpt(messages)
    message = response.choices[0].message

    if hasattr(message, "function_call") and message.function_call is not None:
        print("\n✅ GPT считает, что информации достаточно. Генерируется саммари личности...\n")
        function_name = message.function_call.name
        arguments = json.loads(message.function_call.arguments)

        if function_name == "summarize_user_profile":
            summary_prompt = {
                "role": "system",
                "content": (
                    "Ты пишешь итоговое описание личности эксперта на основе интервью. "
                    "Используй стиль, будто ты презентуешь этого человека в рамках его профессионального образа. "
                    "Сделай текст связным и живым, упоминая ключевые ответы: кто он, чем занимается, что ценит, как хочет быть воспринят аудиторией и т.д."
                )
            }

            qa_text = "\n".join([f"{item['question']}\nОтвет: {item['answer']}" for item in arguments["qa_pairs"]])

            followup = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    summary_prompt,
                    {"role": "user", "content": qa_text}
                ]
            )

            final_summary = followup.choices[0].message
            print("🧠 Саммари эксперта:\n")
            print(final_summary)
            break

    question = message.content
    print(f"🤖 GPT: {question}")
    answer = input("🧠 Ты: ")

    messages.append({"role": "assistant", "content": question})
    messages.append({"role": "user", "content": answer})
