# GDG Krakow Tool (Agent Development Kit)

Этот проект представляет собой агента на базе [Google Agent Development Kit (ADK) 2.0](https://adk.dev/), написанного на Python. Он использует возможности Vertex AI (в частности, модель Gemini).

## Настройка локального окружения

1. Убедитесь, что у вас установлен Python (версии 3.9+).
2. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/aplachykau-git/gdg_agents.git
   cd gdg_agents
   ```

3. Инициализируйте виртуальное окружение и установите зависимости (если вы этого еще не сделали):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install google-adk
   ```

4. Авторизуйтесь в Google Cloud для использования Vertex AI:
   Для того, чтобы скрипты могли получать доступ к моделям Vertex AI, необходимо настроить Application Default Credentials (ADC):
   ```bash
   bash <(curl -sSL https://storage.googleapis.com/cloud-samples-data/adc/setup_adc.sh)
   ```
   *При запуске введите ваш Project ID (например, `gdg-agents-496611`) и пройдите авторизацию в браузере.*

## Переменные окружения (.env)

В проекте используется файл `.env`, который не коммитится в Git для безопасности.
Создайте файл `.env` в директории `gdg_agent/` со следующим содержимым:

```env
# Использовать Vertex AI (1) или Google AI Studio (0)
GOOGLE_GENAI_USE_VERTEXAI=1

# Ваш проект в Google Cloud
GOOGLE_CLOUD_PROJECT=gdg-agents-496611

# Регион, в котором находятся модели (по умолчанию us-central1)
GOOGLE_CLOUD_LOCATION=us-central1
```

*(Если вы хотите использовать обычный API ключ от Google AI Studio вместо Vertex AI, установите `GOOGLE_GENAI_USE_VERTEXAI=0` и добавьте строку `GOOGLE_API_KEY="ваш-ключ"`).*

## Запуск агента

1. Активируйте виртуальное окружение:
   ```bash
   source .venv/bin/activate
   ```

2. Перейдите в папку агента:
   ```bash
   cd gdg_agent
   ```

3. Запустите ADK Developer UI (веб-интерфейс):
   ```bash
   adk web --port 8000
   ```
   
4. Откройте в браузере `http://localhost:8000`, чтобы взаимодействовать с вашим агентом через интерфейс.

## Разработка

Главный код агента находится в файле `gdg_agent/agent.py`. Вы можете изменять системные инструкции, добавлять новые Python-инструменты (`tools`) и менять используемую модель.
