import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
import feedparser
from google import genai
from urllib.parse import quote  # 解決 URL 空白字元轉碼問題

# ==========================================
# 1. 頁面配置與側邊欄金鑰設定
# ==========================================
st.set_page_config(page_title="全球股市、總經與 AI 鷹鴿情緒儀表板", layout="wide")
st.title("🌐 全球股票、總體經濟與 AI 輿論情緒即時儀表板")

st.sidebar.header("⚙️ 系統設定與金鑰")

# 1.1 檢查 FRED API Key
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
    st.sidebar.success("已自動讀取 FRED API Key！")
else:
    fred_key = st.sidebar.text_input("請輸入 FRED API Key:", type="password")

# 1.2 檢查 Gemini API Key (NLP 情緒分析用)
gemini_key = None
if "GEMINI_API_KEY" in st.secrets:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    st.sidebar.success("已自動讀取 Gemini API Key！")
else:
    gemini_input = st.sidebar.text_input("請輸入 Gemini API Key:", type="password")
    if gemini_input:
        gemini_key = gemini_input

if st.sidebar.button("🔄 手動刷新所有快取數據"):
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
    # 擴充股票與金融標的
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
    # 下載最近一年數據
    df = yf.download(list(tickers.values()), period="1y")["Close"]
    # 針對 yfinance 多欄位回傳進行欄位名稱反轉對應
    inv_tickers = {v: k for k, v in tickers.items()}
    df = df.rename(columns=inv_tickers)
    return df

@st.cache_data(ttl=1800)
def fetch_google_news(keyword="Federal Reserve Stock Market Inflation"):
    safe_keyword = quote(keyword)
    url = f"https://news.google.com/rss/search?q={safe_keyword}&hl=en-US"
    feed = feedparser.parse(url)
    return [entry.title for entry in feed.entries[:8]]

# ==========================================
# 3. 主頁面渲染邏輯
# ==========================================
if fred_key:
    try:
        with st.spinner("正在載入全球總經與股市即時數據..."):
            macro_df = get_fred_data(fred_key)
            market_df = get_market_data()

        # 第一區塊：核心總經與市場 KPI 卡片
        st.subheader("📊 關鍵總經與市場指標摘要")
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

        st.write("---")

        # 第二區塊：分頁儀表板（股票、總經、AI 情緒分析）
        tab1, tab2, tab3 = st.tabs([
            "📈 全球股市與金融走勢", 
            "🏛️ 總體經濟趨勢 (FRED)", 
            "📰 即時財經新聞與 AI 鷹鴿情緒分析"
        ])
        
        # 頁籤 1: 股票與金融市場
        with tab1:
            st.subheader("📈 股票與主要資產走勢分析")
            selected_markets = st.multiselect(
                "選擇要比較的股票與金融標的（可複選）：", 
                options=list(market_df.columns), 
                default=["S&P 500", "台灣加權指數", "輝達 (NVDA)"]
            )
            
            if selected_markets:
                # 標準化正規化檢視或直接數值呈現
                fig1 = px.line(market_df, y=selected_markets, title="選定資產近一年價格走勢圖")
                fig1.update_layout(yaxis_title="價格 / 指數", xaxis_title="日期")
                st.plotly_chart(fig1, use_container_width=True)
            else:
                st.info("請至少選擇一個標的進行圖表顯示。")
              
        # 頁籤 2: 總體經濟
        with tab2:
            st.subheader("🏛️ 美國總體經濟指標深度觀察")
            macro_choice = st.selectbox("選擇總體經濟指標：", macro_df.columns)
            fig2 = px.line(macro_df, y=macro_choice, title=f"{macro_choice} 近一年走勢")
            st.plotly_chart(fig2, use_container_width=True)

        # 頁籤 3: NLP 市場新聞與鷹鴿情緒分析
        with tab3:
            st.subheader("📰 即時財經新聞與 Gemini AI 鷹鴿派輿論分析")
            
            search_kw = st.text_input(
                "🔍 輸入新聞關鍵字 (預設: Federal Reserve Stock Market):", 
                value="Federal Reserve Stock Market"
            )
            news_titles = fetch_google_news(search_kw)

            nlp_col1, nlp_col2 = st.columns([1, 1])

            with nlp_col1:
                st.markdown("### 📌 最新財經新聞標題 (Google RSS)")
                if news_titles:
                    for i, title in enumerate(news_titles, 1):
                        st.write(f"**{i}.** {title}")
                else:
                    st.warning("查無相關新聞標題，請嘗試更換關鍵字。")

            with nlp_col2:
                st.markdown("### 🤖 Gemini AI 市場情緒與政策立場判讀")
                if gemini_key:
                    if st.button("🚀 開始執行 AI 情感與鷹鴿分析", type="primary"):
                        if news_titles:
                            with st.spinner("Gemini 正在深度剖析文本立場與市場情緒中..."):
                                try:
                                    news_text = "\n".join([f"- {t}" for t in news_titles])
                                    prompt = f"""
                                    你是一位頂尖的華爾街總體經濟與量化分析師。請分析以下 8 條最新財經新聞標題：
                                    {news_text}

                                    請以繁體中文輸出結構化報告，包含以下內容：
                                    1. **整體市場情緒指數** (0 到 100 分，0 代表極度悲觀/恐慌，100 代表極度樂觀)
                                    2. **貨幣政策與股市影響立場判定** (整體偏向 鷹派 / 鴿派 / 中立)
                                    3. **關鍵總結與驅動因子** (簡述目前市場擔憂或受惠焦點，例如通膨、降息預期或科技股財報)
                                    4. **逐條新聞立場評分表** (請用 Markdown 表格呈現，欄位包含：[編號, 新聞標題簡述, 立場(鷹/鴿/中), 影響評分(-5至+5)])
                                    """
                                    
                                    # 初始化新版 Google GenAI Client
                                    client = genai.Client(api_key=gemini_key)
                                    response = client.models.generate_content(
                                        model='gemini-3.8-flash',
                                        contents=prompt,
                                    )
                                    st.markdown(response.text)
                                except Exception as e:
                                    st.error(f"AI 分析時發生錯誤: {e}")
                        else:
                            st.warning("尚無新聞數據可供分析。")
                else:
                    st.warning("👈 請在左側輸入您的 Gemini API Key 以啟用 AI 文本情緒分析功能。")

    except Exception as e:
        st.error(f"數據讀取失敗，請確認 FRED API Key 是否正確。錯誤訊息: {e}")
else:
    st.info("👈 請在側邊欄輸入您的 FRED API Key 以解鎖完整儀表板功能。")
