import os
import csv

folder_name = input("Enter folder name: ").strip()

script_dir = os.path.dirname(os.path.abspath(__file__))
folder_path = os.path.join(script_dir, folder_name)

if not os.path.isdir(folder_path):
    print(f"Folder '{folder_name}' not found.")
    exit(1)

csv_files = [f for f in os.listdir(folder_path) if f.endswith(".csv")]

if not csv_files:
    print("No CSV files found in that folder.")
    exit(0)

output_path = os.path.join(script_dir, f"{folder_name}_headers.txt")

with open(output_path, "w", encoding="utf-8") as out:
    for file_name in sorted(csv_files):
        file_path = os.path.join(folder_path, file_name)
        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader, None)

        block = f"\n{file_name}\n"
        if headers:
            block += "".join(f"- {h.strip()}\n" for h in headers)
        else:
            block += "(empty file)\n"

        print(block)
        out.write(block)

print(f"Output saved to: {output_path}")