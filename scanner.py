import yfinance as yf
import pandas as pd
import concurrent.futures
from datetime import datetime
import google.generativeai as genai
import os

# === [1. Gemini 3 Flash 설정] ===
GEMINI_API_KEY = "AIzaSyD45Cht5i2fiv19NBxdatFZLTDFrkon47A"
genai.configure(api_key=GEMINI_API_KEY)

# === [2. 분석 대상 종목 (섹터별)] ===
SECTORS = {
    "AI & Tech": ["NVDA", "MSFT", "GOOGL", "AMZN", "META", "PLTR", "AVGO", "ADBE", "CRM", "AMD", "IBM", "NOW", "INTC", "QCOM", "AMAT", "MU", "LRCX", "ADI", "SNOW", "DDOG", "NET", "MDB", "PANW", "CRWD", "ZS", "FTNT", "TEAM", "WDAY", "SMCI", "ARM", "PATH", "AI", "SOUN", "BBAI", "ORCL", "CSCO"],
    "Bio & Health": ["LLY", "NVO", "AMGN", "PFE", "VKTX", "ALT", "ZP", "GILD", "BMY", "JNJ", "ABBV", "MRK", "BIIB", "REGN", "VRTX", "MRNA", "BNTX", "NVS", "AZN", "SNY", "ALNY", "SRPT", "BMRN", "INCY", "UTHR", "GERN", "CRSP", "EDIT", "NTLA", "BEAM", "SAGE", "ITCI", "AXSM"],
    "Finance & Energy": ["JPM", "BAC", "WFC", "C", "GS", "MS", "COF", "AXP", "V", "MA", "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "OXY", "PSX", "VLO", "HAL", "BKR", "HES", "DVN", "FANG", "MRO", "APA", "CTRA", "PXD", "WMB", "KMI", "OKE", "TRGP", "LNG", "EQT", "RRC", "SWN", "CHK", "MTDR", "PDCE", "CIVI", "AES", "CCJ", "SMR"]
}

def analyze_with_gemini(ticker, readiness, price, vol_ratio, obv_status):
    try:
        # 사용자 확인 모델 코드 반영
        model = genai.GenerativeModel('gemini-3-flash-preview') 
        prompt = f"""
        당신은 월가의 퀀트 전문가입니다. {ticker} 종목 분석 보고를 하세요.
        - 지표: 가격 ${price:.2f}, Readiness {readiness:.1f}%, 거래량 {vol_ratio:.1f}배, OBV {obv_status}
        - 요청: 이 종목의 매수 신호가 왜 강력한지 한국어로 3문장 이내로 분석해줘.
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"AI 분석 지연 (사유: {str(e)[:40]})"

def scan_logic(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y", timeout=15)
        if df is None or len(df) < 100: return None
        
        close = df['Close']
        # OBV 지표 계산 (사용자 상시 요청 사항)
        obv = [0]
        for i in range(1, len(df)):
            if close.iloc[i] > close.iloc[i-1]: obv.append(obv[-1] + df['Volume'].iloc[i])
            elif close.iloc[i] < close.iloc[i-1]: obv.append(obv[-1] - df['Volume'].iloc[i])
            else: obv.append(obv[-1])
        df['OBV'] = obv
        
        # 보조지표 및 Readiness 스코어
        sma20 = close.rolling(20).mean()
        sma200 = close.rolling(200).mean()
        vol_ma = df['Volume'].rolling(20).mean()
        highest_22 = close.rolling(22).max()
        wvf = ((highest_22 - df['Low']) / highest_22) * 100
        wvf_limit = wvf.rolling(50).mean() + (2.1 * wvf.rolling(50).std())
        
        o_score = 15 if df['OBV'].iloc[-1] > pd.Series(obv).rolling(20).mean().iloc[-1] else 0
        readiness = (30 if df['Low'].iloc[-1] <= sma20.iloc[-1] * 1.04 else 0) + \
                    (30 if close.iloc[-1] > sma200.iloc[-1] else 0) + \
                    min((wvf.iloc[-1] / wvf_limit.iloc[-1]) * 25, 25) + o_score
        
        vol_p = df['Volume'].iloc[-1] / vol_ma.iloc[-1] if vol_ma.iloc[-1] != 0 else 0
        
        if readiness >= 90 and vol_p > 1.3:
            analysis = analyze_with_gemini(ticker, readiness, close.iloc[-1], vol_p, "강세" if o_score > 0 else "유지")
            return f"[{ticker}] Readiness: {readiness:.1f}% | Price: ${close.iloc[-1]:.2f}\n🤖 Gemini 3 분석: {analysis}\n"
    except: return None

if __name__ == "__main__":
    all_tickers = list(set([t for sub in SECTORS.values() for t in sub]))
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(scan_logic, all_tickers))
    
    found = [r for r in results if r]
    with open("result.txt", "w", encoding="utf-8") as f:
        f.write(f"=== Gemini 3 Flash 주식 분석 리포트 ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===\n")
        if found:
            for res in found:
                f.write(res + "-"*60 + "\n")
        else:
            f.write("오늘 포착된 신호가 없습니다.\n")
