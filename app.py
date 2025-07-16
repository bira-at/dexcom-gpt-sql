import streamlit as st
import pandas as pd
import requests
import urllib.parse
from openai import OpenAI
import datetime
import altair as alt
import json

# Init OpenAI
client = OpenAI(api_key=st.secrets["openai"]["api_key"])

# Page Config
st.set_page_config(page_title="Blutzucker GPT Dashboard", layout="wide")
st.title("🧠 Blutzucker-Analyse mit GPT & Zielbereich")

# Sidebar: Datumsauswahl
st.sidebar.header("📅 Datumsfilter")
start_date = st.sidebar.date_input("Von", value=datetime.date.today() - datetime.timedelta(days=7))
end_date = st.sidebar.date_input("Bis", value=datetime.date.today())
if start_date > end_date:
    st.sidebar.error("Startdatum darf nicht nach dem Enddatum liegen.")
    st.stop()

# Texteingabe
frage = st.text_input("Frage an GPT oder SQL-Abfrage (z. B. 'Durchschnitt', 'Hypoglykämien'):")

# GPT -> SQL

def frage_zu_sql(frage, start_date, end_date):
    prompt = f"""
    Du bist SQL-Experte. Die Tabelle heißt `Blutzucker` mit Spalten:
    - `Uhrzeit` (DATETIME)
    - `Wert` (INTEGER)

    Schreibe ein SQL-Statement für folgende Benutzerfrage in MySQL Syntax:
    '{frage}'

    Es sollen nur Daten zwischen '{start_date} 00:00:00' und '{end_date} 23:59:59' berücksichtigt werden.

    Gib nur das SQL zurück (keine Erklärung), MySQL-Syntax.
    """
    res = client.completions.create(
        model='gpt-3.5-turbo-instruct',
        prompt=prompt,
        temperature=0,
        max_tokens=150,
        stop=["#", ";"]
    )
    return res.choices[0].text.strip()

def baue_sql_ohne_frage(start_date, end_date):
    return f"SELECT * FROM Blutzucker WHERE Uhrzeit BETWEEN '{start_date} 00:00:00' AND '{end_date} 23:59:59'"

# SQL generieren
verwende_gpt = frage and not any(kw in frage.lower() for kw in ["hypo", "schwank", "analyse", "erkläre"])
sql = frage_zu_sql(frage, start_date, end_date) if verwende_gpt else baue_sql_ohne_frage(start_date, end_date)

# SQL-Anzeige
st.subheader("🧾 SQL-Abfrage")
st.code(sql, language="sql")

# Daten abrufen
encoded = urllib.parse.quote(sql)
url = f"https://bira.at/cgi-bin/get_dexcom.py?query={encoded}"
res = requests.get(url)

if not res.ok or not res.text.strip():
    st.error("❌ Fehler beim Abrufen der Daten")
    st.code(res.text or "Keine Antwort vom Server")
    st.stop()

# JSON extrahieren
try:
    json_start = res.text.find("{")
    parsed = json.loads(res.text[json_start:])
    data = parsed.get("data", [])
    if not data:
        st.warning("⚠️ JSON erhalten, aber keine Daten vorhanden.")
        st.stop()
    df = pd.DataFrame(data)
except Exception as e:
    st.error("🧨 Fehler beim Parsen der JSON-Antwort:")
    st.exception(e)
    st.stop()

# Zeitreihe & Zielbereich
if "Uhrzeit" in df.columns and "Wert" in df.columns:
    df["Uhrzeit"] = pd.to_datetime(df["Uhrzeit"])
    df = df.sort_values("Uhrzeit")
    df["Zone"] = pd.cut(df["Wert"],
                         bins=[-float("inf"), 70, 180, float("inf")],
                         labels=["Unterzuckerung", "Normalbereich", "Überzuckerung"])

    # Line Chart
    st.line_chart(df.set_index("Uhrzeit")["Wert"])

    # Dashboard
    st.subheader("📊 Dashboard")
    col1, col2, col3 = st.columns(3)
    col1.metric("Min", int(df["Wert"].min()))
    col2.metric("Max", int(df["Wert"].max()))
    col3.metric("Durchschnitt", round(df["Wert"].mean(), 1))

    # Zielbereich Visualisierung
    st.subheader("📈 Verlauf mit Zielbereich")
    farbe = alt.Scale(domain=["Unterzuckerung", "Normalbereich", "Überzuckerung"],
                      range=["red", "green", "orange"])
    chart = alt.Chart(df).mark_circle(size=60).encode(
        x="Uhrzeit:T",
        y="Wert:Q",
        color=alt.Color("Zone:N", scale=farbe),
        tooltip=["Uhrzeit", "Wert", "Zone"]
    ).properties(height=400).interactive()
    st.altair_chart(chart, use_container_width=True)
else:
    st.dataframe(df)
    if df.shape == (1, 1):
        st.metric("Ergebnis", df.iloc[0, 0])

# GPT-Analyse bei Bedarf
if frage and any(kw in frage.lower() for kw in ["hypo", "schwank", "analyse", "erkläre"]):
    st.subheader("🧠 GPT-Analyse")
    #daten_input = df[["Uhrzeit", "Wert"]].to_csv(index=False)
    daten_input = df[["Uhrzeit", "Wert"]].tail(100).to_csv(index=False)

    analyse_prompt = f"""
    Du bist ein medizinischer Datenanalyst. Analysiere diese Blutzuckerdaten aus einer CSV mit Spalten 'Uhrzeit' und 'Wert' (mg/dl):

    {daten_input}

    Frage des Nutzers: '{frage}'

    Erkläre die Werte, Schwankungen oder kritischen Bereiche auf Deutsch in einfacher Sprache.
    """
    with st.spinner("GPT analysiert Blutzuckerwerte..."):
        res = client.completions.create(
            model="gpt-3.5-turbo-instruct",
            prompt=analyse_prompt,
            temperature=0.7,
            max_tokens=600
        )
        st.success("Analyse abgeschlossen")
        st.markdown(res.choices[0].text.strip())

# Rohdaten
with st.expander("📋 Rohdaten anzeigen"):
    st.dataframe(df, use_container_width=True)
