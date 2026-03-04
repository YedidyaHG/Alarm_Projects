import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import branca.colormap as cm

# הגדרת כותרת לעמוד
st.set_page_config(page_title="מפת אזעקות ידידיה הס-גרין", layout="wide")
st.title("ניתוח אזעקות לפי תאריכים")

# טעינת הנתונים
@st.cache_data(ttl=3600)
def load_data():
    url = "https://raw.githubusercontent.com/yuval-harpaz/alarms/master/data/alarms.csv"     # הכתובת הישירה לקובץ של יובל הרפז
    # טעינה מהאינטרנט במקום מהקובץ המקומי
    df = pd.read_csv(url)
    # טעינת נתוני הקואורדינטות מהקובץ שלך בגיטהאב
    coord = pd.read_csv('coord.csv')
    
    df['time'] = pd.to_datetime(df['time'])
    return df, coord

df_raw, coord = load_data()

# --- תפריט צד (Sidebar) לסינונים ---
st.sidebar.header("מסננים")

# 1. סינון תאריכים עם ברירת מחדל ספציפית
start_default = pd.Timestamp('2026-02-28').date()
end_default = pd.Timestamp('2026-03-04').date()

date_range = st.sidebar.date_input("בחר טווח תאריכים", [start_default, end_default])

# 2. סינון מדינת מקור (Origin)
origins = df_raw['origin'].unique().tolist()
selected_origins = st.sidebar.multiselect("מקור הירי", origins, default=origins)

# 3. סינון סוג איום (Description)
threats = df_raw['description'].unique().tolist()
selected_threats = st.sidebar.multiselect("סוג האיום", threats, default=threats)

# --- עיבוד הנתונים לפי הסינון ---
mask = (
    (df_raw['time'].dt.date >= date_range[0]) & 
    (df_raw['time'].dt.date <= date_range[1]) &
    (df_raw['origin'].isin(selected_origins)) &
    (df_raw['description'].isin(selected_threats))
)
filtered_df = df_raw[mask]

# קיבוץ לפי עיר ומיזוג עם קואורדינטות
summary_df = filtered_df.groupby("cities").size().reset_index(name='alarm_count')
final_df = pd.merge(summary_df, coord, left_on='cities', right_on='loc', how='inner')

# --- יצירת המפה ---
if not final_df.empty:
    colormap = cm.LinearColormap(
        colors=['blue', 'green', 'yellow', 'orange', 'red'],
        vmin=final_df["alarm_count"].min(), 
        vmax=final_df["alarm_count"].max(),
        caption='כמות אזעקות'
    )

    m = folium.Map(location=[31.5, 35.0], zoom_start=7)

    for _, row in final_df.iterrows():
        folium.CircleMarker(
            location=(row['lat'], row['long']),
            radius=8,
            popup=f"{row['cities']}: {row['alarm_count']}",
            color=colormap(row['alarm_count']),
            fill=True,
            fill_color=colormap(row['alarm_count']),
            fill_opacity=0.7,
        ).add_to(m)

    colormap.add_to(m)
    
    # הצגת המפה ב-Streamlit
    st_folium(m, width=1000, height=600)
    
    # הצגת הטבלה מתחת
    st.write("נתונים מסוננים:", final_df[['cities', 'alarm_count']])
else:

    st.warning("אין נתונים התואמים לסינון הנבחר.")


