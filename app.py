"""
Net Worth Calculator - Local-First Multi-Currency Portfolio Manager
Supports: Stocks/ETFs (US & India), Indian Mutual Funds, Cash
Display: INR, AED, USD with live exchange rates
"""

import streamlit as st
import sqlite3
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, date
from typing import Dict, Tuple, Optional, Union
import plotly.graph_objects as go
import plotly.express as px
import logging

# Configuration
DB_PATH = "portfolio.db"
TIMEOUTS = {"yfinance": 10, "mfapi": 8}
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== DATABASE FUNCTIONS ====================
def init_database():
    """Initialize SQLite database with portfolio schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_type TEXT NOT NULL,
            asset_name TEXT NOT NULL,
            ticker TEXT,
            quantity REAL NOT NULL,
            buy_price REAL NOT NULL,
            currency TEXT NOT NULL,
            geography TEXT NOT NULL,
            asset_class TEXT NOT NULL,
            purchase_date DATE,
            xirr REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add columns if they don't exist (for existing databases)
    cursor.execute("PRAGMA table_info(portfolio)")
    columns = [column[1] for column in cursor.fetchall()]

    if "purchase_date" not in columns:
        try:
            cursor.execute("ALTER TABLE portfolio ADD COLUMN purchase_date DATE")
            logger.info("Added purchase_date column")
        except Exception as e:
            logger.warning(f"Could not add purchase_date: {e}")

    if "xirr" not in columns:
        try:
            cursor.execute("ALTER TABLE portfolio ADD COLUMN xirr REAL")
            logger.info("Added xirr column")
        except Exception as e:
            logger.warning(f"Could not add xirr: {e}")

    conn.commit()
    conn.close()

def get_all_holdings() -> pd.DataFrame:
    """Fetch all holdings from database."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM portfolio ORDER BY updated_at DESC", conn)
    conn.close()
    return df

def add_holding(asset_type: str, asset_name: str, ticker: str, quantity: float,
                buy_price: float, currency: str, geography: str, asset_class: str,
                purchase_date: Optional[str] = None, xirr: Optional[float] = None) -> bool:
    """Add new holding to database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO portfolio
            (asset_type, asset_name, ticker, quantity, buy_price, currency, geography, asset_class, purchase_date, xirr)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (asset_type, asset_name, ticker, quantity, buy_price, currency, geography, asset_class, purchase_date, xirr))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error adding holding: {e}")
        st.error(f"Failed to add holding: {str(e)}")
        return False

def delete_holding(holding_id: int) -> bool:
    """Delete holding from database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM portfolio WHERE id = ?", (holding_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error deleting holding: {e}")
        return False

