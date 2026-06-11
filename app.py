import streamlit as st
import pyodbc
import pandas as pd
import plotly.express as px
from pydantic import BaseModel, Field
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

# --- Pydantic & Prompt Setup ---
class Query(BaseModel):
    query: str = Field(description="The generated SQL query string")

class AnalysisResponse(BaseModel):
    summary: str = Field(description="Detailed, highly structured Markdown report with headers and bullet points")
    chart_type: str = Field(description="Type of chart: bar, line, pie, histogram, box, or none")
    x_axis: str = Field(description="Column name for X axis")
    y_axes: List[str] = Field(description="List of column names for Y axis")
    title: str = Field(description="A descriptive title for the chart")

parser = PydanticOutputParser(pydantic_object=Query)
analysis_parser = PydanticOutputParser(pydantic_object=AnalysisResponse)

# --- Prompts ---
sql_template = """
You are an AI SQL assistant 🤖. 
Generate a valid SQL query based on the schema and request.
- Return ONLY the SQL string.
- Use square brackets: [Schema].[Table].
- Context: {full_schema_context}
- Current Table: {current_table}
- Request: {query_description}

Return ONLY a JSON object:
{format_instructions}
"""

analysis_template = """
You are a Senior Data Scientist 📊.
Analyze this dataset:
Columns: {columns}
Statistics: {data_stats}
User Request: {analysis_request}

INSTRUCTIONS:
1. SUMMARY: Provide a HIGHLY STRUCTURED Markdown report using this exact format:
   ### 📈 Key Metrics
   - [Highlight specific numbers, e.g., "Total sales reached $X"]
   ### 🔍 Trend & Curve Analysis
   - [Explain the shape of the curves or bars. E.g., "The gap between A and B is 15%"]
   ### 💡 Comparative Insights
   - [Compare factors directly. E.g., "Product X accounts for 34% of volume"]
   ### 🎯 Conclusion & Impact
   - [Final takeaway]

2. VISUALIZATION: Choose the best chart.
   - 'pie': For percentage distributions or part-to-whole.
   - 'histogram': For frequency distributions of a single metric.
   - 'box': For looking at outliers and distribution ranges.
   - 'line': For trends over time or comparing multiple continuous curves.
   - 'bar': For comparing categories.

Return ONLY a JSON object:
{format_instructions}
"""

