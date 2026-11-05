import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred

# 🛡️ 安全匯入 google-genai，避免因未安裝套件而導致整個 App 啟動失敗
try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

# 頁面基本配置
st.set_page_config(page_title="總體經濟與金融即時儀表板", layout="wide")
st.title("🌐 全球總體經濟與金融指標即時儀表板")

# 側邊欄：輸入 API Key 與刷新控制
st.sidebar.header("⚙️ 設定與金鑰")

# 1. FRED API Key 設定
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
    st.sidebar.success("已自動讀取 FRED API Key！")
else:
    fred_key = st.sidebar.text_input("請輸入你的 FRED API Key:", type="password")

# 2. Gemini API Key 設定
if "GEMINI_API_KEY" in st.secrets:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    st.sidebar.success("已自動讀取 Gemini API Key！")
else:
    gemini_key = st.sidebar.text_input("請輸入你的 Gemini API Key:", type="password", key="gemini_input")

if st.sidebar.button("手動刷新數據"):
    st.cache_data.clear()

# 1. 抓取 FRED 數據 (設快取 1 小時)
@st.cache_data(ttl=3600)
def get_fred_data(api_key):
    fred = Fred(api_key=api_key)
    data = {
        "CPI 物價指數": fred.get_series("CPIAUCSL"),
        "10年期美債殖利率": fred.get_series("DGS10"),
        "2年期美債殖利率": fred.get_series("DGS2"),
        "美國失業率": fred.get_series("UNRATE"),
        "聯邦基金利率": fred.get_series("FEDFUNDS"),
        "日本10年期國債殖利率": fred.get_series("IRLTLT01JPM156N")
    }
    df = pd.DataFrame(data).ffill().tail(365)
    
    # 計算 10 年期減去 2 年期美債殖利率利差 (10Y - 2Y)
    df["美債殖利率利差 (10Y-2Y)"] = df["10年期美債殖利率"] - df["2年期美債殖利率"]
    return df

# 2. 抓取 Market 數據 (設快取 10 分鐘)
@st.cache_data(ttl=600)
def get_market_data():
    tickers = {
        "S&P 500": "^GSPC",
        "台灣加權指數": "^TWII",
        "布蘭特原油": "BZ=F",
        "美元/台幣匯率": "TWD=X",
        "黃金現貨價格": "GC=F"
    }
    df = yf.download(list(tickers.values()), period="1y")["Close"]
    df.rename(columns={v: k for k, v in tickers.items()}, inplace=True)
    return df

