#!/usr/bin/env python3
"""
GitPulse HUD — Standard Official Localization (EN / RU)
Clean, professional developer terminology matching JetBrains & GitHub Desktop standards.
Default language: EN
"""

TRANSLATIONS = {
    "en": {
        "app_title": "GitPulse",
        "app_subtitle": "Git & Telemetry HUD",
        "tab_changes": "Files & Changes",
        "tab_history": "Commit History",
        "tab_pulse": "Repository Pulse",
        "tab_telemetry": "GitHub Analytics",
        
        # Subtitles
        "sub_changes": "Working tree management and commit preparation",
        "sub_history": "Chronological log of repository commits",
        "sub_pulse": "Development velocity and daily activity distribution",
        "sub_telemetry": "Traffic, unique visitors, and release downloads",
        
        # Staging & Working Tree
        "staged_title": "Staged Changes",
        "unstaged_title": "Modified Files",
        "untracked_title": "Untracked Files",
        "clean_tree": "Working tree is clean",
        "clean_tree_sub": "No modified or uncommitted files in this repository.",
        "stage_all": "Stage All",
        "unstage_all": "Unstage All",
        "stash_save": "Stash Changes",
        "stash_pop": "Pop Stash",
        
        # Commit Composer
        "commit_builder": "Commit Composer",
        "commit_type": "Type",
        "commit_scope_placeholder": "Scope (optional)",
        "commit_desc_placeholder": "Concise summary of changes made...",
        "breaking_change": "Breaking Changes (!)",
        "btn_commit": "Commit Changes",
        "btn_commit_push": "Commit & Push",
        
        # Metrics & Pulse
        "velocity_title": "Commit Velocity (14 Days)",
        "punchcard_title": "24-Hour Activity Heatmap",
        "stat_commits": "Commits",
        "stat_contributors": "Authors",
        "stat_files": "Files",
        "stat_stashes": "In Stash",
        "copy_hash": "Copy Hash",
        "hash_copied": "Commit hash copied to clipboard",
        "no_velocity_title": "No Recent Commit Activity",
        "no_velocity_desc": "No commits were recorded in the last 14 days in this branch.",
        "no_punchcard_desc": "No commit timestamps recorded in the selected period.",
        
        # GitHub Analytics
        "views_14d": "Views",
        "uniques_14d": "Visitors",
        "stars": "Stars",
        "forks": "Forks",
        "downloads": "Downloads",
        "open_issues": "Issues",
        "reactions": "Community Reactions",
        "top_referrers": "Top Traffic Sources",
        "release_downloads": "Release Assets",
        "no_releases": "No releases published yet on this repository.",
        "no_referrers": "No external traffic sources recorded yet.",
        "traffic_no_data": "Traffic stats are updated by GitHub once daily.",
        "token_banner_title": "GitHub Access Token Required",
        "token_banner_desc": "To display 14-day page views, unique visitors, and referrer domains (Telegram, Habr, Reddit, Google), configure a GitHub Personal Access Token with repo access.",
        "token_banner_btn": "Configure Token",
        
        # Dialogs & General
        "token_settings": "GitHub Access Token",
        "token_hint": "Provide a Personal Access Token with repository read permissions to display page views and traffic analytics:",
        "save": "Save",
        "cancel": "Cancel",
        "sound_fx": "Sound Feedback",
        "btn_refresh": "Refresh",
        "refreshing": "Updating repository data...",
        "refresh_done": "Up to date",
        "btn_open_repo": "Open Repository...",
        "lang_toggle_tooltip": "Switch Language (EN/RU)",
        
        # Empty / Welcome State
        "no_repo_title": "No Repository Selected",
        "no_repo_desc": "Open a local Git repository to start staging changes, inspecting commits, and viewing analytics.",
        "welcome_title": "Welcome to GitPulse HUD",
        "welcome_desc": "Please select a Git repository on your system to begin."
    },
    "ru": {
        "app_title": "GitPulse",
        "app_subtitle": "Git & Telemetry HUD",
        "tab_changes": "Файлы и коммиты",
        "tab_history": "Журнал изменений",
        "tab_pulse": "Активность и пульс",
        "tab_telemetry": "Аналитика GitHub",
        
        # Subtitles
        "sub_changes": "Управление изменениями и подготовка коммитов",
        "sub_history": "Хронологический список зафиксированных коммитов",
        "sub_pulse": "Динамика коммитов и интенсивность разработки",
        "sub_telemetry": "Посещаемость, просмотры и статистика загрузок",
        
        # Staging & Working Tree
        "staged_title": "Подготовленные изменения",
        "unstaged_title": "Измененные файлы",
        "untracked_title": "Новые неотслеживаемые файлы",
        "clean_tree": "Нет изменений для коммита",
        "clean_tree_sub": "Рабочий каталог полностью синхронизирован.",
        "stage_all": "Подготовить всё",
        "unstage_all": "Отменить подготовку",
        "stash_save": "Спрятать (Stash)",
        "stash_pop": "Восстановить (Pop)",
        
        # Commit Composer
        "commit_builder": "Параметры коммита",
        "commit_type": "Тип",
        "commit_scope_placeholder": "Область (необязательно)",
        "commit_desc_placeholder": "Краткое описание внесенных изменений...",
        "breaking_change": "Критические изменения (!)",
        "btn_commit": "Создать коммит",
        "btn_commit_push": "Коммит и отправка",
        
        # Metrics & Pulse
        "velocity_title": "Динамика коммитов (14 дней)",
        "punchcard_title": "Распределение активности (24ч)",
        "stat_commits": "Коммитов",
        "stat_contributors": "Авторов",
        "stat_files": "Файлов",
        "stat_stashes": "В тайнике",
        "copy_hash": "Копировать хеш",
        "hash_copied": "Хеш коммита скопирован в буфер обмена",
        "no_velocity_title": "Нет недавней активности",
        "no_velocity_desc": "За последние 14 дней в этой ветке не зафиксировано коммитов.",
        "no_punchcard_desc": "Нет данных о времени коммитов за выбранный период.",
        
        # GitHub Analytics
        "views_14d": "Просмотры",
        "uniques_14d": "Посетители",
        "stars": "Звёзды",
        "forks": "Форки",
        "downloads": "Загрузки",
        "open_issues": "Задачи",
        "reactions": "Реакции сообщества",
        "top_referrers": "Источники трафика (Рефереры)",
        "release_downloads": "Файлы релизов",
        "no_releases": "Опубликованных релизов пока нет в этом репозитории.",
        "no_referrers": "Данных о переходах с внешних сайтов пока нет.",
        "traffic_no_data": "Статистика трафика обновляется GitHub раз в сутки.",
        "token_banner_title": "Требуется токен доступа GitHub",
        "token_banner_desc": "Для просмотра графиков посещаемости за 14 дней, уникальных посетителей и источников трафика (Telegram, Habr, Reddit, Google) укажите GitHub Personal Access Token.",
        "token_banner_btn": "Настроить токен",
        
        # Dialogs & General
        "token_settings": "Токен доступа GitHub",
        "token_hint": "Укажите Personal Access Token с доступом к репозиторию для просмотра детальной аналитики посещаемости и источников трафика:",
        "save": "Сохранить",
        "cancel": "Отмена",
        "sound_fx": "Звуковой отклик",
        "btn_refresh": "Обновить",
        "refreshing": "Обновление данных репозитория...",
        "refresh_done": "Данные обновлены",
        "btn_open_repo": "Открыть репозиторий...",
        "lang_toggle_tooltip": "Сменить язык (EN/RU)",
        
        # Empty / Welcome State
        "no_repo_title": "Репозиторий не выбран",
        "no_repo_desc": "Выберите локальный Git-репозиторий для подготовки коммитов, просмотра истории и аналитики.",
        "welcome_title": "Добро пожаловать в GitPulse HUD",
        "welcome_desc": "Пожалуйста, выберите Git-репозиторий для начала работы."
    }
}

CURRENT_LANG = "en"

def set_language(lang):
    global CURRENT_LANG
    if lang in TRANSLATIONS:
        CURRENT_LANG = lang

def get_language():
    return CURRENT_LANG

def t(key):
    return TRANSLATIONS.get(CURRENT_LANG, {}).get(key, TRANSLATIONS["en"].get(key, key))
