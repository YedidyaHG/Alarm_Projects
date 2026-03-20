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

# הסרת שורות של יישובים ספציפיים
cities_to_remove = ['תקומה וחוות יזרעם', 'חיפה-מפרץ']
df_raw = df_raw[~df_raw['cities'].isin(cities_to_remove)]
# איחוד שמות כפולים 
df_raw['cities'] = df_raw['cities'].replace({
    'ינוח-ג\'ת': 'ינוח ג\'ת', 
    'ינוח ג\'ת ': 'ינוח ג\'ת',
    'כפר יסיף': 'כפר יאסיף'
})

# --- תפריט צד (Sidebar) עם כל המסננים ---
st.sidebar.header("מסננים גלובליים")

# 1. סינון תאריכים
default_start = date(2026, 2, 28)
default_end = date(2026, 3, 29)
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
    st.subheader("⚔️ השוואת כמות אזעקות בין ערים")

    # אתחול מספר הערים ב-session_state אם הוא לא קיים
    if 'num_cities' not in st.session_state:
        st.session_state.num_cities = 2

    # שורת כפתורי שליטה
    col_btn1, col_btn2, _ = st.columns([1, 1, 2])
    with col_btn1:
        if st.button("➕ הוסף עיר להשוואה"):
            st.session_state.num_cities += 1
            st.rerun() # מרענן כדי להציג את התיבה החדשה מיד
    with col_btn2:
        if st.button("🔄 איפוס השוואה"):
            st.session_state.num_cities = 2
            st.rerun()

    selected_cities = []
    city_list = sorted(df_raw['cities'].unique().tolist())

    # הגדרת שמות ברירת המחדל
    default_names = ["קריית שמונה", "תל אביב - מרכז העיר"]

    # יצירת תיבות בחירה
    cols = st.columns(min(st.session_state.num_cities, 4)) # מקסימום 4 עמודות בשורה לנראות טובה
    
    for i in range(st.session_state.num_cities):
        # מחליט באיזו עמודה לשים את התיבה (מציג בשורות של 4)
        col_idx = i % 4
        with cols[col_idx]:
            # לוגיקה לבחירת אינדקס ברירת מחדל
            if i < len(default_names) and default_names[i] in city_list:
                d_idx = city_list.index(default_names[i])
            else:
                d_idx = i % len(city_list) # ברירת מחדל רנדומלית לשאר התיבות
            
            city = st.selectbox(f"עיר {i+1}:", city_list, index=d_idx, key=f"city_comp_{i}")
            selected_cities.append(city)

    # סינון הנתונים להשוואה
    compare_data = df_filtered[df_filtered['cities'].isin(selected_cities)].copy()

    if not compare_data.empty:
        st.write("---")
        res_comp = st.radio("רזולוציה:", ["יום", "שבוע", "חודש"], horizontal=True, key="res_comp_multi")
        res_map = {"יום": "D", "שבוע": "W", "חודש": "M"}
        
        compare_data['period'] = compare_data['time'].dt.to_period(res_map[res_comp]).dt.to_timestamp()
        comp_grouped = compare_data.groupby(['period', 'cities']).size().reset_index(name='count')
        
        fig_comp = px.bar(comp_grouped, x="period", y="count", color="cities",
                          barmode="group",
                          title=f"השוואת אזעקות: {' vs '.join(selected_cities)}",
                          labels={'period': 'זמן', 'count': 'כמות אזעקות', 'cities': 'עיר'})

        fig_comp.update_traces(marker_line_width=1, marker_line_color="black")
        fig_comp.update_layout(bargap=0.2, hovermode="x unified")
        
        st.plotly_chart(fig_comp, use_container_width=True)
    else:
        st.info("בחר ערים כדי להציג השוואה.")
    
    st.write("### 📈 סיכום נתונים להשוואה")
    
    # חישוב סך האזעקות לכל עיר שנבחרה בטווח הזמן
    summary_data = compare_data['cities'].value_counts()
    
    # יצירת עמודות להצגת הסיכומים (מספר העמודות כמספר הערים שנבחרו)
    cols_sum = st.columns(len(selected_cities))
    
    for idx, city_name in enumerate(selected_cities):
        with cols_sum[idx]:
            # שליפת הכמות עבור העיר הספציפית (אם אין אזעקות, נציג 0)
            total_alerts = summary_data.get(city_name, 0)
            st.metric(label=f"סה\"כ {city_name}", value=f"{total_alerts} אזעקות")


    # --- TAB 4: עובדות מעניינות ---
    with tab4:
        st.subheader("💡 עובדות מעניינות")
        
        # סינון זיהויי שווא
        df_stats = df_filtered[df_filtered['origin'] != 'FA'].copy()
        
        if not df_stats.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                # 1. המקום עם הכי הרבה + כמות
                city_counts = df_stats['cities'].value_counts()
                top_city = city_counts.idxmax()
                top_city_val = city_counts.max()
                st.metric("העיר המטווחת ביותר", top_city, f"{top_city_val} אזעקות")
                
                # 2. היום העמוס ביותר
                top_day = df_stats['time'].dt.date.value_counts().idxmax()
                top_day_val = df_stats['time'].dt.date.value_counts().max()
                st.metric("היום העמוס ביותר", top_day.strftime('%d/%m/%Y'), f"{top_day_val} אזעקות")
    
            with col2:
                # 3. המקום עם הכי פחות + כמות
                bottom_city = city_counts.idxmin()
                bottom_city_val = city_counts.min()
                st.metric("העיר עם הכי פחות (מעל 0)", bottom_city, f"{bottom_city_val} אזעקות")
                
                # 4. יום רב זירתי
                enemies_per_day = df_stats.groupby(df_stats['time'].dt.date)['origin'].nunique()
                top_enemy_day = enemies_per_day.idxmax()
                enemies_list = df_stats[df_stats['time'].dt.date == top_enemy_day]['origin'].unique().tolist()
                st.metric("יום רב-זירתי מקסימלי", top_enemy_day.strftime('%d/%m/%Y'), f"{enemies_per_day.max()} גזרות")
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



















