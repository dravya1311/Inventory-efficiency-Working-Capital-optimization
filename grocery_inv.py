import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

# --- Configuration ---
st.set_page_config(layout="wide", page_title="Inventory Efficiency Dashboard")

TODAY = date.today()

# --- Data Loading ---
@st.cache_data
def load_data(file_path, current_date):
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        st.error("File not found. Please check path.")
        return pd.DataFrame()

    df.columns = df.columns.str.strip()

    # Clean price
    df['Unit_Price'] = df['Unit_Price'].astype(str).str.replace('$', '', regex=False)
    df['Unit_Price'] = pd.to_numeric(df['Unit_Price'], errors='coerce')

    # Margin
    if 'percentage' in df.columns:
        df['Product_Margin'] = df['percentage'].astype(str).str.replace('%', '', regex=False)
        df['Product_Margin'] = pd.to_numeric(df['Product_Margin'], errors='coerce') / 100
    else:
        df['Product_Margin'] = 0.0

    # Derived metrics
    df['Inventory_Value'] = df['Stock_Quantity'] * df['Unit_Price']
    df['Total_Revenue'] = df['Sales_Volume'] * df['Unit_Price']

    # Dates
    for col in ['Date_Received', 'Last_Order_Date', 'Expiration_Date']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    df['Days_to_Expire'] = (df['Expiration_Date'] - pd.Timestamp(current_date)).dt.days

    # Fix column name issue safely
    if 'Catagory' in df.columns:
        df['Catagory'] = df['Catagory'].fillna('Unknown')
    else:
        df['Catagory'] = 'Unknown'

    # Avg daily sales
    df['Avg_Daily_Sales'] = df['Sales_Volume'] / 30
    df['Avg_Daily_Sales'] = df['Avg_Daily_Sales'].replace(0, 1)

    return df


df = load_data('Grocery_Inventory.csv', TODAY)

# --- Filters ---
if not df.empty:

    st.sidebar.header("🔍 Filters")

    category_filter = st.sidebar.multiselect("Category", df['Catagory'].unique())
    supplier_filter = st.sidebar.multiselect("Supplier", df['Supplier_Name'].unique())

    if category_filter:
        df = df[df['Catagory'].isin(category_filter)]
    if supplier_filter:
        df = df[df['Supplier_Name'].isin(supplier_filter)]

    # --- KPI Calculation ---
    def calculate_kpis(df):
        total_inventory_value = df['Inventory_Value'].sum()

        total_sales_with_margin = (df['Total_Revenue'] * df['Product_Margin']).sum()
        gmroii = total_sales_with_margin / total_inventory_value if total_inventory_value > 0 else 0

        total_stock = df['Stock_Quantity'].sum()
        total_avg_daily_sales = df['Avg_Daily_Sales'].sum()
        coverage = total_stock / total_avg_daily_sales if total_avg_daily_sales > 0 else 0

        near_expiry = df[df['Days_to_Expire'] <= 7]['Inventory_Value'].sum()
        risk_percent = (near_expiry / total_inventory_value) * 100 if total_inventory_value > 0 else 0

        turnover = df['Inventory_Turnover_Rate'].mean() if 'Inventory_Turnover_Rate' in df.columns else 0

        return gmroii, coverage, near_expiry, turnover, risk_percent

    gmroii, coverage, near_expiry, turnover, risk_percent = calculate_kpis(df)

    # --- Dashboard ---
    st.title("📈 Inventory Efficiency & Working Capital Optimization Dashboard")

    st.markdown("""
    This dashboard identifies inventory inefficiencies, working capital blockage
    and operational risks to support decision-making.
    """)

    st.markdown("---")

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Estimated GMROII", f"{gmroii:.2f}x")
    col2.metric("Inventory Coverage", f"{coverage:.1f} days")
    col3.metric("Near Expiry Risk", f"₹{near_expiry:,.0f}")
    col4.metric("Inventory Turnover", f"{turnover:.1f}x")
    col5.metric("Inventory at Risk (%)", f"{risk_percent:.1f}%")

    # --- Dead Inventory ---
    st.markdown("---")
    st.subheader("🚨 Dead / Slow Moving Inventory")

    dead = df[
        (df['Sales_Volume'] < df['Sales_Volume'].quantile(0.25)) &
        (df['Stock_Quantity'] > df['Stock_Quantity'].quantile(0.75))
    ]

    if not dead.empty:
        st.dataframe(
            dead[['Product_Name', 'Catagory', 'Stock_Quantity', 'Sales_Volume', 'Inventory_Value']],
            use_container_width=True
        )
    else:
        st.info("No dead inventory found")

    # --- Footer ---
    st.markdown("---")
    st.caption("Developed by R Yadav")

else:
    st.warning("Dataset not loaded properly.")



   
