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
    "1. AI & Big Tech": [
        "NVDA", "MSFT", "AAPL", "GOOGL", "AMZN", "META", "AVGO", "ORCL",
        "IBM", "INTC", "QCOM", "AMD", "CSCO", "DELL", "HPQ", "SMCI"
    ],

    "2. Semiconductors": [
        "NVDA", "TSM", "AVGO", "AMD", "ASML", "AMAT", "LRCX", "MU",
        "ADI", "TXN", "QCOM", "INTC", "KLAC", "MRVL", "NXPI", "ON"
    ],

    "3. Cloud & Software": [
        "MSFT", "CRM", "NOW", "ADBE", "SNOW", "DDOG", "PANW", "CRWD",
        "MDB", "NET", "TEAM", "WDAY", "ZS", "OKTA", "SPLK", "ESTC"
    ],

    "4. Cybersecurity": [
        "PANW", "CRWD", "FTNT", "NET", "ZS", "OKTA", "CHKP", "QLYS",
        "TENB", "RPD", "S", "GEN", "VRNS", "CYBR", "BUG", "CIBR"
    ],

    "5. Fintech & Payments": [
        "V", "MA", "AXP", "COF", "PYPL", "SQ", "SOFI", "HOOD",
        "DFS", "SYF", "ALLY", "NU", "AFRM", "UPST", "LC", "DAVE"
    ],

    "6. Consumer & Retail": [
        "AMZN", "COST", "WMT", "HD", "NKE", "LULU", "TJX", "MCD",
        "LOW", "SBUX", "TGT", "ROST", "CMG", "YUM", "DG", "DLTR"
    ],

    "7. Healthcare & Pharma": [
        "LLY", "NVO", "JNJ", "MRK", "ABBV", "AMGN", "PFE", "UNH",
        "BMY", "GILD", "REGN", "VRTX", "BIIB", "MRNA", "TMO", "DHR"
    ],

    "8. Energy (Oil & Gas)": [
        "XOM", "CVX", "COP", "SLB", "EOG", "OXY", "MPC", "VLO",
        "PSX", "HAL", "BKR", "HES", "DVN", "FANG", "APA", "CTRA"
    ],

    "9. Industrials": [
        "CAT", "DE", "GE", "HON", "ETN", "UPS", "UNP", "RTX",
        "EMR", "ITW", "PH", "ROK", "AME", "DOV", "XYL", "TT"
    ],

    "10. Defense & Aerospace": [
        "RTX", "LMT", "NOC", "GD", "LHX", "BA", "TDY", "HII",
        "HEI", "TXT", "CW", "AJRD", "MTSI", "SAIC", "CACI", "LDOS"
    ],

    "11. Communication & Media": [
        "GOOGL", "META", "NFLX", "DIS", "CMCSA", "TKO", "FOXA", "WBD",
        "PARA", "SPOT", "ROKU", "LYV", "MSG", "NXST", "SBGI", "SIRI"
    ],

    "12. Financials (Banks)": [
        "JPM", "BAC", "WFC", "GS", "MS", "C", "PNC", "USB",
        "TFC", "FITB", "HBAN", "CFG", "KEY", "RF", "MTB", "ZION"
    ],

    "13. Utilities & Power": [
        "NEE", "SO", "DUK", "EXC", "AEP", "XEL", "CEG", "VST",
        "PEG", "D", "ETR", "PCG", "AES", "ED", "FE", "NRG"
    ],

    "14. REITs": [
        "AMT", "PLD", "EQIX", "O", "PSA", "DLR", "WELL", "SPG",
        "CCI", "SBAC", "VTR", "ARE", "AVB", "EQR", "IRM", "VICI"
    ],

    "15. Travel & Leisure": [
        "BKNG", "ABNB", "MAR", "DAL", "UAL", "RCL", "LUV", "EXPE",
        "NCLH", "CCL", "HLT", "IHG", "MGM", "WYNN", "CZR", "DKNG"
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