sql_prompt_template = PromptTemplate(
    template=sql_template,
    input_variables=["query_description", "current_table", "full_schema_context"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

analysis_prompt_template = PromptTemplate(
    template=analysis_template,
    input_variables=["columns", "data_stats", "analysis_request"],
    partial_variables={"format_instructions": analysis_parser.get_format_instructions()}
)

# --- Database & Execution Helpers ---
def get_connection(server, database, username=None, password=None, auth_type="Windows"):
    try:
        driver = '{ODBC Driver 17 for SQL Server}'
        if auth_type == "Windows":
            conn_str = f'DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;'
        else:
            conn_str = f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};'
        return pyodbc.connect(conn_str)
    except Exception as e:
        st.error(f"Connection Error: {e}")
        if server.lower() in ["localhost", "127.0.0.1"] or auth_type == "Windows":
            st.warning("💡 **Connection Tip:** If this app is running on Streamlit Cloud, it cannot access databases hosted on your local machine (`localhost`) or use `Windows` Authentication. You must either run the app locally on your machine or connect to a cloud-hosted database using `SQL Server` Authentication (username & password).")
        return None

def fetch_full_schema(server, db_name, user, pwd, auth):
    schema_info = {}
    conn = get_connection(server, db_name, user, pwd, auth)
    if conn:
        try:
            cursor = conn.cursor()
            query = "SELECT s.name, t.name, c.name FROM sys.tables t JOIN sys.columns c ON t.object_id = c.object_id JOIN sys.schemas s ON t.schema_id = s.schema_id ORDER BY s.name, t.name;"
            cursor.execute(query)
            for row in cursor.fetchall():
                full_name = f"[{row[0]}].[{row[1]}]"
                if full_name not in schema_info: schema_info[full_name] = []
                schema_info[full_name].append(row[2])
            conn.close()
        except Exception as e: st.error(f"Schema Error: {e}")
    return schema_info

def execute_sql(conn, sql_query):
    try:
        query_type = sql_query.strip().split()[0].upper()
        if query_type in ["SELECT", "WITH"]:
            return {"type": "data", "content": pd.read_sql(sql_query, conn)}
        else:
            cursor = conn.cursor()
            cursor.execute(sql_query); conn.commit()
            return {"type": "success", "content": f"Executed: {query_type}"}
    except Exception as e:
        return {"type": "error", "content": str(e)}

# --- UI Setup ---
st.set_page_config(page_title="AI SQL Analysis Dashboard", layout="wide")

st.markdown("""
    <style>
    div[data-testid="stDialog"] div[role="dialog"] {
        max-width: 90vw !important;
        width: 90vw !important;
    }
    .stContainer { border-radius: 12px; padding: 10px; margin-bottom: 15px; }
    .main .block-container { padding-bottom: 8rem; }
    </style>
    """, unsafe_allow_html=True)

if "history" not in st.session_state: st.session_state.history = []
if "connected" not in st.session_state: st.session_state.connected = False
if "schema_context" not in st.session_state: st.session_state.schema_context = {}
if "selected_db" not in st.session_state: st.session_state.selected_db = None

# --- ANALYSIS POPUP DIALOG ---
@st.dialog("🚀 Advanced Data Analysis Dashboard", width="large")
def show_analysis_popup(entry_idx):
    entry = st.session_state.history[entry_idx]
    df = entry['result']['content']
    
    st.markdown(f"### Deep Analysis: *{entry['question']}*")
    
    ana_prompt = st.text_area("Request specific comparisons (Pie, Curves, Box plots, etc.):", 
                              placeholder="e.g. Compare Sales vs Profit curves. Show me a pie chart of sales distribution.", 
                              height=100,
                              key=f"qana_dlg_{entry_idx}")
    
    if st.button("Generate Visual Insights", key=f"bana_dlg_{entry_idx}", type="primary", use_container_width=True):
        api_key = st.session_state.get('api_key_val', "")
        if not api_key: 
            st.error("Missing API Key in sidebar."); return
        
        with st.spinner("Analyzing Data Distribution..."):
            data_stats = df.describe(include='all').to_string()
            if len(data_stats) > 2000: data_stats = data_stats[:2000] + "..."
            
            model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key)
            prompt = analysis_prompt_template.format(
                columns=", ".join(df.columns),
                data_stats=data_stats,
                analysis_request=ana_prompt
            )
            
            try:
                res_content = model.invoke(prompt).content
                res = analysis_parser.parse(res_content)
                entry['analysis_res'] = res
            except Exception as e:
                st.error(f"Analysis failed: {e}")
    
    if entry.get('analysis_res'):
        res = entry['analysis_res']
        st.divider()
        st.markdown(res.summary) 
        
        if res.chart_type != "none":
            try:
                theme_tpl = "plotly_dark" if st.get_option("theme.base") == "dark" else "plotly_white"
                
                if res.chart_type == "bar": 
                    fig = px.bar(df, x=res.x_axis, y=res.y_axes, title=res.title, barmode='group')
                elif res.chart_type == "line": 
                    fig = px.line(df, x=res.x_axis, y=res.y_axes, title=res.title)
                elif res.chart_type == "pie": 
                    fig = px.pie(df, names=res.x_axis, values=res.y_axes[0], title=res.title)
                elif res.chart_type == "histogram":
                    fig = px.histogram(df, x=res.x_axis, y=res.y_axes[0], title=res.title, marginal="box")
                elif res.chart_type == "box":
                    fig = px.box(df, x=res.x_axis, y=res.y_axes, title=res.title)
                
                fig.update_layout(template=theme_tpl)
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e: 
                st.error(f"Visualization Error: {e}")

