# habit_tracker_full.py
"""
Smart Habit Tracker Dashboard
Features:
- Track: sleep, healthy food portions, junk food items, exercise minutes, water glasses, reading minutes
- Add custom habits (numeric score)
- Save entries per date (session_state; optional CSV import/export)
- Weekly analysis (best day by composite score) and suggestions
- Alerts when metrics fall below thresholds
- Simple browser reminders (fires while page is open)
- Visualizations (bar chart + radar-like summary)
"""

import streamlit as st
import pandas as pd
import numpy as np
import datetime
import io
import altair as alt

st.set_page_config(page_title="💎 Smart Habit Tracker", layout="wide")
st.title("💎 Smart Habit Tracker")

# -----------------------
# Helper functions
# -----------------------
def make_empty_df():
    cols = ["date", "sleep", "healthy_food", "junk_food", "exercise", "water", "reading"]
    return pd.DataFrame(columns=cols)

def composite_score(row):
    # Build a composite normalized score (higher is better)
    # Normalize each metric to a 0-1 range using reasonable caps
    s = min(row.get("sleep", 0) / 9.0, 1.0)           # 0-9 hours considered
    hf = min(row.get("healthy_food", 0) / 5.0, 1.0)   # 5 portions ideal
    jf = 1 - min(row.get("junk_food", 0) / 5.0, 1.0)   # fewer junk better
    ex = min(row.get("exercise", 0) / 60.0, 1.0)      # 60 min ideal
    w = min(row.get("water", 0) / 8.0, 1.0)           # 8 glasses ideal
    r = min(row.get("reading", 0) / 60.0, 1.0)        # 60 min ideal
    # Weighting
    return 0.18*s + 0.18*hf + 0.12*jf + 0.2*ex + 0.16*w + 0.16*r

def analyze_week(df_week):
    # Returns summary: averages, best day (by composite)
    if df_week.empty:
        return None
    df = df_week.copy()
    df["score"] = df.apply(composite_score, axis=1)
    best_idx = df["score"].idxmax()
    best_day = df.loc[best_idx, "date"]
    averages = df[["sleep", "healthy_food", "junk_food", "exercise", "water", "reading"]].mean().to_dict()
    return {"best_day": best_day, "averages": averages, "scores": df[["date","score"]].sort_values("date")}

def suggestions_from_averages(avg):
    # Returns list of suggestion strings based on averages
    tips = []
    if avg["sleep"] < 6:
        tips.append("Try to increase sleep (aim for 7-9 hours). Consider a consistent bedtime.")
    if avg["water"] < 6:
        tips.append("Drink more water — target ~8 glasses daily. Set small reminders.")
    if avg["exercise"] < 20:
        tips.append("Add more movement — even 20–30 min of brisk walk helps.")
    if avg["healthy_food"] < 3:
        tips.append("Increase healthy food portions (fruits/veggies).")
    if avg["junk_food"] > 1:
        tips.append("Reduce junk food frequency; swap one snack for fruit.")
    if avg["reading"] < 15:
        tips.append("Try a short daily reading habit — 10–20 minutes.")
    if not tips:
        tips.append("Great week! Keep up the balanced habits.")
    return tips

# -----------------------
# Session state init
# -----------------------
if "data" not in st.session_state:
    st.session_state.data = make_empty_df()  # persistent only while session is open

if "custom_habits" not in st.session_state:
    st.session_state.custom_habits = {}  # name -> ideal_cap (for normalization)

# -----------------------
# Layout: Sidebar - Entry
# -----------------------
st.sidebar.header("🧭 Mission Control — Entry")
today = datetime.date.today()
entry_date = st.sidebar.date_input("📅 Which day to make an entry for?", today)

sleep = st.sidebar.slider("😴 Sleep (hours)", 0.0, 12.0, 7.0, step=0.5)
healthy_food = st.sidebar.slider("🥗 Healthy food portions", 0, 10, 3)
junk_food = st.sidebar.number_input("🍟 Junk food items (count)", min_value=0, max_value=20, value=0, step=1)
exercise = st.sidebar.number_input("🏃 Exercise (minutes)", min_value=0, max_value=300, value=30, step=5)
water = st.sidebar.slider("💧 Water (glasses)", 0, 20, 6)
reading = st.sidebar.number_input("📚 Reading (minutes)", min_value=0, max_value=600, value=20, step=5)

# Custom habits input (repeatable)
st.sidebar.markdown("---")
st.sidebar.subheader("➕ Custom habit")
custom_name = st.sidebar.text_input("Name (e.g., Meditation)")
custom_value = st.sidebar.number_input("Value (numeric)", min_value=0.0, value=0.0, step=1.0, key="custom_value_input")
custom_cap = st.sidebar.number_input("Ideal cap for normalization (e.g., 30 for minutes)", min_value=1.0, value=30.0, step=1.0)
if st.sidebar.button("Add / Update Custom Habit"):
    if custom_name.strip():
        st.session_state.custom_habits[custom_name.strip()] = float(custom_cap)
        # optionally we'll store custom values per entry; we prompt user to add them below via a dynamic UI
        st.sidebar.success(f"Saved custom habit '{custom_name.strip()}' with cap {custom_cap}.")
    else:
        st.sidebar.error("Please enter a name for the custom habit.")

