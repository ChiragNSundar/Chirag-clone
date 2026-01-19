import subprocess
import sys

def install():
    print(f"Using python: {sys.executable}")
    try:
        with open('requirements.txt', 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print("requirements.txt not found in current directory.")
        return

    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # Handle inline comments if any
        if '#' in line:
            line = line.split('#')[0].strip()

        print(f"Installing: {line}")
        try:
            # Run pip visible in console
            subprocess.run(
                [sys.executable, "-m", "pip", "install", line], 
                check=True
            )
            print("  -> Success")
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode() if e.stderr else "Unknown error"
            print(f"  -> FAILED: {line}")
            # print(f"     Error: {err[:200]}...") # Optional: print first 200 chars of error

if __name__ == '__main__':
    install()
