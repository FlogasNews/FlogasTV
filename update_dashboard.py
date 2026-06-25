import os
import re
import sys
import time
import json
import csv
import datetime
from datetime import timedelta
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from jinja2 import Environment, FileSystemLoader
import github_sync

# Try importing proprietary Flogas and news APIs
try:
    import icepython as icexl
except ImportError:
    icexl = None

try:
    from eventregistry import EventRegistry, QueryArticles, RequestArticlesInfo
except ImportError:
    EventRegistry = None

# Constants & Paths
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(WORKSPACE_DIR, 'commodity_prices.csv')
CACHE_PATH = os.path.join(WORKSPACE_DIR, 'dashboard_cache.json')
TEMPLATE_NAME = 'tv_template.html'
OUTPUT_NAME = 'index.html'

# Default headers for web scraping
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

# ==============================================================================
# Cache Management
# ==============================================================================
def load_cache():
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                print("Loading cached dashboard components...")
                return json.load(f)
        except Exception as e:
            print(f"Error loading cache: {e}")
    return {
        'fig1_html': '',
        'fig2_html': '',
        'fig3_html': '',
        'headlines': []
    }

def save_cache(cache_data):
    try:
        with open(CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
            print("Dashboard cache updated.")
    except Exception as e:
        print(f"Error saving cache: {e}")

# ==============================================================================
# Trading Economics Scraper
# ==============================================================================
def scrape_trading_economics():
    url = "https://tradingeconomics.com/commodities"
    print(f"Scraping real-time Brent and TTF Gas prices from {url}...")
    r = requests.get(url, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        raise Exception(f"Failed to fetch TradingEconomics (status code: {r.status_code})")
    
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # Extract Brent Price (Symbol: CO1:COM)
    brent_row = soup.find('tr', {'data-symbol': 'CO1:COM'})
    if not brent_row:
        raise Exception("Could not find Brent Crude row (CO1:COM)")
    brent_price_td = brent_row.find('td', {'id': 'p'})
    if not brent_price_td:
        raise Exception("Could not find price cell for Brent Crude")
    brent_price = float(brent_price_td.get_text(strip=True).replace(',', ''))
    
    # Extract TTF Gas Price (Symbol: NGEU:COM)
    ttf_row = soup.find('tr', {'data-symbol': 'NGEU:COM'})
    if not ttf_row:
        raise Exception("Could not find TTF Gas row (NGEU:COM)")
    ttf_price_td = ttf_row.find('td', {'id': 'p'})
    if not ttf_price_td:
        raise Exception("Could not find price cell for TTF Gas")
    ttf_price = float(ttf_price_td.get_text(strip=True).replace(',', ''))
    
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
    print(f"[{timestamp_str}] Saved Brent: {brent} | TTF Gas: {ttf_gas}")

# ==============================================================================
# Plotly Graph Generators
# ==============================================================================
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
        paper_bgcolor='white',
        plot_bgcolor='#E5ECF6',
        font=dict(size=24),
        autosize=True,
        margin=dict(l=80, r=80, t=60, b=50)
    )
    return fig

def generate_commodity_chart():
    print("Generating Brent & TTF Gas Prices real-time chart...")
    if not os.path.exists(CSV_PATH):
        return get_empty_commodity_chart(datetime.date.today())
        
    df = pd.read_csv(CSV_PATH)
    if df.empty:
        return get_empty_commodity_chart(datetime.date.today())
        
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    
    # Find target date to display
    today = datetime.date.today()
    available_dates = df['Timestamp'].dt.date.unique()
    
    if len(available_dates) == 0:
        return get_empty_commodity_chart(today)
        
    target_date = today
    if today not in available_dates:
        target_date = max(available_dates)
        print(f"No data for today. Plotting latest date with data: {target_date}")
        
    df_day = df[df['Timestamp'].dt.date == target_date].copy().sort_values('Timestamp')
    
    # Active range boundaries
    start_range = datetime.datetime.combine(target_date, datetime.time(8, 0, 0))
    end_range = datetime.datetime.combine(target_date, datetime.time(18, 0, 0))
    
    # Filter data points within active window (08:00 to 18:00)
    df_active = df_day[(df_day['Timestamp'] >= start_range) & (df_day['Timestamp'] <= end_range)].copy()
    
    if df_active.empty:
        # If there are no data points today within 8am-6pm (e.g. before 8am),
        # return empty chart for target_date
        return get_empty_commodity_chart(target_date)
        
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Brent trace (deepskyblue)
    fig.add_trace(
        go.Scatter(
            x=df_active['Timestamp'],
            y=df_active['Brent'],
            name='Brent Crude ($/Bbl)',
            mode='lines+markers',
            line=dict(color='deepskyblue', width=3),
            marker=dict(size=8, color='deepskyblue')
        ),
        secondary_y=False
    )
    
    # TTF Gas trace (darkviolet)
    fig.add_trace(
        go.Scatter(
            x=df_active['Timestamp'],
            y=df_active['TTF_Gas'],
            name='TTF Gas (€/MWh)',
            mode='lines+markers',
            line=dict(color='darkviolet', width=3),
            marker=dict(size=8, color='darkviolet')
        ),
        secondary_y=True
    )
    
    # Calculate Y-axis ranges with 10% buffer below min and above max
    brent_min = df_active['Brent'].min()
    brent_max = df_active['Brent'].max()
    brent_range = [brent_min * 0.90, brent_max * 1.10]
    
    ttf_min = df_active['TTF_Gas'].min()
    ttf_max = df_active['TTF_Gas'].max()
    ttf_range = [ttf_min * 0.90, ttf_max * 1.10]

    # Theme configuration
    fig.update_layout(
        title={
            'text': f'Brent Crude & TTF Gas Prices ({target_date.strftime("%d %b %Y")})',
            'x': 0.5,
            'xanchor': 'center'
        },
        xaxis=dict(
            title='Time of Day',
            type='date',
            range=[start_range, end_range],
            tickformat='%H:%M',
            showgrid=True,
            gridcolor='white',
            dtick=3600000 * 2,  # Tick every 2 hours
        ),
        yaxis=dict(
            title=dict(
                text='Brent Crude (USD/Bbl)',
                font=dict(color='deepskyblue')
            ),
            tickfont=dict(color='deepskyblue'),
            showgrid=True,
            gridcolor='white',
            zeroline=False,
            range=brent_range
        ),
        yaxis2=dict(
            title=dict(
                text='TTF Gas (EUR/MWh)',
                font=dict(color='darkviolet')
            ),
            tickfont=dict(color='darkviolet'),
            showgrid=False,
            zeroline=False,
            range=ttf_range
        ),
        legend=dict(
            x=0.01,
            y=0.98,
            bgcolor='rgba(255, 255, 255, 0.8)',
            bordercolor='lightgray',
            borderwidth=1,
            font=dict(size=16)
        ),
        paper_bgcolor='white',
        plot_bgcolor='#E5ECF6',
        font=dict(size=24),
        autosize=True,
        margin=dict(l=80, r=80, t=60, b=50)
    )
    
    return fig

# ==============================================================================
# Slow-Moving Components Fetchers
# ==============================================================================
def fetch_nbp_daily(current_date):
    print("Fetching NBP Summer/Winter Daily Prices (Fig 1)...")
    if icexl is None:
        raise ImportError("icepython is not available.")
        
    ed = current_date.strftime('%Y-%m-%d')
    sd = (current_date - timedelta(days=365)).strftime('%Y-%m-%d')
    
    fields = ['volume', 'close']
    my_data = icexl.get_timeseries(['GWMS 1!-ICE'], fields, granularity='D', start_date=sd, end_date=ed)
    my_data2 = icexl.get_timeseries(['GWMS 2!-ICE'], fields, granularity='D', start_date=sd, end_date=ed)
    
    dates, vols, values = zip(*my_data[1:])  
    dates2, vols2, values2 = zip(*my_data2[1:])  
    formatted_dates = [date for date in dates]
    
    num_points = len(formatted_dates)
    indices = [0, num_points//3, 2*num_points//3, num_points-1]
    selected_dates = [formatted_dates[i] for i in indices]
    
    fig1 = make_subplots(rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.1, row_heights=[0.99, 0.01])
    fig1.add_trace(go.Scatter(x=formatted_dates, y=values, mode='lines+markers', marker=dict(color='deepskyblue'), name='Summer 26'), row=1, col=1)
    fig1.add_trace(go.Scatter(x=formatted_dates, y=values2, mode='lines+markers', marker=dict(color='darkviolet'), name='Winter 26'), row=1, col=1)
    
    fig1.update_layout(
        title={'text': 'Summer and Winter 26 Daily NBP Prices 12 Month Lag', 'x': 0.5, 'xanchor': 'center'},
        legend=dict(x=0.01, y=0.98, bgcolor='rgba(255, 255, 255, 0.8)', bordercolor='lightgray', borderwidth=1),
        yaxis_title='p/therm',
        xaxis=dict(tickmode='array', tickvals=[formatted_dates[i] for i in indices], ticktext=selected_dates),
        font=dict(size=24), 
        autosize=True, margin=dict(l=50, r=30, t=60, b=50)
    )
    return fig1.to_html(full_html=False, include_plotlyjs='cdn')

def fetch_nbp_forward_wow(current_date):
    print("Fetching NBP Forward Curve WoW (Fig 2)...")
    if icexl is None:
        raise ImportError("icepython is not available.")
        
    lom = ['GWM ' + str(i) + '!-ICE' for i in range(1, 13)]
    ed = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    sd = (current_date - timedelta(days=8)).strftime('%Y-%m-%d')
    
    my_data_wow = icexl.get_timeseries(lom, ['Last'], granularity='D', start_date=sd, end_date=ed)
    last_week_p = my_data_wow[1][1:]
    
    wow_pull = icexl.get_quotes(lom, ['ICE Theoretical Price'])
    current_theo_p = [i[1] for i in wow_pull[1:]]
    
    def get_next_12_months():
        start_d = datetime.date.today() + datetime.timedelta(days=1)
        months_list = []
        curr_d = start_d
        for _ in range(12):
            curr_m = curr_d.month
            curr_y = curr_d.year
            next_m = curr_m + 1
            next_y = curr_y
            if next_m > 12:
                next_m = 1
                next_y += 1
            curr_d = datetime.date(next_y, next_m, 1)
            months_list.append(curr_d.strftime('%b'))
        return months_list
        
    labels = get_next_12_months()
    
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=labels, y=last_week_p, mode='lines+markers', name='Last Week', marker=dict(color='deepskyblue'), line=dict(color='deepskyblue')))
    fig2.add_trace(go.Scatter(x=labels, y=current_theo_p, mode='lines+markers', name='Current Price', marker=dict(color='darkviolet'), line=dict(color='darkviolet')))
    
    fig2.update_layout(
        title={'text': 'Forward NBP Curve Change Week on Week', 'x': 0.5, 'xanchor': 'center'},
        xaxis_title='Month', yaxis_title='P/th',
        legend=dict(x=0.01, y=0.98, bgcolor='rgba(255, 255, 255, 0.8)', bordercolor='lightgray', borderwidth=1),
        hovermode='x unified',
        font=dict(size=24), autosize=True, margin=dict(l=50, r=30, t=60, b=50)
    )
    return fig2.to_html(full_html=False, include_plotlyjs=False)

