import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import r2_score
from sklearn.feature_selection import r_regression
import math
import seaborn as sns
import icepython as icexl
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
from datetime import datetime, timedelta, date
import eventregistry
import re
from eventregistry import *
from zeep import Client, Settings
import io
from io import StringIO

######################################################## Winter and Summer Graph ##########################################################################

current_date = datetime.date.today()
ed = current_date.strftime('%Y-%m-%d')
sd = (current_date - timedelta(days=365)).strftime('%Y-%m-%d')

symbols = ['GWMS 1!-ICE']
fields = ['volume', 'close',]

my_data = icexl.get_timeseries(symbols, fields, granularity='D', start_date=sd, end_date=ed)

symbols = ['GWMS 2!-ICE']
my_data2 = icexl.get_timeseries(symbols, fields, granularity='D', start_date=sd, end_date=ed)

dates, vols, values = zip(*my_data[1:])  
dates2, vols2, values2 = zip(*my_data2[1:])  

formatted_dates = [date for date in dates]

#sum_volumes = [v + v2 for v, v2 in zip(vols, vols2)]

num_points = len(formatted_dates)
indices = [0, num_points//3, 2*num_points//3, num_points-1]
selected_dates = [formatted_dates[i] for i in indices]

fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=False,  
    vertical_spacing=0.1,  
    row_heights=[0.99, 0.01] 
)


fig.add_trace(go.Scatter(x=formatted_dates, y=values, mode='lines+markers',marker=dict(color='deepskyblue'), name='Summer 26'),row=1, col=1)

fig.add_trace(go.Scatter(x=formatted_dates, y=values2, mode='lines+markers',marker=dict(color='darkviolet'), name='Winter 26'),row=1, col=1)


#fig.add_trace(go.Bar(x=formatted_dates, y=sum_volumes, name='Volumes'),row=2, col=1)

fig.update_layout(title={
        'text': 'Summer and Winter 26 Daily NBP Prices 12 Month Lag',
        'x': 0.5,  # Center the title
        'xanchor': 'center'
    },legend=dict(
        x=0.7,  # Position legend on the chart (left side)
        y=0.98,  # Near the top
        xanchor='left',
        yanchor='top',
        bgcolor='rgba(255, 255, 255, 0.8)', 
        bordercolor='lightgray',
        borderwidth=1
    ),
    title_x=0.5,
    yaxis_title='p/therm',
    showlegend=True,
    xaxis=dict(
        tickmode='array',
        tickvals=[formatted_dates[i] for i in indices],
        ticktext=selected_dates
    ),
       width=1600, 
    height=1600 ,font=dict(size=18)
)

fig.write_image(r"C:\Users\diarmuid.egan\OneDrive - Flogas Ireland\Microsoft Teams Chat Files\Pictures\Daily_tv\SandWNBP.png")

######################################################## Forward Curve WoW ##########################################################################  

current_date = datetime.date.today()
ed = current_date.strftime('%Y-%m-%d')
sd = (current_date - timedelta(days=7)).strftime('%Y-%m-%d')

lom = ['GWM ' + str(i) + '!-ICE' for i in range(1,13)]

my_data = icexl.get_timeseries(lom, ['Last'], granularity='D', start_date=sd, end_date=sd)

last_week_p = my_data[1][1:]

wowf = ['ICE Theoretical Price']

wow_pull = icexl.get_quotes(lom, wowf)

current_theo_p = [i[1] for i in wow_pull[1:]]

def get_next_12_months():
    start_date = datetime.date.today() + datetime.timedelta(days=1)
    
    months_list = []
    current_date = start_date
    for _ in range(12):
        current_month = current_date.month
        current_year = current_date.year
        
        next_month = current_month + 1
        next_year = current_year
        if next_month > 12:
            next_month = 1
            next_year += 1
            
        current_date = datetime.date(next_year, next_month, 1)
        months_list.append(current_date.strftime('%b'))
    return months_list

labels = get_next_12_months()

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=labels, 
    y=last_week_p, 
    mode='lines+markers', 
    name='Last Week',
    marker=dict(color='deepskyblue'),
    line=dict(color='deepskyblue')
))

fig.add_trace(go.Scatter(
    x=labels, 
    y=current_theo_p, 
    mode='lines+markers', 
    name='Current Price',
    marker=dict(color='darkviolet'),
    line=dict(color='darkviolet')
))

fig.update_layout(
    title={
        'text': 'Forward NBP Curve Change Week on Week',
        'x': 0.5,  # Center the title
        'xanchor': 'center'
    },
    xaxis_title='Month',
    yaxis_title='P/th',
    legend=dict(
        x=0.5,  # Position legend on the chart (left side)
        y=0.98,  # Near the top
        xanchor='left',
        yanchor='top',
        bgcolor='rgba(255, 255, 255, 0.8)', 
        bordercolor='lightgray',
        borderwidth=1
    ),
    hovermode='x unified',    width=1600, 
    height=800 ,font=dict(size=18)
)

