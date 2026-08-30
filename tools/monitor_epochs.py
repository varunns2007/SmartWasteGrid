import os
import re
import time

log_file = r'C:\Users\varun\.gemini\antigravity-ide\brain\937f894e-b590-4218-8afd-4278cc4063c0\.system_generated\tasks\task-1249.log'

while True:
    os.system('cls' if os.name == 'nt' else 'clear')
    print("============================================================")
    print("     CONTINUOUS REAL-TIME EPOCH MONITORING ENGINE           ")
    print("============================================================")
    print(f"{'Epoch':<10} | {'GPU Mem':<10} | {'Box Loss':<10} | {'Cls Loss':<10} | {'DFL Loss':<10}")
    print("-" * 62)

    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()

        epoch_lines = {}
        last_progress = ""
        for line in text.splitlines():
            match = re.search(r'(\d+/25)\s+([\d\.]+G)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)', line)
            if match:
                ep, mem, box, cls, dfl = match.groups()
                epoch_lines[ep] = (mem, box, cls, dfl)
                last_progress = f"Training Active: Epoch {ep} ({mem} VRAM)"

        for ep in sorted(epoch_lines.keys(), key=lambda x: int(x.split('/')[0])):
            mem, box, cls, dfl = epoch_lines[ep]
            print(f"{ep:<10} | {mem:<10} | {box:<10} | {cls:<10} | {dfl:<10}")

        print("-" * 62)
        print(f"STATUS: {last_progress}")
    else:
        print("Waiting for training task log...")

    print("============================================================")
    print("Auto-refreshing every 3 seconds... Press Ctrl+C to exit.")
    time.sleep(3)
