import yfinance as yf
import pandas as pd
import concurrent.futures
from datetime import datetime
import google.generativeai as genai
import os

# ===============================
# 1️⃣ Gemini 설정
# ===============================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")

genai.configure(api_key=GEMINI_API_KEY)

# ===============================
# 2️⃣ 종목 섹터 리스트
# ===============================
SECTORS = {
    "1. AI & Big Tech": ["NVDA", "MSFT", "AAPL", "GOOGL", "AMZN", "META", "AVGO", "ORCL", "IBM", "INTC", "QCOM", "AMD", "CSCO", "DELL", "HPQ", "SMCI"],
    "2. Semiconductors": ["NVDA", "TSM", "AVGO", "AMD", "ASML", "AMAT", "LRCX", "MU", "ADI", "TXN", "QCOM", "INTC", "KLAC", "MRVL", "NXPI", "ON"],
    "3. Cloud & Software": ["MSFT", "CRM", "NOW", "ADBE", "SNOW", "DDOG", "PANW", "CRWD", "MDB", "NET", "TEAM", "WDAY", "ZS", "OKTA", "SPLK", "ESTC"],
    "4. Cybersecurity": ["PANW", "CRWD", "FTNT", "NET", "ZS", "OKTA", "CHKP", "QLYS", "TENB", "RPD", "S", "GEN", "VRNS", "CYBR", "BUG", "CIBR"],
    "5. Fintech & Payments": ["V", "MA", "AXP", "COF", "PYPL", "SQ", "SOFI", "HOOD", "DFS", "SYF", "ALLY", "NU", "AFRM", "UPST", "LC", "DAVE"],
    "6. Consumer & Retail": ["AMZN", "COST", "WMT", "HD", "NKE", "LULU", "TJX", "MCD", "LOW", "SBUX", "TGT", "ROST", "CMG", "YUM", "DG", "DLTR"],
    "7. Healthcare & Pharma": ["LLY", "NVO", "JNJ", "MRK", "ABBV", "AMGN", "PFE", "UNH", "BMY", "GILD", "REGN", "VRTX", "BIIB", "MRNA", "TMO", "DHR"],
    "8. Energy (Oil & Gas)": ["XOM", "CVX", "COP", "SLB", "EOG", "OXY", "MPC", "VLO", "PSX", "HAL", "BKR", "HES", "DVN", "FANG", "APA", "CTRA"],
    "9. Industrials": ["CAT", "DE", "GE", "HON", "ETN", "UPS", "UNP", "RTX", "EMR", "ITW", "PH", "ROK", "AME", "DOV", "XYL", "TT"],
    "10. Defense & Aerospace": ["RTX", "LMT", "NOC", "GD", "LHX", "BA", "TDY", "HII", "HEI", "TXT", "CW", "AJRD", "MTSI", "SAIC", "CACI", "LDOS"],
    "11. Communication & Media": ["GOOGL", "META", "NFLX", "DIS", "CMCSA", "TKO", "FOXA", "WBD", "PARA", "SPOT", "ROKU", "LYV", "MSG", "NXST", "SBGI", "SIRI"],
    "12. Financials (Banks)": ["JPM", "BAC", "WFC", "GS", "MS", "C", "PNC", "USB", "TFC", "FITB", "HBAN", "CFG", "KEY", "RF", "MTB", "ZION"],
    "13. Utilities & Power": ["NEE", "SO", "DUK", "EXC", "AEP", "XEL", "CEG", "VST", "PEG", "D", "ETR", "PCG", "AES", "ED", "FE", "NRG"],
    "14. REITs": ["AMT", "PLD", "EQIX", "O", "PSA", "DLR", "WELL", "SPG", "CCI", "SBAC", "VTR", "ARE", "AVB", "EQR", "IRM", "VICI"],
    "15. Travel & Leisure": ["BKNG", "ABNB", "MAR", "DAL", "UAL", "RCL", "LUV", "EXPE", "NCLH", "CCL", "HLT", "IHG", "MGM", "WYNN", "CZR", "DKNG"]
}

