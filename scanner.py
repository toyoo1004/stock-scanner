import yfinance as yf
import pandas as pd
import concurrent.futures
from datetime import datetime
import google.generativeai as genai
import os

# === [1. Gemini 3 Flash 설정] ===
# GitHub Secrets에서 키를 가져오도록 설정
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# === [2. 종목 리스트] ===
SECTORS = {
   "AI & Big Tech": ["NVDA","MSFT","GOOGL","AMZN","META","AAPL","AVGO","AMD","INTC","QCOM","IBM","ORCL","CSCO","ADBE","CRM","NOW","PLTR","SNOW","DDOG","MDB","NET","SMCI","ARM","PATH","AI","SOUN","BBAI","MU","LRCX","AMAT","ADI","ASML","TSM","TXN","KLAC","MRVL","NXPI","MPWR","TER"],
   "Cloud & Software": ["MSFT","AMZN","GOOGL","ORCL","CRM","NOW","TEAM","WDAY","ADBE","INTU","SNOW","DDOG","MDB","NET","OKTA","ZS","PANW","CRWD","FTNT","CHKP","QLYS","GEN","DOCU","DBX","BOX","SUMO","NCNO","WK","FROG","NCNO"],
   "Semiconductors": ["NVDA","AMD","AVGO","INTC","TSM","ASML","AMAT","LRCX","MU","ADI","TXN","QCOM","NXPI","MRVL","KLAC","MPWR","ON","MCHP","SWKS","QRVO","WOLF","COHR","IPGP","LSCC","RMBS","FORM","ACLS","CAMT","UCTT","ICHR","AEHR","GFS"],
   "Bio & Pharma": ["LLY","NVO","AMGN","PFE","GILD","BMY","JNJ","ABBV","MRK","BIIB","REGN","VRTX","MRNA","BNTX","NVS","AZN","SNY","ALNY","SRPT","BMRN","INCY","UTHR","GERN","CRSP","EDIT","NTLA","BEAM","AXSM","ILMN","IONS","HALO","TECH","WST","RGEN"],
   "Financials & Fintech": ["JPM","BAC","WFC","C","GS","MS","COF","AXP","V","MA","DFS","SYF","ALLY","USB","PNC","TFC","FITB","HBAN","KEY","CFG","MTB","CMA","ZION","NU","SOFI","HOOD","SQ","PYPL","AFRM","UPST","LC","DAVE","GLBE","BILL","TOST"],
   "Energy & Uranium": ["XOM","CVX","COP","SLB","EOG","MPC","OXY","PSX","VLO","HAL","BKR","DVN","FANG","APA","CTRA","WMB","KMI","OKE","TRGP","LNG","EQT","RRC","MTDR","CIVI","CCJ","UUUU","NXE","UEC","DNN","SMR","BWXT","LEU","OKLO","CEG","VST"],
   "Industrial & Defense": ["CAT","DE","HON","GE","MMM","UNP","EMR","ETN","PH","NSC","CSX","CMI","ROK","AME","DOV","ITW","PWR","EME","ACM","LMT","RTX","NOC","GD","LHX","HII","LDOS","TXT","HWM","HEI","TDY","AJRD","MTSI","RCAT"],
   "Consumer & Retail": ["AMZN","WMT","COST","HD","LOW","TGT","ROST","TJX","DG","DLTR","BJ","NKE","LULU","DECK","ONON","CROX","SKX","RL","ANF","AEO","URBN","EL","ULTA","ELF","SBUX","CMG","MCD","YUM","DPZ","SHAK","WING","MNST"],
   "Media & Communication": ["NFLX","DIS","WBD","PARA","SPOT","ROKU","LYV","TKO","FOXA","CMCSA","FUBO","GOOGL","META","AAPL","SIRI","WMG","UMG","NXST","SBGI"],
   "Space & Future Tech": ["RKLB","ASTS","LUNR","PL","SPIR","BKSY","VSAT","IRDM","JOBY","ACHR","UP","MNTS","RDW","SIDU","LLAP","BA","HON","LMT","NOC","RTX","GD","IONQ","RGTI","QUBT","IBM","MSFT","GOOGL"]
}

