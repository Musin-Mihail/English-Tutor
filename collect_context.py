import os
import shutil

# Настройки папок вывода
OUTPUT_DIR = "context_for_ai"
BACKEND_OUT = "backend.txt"
CLIENT_OUT = "frontend.txt"

# Папки источников (относительно места запуска скрипта)
BACKEND_SRC = "backend"
CLIENT_SRC = "frontend"

CURRENT_SCRIPT_NAME = os.path.basename(__file__)

IGNORE_DIRS = {
    ".git",
    ".vs",
    ".idea",
    ".vscode",
    "__pycache__",
    "env",
    "venv",
    "bin",
    "obj",
    "packages",
    "TestResults",
    "CopilotIndices",
    "chroma_db",
    "MasterPrompts",
    "ai_models",
    "node_modules",
    ".angular",
    "dist",
    "coverage",
    "out-tsc",
    "context_for_ai",
    "logs",
}

IGNORE_EXTENSIONS = {
    ".exe",
    ".dll",
    ".pdb",
    ".suo",
    ".user",
    ".pyd",
    ".cache",
    ".vsidx",
    ".lref",
    ".resources",
    ".pyc",
    ".db",
    ".sqlite",
    ".db-shm",
    ".db-wal",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".mp3",
    ".mp4",
    ".zip",
    ".tar",
    ".gz",
    ".rar",
    ".nupkg",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".lock",
    ".log",
}

IGNORE_FILES = {
    CURRENT_SCRIPT_NAME,
    "collect_context.py",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "tsconfig.spec.json",
    "karma.conf.js",
    ".editorconfig",
    ".gitignore",
    "README.md",
    "LICENSE.md",
}


def is_binary(file_path):
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b"\0" in chunk
    except Exception:
        return True


def generate_tree(start_path):
    """Генерирует визуальное дерево файлов для конкретной папки"""
    tree_str = f"PROJECT STRUCTURE ({os.path.basename(start_path)}):\n"

    # Если папки нет, возвращаем сообщение об ошибке в дерево
    if not os.path.exists(start_path):
        return f"Directory {start_path} not found.\n"

    for root, dirs, files in os.walk(start_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        # Вычисляем уровень вложенности относительно start_path
        rel_path = os.path.relpath(root, start_path)
        if rel_path == ".":
            level = 0
        else:
            level = rel_path.count(os.sep) + 1

        indent = " " * 4 * level

        # Не печатаем корневую точку, печатаем имя папки
        if rel_path != ".":
            tree_str += f"{indent}{os.path.basename(root)}/\n"

        subindent = " " * 4 * (level + 1)
        for f in files:
            if f in IGNORE_FILES:
                continue
            _, ext = os.path.splitext(f)
            if ext.lower() in IGNORE_EXTENSIONS:
                continue
            if f.endswith(".spec.ts"):
                continue

            tree_str += f"{subindent}{f}\n"

    return tree_str + "\n" + "=" * 50 + "\n\n"


def process_folder(source_folder, output_filename):
    """Обрабатывает одну папку и записывает результат в MasterPrompts"""

    # Полный путь к исходной папке
    start_path = os.path.abspath(source_folder)

    # Проверка существования папки
    if not os.path.exists(start_path):
        print(f"!!! ПРЕДУПРЕЖДЕНИЕ: Папка '{source_folder}' не найдена. Пропускаем.")
        return

    # Полный путь к выходному файлу
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    print(f"Сбор контекста из '{source_folder}' в '{output_path}'...")

    with open(output_path, "w", encoding="utf-8") as outfile:
        # 1. Записываем дерево
        outfile.write(generate_tree(start_path))

        file_count = 0
        for root, dirs, files in os.walk(start_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                if file in IGNORE_FILES:
                    continue

                if file.endswith(".spec.ts"):
                    continue

                _, ext = os.path.splitext(file)
                if ext.lower() in IGNORE_EXTENSIONS:
                    continue

                file_path = os.path.join(root, file)

                if is_binary(file_path):
                    continue

                try:
                    # Относительный путь для заголовка (например: app/main.py)
                    rel_path = os.path.relpath(file_path, start_path)

                    with open(
                        file_path, "r", encoding="utf-8", errors="replace"
                    ) as infile:
                        content = infile.read()

                        outfile.write("=" * 50 + "\n")
                        outfile.write(f"FILE: {rel_path}\n")
                        outfile.write("=" * 50 + "\n")
                        outfile.write(content + "\n\n")

                        file_count += 1
                        # print(f"  -> {rel_path}") # Раскомментируйте для подробного лога

                except Exception as e:
                    print(f"Ошибка чтения {file_path}: {e}")

    print(f"Готово для {source_folder}! Файлов: {file_count}\n")


if __name__ == "__main__":
    # 1. Создаем папку MasterPrompts, если нет
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Создана папка {OUTPUT_DIR}")

    # 2. Обрабатываем Backend
    process_folder(BACKEND_SRC, BACKEND_OUT)

    # 3. Обрабатываем Client
    process_folder(CLIENT_SRC, CLIENT_OUT)

    print("Сбор контекста завершен.")