# 頁面渲染邏輯
if fred_key:
    try:
        macro_df = get_fred_data(fred_key)
        market_df = get_market_data()

        # 取得最新數值
        latest_spread = macro_df["美債殖利率利差 (10Y-2Y)"].dropna().iloc[-1]
        spread_prev = macro_df["美債殖利率利差 (10Y-2Y)"].dropna().iloc[-2]

        # 檢查並顯示美債利差警示燈號
        st.subheader("🚨 關鍵總體經濟指標與景氣警示")
        
        if latest_spread < 0:
            st.error(f"⚠️ **警示：美國 10 年期與 2 年期美債殖利率出現倒掛！當前利差為 {latest_spread:+.2f}%（前一日：{spread_prev:+.2f}%）。歷史經驗顯示這通常是經濟衰退的重要領先指標。**")
        else:
            st.success(f"✅ 美國 10Y-2Y 美債利差正常：{latest_spread:+.2f}%（大於 0，未倒掛）")

        # 第一區塊：核心 KPI 卡片 (6欄)
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            latest_cpi = macro_df["CPI 物價指數"].dropna().iloc[-1]
            st.metric("CPI 物價指數", f"{latest_cpi:.1f}")
            
        with col2:
            latest_rate = macro_df["10年期美債殖利率"].dropna().iloc[-1]
            rate_prev = macro_df["10年期美債殖利率"].dropna().iloc[-2]
            st.metric("10年美債殖利率", f"{latest_rate:.2f}%", f"{latest_rate - rate_prev:+.2f}%")
            
        with col3:
            st.metric("10Y-2Y 美債利差", f"{latest_spread:.2f}%", f"{latest_spread - spread_prev:+.2f}%")
            
        with col4:
            latest_unemp = macro_df["美國失業率"].dropna().iloc[-1]
            st.metric("美國失業率", f"{latest_unemp:.1f}%")
            
        with col5:
            latest_jp = macro_df["日本10年期國債殖利率"].dropna().iloc[-1]
            st.metric("日本10年國債", f"{latest_jp:.2f}%")

        with col6:
            latest_gold = market_df["黃金現貨價格"].dropna().iloc[-1]
            gold_prev = market_df["黃金現貨價格"].dropna().iloc[-2]
            st.metric("黃金現貨價格", f"${latest_gold:.1f}", f"{latest_gold - gold_prev:+.1f}")

        # 第二區塊：互動式圖表
        st.write("---")
        st.subheader("📈 市場走勢與總體指標折線圖")
        
        tab1, tab2 = st.tabs(["金融市場走勢 (yfinance)", "總體經濟趨勢 (FRED)"])
        
        with tab1:
            market_choice = st.selectbox("選擇金融市場標的：", market_df.columns, key="market_select")
            fig1 = px.line(market_df, y=market_choice, title=f"{market_choice} 近一年走勢")
            st.plotly_chart(fig1, use_container_width=True)
            
        with tab2:
            macro_choice = st.selectbox("選擇總體經濟指標：", macro_df.columns, key="macro_select")
            fig2 = px.line(macro_df, y=macro_choice, title=f"{macro_choice} 近一年走勢")
            
            # 若選到了利差，加上 0 軸參考線
            if macro_choice == "美債殖利率利差 (10Y-2Y)":
                fig2.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="倒掛分界線 (0%)")
                
            st.plotly_chart(fig2, use_container_width=True)

        # 第三區塊：AI 智能總體經濟摘要生成
        st.write("---")
        st.subheader("🤖 AI 智能總體經濟摘要")
        
        if st.button("產生 AI 總體經濟摘要"):
            if not HAS_GENAI:
                st.error("⚠️ 系統尚未安裝 `google-genai` 套件，請確認 requirements.txt 中已加入 `google-genai`！")
            elif not gemini_key:
                st.warning("⚠️ 請先在側邊欄輸入您的 Gemini API Key，或設定至 Streamlit Secrets 中！")
            else:
                with st.spinner("AI 正在分析當前數據並撰寫總結短評..."):
                    try:
                        client = genai.Client(api_key=gemini_key)
                        latest_fed = macro_df["聯邦基金利率"].dropna().iloc[-1]
                        latest_2y = macro_df["2年期美債殖利率"].dropna().iloc[-1]
                        
                        prompt = f"""
                        你是一位專業的總體經濟學家與金融分析師。請根據以下最新抓取的即時總體經濟與市場數據，撰寫一份大約 200 字的專業總體經濟短評（使用繁體中文）：
                        - CPI 物價指數: {latest_cpi:.1f}
                        - 10年期美債殖利率: {latest_rate:.2f}%
                        - 2年期美債殖利率: {latest_2y:.2f}%
                        - 10Y-2Y 殖利率利差: {latest_spread:.2f}% (若小於 0 代表倒掛)
                        - 美國失業率: {latest_unemp:.1f}%
                        - 聯邦基金利率: {latest_fed:.2f}%
                        - 日本 10 年期國債殖利率: {latest_jp:.2f}%
                        - 黃金現貨價格: ${latest_gold:.1f}
                        
                        請分析當前的通膨、利率環境、潛在的經濟衰退風險（如美債倒掛情況）以及避險資產（如黃金）的市場表現，語氣需專業、客觀且具備宏觀洞察力。
                        """
                        
                        # 自動備援模型機制
                        models_to_try = ["gemini-2.5-flash", "gemini-3.8-flash"]
                        response = None
                        last_error = None
                        
                        for model_name in models_to_try:
                            try:
                                response = client.models.generate_content(
                                    model=model_name,
                                    contents=prompt,
                                )
                                break
                            except Exception as err:
                                last_error = err
                                continue
                        
                        if response:
                            st.success("✅ AI 總體經濟短評生成完畢：")
                            st.info(response.text)
                        else:
                            raise last_error
                            
                    except Exception as e:
                        st.error(f"AI 摘要生成失敗（可能為模型名稱錯誤或 API 額度限制）。錯誤訊息: {e}")

    except Exception as e:
        st.error(f"數據讀取失敗，請確認 FRED API Key 是否正確。錯誤訊息: {e}")
else:
    st.info("👈 請在左側輸入您的 FRED API Key 以開啟儀表板。")
