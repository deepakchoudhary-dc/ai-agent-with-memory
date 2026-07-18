#!/usr/bin/env python3
"""
Setup script for Local AI Chat App with Human-like Memory
"""

import json
import os
import platform
import subprocess
import sys
import urllib.request


def print_banner():
    """Print welcome banner."""
    print("=" * 60)
    print("🚀 Local AI Chat App with Human-like Memory Setup")
    print("=" * 60)
    print()


def check_python_version():
    """Check if Python version is compatible."""
    print("📋 Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ is required. Current version:", f"{version.major}.{version.minor}.{version.micro}")
        return False

    print(f"✅ Python {version.major}.{version.minor}.{version.micro} - Compatible")
    return True


def create_virtual_environment():
    """Create and activate virtual environment."""
    print("\n🔧 Setting up virtual environment...")

    if os.path.exists("venv"):
        print("✅ Virtual environment already exists")
        return True

    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✅ Virtual environment created successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create virtual environment: {e}")
        return False


def get_activation_command():
    """Get the correct activation command for the platform."""
    system = platform.system().lower()
    if system == "windows":
        return "venv\\Scripts\\activate"
    else:
        return "source venv/bin/activate"


def install_dependencies():
    """Install Python dependencies."""
    print("\n📦 Installing Python dependencies...")

    # Get the correct pip path
    system = platform.system().lower()
    if system == "windows":
        pip_path = os.path.join("venv", "Scripts", "pip.exe")
    else:
        pip_path = os.path.join("venv", "bin", "pip")

    if not os.path.exists(pip_path):
        print("❌ Virtual environment not properly created")
        return False

    try:
        # Upgrade pip first
        subprocess.run([pip_path, "install", "--upgrade", "pip"], check=True)

        # Install requirements
        subprocess.run([pip_path, "install", "-r", "requirements.txt"], check=True)
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False


def check_ollama_installation():
    """Check if Ollama is installed and running."""
    print("\n🤖 Checking Ollama installation...")

    try:
        # Try to connect to Ollama
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                models = [model.get("name", "") for model in data.get("models", [])]

                print("✅ Ollama is running")
                print(f"📝 Available models: {', '.join(models) if models else 'None'}")

                # Check for any model
                if models:
                    print(f"✅ Available models found: {', '.join(models)}")
                    return True
                else:
                    print("⚠️  No models found in Ollama")
                    return False
            else:
                print("❌ Ollama is not responding properly")
                return False

    except Exception as e:
        print(f"❌ Cannot connect to Ollama: {e}")
        print("\n💡 Please ensure Ollama is installed and running:")
        print("   1. Visit https://ollama.ai to download Ollama")
        print("   2. Install and start Ollama")
        print("   3. Run: ollama pull <model-name>")
        return False


def create_env_file():
    """Create .env file from template if it doesn't exist."""
    print("\n⚙️  Setting up environment configuration...")

    if os.path.exists(".env"):
        print("✅ .env file already exists")
        return True

    if os.path.exists(".env.example"):
        try:
            with open(".env.example") as source:
                content = source.read()

            with open(".env", "w") as dest:
                dest.write(content)

            print("✅ .env file created from template")
            print("💡 You can customize settings in the .env file")
            return True
        except Exception as e:
            print(f"❌ Failed to create .env file: {e}")
            return False
    else:
        print("⚠️  .env.example not found, skipping .env creation")
        return True


def run_tests():
    """Run basic tests to verify installation."""
    print("\n🧪 Running basic tests...")

    system = platform.system().lower()
    if system == "windows":
        python_path = os.path.join("venv", "Scripts", "python.exe")
    else:
        python_path = os.path.join("venv", "bin", "python")

    try:
        result = subprocess.run([python_path, "test_app.py"], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            print("✅ Basic tests passed")
            return True
        else:
            print("⚠️  Some tests failed (this might be normal if Ollama isn't running)")
            print("Output:", result.stdout[-200:] if result.stdout else "No output")
            return True  # Don't fail setup for test failures
    except subprocess.TimeoutExpired:
        print("⚠️  Tests timed out (this might be normal)")
        return True
    except Exception as e:
        print(f"⚠️  Could not run tests: {e}")
        return True


def print_next_steps():
    """Print next steps for the user."""
    print("\n" + "=" * 60)
    print("🎉 Setup completed successfully!")
    print("=" * 60)
    print()
    print("📋 Next steps:")
    print("1. Ensure Ollama is running with a local model:")
    print("   ollama pull <model-name>")
    print("   ollama run <model-name>")
    print()
    print("2. Activate the virtual environment:")
    print(f"   {get_activation_command()}")
    print()
    print("3. Start the application:")
    print("   python app.py")
    print()
    print("4. Open your browser and visit:")
    print("   http://localhost:5000")
    print()
    print("💡 Tips:")
    print("- Check the README.md for detailed documentation")
    print("- Customize settings in the .env file")
    print("- Visit /health endpoint to check system status")
    print()


def main():
    """Main setup function."""
    print_banner()

    success = True

    # Check Python version
    if not check_python_version():
        success = False

    # Create virtual environment
    if success and not create_virtual_environment():
        success = False

    # Install dependencies
    if success and not install_dependencies():
        success = False

    # Check Ollama (non-critical)
    ollama_ok = check_ollama_installation()

    # Create .env file
    if success and not create_env_file():
        success = False

    # Run tests (non-critical)
    if success:
        run_tests()

    if success:
        print_next_steps()
        if not ollama_ok:
            print("⚠️  Note: Ollama setup is required for full functionality")
    else:
        print("\n❌ Setup failed. Please check the errors above and try again.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
