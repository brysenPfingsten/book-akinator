# backend/app/workers/llm_worker.py
import os
import json
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

def query_llm_for_book(history: list) -> dict:
    """
    Query OpenAI GPT with a conversation history to guess the book or ask clarifying questions.

    :param history: List of dicts with 'role' and 'content'.
    :return: Structured dict with either 'confident' guess or 'need_clarification'.
    """
    print("HISTORY")
    print(history)
    # System prompt preserved from your original style
    system_prompt = """
You are an assistant helping to identify books based on user descriptions and clarifications.

Your task:

1. If you are confident about the book, reply with JSON like:
{
  "status": "confident",
  "title": "Book Title Here",
  "author": "Author Name Here"
}

2. If you are not confident yet, reply with JSON like:
{
  "status": "need_clarification",
  "question": "A clarifying yes/no question that would help you identify the book."
}

Important rules:
- Respond ONLY in JSON format.
- No extra commentary, no free text.
- Ask **only one** clarifying question at a time if unsure.
- If confident, do NOT ask a question, just output the structured guess.
    """.strip()

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            *history,
        ],
        temperature=0  # deterministic
    )

    content = response.choices[0].message.content
    print(f"[DEBUG] LLM raw output: {content}")

    try:
        # Parse response safely
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse LLM JSON response: {e}")
        return {"status": "error", "error": str(e), "raw_response": content}
