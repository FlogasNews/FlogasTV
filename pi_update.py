import os
import sys
import time
import json
import csv
import datetime
import subprocess
import requests
from bs4 import BeautifulSoup
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from jinja2 import Environment, FileSystemLoader

# Paths relative to the script directory
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(WORKSPACE_DIR, 'commodity_prices.csv')
CACHE_PATH = os.path.join(WORKSPACE_DIR, 'dashboard_cache.json')
TEMPLATE_NAME = 'tv_template.html'
OUTPUT_NAME = 'index.html'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}

def pull_updates_from_github():
    print("Checking for daily morning updates from GitHub...")
    try:
        # Run git pull to get latest dashboard_cache.json and templates from PC
        result = subprocess.run(['git', 'pull'], capture_output=True, text=True, cwd=WORKSPACE_DIR)
        if result.returncode == 0:
            print("Git pull successful:\n", result.stdout.strip())
            return True
        else:
            print("Git pull failed:\n", result.stderr.strip())
            return False
    except Exception as e:
        print(f"Error executing git pull: {e}")
        return False

def load_cache():
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading cache: {e}")
    return {
        'fig1_html': '<div>No NBP daily price cache found.</div>',
        'fig2_html': '<div>No NBP forward curve cache found.</div>',
        'fig3_html': '<div>No diesel curve cache found.</div>',
        'headlines': ['No headlines found in cache.']
    }

def scrape_trading_economics():
    url = "https://tradingeconomics.com/commodities"
    print(f"Scraping real-time Brent and TTF Gas prices from {url}...")
    r = requests.get(url, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        raise Exception(f"Failed to fetch TradingEconomics (status code: {r.status_code})")
    
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # Brent Crude
    brent_row = soup.find('tr', {'data-symbol': 'CO1:COM'})
    if not brent_row:
        raise Exception("Could not find Brent Crude row (CO1:COM)")
    brent_price = float(brent_row.find('td', {'id': 'p'}).get_text(strip=True).replace(',', ''))
    
    # TTF Gas
    ttf_row = soup.find('tr', {'data-symbol': 'NGEU:COM'})
    if not ttf_row:
        raise Exception("Could not find TTF Gas row (NGEU:COM)")
    ttf_price = float(ttf_row.find('td', {'id': 'p'}).get_text(strip=True).replace(',', ''))
    
    return brent_price, ttf_price

def record_prices(brent, ttf_gas):
    now = datetime.datetime.now()
    timestamp_str = now.strftime('%Y-%m-%d %H:%M:%S')
    file_exists = os.path.exists(CSV_PATH)
    
    with open(CSV_PATH, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['Timestamp', 'Brent', 'TTF_Gas'])
        writer.writerow([timestamp_str, brent, ttf_gas])
    print(f"[{timestamp_str}] Recorded Brent: {brent} | TTF Gas: {ttf_gas}")

def get_empty_commodity_chart(target_date):
    start_range = datetime.datetime.combine(target_date, datetime.time(8, 0, 0))
    end_range = datetime.datetime.combine(target_date, datetime.time(18, 0, 0))
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=[], y=[], name='Brent Crude ($/Bbl)'), secondary_y=False)
    fig.add_trace(go.Scatter(x=[], y=[], name='TTF Gas (€/MWh)'), secondary_y=True)
    fig.update_layout(
        title={'text': f'Brent & TTF Gas Prices ({target_date.strftime("%d %b %Y")} - Awaiting Data)', 'x': 0.5, 'xanchor': 'center'},
        xaxis=dict(title='Time of Day', type='date', range=[start_range, end_range], tickformat='%H:%M', gridcolor='rgba(255, 255, 255, 0.1)'),
        yaxis=dict(title=dict(text='Brent Crude (USD/Bbl)', font=dict(color='deepskyblue')), tickfont=dict(color='deepskyblue'), gridcolor='rgba(255, 255, 255, 0.1)'),
        yaxis2=dict(title=dict(text='TTF Gas (EUR/MWh)', font=dict(color='darkviolet')), tickfont=dict(color='darkviolet')),
        paper_bgcolor='white', plot_bgcolor='#E5ECF6', font=dict(size=24), autosize=True,
        margin=dict(l=80, r=80, t=60, b=95)
    )
    return fig

