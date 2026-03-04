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
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📍 מפת אזעקות", "📊 ניתוח עיר", "⚔️ השוואת ערים", "💡 עובדות מעניינות", "עזרו לנו להשתפר! 🚀"])
    
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
            colors=['#006400', '#90EE90', '#FFFF00', '#FF8C00', '#800026'],
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
    
    city_list = sorted(df_raw['cities'].unique().tolist())
    try:
        ks_index = city_list.index("קריית שמונה")
    except ValueError:
        ks_index = 0

    selected_city = st.selectbox("בחר עיר לניתוח:", city_list, index=ks_index)
    
    # שימוש ב-copy כדי לא לשנות את הדאטה המקורי
    city_data = df_filtered[df_filtered['cities'] == selected_city].copy()
    
    if not city_data.empty:
        city_top_day = city_data['time'].dt.date.value_counts().idxmax()
        city_top_day_val = city_data['time'].dt.date.value_counts().max()
        st.info(f"🏠 **ב{selected_city}, היום העמוס ביותר היה:** {city_top_day.strftime('%d/%m/%Y')} עם {city_top_day_val} אזעקות.")

        # --- הוספת בחירת רזולוציה ---
        res_city = st.radio("רזולוציית זמן לתצוגה:", ["יום", "שבוע", "חודש"], horizontal=True, key="res_city")
        res_map_city = {"יום": "D", "שבוע": "W", "חודש": "M"}
        
        # יצירת עמודת זמן מקובצת
        city_data['period'] = city_data['time'].dt.to_period(res_map_city[res_city]).dt.to_timestamp()
        
        # יצירת הגרף לפי ה-period החדש
        fig = px.bar(city_data.groupby(['period', 'origin']).size().reset_index(name='count'), 
                     x="period", y="count", color="origin", 
                     labels={'period': 'זמן', 'count': 'כמות אזעקות', 'origin': 'מקור הירי'},
                     barmode='stack',
                     title=f"התפלגות אזעקות ב{selected_city} לפי {res_city}")

        # עיצוב העמודות (דקות עם קווים שחורים)
        fig.update_traces(
            marker_line_width=1,
            marker_line_color="black"
        )
        
        fig.update_layout(
            bargap=0.3, # הופך את העמודות ליותר דקות (רווח גדול יותר)
            xaxis_title="זמן",
            yaxis_title="כמות אזעקות",
            legend_title="מקור",
            hovermode="x unified"
        )
        
        st.plotly_chart(fig, use_container_width=True)

        # חישוב סך האזעקות לעיר בטווח שנבחר
        total_city_alerts = len(city_data)

        # גרף עוגה עם כותרת דינמית
        enemy_counts = city_data['origin'].value_counts().reset_index()
        enemy_counts.columns = ['אויב', 'כמות']
        
        fig_pie = px.pie(enemy_counts, values='כמות', names='אויב', hole=0.4,
                         title=f"פילוח מקורות הירי ל{selected_city} (סך הכל: {total_city_alerts} אזעקות)",
                         color_discrete_sequence=px.colors.qualitative.Pastel)
        
        st.plotly_chart(fig_pie, use_container_width=True)
        
    else:
        st.info(f"לא נמצאו אזעקות ב{selected_city} בטווח שנבחר.")

