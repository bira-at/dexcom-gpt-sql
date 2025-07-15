import streamlit as st
import pandas as pd
import requests
#import openai
import urllib.parse
#import streamlit_speech_recognition as sr

from openai import OpenAI

client = OpenAI(
  api_key=st.secrets["openai"]["api_key"]  # this is also the default, it can be omitted
)

st.set_page_config(page_title="Blutzucker GPT", layout="centered")
st.title("🧠 Blutzucker-Analyse mit Sprache & GPT")

# Spracheingabe
#spoken = sr.speech_to_text(language="de-DE", start_prompt="Sprich deine Frage…")
frage = st.text_input("Oder gib deine Frage ein:")

def frage_zu_sql(frage):
    prompt = f"""
    Du bist SQL-Experte. Die Tabelle heißt `Blutzucker` mit Spalten:
    - `Uhrzeit` (DATETIME)
    - `Wert` (INTEGER)

    Benutzerfrage: {frage}
    Gib nur das passende SQL-Statement, die Datenbank ist MySQL,  zurück, ohne Erklärung.
    """
  #  res = openai.ChatCompletion.create(
  #      model="gpt-4",
  #      messages=[{"role": "user", "content": prompt}],
  #      temperature=0
  #  )

    res  = client.completions.create(model='gpt-3.5-turbo-instruct',prompt=prompt,temperature=0,max_tokens=150,stop=["#",";"])
      #model='gpt-3.5-turbo-instruct',prompt=prompt)
    return res.choices[0].text.strip()

if frage:
    with st.spinner("GPT fordert SQL..."):
        sql = frage_zu_sql(frage)
        st.code(sql, language="sql")

    encoded = urllib.parse.quote(sql)
    url = f"https://bira.at/cgi-bin/get_dexcom.py?query={encoded}"
    res = requests.get(url)

    if res.ok:
        try:
            st.write("📩 Rohantwort vom Server:")
            st.code(res.text)
            data = res.json().get("data", [])
            if not data:
                st.warning("Keine Daten erhalten.")
                st.stop()
        except Exception as e:
            st.error("Fehler beim Verarbeiten der Antwort:")
            st.exception(e)
            st.stop()
    else:
        st.error(f"Serverantwort: {res.status_code}")
        st.code(res.text)
        st.stop()
