from pathlib import Path
import os
import shutil

# Paths to the database and output file
DB_PATH = Path(os.getenv("INPUT_PATH", "/mnt/input")) / "query_results.db"  # Default path to the SQLite database
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "/mnt/output")) / "query_results.db"  # Default relayed query results output path

def main():
    print(f"Relaying query results from {DB_PATH} to {OUTPUT_PATH}")

    # Copy the input DB to the output path
    shutil.copy(DB_PATH, OUTPUT_PATH)

if __name__ == "__main__":
    main()