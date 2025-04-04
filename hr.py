import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=openai_api_key)

conversation_history = []

system_prompt = {
    "role": "system",
    "content": (
        "Ты специалист по проведению первичного HR-собеседования. \n"
        "Твоя задача — провести интервью с кандидатом, выяснить его профессиональный опыт, навыки, мотивацию, личные качества, карьерные цели и ожидания от работы. \n"
        "Задавай вопросы по одному, дожидайся ответа, и только после — следующий. \n"
        "Задай как минимум 10 вопросов. \n"
        "Когда узнаешь достаточно, вызови функцию summarize_candidate_profile для финального описания кандидата."
    )
}

functions = [
    {
        "name": "summarize_candidate_profile",
        "description": "Создать краткое описание кандидата на основе интервью",
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
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        functions=functions,
        function_call="auto"
    )
    return response

messages = [system_prompt]

print("👋 GPT-Интервьюер начал работу. Отвечайте на вопросы!\n")

while True:
    response = call_gpt(messages)
    message = response.choices[0].message

    if hasattr(message, "function_call") and message.function_call is not None:
        print("\n✅ GPT считает, что информации достаточно. Генерируется финальное описание кандидата...\n")
        function_name = message.function_call.name
        arguments = json.loads(message.function_call.arguments)

        if function_name == "summarize_candidate_profile":
            summary_prompt = {
                "role": "system",
                "content": (
                    "Ты составил итоговое описание кандидата на основе интервью. \n"
                    "Используй стиль, будто представляешь кандидата для дальнейшего обсуждения в HR. \n"
                    "Сделай текст связным и информативным, упоминая ключевые ответы: опыт, навыки, мотивацию, личные качества, карьерные цели и т.д."
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
            print("🧠 Финальное описание кандидата:\n")
            print(final_summary)
            break

    question = message.content
    print(f"🤖 GPT: {question}")
    answer = input("🧠 Вы: ")

    messages.append({"role": "assistant", "content": question})
    messages.append({"role": "user", "content": answer})
