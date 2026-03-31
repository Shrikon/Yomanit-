import os
import subprocess
import time

BASE_DIR = r"C:\yomanit"
QUEUE_FILE = os.path.join(BASE_DIR, "command_queue", "git_command.txt")

def run_command(cmd: str):
    print(f"\n>>> מריץ: {cmd}")
    result = subprocess.run(cmd, cwd=BASE_DIR, shell=True, text=True, capture_output=True)

    print(result.stdout)
    if result.returncode != 0:
        print("שגיאה:")
        print(result.stderr)

def main():
    print("ממתין לפקודות מקלוד...")

    while True:
        if os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                commands = [line.strip() for line in f if line.strip()]

            if commands:
                for cmd in commands:
                    run_command(cmd)

                os.remove(QUEUE_FILE)
                print("✓ בוצע ונמחק מהתור")

        time.sleep(3)

if __name__ == "__main__":
    main()