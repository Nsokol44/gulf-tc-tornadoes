"""Run the full climatology pipeline in order.

Usage: python3 code/run_all.py
Steps: 01 download, 02 parse, 03 broad operational association,
04 Moore and Dixon 2011 rule, 05 primary sample (TCTOR plus the
MD2011 rule for 2024 to 2025), 06 analysis. Each step is a separate
script that can also be run on its own. No em dashes in outputs.
"""
import subprocess
import sys
import pathlib

CODE = pathlib.Path(__file__).resolve().parent

for step in ("01_download_data.py", "02_parse_data.py",
             "03_associate_tc_tornadoes.py", "04_md2011_rule.py",
             "05_build_primary_sample.py", "06_analyse_climatology.py"):
    print(f"=== {step} ===", flush=True)
    subprocess.run([sys.executable, str(CODE / step)], check=True)
print("Pipeline complete.")
