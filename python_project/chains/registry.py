from typing import Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from models import get_chat_model
from memory.manager import memory_manager

class DynamicChainRegistry:
    """
    Modular Registry to dynamically compose model selection, prompt templates, and conversation memory.
    """
    def __init__(self):
        self._prompts: Dict[str, ChatPromptTemplate] = {}
        self._register_default_prompts()

    def _register_default_prompts(self):
        # 1. Stateful Chat Prompt with Conversation Context
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful, highly intelligent AI assistant.\n\nConversation History:\n{chat_history}\n\nDocument context (may be empty):\n{document_context}\n\nUse document context only when relevant. Do not invent facts. When using it, cite the source exactly as [filename — heading]."),
            ("human", "{user_input}")
        ])
        
        # 2. Summarization Prompt with Context
        summary_prompt = ChatPromptTemplate.from_messages([
            ("system", "Summarize the text or conversation context in 3 concise bullet points.\n\nContext:\n{chat_history}"),
            ("human", "{user_input}")
        ])

        # 3. Code Engineering Assistant Prompt
        code_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert software engineer. Write clean, modern, fully commented code.\n\nContext:\n{chat_history}"),
            ("human", "{user_input}")
        ])

        self._prompts["default_chat"] = chat_prompt
        self._prompts["summarizer"] = summary_prompt
        self._prompts["code_assistant"] = code_prompt

    def register_custom_prompt(self, name: str, prompt_template: ChatPromptTemplate):
        """Dynamically register a new prompt template at runtime."""
        self._prompts[name] = prompt_template

    def execute_dynamic_chain(self, user_input: str, thread_id: Optional[str] = None, chain_name: str = "default_chat", model_name: Optional[str] = None, document_context: Optional[list[Dict[str, Any]]] = None) -> str:
        """
        Executes a dynamic pipeline:
        1. Fetch conversation history from memory_manager for thread_id
        2. Format prompt template
        3. Instantiates dynamic chat model (ChatNVIDIA, OpenAI, Claude, Gemini)
        4. Invokes model pipeline and updates session memory!
        """
        # Fetch formatted chat history
        chat_history = memory_manager.get_formatted_context(thread_id or "default")

        # Get prompt template
        prompt = self._prompts.get(chain_name, self._prompts["default_chat"])

        # Instantiate dynamic model (ChatNVIDIA by default or custom model name)
        llm = get_chat_model(model_name=model_name)

        # Build sequence: prompt | llm | StrOutputParser()
        chain = prompt | llm | StrOutputParser()

        # Update memory with user input
        if thread_id:
            memory_manager.add_user_message(thread_id, user_input)

        # Run chain
        response_text = chain.invoke({
            "chat_history": chat_history,
            "user_input": user_input,
            "document_context": self._format_document_context(document_context or [])
        })

        # Update memory with AI output
        if thread_id:
            memory_manager.add_ai_message(thread_id, response_text)

        return response_text

    @staticmethod
    def _format_document_context(chunks: list[Dict[str, Any]]) -> str:
        if not chunks:
            return 'No uploaded document context.'
        return '\n\n'.join(
            f"[Source: {chunk.get('filename', 'document')} — {chunk.get('heading') or 'untitled section'}]\n{chunk.get('content', '')}"
            for chunk in chunks
        )

# Singleton registry instance
chain_registry = DynamicChainRegistry()
