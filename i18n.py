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
        "btn_commit_publish": "Commit & Publish",
        "local_commit_ready": "Commits Saved Locally",
        "local_commit_sub": "All changes are committed in Git. Publish your project to GitHub to sync it to the cloud.",
        "empty_repo_sub": "Create files or publish your project directly to GitHub.",
        "unpushed_title": "Unpushed Commits Ready",
        "unpushed_sub": "You have commits waiting to be pushed to GitHub.",
        "behind_title": "Updates Available on Remote",
        "behind_sub": "Remote repository has new commits that can be pulled.",
        "btn_pull": "Pull Changes",
        "pull_failed": "Pull Failed",
        
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
        
        "token_settings": "GitHub Access Token",
        "token_hint": "Provide a Personal Access Token with repository read permissions to display page views and traffic analytics:",
        "token_guide_title": "GitHub Token & Credentials Setup",
        "token_guide_sub": "Step-by-step guide to connect Personal Access Token for telemetry and Git Push",
        "open_github_token_page": "🌐 Open Token Generator on GitHub",
        "open_github_token_desc": "Opens GitHub in your browser with pre-selected scopes ('repo') for 1-click token creation.",
        "token_steps_title": "How to create a Personal Access Token:",
        "token_step_1": "1. Click the button above to open GitHub (with pre-selected scopes).",
        "token_step_2": "2. Select Expiration (e.g. 90 days or No expiration) and ensure 'repo' scope is checked.",
        "token_step_3": "3. Click 'Generate token' at the bottom, copy the token (starts with 'ghp_'), and paste below.",
        "token_git_push_title": "How to authenticate Git Push (Remember credentials):",
        "token_git_push_desc": "To make Git store your token permanently and never ask for passwords on push, run:",
        "token_git_push_cmd": "git config --global credential.helper store",
        "token_git_push_note": "On your first push, enter your GitHub username and paste your token (ghp_...) as password.",
        "copy_command": "📋 Copy Command",
        "command_copied": "✓ Command Copied",
        "token_active_badge": "Token is active",
        "token_not_set": "No token configured",
        "clear_token": "Clear Token",
        "token_saved": "Token saved successfully!",
        "token_removed": "Token removed.",
        "save": "Save",
        "cancel": "Cancel",
        "sound_fx": "Sound Feedback",
        "btn_refresh": "Refresh",
        "refreshing": "Updating repository data...",
        "refresh_done": "Up to date ✓",
        "btn_open_repo": "Open Repository...",
        "lang_toggle_tooltip": "Switch Language (EN/RU)",
        "btn_push": "Push",
        "btn_push_ahead": "Push Commits to GitHub",
        "push_failed": "Push Failed",
        "commit_failed": "Commit Failed",
        
        # New Feature 1: Branches & Graph
        "switch_branch": "Switch Branch",
        "branches": "Branches",
        "checkout_success": "Switched to branch",
        "checkout_failed": "Failed to switch branch",
        "merge": "Merge into Current",
        
        # New Feature 2: Stashes
        "stashes": "Stashes",
        "stash_shelf": "Stash Shelf",
        "stash_shelf_sub": "Inspect stored working tree changes",
        "apply": "Apply",
        "pop": "Pop",
        "drop": "Drop",
        "no_stashes": "No stashes saved in this repository.",
        "stash_applied": "Stash applied successfully",
        "stash_dropped": "Stash discarded",
        
        # New Feature 3: Release Drafter
        "draft_release": "Draft Release...",
        "release_drafter_title": "Release Drafter & Changelog",
        "release_drafter_sub": "Automatic Conventional Commit release synthesizer",
        "tag_name": "Tag Name (e.g. v1.0.0)",
        "release_name": "Release Title",
        "changelog_preview": "Generated Changelog (Markdown)",
        "copy_markdown": "Copy Markdown",
        "markdown_copied": "Changelog copied to clipboard",
        "create_tag": "Create Git Tag",
        "tag_created": "Git tag created successfully",
        
        # New Feature 4: Secret Scanner
        "scanner_clean": "Secrets: Clean",
        "scanner_warning": "Secret Detected!",
        "secrets_dialog_title": "Sensitive Data Warning",
        "secrets_dialog_desc": "High-risk credentials, private keys, or API tokens were detected in staged files. Committing these may cause a critical security leak.",
        "commit_anyway": "Commit Anyway",
        
        # New Feature 5: Quick Switcher
        "quick_switcher_title": "Quick Switcher",
        "quick_switcher_placeholder": "Search recent repositories (Ctrl+K)...",
        "recent_repos": "Recent Repositories",
        
        "traffic_chart_title": "14-Day Traffic & Unique Visitors",
        "views_count": "views",
        "uniques_count": "uniques",
        "diff_title": "Diff",
        "staged_diff_sub": "Staged in Index",
        "unstaged_diff_sub": "Unstaged Working Tree Changes",
        "stage_file": "Stage File",
        "unstage_file": "Unstage File",
        "no_diff_detected": "(No differences detected or binary file)",
        "view_diff": "View Diff",
        
        # Empty / Welcome State
        "no_repo_title": "No Repository Selected",
        "no_repo_desc": "Open a local Git repository to start staging changes, inspecting commits, and viewing analytics.",
        "welcome_title": "Welcome to GitPulse HUD",
        "welcome_desc": "Please select a Git repository on your system to begin.",
        "open_project_hint": "Open Project...",
        "btn_init_repo": "Initialize Git in this Folder",
        "init_repo_success": "Git repository initialized successfully!",
        
        # Publish to GitHub
        "publish_card_title": "Repository Not Published to GitHub",
        "publish_card_desc": "This project only exists on your computer. Publish it to your GitHub account with a single click!",
        "publish_btn": "Publish to GitHub...",
        "publish_dialog_title": "Publish Repository to GitHub",
        "publish_dialog_sub": "Create remote repository and push your project",
        "publish_repo_name": "Repository Name",
        "publish_repo_desc": "Description (optional)",
        "publish_visibility": "Visibility",
        "publish_public": "Public (anyone can see)",
        "publish_private": "Private (only you can see)",
        "publish_account": "GitHub Account",
        "publish_account_connected": "Connected as",
        "publish_account_not_connected": "GitHub token not configured",
        "publish_action": "Publish Project",
        "publishing": "Publishing to GitHub...",
        "publish_success_title": "Project Published Successfully! 🎉",
        "publish_success_desc": "Your repository is now live on GitHub with upstream tracking configured.",
        "open_on_github": "Open on GitHub",
        "publish_initial_commit_note": "No commits found. An initial commit ('feat: initial commit') with all files will be automatically created.",
        "publish_init_section": "Initialize this repository with:",
        "publish_init_sub": "Skip this step if you're importing an existing repository.",
        "publish_add_readme": "Add a README file",
        "publish_add_readme_desc": "This is where you can write a long description for your project.",
        "publish_add_gitignore": "Add .gitignore",
        "publish_add_gitignore_desc": "Choose which files not to track from a list of templates.",
        "publish_gitignore_template": ".gitignore template:",
        "publish_choose_license": "Choose a license",
        "publish_choose_license_desc": "A license tells others what they can and can't do with your code.",
        "publish_license": "License:",
        "publish_file_exists": "(already exists in project)",
        "publish_template_none": "None"
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
        "btn_commit_publish": "Коммит и публикация",
        "local_commit_ready": "Коммит сохранен локально",
        "local_commit_sub": "Все изменения зафиксированы в Git. Опубликуйте репозиторий на GitHub, чтобы сохранить проект в сети.",
        "empty_repo_sub": "Создайте файлы или опубликуйте репозиторий на GitHub.",
        "unpushed_title": "Есть неотправленные коммиты",
        "unpushed_sub": "У вас есть коммиты, ожидающие отправки в удалённый репозиторий GitHub.",
        "behind_title": "Есть обновления на сервере",
        "behind_sub": "В удалённом репозитории есть коммиты, доступные для получения.",
        "btn_pull": "Получить изменения",
        "pull_failed": "Ошибка получения изменений",
        
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
        
        "token_settings": "Токен доступа GitHub",
        "token_hint": "Укажите Personal Access Token с доступом к репозиторию для просмотра детальной аналитики посещаемости и источников трафика:",
        "token_guide_title": "Подключение и настройка GitHub Token",
        "token_guide_sub": "Пошаговое руководство по подключению токена для аналитики и Git Push",
        "open_github_token_page": "🌐 Открыть страницу создания токена на GitHub",
        "open_github_token_desc": "Открывает страницу на GitHub с уже заполненным названием и необходимыми правами ('repo').",
        "token_steps_title": "Как создать Personal Access Token:",
        "token_step_1": "1. Нажмите кнопку выше, чтобы открыть GitHub с уже предвыбранными правами.",
        "token_step_2": "2. Выберите срок действия (Expiration) и убедитесь, что отмечена галочка 'repo'.",
        "token_step_3": "3. Нажмите 'Generate token' внизу, скопируйте созданный токен (начинается с 'ghp_') и вставьте ниже.",
        "token_git_push_title": "Как подключить токен для отправки коммитов (Git Push):",
        "token_git_push_desc": "Чтобы Git запомнил токен навсегда и больше не запрашивал пароль при каждом пуше, выполните:",
        "token_git_push_cmd": "git config --global credential.helper store",
        "token_git_push_note": "При первом пуше введите ваш никнейм на GitHub, а в качестве пароля вставьте скопированный токен (ghp_...).",
        "copy_command": "📋 Скопировать команду",
        "command_copied": "✓ Команда скопирована",
        "token_active_badge": "Токен подключен",
        "token_not_set": "Токен не настроен",
        "clear_token": "Удалить токен",
        "token_saved": "Токен успешно сохранен!",
        "token_removed": "Токен удален.",
        "save": "Сохранить",
        "cancel": "Отмена",
        "sound_fx": "Звуковой отклик",
        "btn_refresh": "Обновить",
        "refreshing": "Обновление данных репозитория...",
        "refresh_done": "Обновлено ✓",
        "btn_open_repo": "Открыть репозиторий...",
        "lang_toggle_tooltip": "Сменить язык (EN/RU)",
        "btn_push": "Отправить",
        "btn_push_ahead": "Отправить коммиты на GitHub",
        "push_failed": "Ошибка отправки коммитов",
        "commit_failed": "Ошибка создания коммита",
        
        # New Feature 1: Branches & Graph
        "switch_branch": "Переключить ветку",
        "branches": "Ветки",
        "checkout_success": "Переключено на ветку",
        "checkout_failed": "Ошибка переключения ветки",
        "merge": "Слить в текущую ветку",
        
        # New Feature 2: Stashes
        "stashes": "Тайники (Stash)",
        "stash_shelf": "Полка изменений (Stash)",
        "stash_shelf_sub": "Просмотр и восстановление сохраненных копий",
        "apply": "Применить",
        "pop": "Восстановить",
        "drop": "Удалить",
        "no_stashes": "В этом репозитории нет сохраненных изменений.",
        "stash_applied": "Изменения успешно применены",
        "stash_dropped": "Stash успешно удален",
        
        # New Feature 3: Release Drafter
        "draft_release": "Создать релиз...",
        "release_drafter_title": "Конструктор релизов и ченджлог",
        "release_drafter_sub": "Автоматическая генерация описания релиза по коммитам",
        "tag_name": "Имя тега (напр. v1.0.0)",
        "release_name": "Заголовок релиза",
        "changelog_preview": "Сформированный ченджлог (Markdown)",
        "copy_markdown": "Копировать Markdown",
        "markdown_copied": "Ченджлог скопирован в буфер",
        "create_tag": "Создать Git-тег",
        "tag_created": "Тег успешно создан",
        
        # New Feature 4: Secret Scanner
        "scanner_clean": "Безопасность: чисто",
        "scanner_warning": "Обнаружены секреты!",
        "secrets_dialog_title": "Предупреждение безопасности",
        "secrets_dialog_desc": "В подготовленных файлах обнаружены токены или приватные ключи. Коммит может привести к критической утечке данных в репозиторий.",
        "commit_anyway": "Все равно закоммитить",
        
        # New Feature 5: Quick Switcher
        "quick_switcher_title": "Быстрое переключение",
        "quick_switcher_placeholder": "Поиск среди недавних репозиториев (Ctrl+K)...",
        "recent_repos": "Недавние проекты",
        
        "traffic_chart_title": "Трафик и уникальные посетители (14 дней)",
        "views_count": "просмотров",
        "uniques_count": "посетителей",
        "diff_title": "Различия",
        "staged_diff_sub": "Подготовленные изменения в индексе",
        "unstaged_diff_sub": "Неподготовленные изменения рабочей копии",
        "stage_file": "Подготовить",
        "unstage_file": "Отменить подготовку",
        "no_diff_detected": "(Различий не обнаружено или бинарный файл)",
        "view_diff": "Просмотреть различия",
        
        # Empty / Welcome State
        "no_repo_title": "Репозиторий не выбран",
        "no_repo_desc": "Выберите локальный Git-репозиторий для подготовки коммитов, просмотра истории и аналитики.",
        "welcome_title": "Добро пожаловать в GitPulse HUD",
        "welcome_desc": "Пожалуйста, выберите Git-репозиторий для начала работы.",
        "open_project_hint": "Открыть проект...",
        "btn_init_repo": "Инициализировать Git в этой папке",
        "init_repo_success": "Git-репозиторий успешно инициализирован!",
        
        # Publish to GitHub
        "publish_card_title": "Репозиторий ещё не опубликован на GitHub",
        "publish_card_desc": "Этот проект существует только на вашем компьютере. Опубликуйте его на GitHub в один клик!",
        "publish_btn": "Опубликовать на GitHub...",
        "publish_dialog_title": "Публикация репозитория на GitHub",
        "publish_dialog_sub": "Создание удаленного репозитория и отправка проекта",
        "publish_repo_name": "Имя репозитория",
        "publish_repo_desc": "Описание (необязательно)",
        "publish_visibility": "Видимость",
        "publish_public": "Открытый (Public — доступен всем)",
        "publish_private": "Приватный (Private — только для вас)",
        "publish_account": "Аккаунт GitHub",
        "publish_account_connected": "Подключен как",
        "publish_account_not_connected": "GitHub токен не настроен",
        "publish_action": "Опубликовать проект",
        "publishing": "Публикация на GitHub...",
        "publish_success_title": "Проект успешно опубликован! 🎉",
        "publish_success_desc": "Ваш репозиторий опубликован на GitHub, удаленная ветка и отслеживание настроены.",
        "open_on_github": "Открыть на GitHub",
        "publish_initial_commit_note": "В репозитории ещё нет коммитов. Будет создан начальный коммит ('feat: initial commit') со всеми файлами.",
        "publish_init_section": "Инициализация репозитория:",
        "publish_init_sub": "Пропустите этот шаг, если в проекте уже есть нужные файлы.",
        "publish_add_readme": "Добавить файл README",
        "publish_add_readme_desc": "Здесь вы можете описать назначение вашего проекта.",
        "publish_add_gitignore": "Добавить .gitignore",
        "publish_add_gitignore_desc": "Выберите шаблон файлов, которые не следует отслеживать.",
        "publish_gitignore_template": "Шаблон .gitignore:",
        "publish_choose_license": "Выбрать лицензию",
        "publish_choose_license_desc": "Лицензия определяет правила использования вашего кода.",
        "publish_license": "Лицензия:",
        "publish_file_exists": "(уже есть в проекте)",
        "publish_template_none": "Не выбрано"
    }
}

