import subprocess
import time
import os
import sys

# List your scripts in the exact order they need to run
SCRIPTS = [
    "sync_odds.py",
    "sync_box_scores.py",
    "sync_stats.py",
    "run_sims.py"
]

def run_master():
    print("="*40)
    print("🚀 EDGEBOARD MASTER SYNC INITIATED")
    print("="*40)
    
    start_time = time.time()

    for i, script in enumerate(SCRIPTS):
        print(f"\n[{i+1}/{len(SCRIPTS)}] RUNNING: {script}...")
        
        try:
            # subprocess.run waits for the script to finish before moving to the next
            result = subprocess.run([sys.executable, script], check=True)
            
            if result.returncode == 0:
                print(f"✅ {script} completed successfully.")
            
        except subprocess.CalledProcessError as e:
            print(f"\n❌ FATAL ERROR in {script}")
            print("Master sync aborted to prevent data corruption.")
            return

    end_time = time.time()
    duration = round((end_time - start_time) / 60, 2)
    
    print("\n" + "="*40)
    print(f"🎉 SUCCESS: All data is ready for upload!")
    print(f"⏱️ Total Time: {duration} minutes")
    print("="*40)
    print("\nNEXT STEP: Run your Git commands to push edgeboard.db live.")

if __name__ == "__main__":
    run_master()