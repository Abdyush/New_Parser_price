from selenium import webdriver
from datetime import datetime



# Функция определяющая функциональные параметры для парсера
def create_browser_options():
    print("[trace] create_browser_options start")
    options = webdriver.ChromeOptions()
    
    # --- Headless и производительность ---
    options.add_argument("--headless=new")  # Запуск без графического интерфейса (ускоряет работу)
    options.add_argument("--disable-gpu")  # Отключает использование видеокарты (уменьшает баги на сервере)
    options.add_argument("--disable-dev-shm-usage")  # Избегает ошибок памяти в Docker/ограниченных средах
    options.add_argument("--no-sandbox")  # Убирает режим песочницы (нужно для некоторых окружений)
    options.add_argument("--disable-extensions")  # Отключает все расширения Chrome
    options.add_argument("--disable-background-networking")  # Запрещает лишние фоновые запросы
    options.add_argument("--disable-background-timer-throttling")  # Не замедляет скрипты во вкладке
    options.add_argument("--disable-renderer-backgrounding")  # Не снижает приоритет рендеринга
    options.add_argument("--disable-sync")  # Отключает синхронизацию с Google-аккаунтом
    options.add_argument("--metrics-recording-only")  # Собирает только минимальную статистику
    options.add_argument("--disable-client-side-phishing-detection")  # Отключает защиту от фишинга (ускоряет)
    options.add_argument("--disable-component-update")  # Отключает обновление компонентов Chrome
    options.add_argument("--disable-default-apps")  # Не загружает стандартные приложения Chrome
    options.add_argument("--window-size=1920,1080")  # Устанавливает размер окна (полный экран)
    options.add_argument("--disable-software-rasterizer")# Без fallback WebGL
    options.add_argument("--mute-audio")
    
    # --- Логирование и безопасный режим ---
    options.add_argument("--log-level=3")  # Минимум логов от Chrome
    options.add_argument("--ignore-certificate-errors")  # Игнорирует ошибки SSL-сертификатов
    options.add_argument("--allow-insecure-localhost")
    
    return options


# Вспомогательная функция для получения атрибутов элемента (для процееса поиска необходимых элементов страницы)
def get_attributes(driver, element) -> dict:
    return driver.execute_script(
        """
        let attr = arguments[0].attributes;
        let items = {}; 
        for (let i = 0; i < attr.length; i++) {
            items[attr[i].name] = attr[i].value;
        }
        return items;
        """,
        element
    )
    
# ---------- Вспомогательная функция ----------
def parse_date(date_str):
    """Простейший парсер дат DD.MM.YYYY"""
    print(f"[trace] parse_date start date_str={date_str}")
    return datetime.strptime(date_str, "%d.%m.%Y").date()