fig.write_image(r"C:\Users\diarmuid.egan\OneDrive - Flogas Ireland\Microsoft Teams Chat Files\Pictures\Daily_tv\forward_nbp.png")


######################################################## Temp and Wind ########################################################################## 

urls = {'Temp':"https://app.enappsys.com/datadownload?code=isem/weather/tempair/national/history&currency=EUR&delimiter=comma&minavmax=false&pass=211225245243225231229237225238177178183161&res=hh&tag=csv&timezone=WET&user=diarmuid.egan@flogas.ie", 
        'Wind':'https://app.enappsys.com/datadownload?code=isem/elec/renewables/wind/onshore/forecast/history&currency=EUR&delimiter=comma&minavmax=false&pass=211225245243225231229237225238177178183161&res=hh&tag=csv&timezone=WET&user=diarmuid.egan@flogas.ie'}

def gen_url(base):
    current_date = datetime.date.today()
    current_date.strftime('%d/%m/%Y')
    #date_obj = datetime.strptime(input_date, '%d/%m/%Y')
    base = urls[base]
    start_date = (current_date ).strftime('%Y%m%d0000')
    end_date = (current_date + timedelta(days=6)).strftime('%Y%m%d2330')

    
    formatted_url = f"{base}&start={start_date}&end={end_date}"
    return formatted_url

def motel_data(base):
    response = requests.get(gen_url(base))
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data: {response.status_code}")
    
    data = StringIO(response.text)
    df = pd.read_csv(data)

    df['Date (WET)'] = df['Date (WET)'].str.strip('[]')
    df['Date (WET)'] = pd.to_datetime(df['Date (WET)'], format='%d/%m/%Y %H:%M')
    df['Date (WET)'].astype('datetime64[ns]')
    df = df.drop(index=0).reset_index(drop=True)
    
    if base == 'Temp':
        df['LATEST_TEMP'] = df['LATEST'].astype(float)
        df['Date'] = df['Date (WET)']
        return df[['Date','LATEST_TEMP']]
        
    if base == 'Wind':
        df['LATEST_WIND'] = df['LATEST FORECAST (EnAppSys)'].astype(float)
        df['Date'] = df['Date (WET)']
        return df[['Date','LATEST_WIND']]

Wind = motel_data('Wind')
Temp = motel_data('Temp')

temp_summary = Temp.groupby(Temp['Date'].dt.date).agg(
    min_temp=('LATEST_TEMP', 'min'),
    max_temp=('LATEST_TEMP', 'max')
).reset_index()

# Create a timestamp at noon for each day to position the bars
temp_summary['Date'] = pd.to_datetime(temp_summary['Date']) + pd.Timedelta(hours=12)


# --- 3. Create the Plot ---
# Initialize figure with a secondary y-axis
fig = make_subplots(specs=[[{"secondary_y": True}]])

# Add Wind line trace to the primary y-axis
fig.add_trace(
    go.Scatter(
        x=Wind['Date'],
        y=Wind['LATEST_WIND'],
        name='Wind',
        mode='lines',
        line=dict(color='darkviolet')
    ),
    secondary_y=False,
)

# Add Temperature range bars to the secondary y-axis
fig.add_trace(
    go.Bar(
        x=temp_summary['Date'],
        y=temp_summary['max_temp'] - temp_summary['min_temp'], # Bar height is the range
        base=temp_summary['min_temp'], # Start the bar at the min temp
        name='Temp Range',
        marker=dict(color='deepskyblue', opacity=0.6), # Faint color with opacity
        width=1000 * 3600 * 4 # Bar width of 4 hours
    ),
    secondary_y=True,
)

# Add Min/Max labels for each temperature bar using annotations
for i, row in temp_summary.iterrows():
    # Max temp label (top of bar)
    fig.add_annotation(x=row['Date'], y=row['max_temp'], yref="y2",
                       text=f"{row['max_temp']:.1f}", showarrow=False,
                       font=dict(color="black"), yshift=10)
    # Min temp label (bottom of bar)
    fig.add_annotation(x=row['Date'], y=row['min_temp'], yref="y2",
                       text=f"{row['min_temp']:.1f}", showarrow=False,
                       font=dict(color="black"), yshift=-10)

fig.update_layout(
    title={
        'text': 'Wind and Temperatrue Forecast',
        'x': 0.5,
        'xanchor': 'center'
    }, 
    legend_title="Series",
    showlegend=False,    width=1600, 
    height=800,    yaxis=dict(showgrid=False),  
    yaxis2=dict(showgrid=False),    font=dict(size=18))

