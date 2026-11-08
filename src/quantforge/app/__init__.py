"""quantforge web app (Streamlit). Settings come from environment variables or a ``.env`` file
in the folder you launch from; they are loaded here, before branding and certificates read
them."""

from quantforge.data.base import _load_dotenv_once

_load_dotenv_once()
