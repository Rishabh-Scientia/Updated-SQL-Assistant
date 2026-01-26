# Updated-SQL-Assistant
T# 🤖 AI SQL Assistant (Natural Language → SQL + Analysis Dashboard)

Instead of writing complex SQL queries, users can:
✅ Generate SQL queries (CRUD)  
✅ Execute them instantly  
✅ View results in a clean UI  
✅ Analyze and visualize table data (charts + graphs)

Built using **Streamlit + LangChain + Google Gemini + SQL Server**.

---

## 🚀 Features

- 🔗 **Connect to SQL Server**
  - Windows Authentication
  - SQL Server Authentication

- 📂 **Explore Database**
  - List databases
  - List tables
  - View columns of selected table

- 🧠 **Natural Language → SQL**
  - Generate SQL queries using Gemini
  - Supports CRUD operations:
    - `SELECT`
    - `INSERT`
    - `UPDATE`
    - `DELETE`

- ▶️ **Execute Queries**
  - Run queries directly from the app
  - Results displayed instantly

- 📊 **Data Analysis + Visualization (Prototype)**
  - Select a table and analyze data
  - Visualize using charts like:
    - Bar chart
    - Pie chart
    - Line chart (curves)

- 🔑 **User API Key Support**
  - Users can use their own **Gemini API key**
  - No need to hardcode keys

---

## 🛠️ Tech Stack

- **Python**
- **Streamlit**
- **PyODBC**
- **Pandas**
- **LangChain**
- **Google Gemini API**
- **SQL Server**

---

## 📌 Installation (Windows)

### 1️⃣ Clone the repo
```bash
git clone https://github.com/your-username/ai-sql-assistant.git
cd ai-sql-assistant

