import os
import shutil

src_root = r'C:\Users\varun\OneDrive\Desktop\Quantum-Waste-Optimization'
dest_root = r'C:\Users\varun\OneDrive\Desktop\CSW'

print(f"============================================================")
print(f"COMBINING QUANTUM-WASTE-OPTIMIZATION INTO CSW WORKSPACE")
print(f"============================================================")

folders_to_copy = [
    (os.path.join(src_root, 'backend', 'quantum'), os.path.join(dest_root, 'backend', 'quantum')),
    (os.path.join(src_root, 'backend', 'services'), os.path.join(dest_root, 'backend', 'services')),
    (os.path.join(src_root, 'backend', 'routes'), os.path.join(dest_root, 'backend', 'routes')),
    (os.path.join(src_root, 'backend', 'templates'), os.path.join(dest_root, 'templates')),
    (os.path.join(src_root, 'backend', 'templates'), os.path.join(dest_root, 'backend', 'templates')),
    (os.path.join(src_root, 'backend', 'models'), os.path.join(dest_root, 'backend', 'models')),
    (os.path.join(src_root, 'backend', 'database'), os.path.join(dest_root, 'backend', 'database')),
]

files_to_copy = [
    (os.path.join(src_root, 'backend', 'simulator.py'), os.path.join(dest_root, 'backend', 'simulator.py')),
    (os.path.join(src_root, 'backend', 'seed_db.py'), os.path.join(dest_root, 'backend', 'seed_db.py')),
    (os.path.join(src_root, 'backend', 'app.py'), os.path.join(dest_root, 'backend', 'quantum_app.py')),
]

for s_dir, d_dir in folders_to_copy:
    if os.path.exists(s_dir):
        os.makedirs(d_dir, exist_ok=True)
        for item in os.listdir(s_dir):
            s_item = os.path.join(s_dir, item)
            d_item = os.path.join(d_dir, item)
            if os.path.isdir(s_item):
                if not item.startswith(('__pycache__', '.git', 'venv')):
                    shutil.copytree(s_item, d_item, dirs_exist_ok=True)
            else:
                shutil.copy2(s_item, d_item)
        print(f"  [COPIED FOLDER] {s_dir} -> {d_dir}")

for s_file, d_file in files_to_copy:
    if os.path.exists(s_file):
        os.makedirs(os.path.dirname(d_file), exist_ok=True)
        shutil.copy2(s_file, d_file)
        print(f"  [COPIED FILE] {s_file} -> {d_file}")

print("============================================================")
print("SUCCESS: Quantum-Waste-Optimization project combined into CSW!")
print("============================================================")