fig.update_yaxes(title_text="Wind (MW)", secondary_y=False, range=[0, 5000])
fig.update_yaxes(title_text="Temperature (°C)", secondary_y=True)

fig.data[1].showlegend = False

fig.write_image(r"C:\Users\diarmuid.egan\OneDrive - Flogas Ireland\Microsoft Teams Chat Files\Pictures\Daily_tv\wandt.png")

######################################################## Gas and Baseload Table ########################################################################## 

def get_next_24_months():
    start_date = datetime.date.today().replace(day=1)  
    months_list = []
    
    for i in range(1, 25):  
        year = start_date.year + (start_date.month + i - 1) // 12
        month = (start_date.month + i - 1) % 12 + 1
        date = datetime.date(year, month, 1)
        months_list.append(date.strftime('%b-%y'))
    
    return months_list

table_labels = get_next_24_months()

def Baseload_gen(gas, carbon, fx):
    Margin = 4.5
    t1 = gas/(2.93071*0.4913*fx)
    t2 = (0.18404/0.4913)*carbon
    return t2 + t2 + Margin

margin = np.linspace(2, 3.5, 24)

lom24 = ['GWM ' + str(i) + '!-ICE' for i in range(1,25)]

fpf = ['ICE Theoretical Price']

f24_pull = icexl.get_quotes(lom24, fpf)

Gas_forward_theo_p = [i[1] for i in f24_pull[1:]]

CarbonM1 = f24_pull = icexl.get_quotes(['ECF 1!-ICN'], fpf)
CarbonDec27 = f24_pull = icexl.get_quotes(['ECF 13!-ICN'], fpf)

Carbon = np.linspace(float(CarbonM1[1][1]), float(CarbonDec27[1][1]), 24)

GBPEUR = float(icexl.get_quotes(['EURGBP@FXP A0-FX'], ['Last'])[1][1])

Gas = [round(float(Gas_forward_theo_p[i] + margin[i]),1) for i in range(24)]

Baseload = [round(float(Baseload_gen(Gas[i], Carbon[i], GBPEUR)),1) for i in range(24)]

row_labels = ['Period', 'NPB Gas p/th', 'Baseload €/MWh']
table_data = [table_labels, Gas, Baseload]

columns = [['<b>NPB Gas p/th</b>', '<b>Baseload €/MWh</b>']]  # First column: row labels
for i in range(len(table_labels)):
    columns.append([Gas[i], Baseload[i]])

fig = go.Figure(data=[go.Table(
    header=dict(
        values=['<b></b>'] + [f'<b>{label}</b>' for label in table_labels],
        fill_color='rgba(173, 216, 230, 0.5)',
        line_color='black',
        line_width=2,
        align='center',
        font=dict(size=22, color='black', family='Arial')
    ),
    cells=dict(
        values=columns,
        align=['center', 'center'], # This is for horizontal alignment
        fill_color='rgba(173, 216, 230, 0.3)',
        line_color='white',
        line_width=2,
        font=dict(size=22, color='black', family='Arial'),
        height=20)
)])

fig.update_layout(
    width=3200,
    height=600,
    margin=dict(l=20, r=20, t=20, b=20)
)

fig.write_image(r"C:\Users\diarmuid.egan\OneDrive - Flogas Ireland\Microsoft Teams Chat Files\Pictures\Daily_tv\table.png")


######################################################## News ########################################################################## 

er = EventRegistry(apiKey = '1312ee84-a9f9-4fc6-95a4-0ed13b135ec3')

nat_gas_concept_uri = er.getConceptUri("Natural Gas")

q = QueryArticles(conceptUri=nat_gas_concept_uri,lang="eng")

q.setRequestedResult(RequestArticlesInfo(sortBy="date", count=100))

results = er.execQuery(q)

formatted_titles = []

unique_list = []

seen_titles = set()

if results.get('articles') and results['articles'].get('results'):
    for article in results['articles']['results']:
        title = article['title'].strip()
        source_name = article['source']['title']

        if re.search('gas', title, re.IGNORECASE):
            if title not in seen_titles:
                formatted_string = f"{title} - {source_name}"
                unique_list.append(formatted_string)
                seen_titles.add(title)
'''
for line in unique_list:
    print(line)
'''
#news = pd.DataFrame(unique_list)
news = pd.DataFrame({'headline': unique_list})      
news.to_csv(r'C:\Users\diarmuid.egan\OneDrive - Flogas Ireland\Microsoft Teams Chat Files\Pictures\Daily_tv\news.csv')
