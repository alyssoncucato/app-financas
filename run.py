import streamlit.web.bootstrap
import sys
from pathlib import Path

if __name__ == "__main__":
    # Aponta para o arquivo principal do app
    flag_file = Path(__file__).parent / "app.py"
    sys.argv = [
        "streamlit",
        "run",
        str(flag_file),
        "--global.developmentMode=false",
        "--server.headless=true"
    ]
    streamlit.web.bootstrap.run()