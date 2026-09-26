"""Streamlit Cloud entry point.

Streamlit Cloud defaults to looking for `streamlit_app.py`. The real app lives in
`app.py`; this thin shim just runs it so deployment works with the default main
file path.
"""

from app import main

if __name__ == "__main__":
    main()
