from fastapi import FastAPI
import yfinance as yf
import pandas as pd
import ta

app = FastAPI()

def get_safe_history(ticker_symbol: str, period: str = "1mo", interval: str = "1d"):
    """데이터가 비어있지 않게 안전하게 수집하는 함수"""
    ticker = yf.Ticker(ticker_symbol)
    df = ticker.history(period=period, interval=interval)
    if df.empty:
        # 1mo 실패 시 더 긴 기간으로 재시도
        df = ticker.history(period="3mo", interval=1d)
    return df

@app.get("/")
def read_root():
    return {"message": "hoistock API Server is Running!"}

@app.get("/api/widget/macro")
def get_macro_data():
    try:
        # HYG (하이필드 채권 ETF) 및 ^TNX (미국 10년물 국채금리)
        hyg = get_safe_history("HYG", period="3mo")
        tnx = get_safe_history("^TNX", period="3mo")

        if hyg.empty or len(hyg) < 2:
            return {"status": "error", "message": "HYG 데이터 수집 실패"}

        # RSI 계산
        hyg['RSI'] = ta.momentum.rsi(hyg['Close'], window=14)
        
        # NaN 제거 후 마지막 데이터 추출
        hyg_clean = hyg.dropna(subset=['RSI'])
        if hyg_clean.empty:
            rsi_val = float(hyg['RSI'].iloc[-1]) if not pd.isna(hyg['RSI'].iloc[-1]) else 50.0
        else:
            rsi_val = float(hyg_clean['RSI'].iloc[-1])

        curr_hyg = float(hyg['Close'].iloc[-1])
        prev_hyg = float(hyg['Close'].iloc[-2])
        hyg_change = float(((curr_hyg - prev_hyg) / prev_hyg) * 100)

        tnx_val = float(tnx['Close'].iloc[-1]) if not tnx.empty else 0.0

        return {
            "status": "success",
            "data": {
                "hyg_price": round(curr_hyg, 2),
                "hyg_change_pct": round(hyg_change, 2),
                "hyg_rsi": round(rsi_val, 2),
                "us10y_yield": round(tnx_val, 2)
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/widget/{ticker}")
def get_stock_data(ticker: str):
    try:
        ticker_upper = ticker.upper()
        df = get_safe_history(ticker_upper, period="3mo")

        if df.empty or len(df) < 2:
            return {"status": "error", "message": f"{ticker_upper} 데이터를 찾을 수 없습니다."}

        df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
        
        curr_price = float(df['Close'].iloc[-1])
        prev_price = float(df['Close'].iloc[-2])
        change_pct = float(((curr_price - prev_price) / prev_price) * 100)
        
        rsi_series = df['RSI'].dropna()
        rsi_val = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0

        return {
            "status": "success",
            "ticker": ticker_upper,
            "data": {
                "price": round(curr_price, 2),
                "change_pct": round(change_pct, 2),
                "rsi": round(rsi_val, 2)
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
