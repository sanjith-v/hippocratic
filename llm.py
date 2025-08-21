# llm.py
import os
from openai import OpenAI

# Same model as required by the assignment
MODEL_NAME = "gpt-3.5-turbo"

# Create a single client per process
_client = None


def _get_client():
    global _client
    if _client is None:
        # Reads OPENAI_API_KEY from env
        _client = OpenAI()
    return _client


def chat(messages, max_tokens=1200, temperature=0.7):
    """
    Minimal wrapper using the OpenAI v1+ SDK.
    Accepts a `messages` list with system/user/assistant roles.
    """
    client = _get_client()
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message.content
