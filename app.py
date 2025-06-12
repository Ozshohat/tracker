
import streamlit as st
import pandas as pd
import os
import tempfile

st.set_page_config(page_title="מערכת סיווג הוצאות", layout="wide")
st.title("📊 מערכת אונליין לסיווג הוצאות")

CATEGORY_OPTIONS = ["עוז ישראכרט", "עוז כאל", "עוז בנק", "בר ויזה", "בר בנק"]

st.sidebar.header("1️⃣ העלאת מסד נתונים ראשי")
db_file = st.sidebar.file_uploader("בחר קובץ Excel של מסד הנתונים הראשי", type=["xlsx"])

st.sidebar.header("2️⃣ העלאת קבצים חדשים לפי קטגוריה")
uploaded_files = {}
for category in CATEGORY_OPTIONS:
    uploaded_files[category] = st.sidebar.file_uploader(f"העלה קבצים עבור {category}",
                                                         type=["xlsx"],
                                                         accept_multiple_files=True,
                                                         key=category)

def clean_and_prepare_df(df_raw):
    # חיפוש שורת header אמיתית – מחפש את השורה הראשונה שיש בה "תאריך"
    header_row = None
    for i, row in df_raw.iterrows():
        if row.astype(str).str.contains("תאריך").any():
            header_row = i
            break
    if header_row is None:
        return pd.DataFrame()  # לא נמצא header תקני

    df_clean = pd.read_excel(file, skiprows=header_row + 1)
    df_clean = df_clean.dropna(how="all")

    if df_clean.empty or df_clean.shape[1] < 3:
        return pd.DataFrame()

    df_clean = df_clean.rename(columns={
        df_clean.columns[0]: "תאריך",
        df_clean.columns[1]: "בית עסק",
        df_clean.columns[-1]: "סכום"
    })

    # סינון שורות שמכילות טקסטים כלליים או סכום שאינו מספר
    df_clean = df_clean[df_clean["בית עסק"].astype(str).str.len() > 1]
    df_clean = df_clean[pd.to_numeric(df_clean["סכום"], errors="coerce").notna()]
    df_clean["סכום"] = df_clean["סכום"].astype(float)
    df_clean = df_clean[pd.to_datetime(df_clean["תאריך"], errors="coerce").notna()]
    df_clean["תאריך"] = pd.to_datetime(df_clean["תאריך"])

    return df_clean[["תאריך", "בית עסק", "סכום"]]

if db_file:
    db_df = pd.read_excel(db_file)
    if "פירוט נוסף" not in db_df.columns:
        st.error("קובץ מסד הנתונים אינו כולל עמודה בשם 'פירוט נוסף'.")
    else:
        st.success("מסד הנתונים נטען בהצלחה ✅")
        st.dataframe(db_df.head())

        st.markdown("---")
        st.header("📂 עיבוד קבצים חדשים והצעת סיווג")

        all_new_data = []

        for category, files in uploaded_files.items():
            for file in files:
                st.subheader(f"📎 {file.name} ({category})")
                raw_df = pd.read_excel(file, header=None)
                clean_df = clean_and_prepare_df(raw_df)

                if clean_df.empty:
                    st.warning("לא נמצאו נתונים תקפים בקובץ.")
                    continue

                clean_df["שם"] = category.split()[0]  # עוז / בר
                all_new_data.append(clean_df)

        if all_new_data:
            new_data_combined = pd.concat(all_new_data, ignore_index=True)

            st.markdown("---")
            st.header("🧠 סיווג אוטומטי להצעות")

            # מפה: שם בית עסק -> הקטגוריה שלו בעבר
            business_to_category = db_df.dropna(subset=["פירוט נוסף"]).groupby("שם בית עסק")["פירוט נוסף"].agg(lambda x: x.mode().iloc[0] if not x.mode().empty else None).to_dict()

            def suggest_category(business_name):
                name = str(business_name).strip()
                if name in business_to_category:
                    return business_to_category[name]

                name_lower = name.lower()
                if any(w in name_lower for w in ["קפה", "מסעדה", "פיצה", "בייקרי"]):
                    return "אוכל"
                elif any(w in name_lower for w in ["מלון", "הונגריה", "אירופה", "netherlands", "terminal", "נתב"]):
                    return "חול"
                elif any(w in name_lower for w in ["רנואר", "ביגוד", "קסטרו", "fashion", "clothing"]):
                    return "בגדים"
                elif any(w in name_lower for w in ["פז", "דלק", "ten", "סונול"]):
                    return "רכב"
                elif any(w in name_lower for w in ["bit", "ביט"]):
                    return "ביט"
                elif any(w in name_lower for w in ["yes", "חשבון", "ארנונה", "מים", "גז"]):
                    return "חשבונות"
                else:
                    return "שונות"

            new_data_combined["קטגוריה מוצעת"] = new_data_combined["בית עסק"].apply(suggest_category)
            new_data_combined["קטגוריה"] = ""

            edited = st.data_editor(new_data_combined, num_rows="dynamic", use_container_width=True,
                                    column_order=["תאריך", "בית עסק", "סכום", "קטגוריה מוצעת", "קטגוריה", "שם"])

            if st.button("📥 מיזוג למסד הנתונים"):
                edited["פירוט נוסף"] = edited["קטגוריה"].replace("", pd.NA).fillna(edited["קטגוריה מוצעת"])
                edited = edited.drop(columns=["קטגוריה מוצעת", "קטגוריה"])
                final_df = pd.concat([db_df, edited], ignore_index=True)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                    final_df.to_excel(tmp.name, index=False)
                    st.success("✅ הקבצים מוזגו בהצלחה")
                    st.download_button("📤 הורד קובץ מאוחד", tmp.name, file_name="מסד_נתונים_מעודכן.xlsx")
else:
    st.info("נא להעלות קודם את מסד הנתונים הראשי")
