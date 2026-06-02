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
        df[col] = pd.to_datetime(df[col], errors='coerce')

    df['Days_to_Expire'] = (df['Expiration_Date'] - pd.Timestamp(current_date)).dt.days

    # Fill missing
    df['Catagory'] = df['Catagory'].fillna('Unknown')

    # Avg daily sales (proxy)
    df['Avg_Daily_Sales'] = df['Sales_Volume'] / 30
    df['Avg_Daily_Sales'] = df['Avg_Daily_Sales'].replace([0], 1)

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
    avg_turnover = df['Inventory_Turnover_Rate'].mean()

    total_received = df['Stock_Quantity'].sum()
    total_requested = df['Reorder_Quantity'].sum()
    fill_rate = total_received / total_requested if total_requested > 0 else 0

    return gmroii, coverage, near_expiry, avg_turnover, fill_rate


# --- Dashboard ---
if not df.empty:

    gmroii, coverage, near_expiry, turnover, fill_rate = calculate_kpis(df)

    st.title("📈 Inventory Efficiency & Working Capital Optimization Dashboard")

    st.markdown("""
    This dashboard identifies inventory inefficiencies, working capital blockage
    and operational risks to support decision-making.
    """)

    st.markdown("---")

    # KPI Row
    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Estimated GMROII", f"{gmroii:.2f}x")
    col2.metric("Inventory Coverage", f"{coverage:.1f} days")
    col3.metric("Near Expiry Risk", f"₹{near_expiry:,.0f}")
    col4.metric("Inventory Turnover", f"{turnover:.1f}x")
    col5.metric("Stock Availability Ratio (Proxy)", f"{fill_rate:.1%}")

    # --- Insights ---
    st.markdown("---")
    st.subheader("📌 Key Business Insights & Actions")

    category_perf = df.groupby('Catagory').agg({
        'Inventory_Value': 'sum',
        'Sales_Volume': 'sum'
    }).reset_index()

    category_perf['Inv_to_Sales'] = category_perf['Inventory_Value'] / category_perf['Sales_Volume']
    problem_categories = category_perf.sort_values('Inv_to_Sales', ascending=False).head(3)

    st.write(f"""
    - ₹{near_expiry:,.0f} inventory at risk → Immediate liquidation required  
    - Inventory coverage: {coverage:.1f} days → {'Overstocking risk' if coverage > 45 else 'Healthy'}  
    - High inventory low sales categories: {', '.join(problem_categories['Catagory'])}
    """)

    # --- Charts ---
    st.markdown("---")
    st.subheader("📊 Analysis")

    col1, col2 = st.columns(2)

    with col1:
        status_counts = df['Status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        fig = px.pie(status_counts, values='Count', names='Status', hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        top_products = df.groupby('Product_Name')['Total_Revenue'].sum().nlargest(10).reset_index()
        fig = px.bar(top_products, x='Product_Name', y='Total_Revenue', color='Total_Revenue')
        st.plotly_chart(fig, use_container_width=True)

    # --- Heatmap ---
    st.markdown("---")
    st.subheader("💰 Working Capital Blockage Heatmap")

    fig = px.density_heatmap(
        df,
        x='Catagory',
        y='Product_Name',
        z='Inventory_Value',
        color_continuous_scale='Reds',
        hover_data={'Product_Name': True, 'Inventory_Value': ':.0f'}
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- Top Blocked Items ---
    st.subheader("💰 Top 10 Cash Blocked Items")

    top_blocked = df.sort_values(by='Inventory_Value', ascending=False).head(10)
    st.dataframe(
        top_blocked[['Product_Name', 'Catagory', 'Stock_Quantity', 'Inventory_Value']],
        use_container_width=True
    )

    # --- Category Scatter ---
    st.markdown("---")
    st.subheader("Category Performance")

    cat = df.groupby('Catagory').agg({
        'Inventory_Value': 'sum',
        'Sales_Volume': 'mean',
        'Product_Margin': 'mean'
    }).reset_index()

    fig = px.scatter(
        cat,
        x='Sales_Volume',
        y='Inventory_Value',
        size='Inventory_Value',
        color='Product_Margin',
        hover_name='Catagory'
    )

    fig.update_traces(
        hovertemplate="<b>Category: %{hovertext}</b><br>" +
                      "Inventory Value: ₹%{y:,.0f}<br>" +
                      "Avg Sales Volume: %{x:,.0f}<br>" +
                      "Margin: %{marker.color:.1%}<extra></extra>"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("""
    **Insight:** High inventory & low sales = working capital blockage.
    """)

    # --- Dead Inventory ---
    st.markdown("---")
    st.subheader("🚨 Dead / Slow Moving Inventory")

    dead = df[
        (df['Sales_Volume'] < df['Sales_Volume'].quantile(0.25)) &
        (df['Stock_Quantity'] > df['Stock_Quantity'].quantile(0.75))
    ]

    st.dataframe(
        dead[['Product_Name', 'Catagory', 'Stock_Quantity', 'Sales_Volume', 'Inventory_Value']],
        use_container_width=True
    )

else:
    st.warning("Dataset not loaded properly.")
