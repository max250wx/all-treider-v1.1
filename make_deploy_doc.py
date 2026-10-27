"""
Генератор .docx документа для развёртывания проекта на мощном ПК.
Создаёт: DEPLOY_GUIDE.docx
"""

from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os


def add_hyperlink(paragraph, url, text, color="0563C1", underline=True):
    """Добавляет кликабельную гиперссылку."""
    part = paragraph.part
    r_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)

    new_run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")

    if color:
        c = OxmlElement("w:color")
        c.set(qn("w:val"), color)
        rPr.append(c)
    if underline:
        u = OxmlElement("w:u")
        u.set(qn("w:val"), "single")
        rPr.append(u)

    new_run.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink


def add_code_block(doc, code_lines, indent_level=0):
    """Добавляет блок кода с серым фоном."""
    for line in code_lines:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(1 + indent_level * 0.5)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)

        # Серый фон
        pPr = p._p.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), "F2F2F2")
        pPr.append(shd)

        run = p.add_run(line if line else " ")
        run.font.name = "Consolas"
        run.font.size = Pt(9.5)


def add_bullet(doc, text, level=0):
    p = doc.add_paragraph(text, style="List Bullet" if level == 0 else "List Bullet 2")
    return p


def add_heading_colored(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    return h


def build_document():
    doc = Document()

    # ── Титул ──
    title = doc.add_heading("", 0)
    run = title.add_run("AI-трейдер MOEX\nРуководство по развёртыванию")
    run.font.size = Pt(28)
    run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    subtitle = doc.add_paragraph()
    sub_run = subtitle.add_run("Версия 1.0  •  Октябрь 2026")
    sub_run.font.size = Pt(12)
    sub_run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()
    doc.add_paragraph()

    # Оглавление
    add_heading_colored(doc, "Содержание", 1)
    toc_items = [
        "1. Требования к системе",
        "2. Быстрая установка (автоматическая)",
        "3. Ручная установка (пошагово)",
        "4. Получение токена T-Invest API",
        "5. Установка Ollama и моделей AI",
        "6. Настройка и запуск",
        "7. Проверка работоспособности",
        "8. Решение проблем",
        "9. Ссылки и ресурсы",
    ]
    for item in toc_items:
        p = doc.add_paragraph(item)
        p.paragraph_format.left_indent = Cm(1)

    doc.add_page_break()

    # ── 1. Требования ──
    add_heading_colored(doc, "1. Требования к системе", 1)

    doc.add_paragraph("Для работы AI-трейдера MOEX необходимы следующие компоненты:")

    doc.add_heading("Минимальные (для Qwen 7B)", 2)
    add_bullet(doc, "Операционная система: Windows 10/11 или Linux")
    add_bullet(doc, "Python 3.12 или выше")
    add_bullet(doc, "GPU: NVIDIA с 6+ ГБ VRAM (например RTX 3050 / 4050)")
    add_bullet(doc, "RAM: 16 ГБ")
    add_bullet(doc, "Диск: 20 ГБ свободно")

    doc.add_heading("Рекомендуемые (для Qwen 14B)", 2)
    add_bullet(doc, "Операционная система: Windows 11 или Ubuntu 22.04+")
    add_bullet(doc, "GPU: NVIDIA с 12+ ГБ VRAM (RTX 3060 12GB, 4070, 4080)")
    add_bullet(doc, "RAM: 32 ГБ")
    add_bullet(doc, "Диск: 40 ГБ свободно")

    doc.add_heading("Максимальные (для Qwen 32B)", 2)
    add_bullet(doc, "GPU: NVIDIA с 24+ ГБ VRAM (RTX 3090, 4090, A5000)")
    add_bullet(doc, "RAM: 64 ГБ")
    add_bullet(doc, "Диск: 80 ГБ свободно")

    doc.add_page_break()

    # ── 2. Быстрая установка ──
    add_heading_colored(doc, "2. Быстрая установка (автоматическая)", 1)

    doc.add_paragraph(
        "Самый простой способ — использовать готовый скрипт deploy.bat. "
        "Он установит все зависимости, скачает модели и проверит систему."
    )

    doc.add_heading("Шаги:", 2)
    add_bullet(doc, "Скачайте папку проекта C:\\trading на новый ПК")
    add_bullet(doc, "Откройте PowerShell от имени администратора")
    add_bullet(doc, "Выполните команды ниже")

    add_code_block(doc, [
        "cd C:\\trading",
        ".\\deploy.bat",
    ])

    doc.add_paragraph(
        "Скрипт выполнит 4 шага: установка Python-пакетов, проверка Ollama, "
        "скачивание моделей, диагностика системы."
    )

    doc.add_heading("Ожидаемый результат", 2)
    add_code_block(doc, [
        "[1/4] Установка Python-пакетов... OK",
        "[2/4] Проверка Ollama... OK",
        "[3/4] Скачивание моделей... OK",
        "[4/4] Проверка окружения... OK",
        "",
        "============================================",
        "  ГОТОВО",
        "============================================",
    ])

    doc.add_page_break()

    # ── 3. Ручная установка ──
    add_heading_colored(doc, "3. Ручная установка (пошагово)", 1)

    doc.add_paragraph(
        "Если автоматическая установка не сработала, выполните шаги вручную."
    )

    doc.add_heading("Шаг 3.1. Установить Python 3.12+", 2)
    p = doc.add_paragraph()
    p.add_run("Скачайте с официального сайта: ")
    add_hyperlink(p, "https://www.python.org/downloads/", "python.org/downloads")

    doc.add_paragraph("При установке обязательно отметьте галочку «Add Python to PATH».")

    doc.add_paragraph("Проверьте установку:")
    add_code_block(doc, ["python --version"])
    doc.add_paragraph("Ожидаемый вывод: Python 3.12.x")

    doc.add_heading("Шаг 3.2. Создать рабочую папку", 2)
    add_code_block(doc, [
        "mkdir C:\\trading",
        "cd C:\\trading",
    ])

    doc.add_heading("Шаг 3.3. Установить зависимости", 2)
    add_code_block(doc, [
        "python -m pip install --upgrade pip",
        "python -m pip install pandas numpy requests",
        "python -m pip install t-tech-investments --index-url https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple",
        "python -m pip install transformers torch",
        "python -m pip install aiogram",
        "python -m pip install python-docx",
    ])

    doc.add_paragraph("Или одной командой через requirements.txt:")
    add_code_block(doc, ["python -m pip install -r requirements.txt"])

    doc.add_page_break()

    # ── 4. Токен T-Invest ──
    add_heading_colored(doc, "4. Получение токена T-Invest API", 1)

    doc.add_paragraph(
        "Для сбора данных о стакане и сделках необходим токен T-Invest API. "
        "Токен бесплатный, выдаётся на 1 год."
    )

    doc.add_heading("Пошаговая инструкция", 2)

    p = doc.add_paragraph("1. Откройте страницу управления API: ")
    add_hyperlink(p, "https://www.tbank.ru/invest/settings/api/", "tbank.ru/invest/settings/api")

    p = doc.add_paragraph("2. Войдите в аккаунт Т-Инвестиций.")
    p = doc.add_paragraph("3. Убедитесь, что функция «Подтверждение сделок кодом» ОТКЛЮЧЕНА.")
    p = doc.add_paragraph("4. Нажмите «Выпустить токен».")
    p = doc.add_paragraph("5. Скопируйте токен (начинается с t.).")

    doc.add_heading("Важно", 2)
    add_bullet(doc, "Токен нужен БОЕВОЙ (read-only), не Sandbox")
    add_bullet(doc, "Никому не передавайте токен")
    add_bullet(doc, "Токен действует 1 год, потом нужно перевыпустить")

    doc.add_heading("Куда вставить токен", 2)
    doc.add_paragraph("В файле config.py замените строку:")
    add_code_block(doc, [
        'TOKEN = "t.ВАШ_НОВЫЙ_ТОКЕН"',
    ])

    doc.add_page_break()

    # ── 5. Ollama ──
    add_heading_colored(doc, "5. Установка Ollama и моделей AI", 1)

    doc.add_paragraph(
        "Ollama — бесплатная программа для запуска локальных AI-моделей. "
        "Работает без интернета после установки."
    )

    doc.add_heading("Шаг 5.1. Установить Ollama", 2)

    p = doc.add_paragraph()
    p.add_run("Windows: скачайте с ")
    add_hyperlink(p, "https://ollama.com/download/windows", "ollama.com/download/windows")

    doc.add_paragraph("Или через winget:")
    add_code_block(doc, ["winget install Ollama.Ollama"])

    doc.add_paragraph("Linux:")
    add_code_block(doc, ["curl -fsSL https://ollama.com/install.sh | sh"])

    doc.add_heading("Шаг 5.2. Добавить в PATH (Windows)", 2)
    doc.add_paragraph("Откройте новое окно PowerShell:")
    add_code_block(doc, [
        '$env:Path += ";C:\\Users\\<USER>\\AppData\\Local\\Programs\\Ollama"',
        "ollama --version",
    ])
    doc.add_paragraph("Замените <USER> на ваше имя пользователя Windows.")

    doc.add_heading("Шаг 5.3. Скачать модели", 2)

    doc.add_paragraph("Для GPU с 6 ГБ VRAM (Qwen 7B):")
    add_code_block(doc, ["ollama pull qwen2.5:7b"])

    doc.add_paragraph("Для GPU с 12+ ГБ VRAM (Qwen 14B):")
    add_code_block(doc, ["ollama pull qwen2.5:14b"])

    doc.add_paragraph("Для GPU с 24+ ГБ VRAM (Qwen 32B):")
    add_code_block(doc, ["ollama pull qwen2.5:32b"])

    doc.add_heading("Размеры и производительность", 2)

    table = doc.add_table(rows=5, cols=4)
    table.style = "Light Grid Accent 1"
    headers = ["Модель", "VRAM", "Скорость", "Качество"]
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            for r in p.runs:
                r.bold = True

    data = [
        ("Qwen 3B", "3 ГБ", "60-100 т/с", "Базовое"),
        ("Qwen 7B", "5 ГБ", "20-40 т/с", "Хорошее"),
        ("Qwen 14B", "9 ГБ", "15-30 т/с", "Отличное"),
        ("Qwen 32B", "20 ГБ", "5-15 т/с", "Максимум"),
    ]
    for i, row in enumerate(data, start=1):
        for j, val in enumerate(row):
            table.rows[i].cells[j].text = val

    doc.add_page_break()

    # ── 6. Настройка и запуск ──
    add_heading_colored(doc, "6. Настройка и запуск", 1)

    doc.add_heading("Шаг 6.1. Выбрать модель", 2)
    doc.add_paragraph("В файле config.py выберите модель под ваш GPU:")
    add_code_block(doc, [
        "# Для 6 ГБ VRAM:",
        'MODEL = "qwen2.5:7b"',
        "",
        "# Для 12+ ГБ VRAM:",
        '# MODEL = "qwen2.5:14b"',
        "",
        "# Для 24+ ГБ VRAM:",
        '# MODEL = "qwen2.5:32b"',
    ])

    doc.add_heading("Шаг 6.2. Настроить тикеры", 2)
    doc.add_paragraph("В том же config.py укажите тикеры для сбора:")
    add_code_block(doc, [
        'TICKERS = ["GAZP", "RUAL"]',
        '# Альтернативы: "SBER", "LKOH", "VTBR", "MTLR", "NVTK", "YDEX"',
    ])

    doc.add_heading("Шаг 6.3. Запустить систему", 2)
    doc.add_paragraph(
        "Откройте 3 отдельных окна PowerShell. В каждом запустите свою команду."
    )

    doc.add_paragraph("Окно 1 — блокировка сна:")
    add_code_block(doc, ["cd C:\\trading", "python keep_awake.py"])

    doc.add_paragraph("Окно 2 — watchdog (автозапуск скриптов):")
    add_code_block(doc, ["cd C:\\trading", "python watchdog.py"])

    doc.add_paragraph("Окно 3 — AI-тест:")
    add_code_block(doc, ["cd C:\\trading", "python ai_agent_local.py"])

    doc.add_page_break()

    # ── 7. Проверка ──
    add_heading_colored(doc, "7. Проверка работоспособности", 1)

    doc.add_heading("Шаг 7.1. Самодиагностика", 2)
    add_code_block(doc, ["python selfdiag.py"])

    doc.add_paragraph("Отчёт покажет состояние компонентов:")
    add_bullet(doc, "[OK] — компонент работает")
    add_bullet(doc, "[WARN] — предупреждение (можно игнорировать)")
    add_bullet(doc, "[FAIL] — ошибка (требуется исправление)")

    doc.add_heading("Шаг 7.2. Проверка процессов", 2)
    add_code_block(doc, ["Get-Process python | Select-Object Id, CPU, StartTime"])

    doc.add_paragraph("Должно быть 3 процесса:")
    add_bullet(doc, "keep_awake.py — блокировка сна")
    add_bullet(doc, "watchdog.py — управление")
    add_bullet(doc, "orderflow_rest.py — сбор данных")
    add_bullet(doc, "rvi_collector.py — сбор RVI")

    doc.add_heading("Шаг 7.3. Проверка данных", 2)
    add_code_block(doc, [
        "(Get-Content C:\\trading\\trades_GAZP.csv).Count",
        "(Get-Content C:\\trading\\trades_RUAL.csv).Count",
        "(Get-Content C:\\trading\\rvi_data.csv).Count",
    ])

    doc.add_paragraph(
        "Числа должны расти каждые 5 минут. Если не растут — "
        "проверьте watchdog.log."
    )

    doc.add_page_break()

    # ── 8. Проблемы ──
    add_heading_colored(doc, "8. Решение проблем", 1)

    problems = [
        (
            "Ollama не использует GPU",
            [
                "Проверьте: nvidia-smi во время работы модели",
                "Обновите драйвер NVIDIA до версии 560+",
                "Установите CUDA Toolkit 12.x",
                "Переустановите Ollama с флагом --cuda",
            ],
        ),
        (
            "Модель медленно работает (оффлоад на CPU)",
            [
                "Уменьшите контекст: num_ctx=2048 в options",
                "Используйте квантование Q4 вместо Q8",
                "Возьмите меньшую модель (7B вместо 14B)",
            ],
        ),
        (
            "Ошибка токена T-Invest (Unauthenticated)",
            [
                "Проверьте, что токен начинается с 't.'",
                "Убедитесь, что токен БОЕВОЙ (не Sandbox)",
                "Проверьте, что токен не просрочен",
                "В настройках отключите подтверждение сделок кодом",
            ],
        ),
        (
            "Модуль не найден (ModuleNotFoundError)",
            [
                "Проверьте установку: pip list",
                "Переустановите: pip install --force-reinstall <модуль>",
                "Для fasttext: pip install fasttext-wheel",
            ],
        ),
        (
            "Скрипт падает через 10-15 минут",
            [
                "Это известная проблема T-Invest API",
                "Решение: watchdog.py автоматически перезапустит",
                "Проверьте watchdog.log на строки [!] перезапуск",
            ],
        ),
        (
            "Китайские иероглифы в ответах Qwen",
            [
                "Убедитесь, что промпт содержит 'Только русский язык'",
                "Установите temperature=0.1 (не выше)",
                "Попробуйте Saiga YandexGPT 8B как альтернативу",
            ],
        ),
    ]

    for title_text, tips in problems:
        doc.add_heading(title_text, 2)
        for tip in tips:
            add_bullet(doc, tip)

    doc.add_page_break()

    # ── 9. Ссылки ──
    add_heading_colored(doc, "9. Ссылки и ресурсы", 1)

    doc.add_heading("Официальные ресурсы", 2)

    links = [
        ("Python", "https://www.python.org/downloads/", "Скачать Python 3.12+"),
        ("Ollama", "https://ollama.com/download", "Скачать Ollama"),
        ("T-Invest API", "https://www.tbank.ru/invest/settings/api/", "Управление токенами"),
        ("T-Invest SDK", "https://opensource.tbank.ru/", "Документация"),
        ("MOEX ISS", "https://iss.moex.com/iss/reference/", "API Мосбиржи"),
        ("MOEX AlgoPack", "https://www.moex.com/ru/algopack", "Алгоритмические данные"),
    ]

    for name, url, description in links:
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(name + " — ")
        run.bold = True
        add_hyperlink(p, url, url)
        p.add_run(" — " + description)

    doc.add_heading("AI-модели для русского языка", 2)

    models = [
        ("Qwen 2.5", "https://ollama.com/library/qwen2.5", "Лучшая универсальная"),
        ("Saiga YandexGPT", "https://ollama.com/library/saiga_yandexgpt", "Русскоязычная"),
        ("RusMind", "https://huggingface.co/DICPlay/RusMind-3.5.1-Momentum", "Русская 3B"),
        ("GigaChat API", "https://developers.sber.ru/", "Облачная, бесплатно 365M токенов"),
    ]

    for name, url, description in models:
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(name + " — ")
        run.bold = True
        add_hyperlink(p, url, url)
        p.add_run(" — " + description)

    doc.add_heading("Хостинг для бота (бесплатно)", 2)

    hosting = [
        ("Amvera", "https://amvera.ru/", "Российский, 0₽ стартовый"),
        ("BotHost", "https://bothost.ru/", "0₽ навсегда, лёгкие боты"),
        ("GitHub Actions", "https://github.com/features/actions", "Запуск по расписанию"),
    ]

    for name, url, description in hosting:
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(name + " — ")
        run.bold = True
        add_hyperlink(p, url, url)
        p.add_run(" — " + description)

    doc.add_heading("Дополнительные инструменты", 2)

    tools = [
        ("nvidia-smi", "https://developer.nvidia.com/nvidia-system-management-interface", "Мониторинг GPU"),
        ("PowerShell Docs", "https://learn.microsoft.com/ru-ru/powershell/", "Команды Windows"),
        ("pandas docs", "https://pandas.pydata.org/docs/", "Работа с данными"),
        ("backtesting.py", "https://kernc.github.io/backtesting.py/", "Бэктестинг стратегий"),
    ]

    for name, url, description in tools:
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(name + " — ")
        run.bold = True
        add_hyperlink(p, url, url)
        p.add_run(" — " + description)

    # ── Финальный блок ──
    doc.add_page_break()
    add_heading_colored(doc, "Быстрая шпаргалка команд", 1)

    doc.add_heading("Установка", 2)
    add_code_block(doc, [
        "cd C:\\trading",
        "python -m pip install -r requirements.txt",
        "ollama pull qwen2.5:7b",
    ])

    doc.add_heading("Запуск (3 окна)", 2)
    add_code_block(doc, [
        "# Окно 1",
        "python keep_awake.py",
        "",
        "# Окно 2",
        "python watchdog.py",
        "",
        "# Окно 3 (тест)",
        "python ai_agent_local.py",
    ])

    doc.add_heading("Проверка", 2)
    add_code_block(doc, [
        "python selfdiag.py",
        "Get-Process python",
        "(Get-Content C:\\trading\\trades_GAZP.csv).Count",
    ])

    doc.add_heading("Остановка", 2)
    add_code_block(doc, [
        "# В каждом окне: Ctrl+C",
        "# Или все сразу:",
        "Stop-Process -Name python -Force",
    ])

    # ── Footer ──
    doc.add_paragraph()
    doc.add_paragraph()
    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer.add_run("AI-трейдер MOEX © 2026\nДокумент создан автоматически")
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    return doc


if __name__ == "__main__":
    print("Генерация DEPLOY_GUIDE.docx...")
    doc = build_document()
    output = "DEPLOY_GUIDE.docx"
    doc.save(output)
    full_path = os.path.abspath(output)
    print("Готово: " + full_path)
    print("Размер: " + str(round(os.path.getsize(output) / 1024, 1)) + " KB")
    print()
    print("Откройте файл в Word или отправьте на другой ПК.")