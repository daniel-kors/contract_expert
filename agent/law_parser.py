import os
import PyPDF2
import re
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class LawArticle:
    number: str
    title: str
    content: str
    law_type: str


class LawParser:
    def __init__(self, laws_folder: str = "laws"):
        self.laws_folder = laws_folder
        self._loaded_laws = {}

    def load_law(self, law_type: str) -> Dict[str, LawArticle]:
        """Загружает закон из PDF файла и парсит его на статьи"""
        if law_type in self._loaded_laws:
            return self._loaded_laws[law_type]

        if law_type == "44-ФЗ":
            law_file = os.path.join(self.laws_folder, "44fz_.pdf")
        elif law_type == "223-ФЗ":
            law_file = os.path.join(self.laws_folder, "223fz_.pdf")
        else:
            law_file = os.path.join(self.laws_folder, "44fz_.pdf")

        if not os.path.exists(law_file):
            return {}

        articles = self._parse_pdf_law(law_file, law_type)
        self._loaded_laws[law_type] = articles
        return articles

    def _parse_pdf_law(self, file_path: str, law_type: str) -> Dict[str, LawArticle]:
        """УЛУЧШЕННЫЙ парсинг PDF файла закона"""
        articles = {}

        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                full_text = ""

                for page in reader.pages:
                    try:
                        page_text = page.extract_text()
                        # Нормализуем текст - критически важно для парсинга
                        page_text = re.sub(r'\s+', ' ', page_text)
                        full_text += page_text + " "
                    except Exception:
                        continue

                # УЛУЧШЕННЫЕ паттерны для извлечения статей
                patterns = [
                    # Основной паттерн для статей с названиями и содержанием
                    r"Статья\s+(\d+(?:[.,]\d+)?)[\s.]*([^.]{5,80}?)[\s.]*([^С]{2,1500}?)(?=Статья\s+\d+|$)",
                    # Паттерн для статей без названий
                    r"Статья\s+(\d+(?:[.,]\d+)?)\.\s*([^С]{2,1500}?)(?=Статья\s+\d+|$)",
                    # Паттерн для статей с римскими цифрами и сложной структурой
                    r"Ст\.\s*(\d+(?:[.,]\d+)?)[\s.]*([^С]{2,1500}?)(?=Ст\.\s*\d+|Статья\s+\d+|$)",
                    # Резервный паттерн для сложных случаев
                    r"Статья\s+(\d+)[^С]{0,100}?([^.]{5,50})[^С]{0,100}?([^С]{2,1500}?)(?=Статья\s+\d+|$)"
                ]

                for pattern in patterns:
                    matches = re.finditer(pattern, full_text, re.IGNORECASE | re.DOTALL)

                    for match in matches:
                        if len(match.groups()) >= 2:
                            article_num = match.group(1).strip()

                            # Обрабатываем разные группы захвата
                            if len(match.groups()) == 3:
                                article_title = match.group(2).strip() if match.group(2) else "Общие положения"
                                article_content = match.group(3).strip()
                            else:
                                article_title = "Общие положения"
                                article_content = match.group(2).strip() if match.group(2) else ""

                            # ОЧИСТКА контента от мусора
                            article_content = self._clean_article_content(article_content)

                            # ВАЛИДАЦИЯ статьи
                            if (self._is_valid_article(article_num, article_content) and
                                    article_num not in articles):
                                articles[article_num] = LawArticle(
                                    number=article_num,
                                    title=article_title[:100],
                                    content=article_content[:2000],  # Увеличил лимит
                                    law_type=law_type
                                )

                # Если статей мало - пробуем альтернативный метод
                if len(articles) < 15:
                    additional_articles = self._fallback_parsing(full_text, law_type)
                    articles.update(additional_articles)

                return articles

        except Exception as e:
            return {}

    def _clean_article_content(self, content: str) -> str:
        """Очищает контент статьи от мусора"""
        if not content:
            return ""

        # Удаляем служебные блоки
        cleanup_patterns = [
            r'Федеральный закон.*?№\s*\d+[^-]*-ФЗ',
            r'\d+\s*страниц?а?\s*\d*',
            r'Раздел\s+[IVXLCDM]+.*',
            r'Глава\s+\d+.*',
            r'\([^)]*\)\s*\([^)]*\)',  # Двойные скобки
            r'\d+\s*-\s*ФЗ',
            r'Принят.*Государственной Думой',
            r'Одобрен.*Советом Федерации',
        ]

        cleaned = content
        for pattern in cleanup_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Нормализуем пробелы
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned

    def _is_valid_article(self, article_num: str, content: str) -> bool:
        """Проверяет валидность извлеченной статьи"""
        if not article_num or not content:
            return False

        # Проверяем что номер статьи - число
        if not re.match(r'^\d+(?:[.,]\d+)?$', article_num):
            return False

        # Проверяем минимальную длину контента
        if len(content) < 30:
            return False

        # Исключаем оглавление и служебные блоки
        excluded_phrases = [
            'оглавление', 'содержание', 'приложение', 'глава',
            'раздел', 'статья статья', 'часть первая', 'часть вторая'
        ]

        content_lower = content.lower()
        for phrase in excluded_phrases:
            if phrase in content_lower:
                return False

        return True

    def _fallback_parsing(self, full_text: str, law_type: str) -> Dict[str, LawArticle]:
        """Альтернативный метод парсинга если основной не сработал"""
        articles = {}

        # Разделяем по "Статья X" и берем следующий текст
        parts = re.split(r'(Статья\s+\d+(?:[.,]\d+)?)', full_text)

        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                article_match = re.match(r'Статья\s+(\d+(?:[.,]\d+)?)', parts[i])
                if article_match:
                    article_num = article_match.group(1)
                    article_content = parts[i + 1]

                    # Берем текст до следующей статьи или ограничиваем длину
                    next_article_match = re.search(r'Статья\s+\d', article_content)
                    if next_article_match:
                        article_content = article_content[:next_article_match.start()]

                    article_content = self._clean_article_content(article_content[:2000])

                    if article_num not in articles and len(article_content) > 50:
                        articles[article_num] = LawArticle(
                            number=article_num,
                            title="Извлеченная статья",
                            content=article_content,
                            law_type=law_type
                        )

        return articles

    def get_article(self, law_type: str, article_number: str) -> Optional[LawArticle]:
        """Получает конкретную статью закона"""
        articles = self.load_law(law_type)
        return articles.get(article_number)

    def search_articles(self, law_type: str, query: str) -> List[LawArticle]:
        """Ищет статьи по ключевым словам"""
        articles = self.load_law(law_type)
        matching_articles = []

        query_lower = query.lower()
        for article in articles.values():
            article_text = f"{article.title} {article.content}".lower()
            if query_lower in article_text:
                matching_articles.append(article)

        return matching_articles

    def get_relevant_articles_for_contract(self, contract_text: str, law_type: str) -> List[LawArticle]:
        """УЛУЧШЕННЫЙ поиск релевантных статей с весовой системой"""
        articles_dict = self.load_law(law_type)

        if not articles_dict:
            return []

        # Нормализуем текст контракта
        contract_clean = re.sub(r'\s+', ' ', contract_text.lower())
        articles = list(articles_dict.values())

        # Система весов для разных тем
        topic_weights = {
            "price": {
                "keywords": ["цена", "стоимость", "рубл", "сумма", "бюджет", "оплат", "финанс"],
                "weight": 2.0,
                "priority_articles": ["34", "22", "19"]  # Приоритетные статьи для темы
            },
            "deadlines": {
                "keywords": ["срок", "период", "дата", "время", "исполнен", "поставк", "выполнен"],
                "weight": 1.5,
                "priority_articles": ["34", "35", "36"]
            },
            "responsibility": {
                "keywords": ["ответственность", "штраф", "пеня", "неустойка", "нарушен", "санкц"],
                "weight": 1.8,
                "priority_articles": ["34", "37"]
            },
            "requirements": {
                "keywords": ["требован", "услов", "правил", "норм", "стандарт", "качеств", "гарант"],
                "weight": 1.3,
                "priority_articles": ["33", "34", "32"]
            },
            "changes": {
                "keywords": ["изменен", "расторжен", "прекращен", "пересмотр", "корректировк"],
                "weight": 1.2,
                "priority_articles": ["95", "34", "36"]
            }
        }

        scored_articles = []

        for article in articles:
            score = 0
            article_text = f"{article.title} {article.content}".lower()

            # 1. Прямое совпадение ключевых слов
            for topic, data in topic_weights.items():
                topic_keywords = data["keywords"]
                topic_weight = data["weight"]

                # Проверяем есть ли ключевые слова и в контракте и в статье
                contract_has_topic = any(kw in contract_clean for kw in topic_keywords)
                article_has_topic = any(kw in article_text for kw in topic_keywords)

                if contract_has_topic and article_has_topic:
                    score += topic_weight

                    # Дополнительные баллы за множественные совпадения
                    matches = sum(1 for kw in topic_keywords if kw in contract_clean and kw in article_text)
                    score += matches * 0.3

                    # Дополнительные баллы если статья в списке приоритетных для темы
                    if article.number in data["priority_articles"]:
                        score += 0.8

            # 2. Совпадение числовых значений (для статей с лимитами)
            number_matches = self._find_numeric_matches(contract_clean, article_text)
            score += number_matches * 0.5

            # 3. Длина совпадающих слов (только значимые слова)
            contract_words = set(re.findall(r'\b[а-я]{4,}\b', contract_clean))
            article_words = set(re.findall(r'\b[а-я]{4,}\b', article_text))
            common_words = contract_words & article_words

            score += len(common_words) * 0.1

            if score > 0.3:  # Минимальный порог релевантности
                scored_articles.append((article, score))

        # Сортируем по релевантности
        scored_articles.sort(key=lambda x: x[1], reverse=True)

        return [article for article, score in scored_articles[:10]]  # Топ-10 статей

    def _find_numeric_matches(self, contract_text: str, article_text: str) -> int:
        """Находит совпадения числовых значений (лимиты, сроки и т.д.)"""
        # Ищем числа в статье (4-7 цифр - обычно суммы, сроки)
        article_numbers = set(re.findall(r'\b\d{4,7}\b', article_text))

        # Ищем те же числа в контракте
        contract_numbers = set(re.findall(r'\b\d{4,7}\b', contract_text))

        return len(contract_numbers & article_numbers)