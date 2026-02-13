import subprocess
import os
import sys
import shutil


def deploy_package():
    print("=== Starting Plotune SDK deployment ===")

    pypi_token = os.getenv("PYPI_TOKEN")
    if not pypi_token:
        print("[ERROR] PYPI_TOKEN is missing from environment variables.")
        sys.exit(1)

    print("[INFO] Cleaning previous build artifacts...")
    for folder in ["dist", "build"]:
        shutil.rmtree(folder, ignore_errors=True)

    print("[INFO] Building distribution packages with uv...")
    try:
        subprocess.run(["uv", "build"], check=True)
        print("[SUCCESS] Package build completed.")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Build failed: {e}")
        sys.exit(1)

    print("[INFO] Uploading package to PyPI...")
    try:
        subprocess.run(
            [
                "uv",
                "publish",
                "--token",
                pypi_token,
            ],
            check=True,
        )
        print("[SUCCESS] Plotune SDK published successfully.")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Upload failed: {e}")
        sys.exit(1)

    print("=== Deployment process finished ===")


if __name__ == "__main__":
    deploy_package()
