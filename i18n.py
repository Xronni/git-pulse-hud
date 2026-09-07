#!/usr/bin/env python3
"""
GitPulse HUD — Internationalization (i18n)
Full localization support for English and Russian.
"""

TRANSLATIONS = {
    "en": {
        "app_title": "GitPulse HUD",
        "tab_stage": "⚡ Stage & Commit",
        "tab_pulse": "📊 Repo Pulse",
        "tab_insights": "🌐 GitHub Insights",
        "staged_changes": "Staged Changes",
        "unstaged_changes": "Unstaged Changes",
        "untracked_files": "Untracked Files",
        "clean_tree": "✨ Working tree clean — ready to code",
        "stage_all": "Stage All",
        "unstage_all": "Unstage All",
        "commit_builder": "Conventional Commit Builder",
        "commit_type": "Type",
        "commit_scope": "Scope (opt)",
        "commit_desc": "Description (e.g. add tactile sound feedback)",
        "breaking_change": "Breaking Change (!)",
        "btn_commit": "Commit",
        "btn_commit_push": "Commit & Push",
        "btn_stash": "Stash",
        "btn_pop": "Pop Stash",
        "btn_refresh": "Refresh",
        "btn_open_repo": "Open Repository",
        "velocity_title": "Commit Velocity (Last 14 Days)",
        "punchcard_title": "Developer Focus Rhythm (24h Punchcard)",
        "stat_commits": "Commits",
        "stat_contributors": "Contributors",
        "stat_files": "Tracked Files",
        "stat_stashes": "Stashes",
        "recent_commits": "Recent Commits",
        "copy_hash": "Copy hash",
        "hash_copied": "Hash copied to clipboard!",
        "views_14d": "Page Views (14d)",
        "uniques_14d": "Unique Visitors (14d)",
        "stars": "Stars",
        "forks": "Forks",
        "downloads": "Downloads",
        "open_issues": "Open Issues",
        "reactions": "Reactions",
        "top_referrers": "Top Referrers (Where visitors come from)",
        "release_downloads": "Release Assets & Download Counters",
        "no_releases": "No releases published yet on GitHub.",
        "no_referrers": "No referrer traffic data found yet.",
        "token_settings": "GitHub Token",
        "token_hint": "To see 14-day page views, unique visitors, and referrers, add a GitHub PAT with repo access:",
        "save": "Save",
        "cancel": "Cancel",
        "sound_fx": "Sound Effects",
        "token_saved": "GitHub token saved successfully!",
        "commit_success": "Commit created successfully!",
        "push_success": "Pushed to remote successfully!",
        "stash_success": "Changes stashed.",
        "pop_success": "Stash popped.",
        "error_commit": "Commit failed",
        "error_push": "Push failed"
    },
    "ru": {
        "app_title": "GitPulse HUD",
        "tab_stage": "⚡ Стейджинг & Коммит",
        "tab_pulse": "📊 Пульс репозитория",
        "tab_insights": "🌐 Метрики GitHub",
        "staged_changes": "Подготовленные к коммиту (Staged)",
        "unstaged_changes": "Измененные файлы (Unstaged)",
        "untracked_files": "Новые неотслеживаемые файлы",
        "clean_tree": "✨ Рабочее дерево чисто — можно кодить",
        "stage_all": "Стейджить всё",
        "unstage_all": "Снять всё",
        "commit_builder": "Конструктор Conventional Commits",
        "commit_type": "Тип",
        "commit_scope": "Скоуп (опц)",
        "commit_desc": "Краткое описание (напр. добавить тактильный звук)",
        "breaking_change": "Ломающее изменение (!)",
        "btn_commit": "Коммит",
        "btn_commit_push": "Коммит и Пуш",
        "btn_stash": "В Stash",
        "btn_pop": "Извлечь Stash",
        "btn_refresh": "Обновить",
        "btn_open_repo": "Выбрать репозиторий",
        "velocity_title": "Скорость коммитов (последние 14 дней)",
        "punchcard_title": "Ритм продуктивности (24ч Punchcard)",
        "stat_commits": "Коммитов",
        "stat_contributors": "Авторов",
        "stat_files": "Файлов в репо",
        "stat_stashes": "В Stash",
        "recent_commits": "Недавние коммиты",
        "copy_hash": "Скопировать хеш",
        "hash_copied": "Хеш скопирован в буфер обмена!",
        "views_14d": "Просмотры (14 дн)",
        "uniques_14d": "Уникальные гости (14 дн)",
        "stars": "Звёзды ⭐",
        "forks": "Форки 🍴",
        "downloads": "Скачиваний 📦",
        "open_issues": "Тикеты 💬",
        "reactions": "Реакции 👍 ❤️ 🚀",
        "top_referrers": "Источники переходов (Откуда приходят люди)",
        "release_downloads": "Файлы релизов и счётчик скачиваний",
        "no_releases": "На GitHub пока нет опубликованных релизов.",
        "no_referrers": "Пока нет данных о переходах с внешних сайтов.",
        "token_settings": "Токен GitHub",
        "token_hint": "Для доступа к просмотрам страниц, уникальным посетителям и сайтам-источникам укажите Personal Access Token:",
        "save": "Сохранить",
        "cancel": "Отмена",
        "sound_fx": "Звуковые эффекты",
        "token_saved": "Токен GitHub успешно сохранен!",
        "commit_success": "Коммит успешно создан!",
        "push_success": "Изменения успешно отправлены на GitHub!",
        "stash_success": "Изменения сохранены в Stash.",
        "pop_success": "Stash успешно извлечен.",
        "error_commit": "Ошибка создания коммита",
        "error_push": "Ошибка отправки в репозиторий"
    }
}

CURRENT_LANG = "ru"

def set_language(lang):
    global CURRENT_LANG
    if lang in TRANSLATIONS:
        CURRENT_LANG = lang

def get_language():
    return CURRENT_LANG

def t(key):
    return TRANSLATIONS.get(CURRENT_LANG, {}).get(key, TRANSLATIONS["en"].get(key, key))
