"""
Очистка проекта для деплоя
Удаляет все лишние файлы, оставляя только необходимые для production
"""

import os
import shutil

# Файлы для удаления
files_to_delete = [
    # Документация разработки
    'SETUP_INSTRUCTIONS.md',
    'LAUNCH_CHECKLIST.md',
    'TESTING_GUIDE.md',
    'TROUBLESHOOTING.md',
    'QUICK_START.md',
    'PRIVACY_POLICY.md',
    'CONSENT.md',
    'TELEGRAM_GROUP_SETUP.md',
    'ADMIN_PANEL_GUIDE.md',
    'REFERRAL_UTM_SYSTEM.md',
    'UTM_REFERRAL_QUICKSTART.md',
    'DAILY_REPORTS_GUIDE.md',
    'MASTERS_CALENDAR_GUIDE.md',
    'ADMIN_FULL_GUIDE.md',
    'MVP_MIGRATION_STEPS.md',
    'README_MVP.md',

    # Тестовые файлы
    'seed_database.py',
    'test_utm_system.py',
    'test_metro_client.py',
    'test_edge_cases.py',
    'test_chaos_scenarios.py',
    'run_all_tests.py',
    'test_masters_scenarios.py',

    # Скрипты миграции и бэкапы
    'admin_app_FULL_BACKUP.py',
    'cleanup_mvp.py',
    'admin_app_mvp.py',
    'migrate_to_mvp.py',
    'daily_report_scheduler.py',  # Дубликат функционала

    # Временные файлы
    'base_mvp.html',
    'index_mvp.html',
]

# Папки для удаления
folders_to_delete = [
    'templates_FULL_BACKUP',
    '__pycache__',
    'Скриншот',
]

def cleanup():
    """Удалить лишние файлы"""
    project_root = os.path.dirname(os.path.abspath(__file__))

    print("=" * 70)
    print("CLEANING UP PROJECT FOR DEPLOYMENT")
    print("=" * 70)
    print()

    deleted_count = 0

    # Удаление файлов
    print("Deleting files...")
    for file in files_to_delete:
        file_path = os.path.join(project_root, file)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"  [OK] {file}")
                deleted_count += 1
            except Exception as e:
                print(f"  [ERROR] {file}: {e}")
        else:
            print(f"  [SKIP] {file} (not found)")

    # Удаление папок
    print("\nDeleting folders...")
    for folder in folders_to_delete:
        folder_path = os.path.join(project_root, folder)
        if os.path.exists(folder_path):
            try:
                shutil.rmtree(folder_path)
                print(f"  [OK] {folder}/")
                deleted_count += 1
            except Exception as e:
                print(f"  [ERROR] {folder}/: {e}")
        else:
            print(f"  [SKIP] {folder}/ (not found)")

    # Удаление __pycache__ во всех подпапках
    print("\nCleaning __pycache__...")
    for root, dirs, files in os.walk(project_root):
        if '__pycache__' in dirs:
            cache_path = os.path.join(root, '__pycache__')
            try:
                shutil.rmtree(cache_path)
                print(f"  [OK] {os.path.relpath(cache_path, project_root)}")
                deleted_count += 1
            except Exception as e:
                print(f"  [ERROR] {cache_path}: {e}")

    print()
    print("=" * 70)
    print(f"CLEANUP COMPLETED! Deleted {deleted_count} items")
    print("=" * 70)
    print()
    print("Remaining structure:")
    print("  - main.py                 # Telegram bot")
    print("  - admin_app.py            # Admin panel")
    print("  - database.py             # Database")
    print("  - config.py               # Configuration")
    print("  - alerts.py               # Alerts")
    print("  - daily_report.py         # Daily reports")
    print("  - feedback_scheduler.py   # Feedback collection")
    print("  - handlers/               # Bot handlers")
    print("  - templates/              # Admin templates")
    print("  - static/                 # Static files")
    print("  - utils/                  # Utilities")
    print()
    print("Ready for deployment!")

if __name__ == '__main__':
    cleanup()
