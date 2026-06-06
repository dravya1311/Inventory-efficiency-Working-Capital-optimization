import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

# --- CONFIG ---
st.set_page_config(layout="wide", page_title="Inventory Efficiency Dashboard")
TODAY = date.today()

# --- LOAD DATA ---
@st.cache_data
def load_data(file_path, current_date):
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        st.error("File not found. Please check path.")
        return pd.DataFrame()

    # Clean column names
    df.columns = df.columns.str.strip()

    # --- Data Cleaning ---
    if 'Unit_Price' in df.columns:
        df['Unit_Price'] = df['Unit_Price'].astype(str).str.replace('$', '', regex=False)
        df['Unit_Price'] = pd.to_numeric(df['Unit_Price'], errors='coerce')

    # Margin
    if 'percentage' in df.columns:
        df['Product_Margin'] = df['percentage'].astype(str).str.replace('%', '', regex=False)
        df['Product_Margin'] = pd.to_numeric(df['Product_Margin'], errors='coerce') / 100
    else:
        df['Product_Margin'] = 0.0

    # Derived Metrics
    df['Inventory_Value'] = df.get('Stock_Quantity', 0) * df.get('Unit_Price', 0)
    df['Total_Revenue'] = df.get('Sales_Volume', 0) * df.get('Unit_Price', 0)

    # Dates
    for col in ['Date_Received', 'Last_Order_Date', 'Expiration_Date']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    if 'Expiration_Date' in df.columns:
        df['Days_to_Expire'] = (df['Expiration_Date'] - pd.Timestamp(current_date)).dt.days
    else:
        df['Days_to_Expire'] = 999

    # Fix Category spelling safely
    if 'Catagory' in df.columns:
        df['Catagory'] = df['Catagory'].fillna('Unknown')
    else:
        df['Catagory'] = 'Unknown'

    # Avg daily sales (safe)
    df['Avg_Daily_Sales'] = df.get('Sales_Volume', 0) / 30
    df['Avg_Daily_Sales'] = df['Avg_Daily_Sales'].replace(0, 1)

    return df


df = load_data('Grocery_Inventory.csv', TODAY)

# --- FILTERS ---
if not df.empty:

    st.sidebar.header("🔍 Filters")

    if 'Catagory' in df.columns:
        category_filter = st.sidebar.multiselect("Category", df['Catagory'].unique())
        if category_filter:
            df = df[df['Catagory'].isin(category_filter)]

    if 'Supplier_Name' in df.columns:
        supplier_filter = st.sidebar.multiselect("Supplier", df['Supplier_Name'].unique())
        if supplier_filter:
            df = df[df['Supplier_Name'].isin(supplier_filter)]

    # --- KPI FUNCTION ---
    def calculate_kpis(df):
        total_inventory_value = df['Inventory_Value'].sum()

        total_sales_with_margin = (df['Total_Revenue'] * df['Product_Margin']).sum()
        gmroii = total_sales_with_margin / total_inventory_value if total_inventory_value > 0 else 0

        total_stock = df.get('Stock_Quantity', 0).sum()
        total_avg_daily_sales = df['Avg_Daily_Sales'].sum()
        coverage = total_stock / total_avg_daily_sales if total_avg_daily_sales > 0 else 0

        near_expiry = df[df['Days_to_Expire'] <= 7]['Inventory_Value'].sum()
        risk_percent = (near_expiry / total_inventory_value) * 100 if total_inventory_value > 0 else 0

        turnover = df.get('Inventory_Turnover_Rate', pd.Series([0])).mean()

        return gmroii, coverage, near_expiry, turnover, risk_percent

    gmroii, coverage, near_expiry, turnover, risk_percent = calculate_kpis(df)

    # --- HEADER ---
    st.title("📈 Inventory Efficiency & Working Capital Optimization Dashboard")

    st.markdown("""
    This dashboard identifies inventory inefficiencies, working capital blockage,
    and operational risks to support decision-making.
    """)

    st.markdown("---")

    # --- KPI DISPLAY ---
    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Estimated GMROII", f"{gmroii:.2f}x")
    col2.metric("Inventory Coverage", f"{coverage:.1f} days")
    col3.metric("Near Expiry Risk", f"₹{near_expiry:,.0f}")
    col4.metric("Inventory Turnover", f"{turnover:.1f}x")
    col5.metric("Inventory at Risk (%)", f"{risk_percent:.1f}%")

    # --- INSIGHTS ---
    st.markdown("---")
    st.subheader("📌 Key Insights")

    category_perf = df.groupby('Catagory').agg({
        'Inventory_Value': 'sum',
        'Sales_Volume': 'sum'
    }).reset_index()

    category_perf['Inv_to_Sales'] = category_perf['Inventory_Value'] / category_perf['Sales_Volume'].replace(0, 1)
    problem_categories = category_perf.sort_values('Inv_to_Sales', ascending=False).head(3)

    st.write(f"""
    - ₹{near_expiry:,.0f} inventory at risk → Immediate action required  
    - Inventory coverage: {coverage:.1f} days  
    - Problem categories: {', '.join(problem_categories['Catagory'])}
    """)

    # --- CHARTS ---
    st.markdown("---")
    col1, col2 = st.columns(2)

    if 'Status' in df.columns:
        with col1:
            fig = px.pie(df, names='Status')
            st.plotly_chart(fig, use_container_width=True)

    if 'Product_Name' in df.columns:
        with col2:
            top_products = df.groupby('Product_Name')['Total_Revenue'].sum().nlargest(10).reset_index()
            fig = px.bar(top_products, x='Product_Name', y='Total_Revenue')
            st.plotly_chart(fig, use_container_width=True)

    # --- DEAD INVENTORY ---
    st.markdown("---")
    st.subheader("🚨 Dead Inventory")

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

    # --- FOOTER ---
    st.markdown("---")
    st.caption("Developed by R Yadav")

else:
    st.warning("Dataset not loaded properly.")
