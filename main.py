from fastapi import FastAPI
import yfinance as yf
import pandas as pd
import ta

app = FastAPI()

def get_macro_data():
    """거시경제 지표 수집 (HYG, US10Y, VIX, DXY)"""
    try:
        hyg = yf.download("HYG", period="30d", interval="1d")
        tnx = yf.download("^TNX", period="5d", interval="1d")
        vix = yf.download("^VIX", period="5d", interval="1d")
        dxy = yf.download("DX-Y.NY", period="5d", interval="1d")

        for d in [hyg, tnx, vix, dxy]:
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)

        hyg_latest = round(float(hyg['Close'].iloc[-1]), 2)
        hyg_ma20 = round(float(ta.trend.sma_indicator(hyg['Close'], window=20).iloc[-1]), 2)
        us10y_latest = round(float(tnx['Close'].iloc[-1]), 2)
        vix_latest = round(float(vix['Close'].iloc[-1]), 2)
        dxy_latest = round(float(dxy['Close'].iloc[-1]), 2)

        hyg_safe = hyg_latest >= hyg_ma20
        us10y_safe = us10y_latest <= 4.5
        vix_safe = vix_latest <= 20.0
        dxy_safe = dxy_latest <= 105.0

        macro_score = sum([hyg_safe, us10y_safe, vix_safe, dxy_safe])

        return {
            "hyg_price": hyg_latest,
            "hyg_safe": hyg_safe,
            "us10y_rate": us10y_latest,
            "us10y_safe": us10y_safe,
            "vix": vix_latest,
            "vix_safe": vix_safe,
            "dxy": dxy_latest,
            "dxy_safe": dxy_safe,
            "macro_score": f"{macro_score}/4",
            "is_macro_safe": macro_score >= 3
        }
    except Exception as e:
        return {"error": str(e)}

def calculate_ticker_metrics(ticker_symbol: str):
    """주식 종목별 기술적 지표 및 조건 확인"""
    df = yf.download(ticker_symbol, period="150d", interval="1d")
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 이동평균선 및 기술적 지표 계산 (ta 라이브러리 활용)
    df['MA5'] = ta.trend.sma_indicator(df['Close'], window=5)
    df['MA60'] = ta.trend.sma_indicator(df['Close'], window=60)
    df['MA120'] = ta.trend.sma_indicator(df['Close'], window=120)
    df['VOL_MA20'] = ta.trend.sma_indicator(df['Volume'], window=20)
    
    df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
    df['CCI'] = ta.trend.cci(df['High'], df['Low'], df['Close'], window=20)
    df['Sto_K'] = ta.momentum.stoch(df['High'], df['Low'], df['Close'], window=14, smooth_window=3)

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    rsi_val = round(float(latest['RSI']), 1)
    rsi_turn = (rsi_val <= 38) and (rsi_val > float(prev['RSI']))

    cci_val = round(float(latest['CCI']), 1)
    cci_turn = (cci_val <= -100) and (cci_val > float(prev['CCI']))

    sto_val = round(float(latest['Sto_K']), 1)
    sto_turn = (sto_val <= 25) and (sto_val > float(prev['Sto_K']))

    vol_ratio = round((float(latest['Volume']) / float(latest['VOL_MA20'])) * 100, 1)
    vol_pass = vol_ratio >= 120

    is_green_candle = float(latest['Close']) > float(latest['Open'])
    above_ma5 = float(latest['Close']) >= float(latest['MA5'])
    candle_pass = is_green_candle and above_ma5

    macro = get_macro_data()

    score = 0
    score += 1 if rsi_turn else 0
    score += 1 if cci_turn else 0
    score += 1 if sto_turn else 0
    score += 1 if vol_pass else 0
    score += 1 if candle_pass else 0
    score += 1 if macro.get("is_macro_safe", False) else 0

    disp_60 = round((float(latest['Close']) / float(latest['MA60'])) * 100, 1)
    disp_120 = round((float(latest['Close']) / float(latest['MA120'])) * 100, 1)

    return {
        "symbol": ticker_symbol,
        "price": round(float(latest['Close']), 2),
        "disp_60": disp_60,
        "disp_120": disp_120,
        "buy_score": f"{score}/6",
        "verification": {
            "vol_ratio": f"{vol_ratio}%",
            "vol_pass": vol_pass,
            "candle_pass": candle_pass
        },
        "macro_filter": {
            "hyg_price": f"${macro.get('hyg_price')}",
            "us10y_rate": f"{macro.get('us10y_rate')}%",
            "is_safe": macro.get("is_macro_safe")
        }
    }

@app.get("/api/widget/macro")
def get_macro_widget():
    return {"status": "success", "data": get_macro_data()}

@app.get("/api/widget/{ticker}")
def get_stock_widget(ticker: str):
    try:
        data = calculate_ticker_metrics(ticker.upper())
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}