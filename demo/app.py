import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
import feedparser
import google.generativeai as genai
from urllib.parse import quote  # 解決搜尋關鍵字包含空白字元導致的 URL 錯誤

st.set_page_config(page_title="總體經濟、金融與 NLP 市場情緒儀表板", layout="wide")
st.title("🌐 總體經濟、金融指標與 AI 輿論情緒即時儀表板")

# 1. 側邊欄：安全讀取 Secrets 金鑰
st.sidebar.header("⚙️ 設定與金鑰")
fred_key = st.secrets["FRED_API_KEY"] if "FRED_API_KEY" in st.secrets else st.sidebar.text_input("請輸入 FRED API Key:", type="password")

gemini_key = None
if "GEMINI_API_KEY" in st.secrets:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=gemini_key)
else:
    gemini_input = st.sidebar.text_input("請輸入 Gemini API Key:", type="password")
    if gemini_input:
        gemini_key = gemini_input
        genai.configure(api_key=gemini_key)

# 2. RSS 新聞抓取函式 (支援中英文關鍵字與空白轉碼)
@st.cache_data(ttl=1800)
def fetch_google_news(keyword="Federal Reserve Inflation"):
    safe_keyword = quote(keyword)
    url = f"https://news.google.com/rss/search?q={safe_keyword}&hl=en-US"
    feed = feedparser.parse(url)
    return [entry.title for entry in feed.entries[:8]]

# 3. NLP 市場新聞情緒分析介面設計範例
st.subheader("📰 即時財經新聞與 LLM 鷹鴿派情緒分析")
col_kw, col_role = st.columns([1, 1])
with col_kw:
    search_kw = st.text_input("🔍 輸入關注關鍵字 (例: Federal Reserve Inflation, TSMC):", value="Federal Reserve Inflation")
with col_role:
    analyst_role = st.selectbox("🎭 選擇 AI 分析師視角:", ["專業總體經濟分析師", "華爾街股票投資分析師", "風險控管經理人"])

custom_prompt = st.text_input("✍️ 自訂額外分析指令 (選填):", placeholder="例如：請特別評估對台灣科技股與匯率的潛在衝擊...")

news_titles = fetch_google_news(search_kw)
c1, c2 = st.columns([1, 1])

with c1:
    st.markdown("### 📌 最新相關新聞標題 (RSS)")
    for i, title in enumerate(news_titles, 1):
        st.write(f"**{i}.** {title}")

with c2:
    st.markdown("### 🤖 Gemini AI 情緒評分與報告")
    if gemini_key and st.button("🚀 開始分析市場情緒", type="primary"):
        with st.spinner("AI 正在閱讀新聞並進行鷹鴿派與情緒評估..."):
            news_text = "\n".join([f"- {t}" for t in news_titles])
            prompt = f"你是一位【{analyst_role}】。請針對以下 8 條關於「{search_kw}」的新聞標題進行剖析：\n{news_text}\n\n" \
                     f"額外分析要求：{custom_prompt if custom_prompt else '無'}\n" \
                     f"請以繁體中文輸出結構化報告：\n" \
                     f"1. **整體市場情緒分數**（0~100分，並說明多空/鷹鴿含義）\n" \
                     f"2. **政策或市場立場判定**（鷹派 / 鴿派 / 樂觀 / 悲觀）\n" \
                     f"3. **逐條新聞情緒評分與簡評**（以 Markdown 表格呈現）"
            
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt)
            st.markdown(response.text)
