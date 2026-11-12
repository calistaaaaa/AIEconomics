import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from fredapi import Fred
import feedparser
from google import genai
from urllib.parse import quote

# ==========================================
# 0. 頁面全域配置與「白底黑字」Light Mode CSS
# ==========================================
st.set_page_config(
    page_title="全球金融總經、加密貨幣技術分析與 AI 智慧戰情室", 
    page_icon="🌐", 
    layout="wide"
)

# 強制設定全域背景為白色、字體為黑色，打造乾淨明亮的金融戰情室風格
st.markdown("""
    <style>
        /* 全域背景白、字體黑 */
        .stApp { 
            background-color: #ffffff !important; 
            color: #111111 !important; 
        }
        
        /* 側邊欄背景改為淺灰白，字體深色 */
        [data-testid="stSidebar"] {
            background-color: #f8f9fa !important;
            color: #111111 !important;
        }

        /* 標題與文字強制深色 */
        h1, h2, h3, h4, p, li, span, label {
            color: #111111 !important;
        }

        /* 第一頁四個總經指標框框 (stMetric)：改為白底、黑字、精緻灰邊框 */
        div[data-testid="stMetric"] {
            background-color: #ffffff !important;
            border: 1px solid #e0e0e0 !important;
            padding: 15px !important;
            border-radius: 10px !important;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }
        div[data-testid="stMetric"] label {
            color: #555555 !important; /* 標題用深灰色 */
            font-size: 14px !important;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            color: #0066cc !important; /* 數值用專業藍色 */
            font-size: 24px !important;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricDelta"] {
            color: #00875a !important; /* 漲跌幅用綠色 */
        }

        /* 第四頁新聞卡片 (news-card)：白底、黑字、左側藍邊 */
        .news-card { 
            background-color: #fdfdfd !important; 
            color: #111111 !important; 
            padding: 14px 16px !important; 
            border-radius: 8px !important; 
            margin-bottom: 10px !important; 
            border: 1px solid #e0e0e0 !important;
            border-left: 4px solid #0066cc !important; 
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            line-height: 1.5;
        }
        .news-card b {
            color: #0066cc !important;
            margin-right: 6px;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 側邊欄控制台與金鑰設定
# ==========================================
st.sidebar.title("⚙️ 戰情室控制台")
st.sidebar.markdown("---")

st.sidebar.subheader("🔑 系統金鑰設定")
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
    st.sidebar.success("已自動載入 FRED API Key")
else:
    fred_key = st.sidebar.text_input("輸入 FRED API Key:", type="password")

gemini_key = None
if "GEMINI_API_KEY" in st.secrets:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    st.sidebar.success("已自動載入 Gemini API Key")
else:
    gemini_input = st.sidebar.text_input("輸入 Gemini API Key:", type="password")
    if gemini_input:
        gemini_key = gemini_input

st.sidebar.markdown("---")

nav_choice = st.sidebar.radio(
    "📂 功能導覽",
    [
        "📊 核心總經與市場摘要", 
        "📈 全球股市與總經走勢", 
        "🤖 股票/加密貨幣技術分析與 AI 預測",
        "📰 即時 Gemini AI 智慧分析戰情室"
    ]
)

if st.sidebar.button("🔄 重新整理所有快取資料", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# 2. 數據抓取與技術指標計算函式
# ==========================================
@st.cache_data(ttl=3600)
def get_fred_data(api_key):
    fred = Fred(api_key=api_key)
    data = {
        "CPI 物價指數": fred.get_series("CPIAUCSL"),
        "10年期美債殖利率": fred.get_series("DGS10"),
        "美國失業率": fred.get_series("UNRATE"),
        "聯邦基金利率": fred.get_series("FEDFUNDS")
    }
    df = pd.DataFrame(data).ffill().tail(365)
    return df

@st.cache_data(ttl=600)
def get_market_data():
    tickers = {
        "S&P 500": "^GSPC",
        "Nasdaq 100": "^NDX",
        "台灣加權指數": "^TWII",
        "台積電 (2330.TW)": "2330.TW",
        "輝達 (NVDA)": "NVDA",
        "蘋果 (AAPL)": "AAPL",
        "特斯拉 (TSLA)": "TSLA",
        "比特幣 (BTC-USD)": "BTC-USD",
        "以太坊 (ETH-USD)": "ETH-USD",
        "布蘭特原油": "BZ=F",
        "美元/台幣匯率": "TWD=X"
    }
    df = yf.download(list(tickers.values()), period="1y")["Close"]
    inv_tickers = {v: k for k, v in tickers.items()}
    df = df.rename(columns=inv_tickers)
    return df

@st.cache_data(ttl=300)
def get_single_asset_data(ticker, period="6mo"):
    df = yf.download(ticker, period=period)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def calculate_technical_indicators(df):
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    return df

@st.cache_data(ttl=1800)
def fetch_google_news(keyword, count=8):
    safe_keyword = quote(keyword)
    url = f"https://news.google.com/rss/search?q={safe_keyword}&hl=en-US"
    feed
