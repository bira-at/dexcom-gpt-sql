import streamlit as st
import pandas as pd
import requests
import openai
import urllib.parse
import streamlit_speech_recognition as sr

openai.api_key = st.secrets["openai_api_key"]

st.set_page_config(page_title="Blutzucker GPT", layout="centered")
st.title("🧠 Blutzucker-Analyse mit Sprache & GPT")

# Spracheingabe
spoken = sr.speech_to_text(language="de-DE", start_prompt="Sprich deine Frage…")
frage = spoken or st.text_input("Oder gib deine Frage ein:")

def frage_zu_sql(frage):
    prompt = f"""
    Du bist SQL-Experte. Die Tabelle heißt `Blutzucker` mit Spalten:
    - `Uhrzeit` (DATETIME)
    - `Wert` (INTEGER)

    Benutzerfrage: {frage}
    Gib nur das passende SQL-Statement zurück, ohne Erklärung.
    """
    res = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return res.choices[0].message["content"].strip()

if frage:
    with st.spinner("GPT fordert SQL..."):
        sql = frage_zu_sql(frage)
        st.code(sql, language="sql")

    encoded = urllib.parse.quote(sql)
    url = f"https://bira.at/cgi-bin/get_dexcom.py?query={encoded}"
    res = requests.get(url)

    if res.ok:
        data = res.json().get("data", [])
        if data:
            df = pd.DataFrame(data, columns=["Uhrzeit", "Wert"])
            df["Uhrzeit"] = pd.to_datetime(df["Uhrzeit"])
            st.success("Daten geladen")
            st.dataframe(df)
            st.line_chart(df.set_index("Uhrzeit")["Wert"])
        else:
            st.warning("Keine Daten erhalten.")
    else:
        st.error("Fehler beim Laden der Daten.")
