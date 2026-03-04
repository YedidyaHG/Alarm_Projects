import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import branca.colormap as cm
import plotly.express as px
from datetime import date

st.set_page_config(page_title="ניתוח אזעקות ישראל", layout="wide")

@st.cache_data(ttl=3600)
def load_data():
    url = "https://raw.githubusercontent.com/yuval-harpaz/alarms/master/data/alarms.csv"
    df = pd.read_csv(url)
    coord = pd.read_csv('coord.csv')
    df['time'] = pd.to_datetime(df['time'])
    return df, coord

df_raw, coord = load_data()

# --- תפריט צד (Sidebar) עם כל המסננים ---
st.sidebar.header("מסננים גלובליים")

# 1. סינון תאריכים
default_start = date(2026, 2, 28)
default_end = date(2026, 3, 4)
date_range = st.sidebar.date_input("טווח תאריכים", [default_start, default_end])

# 2. סינון מקור הירי (Origin)
all_origins = sorted(df_raw['origin'].dropna().unique().tolist())
selected_origins = st.sidebar.multiselect("מקור הירי", all_origins, default=all_origins)

# 3. סינון סוג האיום (Description)
all_threats = sorted(df_raw['description'].dropna().unique().tolist())
selected_threats = st.sidebar.multiselect("סוג האיום", all_threats, default=all_threats)

# --- החלת כל המסננים על הדאטא ---
mask = (
    (df_raw['time'].dt.date >= date_range[0]) & 
    (df_raw['time'].dt.date <= date_range[1]) &
    (df_raw['origin'].isin(selected_origins)) &
    (df_raw['description'].isin(selected_threats))
)
df_filtered = df_raw[mask]

# יצירת טאבים לממשק נקי
tab1, tab2, tab3 = st.tabs(["📍 מפת אזעקות", "📊 ניתוח עיר בודדת", "⚔️ השוואת ערים"])

# --- TAB 1: המפה ---
with tab1:
    st.subheader("מפת אזעקות אינטראקטיבית")
    summary_df = df_filtered.groupby("cities").size().reset_index(name='alarm_count')
    final_df = pd.merge(summary_df, coord, left_on='cities', right_on='loc', how='inner')
    
    # בתוך tab1, תחת יצירת המפה:
    if not final_df.empty:
        m = folium.Map(location=[31.5, 35.0], zoom_start=7)
        
        # הגדרת הצבעים לפי הסדר שביקשת (מהנמוך לגבוה)
        # ירוק כהה (מעט אזעקות) -> ירוק בהיר -> צהוב -> כתום -> אדום (הרבה אזעקות)
        colormap = cm.LinearColormap(
            colors=['#ffffb2', '#fecc5c', '#fd8d3c', '#f03b20', '#bd0026'],
            vmin=float(final_df["alarm_count"].min()), 
            vmax=float(final_df["alarm_count"].max()),
            caption='כמות אזעקות'
        )
        
        for _, row in final_df.iterrows():
            folium.CircleMarker(
                location=(row['lat'], row['long']),
                radius=8,
                popup=f"{row['cities']}: {row['alarm_count']}",
                color=colormap(row['alarm_count']), 
                fill=True,
                fill_color=colormap(row['alarm_count']), 
                fill_opacity=0.7
            ).add_to(m)
            
        colormap.add_to(m)
        st_folium(m, width=1000, height=600)
    else:
        st.warning("אין נתונים להצגה על המפה תחת המסננים שנבחרו.")

# --- TAB 2: ניתוח עיר בודדת ---
with tab2:
    st.subheader("ניתוח היסטורי לפי עיר")
    city_list = sorted(df_raw['cities'].unique())
    selected_city = st.selectbox("בחר עיר לניתוח:", city_list)
    
    # סינון הנתונים כבר כולל את המקור וסוג האיום מה-Sidebar
    city_data = df_filtered[df_filtered['cities'] == selected_city]
    
    if not city_data.empty:
        fig = px.histogram(city_data, x="time", color="origin", 
                           title=f"התפלגות אזעקות ב{selected_city} (לפי המסננים שנבחרו)",
                           labels={'time': 'זמן', 'count': 'כמות אזעקות', 'origin': 'מקור'},
                           barmode='stack',
                           color_discrete_sequence=px.colors.qualitative.Safe)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(f"לא נמצאו אזעקות ב{selected_city} התואמות לסינון.")

# --- TAB 3: השוואת ערים ---
with tab3:
    st.subheader("השוואה בין שתי ערים")
    col1, col2 = st.columns(2)
    with col1:
        city1 = st.selectbox("עיר א':", city_list, index=0)
    with col2:
        city2 = st.selectbox("עיר ב':", city_list, index=min(1, len(city_list)-1))
    
    comp_df = df_filtered[df_filtered['cities'].isin([city1, city2])]
    
    if not comp_df.empty:
        res = st.radio("רזולוציית זמן לגרף:", ["יום", "שבוע", "חודש"], horizontal=True)
        res_map = {"יום": "D", "שבוע": "W", "חודש": "ME"}
        
        comp_df['period'] = comp_df['time'].dt.to_period(res_map[res]).dt.to_timestamp()
        chart_data = comp_df.groupby(['period', 'cities']).size().reset_index(name='count')
        
        fig2 = px.bar(chart_data, x="period", y="count", color="cities",
                      barmode='group', title=f"השוואת {city1} מול {city2}",
                      labels={'period': 'זמן', 'count': 'כמות אזעקות', 'cities': 'עיר'},
                      color_discrete_sequence=["#EF553B", "#636EFA"])
        st.plotly_chart(fig2, use_container_width=True)
        
        st.markdown(f"**סיכום בתקופה הנבחרת:**")
        st.write(f"- {city1}: {len(comp_df[comp_df['cities'] == city1])} אזעקות")
        st.write(f"- {city2}: {len(comp_df[comp_df['cities'] == city2])} אזעקות")
    else:
        st.info("אין מספיק נתונים להשוואה בטווח ובסינון שנבחר.")


