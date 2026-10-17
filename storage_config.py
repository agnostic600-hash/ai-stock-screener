"""Never print a DSN or credentials. Environment for CLI; Streamlit secrets for hosted UI."""
import os

def database_url():
    value=os.getenv('DISCOVERY_DATABASE_URL')
    if value:return value
    import streamlit as st
    try:return st.secrets.get('DISCOVERY_DATABASE_URL')
    except (FileNotFoundError,st.errors.StreamlitSecretNotFoundError):return None
