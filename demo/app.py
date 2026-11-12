import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
import feedparser
from google import genai
from urllib.parse import quote

# ==========================================
# 0. 頁面全域配置
# ==========================================
st.set_page_config(
    page_title="全球金融總經與 Gemini AI 智慧戰情室", 
    page_icon="🌐", 
    layout="wide"
)

# 自訂暗色/現代化混合風格 CSS
st.markdown("""
    <style>
        .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
        .news-card { background-color: #161b22; padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #58a6ff; }
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
        "📰 即時 Gemini AI 智慧分析戰情室"
    ]
)

if st.sidebar.button("🔄 重新整理所有快取資料", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# 2. 數據抓取函式 (FRED, yfinance, RSS 新聞)
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
        "布蘭特原油": "BZ=F",
        "美元/台幣匯率": "TWD=X"
    }
    df = yf.download(list(tickers.values()), period="1y")["Close"]
    inv_tickers = {v: k for k, v in tickers.items()}
    df = df.rename(columns=inv_tickers)
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
        with st.spinner("正在連線至 FRED 與 Yahoo Finance 獲取即時數據..."):
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
            st.info("💡 提示：您可以透過左側選單切換至「全球股市與總經走勢」檢視互動圖表，或至「即時 Gemini AI 智慧分析戰情室」進行輿論情緒與鷹鴿派分析。")

        # ----------------------------------------------------
        # 頁面二：全球股市與總經走勢
        # ----------------------------------------------------
        elif nav_choice == "📈 全球股市與總經走勢":
            st.title("📈 全球股市與總體經濟趨勢分析")
            st.markdown("透過互動式圖表深度探索各大指數、美台權值股與總經指標在過去一年的表現軌跡。")
            st.write("---")

            # 上半部：股市資產比較
            st.subheader("🇺🇸🇹🇼 全球股市與金融商品走勢")
            selected_markets = st.multiselect(
                "勾選要比較的股票與標的：", 
                options=list(market_df.columns), 
                default=["S&P 500", "台灣加權指數", "輝達 (NVDA)"]
            )
            
            if selected_markets:
                fig1 = px.line(market_df, y=selected_markets, title="選定標的近一年價格走勢")
                fig1.update_layout(yaxis_title="價格 / 指數", xaxis_title="日期", legend_title="金融標的")
                st.plotly_chart(fig1, use_container_width=True)
            else:
                st.warning("請至少選擇一項金融標的以顯示圖表。")

            st.write("---")

            # 下半部：總經指標
            st.subheader("🏛️ 美國總體經濟指標走勢")
            macro_choice = st.selectbox("選擇要檢視的總體經濟指標：", macro_df.columns)
            fig2 = px.line(macro_df, y=macro_choice, title=f"近一年 {macro_choice} 歷史變動圖")
            fig2.update_layout(yaxis_title="數值", xaxis_title="日期")
            st.plotly_chart(fig2, use_container_width=True)

        # ----------------------------------------------------
        # 頁面三：即時 Gemini AI 智慧分析戰情室
        # ----------------------------------------------------
        elif nav_choice == "📰 即時 Gemini AI 智慧分析戰情室":
            st.title("🤖 即時 Gemini AI 智慧分析戰情室")
            st.markdown("結合即時 **Google News RSS** 與 **Gemini 智慧模型**，為您進行總體經濟、貨幣政策立場（鷹/鴿派）與市場情緒量化評分。")
            st.write("---")

            search_kw = st.text_input(
                "🔍 自訂新聞搜尋關鍵字:", 
                value="Federal Reserve Stock Market Inflation"
            )
            max_news_count = st.slider("抓取新聞則數", min_value=3, max_value=15, value=8)
            news_titles = fetch_google_news(search_kw, max_news_count)

            col_news, col_ai = st.columns([1, 1], gap="large")

            # 左側：即時新聞清單
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

            # 右側：Gemini AI 分析
            with col_ai:
                st.subheader("📊 Gemini AI 深度輿論量化分析")
                
                if not gemini_key:
                    st.warning("👈 請先在左側輸入您的 **Gemini API Key** 以解鎖 AI 分析戰情室功能。")
                else:
                    if st.button("🚀 啟動 AI 鷹鴿情緒與政策立場剖析", type="primary", use_container_width=True):
                        if news_titles:
                            with st.spinner("Gemini 正在解讀新聞語意與市場情緒中..."):
                                try:
                                    news_text = "\n".join([f"- {t}" for t in news_titles])
                                    prompt = f"""
                                    你是一位頂尖的華爾街總體經濟與量化分析師。請分析以下 {len(news_titles)} 條最新財經新聞標題：
                                    {news_text}

                                    請以專業繁體中文輸出結構化報告，包含以下項目：
                                    1. **整體市場情緒指數** (0 到 100 分，0 代表極度悲觀/恐慌，100 代表極度樂觀)
                                    2. **貨幣政策與股市影響立場判定** (整體偏向 鷹派 / 鴿派 / 中立)
                                    3. **關鍵總結與市場驅動因子** (簡述目前市場焦點與隱憂)
                                    4. **逐條新聞立場評分表** (請用 Markdown 表格呈現，欄位包含：[編號, 新聞標題簡述, 立場(鷹/鴿/中), 影響評分(-5至+5)])
                                    """
                                    
                                    client = genai.Client(api_key=gemini_key)
                                    response = client.models.generate_content(
                                        model='gemini-2.5-flash',
                                        contents=prompt,
                                    )
                                    
                                    st.markdown("---")
                                    st.markdown(response.text)
                                except Exception as e:
                                    st.error(f"AI 分析時發生錯誤: {e}")
                        else:
                            st.warning("目前沒有可供分析的新聞資料。")

    except Exception as e:
        st.error(f"資料讀取失敗，請確認您的 FRED API Key 是否正確。詳細錯誤: {e}")
