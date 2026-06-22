import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from fpdf import FPDF
import os
from PIL import Image

st.set_page_config(page_title="SAP Analysis Dashboard", layout="wide", initial_sidebar_state="collapsed")

#UI/UX DESIGN
st.markdown("""
<style>
    /* Import modern typography */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif;
    }
    
    /* Crisp Bento Box Cards without custom background color */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 8px !important;
        border: 1px solid #E2E8F0 !important; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03) !important;
        padding: 1.5rem;
        transition: box-shadow 0.2s ease;
    }
    
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05) !important;
        border-color: #CBD5E1 !important; 
    }

    /* Custom Button Base: #FF4D4D */
    button[kind="primary"] {
        background-color: #FF4D4D !important; 
        border: none !important;
        border-radius: 6px !important;
        padding: 0.5rem 1.5rem !important;
        transition: background-color 0.2s ease;
    }
    
    button[kind="primary"]:hover {
        background-color: #E63E3E !important; 
    }

    /* Force all text INSIDE the primary buttons to be pure white */
    button[kind="primary"] * {
        color: #FFFFFF !important; 
        font-weight: 500 !important;
    }
    
    /* Headers - Clean Dark Gray */
    h1, h2, h3 {
        color: #0F172A !important; 
        font-weight: 600 !important;
        margin-top: 0px !important;
        padding-top: 0px !important;
    }
    
    /* Standard Text */
    p, .stMarkdown {
        color: #334155;
    }
</style>
""", unsafe_allow_html=True)


#DATA PROCESSING
def process_and_save_to_db(pcgmdt_file, cn42n_file, db_path="project_database.db"):
    df_pcgmdt = pd.read_excel(pcgmdt_file)
    df_cn42n = pd.read_excel(cn42n_file)

    df_pcgmdt.columns = df_pcgmdt.columns.str.strip()
    df_cn42n.columns = df_cn42n.columns.str.strip()

    df_pcgmdt = df_pcgmdt[df_pcgmdt['Phys.Progress %(SAP)'] > 50]

    merged_df = pd.merge(
        df_pcgmdt, 
        df_cn42n, 
        left_on='Project', 
        right_on='Project definition', 
        how='inner',
        suffixes=('', '_cn42n_drop')
    )

    if 'Project definition' in merged_df.columns:
        merged_df.drop(columns=['Project definition'], inplace=True)
    cols_to_drop = [col for col in merged_df.columns if col.endswith('_cn42n_drop')]
    merged_df.drop(columns=cols_to_drop, inplace=True)
    
    target_schema_mapping = {
        'Project': 'Project_ID',
        'Project Description': 'Project_Name',
        'Profit Center': 'Profit_Center',
        'Fixed Fee basis': 'Fixed_Fee_Basis',
        'SBU': 'SBU',
        'Project Type': 'Project_Type',
        'Prj Cordinator Num': 'Coordinator_No',
        'Project Cordinator': 'Project_Coordinator',
        'Cgm No': 'CGM_No',
        'CGM': 'CGM_Name',
        'Phys.Progress %(SAP)': 'Physical_Progress_SAP',
        'No.of person resp.': 'No_Of_Person_Resp', 
        'Start date': 'Start_Date',      
        'Finish date': 'Finish_Date',    
        'Status': 'Status',
        'Name 1': 'Client_Name',
        'Client Address': 'Client_Address'
    }
    
    merged_df.rename(columns={k: v for k, v in target_schema_mapping.items() if k in merged_df.columns}, inplace=True)
    
    final_columns = [col for col in target_schema_mapping.values() if col in merged_df.columns]
    merged_df = merged_df[final_columns]

    for col in ['Start_Date', 'Finish_Date']:
        if col in merged_df.columns:
            merged_df[col] = pd.to_datetime(merged_df[col], errors='coerce').dt.strftime('%d-%m-%Y')
            
    merged_df = merged_df.astype(object)
    merged_df = merged_df.fillna("null")

    conn = sqlite3.connect(db_path)
    merged_df.to_sql('Cleaned_Projects', conn, if_exists='replace', index=False)
    conn.close()

    return merged_df