def analyze_with_gemini(ticker, readiness, price, vol_ratio, obv_status):
    if not GEMINI_API_KEY:
        return "AI 분석 불가 (사유: API Key 미설정)"
    try:
        # 모델명을 안정적인 1.5-flash로 설정
        model = genai.GenerativeModel('gemini-2.5-flash') 
        prompt = f"""
        당신은 월스트리트 출신 퀀트 분석가입니다. {ticker} 종목에 대해 분석하세요.
        - 지표: 현재가 ${price:.2f}, Readiness {readiness:.1f}%, 거래량 {vol_ratio:.1f}배, OBV {obv_status}
        - 요청: 기술적 관점에서 왜 지금이 매수 적기인지 한국어로 3문장 내외로 아주 날카롭게 요약해줘.
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"AI 분석 일시 지연 (사유: {str(e)[:40]})"

def scan_logic(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y", timeout=15)
        if df is None or df.empty or len(df) < 100:
            return None
        
        close = df['Close']
        
        # === [OBV 계산 - 사용자 요청 사항] ===
        obv = [0]
        for i in range(1, len(df)):
            if close.iloc[i] > close.iloc[i-1]: 
                obv.append(obv[-1] + df['Volume'].iloc[i])
            elif close.iloc[i] < close.iloc[i-1]: 
                obv.append(obv[-1] - df['Volume'].iloc[i])
            else: 
                obv.append(obv[-1])
        df['OBV'] = obv
        
        # 지표 계산
        sma20 = close.rolling(20).mean()
        sma200 = close.rolling(200).mean()
        vol_ma = df['Volume'].rolling(20).mean()
        highest_22 = close.rolling(22).max()
        wvf = ((highest_22 - df['Low']) / highest_22) * 100
        wvf_limit = wvf.rolling(50).mean() + (2.1 * wvf.rolling(50).std())
        
        # OBV 점수 반영
        o_score = 15 if df['OBV'].iloc[-1] > pd.Series(obv).rolling(20).mean().iloc[-1] else 0
        readiness = (30 if df['Low'].iloc[-1] <= sma20.iloc[-1] * 1.04 else 0) + \
                    (30 if close.iloc[-1] > sma200.iloc[-1] else 0) + \
                    min((wvf.iloc[-1] / wvf_limit.iloc[-1]) * 25, 25) + o_score
        
        vol_p = df['Volume'].iloc[-1] / vol_ma.iloc[-1] if vol_ma.iloc[-1] != 0 else 0
        
        # Readiness 점수가 90점 이상이고 거래량이 터진 경우만 추출
        if readiness >= 90 and vol_p > 1.3:
            obv_status = "상승(Bullish)" if o_score > 0 else "중립"
            analysis = analyze_with_gemini(ticker, readiness, close.iloc[-1], vol_p, obv_status)
            return f"[{ticker}] Readiness: {readiness:.1f}% | Price: ${close.iloc[-1]:.2f}\n🤖 AI 분석: {analysis}\n"
    except:
        return None
    return None

if __name__ == "__main__":
    all_tickers = list(set([t for sub in SECTORS.values() for t in sub]))
    print(f"Scanning {len(all_tickers)} tickers...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(scan_logic, all_tickers))
    
    found = [r for r in results if r]
    
    with open("result.txt", "w", encoding="utf-8") as f:
        f.write(f"=== Gemini AI 주식 분석 리포트 ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===\n")
        f.write(f"수신인: toyoo1004@gmail.com\n\n")
        if found:
            for res in found:
                f.write(res + "-"*60 + "\n")
        else:
            f.write("오늘 포착된 매수 신호 종목이 없습니다.\n")