# --- TAB 3: השוואת ערים ---
with tab3:
    st.subheader("השוואה בין שתי ערים")
    
    # הופך את רשימת הערים לרשימה רגילה כדי שנוכל לחפש בה אינדקס
    city_list = sorted(df_raw['cities'].unique().tolist())
    
    # 1. מציאת המיקום (index) של הערים שביקשת כברירת מחדל
    try:
        default_index_1 = city_list.index("תל אביב - דרום העיר ויפו")
    except ValueError:
        default_index_1 = 0 # אם לא מצא, יבחר את הראשונה ברשימה
        
    try:
        default_index_2 = city_list.index("ירושלים - מערב")
    except ValueError:
        default_index_2 = min(1, len(city_list)-1)

    # 2. יצירת תיבות הבחירה עם ה-index שמצאנו
    col1, col2 = st.columns(2)
    with col1:
        city1 = st.selectbox("עיר א':", city_list, index=default_index_1)
    with col2:
        city2 = st.selectbox("עיר ב':", city_list, index=default_index_2)
    
    # 3. סינון הנתונים להשוואה
    comp_df = df_filtered[df_filtered['cities'].isin([city1, city2])].copy()
    
    if not comp_df.empty:
        comp_df['time'] = pd.to_datetime(comp_df['time']) 
        
        res = st.radio("רזולוציית זמן לגרף:", ["יום", "שבוע", "חודש"], horizontal=True)
        res_map = {"יום": "D", "שבוע": "W", "חודש": "M"} 
        
        comp_df['period'] = comp_df['time'].dt.to_period(res_map[res]).dt.to_timestamp()
        chart_data = comp_df.groupby(['period', 'cities']).size().reset_index(name='count')
        
        # 4. יצירת הגרף
        fig2 = px.bar(chart_data, x="period", y="count", color="cities",
                      barmode='group', title=f"השוואת {city1} מול {city2}",
                      labels={'period': 'זמן', 'count': 'כמות אזעקות', 'cities': 'עיר'},
                      color_discrete_sequence=["#EF553B", "#636EFA"])
        
        # הוספת יישור לימין לגרף
        fig2.update_layout(xaxis_title="זמן", yaxis_title="כמות אזעקות", legend_title="עיר")
        
        st.plotly_chart(fig2, use_container_width=True)
        
        st.markdown(f"**סיכום בתקופה הנבחרת:**")
        st.write(f"- {city1}: {len(comp_df[comp_df['cities'] == city1])} אזעקות")
        st.write(f"- {city2}: {len(comp_df[comp_df['cities'] == city2])} אזעקות")
    else:
        st.info("אין מספיק נתונים להשוואה בטווח ובסינון שנבחר.")



    # --- TAB 4: עובדות מעניינות ---
    with tab4:
        st.subheader("💡 עובדות מעניינות")
        
        # סינון זיהויי שווא כדי לא להטות את הסטטיסטיקה
        df_stats = df_filtered[df_filtered['origin'] != 'FA'].copy()
        
        if not df_stats.empty:
            col1, col2 = st.columns(2)
            with col1:
                top_city = df_stats['cities'].value_counts().idxmax()
                st.metric("העיר המטווחת ביותר", top_city)
                
                top_day = df_stats['time'].dt.date.value_counts().idxmax()
                st.metric("היום העמוס ביותר", top_day.strftime('%d/%m/%Y'))
    
            with col2:
                city_counts = df_stats['cities'].value_counts()
                bottom_city = city_counts.idxmin()
                st.metric("העיר עם הכי פחות (מעל 0)", bottom_city)
                
                # יום רב זירתי
                enemies_per_day = df_stats.groupby(df_stats['time'].dt.date)['origin'].nunique()
                top_enemy_day = enemies_per_day.idxmax()
                enemies_list = df_stats[df_stats['time'].dt.date == top_enemy_day]['origin'].unique().tolist()
                st.metric("יום רב-זירתי מקסימלי", top_enemy_day.strftime('%d/%m/%Y'))
                st.caption(f"האויבים שתקפו: {', '.join(enemies_list)}")
    
            st.divider()
            
            # גרף שעות עם צבעי אויב
            st.write("### ⏰ השעה עם הסיכוי הכי גבוה לאזעקה")
            df_stats['hour'] = df_stats['time'].dt.hour
            hour_data = df_stats.groupby(['hour', 'origin']).size().reset_index(name='count')
            
            fig_hour = px.bar(hour_data, x='hour', y='count', color='origin',
                              labels={'hour': 'שעה ביממה', 'count': 'כמות אזעקות', 'origin': 'מקור הירי'},
                              barmode='stack')
    
            fig_hour.update_traces(marker_line_width=1, marker_line_color="black")
            fig_hour.update_layout(
                xaxis=dict(tickmode='linear', tick0=0, dtick=1),
                bargap=0.3, # רווח גדול יותר = עמודות דקות יותר
                hovermode="x unified"
            )
            st.plotly_chart(fig_hour, use_container_width=True)
            
            # היום הכי שקט
            all_days_count = df_stats.groupby(df_stats['time'].dt.date).size()
            quietest_day = all_days_count.idxmin()
            st.success(f"🕊️ **היום השקט ביותר בטווח זה:** {quietest_day.strftime('%d/%m/%Y')} (רק {all_days_count.min()} אזעקות)")
        else:
            st.info("אין מספיק נתונים להצגת עובדות.")
        
    # --- TAB 5: פידבק ושיפורים ---
    with tab5:
        st.subheader("עזרו לנו להשתפר! 🚀")
        st.write("יש לכם רעיון לפיצ'ר חדש? מצאתם טעות בנתונים? נשמח לשמוע.")
        
        # המרת הלינק שלך לפורמט הטמעה (embedded)
        form_url = "https://docs.google.com/forms/d/e/1FAIpQLScieeNG66uGquJR_lEwIUp3Ynsl6TKDjRkvoOQ7gFC2Pnrl1Q/viewform?embedded=true"
        
        # הצגת הטופס בתוך האפליקציה
        st.components.v1.iframe(form_url, height=800, scrolling=True)








