"""
Wealth Manager Pro - Demo Version
Session-state based portfolio manager (no database)
Suitable for Streamlit Community Cloud deployment
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, date
from typing import Dict, Tuple, Optional, Union
import plotly.graph_objects as go
import plotly.express as px
import logging

# Configuration
TIMEOUTS = {"yfinance": 10, "mfapi": 8}
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== SESSION STATE INITIALIZATION ====================
def init_session_state():
    """Initialize session state with dummy portfolio on first load."""
    if "portfolio" not in st.session_state:
        # Dummy portfolio with realistic data (Scenario 1 Demo)
        dummy_portfolio = [
            {
                "id": 1,
                "asset_type": "Stock/ETF",
                "asset_name": "Vanguard S&P 500 ETF",
                "ticker": "VOO",
                "quantity": 50.0,
                "buy_price": 350.0,
                "currency": "USD",
                "geography": "US",
                "asset_class": "Equity",
                "purchase_date": "2023-06-15",
                "xirr": None,
            },
            {
                "id": 2,
                "asset_type": "Stock/ETF",
                "asset_name": "Apple Inc",
                "ticker": "AAPL",
                "quantity": 25.0,
                "buy_price": 145.0,
                "currency": "USD",
                "geography": "US",
                "asset_class": "Equity",
                "purchase_date": "2024-01-10",
                "xirr": None,
            },
            {
                "id": 3,
                "asset_type": "Stock/ETF",
                "asset_name": "Infosys Limited",
                "ticker": "INFY.NS",
                "quantity": 100.0,
                "buy_price": 1650.0,
                "currency": "INR",
                "geography": "India",
                "asset_class": "Equity",
                "purchase_date": "2022-03-20",
                "xirr": None,
            },
            {
                "id": 4,
                "asset_type": "Stock/ETF",
                "asset_name": "Reliance Industries",
                "ticker": "RELIANCE.NS",
                "quantity": 75.0,
                "buy_price": 2450.0,
                "currency": "INR",
                "geography": "India",
                "asset_class": "Equity",
                "purchase_date": "2023-08-05",
                "xirr": None,
            },
            {
                "id": 5,
                "asset_type": "Indian Mutual Fund",
                "asset_name": "Axis Bluechip Fund",
                "ticker": "120465",
                "quantity": 500.0,
                "buy_price": 45.25,
                "currency": "INR",
                "geography": "India",
                "asset_class": "Equity",
                "purchase_date": "2023-12-01",
                "xirr": None,
            },
            {
                "id": 6,
                "asset_type": "Cash",
                "asset_name": "Savings Account (INR)",
                "ticker": "CASH",
                "quantity": 1.0,
                "buy_price": 500000.0,
                "currency": "INR",
                "geography": "India",
                "asset_class": "Cash",
                "purchase_date": None,
                "xirr": None,
            },
            {
                "id": 7,
                "asset_type": "Cash",
                "asset_name": "Checking Account (USD)",
                "ticker": "CASH",
                "quantity": 1.0,
                "buy_price": 25000.0,
                "currency": "USD",
                "geography": "US",
                "asset_class": "Cash",
                "purchase_date": None,
                "xirr": None,
            },
            {
                "id": 8,
                "asset_type": "Cash",
                "asset_name": "Emergency Fund (AED)",
                "ticker": "CASH",
                "quantity": 1.0,
                "buy_price": 50000.0,
                "currency": "AED",
                "geography": "Global",
                "asset_class": "Cash",
                "purchase_date": None,
                "xirr": None,
            },
        ]
        st.session_state.portfolio = pd.DataFrame(dummy_portfolio)
        st.session_state.next_id = 9

    if "editing" not in st.session_state:
        st.session_state.editing = {}

    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = {}


def get_all_holdings() -> pd.DataFrame:
    """Get all holdings from session state."""
    if "portfolio" in st.session_state:
        return st.session_state.portfolio.copy()
    return pd.DataFrame()


def add_holding(asset_type: str, asset_name: str, ticker: str, quantity: float,
                buy_price: float, currency: str, geography: str, asset_class: str,
                purchase_date: Optional[str] = None, xirr: Optional[float] = None) -> bool:
    """Add new holding to session state."""
    try:
        new_holding = {
            "id": st.session_state.next_id,
            "asset_type": asset_type,
            "asset_name": asset_name,
            "ticker": ticker,
            "quantity": quantity,
            "buy_price": buy_price,
            "currency": currency,
            "geography": geography,
            "asset_class": asset_class,
            "purchase_date": purchase_date,
            "xirr": xirr,
        }
        st.session_state.portfolio = pd.concat(
            [st.session_state.portfolio, pd.DataFrame([new_holding])],
            ignore_index=True
        )
        st.session_state.next_id += 1
        return True
    except Exception as e:
        logger.error(f"Error adding holding: {e}")
        st.error(f"Failed to add holding: {str(e)}")
        return False


def delete_holding(holding_id: int) -> bool:
    """Delete holding from session state."""
    try:
        st.session_state.portfolio = st.session_state.portfolio[st.session_state.portfolio["id"] != holding_id]
        return True
    except Exception as e:
        logger.error(f"Error deleting holding: {e}")
        return False


def update_holding(holding_id: int, asset_type: str, asset_name: str, ticker: str, quantity: float,
                   buy_price: float, currency: str, geography: str, asset_class: str,
                   purchase_date: Optional[str] = None, xirr: Optional[float] = None) -> bool:
    """Update existing holding in session state."""
    try:
        mask = st.session_state.portfolio["id"] == holding_id
        st.session_state.portfolio.loc[mask, "asset_type"] = asset_type
        st.session_state.portfolio.loc[mask, "asset_name"] = asset_name
        st.session_state.portfolio.loc[mask, "ticker"] = ticker
        st.session_state.portfolio.loc[mask, "quantity"] = quantity
        st.session_state.portfolio.loc[mask, "buy_price"] = buy_price
        st.session_state.portfolio.loc[mask, "currency"] = currency
        st.session_state.portfolio.loc[mask, "geography"] = geography
        st.session_state.portfolio.loc[mask, "asset_class"] = asset_class
        st.session_state.portfolio.loc[mask, "purchase_date"] = purchase_date
        st.session_state.portfolio.loc[mask, "xirr"] = xirr
        return True
    except Exception as e:
        logger.error(f"Error updating holding: {e}")
        st.error(f"Failed to update holding: {str(e)}")
        return False


# ==================== MOCKED PRICE DATA ====================
# For demo app: use realistic but mocked prices to avoid API delays on startup
DEMO_CURRENT_PRICES = {
    "VOO": 425.50,      # S&P 500 ETF
    "AAPL": 182.75,     # Apple
    "INFY.NS": 1875.25, # Infosys
    "RELIANCE.NS": 2890.50,  # Reliance
    "120465": 52.40,    # Axis Bluechip Fund NAV
}

@st.cache_data(ttl=300)
def get_exchange_rates() -> Dict[str, float]:
    """Get USD to INR and USD to AED exchange rates (cached)."""
    # Use realistic default rates (updated quarterly in demo)
    rates = {"USDINR": 83.45, "USDAED": 3.67}

    # Try to fetch live rates but don't hang if it fails
    try:
        logger.info("Attempting to fetch live exchange rates...")
        data_inr = yf.Ticker("USDINR=X")
        hist = data_inr.history(period="1d", timeout=3)
        if not hist.empty and "Close" in hist.columns:
            rate_inr = float(hist["Close"].iloc[-1])
            if rate_inr > 0:
                rates["USDINR"] = rate_inr
                logger.info(f"✅ Live USDINR: {rate_inr}")
    except Exception as e:
        logger.warning(f"Using cached USDINR rate (fetch failed): {e}")

    try:
        data_aed = yf.Ticker("USDAED=X")
        hist = data_aed.history(period="1d", timeout=3)
        if not hist.empty and "Close" in hist.columns:
            rate_aed = float(hist["Close"].iloc[-1])
            if rate_aed > 0:
                rates["USDAED"] = rate_aed
                logger.info(f"✅ Live USDAED: {rate_aed}")
    except Exception as e:
        logger.warning(f"Using cached USDAED rate (fetch failed): {e}")

    logger.info(f"Final exchange rates: {rates}")
    return rates


def validate_stock_ticker(ticker: str) -> Tuple[bool, str]:
    """Validate if stock/ETF ticker exists."""
    try:
        data = yf.Ticker(ticker)
        info = data.info
        if "regularMarketPrice" in info or "currentPrice" in info:
            return True, f"✅ Found: {info.get('longName', ticker)}"

        hist = data.history(period="5d")
        if not hist.empty:
            return True, f"✅ Ticker {ticker} found"

        return False, "Could not fetch data for this ticker"
    except Exception as e:
        logger.warning(f"Validation error for {ticker}: {e}")
        return None, f"⚠️ Connection issue. If you're sure ticker is correct, proceed anyway. Error: {str(e)[:50]}"


def validate_mf_amfi_code(amfi_code: str) -> Tuple[bool, Optional[str]]:
    """Validate if mutual fund AMFI code exists."""
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


def get_current_price(asset_type: str, ticker: str, use_demo_data: bool = True) -> Optional[float]:
    """Get current price based on asset type.
    For demo portfolio, uses mocked prices. For new user additions, fetches live."""
    if asset_type == "Cash":
        return 1.0

    # Try demo data first (fast, no API calls)
    if use_demo_data and ticker in DEMO_CURRENT_PRICES:
        logger.info(f"Using mocked price for {ticker}: ${DEMO_CURRENT_PRICES[ticker]}")
        return DEMO_CURRENT_PRICES[ticker]

    # Fall back to live data for new holdings user adds
    if asset_type == "Stock/ETF":
        return get_stock_price(ticker) or DEMO_CURRENT_PRICES.get(ticker)
    elif asset_type == "Indian Mutual Fund":
        return get_mf_nav(ticker) or DEMO_CURRENT_PRICES.get(ticker)

    return None


# ==================== CALCULATION FUNCTIONS ====================
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
    """Calculate XIRR based on purchase date and current price."""
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

        xirr = ((current_value / initial_investment) ** (365 / days_held)) - 1
        return round(xirr * 100, 2)

    except Exception as e:
        logger.warning(f"Could not calculate XIRR: {e}")
        return None


def calculate_portfolio_value() -> Tuple[pd.DataFrame, Dict[str, float], Dict[str, float]]:
    """Calculate current portfolio value with all holdings and exchange rates."""
    df = get_all_holdings()
    rates = get_exchange_rates()

    if df.empty:
        return df, {"USD": 0.0, "INR": 0.0, "AED": 0.0}, rates

    # Add current price and converted values (use mocked prices for demo portfolio)
    df["current_price_usd"] = df.apply(
        lambda row: convert_to_usd(row["buy_price"], row["currency"], rates) if row["asset_type"] == "Cash"
        else convert_to_usd(get_current_price(row["asset_type"], row["ticker"], use_demo_data=True) or row["buy_price"], row["currency"], rates),
        axis=1
    )

    df["current_value_usd"] = df["quantity"] * df["current_price_usd"]

    df["cost_value_usd"] = df.apply(
        lambda row: row["quantity"] * convert_to_usd(row["buy_price"], row["currency"], rates),
        axis=1
    )

    df["gain_loss_usd"] = df["current_value_usd"] - df["cost_value_usd"]

    # Calculate XIRR for each holding
    df["calculated_xirr"] = df.apply(
        lambda row: calculate_xirr(
            row.get("purchase_date"),
            convert_to_usd(row["buy_price"], row["currency"], rates),
            row["current_price_usd"],
            row["quantity"]
        ) if row["asset_type"] in ["Stock/ETF", "Indian Mutual Fund"] else None,
        axis=1
    )

    total_usd = df["current_value_usd"].sum()
    total_inr = total_usd * rates["USDINR"]
    total_aed = total_usd * rates["USDAED"]

    return df, {"USD": round(total_usd, 2), "INR": round(total_inr, 2), "AED": round(total_aed, 2)}, rates


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
            asset_name = st.text_input(
                "Asset Name (e.g., Apple, HDFC Bank)",
                placeholder="e.g., Apple Inc",
                key="asset_name_input"
            )
            currency = st.selectbox(
                "Currency",
                ["INR", "USD", "AED"],
                key="currency_select"
            )

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
            quantity = 1.0
            buy_price = st.number_input(
                "💰 Total Amount",
                min_value=0.01,
                value=1.0,
                step=0.01,
                help="Total cash amount you have"
            )
        else:
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
            default_class = 3 if asset_type == "Cash" else 0
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
                help="Date when you purchased this asset"
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
                    help="Extended Internal Rate of Return"
                )
                if xirr == 0.0:
                    xirr = None

        submitted = st.form_submit_button("✅ Add Asset", use_container_width=True)

        if submitted:
            if not asset_name:
                st.error("❌ Asset name is required")
            elif asset_type != "Cash" and not ticker:
                st.error("❌ Ticker/AMFI code is required")
            else:
                validation_passed = True
                needs_confirmation = False

                # Validate ticker
                if asset_type == "Stock/ETF":
                    with st.spinner(f"🔍 Validating ticker {ticker}..."):
                        is_valid, msg = validate_stock_ticker(ticker)
                        if is_valid is False:
                            st.error(f"❌ {msg}")
                            validation_passed = False
                        elif is_valid is None:
                            st.warning(f"⚠️ {msg}")
                            needs_confirmation = True
                        else:
                            st.success(msg)

                elif asset_type == "Indian Mutual Fund":
                    with st.spinner(f"🔍 Validating AMFI code {ticker}..."):
                        is_valid, fund_name = validate_mf_amfi_code(ticker)
                        if not is_valid:
                            st.warning(f"⚠️ Could not verify AMFI code '{ticker}'")
                            needs_confirmation = True
                        elif fund_name:
                            st.success(f"✅ Found: {fund_name}")

                # Show confirmation if needed
                if needs_confirmation and validation_passed:
                    st.divider()
                    confirm_col1, confirm_col2 = st.columns(2)
                    with confirm_col1:
                        if st.checkbox(f"✅ I confirm that '{ticker}' is correct"):
                            validation_passed = True
                        else:
                            validation_passed = False
                            st.info("Please verify and try again.")

                # Add holding
                if validation_passed:
                    purchase_date_str = purchase_date.isoformat() if purchase_date else None
                    if add_holding(asset_type, asset_name, ticker, quantity, buy_price, currency, geography, asset_class, purchase_date_str, xirr):
                        st.success(f"✅ Added {asset_name} successfully!")
                        st.rerun()


def render_visualizations(df: pd.DataFrame):
    """Render compact donut charts."""
    if df.empty:
        st.info("📊 Add assets to see visualizations")
        return

    st.markdown("##### 📈 Portfolio Allocation")

    col1, col2 = st.columns(2, gap="small")

    with col1:
        asset_allocation = get_asset_class_allocation(df)
        if asset_allocation:
            colors = ["#0969DA", "#3b82f6", "#60a5fa", "#93c5fd"]
            fig = go.Figure(data=[go.Pie(
                labels=list(asset_allocation.keys()),
                values=list(asset_allocation.values()),
                hole=0.4,
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
            colors = ["#059669", "#10b981", "#34d399", "#6ee7b7"]
            fig = go.Figure(data=[go.Pie(
                labels=list(geo_allocation.keys()),
                values=list(geo_allocation.values()),
                hole=0.4,
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
                st.text(str(purchase_date_val)[:10])
            else:
                st.text("—")
        with col11:
            calculated_xirr = row.get("calculated_xirr", None)
            manual_xirr = row.get("xirr", None)

            if calculated_xirr is not None:
                if manual_xirr and manual_xirr != 0:
                    st.text(f"📌 {manual_xirr:.2f}%")
                else:
                    st.text(f"📊 {calculated_xirr:.2f}%")
            elif manual_xirr and manual_xirr != 0:
                st.text(f"📌 {manual_xirr:.2f}%")
            else:
                st.text("—")
        with col12:
            if st.button("✏️", key=f"edit_btn_{holding_id}", use_container_width=True):
                st.session_state[editing_key] = not st.session_state.get(editing_key, False)
        with col13:
            if st.button("🗑️", key=f"delete_btn_{holding_id}", use_container_width=True):
                st.session_state[confirm_delete_key] = True

        # Show edit form
        if st.session_state.get(editing_key, False):
            st.info("✏️ Edit Mode")
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

                    if edit_asset_type == "Cash":
                        edit_quantity = 1.0
                        edit_buy_price = st.number_input(
                            "💰 Total Amount",
                            value=float(row["buy_price"]),
                            step=0.01,
                            key=f"edit_buy_price_{holding_id}"
                        )
                    else:
                        edit_quantity = st.number_input(
                            "Quantity / Units",
                            value=float(row["quantity"]),
                            step=0.01,
                            key=f"edit_quantity_{holding_id}"
                        )
                        edit_buy_price = st.number_input(
                            "Purchase Price Per Unit",
                            value=float(row["buy_price"]),
                            step=0.01,
                            key=f"edit_buy_price_{holding_id}"
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
                    if st.form_submit_button("💾 Save", use_container_width=True):
                        edit_purchase_date_str = edit_purchase_date.isoformat() if edit_purchase_date else None
                        if update_holding(holding_id, edit_asset_type, edit_asset_name, edit_ticker, edit_quantity, edit_buy_price, edit_currency, edit_geography, edit_asset_class, edit_purchase_date_str, edit_xirr):
                            st.success("✅ Updated")
                            st.session_state[editing_key] = False
                            st.rerun()

                with edit_submit_col2:
                    if st.form_submit_button("❌ Cancel", use_container_width=True):
                        st.session_state[editing_key] = False
                        st.rerun()

        # Show delete confirmation
        if st.session_state.get(confirm_delete_key, False):
            st.warning(f"⚠️ Delete **{row['asset_name']}**?")
            conf_col1, conf_col2 = st.columns(2, gap="small")

            with conf_col1:
                if st.button("✅ Confirm", key=f"confirm_yes_{holding_id}", use_container_width=True):
                    if delete_holding(holding_id):
                        st.success("✅ Deleted")
                        del st.session_state[confirm_delete_key]
                        st.rerun()

            with conf_col2:
                if st.button("❌ Cancel", key=f"confirm_no_{holding_id}", use_container_width=True):
                    st.session_state[confirm_delete_key] = False
                    st.rerun()


# ==================== MAIN APP ====================
def main():
    st.set_page_config(
        page_title="Wealth Manager Pro - Demo",
        page_icon="💼",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Initialize session state
    init_session_state()

    # Premium Header
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
    .demo-badge {
        display: inline-block;
        background: #FEE2E2;
        color: #991B1B;
        padding: 0.25rem 0.75rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-left: 0.5rem;
    }
    </style>
    <div class="header-title">💼 Wealth Manager Pro <span class="demo-badge">DEMO</span></div>
    <div class="header-subtitle">Portfolio Management & Net Worth Tracking (Sample Data)</div>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown("### 📚 Asset Reference Guide")
        st.markdown("""
        **Indian Stocks (NSE)**
        - HDFCBANK.NS, INFY.NS, RELIANCE.NS, TCS.NS, SBIN.NS

        **US Stocks**
        - AAPL, MSFT, GOOGL, AMZN, TSLA, VOO

        **Mutual Funds**
        - 6-digit AMFI code (e.g., 120465)

        **Settings**
        """)
        if st.button("🔄 Clear Cache & Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # Calculate portfolio
    df, totals, rates = calculate_portfolio_value()

    # Render dashboard
    render_metric_cards(totals, rates)

    # Input form
    render_input_form()

    # Visualizations
    if not df.empty:
        st.write("")
        render_visualizations(df)

    # Holdings table
    st.write("")
    render_holdings_table(df)

    # Debug Info
    with st.expander("🔍 System Info"):
        if not df.empty:
            debug_df = df[[
                "asset_name", "asset_type", "ticker", "buy_price",
                "current_price_usd", "current_value_usd"
            ]].copy()
            debug_df.columns = ["Asset", "Type", "Ticker", "Buy Price", "Current Price (USD)", "Current Value (USD)"]

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

    # Footer
    col1, col2, col3 = st.columns([1, 1, 1], gap="small")
    with col1:
        st.caption(f"🕐 {datetime.now().strftime('%H:%M:%S')}")
    with col2:
        st.caption(f"📊 {len(df)} holdings")
    with col3:
        st.caption("Session-based (Demo)")


if __name__ == "__main__":
    main()
