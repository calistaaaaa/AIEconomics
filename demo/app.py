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
# 0. 頁面全域配置
# ==========================================
st.set_page_config(
    page_title="全球金融總經、加密貨幣技術分析與 AI 智慧戰情室", 
    page_icon="🌐", 
    layout="wide"
)

# 自訂暗色/現代化混合風格 CSS（強制全域文字顏色為亮色，避免黑底黑字）
st.markdown("""
    <style>
        .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
        .news-card { background-color: #161b22; padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #58a6ff; }
        /* 確保全域文字與標題清晰 */
        .stApp { color: #e6edf3; }
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
    feed = feedparser.parse(url)
    return [entry.title for entry in feed.entries[:count]]

# ==========================================
# 3. 主頁面渲染邏輯
# ==========================================
if not fred_key:
    st.warning("⚠️ 請先於左側側邊欄輸入您的 **FRED API Key** 以啟用完整系統數據。")
else:
    try:
        with st.spinner("正在連線至 FRED 與 Yahoo Finance 獲取即時資料..."):
            macro_df = get_fred_data(fred_key)
            market_df = get_market_data()

        # ----------------------------------------------------
        # 頁面一：核心總經與市場摘要
        # ----------------------------------------------------
        if nav_choice == "📊 核心總經與市場摘要":
            st.title("🌐 全球金融、總經與 AI 輿論情緒戰情室")
            st.markdown("歡迎回來！以下為您即時掌握當前美國重要總體經濟指標與市場基準的最新狀態。")
            st.write("---")

            st.subheader("📌 美國總體經濟關鍵指標 (FRED)")
            col1, col2, col3, col4 = st.columns(4)
            
            latest_cpi = macro_df["CPI 物價指數"].dropna().iloc[-1]
            col1.metric("CPI 物價指數", f"{latest_cpi:.1f}")
            
            latest_rate = macro_df["10年期美債殖利率"].dropna().iloc[-1]
            rate_prev = macro_df["10年期美債殖利率"].dropna().iloc[-2]
            col2.metric("10年美債殖利率", f"{latest_rate:.2f}%", f"{latest_rate - rate_prev:+.2f}%")
            
            latest_unemp = macro_df["美國失業率"].dropna().iloc[-1]
            col3.metric("美國失業率", f"{latest_unemp:.1f}%")
            
            latest_fed = macro_df["聯邦基金利率"].dropna().iloc[-1]
            col4.metric("聯邦基金利率", f"{latest_fed:.2f}%")

            st.write("")
            st.info("💡 提示：您可以透過左側選單切換至「股票/加密貨幣技術分析與 AI 預測」或「即時 AI 智慧分析戰情室」。")

        # ----------------------------------------------------
        # 頁面二：全球股市與總經走勢
        # ----------------------------------------------------
        elif nav_choice == "📈 全球股市與總經走勢":
            st.title("📈 全球股市與總體經濟趨勢分析")
            st.markdown("透過互動式圖表深度探索各大指數、美台權值股與總經指標在過去一年的表現軌跡。")
            st.write("---")

            st.subheader("🇺🇸🇹🇼 全球股市與金融商品走勢")
            selected_markets = st.multiselect(
                "勾選要比較的股票與標的：", 
                options=list(market_df.columns), 
                default=["S&P 500", "台灣加權指數", "輝達 (NVDA)"]
            )
            
            if selected_markets:
                fig1 = px.line(market_df, y=selected_markets, title="選定標的近一年價格走勢")
                # 修正文字顏色，避免黑色字體看不見
                fig1.update_layout(
                    yaxis_title="價格 / 指數", 
                    xaxis_title="日期", 
                    legend_title="金融標的",
                    template="plotly_dark",
                    font=dict(color="#e6edf3")
                )
                st.plotly_chart(fig1, use_container_width=True)
            else:
                st.warning("請至少選擇一項金融標的以顯示圖表。")

            st.write("---")

            st.subheader("🏛️ 美國總體經濟指標走勢")
            macro_choice = st.selectbox("選擇要檢視的總體經濟指標：", macro_df.columns)
            fig2 = px.line(macro_df, y=macro_choice, title=f"近一年 {macro_choice} 歷史變動圖")
            fig2.update_layout(
                yaxis_title="數值", 
                xaxis_title="日期",
                template="plotly_dark",
                font=dict(color="#e6edf3")
            )
            st.plotly_chart(fig2, use_container_width=True)

        # ----------------------------------------------------
        # 頁面三：股票/加密貨幣技術分析與 AI 預測
        # ----------------------------------------------------
        elif nav_choice == "🤖 股票/加密貨幣技術分析與 AI 預測":
            st.title("📈 股票 / 加密貨幣技術分析與 AI 預測")
            st.markdown("選取特定標的，檢視歷史走勢、技術指標（SMA、RSI、MACD），並透過 Gemini AI 進行趨勢解讀與買賣訊號評估。")
            st.write("---")

            col_sel1, col_sel2 = st.columns([2, 1])
            with col_sel1:
                asset_options = {
                    "蘋果 (AAPL)": "AAPL",
                    "特斯拉 (TSLA)": "TSLA",
                    "輝達 (NVDA)": "NVDA",
                    "台積電 (2330.TW)": "2330.TW",
                    "比特幣 (BTC-USD)": "BTC-USD",
                    "以太坊 (ETH-USD)": "ETH-USD",
                    "S&P 500 指數基金 (SPY)": "SPY"
                }
                selected_name = st.selectbox("🎯 選擇分析標的：", list(asset_options.keys()))
                ticker_symbol = asset_options[selected_name]

            with col_sel2:
                period_choice = st.selectbox("⏱️ 選擇歷史區間：", ["3mo", "6mo", "1y", "2y"], index=1)

            with st.spinner(f"正在載入 {selected_name} 的技術數據中..."):
                asset_df = get_single_asset_data(ticker_symbol, period=period_choice)
                asset_df = calculate_technical_indicators(asset_df)

            if not asset_df.empty:
                latest_price = asset_df['Close'].iloc[-1]
                prev_price = asset_df['Close'].iloc[-2]
                price_change = latest_price - prev_price
                price_pct = (price_change / prev_price) * 100
                latest_rsi = asset_df['RSI'].iloc[-1]

                mcol1, mcol2, mcol3 = st.columns(3)
                mcol1.metric("最新收盤價", f"{latest_price:.2f}", f"{price_change:+.2f} ({price_pct:+.2f}%)")
                mcol2.metric("14日 RSI 強弱指標", f"{latest_rsi:.1f}", "超買 > 70 | 超賣 < 30" if latest_rsi else "")
                mcol3.metric("資料筆數", f"{len(asset_df)} 交易日")

                st.write("")

                # 建立 Plotly 子圖表
                fig = make_subplots(
                    rows=3, cols=1, 
                    shared_xaxes=True, 
                    vertical_spacing=0.08, 
                    row_heights=[0.5, 0.25, 0.25],
                    subplot_titles=(f"{selected_name} 價格與均線 (SMA 20/50)", "RSI 相對強弱指標", "MACD 動能指標")
                )

                # 1. 價格與 SMA
                fig.add_trace(go.Scatter(x=asset_df.index, y=asset_df['Close'], name="收盤價", line=dict(color="#58a6ff")), row=1, col=1)
                fig.add_trace(go.Scatter(x=asset_df.index, y=asset_df['SMA_20'], name="SMA 20", line=dict(color="#ffa657", dash="dot")), row=1, col=1)
                fig.add_trace(go.Scatter(x=asset_df.index, y=asset_df['SMA_50'], name="SMA 50", line=dict(color="#ff7b72", dash="dot")), row=1, col=1)

                # 2. RSI
                fig.add_trace(go.Scatter(x=asset_df.index, y=asset_df['RSI'], name="RSI", line=dict(color="#bc8cff")), row=2, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="#ff7b72", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="#3fb950", row=2, col=1)

                # 3. MACD
                fig.add_trace(go.Scatter(x=asset_df.index, y=asset_df['MACD'], name="MACD", line=dict(color="#3fb950")), row=3, col=1)
                fig.add_trace(go.Scatter(x=asset_df.index, y=asset_df['Signal_Line'], name="Signal", line=dict(color="#f85149")), row=3, col=1)

                # 強制使用 plotly_dark 模板並設定字體顏色為亮色，彻底解決黑字看不見的問題
                fig.update_layout(
                    height=800, 
                    template="plotly_dark", 
                    font=dict(color="#e6edf3", size=12),
                    margin=dict(l=30, r=30, t=50, b=30),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                # 更新所有子圖表的座標軸文字顏色
                fig.update_xaxes(showgrid=True, gridcolor="#30363d")
                fig.update_yaxes(showgrid=True, gridcolor="#30363d")

                st.plotly_chart(fig, use_container_width=True)

                st.write("---")

                # Gemini AI 技術預測與買賣訊號解讀
                st.subheader(f"🤖 Gemini AI 技術面預測與買賣訊號解讀 ({selected_name})")
                if not gemini_key:
                    st.warning("👈 請先在左側輸入您的 **Gemini API Key** 以解鎖 AI 技術面預測功能。")
                else:
                    if st.button(f"🚀 啟動 {selected_name} AI 技術深度剖析", type="primary", use_container_width=True):
                        with st.spinner("Gemini 量化分析師正在解讀圖表與技術指標中..."):
                            try:
                                summary_text = f"""
                                標的名稱: {selected_name} ({ticker_symbol})
                                最新收盤價: {latest_price:.2f}
                                SMA 20: {asset_df['SMA_20'].iloc[-1]:.2f}
                                SMA 50: {asset_df['SMA_50'].iloc[-1]:.2f}
                                14日 RSI: {latest_rsi:.1f}
                                MACD: {asset_df['MACD'].iloc[-1]:.2f}, Signal: {asset_df['Signal_Line'].iloc[-1]:.2f}
                                """
                                
                                prompt = f"""
                                你是一位專業的華爾街量化技術分析師與加密貨幣/股票交易專家。請根據以下技術指標數據進行深度解讀：
                                {summary_text}

                                請以
