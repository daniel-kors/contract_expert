from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
from werkzeug.utils import secure_filename
import json
from datetime import datetime
import logging

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'dev-secret-key-change-in-production-12345'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# Устанавливаем переменные окружения напрямую
os.environ['GIGACHAT_CREDENTIALS'] = ''  # Замените на реальные учетные данные

# Поддерживаемые форматы файлов
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}


def allowed_file(filename):
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


# Инициализация ИИ-агента с обработкой ошибок
try:
    from agent.contract_analyzer import ContractAnalyzer

    analyzer = ContractAnalyzer()
    AI_AVAILABLE = True
    print("✓ AI Agent initialized successfully")
except Exception as e:
    print(f"✗ AI Agent initialization failed: {e}")
    AI_AVAILABLE = False
    analyzer = None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['GET', 'POST'])
def upload_files():
    if request.method == 'POST':
        # Проверяем, что контракт загружен
        if 'contract_file' not in request.files:
            return jsonify({'error': 'Необходимо загрузить контракт'}), 400

        contract_file = request.files['contract_file']
        notice_file = request.files.get('notice_file')  # Извещение необязательно
        law_type = request.form.get('law_type', '44-ФЗ')

        if contract_file.filename == '':
            return jsonify({'error': 'Не выбран файл контракта'}), 400

        if contract_file and allowed_file(contract_file.filename):
            # Сохраняем контракт
            contract_filename = secure_filename(contract_file.filename)

            # Создаем папку если не существует
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

            contract_path = os.path.join(app.config['UPLOAD_FOLDER'], contract_filename)
            contract_file.save(contract_path)

            # Сохраняем извещение если оно загружено
            notice_path = None
            if notice_file and notice_file.filename != '' and allowed_file(notice_file.filename):
                notice_filename = secure_filename(notice_file.filename)
                notice_path = os.path.join(app.config['UPLOAD_FOLDER'], notice_filename)
                notice_file.save(notice_path)

            # Сохраняем в сессию
            session['contract_path'] = contract_path
            session['notice_path'] = notice_path
            session['law_type'] = law_type

            return redirect(url_for('analyze'))
        else:
            return jsonify({'error': 'Неподдерживаемый формат файла. Разрешены: PDF, DOCX, TXT'}), 400

    return render_template('upload.html')


@app.route('/analyze')
def analyze():
    return render_template('analysis.html')


@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    try:
        if not AI_AVAILABLE:
            return jsonify({
                'error': 'AI сервис временно недоступен. Проверьте настройки GigaChat.',
                'basic_analysis': {'errors': [], 'warnings': []},
                'comparison': {'mismatches': []},
                'ai_analysis': {'issues': [], 'recommendations': ['AI анализ недоступен'],
                                'summary': 'Сервис временно отключен'},
                'summary': {'total_issues': 0, 'critical_issues': 0, 'status': 'unknown'},
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

        contract_path = session.get('contract_path')
        notice_path = session.get('notice_path')
        law_type = session.get('law_type', '44-ФЗ')

        logger.info(f"Starting analysis: contract={contract_path}, notice={notice_path}, law_type={law_type}")

        if not contract_path:
            return jsonify({'error': 'Файл контракта не найден'}), 400

        # Проверяем что контракт существует
        if not os.path.exists(contract_path):
            return jsonify({'error': f'Контракт не найден: {contract_path}'}), 400

        # Проверяем что извещение существует если оно было загружено
        if notice_path and not os.path.exists(notice_path):
            return jsonify({'error': f'Извещение не найдено: {notice_path}'}), 400

        # Логируем информацию о файлах
        contract_text = analyzer.file_processor.extract_text(contract_path)
        logger.info(f"Contract text length: {len(contract_text)}")
        logger.info(f"First 500 chars: {contract_text[:500]}")

        if notice_path:
            notice_text = analyzer.file_processor.extract_text(notice_path)
            logger.info(f"Notice text length: {len(notice_text)}")

        # Анализ контракта
        result = analyzer.analyze_contract(
            contract_path=contract_path,
            notice_path=notice_path,
            law_type=law_type
        )

        # Сохраняем результат в сессию
        session['analysis_result'] = result

        logger.info("Analysis completed successfully")
        return jsonify(result)

    except Exception as e:
        logger.error(f"Analysis error: {str(e)}", exc_info=True)
        return jsonify({'error': f'Ошибка анализа: {str(e)}'}), 500


@app.route('/results')
def results():
    result = session.get('analysis_result', {})
    return render_template('results.html', result=result)


# Простая заглушка для тестирования
@app.route('/test')
def test():
    return jsonify({
        'status': 'OK',
        'ai_available': AI_AVAILABLE,
        'upload_folder': app.config['UPLOAD_FOLDER'],
        'upload_folder_exists': os.path.exists(app.config['UPLOAD_FOLDER'])
    })


@app.route('/chat')
def chat():
    return render_template('chat.html')


@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.json
    question = data.get('question')

    if not question:
        return jsonify({'error': 'Вопрос не может быть пустым'}), 400

    try:
        # Используем GigaChat для ответа на вопросы
        if AI_AVAILABLE:
            from agent.gigachat_client import GigaChatClient
            giga_client = GigaChatClient()
            response = giga_client.ask_question(question, {})
        else:
            response = "AI сервис временно недоступен. Проверьте настройки GigaChat."

        return jsonify({'answer': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Создаем папку для загрузок
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    print("=" * 50)
    print("Контрактный эксперт")
    print("=" * 50)
    print(f"AI Agent available: {AI_AVAILABLE}")
    print(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    print(f"Server running on: http://localhost:5000")
    print("=" * 50)

    # Запускаем без debug mode чтобы избежать проблем с .env
    app.run(debug=True, host='0.0.0.0', port=5000)