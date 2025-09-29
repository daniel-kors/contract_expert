import os
import json
from typing import Dict, List, Any
from .tools import FileProcessor, ContractValidator
from .gigachat_client import GigaChatClient


class ContractAnalyzer:
    def __init__(self):
        self.file_processor = FileProcessor()
        self.validator = ContractValidator()
        self.giga_client = GigaChatClient()

    def analyze_contract(self, contract_path: str, notice_path: str = None, law_type: str = "44-ФЗ") -> Dict[str, Any]:
        """Основной метод анализа контракта"""

        # Извлекаем текст из контракта
        contract_text = self.file_processor.extract_text(contract_path)

        # Извлекаем текст из извещения если оно есть
        notice_text = None
        if notice_path:
            notice_text = self.file_processor.extract_text(notice_path)

        # Базовый анализ
        basic_analysis = self.validator.basic_validation(contract_text, law_type)

        # Сравнение с извещением (только если извещение есть)
        comparison = {'mismatches': [], 'parameters_compared': []}
        if notice_text:
            comparison = self.validator.compare_with_notice(contract_text, notice_text)

        # Глубокий анализ с помощью GigaChat
        ai_analysis = self.giga_client.analyze_contract(
            contract_text=contract_text,
            notice_text=notice_text,
            law_type=law_type
        )

        # Формируем итоговый отчет
        result = {
            'basic_analysis': basic_analysis,
            'comparison': comparison,
            'ai_analysis': ai_analysis,
            'summary': self._generate_summary(basic_analysis, comparison, ai_analysis),
            'timestamp': self._get_timestamp(),
            'has_notice': notice_text is not None
        }

        return result

    def _generate_summary(self, basic: Dict[str, Any], comparison: Dict[str, Any], ai: Dict[str, Any]) -> Dict[
        str, Any]:
        """Генерирует сводку по результатам анализа"""
        total_issues = (
                len(basic.get('errors', [])) +
                len(comparison.get('mismatches', [])) +
                len(ai.get('issues', []))
        )

        return {
            'total_issues': total_issues,
            'critical_issues': len([issue for issue in basic.get('errors', []) if issue.get('severity') == 'critical']),
            'recommendations': ai.get('recommendations', []),
            'status': 'high_risk' if total_issues > 5 else 'medium_risk' if total_issues > 0 else 'low_risk'
        }

    def _get_timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

