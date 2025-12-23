# How to run FASTAPI application

1. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   ```
2. Activate the virtual environment:
   On macOS and Linux:

   ```bash
   source .venv/bin/activate
   ```

   On Windows Bash:

   ```bash
   source .venv/Scripts/activate
   ```

   On Windows PowerShell:

   ```bash
   .venv\Scripts\Activate.ps1
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   fastapi dev main.py
   ```
