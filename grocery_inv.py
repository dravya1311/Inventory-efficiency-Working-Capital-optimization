import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date 

# --- Configuration ---
st.set_page_config(layout="wide", page_title="Supply Chain Inventory KPI Dashboard")

# Calculate the current date using the simplest method possible (date.today())
# This is defined outside the cached function for reliability.
TODAY = date.today() 

# --- Data Loading and Preprocessing ---
@st.cache_data
def load_data(file_path, current_date):
    """Loads and preprocesses the inventory data."""
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        st.error(f"Error: File not found at {file_path}. Please ensure 'Grocery_Inventory.csv' is in the correct path.")
        return pd.DataFrame() # Return empty DataFrame on error

    # Clean column names by stripping whitespace (Fixes common KeyError)
    df.columns = df.columns.str.strip()

    # 1. Clean 'Unit_Price' (Remove '$' and convert to float)
    df['Unit_Price'] = df['Unit_Price'].astype(str).str.replace('$', '', regex=False).str.strip()
    df['Unit_Price'] = pd.to_numeric(df['Unit_Price'], errors='coerce')

    # 2. Clean 'percentage' (now treated as 'Product_Margin')
    if 'percentage' in df.columns:
        # Convert the percentage string to a decimal fraction (e.g., "1.96%" -> 0.0196)
        df['Product_Margin'] = df['percentage'].astype(str).str.replace('%', '', regex=False).str.strip()
        df['Product_Margin'] = pd.to_numeric(df['Product_Margin'], errors='coerce') / 100 
    else:
        st.error("Financial column 'percentage' (intended for Margin) not found. Setting Margin to 0.0.")
        df['Product_Margin'] = 0.0

    # 3. Calculate Key Derived Metrics
    df['Inventory_Value'] = df['Stock_Quantity'] * df['Unit_Price']
    df['Total_Revenue'] = df['Sales_Volume'] * df['Unit_Price']
    
    # 4. Handle Date Columns (for shelf-life analysis)
    date_cols = ['Date_Received', 'Last_Order_Date', 'Expiration_Date']
    for col in date_cols:
        # Use a flexible conversion attempt
        df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=False)

    # 5. Calculate Days Until Expiration
    # FIX: Explicitly convert the simple date object to a Pandas Timestamp for robust subtraction
    df['Days_to_Expire'] = (df['Expiration_Date'] - pd.Timestamp(current_date)).dt.days
    
    # Fill any missing Category values for safe grouping
    df['Catagory'] = df['Catagory'].fillna('Unknown')
    
    # Calculate Average Daily Sales Volume for Coverage Ratio (based on Sales_Volume / 30 days proxy)
    df['Avg_Daily_Sales'] = df['Sales_Volume'] / 30 # Simple 30-day average proxy
    # Handle division by zero
    df['Avg_Daily_Sales'] = df['Avg_Daily_Sales'].replace([float('inf'), float('-inf'), 0], 1)

    return df

# Attempt to load the data, passing TODAY as a parameter
df = load_data('Grocery_Inventory.csv', TODAY)

# --- KPI Calculation Function (Advanced Set) ---
def calculate_kpis(df):
    """Calculates and returns the primary advanced dashboard KPIs."""
    if df.empty:
        return None

    # 1. Gross Margin Return on Inventory Investment (GMROII)
    # (Total Revenue * Avg Margin) / Total Inventory Value
    total_inventory_value = df['Inventory_Value'].sum()
    total_sales_with_margin = (df['Total_Revenue'] * df['Product_Margin']).sum()
    gmroii = total_sales_with_margin / total_inventory_value if total_inventory_value > 0 else 0

    # 2. Inventory Coverage Ratio (Days of Supply)
    # Total Stock Quantity / Average Daily Sales Volume (across all products)
    total_stock = df['Stock_Quantity'].sum()
    total_avg_daily_sales = df['Avg_Daily_Sales'].sum()
    coverage_ratio = total_stock / total_avg_daily_sales if total_avg_daily_sales > 0 else 0

    # 3. Expired/Near-Expired Value (Inventory that expires in 7 days or less)
    near_expired_value = df[df['Days_to_Expire'] <= 7]['Inventory_Value'].sum()

    # 4. Average Inventory Turnover Rate (ATR)
    avg_turnover_rate = df['Inventory_Turnover_Rate'].mean()
    
    # 5. Fill Rate Proxy (Simplistic based on available columns: Items Received / Items Requested)
    # Note: Requires external data for true Fill Rate, but we proxy with data we have:
    total_received = df['Stock_Quantity'].sum()
    total_requested_proxy = df['Reorder_Quantity'].sum()
    fill_rate_proxy = total_received / total_requested_proxy if total_requested_proxy > 0 else 0

    return {
        'GMROII': gmroii,
        'Inventory Coverage Ratio (Days)': coverage_ratio,
        'Near-Expired Value (7 Days)': near_expired_value,
        'Avg Inventory Turnover Rate': avg_turnover_rate,
        'Fill Rate Proxy': fill_rate_proxy
    }

