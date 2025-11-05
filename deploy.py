import subprocess
import os
from dotenv import load_dotenv

def deploy_package():
    print("🚀 Loading .env file...")
    load_dotenv()
    
    pypi_token = os.getenv("PYPI_TOKEN")

    if not pypi_token:
        print("❌ ERROR: PYPI_TOKEN environment variable not found in the .env file.")
        print("Please check the contents of your .env file.")
        return

    # 2. Clean up previous distribution files (Optional but good practice)
    print("🧹 Cleaning up previous 'dist' folder and '__pycache__' files...")
    try:
        # Note: This command is for Unix-like systems (Linux/macOS). 
        # Adjust if you are strictly on Windows (e.g., use 'shutil.rmtree')
        subprocess.run(["rm", "-rf", "dist", "build", "*.egg-info"], check=True)
    except FileNotFoundError:
        pass # Ignore if 'rm' is not found or files don't exist

    # 3. Build the package (.whl and .tar.gz)
    print("📦 Building distribution packages (python -m build)...")
    try:
        subprocess.run(["python", "-m", "build"], check=True)
        print("✅ Packages successfully built.")
    except subprocess.CalledProcessError as e:
        print(f"❌ ERROR: Package build failed. Error: {e}")
        return

    # 4. Upload the package to PyPI using Twine
    print("📤 Uploading to PyPI (python -m twine upload dist/*)...")
    try:
        # We pass the token directly to Twine using ENV variables.
        # TWINE_USERNAME must be "__token__".
        # TWINE_PASSWORD is the actual token from the .env file.
        env = os.environ.copy()
        env["TWINE_USERNAME"] = "__token__"
        env["TWINE_PASSWORD"] = pypi_token

        subprocess.run(
            ["python", "-m", "twine", "upload", "dist/*"],
            env=env,
            check=True
        )
        print("🎉 Upload completed successfully!")

    except subprocess.CalledProcessError as e:
        print(f"❌ ERROR: Twine upload failed. Error: {e}")
    except FileNotFoundError:
        print("❌ ERROR: 'twine' module not found. Please install it with 'pip install twine'.")


if __name__ == "__main__":
    deploy_package()