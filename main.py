"""Run the whole project from start to finish.

    python main.py              # uses data/raw/ if it is already downloaded
    python main.py --download   # downloads the data again first

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
    ("5. Evaluation charts", "src/evaluate.py"),
    ("6. PDF summary", "src/make_summary_pdf.py"),
]


def main():
    have_data = (ROOT / "data" / "raw" / "prices_nl_hourly.csv").exists()
    force_download = "--download" in sys.argv

    for name, script in STEPS:
        if script == "data/download_data.py" and have_data and not force_download:
            print(f"\n>>> {name}: skipped, data/raw/ already exists (use --download to refresh)")
            continue
        print(f"\n>>> {name}  ({script})", flush=True)
        subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, check=True)

    print("\nAll steps finished. Results: outputs/results.csv and outputs/summary.pdf")


if __name__ == "__main__":
    main()
