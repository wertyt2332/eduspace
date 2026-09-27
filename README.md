# EduSpace — платформа дистанционного обучения

Минималистичная веб-платформа для дистанционного обучения.
Роли: **админ**, **учитель**, **ученик**.

## Что уже работает (этап 1)

- Вход по логину/паролю
- Автоматическое создание админа при первом запуске
- Разделение кабинетов по ролям
- Адаптивный минималистичный интерфейс

## Быстрый старт (локально)

```bash
git clone <URL-репозитория>
cd eduspace

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
# открой .env и поменяй SECRET_KEY и ADMIN_PASSWORD

python app.py
```

Открой http://localhost:5000 — увидишь страницу входа.

**Логин/пароль админа** = значения `ADMIN_LOGIN` и `ADMIN_PASSWORD` из `.env`
(по умолчанию `admin` / `admin123` — **обязательно поменяй**).

## Деплой на Render

1. Залей проект в GitHub.
2. Зайди на [render.com](https://render.com), **New → Web Service** → подключи репозиторий.
3. Render подхватит `render.yaml` автоматически. Если нет:
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn -b 0.0.0.0:$PORT app:app`
4. В **Environment** задай переменные:
   - `SECRET_KEY` — длинная случайная строка
   - `ADMIN_LOGIN`, `ADMIN_PASSWORD` — учётка админа
   - `SUPABASE_URL`, `SUPABASE_KEY` — заполним на этапе 5
5. Deploy.

## Структура

```
blueprints/   — модули по ролям (auth, admin, teacher, student)
models.py     — модели БД (User, Section, Subsection, Task, Submission)
templates/    — Jinja2-шаблоны (Bootstrap 5)
static/       — CSS
config.py     — конфигурация
app.py        — точка входа
```

## Следующие этапы

- [x] Этап 1. Фундамент + авторизация
- [ ] Этап 2. Панель админа (пользователи, разделы, CSV-импорт)
- [ ] Этап 3. Панель учителя (подразделы, задания, назначение учеников)
- [ ] Этап 4. Панель ученика (задания, ответы, оценки)
- [ ] Этап 5. Supabase Storage для файлов
- [ ] Этап 6. Финализация деплоя