def update_holding(holding_id: int, asset_type: str, asset_name: str, ticker: str, quantity: float,
                   buy_price: float, currency: str, geography: str, asset_class: str,
                   purchase_date: Optional[str] = None, xirr: Optional[float] = None) -> bool:
    """Update existing holding in database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE portfolio
            SET asset_type = ?, asset_name = ?, ticker = ?, quantity = ?, buy_price = ?,
                currency = ?, geography = ?, asset_class = ?, purchase_date = ?, xirr = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (asset_type, asset_name, ticker, quantity, buy_price, currency, geography, asset_class, purchase_date, xirr, holding_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error updating holding: {e}")
        st.error(f"Failed to update holding: {str(e)}")
        return False

# ==================== PRICE FETCHING FUNCTIONS ====================
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_exchange_rates() -> Dict[str, float]:
    """Fetch USD to INR and USD to AED exchange rates."""
    rates = {"USDINR": 85.5, "USDAED": 3.67}  # Realistic fallback rates

    try:
        logger.info("Fetching USDINR exchange rate...")
        data_inr = yf.Ticker("USDINR=X")
        hist = data_inr.history(period="1d")
        if not hist.empty and "Close" in hist.columns:
            rate_inr = float(hist["Close"].iloc[-1])
            if rate_inr > 0:
                rates["USDINR"] = rate_inr
                logger.info(f"USDINR: {rate_inr}")
    except Exception as e:
        logger.warning(f"Error fetching USDINR: {e}")

    try:
        logger.info("Fetching USDAED exchange rate...")
        data_aed = yf.Ticker("USDAED=X")
        hist = data_aed.history(period="1d")
        if not hist.empty and "Close" in hist.columns:
            rate_aed = float(hist["Close"].iloc[-1])
            if rate_aed > 0:
                rates["USDAED"] = rate_aed
                logger.info(f"USDAED: {rate_aed}")
    except Exception as e:
        logger.warning(f"Error fetching USDAED: {e}")

    logger.info(f"Final exchange rates: {rates}")
    return rates

def validate_stock_ticker(ticker: str) -> Tuple[bool, str]:
    """Validate if stock/ETF ticker exists. Returns (is_valid, message)."""
    try:
        data = yf.Ticker(ticker)
        info = data.info
        if "regularMarketPrice" in info or "currentPrice" in info:
            return True, f"✅ Found: {info.get('longName', ticker)}"

        # Try downloading to validate
        hist = data.history(period="5d")
        if not hist.empty:
            return True, f"✅ Ticker {ticker} found"

        return False, "Could not fetch data for this ticker"
    except Exception as e:
        logger.warning(f"Validation error for {ticker}: {e}")
        return None, f"⚠️ Connection issue. If you're sure ticker is correct, proceed anyway. Error: {str(e)[:50]}"

@st.cache_data(ttl=300)
def get_stock_price(ticker: str) -> Optional[float]:
    """Fetch current stock/ETF price from yfinance."""
    if not ticker or ticker == "CASH":
        return None

    try:
        data = yf.Ticker(ticker)
        hist = data.history(period="5d")
        if not hist.empty and "Close" in hist.columns:
            price = float(hist["Close"].iloc[-1])
            if price > 0:
                logger.info(f"✅ Stock price for {ticker}: {price}")
                return price
        logger.warning(f"⚠️ No valid price data for {ticker}")
    except Exception as e:
        logger.error(f"❌ Error fetching stock {ticker}: {str(e)[:100]}")
    return None

def validate_mf_amfi_code(amfi_code: str) -> Tuple[bool, Optional[str]]:
    """Validate if mutual fund AMFI code exists and return fund name."""
    try:
        url = f"https://api.mfapi.in/mf/{amfi_code}"
        response = requests.get(url, timeout=TIMEOUTS["mfapi"])
        response.raise_for_status()
        data = response.json()

        if "meta" in data and "fund_name" in data["meta"]:
            fund_name = data["meta"]["fund_name"]
            logger.info(f"Found mutual fund: {fund_name} ({amfi_code})")
            return True, fund_name
        elif "data" in data and len(data["data"]) > 0:
            return True, None
    except Exception as e:
        logger.warning(f"Validation failed for AMFI code {amfi_code}: {e}")

    return False, None

@st.cache_data(ttl=300)
def get_mf_nav(amfi_code: str) -> Optional[float]:
    """Fetch Indian Mutual Fund NAV from mfapi.in."""
    if not amfi_code:
        return None

    try:
        url = f"https://api.mfapi.in/mf/{amfi_code}"
        response = requests.get(url, timeout=TIMEOUTS["mfapi"])
        response.raise_for_status()
        data = response.json()

        if "data" in data and len(data["data"]) > 0:
            nav = float(data["data"][0]["nav"])
            if nav > 0:
                logger.info(f"✅ Mutual Fund NAV for {amfi_code}: {nav}")
                return nav
        logger.warning(f"⚠️ No valid NAV data for {amfi_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error fetching MF {amfi_code}: {str(e)[:100]}")
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"❌ Error parsing MF data for {amfi_code}: {str(e)[:100]}")

    return None

def get_current_price(asset_type: str, ticker: str) -> Optional[float]:
    """Get current price based on asset type."""
    if asset_type == "Cash":
        return 1.0
    elif asset_type == "Stock/ETF":
        return get_stock_price(ticker)
    elif asset_type == "Indian Mutual Fund":
        return get_mf_nav(ticker)
    return None

# ==================== CALCULATION FUNCTIONS ====================
def calculate_portfolio_value() -> Tuple[pd.DataFrame, Dict[str, float], Dict[str, float]]:
    """Calculate current portfolio value with all holdings and exchange rates."""
    df = get_all_holdings()
    rates = get_exchange_rates()

    if df.empty:
        return df, {"USD": 0.0, "INR": 0.0, "AED": 0.0}

    # Add current price and converted values
    df["current_price_usd"] = df.apply(
        lambda row: convert_to_usd(row["buy_price"], row["currency"], rates) if row["asset_type"] == "Cash"
        else convert_to_usd(get_current_price(row["asset_type"], row["ticker"]) or row["buy_price"], row["currency"], rates),
        axis=1
    )

    df["current_value_usd"] = df["quantity"] * df["current_price_usd"]

    df["cost_value_usd"] = df.apply(
        lambda row: row["quantity"] * convert_to_usd(row["buy_price"], row["currency"], rates),
        axis=1
    )

    df["gain_loss_usd"] = df["current_value_usd"] - df["cost_value_usd"]

    # Calculate XIRR for each holding (convert buy_price to USD for consistent comparison)
    df["calculated_xirr"] = df.apply(
        lambda row: calculate_xirr(
            row.get("purchase_date"),
            convert_to_usd(row["buy_price"], row["currency"], rates),  # Convert to USD
            row["current_price_usd"],
            row["quantity"]
        ) if row["asset_type"] in ["Stock/ETF", "Indian Mutual Fund"] else None,
        axis=1
    )

    total_usd = df["current_value_usd"].sum()
    total_inr = total_usd * rates["USDINR"]
    total_aed = total_usd * rates["USDAED"]

    return df, {"USD": round(total_usd, 2), "INR": round(total_inr, 2), "AED": round(total_aed, 2)}, rates

def convert_to_usd(amount: float, currency: str, rates: Dict[str, float]) -> float:
    """Convert any currency amount to USD."""
    if currency == "USD":
        return amount
    elif currency == "INR":
        return amount / rates["USDINR"]
    elif currency == "AED":
        return amount / rates["USDAED"]
    return amount

def calculate_xirr(purchase_date: Optional[str], buy_price_usd: float, current_price_usd: float, quantity: float) -> Optional[float]:
    """
    Calculate XIRR (Extended Internal Rate of Return) based on purchase date and current price.
    Both prices must be in USD (same currency).
    Returns annual percentage return.
    """
    if not purchase_date or buy_price_usd <= 0 or quantity <= 0 or current_price_usd <= 0:
        return None

    try:
        purchase_dt = pd.to_datetime(purchase_date).date()
        today = datetime.now().date()

        days_held = (today - purchase_dt).days
        if days_held <= 0:
            return 0.0

        initial_investment = buy_price_usd * quantity
        current_value = current_price_usd * quantity

        # XIRR = ((current_value / initial_investment) ^ (365 / days_held)) - 1
        # Formula: (ending_value / beginning_value) ^ (365 / days) - 1
        xirr = ((current_value / initial_investment) ** (365 / days_held)) - 1
        return round(xirr * 100, 2)  # Convert to percentage

    except Exception as e:
        logger.warning(f"Could not calculate XIRR: {e}")
        return None

def get_asset_class_allocation(df: pd.DataFrame) -> Dict[str, float]:
    """Calculate asset class allocation by value."""
    if df.empty:
        return {}
    return df.groupby("asset_class")["current_value_usd"].sum().to_dict()

def get_geographic_allocation(df: pd.DataFrame) -> Dict[str, float]:
    """Calculate geographic allocation by value."""
    if df.empty:
        return {}
    return df.groupby("geography")["current_value_usd"].sum().to_dict()

# ==================== UI COMPONENTS ====================
def render_metric_cards(totals: Dict[str, float], rates: Dict[str, float]):
    """Render compact metric cards for total net worth."""
    col1, col2, col3 = st.columns(3, gap="small")

    # Indian Rupee Card
    with col1:
        with st.container(border=True):
            st.markdown("**🇮🇳 Total Net Worth (INR)**")
            st.markdown(f"### ₹ {totals['INR']:,.0f}")

    # US Dollar Card
    with col2:
        with st.container(border=True):
            st.markdown("**🇺🇸 Total Net Worth (USD)**")
            st.markdown(f"### $ {totals['USD']:,.0f}")

    # UAE Dirham Card
    with col3:
        with st.container(border=True):
            st.markdown("**🇦🇪 Total Net Worth (AED)**")
            st.markdown(f"### د.إ {totals['AED']:,.0f}")

    # Compact Session Info
    st.caption(f"📈 Rates: 1 USD = ₹{rates['USDINR']:.2f} | د.إ {rates['USDAED']:.2f}")

def render_input_form():
    """Render compact input form for adding new assets."""
    st.markdown("##### ➕ Add New Asset")

    # Asset Type selector OUTSIDE form to enable on_change callback
    asset_type = st.selectbox(
        "Asset Type",
        ["Stock/ETF", "Indian Mutual Fund", "Cash"],
        key="asset_type_select",
        on_change=st.rerun
    )

    with st.form("asset_form", border=True):
        col1, col2 = st.columns(2)

        with col1:
            asset_name = st.text_input("Asset Name (e.g., Apple, HDFC Bank)", placeholder="e.g., Apple Inc")
            currency = st.selectbox("Currency", ["INR", "USD", "AED"], key="currency_select")

        with col2:
            if asset_type == "Cash":
                ticker = "CASH"
                st.info("💰 For Cash, enter the total amount below")
            else:
                help_text = (
                    "**India**: HDFCBANK.NS, INFY.NS, RELIANCE.NS, TCS.NS, SBIN.NS\n\n"
                    "**US**: AAPL, MSFT, GOOGL, AMZN, TSLA\n\n"
                    "**MF AMFI**: 6-digit code (e.g., 104556)"
                ) if asset_type == "Stock/ETF" else "6-digit AMFI code (e.g., 104556)"

                ticker = st.text_input(
                    "Ticker / AMFI Code",
                    placeholder="HDFCBANK.NS or AAPL" if asset_type == "Stock/ETF" else "104556",
                    help=help_text
                )

        # Dynamic fields based on asset type
        if asset_type == "Cash":
            # For Cash: show only total amount
            quantity = 1.0  # Always 1 for cash
            buy_price = st.number_input(
                "💰 Total Amount",
                min_value=0.01,
                value=1.0,
                step=0.01,
                help="Total cash amount you have"
            )
        else:
            # For Stocks/ETF and Mutual Funds: show quantity and price per unit
            quantity = st.number_input(
                "Quantity / Units",
                min_value=0.01,
                value=1.0,
                step=0.01,
                help="Number of units/shares you own"
            )
            buy_price = st.number_input(
                "Purchase Price Per Unit",
                min_value=0.01,
                value=1.0,
                step=0.01,
                help="Price per unit/share when purchased"
            )

        col3, col4 = st.columns(2)
        with col3:
            geography = st.selectbox("Geography", ["India", "US", "Global"], key="geo_select")

        with col4:
            # Auto-select Cash asset class if Cash type is selected
            default_class = 3 if asset_type == "Cash" else 0  # Index 3 = "Cash", 0 = "Equity"
            asset_class = st.selectbox(
                "Asset Class",
                ["Equity", "Debt", "Gold", "Cash"],
                index=default_class,
                key="class_select"
            )

        col5, col6 = st.columns(2)
        with col5:
            purchase_date = st.date_input(
                "Purchase Date (Optional)",
                value=None,
                key="purchase_date_select",
                min_value=date(1975, 1, 1),
                max_value=date.today(),
                help="Date when you purchased this asset (from January 1975)"
            )

        with col6:
            xirr = None
            if asset_type == "Stock/ETF":
                xirr = st.number_input(
                    "XIRR % (Optional)",
                    min_value=-100.0,
                    max_value=500.0,
                    value=0.0,
                    step=0.1,
                    help="Extended Internal Rate of Return (annual % return)"
                )
                if xirr == 0.0:
                    xirr = None

        submitted = st.form_submit_button("✅ Add Asset", use_container_width=True)

        if submitted:
            # Validation
            if not asset_name:
                st.error("❌ Asset name is required")
            elif asset_type != "Cash" and not ticker:
                st.error("❌ Ticker/AMFI code is required for this asset type")
            else:
                validation_passed = True
                validation_msg = ""
                needs_confirmation = False

                # Validate ticker exists
                if asset_type == "Stock/ETF":
                    with st.spinner(f"🔍 Validating ticker {ticker}..."):
                        is_valid, msg = validate_stock_ticker(ticker)
                        validation_msg = msg

                        if is_valid is False:
                            st.error(f"❌ {msg}")
                            validation_passed = False
                        elif is_valid is None:
                            # Connection issue - ask for confirmation
                            st.warning(f"⚠️ Could not verify ticker '{ticker}' due to connection issue.")
                            st.info(f"💡 {msg}")
                            needs_confirmation = True
                        else:
                            st.success(msg)

                elif asset_type == "Indian Mutual Fund":
                    with st.spinner(f"🔍 Validating AMFI code {ticker}..."):
                        is_valid, fund_name = validate_mf_amfi_code(ticker)
                        if not is_valid:
                            st.warning(f"⚠️ Could not verify AMFI code '{ticker}'")
                            st.info("💡 This code may be incorrect. Verify at: https://api.mfapi.in")
                            needs_confirmation = True
                        elif fund_name:
                            st.success(f"✅ Found: {fund_name}")

                # Show confirmation if needed
                if needs_confirmation and validation_passed:
                    st.divider()
                    confirm_col1, confirm_col2 = st.columns(2)
                    with confirm_col1:
                        if st.checkbox(f"✅ I confirm that '{ticker}' is correct and want to proceed"):
                            validation_passed = True
                        else:
                            validation_passed = False
                            st.info("Please verify the ticker and try again.")

                # Add holding if validation passed
                if validation_passed:
                    purchase_date_str = purchase_date.isoformat() if purchase_date else None
                    if add_holding(asset_type, asset_name, ticker, quantity, buy_price, currency, geography, asset_class, purchase_date_str, xirr):
                        st.success(f"✅ Added {asset_name} successfully!")
                        st.rerun()

def render_visualizations(df: pd.DataFrame):
    """Render compact donut charts for asset class and geographic distribution."""
    if df.empty:
        st.info("📊 Add assets to see visualizations")
        return

    st.markdown("##### 📈 Portfolio Allocation")

    col1, col2 = st.columns(2, gap="small")

    with col1:
        asset_allocation = get_asset_class_allocation(df)
        if asset_allocation:
            # Premium corporate blue palette for asset class
            colors = ["#0969DA", "#3b82f6", "#60a5fa", "#93c5fd"]
            fig = go.Figure(data=[go.Pie(
                labels=list(asset_allocation.keys()),
                values=list(asset_allocation.values()),
                hole=0.4,  # Creates donut chart
                marker=dict(colors=colors[:len(asset_allocation)], line=dict(color="#FFFFFF", width=2)),
                textposition="inside",
                textinfo="label+percent"
            )])
            fig.update_layout(
                title="<b>Asset Class</b>",
                title_font_size=13,
                height=320,
                margin=dict(l=0, r=0, t=30, b=0),
                showlegend=True,
                legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=0.95, font=dict(size=10)),
                paper_bgcolor="#F6F8FA",
                plot_bgcolor="#F6F8FA",
                font=dict(family="sans serif", color="#1F2328", size=10)
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        geo_allocation = get_geographic_allocation(df)
        if geo_allocation:
            # Premium green and teal palette for geography
            colors = ["#059669", "#10b981", "#34d399", "#6ee7b7"]
            fig = go.Figure(data=[go.Pie(
                labels=list(geo_allocation.keys()),
                values=list(geo_allocation.values()),
                hole=0.4,  # Creates donut chart
                marker=dict(colors=colors[:len(geo_allocation)], line=dict(color="#FFFFFF", width=2)),
                textposition="inside",
                textinfo="label+percent"
            )])
            fig.update_layout(
                title="<b>Geography</b>",
                title_font_size=13,
                height=320,
                margin=dict(l=0, r=0, t=30, b=0),
                showlegend=True,
                legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=0.95, font=dict(size=10)),
                paper_bgcolor="#F6F8FA",
                plot_bgcolor="#F6F8FA",
                font=dict(family="sans serif", color="#1F2328", size=10)
            )
            st.plotly_chart(fig, use_container_width=True)

def render_holdings_table(df: pd.DataFrame):
    """Render premium holdings table with professional formatting."""
    if df.empty:
        with st.container(border=True):
            st.markdown('<div style="padding: 30px; text-align: center;">', unsafe_allow_html=True)
            st.markdown("### 📋 No Holdings Yet")
            st.markdown("Add your first asset above to get started!")
            st.markdown('</div>', unsafe_allow_html=True)
        return

    st.markdown("##### 📋 Current Holdings")

    # Table header
    header_col1, header_col2, header_col3, header_col4, header_col5, header_col6, header_col7, header_col8, header_col9, header_col10, header_col11, header_col12, header_col13 = st.columns(
        [1.8, 1.2, 1.1, 0.75, 0.95, 0.75, 1.1, 1, 0.95, 1.1, 0.65, 0.65, 0.65], gap="small"
    )

    with header_col1:
        st.markdown("**Asset Name**")
    with header_col2:
        st.markdown("**Type**")
    with header_col3:
        st.markdown("**Ticker**")
    with header_col4:
        st.markdown("**Qty**")
    with header_col5:
        st.markdown("**Buy Price**")
    with header_col6:
        st.markdown("**Curr**")
    with header_col7:
        st.markdown("**Current Value**")
    with header_col8:
        st.markdown("**Geography**")
    with header_col9:
        st.markdown("**Class**")
    with header_col10:
        st.markdown("**Buy Date**")
    with header_col11:
        st.markdown("**XIRR %**")
    with header_col12:
        st.markdown("**Edit**")
    with header_col13:
        st.markdown("**Delete**")

    st.divider()

    # Table rows
    for idx, row in df.iterrows():
        col1, col2, col3, col4, col5, col6, col7, col8, col9, col10, col11, col12, col13 = st.columns(
            [1.8, 1.2, 1.1, 0.75, 0.95, 0.75, 1.1, 1, 0.95, 1.1, 0.65, 0.65, 0.65], gap="small"
        )

        holding_id = row["id"]
        confirm_delete_key = f"confirm_delete_{holding_id}"
        editing_key = f"editing_{holding_id}"

        with col1:
            st.text(row["asset_name"])
        with col2:
            st.text(row["asset_type"])
        with col3:
            st.text(str(row["ticker"]))
        with col4:
            st.text(f"{row['quantity']:.2f}")
        with col5:
            st.text(f"{row['buy_price']:.2f}")
        with col6:
            st.text(row["currency"])
        with col7:
            current_value = row.get("current_value_usd", 0)
            st.text(f"${current_value:,.2f}")
        with col8:
            st.text(row["geography"])
        with col9:
            st.text(row["asset_class"])
        with col10:
            purchase_date_val = row.get("purchase_date", "")
            if purchase_date_val:
                st.text(purchase_date_val[:10])
            else:
                st.text("—")
        with col11:
            calculated_xirr = row.get("calculated_xirr", None)
            manual_xirr = row.get("xirr", None)

            if calculated_xirr is not None:
                if manual_xirr and manual_xirr != 0:
                    st.text(f"📌 {manual_xirr:.2f}%")  # Manual override
                else:
                    st.text(f"📊 {calculated_xirr:.2f}%")  # Calculated
            elif manual_xirr and manual_xirr != 0:
                st.text(f"📌 {manual_xirr:.2f}%")  # Manual value only
            else:
                st.text("—")
        with col12:
            if st.button("✏️", key=f"edit_btn_{holding_id}", help="Click to edit this holding", use_container_width=True):
                st.session_state[editing_key] = not st.session_state.get(editing_key, False)
        with col13:
            if st.button("🗑️", key=f"delete_btn_{holding_id}", help="Click to delete this holding", use_container_width=True):
                st.session_state[confirm_delete_key] = True

        # Show edit form if editing is active
        if st.session_state.get(editing_key, False):
            st.info("✏️ Edit Mode - Modify the fields below and click Save")
            with st.form(f"edit_form_{holding_id}", border=True):
                edit_col1, edit_col2 = st.columns(2)

                with edit_col1:
                    edit_asset_type = st.selectbox(
                        "Asset Type",
                        ["Stock/ETF", "Indian Mutual Fund", "Cash"],
                        index=["Stock/ETF", "Indian Mutual Fund", "Cash"].index(row["asset_type"]),
                        key=f"edit_asset_type_{holding_id}",
                        on_change=st.rerun
                    )
                    edit_asset_name = st.text_input("Asset Name", value=row["asset_name"], key=f"edit_asset_name_{holding_id}")
                    edit_currency = st.selectbox("Currency", ["INR", "USD", "AED"], index=["INR", "USD", "AED"].index(row["currency"]), key=f"edit_currency_{holding_id}")

                with edit_col2:
                    if edit_asset_type == "Cash":
                        edit_ticker = "CASH"
                        st.info("💰 For Cash, edit the total amount below")
                    else:
                        edit_ticker = st.text_input("Ticker / AMFI Code", value=row["ticker"], key=f"edit_ticker_{holding_id}")

                    # Dynamic fields based on asset type
                    if edit_asset_type == "Cash":
                        edit_quantity = 1.0
                        edit_buy_price = st.number_input(
                            "💰 Total Amount",
                            value=float(row["buy_price"]),
                            step=0.01,
                            key=f"edit_buy_price_{holding_id}",
                            help="Total cash amount"
                        )
                    else:
                        edit_quantity = st.number_input(
                            "Quantity / Units",
                            value=float(row["quantity"]),
                            step=0.01,
                            key=f"edit_quantity_{holding_id}",
                            help="Number of units/shares"
                        )
                        edit_buy_price = st.number_input(
                            "Purchase Price Per Unit",
                            value=float(row["buy_price"]),
                            step=0.01,
                            key=f"edit_buy_price_{holding_id}",
                            help="Price per unit/share"
                        )

                edit_col3, edit_col4 = st.columns(2)
                with edit_col3:
                    edit_geography = st.selectbox("Geography", ["India", "US", "Global"], index=["India", "US", "Global"].index(row["geography"]), key=f"edit_geography_{holding_id}")

                with edit_col4:
                    edit_asset_class = st.selectbox("Asset Class", ["Equity", "Debt", "Gold", "Cash"], index=["Equity", "Debt", "Gold", "Cash"].index(row["asset_class"]), key=f"edit_asset_class_{holding_id}")

                edit_col5, edit_col6 = st.columns(2)
                with edit_col5:
                    purchase_date_val = row.get("purchase_date", None)
                    edit_purchase_date = st.date_input(
                        "Purchase Date",
                        value=pd.to_datetime(purchase_date_val).date() if purchase_date_val else None,
                        key=f"edit_purchase_date_{holding_id}",
                        min_value=date(1975, 1, 1),
                        max_value=date.today()
                    )

                with edit_col6:
                    edit_xirr = None
                    if edit_asset_type == "Stock/ETF":
                        xirr_val = row.get("xirr", None)
                        edit_xirr = st.number_input(
                            "XIRR %",
                            value=float(xirr_val) if xirr_val else 0.0,
                            min_value=-100.0,
                            max_value=500.0,
                            step=0.1,
                            key=f"edit_xirr_{holding_id}"
                        )
                        if edit_xirr == 0.0:
                            edit_xirr = None

                edit_submit_col1, edit_submit_col2 = st.columns(2)
                with edit_submit_col1:
                    if st.form_submit_button("💾 Save Changes", use_container_width=True):
                        edit_purchase_date_str = edit_purchase_date.isoformat() if edit_purchase_date else None
                        if update_holding(holding_id, edit_asset_type, edit_asset_name, edit_ticker, edit_quantity, edit_buy_price, edit_currency, edit_geography, edit_asset_class, edit_purchase_date_str, edit_xirr):
                            st.success(f"✅ Updated {edit_asset_name}")
                            st.session_state[editing_key] = False
                            st.rerun()

                with edit_submit_col2:
                    if st.form_submit_button("❌ Cancel", use_container_width=True):
                        st.session_state[editing_key] = False
                        st.rerun()

        # Show delete confirmation dialog if delete was clicked
        if st.session_state.get(confirm_delete_key, False):
            st.warning(f"⚠️ Delete **{row['asset_name']}** ({row['ticker']})? This cannot be undone.")
            conf_col1, conf_col2, conf_col3 = st.columns([1, 1, 2], gap="small")

            with conf_col1:
                if st.button("✅ Yes, Delete", key=f"confirm_yes_{holding_id}", use_container_width=True):
                    if delete_holding(holding_id):
                        st.success(f"✅ Deleted {row['asset_name']}")
                        del st.session_state[confirm_delete_key]
                        st.rerun()

            with conf_col2:
                if st.button("❌ Cancel", key=f"confirm_no_{holding_id}", use_container_width=True):
                    st.session_state[confirm_delete_key] = False
                    st.rerun()

            st.divider()

# ==================== MAIN APP ====================
def main():
    st.set_page_config(
        page_title="Wealth Manager Pro",
        page_icon="💼",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Premium Header (Compact)
    st.markdown("""
    <style>
    .header-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0969DA;
        margin: 0;
        padding: 0.3rem 0;
    }
    .header-subtitle {
        font-size: 0.85rem;
        color: #6B7280;
        margin: 0;
        padding: 0;
    }
    </style>
    <div class="header-title">💼 Wealth Manager Pro</div>
    <div class="header-subtitle">Portfolio Management & Net Worth Tracking</div>
    """, unsafe_allow_html=True)

    # Sidebar with ticker format reference
    with st.sidebar:
        st.markdown("### 📚 Asset Reference Guide")
        st.markdown("""
        **Indian Stocks (NSE)**
        - Append `.NS` to the stock symbol
        - Examples: `HDFCBANK.NS`, `INFY.NS`, `RELIANCE.NS`, `TCS.NS`, `SBIN.NS`, `MARUTI.NS`

        **Indian Stocks (BSE)**
        - Append `.BO` to the stock symbol
        - Examples: `HDFCBANK.BO`, `INFY.BO`

        **US Stocks**
        - Use the ticker symbol directly (no suffix)
        - Examples: `AAPL`, `MSFT`, `GOOGL`, `AMZN`, `TSLA`, `IBM`

        **Global Markets**
        - London: `.L` suffix (e.g., `ASML.AS`)
        - Europe: `.DE`, `.PA`, etc.

        **Mutual Funds**
        - 6-digit AMFI code (no suffix)
        - Example: `104556`

        **🔗 Find Tickers:**
        - [Yahoo Finance](https://finance.yahoo.com)
        - [NSE India](https://www.nseindia.com)
        - [MF India API](https://api.mfapi.in)
        """)

        st.divider()
        if st.button("🔄 Clear Cache & Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # Initialize database
    init_database()

    # Calculate portfolio
    df, totals, rates = calculate_portfolio_value()

    # Render compact dashboard
    render_metric_cards(totals, rates)

    # Input form
    render_input_form()

    # Visualizations
    if not df.empty:
        st.write("")  # Minimal spacing
        render_visualizations(df)

    # Holdings table
    st.write("")
    render_holdings_table(df)

    # Debug Info (collapsible)
    with st.expander("🔍 System Info"):
        if not df.empty:
            debug_df = df[[
                "asset_name", "asset_type", "ticker", "buy_price",
                "current_price_usd", "current_value_usd"
            ]].copy()
            debug_df.columns = ["Asset", "Type", "Ticker", "Buy Price", "Current Price (USD)", "Current Value (USD)"]

            # Format numeric columns
            for col in ["Buy Price", "Current Price (USD)", "Current Value (USD)"]:
                debug_df[col] = debug_df[col].apply(lambda x: f"${x:,.2f}")

            st.dataframe(debug_df, use_container_width=True, hide_index=True)

            col1, col2, col3 = st.columns(3, gap="small")
            with col1:
                st.metric("Total (USD)", f"${totals['USD']:,.0f}", label_visibility="collapsed")
            with col2:
                st.metric("USDINR", f"{rates['USDINR']:.2f}", label_visibility="collapsed")
            with col3:
                st.metric("USDAED", f"{rates['USDAED']:.2f}", label_visibility="collapsed")
        else:
            st.info("No holdings data to display")

    # Compact Footer
    col1, col2, col3 = st.columns([1, 1, 1], gap="small")
    with col1:
        st.caption(f"🕐 {datetime.now().strftime('%H:%M:%S')}")
    with col2:
        st.caption(f"📊 {len(df)} holdings")
    with col3:
        st.caption("portfolio.db")

if __name__ == "__main__":
    main()
