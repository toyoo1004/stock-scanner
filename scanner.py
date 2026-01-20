import yfinance as yf
import pandas as pd
import concurrent.futures
from datetime import datetime
import google.generativeai as genai
import gspread
import json
import os

# === [1. 설정부] ===
# Gemini API 설정
genai.configure(api_key="AIzaSyD45Cht5i2fiv19NBxdatFZLTDFrkon47A")

# 구글 시트 업데이트 함수
def update_google_sheet(found_data):
    try:
        # GitHub Secrets에 저장한 GSPREAD_KEY 불러오기
        secret_json = json.loads(os.environ['GSPREAD_KEY'])
        gc = gspread.service_account_from_dict(secret_json)
        
        # 사용자님 시트 주소
        sheet_url = "https://docs.google.com/spreadsheets/d/1nX2rx6Mkx98zPQqkOJEYigxnAYwBxsartKDX-vFLvjQ/edit"
        sh = gc.open_by_url(sheet_url)
        worksheet = sh.get_worksheet(0)
        
        # 데이터 입력 (날짜, 티커, 준비도, 현재가, AI 분석)
        for data in found_data:
            now = datetime.now().strftime('%Y-%m-%d %H:%M')
            worksheet.append_row([now, data['ticker'], f"{data['readiness']}%", data['price'], data['analysis']])
        print("✅ 구글 시트 업데이트 성공!")
    except Exception as e:
        print(f"❌ 구글 시트 업데이트 실패: {e}")

# Gemini 3 Flash 분석 함수
def analyze_with_gemini(ticker, readiness, price, vol_ratio, obv_status):
    try:
        model = genai.GenerativeModel('gemini-3-flash-preview') 
        prompt = f"""
        당신은 주식 전문가입니다. {ticker} 분석:
        현재가 ${price:.2f}, 준비도 {readiness:.1f}%, 거래량 {vol_ratio:.1f}배, OBV {obv_status}.
        이 데이터를 바탕으로 매수 추천 이유를 한국어로 3문장 이내 요약하세요.
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return "AI 분석 지연 중"

# 종목 스캔 로직
def scan_logic(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y", timeout=15)
        if df is None or len(df) < 100: return None
        
        close = df['Close']
        # [핵심 요청] OBV 지표 계산
        obv = [0]
        for i in range(1, len(df)):
            if close.iloc[i] > close.iloc[i-1]: obv.append(obv[-1] + df['Volume'].iloc[i])
            elif close.iloc[i] < close.iloc[i-1]: obv.append(obv[-1] - df['Volume'].iloc[i])
            else: obv.append(obv[-1])
        df['OBV'] = obv
        
        # 스캔 지표 (Readiness)
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
        
        # 조건: 준비도 90% 이상 & 거래량 1.3배 이상
        if readiness >= 90 and vol_p > 1.3:
            obv_status = "상승 강세" if o_score > 0 else "보통"
            analysis = analyze_with_gemini(ticker, readiness, close.iloc[-1], vol_p, obv_status)
            return {
                'ticker': ticker,
                'readiness': readiness,
                'price': round(close.iloc[-1], 2),
                'analysis': analysis
            }
    except:
        return None

# === [2. 메인 실행부] ===
if __name__ == "__main__":
    # 분석할 종목 리스트
    tickers = ["NVDA", "MSFT", "GOOGL", "PLTR", "MDB", "AZN", "LLY", "COF", "AES", "TSLA", "AMD"]
    
    print("🚀 스캔 시작...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(scan_logic, tickers))
    
    found = [r for r in results if r]
    
    if found:
        print(f"🎯 {len(found)}개 종목 발견! 시트 업데이트 중...")
        update_google_sheet(found)
        
        # 결과 파일 저장 (이메일 발송용 유지)
        with open("result.txt", "w", encoding="utf-8") as f:
            for item in found:
                f.write(f"[{item['ticker']}] {item['readiness']}% | ${item['price']}\n{item['analysis']}\n\n")
    else:
        print("보여줄 종목이 없습니다.")
        with open("result.txt", "w", encoding="utf-8") as f:
            f.write("오늘 포착된 신호가 없습니다.")