# Show any custom habit fields in the sidebar for the current entry
custom_inputs = {}
if st.session_state.custom_habits:
    st.sidebar.markdown("**Custom habit entries**")
    for name, cap in st.session_state.custom_habits.items():
        # generate a unique key per habit + date to avoid collisions
        v = st.sidebar.number_input(f"{name} (value)", min_value=0.0, value=0.0, step=1.0, key=f"ch_{name}_{entry_date}")
        custom_inputs[name] = float(v)

st.sidebar.markdown("---")
if st.sidebar.button("💾 Save Entry"):
    # Build new entry dict (with custom habits stored in a JSON-like column)
    new = {
        "date": pd.to_datetime(entry_date).date(),
        "sleep": float(sleep),
        "healthy_food": int(healthy_food),
        "junk_food": int(junk_food),
        "exercise": float(exercise),
        "water": int(water),
        "reading": float(reading),
    }
    # Add custom columns to dataframe dynamically
    for cname, val in custom_inputs.items():
        if cname not in st.session_state.data.columns:
            st.session_state.data[cname] = np.nan  # create new column
        new[cname] = val
    st.session_state.data = pd.concat([st.session_state.data, pd.DataFrame([new])], ignore_index=True)
    # Ensure 'date' dtype consistent
    st.session_state.data["date"] = pd.to_datetime(st.session_state.data["date"]).dt.date
    st.success("✅ Entry saved!")

# -----------------------
# Top: quick import/export controls
# -----------------------
st.sidebar.markdown("---")
st.sidebar.subheader("💼 Import / Export")
uploaded = st.sidebar.file_uploader("Upload CSV to import entries", type=["csv"])
if uploaded is not None:
    try:
        dfu = pd.read_csv(uploaded, parse_dates=["date"])
        # basic validation: must have date column
        if "date" not in dfu.columns:
            st.sidebar.error("CSV missing 'date' column.")
        else:
            # append imported (dates normalized)
            dfu["date"] = pd.to_datetime(dfu["date"]).dt.date
            st.session_state.data = pd.concat([st.session_state.data, dfu], ignore_index=True)
            st.sidebar.success("Imported entries added to session data.")
    except Exception as e:
        st.sidebar.error(f"Failed to import CSV: {e}")

# Download CSV
def get_csv_bytes(df):
    out = io.BytesIO()
    df.to_csv(out, index=False)
    return out.getvalue()

if not st.session_state.data.empty:
    csv_bytes = get_csv_bytes(st.session_state.data)
    st.sidebar.download_button("⬇️ Download CSV", data=csv_bytes, file_name="habit_data.csv", mime="text/csv")

if st.sidebar.button("🗑️ Clear all session data"):
    st.session_state.data = make_empty_df()
    st.success("Session data cleared.")

# -----------------------
# Main area: Display and analysis
# -----------------------
st.subheader("📊 Display your data")
if st.session_state.data.empty:
    st.info("No data yet — add an entry from the left sidebar.")
else:
    df = st.session_state.data.copy()
    df = df.sort_values("date")
    # show table (first columns visible)
    st.dataframe(df.style.format({c: "{:.1f}" for c in df.select_dtypes(include=[np.number]).columns}))

    # Show time range controls
    st.markdown("---")
    st.subheader("📈 Plot your habits over time")
    col1, col2 = st.columns([2,1])

    with col1:
        # Melt numeric columns into long form for plotting (skip custom non-numeric)
        numeric_cols = [c for c in df.columns if c != "date" and np.issubdtype(df[c].dropna().dtype, np.number) or c in ["sleep","exercise","water","reading","healthy_food","junk_food"]]
        # ensure numeric_cols includes typical ones
        plot_df = df[["date"] + numeric_cols].melt(id_vars=["date"], var_name="habit", value_name="value")
        chart = alt.Chart(plot_df).mark_bar().encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y("value:Q", title="Value"),
            color=alt.Color("habit:N", legend=alt.Legend(title="Habit")),
            tooltip=["date", "habit", "value"]
        ).properties(height=400, width=800).interactive()
        st.altair_chart(chart, use_container_width=True)

    with col2:
        # Weekly summary (last 7 days)
        st.subheader("Weekly analysis (last 7 days)")
        last_7 = df[df["date"] >= (datetime.date.today() - datetime.timedelta(days=6))]
        analysis = analyze_week(last_7)
        if analysis is None:
            st.write("Not enough data in the last 7 days.")
        else:
            best_day = analysis["best_day"]
            st.metric("Best day (by composite score)", str(best_day))
            avgs = analysis["averages"]
            st.write("Averages (last 7 days):")
            avg_df = pd.DataFrame.from_dict(avgs, orient="index", columns=["average"]).round(2)
            st.table(avg_df)

            # Suggestions
            st.write("Suggestions:")
            for tip in suggestions_from_averages(avgs):
                st.write("•", tip)

            # Low-performance alerts
            alerts = []
            if avgs["water"] < 5:
                alerts.append("Low average water intake — consider setting water reminders.")
            if avgs["sleep"] < 6:
                alerts.append("Low average sleep — consistent schedule may help.")
            if avgs["exercise"] < 15:
                alerts.append("Low average exercise minutes.")
            if alerts:
                for a in alerts:
                    st.warning(a)

