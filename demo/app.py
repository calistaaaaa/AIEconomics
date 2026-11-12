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

st.markdown("""
    <style>
        .stApp { 
            background-color: #ffffff !important; 
            color: #111111 !important; 
        }
        
        [data-testid="stSidebar"] {
            background-color: #f8f9fa !important;
            color: #111111 !important;
        }

        h1, h2, h3, h4, h5, h6, p, li, span, label, div, table, th, td, .stMarkdown, .stMarkdown p {
            color: #111111 !important;
        }

        div[data-testid="stMetric"] {
            background-color: #ffffff !important;
            border: 1px solid #e0e0e0 !important;
            padding: 15px !important;
            border-radius: 10px !important;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }
        div[data-testid="stMetric"] label {
            color: #555555 !important;
            font-size: 14px !important;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            color: #0066cc !important;
            font-size: 24px !important;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricDelta"] {
            color: #00875a !important;
        }

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
                fig1.update_layout(
                    yaxis_title="價格 / 指數", 
                    xaxis_title="日期", 
                    legend_title="金融標的",
                    template="plotly_white",
                    paper_bgcolor="#ffffff",
                    plot_bgcolor="#ffffff",
                    font=dict(color="#111111")
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
                template="plotly_white",
                paper_bgcolor="#ffffff",
                plot_bgcolor="#ffffff",
                font=dict(color="#111111")
            )
            st.plotly_chart(fig2, use_container_width=True)

        # ----------------------------------------------------
        # 頁面三：股票/加密貨幣技術分析與 AI 預測 (按鈕觸發 200~300 字簡要分析)
        # ----------------------------------------------------
        elif nav_choice == "🤖 股票/加密貨幣技術分析與 AI 預測":
            st.title("📈 股票 / 加密貨幣技術分析與 AI 預測")
            st.markdown("選取特定標的，檢視歷史走勢與技術指標，點擊下方按鈕即可透過 Gemini AI 產出約 200-300 字的精煉解讀。")
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

                fig = make_subplots(
                    rows=3, cols=1, 
                    shared_xaxes=True, 
                    vertical_spacing=0.08, 
                    row_heights=[0.5, 0.25, 0.25],
                    subplot_titles=(f"{selected_name} 價格與均線 (SMA 20/50)", "RSI 相對強弱指標", "MACD 動能指標")
                )

                fig.add_trace(go.Scatter(x=asset_df.index, y=asset_df['Close'], name="收盤價", line=dict(color="#0066cc")), row=1, col=1)
                fig.add_trace(go.Scatter(x=asset_df.index, y=asset_df['SMA_20'], name="SMA 20", line=dict(color="#d97706", dash="dot")), row=1, col=1)
                fig.add_trace(go.Scatter(x=asset_df.index, y=asset_df['SMA_50'], name="SMA 50", line=dict(color="#dc2626", dash="dot")), row=1, col=1)

                fig.add_trace(go.Scatter(x=asset_df.index, y=asset_df['RSI'], name="RSI", line=dict(color="#7c3aed")), row=2, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="#dc2626", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="#16a34a", row=2, col=1)

                fig.add_trace(go.Scatter(x=asset_df.index, y=asset_df['MACD'], name="MACD", line=dict(color="#16a34a")), row=3, col=1)
                fig.add_trace(go.Scatter(x=asset_df.index, y=asset_df['Signal_Line'], name="Signal", line=dict(color="#dc2626")), row=3, col=1)

                fig.update_layout(
                    height=800, 
                    template="plotly_white", 
                    paper_bgcolor="#ffffff",
                    plot_bgcolor="#ffffff",
                    font=dict(color="#111111", size=12),
                    margin=dict(l=30, r=30, t=50, b=30),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                fig.update_xaxes(showgrid=True, gridcolor="#e5e7eb")
                fig.update_yaxes(showgrid=True, gridcolor="#e5e7eb")

                st.plotly_chart(fig, use_container_width=True)

                st.write("---")

                st.subheader(f"🤖 Gemini AI 技術面預測與買賣訊號解讀 ({selected_name})")
                if st.button(f"🚀 啟動 {selected_name} AI 技術深度剖析", type="primary", use_container_width=True):
                    if not gemini_key:
                        st.warning("⚠️ 請先於左側側邊欄輸入您的 Gemini API Key。")
                    else:
                        with st.spinner("Gemini 正在產生精煉分析報告中..."):
                            try:
                                summary_text = f"""
                                標的: {selected_name} ({ticker_symbol}), 收盤價: {latest_price:.2f}, 
                                SMA 20: {asset_df['SMA_20'].iloc[-1]:.2f}, SMA 50: {asset_df['SMA_50'].iloc[-1]:.2f}, 
                                14日 RSI: {latest_rsi:.1f}, MACD: {asset_df['MACD'].iloc[-1]:.2f}
                                """
                                prompt = f"""
                                你是華爾街量化分析師。請依據以下技術數據進行分析，並嚴格限制總字數在 200 至 300 字之間，以繁體中文條列輸出：
                                {summary_text}
                                包含：1. 趨勢判定 2. 指標解讀 3. 操作建議與風險。
                                """
                                client = genai.Client(api_key=gemini_key)
                                response = client.models.generate_content(
                                    model='gemini-2.5-flash',
                                    contents=prompt,
                                )
                                st.markdown(response.text)
                            except Exception as e:
                                st.error(f"AI 分析發生錯誤: {e}")
            else:
                st.warning("無法取得該標的的歷史數據，請確認代號是否正確。")

        # ----------------------------------------------------
        # 頁面四：即時 Gemini AI 智慧分析戰情室 (按鈕觸發 200~300 字簡要分析)
        # ----------------------------------------------------
        elif nav_choice == "📰 即時 Gemini AI 智慧分析戰情室":
            st.title("🤖 即時 Gemini AI 智慧分析戰情室")
            st.markdown("結合即時 **Google News RSS** 與 **Gemini 智慧模型**，點擊下方按鈕即可產出約 200-300 字的精煉市場輿論與鷹鴿派立場報告。")
            st.write("---")

            search_kw = st.text_input(
                "🔍 自訂新聞搜尋關鍵字:", 
                value="Federal Reserve Stock Market Crypto"
            )
            max_news_count = st.slider("抓取新聞則數", min_value=3, max_value=15, value=8)
            news_titles = fetch_google_news(search_kw, max_news_count)

            col_news, col_ai = st.columns([1, 1], gap="large")

            with col_news:
                st.subheader(f"📌 即時財經新聞流 (關鍵字: `{search_kw}`)")
                if news_titles:
                    for i, title in enumerate(news_titles, 1):
                        st.markdown(f"""
                            <div class="news-card">
                                <b>#{i}</b> {title}
                            </div>
                        """, unsafe_allow_html=True)
                else:
                    st.warning("查無相關新聞標題，請嘗試更換關鍵字。")

            with col_ai:
                st.subheader("📊 Gemini AI 深度輿論量化分析")
                
                if st.button("🚀 啟動 AI 鷹鴿情緒與政策立場剖析", type="primary", use_container_width=True):
                    if not gemini_key:
                        st.warning("⚠️ 請先於左側側邊欄輸入您的 Gemini API Key。")
                    else:
                        if news_titles:
                            with st.spinner("Gemini 正在解讀新聞並統整精煉報告中..."):
                                try:
                                    news_text = "\n".join([f"- {t}" for t in news_titles])
                                    prompt = f"""
                                    你是一位頂尖的華爾街總體經濟分析師。請分析以下新聞標題，並嚴格限制總字數在 200 至 300 字之間，以繁體中文輸出精煉報告：
                                    {news_text}
                                    包含：1. 市場情緒與分數 (0-100) 2. 政策立場 (鷹/鴿/中) 3. 核心驅動因子與短評。
                                    """
                                    client = genai.Client(api_key=gemini_key)
                                    response = client.models.generate_content(
                                        model='gemini-2.5-flash',
                                        contents=prompt,
                                    )
                                    st.markdown(response.text)
                                except Exception as e:
                                    st.error(f"AI 分析時發生錯誤: {e}")
                        else:
                            st.warning("目前沒有可供分析的新聞資料。")

    except Exception as e:
        st.error(f"資料讀取失敗，請確認您的 FRED API Key 是否正確。詳細錯誤: {e}")
