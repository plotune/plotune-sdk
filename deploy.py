import subprocess
import os
import sys
import shutil
from dotenv import load_dotenv


def deploy_package():
    print("=== Starting package deployment ===")

    # Load environment variables
    print("[INFO] Loading environment variables from .env...")
    load_dotenv()
    pypi_token = os.getenv("PYPI_TOKEN")

    if not pypi_token:
        print("[ERROR] PYPI_TOKEN is missing from the environment. Please verify your .env file.")
        return

    # Clean build artifacts
    print("[INFO] Cleaning previous build artifacts...")
    for folder in ["dist", "build"]:
        shutil.rmtree(folder, ignore_errors=True)
    for egg in [f for f in os.listdir(".") if f.endswith(".egg-info")]:
        shutil.rmtree(egg, ignore_errors=True)

    python_exe = sys.executable
    print(f"[INFO] Using Python executable: {python_exe}")

    # Build package
    print("[INFO] Building distribution packages (python -m build)...")
    try:
        subprocess.run([python_exe, "-m", "build"], check=True)
        print("[SUCCESS] Package build completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Package build failed: {e}")
        return

    # Upload package
    print("[INFO] Uploading package to PyPI (python -m twine upload dist/*)...")
    try:
        env = os.environ.copy()
        env["TWINE_USERNAME"] = "__token__"
        env["TWINE_PASSWORD"] = pypi_token

        subprocess.run(
            [python_exe, "-m", "twine", "upload", "dist/*"],
            env=env,
            check=True
        )
        print("[SUCCESS] Upload completed successfully.")

    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Upload failed: {e}")
    except FileNotFoundError:
        print("[ERROR] The 'twine' module was not found. Please install it with 'pip install twine'.")

    print("=== Deployment process finished ===")


if __name__ == "__main__":
    deploy_package()
