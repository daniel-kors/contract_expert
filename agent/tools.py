import PyPDF2
from docx import Document
import re
from typing import Dict, List, Any, Optional


class FileProcessor:
    """Обработка файлов контрактов"""

    def extract_text(self, file_path: str) -> str:
        """Извлекает текст из файла с поддержкой разных регистров расширений"""
        try:
            file_path_lower = file_path.lower()

            if file_path_lower.endswith('.pdf'):
                return self._extract_from_pdf(file_path)
            elif file_path_lower.endswith('.docx'):
                return self._extract_from_docx(file_path)
            elif file_path_lower.endswith('.txt'):
                return self._extract_from_txt(file_path)
            else:
                return self._extract_with_fallback(file_path)
        except Exception as e:
            print(f"Error extracting text from {file_path}: {e}")
            return f"Ошибка чтения файла: {str(e)}"

    def _extract_from_pdf(self, file_path: str) -> str:
        """Извлекает текст из PDF файла"""
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)

                if reader.is_encrypted:
                    try:
                        reader.decrypt('')
                    except:
                        return "PDF файл защищен паролем"

                text = ""
                for page in reader.pages:
                    try:
                        text += page.extract_text() + "\n"
                    except:
                        continue

                return text if text.strip() else "Не удалось извлечь текст из PDF"

        except Exception as e:
            raise Exception(f"Ошибка чтения PDF: {str(e)}")

    def _extract_from_docx(self, file_path: str) -> str:
        """Извлекает текст из DOCX файла с улучшенной обработкой"""
        try:
            doc = Document(file_path)
            full_text = []

            # Извлекаем текст из параграфов
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    full_text.append(paragraph.text)

            # Извлекаем текст из таблиц
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            full_text.append(cell.text)

            return "\n".join(full_text)
        except Exception as e:
            raise Exception(f"Ошибка чтения DOCX: {str(e)}")

    def _extract_from_txt(self, file_path: str) -> str:
        """Извлекает текст из TXT файла"""
        try:
            encodings = ['utf-8', 'cp1251', 'windows-1251', 'iso-8859-1']
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as file:
                        return file.read()
                except UnicodeDecodeError:
                    continue
            raise Exception("Не удалось декодировать файл")
        except Exception as e:
            raise Exception(f"Ошибка чтения TXT: {str(e)}")

    def _extract_with_fallback(self, file_path: str) -> str:
        """Резервный метод извлечения текста"""
        try:
            return self._extract_from_txt(file_path)
        except:
            raise Exception("Неподдерживаемый формат файла")


