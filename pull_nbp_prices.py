import datetime
import os
import requests
import io
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def get_date_30_months_ago(ref_date):
    """
    Returns the date exactly 30 months prior to the reference date.
    """
    year = ref_date.year
    month = ref_date.month
    day = ref_date.day
    
    # 30 months = 2 years (24 months) + 6 months
    year -= 2
    month -= 6
    if month <= 0:
        month += 12
        year -= 1
        
    while True:
        try:
            return datetime.date(year, month, day)
        except ValueError:
            # Handle month end day index errors (e.g., Feb 31st)
            day -= 1

def fetch_nbp_data():
    base_url = "https://data.nationalgas.com/api/find-gas-data-download"
    
    # Define date range (last 30 months to today)
    today = datetime.date.today()
    start_date = get_date_30_months_ago(today)
    
    print(f"Fetching daily NBP spot prices (SAP) from {start_date} to {today}...")
    
    # Chunk requests into 180-day periods to be safe against timeouts/limits
    chunk_size = datetime.timedelta(days=180)
    current_start = start_date
    
    dfs = []
    
    while current_start <= today:
        current_end = min(current_start + chunk_size, today)
        
        # Format dates for API
        start_str = current_start.strftime("%Y-%m-%dT00:00:00")
        end_str = current_end.strftime("%Y-%m-%dT23:59:59")
        
        params = {
            'applicableFor': 'Y',
            'dateFrom': start_str,
            'dateTo': end_str,
            'dateType': 'GASDAY',
            'latestFlag': 'Y',
            'ids': 'PUBOB603', # SAP, Actual Day
            'type': 'CSV'
        }
        
        print(f"Querying chunk: {current_start} to {current_end}...")
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(base_url, headers=headers, params=params, timeout=20)
            
            if response.status_code == 200 and response.text.strip():
                # Read CSV response into a dataframe
                df_chunk = pd.read_csv(io.StringIO(response.text))
                if not df_chunk.empty:
                    dfs.append(df_chunk)
                    print(f"  Successfully retrieved {len(df_chunk)} records.")
                else:
                    print("  No records found in this chunk.")
            else:
                print(f"  Failed to retrieve data. Status code: {response.status_code}")
                if response.text:
                    print(f"  Error message: {response.text[:200]}")
        except Exception as e:
            print(f"  Error querying chunk: {e}")
            
        current_start = current_end + datetime.timedelta(days=1)
        
    if not dfs:
        print("No data could be retrieved. Exiting.")
        return
        
    # Combine chunks
    df_all = pd.concat(dfs, ignore_index=True)
    
    # Clean and parse columns
    # Expected columns: Applicable At, Applicable For, Data Item, Value, Generated Time, Quality Indicator
    print(f"\nTotal records retrieved: {len(df_all)}")
    
    # Parse dates
    df_all['Date'] = pd.to_datetime(df_all['Applicable For'], format='%d/%m/%Y').dt.date
    df_all['Value'] = pd.to_numeric(df_all['Value'], errors='coerce')
    
    # Clean data
    df_all = df_all.dropna(subset=['Date', 'Value'])
    
    # Sort and deduplicate
    df_all = df_all.sort_values(by='Date')
    df_all = df_all.drop_duplicates(subset=['Date'], keep='last')
    
    # Calculate prices in pence per therm (1 therm = 29.3071 kWh)
    conv_factor = 29.3071
    df_all['Value_p_kWh'] = df_all['Value']
    df_all['Value_p_therm'] = df_all['Value_p_kWh'] * conv_factor
    
    # Select and rename columns for final output
    df_final = df_all[[
        'Date', 
        'Value_p_kWh', 
        'Value_p_therm', 
        'Applicable At', 
        'Generated Time', 
        'Quality Indicator'
    ]].copy()
    
    df_final.columns = [
        'Date', 
        'Price (p/kWh)', 
        'Price (p/therm)', 
        'Published At', 
        'System Generated At', 
        'Quality Indicator'
    ]
    
    # Save to CSV
    output_csv = "nbp_spot_prices_30m.csv"
    df_final.to_csv(output_csv, index=False)
    print(f"Saved cleaned daily prices to {output_csv}")
    
    # Print summary statistics
    min_date = df_final['Date'].min()
    max_date = df_final['Date'].max()
    num_days = len(df_final)
    
    print("\n--- Summary Statistics ---")
    print(f"Date Range: {min_date} to {max_date}")
    print(f"Total Gas Days with Data: {num_days}")
    print(f"Average Price: {df_final['Price (p/kWh)'].mean():.4f} p/kWh ({df_final['Price (p/therm)'].mean():.2f} p/therm)")
    print(f"Min Price: {df_final['Price (p/kWh)'].min():.4f} p/kWh ({df_final['Price (p/therm)'].min():.2f} p/therm) on {df_final.loc[df_final['Price (p/kWh)'].idxmin(), 'Date']}")
    print(f"Max Price: {df_final['Price (p/kWh)'].max():.4f} p/kWh ({df_final['Price (p/therm)'].max():.2f} p/therm) on {df_final.loc[df_final['Price (p/kWh)'].idxmax(), 'Date']}")
    
    latest_row = df_final.iloc[-1]
    print(f"Latest Price (Gas Day {latest_row['Date']}): {latest_row['Price (p/kWh)']:.4f} p/kWh ({latest_row['Price (p/therm)']:.2f} p/therm)")
    
    # Generate Plot
    print("\nGenerating history plot...")
    plt.figure(figsize=(12, 6))
    plt.plot(df_final['Date'], df_final['Price (p/therm)'], color='#1f77b4', linewidth=1.5, label='NBP Daily Spot Price (SAP)')
    plt.title('Daily NBP Spot Prices (System Average Price) - Last 30 Months', fontsize=14, fontweight='bold', pad=15)
    plt.xlabel('Gas Day', fontsize=12)
    plt.ylabel('Price (pence per therm)', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend(loc='upper right')
    plt.tight_layout()
    
    plot_filename = "nbp_spot_prices_plot.png"
    plt.savefig(plot_filename, dpi=150)
    plt.close()
    print(f"Plot saved to {plot_filename}")

if __name__ == "__main__":
    fetch_nbp_data()