# --- PDF GENERATION
def generate_pdf(dataframe):
    pdf = FPDF(orientation="L", unit="mm", format=(420, 594))
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    
    page_width = pdf.w - 2 * pdf.l_margin
    line_height = 6 
    
    def sanitize_txt(text):
        return str(text).encode('latin-1', 'replace').decode('latin-1')
    
    exact_widths = {
        'Sl. No.': 8.4 
    }
    
    rel_widths = {
        'Status': 0.6,           
        'Project_Name': 3.0,     
        'Client_Address': 4.0,   
        'Client_Name': 1.5       
    }
    
    fixed_total_mm = sum([exact_widths.get(col, 0) for col in dataframe.columns])
    available_width = page_width - fixed_total_mm
    
    total_weight = sum([rel_widths.get(col, 1.0) for col in dataframe.columns if col not in exact_widths])
    
    col_widths = []
    for col in dataframe.columns:
        if col in exact_widths:
            col_widths.append(exact_widths[col])
        else:
            weight = rel_widths.get(col, 1.0)
            col_widths.append((weight / total_weight) * available_width)
            
    pdf.set_font("helvetica", style="B", size=8)
    
    max_lines = 1
    for i, col in enumerate(dataframe.columns):
        txt = sanitize_txt(col)
        cw = col_widths[i]
        usable_cw = max(cw - 1.5, 1.0) 
        lines = int(pdf.get_string_width(txt) / usable_cw) + 1
        if lines > max_lines: max_lines = lines
    
    row_height = ((max_lines + 1) * line_height) + 2 
    start_y = pdf.get_y()
    
    for i, col in enumerate(dataframe.columns):
        txt = sanitize_txt(col)
        cw = col_widths[i]
        x, y = pdf.get_x(), pdf.get_y()
        
        pdf.rect(x, y, cw, row_height)
        pdf.set_xy(x + 0.5, y + 1)
        pdf.multi_cell(cw - 1, line_height, txt=txt, border=0, align="C")
        pdf.set_xy(x + cw, start_y)
        
    pdf.set_y(start_y + row_height)
    
    pdf.set_font("helvetica", size=8)
    for index, row in dataframe.iterrows():
        max_lines = 1
        
        for i, item in enumerate(row):
            txt = sanitize_txt(item)
            cw = col_widths[i]
            usable_cw = max(cw - 1.5, 1.0)
            lines = int(pdf.get_string_width(txt) / usable_cw) + 1 + str(txt).count('\n')
            if lines > max_lines: max_lines = lines
                
        row_height = ((max_lines + 1) * line_height) + 2 
        
        if pdf.get_y() + row_height > (pdf.h - 25):
            pdf.add_page()
            
        start_y = pdf.get_y()
        
        for i, item in enumerate(row):
            txt = sanitize_txt(item)
            cw = col_widths[i]
            x, y = pdf.get_x(), pdf.get_y()
            
            pdf.rect(x, y, cw, row_height)
            pdf.set_xy(x + 0.5, y + 1)
            pdf.multi_cell(cw - 1, line_height, txt=txt, border=0, align="L")
            pdf.set_xy(x + cw, start_y)
            
        pdf.set_y(start_y + row_height)
        
    raw_pdf_output = pdf.output(dest="S")
    
    if isinstance(raw_pdf_output, str):
        return raw_pdf_output.encode("latin-1")
    elif isinstance(raw_pdf_output, bytearray):
        return bytes(raw_pdf_output)
    else:
        return raw_pdf_output
    
# Header Box
with st.container(border=True):
    col_logo, col_text = st.columns([1, 10])
    
    with col_logo:
        # Dynamically loading of the logo image
        if os.path.exists("app_logo.ico"):
            logo_img = Image.open("app_logo.ico")
            st.image(logo_img, use_container_width=True)
            
    with col_text:
        st.title("SAP Data Automation Dashboard")
        st.markdown("Seamlessly merge, analyze, and export your project data. Upload your standard reports below to generate unified insights instantly.")

# Upload Box
with st.container(border=True):
    st.subheader("Document Ingestion")
    col1, col2 = st.columns(2)
    with col1:
        pcgmdt_upload = st.file_uploader("Upload Primary Report (PCGMDT)", type=['xlsx', 'xls'], help="Must contain Project Id and SAP")
    with col2:
        cn42n_upload = st.file_uploader("Upload Secondary Report (CN42N)", type=['xlsx', 'xls'], help="Must contain Project Id")