# --- Main Dashboard Layout ---
if not df.empty and calculate_kpis(df) is not None:
    kpis = calculate_kpis(df)

    # --- Header ---
    st.title("📈 Supply Chain Inventory & Financial Performance Dashboard")
    st.markdown("---")

    # --- KPI Cards (Row 1 - Advanced KPIs) ---
    st.subheader("Strategic & Financial Performance")
    
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="GMROII (Gross Margin Return on Inventory)",
            value=f"{kpis['GMROII']:.2f}x",
            help="Measures the amount of gross margin generated for every $1 invested in inventory."
        )

    with col2:
        st.metric(
            label="Inventory Coverage (Days of Supply)",
            value=f"{kpis['Inventory Coverage Ratio (Days)']:.1f} days",
            help="How many days the current stock quantity can cover average sales demand."
        )

    with col3:
        st.metric(
            label="Near-Expired Value (Risk)",
            value=f"${kpis['Near-Expired Value (7 Days)']:.0f}",
            help="Total monetary value of stock expiring in the next 7 days or less.",
            delta_color="inverse"
        )

    with col4:
        st.metric(
            label="Avg Inventory Turnover Rate",
            value=f"{kpis['Avg Inventory Turnover Rate']:.1f}x",
            help="Higher turnover indicates faster sales and better efficiency."
        )

    with col5:
        st.metric(
            label="Fill Rate Proxy (Received/Requested)",
            value=f"{kpis['Fill Rate Proxy']:.1%}",
            help="Simplified measure of how often requested stock quantity is received."
        )

    st.markdown("---")

    # --- Analytical Charts (Row 2) ---
    st.subheader("Deep Dive Analysis")
    chart_col1, chart_col2 = st.columns([1, 1.3])

    # Chart 1: Inventory Health by Status (Pie Chart)
    with chart_col1:
        st.markdown("##### 1. Operational Status Breakdown")
        status_counts = df['Status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        fig_status = px.pie(
            status_counts,
            values='Count',
            names='Status',
            title='Proportion of Stock by Operational Status',
            color_discrete_sequence=px.colors.qualitative.Bold,
            hole=0.4
        )
        fig_status.update_traces(textposition='inside', textinfo='percent+label')
        fig_status.update_layout(showlegend=True)
        st.plotly_chart(fig_status, use_container_width=True)

    # Chart 2: Top 10 Products by Sales Revenue (Bar Chart)
    with chart_col2:
        st.markdown("##### 2. Top 10 Products by Sales Revenue")
        top_products = df.groupby('Product_Name')['Total_Revenue'].sum().nlargest(10).reset_index()
        top_products.columns = ['Product_Name', 'Total_Revenue']
        fig_revenue = px.bar(
            top_products,
            x='Product_Name',
            y='Total_Revenue',
            color='Total_Revenue',
            title='Highest Revenue Generating Products',
            labels={'Total_Revenue': 'Total Revenue ($)', 'Product_Name': 'Product'},
            color_continuous_scale=px.colors.sequential.Plasma
        )
        fig_revenue.update_layout(xaxis={'categoryorder':'total descending'}, yaxis_title="Total Revenue ($)")
        st.plotly_chart(fig_revenue, use_container_width=True)

    # --- Analytical Chart (Row 3) ---
    st.subheader("Category Performance: Sales vs. Inventory Value")
    
    # Chart 3: Inventory Value and Sales Volume by Category (Scatter Plot)
    category_agg = df.groupby('Catagory').agg(
        Total_Inventory_Value=('Inventory_Value', 'sum'),
        Average_Sales_Volume=('Sales_Volume', 'mean'),
        Average_Margin=('Product_Margin', 'mean'), 
        Unique_Suppliers=('Supplier_ID', 'nunique')
    ).reset_index()
    
    fig_cat = px.scatter(
        category_agg,
        x='Average_Sales_Volume',
        y='Total_Inventory_Value',
        size='Total_Inventory_Value',
        color='Average_Margin', 
        hover_name='Catagory',
        size_max=60,
        title='Inventory Value vs. Avg Sales Volume by Category (Color = Avg Margin)',
        labels={
            'Average_Sales_Volume': 'Average Sales Volume (Units)',
            'Total_Inventory_Value': 'Total Inventory Value ($)',
            'Average_Margin': 'Average Margin'
        },
        color_continuous_scale=px.colors.sequential.Viridis
    )
    # Customize hover template for margin display
    fig_cat.update_traces(hovertemplate="<b>Category: %{hovertext}</b><br>" +
                                        "Inventory Value: $%{y:,.0f}<br>" +
                                        "Avg Sales Volume: %{x:,.0f}<br>" +
                                        "Avg Margin: %{marker.color:.1%}<extra></extra>")
    st.plotly_chart(fig_cat, use_container_width=True)

    # --- Raw Data Expiring Soon ---
    st.markdown("---")
    st.subheader("🚨 Raw Data: Products Nearing Expiration (7 Days Risk)")
    expiring_soon_data = df[df['Days_to_Expire'] <= 7].sort_values('Days_to_Expire')
    
    # Select relevant columns for display
    display_cols = [
        'Product_Name',
        'Catagory',
        'Supplier_Name',
        'Stock_Quantity',
        'Expiration_Date',
        'Days_to_Expire',
        'Inventory_Value',
        'Product_Margin'
    ]
    # FIX: Removed .background_gradient() which requires matplotlib
    st.dataframe(expiring_soon_data[display_cols].style.format({'Product_Margin': '{:.1%}'}), use_container_width=True)


else:
    # This message appears if the DataFrame is empty (e.g., file not found or corrupted)
    st.warning("Please ensure the 'Grocery_Inventory.csv' file is accessible and properly formatted to run the dashboard. Check for data inconsistencies or missing critical columns.")