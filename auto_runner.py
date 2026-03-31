import os
import subprocess
import time
from datetime import datetime

REPO_PATH = r"C:\yomanit"
INBOX_PATH = r"C:\yomanit\ai_inbox"
WATCH_INTERVAL = 3

ALLOWED_PATHS = [
    "backend/parsers/",
    "backend/routers/",
    "backend/validation/",
    "backend/tests/",
    "backend/index_cache.py",
    "frontend/app/",
    "frontend/",
]


def parse_response(text):
    lines = text.splitlines()
    target = None
    commit = "auto update"
    code_lines = []
    in_code = False

    for line in lines:
        if line.startswith("TARGET:"):
            target = line.replace("TARGET:", "").strip()
            continue
        if line.startswith("COMMIT:"):
            commit = line.replace("COMMIT:", "").strip()
            break
        if target:
            if not in_code:
                if line.strip() == "":
                    continue
                else:
                    in_code = True
            code_lines.append(line)

    if not target:
        raise Exception("לא נמצא TARGET")
    if not code_lines:
        raise Exception("לא נמצא קוד")

    return target, commit, "\n".join(code_lines)


def validate_path(target):
    normalized = target.replace("\\", "/")
    for allowed in ALLOWED_PATHS:
        if normalized.startswith(allowed) or normalized == allowed:
            return True
    raise Exception(f"נתיב לא מורשה: {target}")


def validate_code(content):
    if len(content.strip()) < 50:
        raise Exception("קוד קצר מדי")
    if "def " not in content and "class " not in content:
        raise Exception("לא נראה כמו קוד")
    return True


def safe_write(path, new_content):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            old = f.read()
        if len(new_content) < len(old) * 0.3:
            raise Exception("חשד לדריסת קובץ")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"✓ נכתב: {path}")


def git_commit_push_all(commit_message):
    r1 = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_PATH, capture_output=True, text=True)

    if not r1.stdout.strip():
        print("אין שינויים ל-commit")
        return

    subprocess.run(["git", "add", "."], cwd=REPO_PATH)

    r2 = subprocess.run(
        ["git", "commit", "-m", commit_message],
        cwd=REPO_PATH,
        capture_output=True,
        text=True
    )

    r3 = subprocess.run(
        ["git", "push"],
        cwd=REPO_PATH,
        capture_output=True,
        text=True
    )

    print(f"git commit: {r2.stdout.strip()}")
    print(f"git push:   {r3.returncode} {r3.stderr.strip() or r3.stdout.strip()}")


def rollback(file_path):
    if not file_path:
        return
    subprocess.run(["git", "checkout", "--", file_path], cwd=REPO_PATH)
    print("בוצע rollback")


def get_next_file():
    if not os.path.exists(INBOX_PATH):
        os.makedirs(INBOX_PATH)
        return None
    files = sorted(f for f in os.listdir(INBOX_PATH) if f.endswith(".txt"))
    return files[0] if files else None


def parse_gitonly(text):
    target = None
    commit = "auto commit"
    gitonly = False
    forcecommit = False
    for line in text.splitlines():
        if line.startswith("TARGET:"):
            target = line.replace("TARGET:", "").strip()
        elif line.startswith("COMMIT:"):
            commit = line.replace("COMMIT:", "").strip()
        elif line.startswith("FORCECOMMIT:"):
            forcecommit = line.replace("FORCECOMMIT:", "").strip().lower() == "true"
        elif line.startswith("GITONLY:"):
            gitonly = line.replace("GITONLY:", "").strip().lower() == "true"
    return target, commit, gitonly, forcecommit


def process_once():
    file_name = get_next_file()

    if file_name:
        full_path = os.path.join(INBOX_PATH, file_name)
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        target = None
        try:
            target, commit, gitonly = parse_gitonly(content)

            if gitonly:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                git_commit_push_all(f"{commit} | {timestamp}")
                os.remove(full_path)
                print(f"✓ GITONLY הושלם — {file_name} נמחק\n")
                return True

            target, commit, code = parse_response(content)
            validate_path(target)
            validate_code(code)

            full_target_path = os.path.join(REPO_PATH, target)

            print(f"\n→ TARGET: {target}")
            print(f"→ COMMIT: {commit}")

            safe_write(full_target_path, code)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            git_commit_push_all(f"{commit} | {timestamp}")

            os.remove(full_path)
            print(f"✓ הושלם בהצלחה — {file_name} נמחק\n")
            return True

        except Exception as e:
            print(f"✗ שגיאה: {e}")
            rollback(target if target else "")
            error_path = os.path.join(INBOX_PATH, "errors")
            os.makedirs(error_path, exist_ok=True)
            try:
                os.rename(full_path, os.path.join(error_path, file_name))
            except:
                pass
            return False

    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        git_commit_push_all(f"auto: sync changes | {timestamp}")
        return False


def watch_loop():
    print(f"🔄 AI auto_runner פעיל — GIT DRIVEN")
    while True:
        try:
            process_once()
            time.sleep(WATCH_INTERVAL)
        except KeyboardInterrupt:
            print("\nנעצר.")
            break


if __name__ == "__main__":
    import sys
    if "--watch" in sys.argv:
        watch_loop()
    else:
        process_once()