# Processing
if pcgmdt_upload and cn42n_upload:
    
    # Shows Session State
    if "data_processed" not in st.session_state:
        st.session_state.data_processed = False

    # Action
    with st.container(border=True):
        st.write("Ready to build the database.")
        process_clicked = st.button("Process & Analyze Data", type="primary")
        
    if process_clicked or st.session_state.data_processed:
        if not st.session_state.data_processed:
            with st.spinner("Cleaning, merging, and rendering your dashboard..."):
                try:
                    st.session_state.master_df = process_and_save_to_db(pcgmdt_upload, cn42n_upload)
                    st.session_state.data_processed = True
                    st.success("Data successfully merged and committed to SQLite.")
                except Exception as e:
                    st.error(f"An error occurred: {e}")
                    st.stop()
        
        df = st.session_state.master_df.copy()
        df['Physical_Progress_SAP'] = pd.to_numeric(df['Physical_Progress_SAP'], errors='coerce')

        # Filter Box
        with st.container(border=True):
            st.subheader("Data Filters")
            f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns(5)
            
            with f_col1:
                profit_centers = sorted([str(x) for x in df['Profit_Center'].unique() if x != "null"])
                selected_pc = st.multiselect("Profit Center", options=profit_centers, default=[])
                
            with f_col2:
                sbu_types = sorted([str(x) for x in df['SBU'].unique() if x != "null"])
                selected_sbu = st.multiselect("SBU", options=sbu_types, default=[])
                
            with f_col3:
                project_types = sorted([str(x) for x in df['Project_Type'].unique() if x != "null"])
                selected_pt = st.multiselect("Project Type", options=project_types, default=[])
                
            with f_col4:
                sort_order = st.selectbox("Sort Progress", options=["Descending", "Ascending"])
                
            with f_col5:
                top_n = st.selectbox("Record Limit", options=["All", "Top 10", "Top 20", "Top 50", "Top 100"])

        # Filters
        if selected_pc:
            df = df[df['Profit_Center'].isin(selected_pc)]
        if selected_sbu:
            df = df[df['SBU'].isin(selected_sbu)]
        if selected_pt:
            df = df[df['Project_Type'].isin(selected_pt)]
            
        is_ascending = True if sort_order == "Ascending" else False
        df = df.sort_values(by="Physical_Progress_SAP", ascending=is_ascending)
        
        if top_n != "All":
            limit = int(top_n.replace("Top ", ""))
            df = df.head(limit)

        df.reset_index(drop=True, inplace=True)
        df.insert(0, 'Sl. No.', range(1, len(df) + 1))

        # Visualization
        with st.container(border=True):
            st.subheader("SAP Progress Analytics")
            fig = px.bar(
                df, 
                x='Project_Name', 
                y='Physical_Progress_SAP', 
                color='Physical_Progress_SAP',
                labels={'Physical_Progress_SAP': 'Progress (%)', 'Project_Name': 'Project Title'},
                color_continuous_scale="Viridis" 
            )
            fig.update_layout(
                xaxis_tickangle=-45, 
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, sans-serif")
            )
            st.plotly_chart(fig, use_container_width=True)

        # Output & Export
        with st.container(border=True):
            st.subheader(f"Master Records ({len(df)} entries)")
            st.dataframe(df, use_container_width=True, hide_index=True) 
            
            st.divider()   
            pdf_data = generate_pdf(df)
            col_empty, col_btn = st.columns([5, 1])
            with col_btn:
                st.download_button(
                    label="Export Report (PDF)",
                    data=pdf_data,
                    file_name="SAP_Automated_Report.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True 
                )

else:
    with st.container(border=True):
        st.info("Awaiting Data: Please upload both your primary and secondary records above to unlock the dashboard.")

# Signature
st.markdown("""
    <div style='text-align: center; margin-top: 30px; padding: 10px; color: #64748B; font-size: 13px; font-weight: 400;'>
        Automated Data Tool | Created by Mohammad Zishan Alam
    </div>
""", unsafe_allow_html=True)