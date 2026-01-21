import yfinance as yf
import pandas as pd
import concurrent.futures
from datetime import datetime
import google.generativeai as genai
import os

# ===============================
# 1️⃣ Gemini 설정 (로그 출력 절대 없음)
# ===============================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")

genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-2.5-flash"

model = genai.GenerativeModel(
    MODEL_NAME,
    generation_config={
        "temperature": 0.4,
        "top_p": 0.9,
        "max_output_tokens": 300
    }
)

# ===============================
# 2️⃣ 종목 섹터 (유지)
# ===============================

SECTORS = {
    "AI & Big Tech": [
        "NVDA","MSFT","GOOGL","AMZN","META","AAPL","AVGO","AMD","INTC","QCOM",
        "IBM","ORCL","CSCO","ADBE","CRM","NOW","PLTR","SNOW","DDOG","MDB","NET",
        "SMCI","ARM","PATH","AI","SOUN","BBAI","MU","LRCX","AMAT","ADI","ASML","TSM"
    ],
    "Bio & Pharma": [
        "LLY","NVO","AMGN","PFE","GILD","BMY","JNJ","ABBV","MRK","BIIB","REGN","VRTX",
        "MRNA","BNTX","NVS","AZN","SNY","ALNY","SRPT","BMRN","INCY","UTHR","GERN",
        "CRSP","EDIT","NTLA","BEAM","AXSM"
    ],
    "Financials & Energy": [
        "JPM","BAC","WFC","C","GS","MS","COF","AXP","V","MA",
        "XOM","CVX","COP","SLB","EOG","MPC","OXY","PSX","VLO","HAL",
        "BKR","FANG","APA","CTRA","WMB","KMI","OKE","TRGP","LNG","EQT"
    ]
}

# ===============================
# 3️⃣ Gemini 분석 (완전 무로그)
# ===============================

def analyze_with_gemini(ticker, readiness, price, vol_ratio, obv_status):
    try:
        prompt = f"""
당신은 월스트리트 출신 퀀트 분석가입니다.

종목: {ticker}
현재가: ${price:.2f}
Readiness 점수: {readiness:.1f}%
거래량: 평균 대비 {vol_ratio:.1f}배
OBV 상태: {obv_status}

요청:
기술적 관점에서 왜 지금이 매수 타이밍인지
한국어로 3문장 이내로 간결하게 설명하세요.
"""
        response = model.generate_content(prompt)

        if response and response.text:
            return response.text.strip()
        else:
            return "AI 분석 결과 없음"

    except Exception:
        # ❗❗❗ 절대 에러 출력/반환 금지
        return "AI 분석 일시 중단"

# ===============================
# 4️⃣ 스캔 로직
# ===============================

def scan_logic(ticker):
    try:
        df = yf.Ticker(ticker).history(period="1y", timeout=15)
        if df is None or df.empty or len(df) < 200:
            return None

        close = df["Close"]
        volume = df["Volume"]

        # OBV
        obv = [0]
        for i in range(1, len(df)):
            if close.iloc[i] > close.iloc[i-1]:
                obv.append(obv[-1] + volume.iloc[i])
            elif close.iloc[i] < close.iloc[i-1]:
                obv.append(obv[-1] - volume.iloc[i])
            else:
                obv.append(obv[-1])

        df["OBV"] = obv

        sma20 = close.rolling(20).mean()
        sma200 = close.rolling(200).mean()
        vol_ma = volume.rolling(20).mean()

        highest_22 = close.rolling(22).max()
        wvf = ((highest_22 - df["Low"]) / highest_22) * 100
        wvf_limit = wvf.rolling(50).mean() + 2.1 * wvf.rolling(50).std()

        obv_score = 15 if df["OBV"].iloc[-1] > pd.Series(obv).rolling(20).mean().iloc[-1] else 0

        readiness = (
            (30 if df["Low"].iloc[-1] <= sma20.iloc[-1] * 1.04 else 0) +
            (30 if close.iloc[-1] > sma200.iloc[-1] else 0) +
            min((wvf.iloc[-1] / wvf_limit.iloc[-1]) * 25, 25) +
            obv_score
        )

        vol_ratio = volume.iloc[-1] / vol_ma.iloc[-1] if vol_ma.iloc[-1] else 0

        if readiness >= 90 and vol_ratio > 1.3:
            obv_status = "상승(Bullish)" if obv_score > 0 else "중립"
            ai_text = analyze_with_gemini(
                ticker, readiness, close.iloc[-1], vol_ratio, obv_status
            )

            return (
                f"[{ticker}] Readiness {readiness:.1f}% | Price ${close.iloc[-1]:.2f}\n"
                f"🤖 AI 분석: {ai_text}\n"
            )

    except Exception:
        return None

    return None

# ===============================
# 5️⃣ 실행부
# ===============================

if __name__ == "__main__":
    all_tickers = list(set(t for sector in SECTORS.values() for t in sector))

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(scan_logic, all_tickers))

    signals = [r for r in results if r]

    with open("result.txt", "w", encoding="utf-8") as f:
        f.write(f"=== Gemini AI 주식 분석 리포트 ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===\n\n")

        if signals:
            for s in signals:
                f.write(s + "-" * 60 + "\n")
        else:
            f.write("오늘 포착된 매수 신호 종목이 없습니다.\n")
