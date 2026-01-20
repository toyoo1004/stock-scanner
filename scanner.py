import yfinance as yf
import pandas as pd
import concurrent.futures
from datetime import datetime
import sys

# === [25개 섹터 티커 리스트] ===
SECTORS = {
    "1. AI & Cloud": ["NVDA", "MSFT", "GOOGL", "AMZN", "META", "PLTR", "AVGO", "ADBE", "CRM", "AMD", "IBM", "NOW", "INTC", "QCOM", "AMAT", "MU", "LRCX", "ADI", "SNOW", "DDOG", "NET", "MDB", "PANW", "CRWD", "ZS", "FTNT", "TEAM", "WDAY", "SMCI", "ARM", "PATH", "AI", "SOUN", "BBAI", "ORCL", "CSCO"],
    "2. Semiconductors": ["TSM", "AVGO", "AMD", "INTC", "ASML", "AMAT", "LRCX", "MU", "QCOM", "ADI", "TXN", "MRVL", "KLAC", "NXPI", "STM", "ON", "MCHP", "MPWR", "TER", "ENTG", "SWKS", "QRVO", "WOLF", "COHR", "IPGP", "LSCC", "RMBS", "FORM", "ACLS", "CAMT", "UCTT", "ICHR", "AEHR", "GFS"],
    "3. Rare Earth": ["MP", "UUUU", "LAC", "ALTM", "SGML", "PLL", "LTHM", "REMX", "TMC", "NB", "TMQ", "TMRC", "UAMY", "AREC", "IDR", "RIO", "BHP", "VALE", "FCX", "SCCO", "AA", "CENX", "KALU", "CRS", "ATI", "HAYW"],
    "4. Weight Loss & Bio": ["LLY", "NVO", "AMGN", "PFE", "VKTX", "ALT", "ZP", "GILD", "BMY", "JNJ", "ABBV", "MRK", "BIIB", "REGN", "VRTX", "MRNA", "BNTX", "NVS", "AZN", "SNY", "ALNY", "SRPT", "BMRN", "INCY", "UTHR", "GERN", "CRSP", "EDIT", "NTLA", "BEAM", "SAGE", "ITCI", "AXSM"],
    "5. Fintech & Crypto": ["COIN", "MSTR", "HOOD", "SQ", "PYPL", "SOFI", "AFRM", "UPST", "MARA", "RIOT", "CLSK", "HUT", "WULF", "CIFR", "BTBT", "IREN", "CORZ", "SDIG", "GREE", "BITF", "V", "MA", "AXP", "DFS", "COF", "NU", "DAVE", "LC", "GLBE", "BILL", "TOST", "MQ", "FOUR"],
    "6. Defense & Space": ["RTX", "LMT", "NOC", "GD", "BA", "LHX", "HII", "LDOS", "TXT", "HWM", "AXON", "KTOS", "AVAV", "RKLB", "SPCE", "ASTS", "LUNR", "PL", "SPIR", "BKSY", "VSAT", "IRDM", "SAIC", "CACI", "CW", "HEI", "TDY", "AJRD", "MTSI", "RCAT", "SHLD"],
    "7. Uranium & Nuclear": ["CCJ", "UUUU", "NXE", "UEC", "DNN", "SMR", "BWXT", "LEU", "OKLO", "FLR", "URA", "URNM", "NLR", "SRUUF", "FCU", "GLO", "PDN", "BOE", "DYL", "PENMF", "CEG", "PEG", "EXC", "D", "SO", "NEE", "DUK", "ETR", "PCG", "VST"],
    "8. Consumer & Luxury": ["LVMUY", "RACE", "NKE", "LULU", "ONON", "DECK", "CROX", "SKX", "RL", "TPR", "CPRI", "PVH", "VFC", "UAA", "COLM", "GPS", "ANF", "AEO", "URBN", "ROST", "TJX", "HESAY", "CFRUY", "PPRUY", "BURBY", "BOSS.DE", "EL", "COTY", "ULTA", "ELF"],
    "9. Meme & Reddit": ["GME", "AMC", "RDDT", "DJT", "TSLA", "PLTR", "SOFI", "OPEN", "LCID", "RIVN", "CHPT", "NKLA", "SPCE", "TLRY", "CGC", "SNDL", "BB", "NOK", "KOSS", "EXPR", "MULN", "FFIE", "HOLO", "GNS", "CVNA", "AI", "BIG", "RAD", "WISH", "CLOV"],
    "10. Quantum": ["IONQ", "RGTI", "QUBT", "HON", "IBM", "MSFT", "GOOGL", "INTC", "FORM", "AMAT", "ASML", "KEYS", "ADI", "TXN", "NVDA", "AMD", "QCOM", "AVGO", "TSM", "MU", "D-WAVE", "ARQQ", "QBTS", "QMCO"],
    "11. Robotics": ["ISRG", "TER", "PATH", "SYM", "RKLY", "ABB", "CGNX", "ROCK", "ATSG", "BRKS", "TKR", "ROBO", "BOTZ", "IRBT", "NVDA", "TSLA", "DE", "CAT", "EMR", "PH", "FANUC", "YASKY", "KUKAY", "SIEGY"],
    "12. Biotech": ["VRTX", "AMGN", "MRNA", "BNTX", "REGN", "GILD", "BIIB", "ILMN", "CRSP", "BEAM", "NTLA", "EDIT", "NVTA", "ARWR", "IONS", "SRPT", "BMRN", "INCY", "UTHR", "EXEL", "HALO", "TECH", "WST", "RGEN", "TXG", "PACB", "QGEN", "GMAB", "ARGX", "BGNE"],
    "13. E-commerce": ["AMZN", "WMT", "COST", "HD", "SHOP", "MELI", "BABA", "PDD", "EBAY", "ETSY", "CPNG", "SE", "JMIA", "JD", "VIPS", "TGT", "LOW", "BBY", "M", "KSS", "JWN", "GPS", "ANF", "AEO", "URBN", "ROST", "TJX", "DLTR", "DG", "BJ"],
    "14. Gaming": ["RBLX", "U", "EA", "TTWO", "SONY", "NTES", "ATVI", "SE", "PLTK", "SKLZ", "EDR", "MSFT", "NVDA", "GME", "UBSFY", "NCBDY", "TCEHY", "BILI", "DOYU", "HUYA", "CRSR", "LOGI", "HEAR", "ZNGA"],
    "15. Streaming": ["NFLX", "DIS", "WBD", "PARA", "SPOT", "ROKU", "AMC", "CNK", "LYV", "MSG", "TKO", "FOXA", "CMCSA", "IQ", "FUBO", "GOOGL", "AMZN", "AAPL", "SIRI", "LGF-A", "WMG", "UMG", "TR", "NXST", "SBGI"],
    "16. Banking": ["JPM", "BAC", "WFC", "C", "GS", "MS", "HSBC", "RY", "TD", "UBS", "NU", "SOFI", "ALLY", "FITB", "HBAN", "USB", "PNC", "TFC", "COF", "AXP", "V", "MA", "DFS", "SYF", "KEY", "CFG", "RF", "MTB", "CMA", "ZION"],
    "17. Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "OXY", "PSX", "VLO", "HAL", "BKR", "HES", "DVN", "FANG", "MRO", "APA", "CTRA", "PXD", "WMB", "KMI", "OKE", "TRGP", "LNG", "EQT", "RRC", "SWN", "CHK", "MTDR", "PDCE", "CIVI"],
    "18. Renewables": ["ENPH", "SEDG", "FSLR", "NEE", "BEP", "RUN", "ARRY", "CSIQ", "DQ", "JKS", "MAXN", "SPWR", "NOVA", "SHLS", "GEV", "CWEN", "AY", "HASI", "ORA", "TPIC", "BLDP", "PLUG", "FCEL", "BE", "AMRC", "STEM", "FLNC", "AES", "CEG", "VST"],
    "19. Gold": ["GOLD", "NEM", "KL", "AU", "GDX", "GDXJ", "AEM", "FNV", "WPM", "KGC", "PAAS", "MAG", "SAND", "OR", "PHYS", "HMY", "GFI", "IAG", "NGD", "EGO", "DRD", "SBSW", "CDE", "HL", "AG", "EXK", "FSM", "MUX", "USAS", "GORO"],
    "20. Industrial": ["UPS", "FDX", "CAT", "DE", "HON", "GE", "MMM", "UNP", "EMR", "ITW", "PH", "ETN", "NSC", "CSX", "CMI", "ROK", "AME", "DOV", "XYL", "TT", "CARR", "OTIS", "JCI", "LII", "GWW", "FAST", "URI", "PWR", "EME", "ACM"],
    "21. Real Estate": ["AMT", "PLD", "CCI", "EQIX", "PSA", "O", "DLR", "WELL", "AVB", "EQR", "VTR", "ARE", "SPG", "WY", "SBAC", "VICI", "GLPI", "IRM", "MAA", "ESS", "UDR", "CPT", "INVH", "AMH", "SUI", "ELS", "LAMR", "OUT", "KIM", "REG"],
    "22. Travel": ["BKNG", "ABNB", "MAR", "H", "RCL", "CCL", "NCLH", "DAL", "UAL", "LUV", "EXPE", "TRIP", "MGM", "WYNN", "CZR", "LVS", "PENN", "DKNG", "BYD", "CHH", "WH", "HLT", "IHG", "VAC", "TNL", "PLYA", "SAVE", "JBLU", "ALK", "HA"],
    "23. Food": ["PEP", "KO", "MDLZ", "MNST", "HSY", "KDP", "STZ", "BUD", "KR", "SYY", "ADM", "GIS", "K", "HRL", "SBUX", "CMG", "YUM", "QSR", "DPZ", "WEN", "MCD", "DRI", "TXRH", "CBRL", "BJRI", "CAKE", "WING", "SHAK", "DNUT", "BRC"],
    "24. Cybersecurity": ["PANW", "CRWD", "FTNT", "NET", "ZS", "OKTA", "S", "QLYS", "CHKP", "TENB", "RPD", "GEN", "VRNS", "CYBR", "BB", "HACK", "CIBR", "BUG", "FEYE", "MIME", "PFPT", "SAIL", "PING", "SUMO", "FROG", "NCNO", "WK", "DOCU", "DBX", "BOX"],
    "25. Space": ["SPCE", "RKLB", "ASTS", "BKSY", "PL", "SPIR", "LUNR", "VSAT", "IRDM", "JOBY", "ACHR", "UP", "MNTS", "RDW", "SIDU", "LLAP", "VORB", "ASTR", "DCO", "TL0", "BA", "LMT", "NOC", "RTX", "LHX", "GD", "HII", "LDOS", "TXT", "HWM"]
}

