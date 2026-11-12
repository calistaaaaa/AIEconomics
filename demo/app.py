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
# 0. 頁面全域配置與暗色主題 CSS 修復
# ==========================================
st.set_page_config(
    page_title="全球金融總經、加密貨幣技術分析與 AI 智慧戰情室", 
    page_icon="🌐", 
    layout="wide"
)

# 強制統一暗色科技風主題與高亮文字，徹底解決「黑黑一塊、字看不見」的問題
st.markdown("""
    <style>
        /* 全域背景與基礎字體顏色 */
        .stApp { 
            background-color: #0e1117 !important; 
            color: #e6edf3 !important; 
        }
        
        /* 修復第一頁與第三頁的指標卡片 (stMetric) */
        div[data-testid="stMetric"] {
            background-color: #161b22 !important;
            border: 1px solid #30363d !important;
            padding: 15px !important;
            border-radius: 10px !important;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }
        div[data-testid="stMetric"] label {
            color: #8b949e !important;
            font-size: 14px !important;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            color: #58a6ff !important;
            font-size: 24px !important;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricDelta"] {
            color: #3fb950 !important;
        }

        /* 修復第四頁的新聞條目卡片 (news-card) */
        .news-card { 
            background-color: #161b22 !important; 
            color: #e6edf3 !important; 
            padding: 14px 16px !important; 
            border-radius: 8px !important; 
            margin-bottom: 10px !important; 
            border: 1px solid #30363d !important;
            border-left: 4px solid #58a6ff !important; 
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            line-height: 1.5;
        }
        .news-card b {
            color: #58a6ff !important;
            margin-right: 6px;
        }

        /* 確保所有 Markdown 標題與一般文字皆為亮色 */
        h1, h2, h3, h4, p, li, span {
            color: #e6edf3;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 側邊欄控制台與金鑰設定
# ==========================================
st.sidebar.title("⚙️ 戰情室控制台")
st.sidebar.markdown("---")

st.sidebar.subheader("🔑 系統金鑰設定")
# 1.1 檢查 FRED API Key
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
    st.sidebar.success("已自動載入 FRED API Key")
else:
    fred_key = st.sidebar.text_input("輸入 FRED API Key:", type="password")

# 1.2 檢查 Gemini API Key
gemini_key = None
if "GEMINI_API_KEY" in st.secrets:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    st.sidebar.success("已自動載入 Gemini API Key")
else:
    gemini_input = st.sidebar.text_input("輸入 Gemini API Key:", type="password")
    if gemini_input:
        gemini_key = gemini_input

st.sidebar.markdown("---")

# 導覽列選擇
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
        "1
