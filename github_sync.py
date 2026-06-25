import os
import subprocess
import datetime

def push_to_github(workspace_dir=None):
    if workspace_dir is None:
        workspace_dir = os.path.dirname(os.path.abspath(__file__))
    
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] Pushing updated files to GitHub...")
    
    try:
        # Check if the folder is a git repository
        if not os.path.exists(os.path.join(workspace_dir, '.git')):
            print("Warning: Local directory is not a Git repository. Cannot push to GitHub.")
            return False
            
        # Files we want to update and sync
        files_to_sync = [
            'dashboard_cache.json',
            'nbp_spot_prices_30m.csv', 
            'nbp_spot_prices_plot.png'
        ]
        
        # Filter files that actually exist
        existing_files = [f for f in files_to_sync if os.path.exists(os.path.join(workspace_dir, f))]
        
        if not existing_files:
            print("No files found to stage for commit.")
            return False
            
        # Stage the files
        subprocess.run(['git', 'add'] + existing_files, check=True, cwd=workspace_dir)
        
        # Check if there are changes to commit
        status = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True, check=True, cwd=workspace_dir)
        if not status.stdout.strip():
            print("No changes detected in tracked files. Skipping push.")
            return True
            
        # Commit the changes
        commit_msg = f"Auto-update TV Dashboard: {timestamp}"
        subprocess.run(['git', 'commit', '-m', commit_msg], check=True, cwd=workspace_dir)
        
        # Push to origin main
        result = subprocess.run(['git', 'push', 'origin', 'main'], capture_output=True, text=True, check=True, cwd=workspace_dir)
        print("Successfully pushed to GitHub.")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Git command failed: {' '.join(e.cmd)}")
        if e.stdout:
            print(f"Stdout:\n{e.stdout}")
        if e.stderr:
            print(f"Stderr:\n{e.stderr}")
        return False
    except Exception as e:
        print(f"Error during GitHub push: {e}")
        return False

if __name__ == "__main__":
    push_to_github()