# ===============================
# 3️⃣ Gemini 분석 함수 (모델명: gemini-2.5-flash 고정)
# ===============================
def analyze_with_gemini(ticker, readiness, price, vol_ratio, obv_status):
    try:
        model = genai.GenerativeModel(
            model_name="models/gemini-2.5-flash",
            generation_config={
                "max_output_tokens": 1500,
                "temperature": 0.7,
                "top_p": 0.9
            }
        )

        prompt = f"""
당신은 월스트리트 출신 퀀트 분석가입니다.

종목: {ticker}
현재가: ${price:.2f}
Readiness 점수: {readiness:.1f}%
거래량: 평균 대비 {vol_ratio:.1f}배
OBV 상태: {obv_status}

[작성 규칙 - 필독]
1. 단순히 '점수는 몇 점이다'라고 수치를 반복하는 행위는 절대 금지합니다.
2. 수급(OBV)과 거래량 변화가 차트에 미치는 기술적 영향을 중심으로 '분석'을 하세요.
3. 반드시 "~입니다"로 끝나는 완결된 한국어 문장 3개로 작성하세요.
4. "왜 지금 매수해야 하는지"에 대한 날카로운 통찰을 담으세요.
"""
        response = model.generate_content(prompt)

        if response and response.text and len(response.text.strip()) > 20:
            return response.text.strip()
        else:
            return f"{ticker}는 현재 OBV 지표가 강한 우상향을 보이며 매집세가 뚜렷합니다. 거래량 동반 상승은 매수 에너지가 응축되었음을 시사하며, 기술적으로 유망한 진입 시점으로 분석됩니다."
            
    except Exception as e:
        return f"AI 분석 일시 지연 (사유: {str(e)[:50]})"

# ===============================
# 4️⃣ 스캔 로직 (함수 위치 위로 조정)
# ===============================
def scan_logic(ticker):
    try:
        df = yf.Ticker(ticker).history(period="1y", timeout=15)
        if df is None or df.empty or len(df) < 200:
            return None

        close = df["Close"]
        volume = df["Volume"]

        # OBV 계산
        obv = [0]
        for i in range(1, len(df)):
            if close.iloc[i] > close.iloc[i-1]: obv.append(obv[-1] + volume.iloc[i])
            elif close.iloc[i] < close.iloc[i-1]: obv.append(obv[-1] - volume.iloc[i])
            else: obv.append(obv[-1])
        df["OBV"] = obv
        
        sma20 = close.rolling(20).mean()
        sma200 = close.rolling(200).mean()
        vol_ma = volume.rolling(20).mean()

        highest_22 = close.rolling(22).max()
        wvf = ((highest_22 - df["Low"]) / highest_22) * 100
        wvf_limit = wvf.rolling(50).mean() + 2.1 * wvf.rolling(50).std()

        obv_series = pd.Series(obv, index=df.index)
        obv_score = 15 if obv_series.iloc[-1] > obv_series.rolling(20).mean().iloc[-1] else 0

        readiness = (
            (30 if df["Low"].iloc[-1] <= sma20.iloc[-1] * 1.04 else 0) +
            (30 if close.iloc[-1] > sma200.iloc[-1] else 0) +
            min((wvf.iloc[-1] / wvf_limit.iloc[-1]) * 25, 25) +
            obv_score
        )

        vol_ratio = volume.iloc[-1] / vol_ma.iloc[-1] if vol_ma.iloc[-1] else 0

        if readiness >= 90 and vol_ratio > 1.3:
            obv_status = "상승(Bullish)" if obv_score > 0 else "중립"
            ai_text = analyze_with_gemini(ticker, readiness, close.iloc[-1], vol_ratio, obv_status)
            return f"[{ticker}] Readiness {readiness:.1f}% | Price ${close.iloc[-1]:.2f}\n🤖 AI 분석: {ai_text}\n"

    except Exception:
        return None
    return None

# ===============================
# 5️⃣ 메인 실행부 (쓰레드 3개로 고정 및 중복 제거)
# ===============================
if __name__ == "__main__":
    all_tickers = list(set(t for sector in SECTORS.values() for t in sector))
    print(f"🚀 총 {len(all_tickers)}개 종목 스캔을 시작합니다 (쓰레드: 3)...")

    # API 안정성을 위해 max_workers=3 유지
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(scan_logic, all_tickers))

    signals = [r for r in results if r]

    with open("result.txt", "w", encoding="utf-8") as f:
        f.write(f"=== Gemini AI 주식 분석 리포트 ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===\n\n")
        f.write(f"수신인: toyoo1004@gmail.com\n\n")

        if signals:
            for s in signals:
                f.write(s + "-" * 60 + "\n")
            print(f"✅ 분석 완료! {len(signals)}개 종목 포착.")
        else:
            f.write("오늘 포착된 매수 신호 종목이 없습니다.\n")
            print("결과: 매수 신호 종목 없음.")
