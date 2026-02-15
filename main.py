import subprocess
import time
import os

def run_authentic_sync():
    """Executes the authentic data pipeline without any test data."""
    print("🛡️  INITIALIZING AUTHENTIC NBA DATA PIPELINE")
    print("-------------------------------------------")
    
    # 1. THE PIPELINE: List of scripts in order of execution
    # sync_odds: Gets live betting lines from the API
    # sync_stats: Gets real starters and historical logs
    # run_sims: Performs Monte Carlo math on the real data
    scripts = [
        "sync_odds.py",    
        "sync_stats.py",   
        "run_sims.py"      
    ]
    
    for script in scripts:
        if not os.path.exists(script):
            print(f"⚠️  Missing file: {script}. Please ensure it exists in this folder.")
            continue

        print(f"🚀 Executing: {script}...")
        try:
            # We use 'check=True' to stop if a script crashes
            subprocess.run(["python", script], check=True)
            print(f"✅ {script} Successful.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error in {script}. The system will attempt to continue...")
        
        # A 2-second pause helps prevent the APIs from flagging your IP
        time.sleep(2)

    print("\n🏁 SYNC COMPLETE. Authentic data has been processed.")
    print("👉 Refresh your dashboard at http://127.0.0.1:5000")

if __name__ == "__main__":
    run_authentic_sync()