# -----------------------
# Composite weekly scoring visual
# -----------------------
st.markdown("---")
st.subheader("📌 Weekly composite scores")
if not st.session_state.data.empty:
    last_14 = st.session_state.data.copy()
    last_14["date"] = pd.to_datetime(last_14["date"]).dt.date
    last_30 = last_14[last_14["date"] >= (datetime.date.today() - datetime.timedelta(days=29))]
    if last_30.empty:
        st.write("No recent data.")
    else:
        last_30["score"] = last_30.apply(composite_score, axis=1)
        score_chart = alt.Chart(last_30).mark_line(point=True).encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y("score:Q", title="Composite score (0-1)"),
            tooltip=["date", alt.Tooltip("score:Q", format=".2f")]
        ).properties(height=300, width=900)
        st.altair_chart(score_chart, use_container_width=True)

# -----------------------
# Simple browser reminders (JS component)
# -----------------------
st.markdown("---")
st.subheader("⏰ Reminders (browser notifications while page is open)")
remind_water = st.checkbox("Remind me to drink water every 60 seconds while page is open")
remind_custom_text = st.text_input("Reminder text (optional)", "Time to hydrate! 💧")

# A bit of JS to ask notification permission and (if checked) show repeated reminders while open.
# This will only work while the user keeps the Streamlit tab open.
if remind_water and st.button("▶️ Enable reminders"):
    # Insert a small script; note: streamlit.components.v1.html allowed
    notify_js = f"""
    <script>
    // Request permission then start interval notifications
    function notifyMe() {{
      if (!("Notification" in window)) {{
        alert("This browser does not support desktop notification");
      }} else if (Notification.permission === "granted") {{
        // show immediately and then every 60 sec
        var n = new Notification("{remind_custom_text}");
        window.reminder_interval = window.setInterval(function() {{
            var n2 = new Notification("{remind_custom_text}");
        }}, 60000);
      }} else if (Notification.permission !== "denied") {{
        Notification.requestPermission().then(function (permission) {{
          if (permission === "granted") {{
            var n = new Notification("{remind_custom_text}");
            window.reminder_interval = window.setInterval(function() {{
                var n2 = new Notification("{remind_custom_text}");
            }}, 60000);
          }} else {{
            alert("Notification permission denied.");
          }}
        }});
      }} else {{
        alert("Notification permission denied previously. Please enable in browser settings.");
      }}
    }}
    notifyMe();
    </script>
    """
    st.components.v1.html(notify_js)

if st.button("⏹️ Stop reminders (clears interval)"):
    clear_js = """
    <script>
    if (window.reminder_interval) {
        clearInterval(window.reminder_interval);
        window.reminder_interval = null;
        alert("Reminders stopped.");
    } else {
        alert("No active reminders found.");
    }
    </script>
    """
    st.components.v1.html(clear_js)

# -----------------------
# Extra: Quick insights and tips (auto-generated)
# -----------------------
st.markdown("---")
st.subheader("🔎 Quick Insights & Tips")
if st.session_state.data.empty:
    st.write("Add entries to get personalized insights.")
else:
    df_all = st.session_state.data.copy()
    df_all["date"] = pd.to_datetime(df_all["date"]).dt.date
    recent = df_all[df_all["date"] >= (datetime.date.today() - datetime.timedelta(days=6))]
    if recent.empty:
        st.write("Not enough recent data for insights (last 7 days).")
    else:
        rec_avg = recent[["sleep","healthy_food","junk_food","exercise","water","reading"]].mean().to_dict()
        # Show two quick rules
        if rec_avg["junk_food"] > 2:
            st.info("You've eaten junk food more than 2 times/day on average — try healthier swaps on 1-2 days.")
        if rec_avg["reading"] >= 30:
            st.success("Nice reading habit — you're averaging >=30 minutes per day!")
        # Custom habit highlight
        for cname in st.session_state.custom_habits.keys():
            if cname in recent.columns:
                val = recent[cname].mean()
                st.write(f"Custom habit '{cname}' average (last 7d): {val:.1f} (cap {st.session_state.custom_habits[cname]})")

# -----------------------
# Footer + credits
# -----------------------
st.markdown("---")
st.caption("Built with Streamlit • This session stores data only while the app is open (use Export to save).")