# --- SIDEBAR: CONFIG ---
with st.sidebar:
    st.title("⚙️ AI SQL Studio")
    st.markdown("### 🔑 API Configuration")
    api_key_input = st.text_input("Google API Key", type="password", placeholder="Enter Gemini Key...")
    st.session_state['api_key_val'] = api_key_input
    st.divider()
    st.markdown("### 🔌 Server Connection")
    server = st.text_input("Server Address", value="localhost")
    auth_mode = st.radio("Authentication", ["Windows", "SQL Server"])
    
    u, p = (None, None)
    if auth_mode == "SQL Server":
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
    
    if st.button("Connect to Server", use_container_width=True, type="primary"):
        conn = get_connection(server, "master", u, p, auth_mode)
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sys.databases WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb')")
            st.session_state.databases = [row[0] for row in cursor.fetchall()]
            st.session_state.server, st.session_state.auth_type, st.session_state.username, st.session_state.password = server, auth_mode, u, p
            st.session_state.connected = True
            st.success("Connected!")

    if st.session_state.connected:
        st.divider()
        db_options = st.session_state.databases
        current_db = st.selectbox("Select Database", db_options, 
                                  index=db_options.index(st.session_state.selected_db) if st.session_state.selected_db in db_options else 0)
        
        if st.session_state.selected_db != current_db:
            st.session_state.selected_db = current_db
            with st.spinner("Fetching Schema..."):
                st.session_state.schema_context = fetch_full_schema(st.session_state.server, current_db, st.session_state.username, st.session_state.password, st.session_state.auth_type)
        
        table_list = list(st.session_state.schema_context.keys())
        selected_table = st.selectbox("Working Table Context", table_list)
        
        if st.button("🗑️ Clear History", use_container_width=True):
            st.session_state.history = []
            st.rerun()

# --- MAIN WORKSPACE ---
if not st.session_state.connected:
    st.header("Welcome to AI SQL Assistant 🤖")
    st.info("Connect to your SQL Server in the sidebar to get started.")
else:
    st.title(f"📊 Dashboard: {st.session_state.selected_db}")
    st.caption(f"Connected to {st.session_state.server} | Scope: {selected_table}")

    for i, entry in enumerate(reversed(st.session_state.history)):
        idx = len(st.session_state.history) - 1 - i
        with st.container(border=True):
            col_header, col_btn1, col_btn2 = st.columns([8, 1, 1])
            col_header.markdown(f"#### ❓ {entry['question']}")
            if col_btn1.button("⚙️", key=f"opt_{idx}"):
                st.session_state[f"edit_{idx}"] = not st.session_state.get(f"edit_{idx}", False)
            if col_btn2.button("📈", key=f"an_{idx}"):
                show_analysis_popup(idx)

            if st.session_state.get(f"edit_{idx}", False):
                with st.expander("📝 Modify Natural Language Request", expanded=True):
                    edit_q = st.text_area("New description", value=entry['question'], height=100, key=f"input_{idx}")
                    if st.button("Update Data", key=f"upd_{idx}", type="primary"):
                        api_key = st.session_state.get('api_key_val', "")
                        if not api_key: st.error("API Key required."); st.stop()
                        model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key)
                        schema_sum = "\n".join([f"- {k}: {', '.join(v)}" for k,v in st.session_state.schema_context.items()])
                        sql = parser.parse(model.invoke(sql_prompt_template.format(query_description=edit_q, current_table=selected_table, full_schema_context=schema_sum)).content).query
                        conn = get_connection(st.session_state.server, st.session_state.selected_db, st.session_state.username, st.session_state.password, st.session_state.auth_type)
                        st.session_state.history[idx] = {"question": edit_q, "sql": sql, "result": execute_sql(conn, sql), "analysis_res": None}
                        conn.close()
                        st.rerun()

            if entry['result']['type'] == "data":
                st.code(entry['sql'], language="sql")
                st.dataframe(entry['result']['content'], use_container_width=True, height=350)
            elif entry['result']['type'] == "success":
                st.success(entry['result']['content'])
            else:
                st.error(entry['result']['content'])

    user_input = st.chat_input("💬 Ask a question about your database...")
    if user_input:
        api_key = st.session_state.get('api_key_val', "")
        if not api_key: st.sidebar.error("⚠️ Provide a Google API Key in the sidebar first!")
        else:
            with st.spinner("AI is thinking..."):
                schema_sum = "\n".join([f"- {k}: {', '.join(v)}" for k,v in st.session_state.schema_context.items()])
                model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key)
                sql_res = model.invoke(sql_prompt_template.format(query_description=user_input, current_table=selected_table, full_schema_context=schema_sum))
                sql = parser.parse(sql_res.content).query
                conn = get_connection(st.session_state.server, st.session_state.selected_db, st.session_state.username, st.session_state.password, st.session_state.auth_type)
                st.session_state.history.append({"question": user_input, "sql": sql, "result": execute_sql(conn, sql), "analysis_res": None})
                conn.close()
                st.rerun()