"""
Выгружает всю БД в seed_data.json.
Запуск: python dump_data.py
"""
from app import app
from backup import save_to_local_file


def main():
    with app.app_context():
        path = 'seed_data.json'
        save_to_local_file(path)
        import json
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f'✅ Сохранено в {path}:')
        print(f'   Пользователей: {len(data["users"])}')
        print(f'   Разделов:      {len(data["sections"])}')
        print(f'   Подразделов:   {len(data["subsections"])}')
        print(f'   Заданий:       {len(data["tasks"])}')
        print(f'   Материалов:    {len(data["materials"])}')
        print(f'   Ответов:       {len(data["submissions"])}')


if __name__ == '__main__':
    main()
