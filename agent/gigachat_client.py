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

    def analyze_contract(self, contract_text: str, notice_text: str = None, law_type: str = "44-ФЗ") -> Dict[str, Any]:
        """Анализ контракта с помощью GigaChat"""

        if notice_text:
            prompt_template = """
            Ты - эксперт по государственным закупкам {law_type}. 
            Проанализируй контракт и извещение о закупке.

            КОНТРАКТ:
            {contract_text}

            ИЗВЕЩЕНИЕ О ЗАКУПКЕ:
            {notice_text}

            Проведи тщательный анализ и найди РЕАЛЬНЫЕ проблемы, а не выдуманные.
            Обрати внимание на:

            1. Соответствие контракта извещению (цена, сроки, предмет)
            2. Наличие всех существенных условий
            3. Ясность формулировок
            4. Соответствие законодательству {law_type}

            ВАЖНО: Не выдумывай проблемы! Если разделы присутствуют - не пиши что их нет.
            Сосредоточься на реальных рисках.

            Ответ в формате JSON:
            {{
                "issues": [
                    {{
                        "type": "тип_проблемы",
                        "severity": "critical|warning|info",
                        "description": "конкретное описание реальной проблемы",
                        "recommendation": "практическая рекомендация"
                    }}
                ],
                "recommendations": ["общие рекомендации"],
                "summary": "объективная оценка"
            }}
            """
        else:
            prompt_template = """
            Ты - эксперт по государственным закупкам {law_type}. 
            Проанализируй контракт.

            КОНТРАКТ:
            {contract_text}

            Проведи тщательный анализ и найди РЕАЛЬНЫЕ проблемы.
            Обрати внимание на:

            1. Полноту и ясность условий
            2. Соответствие {law_type}
            3. Потенциальные риски для сторон
            4. Внутреннюю согласованность

            ВАЖНО: Анализируй только то, что есть в тексте! Не выдумывай отсутствующие разделы.
            Если раздел присутствует - не утверждай что его нет.

            Ответ в формате JSON:
            {{
                "issues": [
                    {{
                        "type": "тип_проблемы", 
                        "severity": "critical|warning|info",
                        "description": "конкретное описание реальной проблемы",
                        "recommendation": "практическая рекомендация"
                    }}
                ],
                "recommendations": ["общие рекомендации"],
                "summary": "объективная оценка"
            }}
            """

        prompt = ChatPromptTemplate.from_template(prompt_template)
        chain = prompt | self.model | self.parser

        try:
            if notice_text:
                response = chain.invoke({
                    "law_type": law_type,
                    "contract_text": contract_text[:15000],  # Ограничиваем длину
                    "notice_text": notice_text[:10000]
                })
            else:
                response = chain.invoke({
                    "law_type": law_type,
                    "contract_text": contract_text[:15000]
                })

            return self._parse_response(response)
        except Exception as e:
            print(f"GigaChat analysis error: {e}")
            return {
                "issues": [{
                    "type": "api_error",
                    "severity": "warning",
                    "description": f"Ошибка подключения к AI сервису: {str(e)}",
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
                return json.loads(json_str)
        except:
            pass

        return {
            "issues": [{
                "type": "parse_error",
                "severity": "warning",
                "description": "Не удалось распознать структурированный ответ",
                "recommendation": "Проверьте контракт вручную"
            }],
            "recommendations": ["Проведите дополнительную проверку"],
            "summary": "Требуется ручная проверка"
        }