def fetch_diesel_forward_wow(current_date):
    print("Fetching Forward Diesel/Heating Oil Curve WoW (Fig 3)...")
    if icexl is None:
        raise ImportError("icepython is not available.")
        
    sd_gas = (current_date - timedelta(days=7)).strftime('%Y-%m-%d')
    lom_gas = ['GAS ' + str(i) + '!-ICE' for i in range(1, 13)]
    
    my_data_gas = icexl.get_timeseries(lom_gas, ['Last'], granularity='D', start_date=sd_gas, end_date=sd_gas)
    last_week_gas_p = my_data_gas[1][1:]
    
    wow_pull_gas = icexl.get_quotes(lom_gas, ['ICE Theoretical Price'])
    current_theo_gas_p = [i[1] for i in wow_pull_gas[1:]]
    
    def get_next_12_months():
        start_d = datetime.date.today() + datetime.timedelta(days=1)
        months_list = []
        curr_d = start_d
        for _ in range(12):
            curr_m = curr_d.month
            curr_y = curr_d.year
            next_m = curr_m + 1
            next_y = curr_y
            if next_m > 12:
                next_m = 1
                next_y += 1
            curr_d = datetime.date(next_y, next_m, 1)
            months_list.append(curr_d.strftime('%b'))
        return months_list
        
    labels = get_next_12_months()
    
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=labels, 
        y=last_week_gas_p, 
        mode='lines+markers', 
        name='Last Week',
        marker=dict(color='deepskyblue'),
        line=dict(color='deepskyblue')
    ))
    fig3.add_trace(go.Scatter(
        x=labels, 
        y=current_theo_gas_p, 
        mode='lines+markers', 
        name='Current Price',
        marker=dict(color='darkviolet'),
        line=dict(color='darkviolet')
    ))
    
    fig3.update_layout(
        title={'text': 'Forward Diesel/Heating Oil Curve Change Week on Week', 'x': 0.5, 'xanchor': 'center'},
        xaxis_title='Month', yaxis_title='USD ($) /MT',
        legend=dict(x=0.01, y=0.98, bgcolor='rgba(255, 255, 255, 0.8)', bordercolor='lightgray', borderwidth=1),
        hovermode='x unified',
        font=dict(size=24), autosize=True, margin=dict(l=50, r=30, t=60, b=50)
    )
    return fig3.to_html(full_html=False, include_plotlyjs=False)

