from abc import ABC, abstractmethod
import streamlit as st
from google import genai
from google.genai import types
from openai import OpenAI as OpenAIClient


# Abstract Base Class (The Strategy)
class AIStrategy(ABC):
    @abstractmethod
    def generate(self, model_id, chat_history, system_instruction):
        pass


# Concrete Strategy for Google Gemini
class GeminiStrategy(AIStrategy):
    def generate(self, model_id, chat_history, system_instruction):
        client = genai.Client(api_key=st.secrets["api_keys"]["google"])
        api_contents = [
            types.Content(
                role="user" if m["role"] == "user" else "model",
                parts=[types.Part.from_text(text=m["content"])]
            ) for m in chat_history
        ]
        response = client.models.generate_content(
            model=model_id,
            contents=api_contents,
            config=types.GenerateContentConfig(
                temperature=0.7,
                system_instruction=system_instruction
            )
        )
        return response.text

# Concrete Strategy for OpenAI / ChatGPT
class OpenAIStrategy(AIStrategy):
    def generate(self, model_id, chat_history, system_instruction):
        oa_client = OpenAIClient(api_key=st.secrets["api_keys"]["openai"])
        oa_messages = [{"role": "system", "content": system_instruction}]
        for m in chat_history:
            role = "assistant" if m["role"] == "model" else m["role"]
            oa_messages.append({"role": role, "content": m["content"]})

        response = oa_client.chat.completions.create(
            model=model_id,
            messages=oa_messages,
            temperature=0.7
        )
        return response.choices[0].message.content


# Updated AIManager with Failover Logic
class AIManager:
    def __init__(self, model_):
        self.preferred_label = model_
        # Define the priority order: Primary first, then the other
        self.failover_order = [
            model_,
            "ChatGPT 5.2" if model_ == "gemini-3-pro-preview" else "gemini-3-pro-preview"
        ]
        self.strategies = {
            "gemini-3-pro-preview": (GeminiStrategy(), "gemini-3-pro-preview"),
            "ChatGPT 5.2": (OpenAIStrategy(), "gpt-5.2-thinking")
        }

    def get_response(self, chat_history, system_instruction):
        last_error = None
        for model_label in self.failover_order:
            try:
                strategy, model_id = self.strategies[model_label]
                return strategy.generate(model_id, chat_history, system_instruction)
            except Exception as e:
                last_error = e
                # Log or print warning that primary failed, moving to secondary
                continue

        return f"All models failed. Last error: {str(last_error)}"