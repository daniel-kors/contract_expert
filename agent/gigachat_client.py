import os
import json
from typing import Dict, List, Any
from langchain_gigachat.chat_models import GigaChat
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


class GigaChatClient:
    def __init__(self):
        self.model = GigaChat(
            model="GigaChat-2-Max",
            verify_ssl_certs=False,
            credentials=os.getenv("GIGACHAT_CREDENTIALS")
        )
        self.parser = StrOutputParser()

    def analyze_contract(self, contract_text: str, notice_text: str = None,
                         law_type: str = "44-ФЗ", law_context: str = None) -> Dict[str, Any]:
        """Анализ контракта с помощью GigaChat с учетом текстов законов"""

        # Базовый промпт с учетом контекста закона
        base_prompt = """
        Ты - эксперт по государственным закупкам {law_type}. 
        Проанализируй контракт на соответствие законодательству.

        {law_context}

        КОНТРАКТ:
        {contract_text}
        """

        if notice_text:
            prompt_template = base_prompt + """
            ИЗВЕЩЕНИЕ О ЗАКУПКЕ:
            {notice_text}

            Проведи тщательный анализ и найди РЕАЛЬНЫЕ проблемы.
            Обрати внимание на соответствие конкретным статьям {law_type}, указанным выше.

            ВАЖНО: Ссылайся на конкретные статьи закона при выявлении нарушений!
            Не выдумывай проблемы! Анализируй только то, что есть в тексте.

            Ответ в формате JSON:
            {{
                "issues": [
                    {{
                        "type": "тип_проблемы",
                        "severity": "critical|warning|info",
                        "description": "конкретное описание проблемы со ссылкой на статью закона",
                        "law_reference": "ссылка на статью закона",
                        "recommendation": "практическая рекомендация по исправлению"
                    }}
                ],
                "recommendations": ["общие рекомендации"],
                "summary": "объективная оценка с учетом законодательства"
            }}
            """
        else:
            prompt_template = base_prompt + """
            Проведи тщательный анализ и найди РЕАЛЬНЫЕ проблемы.
            Обрати внимание на соответствие конкретным статьям {law_type}, указанным выше.

            ВАЖНО: Ссылайся на конкретные статьи закона при выявлении нарушений!
            Анализируй только то, что есть в тексте контракта.

            Ответ в формате JSON:
            {{
                "issues": [
                    {{
                        "type": "тип_проблемы", 
                        "severity": "critical|warning|info",
                        "description": "конкретное описание проблемы со ссылкой на статью закона", 
                        "law_reference": "ссылка на статью закона",
                        "recommendation": "практическая рекомендация по исправлению"
                    }}
                ],
                "recommendations": ["общие рекомендации"],
                "summary": "объективная оценка с учетом законодательства"
            }}
            """

        prompt = ChatPromptTemplate.from_template(prompt_template)
        chain = prompt | self.model | self.parser

        try:
            invoke_data = {
                "law_type": law_type,
                "law_context": law_context or f"Анализ на соответствие {law_type}",
                "contract_text": contract_text[:12000],  # Ограничиваем длину
            }

            if notice_text:
                invoke_data["notice_text"] = notice_text[:8000]

            response = chain.invoke(invoke_data)
            return self._parse_response(response)

        except Exception as e:
            print(f"GigaChat analysis error: {e}")
            return {
                "issues": [{
                    "type": "api_error",
                    "severity": "warning",
                    "description": f"Ошибка подключения к AI сервису: {str(e)}",
                    "law_reference": "",
                    "recommendation": "Проверьте интернет-соединение и учетные данные GigaChat"
                }],
                "recommendations": ["Проведите ручную проверку контракта"],
                "summary": "AI анализ временно недоступен"
            }

    def ask_question(self, question: str, context: Dict = None) -> str:
        """Задает вопрос о контракте"""
        prompt = ChatPromptTemplate.from_template("""
        Ответь на вопрос о контракте на основе контекста.

        Контекст: {context}
        Вопрос: {question}

        Ответ:
        """)

        chain = prompt | self.model | self.parser

        return chain.invoke({
            "context": str(context),
            "question": question
        })

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Парсит ответ от GigaChat"""
        try:
            # Ищем JSON в ответе
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end != 0:
                json_str = response[start:end]
                parsed = json.loads(json_str)

                # Добавляем поле law_reference если его нет
                for issue in parsed.get('issues', []):
                    if 'law_reference' not in issue:
                        issue['law_reference'] = ""

                return parsed
        except:
            pass

        return {
            "issues": [{
                "type": "parse_error",
                "severity": "warning",
                "description": "Не удалось распознать структурированный ответ",
                "law_reference": "",
                "recommendation": "Проверьте контракт вручную"
            }],
            "recommendations": ["Проведите дополнительную проверку"],
            "summary": "Требуется ручная проверка"
        }