class ContractValidator:
    """Улучшенная валидация контрактов"""

    def __init__(self):
        # Более гибкие паттерны для поиска разделов
        self.mandatory_clauses_44 = {
            "предмет контракта": [
                "предмет контракта", "предмет договора", "i. предмет", "1. предмет"
            ],
            "цена контракта": [
                "цена контракта", "цена договора", "стоимость", "ii. цена",
                "2. цена", "цена и порядок расчетов"
            ],
            "срок исполнения": [
                "срок исполнения", "срок поставки", "срок действия",
                "iii. порядок", "3. порядок", "дата начала", "дата окончания"
            ],
            "порядок оплаты": [
                "порядок оплаты", "условия оплаты", "расчеты", "оплата",
                "срок оплаты", "2.4", "2.5", "2.6"
            ],
            "ответственность сторон": [
                "ответственность сторон", "ответственность", "штраф",
                "пеня", "неустойка", "vii. ответственность", "7. ответственность"
            ],
            "условия расторжения": [
                "условия расторжения", "расторжение", "односторонний отказ",
                "xi. срок действия", "11. срок действия"
            ],
            "гарантийные обязательства": [
                "гарантийные обязательства", "гарантия", "гарантийный срок",
                "качество товара", "vi. качество", "6. качество"
            ]
        }

    def basic_validation(self, contract_text: str, law_type: str) -> Dict[str, Any]:
        """Улучшенная проверка обязательных условий"""
        errors = []
        warnings = []

        # Приводим текст к нижнему регистру для поиска
        text_lower = contract_text.lower()

        # Проверяем наличие обязательных разделов
        for clause_name, patterns in self.mandatory_clauses_44.items():
            found = any(pattern in text_lower for pattern in patterns)

            if not found:
                # Проверяем наличие ключевых слов, связанных с разделом
                if self._check_related_keywords(clause_name, text_lower):
                    warnings.append({
                        'type': 'clause_format',
                        'clause': clause_name,
                        'severity': 'warning',
                        'message': f'Раздел "{clause_name}" присутствует, но имеет нестандартное название'
                    })
                else:
                    errors.append({
                        'type': 'missing_clause',
                        'clause': clause_name,
                        'severity': 'critical',
                        'message': f'Отсутствует обязательный раздел: {clause_name}'
                    })

        # Проверка цены контракта
        price_found = self._find_price(contract_text)
        if not price_found:
            errors.append({
                'type': 'missing_price',
                'severity': 'critical',
                'message': 'Не обнаружена цена контракта'
            })

        # Проверка реквизитов
        requisites_check = self._check_requisites(contract_text)
        warnings.extend(requisites_check)

        return {
            'errors': errors,
            'warnings': warnings,
            'mandatory_clauses_checked': list(self.mandatory_clauses_44.keys())
        }

    def _check_related_keywords(self, clause_name: str, text: str) -> bool:
        """Проверяет наличие ключевых слов, связанных с разделом"""
        keyword_map = {
            "предмет контракта": ["поставщик", "заказчик", "товар", "продукция"],
            "цена контракта": ["рубл", "копеек", "сумма", "стоимость"],
            "порядок оплаты": ["оплата", "платеж", "перечислен", "счет"],
            "ответственность сторон": ["штраф", "пеня", "ответственность", "нарушен"],
            "условия расторжения": ["расторжен", "отказ", "прекращен"],
            "гарантийные обязательства": ["гарантия", "качество", "брак", "замен"]
        }

        keywords = keyword_map.get(clause_name, [])
        return any(keyword in text for keyword in keywords)

    def _find_price(self, text: str) -> bool:
        """Ищет цену контракта"""
        price_patterns = [
            r'цена[\s\S]{1,200}?(\d{1,}[\d\s]*[.,]\d{2})',
            r'стоимость[\s\S]{1,200}?(\d{1,}[\d\s]*[.,]\d{2})',
            r'(\d{1,}[\d\s]*[.,]\d{2})\s*рубл',
            r'цена контракта[^0-9]{0,100}(\d{1,}[\d\s]*[.,]\d{2})'
        ]

        return any(re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                   for pattern in price_patterns)

    def _check_requisites(self, text: str) -> List[Dict]:
        """Проверяет наличие реквизитов"""
        warnings = []
        text_lower = text.lower()

        requisites_to_check = {
            "инн": ["инн", "идентификационный номер"],
            "расчетный счет": ["расчетный счет", "р/с", "р/счет"],
            "бик": ["бик", "банковский идентификационный код"],
            "кпп": ["кпп", "код причины"],
            "огрн": ["огрн", "основной государственный регистрационный номер"]
        }

        missing = []
        for req_name, patterns in requisites_to_check.items():
            if not any(pattern in text_lower for pattern in patterns):
                missing.append(req_name)

        if missing:
            warnings.append({
                'type': 'missing_requisites',
                'severity': 'warning',
                'message': f'Возможно отсутствуют реквизиты: {", ".join(missing)}'
            })

        return warnings

    def compare_with_notice(self, contract_text: str, notice_text: str) -> Dict[str, Any]:
        """Сравнение контракта с извещением"""
        mismatches = []

        # Сравнение цены
        contract_price = self._extract_price_value(contract_text)
        notice_price = self._extract_price_value(notice_text)

        if contract_price and notice_price and contract_price != notice_price:
            mismatches.append({
                'parameter': 'price',
                'contract_value': contract_price,
                'notice_value': notice_price,
                'message': f'Цена контракта ({contract_price}) не соответствует цене в извещении ({notice_price})'
            })

        return {
            'mismatches': mismatches,
            'parameters_compared': ['price']
        }

    def _extract_price_value(self, text: str) -> Optional[str]:
        """Извлекает числовое значение цены"""
        # Ищем паттерны с ценами
        patterns = [
            r'цена[\s\S]{1,200}?(\d{1,}[\d\s]*[.,]\d{2})',
            r'стоимость[\s\S]{1,200}?(\d{1,}[\d\s]*[.,]\d{2})',
            r'(\d{1,}[\d\s]*[.,]\d{2})\s*рубл'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1)

        return None