CURRENT_LANG = "en"

MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_RU = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]

def set_language(lang):
    global CURRENT_LANG
    if lang in TRANSLATIONS:
        CURRENT_LANG = lang

def get_language():
    return CURRENT_LANG

def t(key):
    return TRANSLATIONS.get(CURRENT_LANG, {}).get(key, TRANSLATIONS["en"].get(key, key))

def format_date_label(d_str):
    """Localizes 'YYYY-MM-DD' into 'DD Mon' (e.g. '07 Sep' in EN, '07 сен' in RU)."""
    try:
        parts = d_str.split("-")
        day_num = parts[2]
        month_idx = int(parts[1]) - 1
        months = MONTHS_RU if CURRENT_LANG == "ru" else MONTHS_EN
        return f"{day_num} {months[month_idx]}"
    except Exception:
        return d_str

def format_relative_time(rel_str):
    """Localizes git relative time into Russian when active language is RU."""
    if CURRENT_LANG != "ru" or not rel_str:
        return rel_str

    s = rel_str.strip()
    replacements = [
        ("seconds ago", "сек. назад"),
        ("second ago", "сек. назад"),
        ("minutes ago", "мин. назад"),
        ("minute ago", "мин. назад"),
        ("hours ago", "ч. назад"),
        ("hour ago", "ч. назад"),
        ("days ago", "дн. назад"),
        ("day ago", "дн. назад"),
        ("weeks ago", "нед. назад"),
        ("week ago", "нед. назад"),
        ("months ago", "мес. назад"),
        ("month ago", "мес. назад"),
        ("years ago", "г. назад"),
        ("year ago", "г. назад"),
        ("yesterday", "вчера"),
        ("just now", "только что")
    ]
    for eng, ru in replacements:
        if eng in s:
            return s.replace(eng, ru)
    return s