def fetch_news():
    print("Fetching News headlines...")
    if EventRegistry is None:
        raise ImportError("eventregistry is not available.")
        
    er = EventRegistry(apiKey='1312ee84-a9f9-4fc6-95a4-0ed13b135ec3')
    nat_gas_concept_uri = er.getConceptUri("Natural Gas")
    q = QueryArticles(conceptUri=nat_gas_concept_uri, lang="eng")
    q.setRequestedResult(RequestArticlesInfo(sortBy="date", count=100))
    results = er.execQuery(q)
    
    unique_list = []
    seen_titles = set()
    if results.get('articles') and results['articles'].get('results'):
        for article in results['articles']['results']:
            title = article['title'].strip()
            source_name = article['source']['title']
            if re.search('gas', title, re.IGNORECASE) and title not in seen_titles:
                unique_list.append(f"{title} - {source_name}")
                seen_titles.add(title)
                
    if not unique_list:
        return ["No gas news headlines found today."]
    return unique_list + unique_list  # Duplicate for smooth scrolling layout

# ==============================================================================
# Main Update Runner
# ==============================================================================
def update_dashboard(force_slow_refresh=False):
    print("\n--- Starting Dashboard Update Cycle ---")
    current_date = datetime.date.today()
    cache = load_cache()
    
    # 1. Scrape real-time prices (Always update this)
    realtime_success = False
    try:
        brent, ttf = scrape_trading_economics()
        record_prices(brent, ttf)
        realtime_success = True
    except Exception as e:
        print(f"Error scraping real-time commodities: {e}")
        print("Continuing with rendering using existing database records.")
        
    # 2. Update real-time commodity chart (fig4)
    fig4_html = ''
    try:
        fig4 = generate_commodity_chart()
        fig4_html = fig4.to_html(full_html=False, include_plotlyjs=False)
    except Exception as e:
        print(f"Error generating commodity chart: {e}")
        fig4_html = "<div>Error generating commodity chart. Check console logs.</div>"
        
    # 3. Fetch slow-moving components (Every 1 hour, or if cache is empty, or if forced)
    cache_dirty = False
    
    # Fetch fig1 (Summer/Winter NBP Prices)
    if force_slow_refresh or not cache['fig1_html']:
        try:
            cache['fig1_html'] = fetch_nbp_daily(current_date)
            cache_dirty = True
        except Exception as e:
            print(f"Failed to refresh NBP daily (fig1): {e}. Reusing cache.")
            
    # Fetch fig2 (NBP Forward WoW)
    if force_slow_refresh or not cache['fig2_html']:
        try:
            cache['fig2_html'] = fetch_nbp_forward_wow(current_date)
            cache_dirty = True
        except Exception as e:
            print(f"Failed to refresh NBP Forward WoW (fig2): {e}. Reusing cache.")
            
    # Fetch fig3 (Forward Diesel/Heating Oil Curve WoW)
    if force_slow_refresh or not cache['fig3_html']:
        try:
            cache['fig3_html'] = fetch_diesel_forward_wow(current_date)
            cache_dirty = True
        except Exception as e:
            print(f"Failed to refresh Diesel Forward WoW (fig3): {e}. Reusing cache.")
            
    # Fetch headlines
    if force_slow_refresh or not cache['headlines']:
        try:
            cache['headlines'] = fetch_news()
            cache_dirty = True
        except Exception as e:
            print(f"Failed to refresh news: {e}. Reusing cache.")
            
    # Write cache to disk if dirty
    if cache_dirty:
        save_cache(cache)
        
    # 4. Render HTML template using Jinja2
    print("Rendering index.html...")
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
        print(f"Success! Dashboard {OUTPUT_NAME} generated at {output_file_path}")
        
        # Sync changes to GitHub
        github_sync.push_to_github(WORKSPACE_DIR)
        
    except Exception as e:
        print(f"Critical error rendering index.html: {e}")
        
    print("--- Update Cycle Complete ---")

# ==============================================================================
# Script Entry Point
# ==============================================================================
if __name__ == "__main__":
    once = "--once" in sys.argv
    
    if once:
        # Run once and exit
        update_dashboard(force_slow_refresh=True)
    else:
        # Continuous loop: update real-time every 5 minutes, slow items every 1 hour
        print("Starting Energy Market Dashboard Background Update Service...")
        print("Intervals: Real-time Commodities = 5 mins | Slow Components = 1 hour")
        
        # Initial run: force all components to fetch
        update_dashboard(force_slow_refresh=True)
        
        last_slow_refresh = time.time()
        
        try:
            while True:
                time.sleep(300) # Sleep for 5 minutes
                
                # Check if 1 hour (3600 seconds) has passed to refresh slow components
                current_time = time.time()
                force_slow = False
                if current_time - last_slow_refresh >= 3600:
                    force_slow = True
                    last_slow_refresh = current_time
                    
                update_dashboard(force_slow_refresh=force_slow)
                
        except KeyboardInterrupt:
            print("\nDashboard update service stopped by user.")
            sys.exit(0)