def generate_commodity_chart():
    if not os.path.exists(CSV_PATH):
        return get_empty_commodity_chart(datetime.date.today())
        
    df = pd.read_csv(CSV_PATH)
    if df.empty:
        return get_empty_commodity_chart(datetime.date.today())
        
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    today = datetime.date.today()
    available_dates = df['Timestamp'].dt.date.unique()
    
    if len(available_dates) == 0:
        return get_empty_commodity_chart(today)
        
    target_date = today
    if today not in available_dates:
        target_date = max(available_dates)
        
    df_day = df[df['Timestamp'].dt.date == target_date].copy().sort_values('Timestamp')
    
    start_range = datetime.datetime.combine(target_date, datetime.time(8, 0, 0))
    end_range = datetime.datetime.combine(target_date, datetime.time(18, 0, 0))
    df_active = df_day[(df_day['Timestamp'] >= start_range) & (df_day['Timestamp'] <= end_range)].copy()
    
    if df_active.empty:
        return get_empty_commodity_chart(target_date)
        
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    fig.add_trace(
        go.Scatter(
            x=df_active['Timestamp'], y=df_active['Brent'],
            name='Brent Crude ($/Bbl)', mode='lines+markers',
            line=dict(color='deepskyblue', width=3), marker=dict(size=8, color='deepskyblue')
        ), secondary_y=False
    )
    
    fig.add_trace(
        go.Scatter(
            x=df_active['Timestamp'], y=df_active['TTF_Gas'],
            name='TTF Gas (€/MWh)', mode='lines+markers',
            line=dict(color='darkviolet', width=3), marker=dict(size=8, color='darkviolet')
        ), secondary_y=True
    )
    
    brent_min, brent_max = df_active['Brent'].min(), df_active['Brent'].max()
    brent_range = [brent_min * 0.90, brent_max * 1.10]
    
    ttf_min, ttf_max = df_active['TTF_Gas'].min(), df_active['TTF_Gas'].max()
    ttf_range = [ttf_min * 0.90, ttf_max * 1.10]

    fig.update_layout(
        title={'text': f'Brent Crude & TTF Gas Prices ({target_date.strftime("%d %b %Y")})', 'x': 0.5, 'xanchor': 'center'},
        xaxis=dict(title='Time of Day', type='date', range=[start_range, end_range], tickformat='%H:%M', showgrid=True, gridcolor='white', dtick=3600000 * 2),
        yaxis=dict(title=dict(text='Brent Crude (USD/Bbl)', font=dict(color='deepskyblue')), tickfont=dict(color='deepskyblue'), showgrid=True, gridcolor='white', zeroline=False, range=brent_range),
        yaxis2=dict(title=dict(text='TTF Gas (EUR/MWh)', font=dict(color='darkviolet')), tickfont=dict(color='darkviolet'), showgrid=False, zeroline=False, range=ttf_range),
        legend=dict(x=0.01, y=0.98, bgcolor='rgba(255, 255, 255, 0.8)', bordercolor='lightgray', borderwidth=1, font=dict(size=16)),
        paper_bgcolor='white', plot_bgcolor='#E5ECF6', font=dict(size=24), autosize=True,
        margin=dict(l=80, r=80, t=60, b=95)
    )
    return fig

def update_dashboard():
    print("\n--- Starting Pi Update Cycle ---")
    
    # 1. Pull daily updates (NBP/Diesel curves & headlines) from GitHub
    pull_updates_from_github()
    
    # 2. Scrape real-time commodities
    try:
        brent, ttf = scrape_trading_economics()
        record_prices(brent, ttf)
    except Exception as e:
        print(f"Scraping error: {e}. Using existing CSV records.")
        
    # 3. Load other curves from the downloaded cache
    cache = load_cache()
    
    # 4. Generate commodity chart
    try:
        fig4 = generate_commodity_chart()
        fig4_html = fig4.to_html(full_html=False, include_plotlyjs=False)
    except Exception as e:
        print(f"Error plotting commodity chart: {e}")
        fig4_html = "<div>Error plotting commodity chart.</div>"
        
    # 5. Render index.html locally
    try:
        env = Environment(loader=FileSystemLoader(WORKSPACE_DIR))
        template = env.get_template(TEMPLATE_NAME)
        html_content = template.render(
            fig1_html=cache['fig1_html'],
            fig2_html=cache['fig2_html'],
            fig3_html=cache['fig3_html'],
            fig4_html=fig4_html,
            headlines=cache['headlines']
        )
        
        output_file_path = os.path.join(WORKSPACE_DIR, OUTPUT_NAME)
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Dashboard generated locally: {output_file_path}")
    except Exception as e:
        print(f"Error rendering template: {e}")
        
    print("--- Cycle Complete ---")

if __name__ == "__main__":
    once = "--once" in sys.argv
    if once:
        update_dashboard()
    else:
        print("Starting Pi Energy Dashboard Update Loop (5-minute interval)...")
        # Run first cycle immediately
        update_dashboard()
        try:
            while True:
                time.sleep(300)
                update_dashboard()
        except KeyboardInterrupt:
            print("\nStopped Pi update service.")
            sys.exit(0)
