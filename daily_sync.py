import subprocess

scripts = [
    "clean_db.py",
    "sync_odds.py",
    "sync_box_scores.py",
    "sync_stats.py",
    "run_sims.py"
]

for script in scripts:
    print(f"--- Running {script} ---")
    subprocess.run(["python", script])

print("✅ Daily Sync Complete! Ready to push to GitHub.")