def scan_logic(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 타임아웃을 15초로 늘려 안정성 확보
        df = stock.history(period="1y", timeout=15)
        
        if df is None or len(df) < 100:
            return None
        
        close = df['Close']
        # OBV 계산
        obv = [0]
        for i in range(1, len(df)):
            if close.iloc[i] > close.iloc[i-1]:
                obv.append(obv[-1] + df['Volume'].iloc[i])
            elif close.iloc[i] < close.iloc[i-1]:
                obv.append(obv[-1] - df['Volume'].iloc[i])
            else:
                obv.append(obv[-1])
        df['OBV'] = obv
        
        # 보조지표
        sma20 = close.rolling(20).mean()
        sma200 = close.rolling(200).mean()
        vol_ma = df['Volume'].rolling(20).mean()
        
        # WVF
        highest_22 = close.rolling(22).max()
        wvf = ((highest_22 - df['Low']) / highest_22) * 100
        wvf_limit = wvf.rolling(50).mean() + (2.1 * wvf.rolling(50).std())
        
        # 스코어링
        p_score = 30 if df['Low'].iloc[-1] <= sma20.iloc[-1] * 1.04 else 0
        t_score = 30 if close.iloc[-1] > sma200.iloc[-1] else 0
        f_score = min((wvf.iloc[-1] / wvf_limit.iloc[-1]) * 25, 25) if wvf_limit.iloc[-1] != 0 else 0
        o_score = 15 if df['OBV'].iloc[-1] > df['OBV'].rolling(20).mean().iloc[-1] else 0
        
        readiness = p_score + t_score + f_score + o_score
        vol_p = df['Volume'].iloc[-1] / vol_ma.iloc[-1] if vol_ma.iloc[-1] != 0 else 0
        
        if readiness >= 90 and vol_p > 1.3:
            return f"[{ticker}] Readiness: {readiness:.1f}% | Price: ${close.iloc[-1]:.2f} | Vol: {vol_p:.1f}x"
    except Exception as e:
        return None
    return None

if __name__ == "__main__":
    print(f"=== SCAN START: {datetime.now()} ===")
    
    # 티커 추출 및 중복 제거
    all_tickers = []
    for t_list in SECTORS.values():
        all_tickers.extend(t_list)
    unique_tickers = list(set(all_tickers))
    
    # 병렬 처리 (서버 부하 조절을 위해 10개로 제한)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(scan_logic, unique_tickers))
    
    found = [r for r in results if r]
    
    print("\n" + "="*50)
    if found:
        print(f"🎯 SIGNAL BUY DETECTED ({len(found)} stocks):")
        for f in found:
            print(f)
    else:
        print("No signals found.")
    print("="*50)
    print(f"=== SCAN END: {datetime.now()} ===")
