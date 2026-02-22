import subprocess
import sys
import time

def run_script(script_name):
    """Runs a python script and waits for it to finish."""
    print(f"\n🚀 [STARTING] {script_name}...")
    try:
        # We use sys.executable to ensure it uses the same python environment
        result = subprocess.run([sys.executable, script_name], check=True)
        if result.returncode == 0:
            print(f"✅ [FINISHED] {script_name} successfully.")
    except subprocess.CalledProcessError as e:
        print(f"❌ [ERROR] {script_name} failed with error: {e}")
        sys.exit(1) # Stop the whole chain if one script fails

def main():
    start_time = time.time()
    
    # THE CRITICAL ORDER OF OPERATIONS
    sync_chain = [
        "clean_db.py",          # 1. Wipe old stats locally
        "sync_odds.py",         # 2. Pull fresh lines
        "sync_box_scores.py",   # 3. Pull 2026 logs
        "sync_stats.py",        # 4. Calculate hit trends
        "run_sims.py",          # 5. Run the Monte Carlo engine
        "push_stats_to_live.py" # 6. ADD THIS HERE: Export and push CSVs
    ]

    print("--- 🏀 EDGEBOARD MASTER DAILY SYNC 🏀 ---")
    
    # ... rest of your code ...
    
    for script in sync_chain:
        run_script(script)

    end_time = time.time()
    duration = round((end_time - start_time) / 60, 2)
    
    print("\n" + "="*40)
    print(f"🏁 ALL SYSTEMS GREEN")
    print(f"⏱️ Total Sync Time: {duration} minutes")
    print(f"💾 Local 'edgeboard.db' is now optimized and ready for Git.")
    print("="*40)

if __name__ == "__main__":
    main()