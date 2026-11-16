"""Run the whole project from start to finish.

    python main.py              # downloads only the data files that are missing
    python main.py --download   # downloads all data again first

Each step is a small script that can also be run on its own.
"""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

STEPS = [
    ("1. Download data", "data/download_data.py"),
    ("1. Check data", "src/check_data.py"),
    ("2. Merge + features", "src/build_dataset.py"),
    ("3. Benchmarks", "src/benchmarks.py"),
    ("4. OLS model", "src/model_ols.py"),
    ("4. Diebold-Mariano test", "src/dm_test.py"),
    ("5. Evaluation charts", "src/evaluate.py"),
    ("6. Battery: check the one-day LP", "battery/check_one_day.py"),
    ("6. Battery: trade through 2025", "battery/backtest.py"),
    ("6. Battery: sensitivity", "battery/sensitivity.py"),
    ("6. Battery: charts", "battery/charts.py"),
    ("7. PDF summary", "src/make_summary_pdf.py"),
]


def main():
    force_download = "--download" in sys.argv

    for name, script in STEPS:
        command = [sys.executable, str(ROOT / script)]
        # The download script skips files that already exist, unless we force it.
        if script == "data/download_data.py" and force_download:
            command.append("--force")
        print(f"\n>>> {name}  ({script})", flush=True)
        subprocess.run(command, cwd=ROOT, check=True)

    print("\nAll steps finished. Results: outputs/results.csv and outputs/summary.pdf")


if __name__ == "__main__":
    main()
