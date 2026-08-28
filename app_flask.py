import os
import json
import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, make_response
from datetime import datetime, timedelta

# Import simulate_whatif from run_phase3
from run_phase3 import simulate_whatif, calculate_confidence

app = Flask(__name__)

# Constants
UI_DIR = os.path.join('UiOfProject', 'stitch_stocksense_retail_analytics')

# Load files once
DEMAND_PROFILE_PATH = 'demand_profile.csv'
DECOMPOSITION_PATH = 'decomposition.csv'
PRODUCTS_PATH = 'products.csv'
SALES_PATH = 'sales.csv'
CALENDAR_PATH = 'calendar.csv'
FORECAST_PATH = 'forecast.csv'
ALERTS_PATH = 'alerts.csv'

def load_data():
    profiles = pd.read_csv(DEMAND_PROFILE_PATH)
    decomp = pd.read_csv(DECOMPOSITION_PATH)
    products = pd.read_csv(PRODUCTS_PATH)
    sales = pd.read_csv(SALES_PATH)
    calendar = pd.read_csv(CALENDAR_PATH)
    forecast = pd.read_csv(FORECAST_PATH)
    alerts = pd.read_csv(ALERTS_PATH)
    return profiles, decomp, products, sales, calendar, forecast, alerts

profiles_df, decomp_df, products_df, sales_df, calendar_df, forecast_df, alerts_df = load_data()

# Helper mappings
prod_name_map = dict(zip(products_df['product_id'], products_df['product_name']))
prod_cat_map = dict(zip(products_df['product_id'], products_df['category']))

# Create static directory for uploads
UPLOAD_FOLDER = os.path.join('static', 'product_images')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Premium fallback images from Unsplash by category
CATEGORY_IMAGES = {
    'Staples': 'https://images.unsplash.com/photo-1574316071802-0d684efa7bf5?w=150&auto=format&fit=crop&q=60',
    'Dairy': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=150&auto=format&fit=crop&q=60',
    'Bakery': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=150&auto=format&fit=crop&q=60',
    'Snacks': 'https://images.unsplash.com/photo-1599490659273-e3a72a6216d3?w=150&auto=format&fit=crop&q=60',
    'Beverages': 'https://images.unsplash.com/photo-1534080391025-a7f0e838008f?w=150&auto=format&fit=crop&q=60',
    'Household': 'https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=150&auto=format&fit=crop&q=60',
    'Produce': 'https://images.unsplash.com/photo-1597362925123-77861d3fbac7?w=150&auto=format&fit=crop&q=60',
    'Personal Care': 'https://images.unsplash.com/photo-1526947425960-945c6e72858f?w=150&auto=format&fit=crop&q=60',
    'Health Snacks': 'https://images.unsplash.com/photo-1590080875515-8a3a8dc5735e?w=150&auto=format&fit=crop&q=60'
}
DEFAULT_PRODUCT_IMAGE = 'https://images.unsplash.com/photo-1542838132-92c53300491e?w=150&auto=format&fit=crop&q=60'

def get_product_image_url(pid, category):
    filename = f"{pid}.png"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        mtime = int(os.path.getmtime(filepath))
        return f"/static/product_images/{filename}?t={mtime}"
    return CATEGORY_IMAGES.get(category, DEFAULT_PRODUCT_IMAGE)

# ----------------------------------------------------
# API ENDPOINTS
# ----------------------------------------------------
@app.route('/api/dashboard')
def api_dashboard():
    category = request.args.get('category', 'All Categories')
    
    # Filter products first
    if category != 'All Categories':
        valid_pids = products_df[products_df['category'] == category]['product_id'].tolist()
        filtered_sales = sales_df[sales_df['product_id'].isin(valid_pids)]
        filtered_alerts = alerts_df[alerts_df['product_id'].isin(valid_pids)]
        filtered_profiles = profiles_df[profiles_df['product_id'].isin(valid_pids)]
        filtered_forecast = forecast_df[forecast_df['product_id'].isin(valid_pids)]
    else:
        valid_pids = products_df['product_id'].tolist()
        filtered_sales = sales_df
        filtered_alerts = alerts_df
        filtered_profiles = profiles_df
        filtered_forecast = forecast_df

    # 1. Metrics
    total_sales_units = int(filtered_sales['units_sold'].sum())
    stockout_count = len(filtered_alerts[filtered_alerts['alert_type'] == 'STOCKOUT_RISK'])
    overstock_count = len(filtered_alerts[filtered_alerts['alert_type'] == 'OVERSTOCK'])
    
    # Average confidence score
    conf_scores = []
    for idx, row in filtered_profiles.iterrows():
        score, _, _ = calculate_confidence(row['history_days_available'], row['category_fallback_used'], row['data_quality_flag'])
        conf_scores.append(score)
    avg_conf = int(np.mean(conf_scores) * 100) if conf_scores else 100
    
    # 2. Sales performance table
    # Show last day's sales vs demand
    last_sales = filtered_sales.sort_values('date').groupby('product_id').last()
    sales_performance = []
    # Pick top 5 products of the filtered category
    pids_to_show = [pid for pid in ['P01', 'P02', 'P03', 'P04', 'P05'] if pid in valid_pids]
    if not pids_to_show and valid_pids:
        pids_to_show = valid_pids[:5]
        
    for pid in pids_to_show:
        if pid in last_sales.index:
            units = int(last_sales.loc[pid, 'units_sold'])
        else:
            units = 0
            
        f_rows = filtered_forecast[(filtered_forecast['product_id'] == pid) & (filtered_forecast['date'] == '2028-01-01')]
        if not f_rows.empty:
            pred = int(round(f_rows.iloc[0]['predicted_demand']))
        else:
            pred = 0
            
        p_row = products_df[products_df['product_id'] == pid].iloc[0]
        sales_performance.append({
            'product_id': pid,
            'product_name': p_row['product_name'],
            'units_sold': units,
            'predicted_demand': pred,
            'delta': units - pred,
            'image_url': get_product_image_url(pid, p_row['category'])
        })
        
    # 3. Stockout Alerts list (top 3)
    stockout_alerts = []
    so_df = filtered_alerts[filtered_alerts['alert_type'] == 'STOCKOUT_RISK'].merge(products_df, on='product_id')
    for idx, row in so_df.head(3).iterrows():
        stockout_alerts.append({
            'product_id': row['product_id'],
            'product_name': row['product_name'],
            'recommended_action': row['recommended_action'],
            'urgency_level': row['urgency_level'],
            'image_url': get_product_image_url(row['product_id'], row['category'])
        })
        
    # 4. Overstock Alerts list (top 3)
    overstock_alerts = []
    os_df = filtered_alerts[filtered_alerts['alert_type'] == 'OVERSTOCK'].merge(products_df, on='product_id')
    for idx, row in os_df.head(3).iterrows():
        overstock_alerts.append({
            'product_id': row['product_id'],
            'product_name': row['product_name'],
            'recommended_action': row['recommended_action'],
            'image_url': get_product_image_url(row['product_id'], row['category'])
        })
        
    # 5. Chart data (forecast total summed demand per day)
    forecast_dates = sorted(filtered_forecast['date'].unique())
    chart_dates = []
    chart_values = []
    for d in forecast_dates:
        daily_sum = int(filtered_forecast[filtered_forecast['date'] == d]['predicted_demand'].sum())
        chart_dates.append(pd.to_datetime(d).strftime('%b %d'))
        chart_values.append(daily_sum)
        
    return jsonify({
        'total_sales': f"{total_sales_units:,}",
        'stockout_risk': stockout_count,
        'overstocked': overstock_count,
        'confidence': avg_conf,
        'confidence_label': 'High Reliability' if avg_conf >= 80 else 'Medium Reliability',
        'sales_performance': sales_performance,
        'stockout_alerts': stockout_alerts,
        'overstock_alerts': overstock_alerts,
        'chart_data': {
            'labels': chart_dates[:7],
            'values': chart_values[:7]
        }
    })

@app.route('/api/products')
def api_products():
    prod_list = []
    last_sales = sales_df.sort_values('date').groupby('product_id').last()
    
    for idx, row in products_df.iterrows():
        pid = row['product_id']
        
        # Safe Profile load
        profile_rows = profiles_df[profiles_df['product_id'] == pid]
        if len(profile_rows) > 0:
            profile = profile_rows.iloc[0]
            avg_daily_sales = int(round(profile['baseline_demand']))
            velocity = 'Fast Mover' if 'fast_mover' in profile['fast_or_slow_mover_label'] else 'Slow Mover'
            is_provisional = 'provisional' in profile['fast_or_slow_mover_label']
            conf_score, conf_label, _ = calculate_confidence(
                profile['history_days_available'],
                profile['category_fallback_used'],
                profile['data_quality_flag']
            )
        else:
            avg_daily_sales = 0
            velocity = 'Slow Mover'
            is_provisional = True
            conf_score, conf_label = 0.5, 'Low'
            
        # Safe Stock load
        if pid in last_sales.index:
            curr_stock = int(last_sales.loc[pid, 'stock_available_end_of_day'])
        else:
            curr_stock = 100  # Default stock for new products
        
        prod_list.append({
            'product_id': pid,
            'product_name': row['product_name'],
            'category': row['category'],
            'unit_price': float(row['unit_price']),
            'launch_date': row['launch_date'],
            'current_stock': curr_stock,
            'avg_daily_sales': avg_daily_sales,
            'velocity': velocity,
            'is_provisional': is_provisional,
            'confidence': f"{conf_label} ({int(conf_score * 100)}%)",
            'image_url': get_product_image_url(pid, row['category'])
        })
    return jsonify(prod_list)

@app.route('/api/product/add', methods=['POST'])
def api_add_product():
    global products_df, profiles_df, sales_df, alerts_df, forecast_df, decomp_df, prod_name_map, prod_cat_map
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    product_name = data.get('product_name')
    category = data.get('category')
    unit_price = data.get('unit_price')
    initial_stock = data.get('initial_stock')
    launch_date = data.get('launch_date')
    
    if not all([product_name, category, unit_price is not None, initial_stock is not None, launch_date]):
        return jsonify({'error': 'Missing required fields'}), 400
        
    try:
        # Determine next ID
        pids = products_df['product_id'].str.extract(r'P(\d+)')[0].astype(int)
        next_id_num = pids.max() + 1
        new_pid = f"P{next_id_num:02d}"
        
        # 1. Add to products.csv
        new_product_row = {
            'product_id': new_pid,
            'product_name': product_name,
            'category': category,
            'unit_price': float(unit_price),
            'launch_date': launch_date
        }
        products_df = pd.concat([products_df, pd.DataFrame([new_product_row])], ignore_index=True)
        products_df.to_csv(PRODUCTS_PATH, index=False)
        
        # Update mappings
        prod_name_map[new_pid] = product_name
        prod_cat_map[new_pid] = category
        
        # 2. Add to demand_profile.csv
        new_profile_row = {
            'product_id': new_pid,
            'baseline_demand': 5.0,
            'fast_or_slow_mover_label': 'slow_mover (provisional)',
            'history_days_available': 0,
            'category_fallback_used': True,
            'data_quality_flag': 'Green',
            'weekday_factors': json.dumps({
                'Monday': 1.0, 'Tuesday': 1.0, 'Wednesday': 1.0, 'Thursday': 1.0,
                'Friday': 1.0, 'Saturday': 1.0, 'Sunday': 1.0
            })
        }
        profiles_df = pd.concat([profiles_df, pd.DataFrame([new_profile_row])], ignore_index=True)
        profiles_df.to_csv(DEMAND_PROFILE_PATH, index=False)
        
        # 3. Add to sales.csv (at least one initial row so it shows up in stock list)
        new_sales_row = {
            'date': launch_date,
            'product_id': new_pid,
            'units_sold': 0,
            'stock_available_end_of_day': int(initial_stock),
            'on_promotion': 0
        }
        sales_df = pd.concat([sales_df, pd.DataFrame([new_sales_row])], ignore_index=True)
        sales_df.to_csv(SALES_PATH, index=False)
        
        # 4. Add to alerts.csv
        new_alert_row = {
            'product_id': new_pid,
            'alert_type': 'Normal',
            'urgency_level': 'Low',
            'recommended_action': 'No action required',
            'recommended_quantity': 0,
            'predicted_demand_over_lead_time': 0.0
        }
        alerts_df = pd.concat([alerts_df, pd.DataFrame([new_alert_row])], ignore_index=True)
        alerts_df.to_csv(ALERTS_PATH, index=False)
        
        # 5. Add to forecast.csv (next 14 days)
        start_dt = datetime.strptime(launch_date, '%Y-%m-%d')
        fore_rows = []
        for i in range(1, 15):
            day_dt = start_dt + timedelta(days=i)
            fore_rows.append({
                'date': day_dt.strftime('%Y-%m-%d'),
                'product_id': new_pid,
                'predicted_demand': 5.0,
                'baseline_used': 5.0,
                'day_factor_used': 1.0,
                'event_multiplier_used': 1.0
            })
        forecast_df = pd.concat([forecast_df, pd.DataFrame(fore_rows)], ignore_index=True)
        forecast_df.to_csv(FORECAST_PATH, index=False)
        
        # 6. Add to decomposition.csv (next 14 days component breakdown)
        decomp_rows = []
        for i in range(1, 15):
            day_dt = start_dt + timedelta(days=i)
            decomp_rows.append({
                'date': day_dt.strftime('%Y-%m-%d'),
                'product_id': new_pid,
                'trend_component': 4.0,
                'seasonality_component': 0.8,
                'event_component': 0.2
            })
        decomp_df = pd.concat([decomp_df, pd.DataFrame(decomp_rows)], ignore_index=True)
        decomp_df.to_csv(DECOMPOSITION_PATH, index=False)
        
        return jsonify({'success': True, 'product_id': new_pid})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to save product: {str(e)}'}), 500

@app.route('/api/product/<pid>')
def api_product_detail(pid):
    row = products_df[products_df['product_id'] == pid].iloc[0]
    
    # Safe Profile load
    profile_rows = profiles_df[profiles_df['product_id'] == pid]
    if len(profile_rows) > 0:
        profile = profile_rows.iloc[0]
        avg_daily_sales = int(round(profile['baseline_demand']))
        velocity = 'Fast Mover' if 'fast_mover' in profile['fast_or_slow_mover_label'] else 'Slow Mover'
        is_provisional = 'provisional' in profile['fast_or_slow_mover_label']
        conf_score, conf_label, conf_reason = calculate_confidence(
            profile['history_days_available'],
            profile['category_fallback_used'],
            profile['data_quality_flag']
        )
    else:
        avg_daily_sales = 0
        velocity = 'Slow Mover'
        is_provisional = True
        conf_score, conf_label, conf_reason = 0.5, 'Low', 'Newly added product'
        
    # Safe Stock load
    sales_rows = sales_df[sales_df['product_id'] == pid]
    if len(sales_rows) > 0:
        last_sales = sales_rows.sort_values('date').iloc[-1]
        curr_stock = int(last_sales['stock_available_end_of_day'])
    else:
        curr_stock = 100
        
    # Safe Alert load
    alert_rows = alerts_df[alerts_df['product_id'] == pid]
    if len(alert_rows) > 0:
        alert = alert_rows.iloc[0]
        alert_type = alert['alert_type']
        urgency_level = alert['urgency_level']
        recommended_action = alert['recommended_action']
        recommended_quantity = int(alert['recommended_quantity'])
    else:
        alert_type = 'Normal'
        urgency_level = 'Low'
        recommended_action = 'No immediate action required'
        recommended_quantity = 0
    
    return jsonify({
        'product_id': pid,
        'product_name': row['product_name'],
        'category': row['category'],
        'unit_price': float(row['unit_price']),
        'current_stock': curr_stock,
        'avg_daily_sales': avg_daily_sales,
        'velocity': velocity,
        'is_provisional': is_provisional,
        'confidence': f"{conf_label} ({int(conf_score * 100)}%)",
        'confidence_reason': conf_reason,
        'alert_type': alert_type,
        'urgency_level': urgency_level,
        'recommended_action': recommended_action,
        'recommended_quantity': recommended_quantity,
        'image_url': get_product_image_url(pid, row['category'])
    })

@app.route('/api/product/<pid>/upload_image', methods=['POST'])
def api_upload_image(pid):
    if 'image' not in request.files:
        return jsonify({'error': 'No image file found'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        filename = f"{pid}.png"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        return jsonify({
            'success': True,
            'image_url': get_product_image_url(pid, prod_cat_map.get(pid, 'Staples'))
        })

@app.route('/api/sales/<pid>')
def api_sales_data(pid):
    # Returns history and forecasts for charts
    launch_date = products_df[products_df['product_id'] == pid].iloc[0]['launch_date']
    hist = sales_df[(sales_df['product_id'] == pid) & (sales_df['date'] >= launch_date)].sort_values('date')
    fore = forecast_df[forecast_df['product_id'] == pid].sort_values('date')
    
    hist_list = []
    for idx, row in hist.iterrows():
        hist_list.append({
            'date': str(row['date']),
            'sales': int(row['units_sold'])
        })
        
    fore_list = []
    for idx, row in fore.iterrows():
        fore_list.append({
            'date': str(row['date']),
            'predicted': float(row['predicted_demand']),
            'baseline': float(row['baseline_used']),
            'day_factor': float(row['day_factor_used']),
            'event_multiplier': float(row['event_multiplier_used'])
        })
        
    # Also get decomposition
    decomp = decomp_df[decomp_df['product_id'] == pid].sort_values('date')
    decomp_list = []
    for idx, row in decomp.iterrows():
        decomp_list.append({
            'date': str(row['date']),
            'trend': float(row['trend_component']),
            'seasonality': float(row['seasonality_component']),
            'event': float(row['event_component'])
        })
        
    return jsonify({
        'history': hist_list,
        'forecast': fore_list,
        'decomposition': decomp_list
    })

@app.route('/api/sales/add', methods=['POST'])
def api_add_sale():
    global sales_df
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    pid = data.get('product_id')
    date_str = data.get('date')
    units_sold = data.get('units_sold')
    
    if not all([pid, date_str, units_sold is not None]):
        return jsonify({'error': 'Missing required fields'}), 400
        
    try:
        units_sold = int(units_sold)
        
        # Calculate stock for PID
        sales_pid = sales_df[sales_df['product_id'] == pid].sort_values('date')
        if not sales_pid.empty:
            last_stock = int(sales_pid.iloc[-1]['stock_available_end_of_day'])
        else:
            last_stock = 100
            
        new_stock = max(0, last_stock - units_sold)
        
        new_sale_row = {
            'date': date_str,
            'product_id': pid,
            'units_sold': units_sold,
            'stock_available_end_of_day': new_stock,
            'on_promotion': 0
        }
        
        sales_df = pd.concat([sales_df, pd.DataFrame([new_sale_row])], ignore_index=True)
        sales_df.to_csv(SALES_PATH, index=False)
        
        return jsonify({
            'success': True,
            'message': f'Sale recorded successfully for {pid} on {date_str}!'
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to add sale: {str(e)}'}), 500

@app.route('/api/sales/history')
def api_sales_history():
    category = request.args.get('category', 'All Products')
    pid_filter = request.args.get('product_id', None)
    
    merged = sales_df.merge(products_df[['product_id', 'product_name', 'category']], on='product_id', how='inner')
    
    if pid_filter and pid_filter not in ['All Products', 'All Categories']:
        merged = merged[merged['product_id'] == pid_filter]
    elif category and category not in ['All Products', 'All Categories']:
        merged = merged[merged['category'] == category]
        
    merged = merged.sort_values('date', ascending=False)
    
    history_list = []
    for idx, row in merged.iterrows():
        units = int(row['units_sold'])
        pid = row['product_id']
        price = float(row['unit_price']) if 'unit_price' in row and pd.notna(row['unit_price']) else float(products_df[products_df['product_id'] == pid].iloc[0]['unit_price'])
        total = round(units * price, 2)
        history_list.append({
            'sale_id': f"#{idx+1000}",
            'date': str(row['date']),
            'product_id': pid,
            'product_name': row['product_name'],
            'category': row['category'],
            'units_sold': units,
            'unit_price': price,
            'total_amount': total,
            'status': 'Recorded'
        })
        
    return jsonify(history_list)

@app.route('/api/sales/analysis')
def api_sales_analysis():
    category = request.args.get('category', 'All Categories')
    pid_filter = request.args.get('product_id', None)
    
    merged = sales_df.merge(products_df[['product_id', 'product_name', 'category']], on='product_id', how='inner')
    
    if pid_filter and pid_filter not in ['All Products', 'All Categories']:
        merged = merged[merged['product_id'] == pid_filter]
        filtered_decomp = decomp_df[decomp_df['product_id'] == pid_filter]
    elif category and category not in ['All Products', 'All Categories']:
        merged = merged[merged['category'] == category]
        valid_pids = products_df[products_df['category'] == category]['product_id'].tolist()
        filtered_decomp = decomp_df[decomp_df['product_id'].isin(valid_pids)]
    else:
        filtered_decomp = decomp_df

    # Safely compute price and total
    merged['price'] = merged.apply(lambda r: float(r['unit_price']) if 'unit_price' in r and pd.notna(r['unit_price']) else float(products_df[products_df['product_id'] == r['product_id']].iloc[0]['unit_price']), axis=1)
    merged['total'] = merged['units_sold'] * merged['price']
    daily = merged.groupby('date').agg({'units_sold': 'sum', 'total': 'sum'}).reset_index().sort_values('date')
    
    labels = [pd.to_datetime(d).strftime('%b %d') for d in daily['date']]
    revenue_values = [round(float(v), 2) for v in daily['total']]
    unit_values = [int(u) for u in daily['units_sold']]
    
    # 2. Weekday breakdown
    merged['date_dt'] = pd.to_datetime(merged['date'])
    merged['weekday'] = merged['date_dt'].dt.strftime('%a')
    dow_order = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    dow_sales = merged.groupby('weekday')['units_sold'].sum()
    total_sales_sum = dow_sales.sum()
    
    weekday_breakdown = []
    for day in dow_order:
        val = int(dow_sales.get(day, 0))
        pct = round((val / total_sales_sum * 100), 1) if total_sales_sum > 0 else 0
        weekday_breakdown.append({
            'day': day,
            'units': val,
            'percentage': pct
        })
        
    # 3. Time Series Decomposition components
    decomp_daily = filtered_decomp.groupby('date').agg({
        'trend_component': 'mean',
        'seasonality_component': 'mean',
        'event_component': 'mean'
    }).reset_index().sort_values('date')
    
    decomp_dates = [pd.to_datetime(d).strftime('%b %d') for d in decomp_daily['date']]
    trend = [round(float(v), 2) for v in decomp_daily['trend_component']]
    seasonality = [round(float(v), 2) for v in decomp_daily['seasonality_component']]
    event = [round(float(v), 2) for v in decomp_daily['event_component']]
    
    return jsonify({
        'trend_labels': labels,
        'revenue_values': revenue_values,
        'unit_values': unit_values,
        'weekday_breakdown': weekday_breakdown,
        'decomp_labels': decomp_dates,
        'trend': trend,
        'seasonality': seasonality,
        'event': event
    })


@app.route('/api/alerts')
def api_alerts():
    res = []
    for idx, row in alerts_df.iterrows():
        pid = str(row['product_id'])
        if pid not in prod_name_map:
            continue
        category = prod_cat_map.get(pid, 'Staples')
        
        sales_pid = sales_df[sales_df['product_id'] == pid]
        if not sales_pid.empty:
            curr_stock = int(sales_pid.sort_values('date').iloc[-1]['stock_available_end_of_day'])
        else:
            curr_stock = int(row['current_stock']) if pd.notna(row.get('current_stock')) else 100
            
        pred_demand = float(row['predicted_demand_over_lead_time']) if pd.notna(row.get('predicted_demand_over_lead_time')) else 25.0
        rec_qty = int(row['recommended_quantity']) if pd.notna(row.get('recommended_quantity')) else 0
        
        res.append({
            'product_id': pid,
            'product_name': prod_name_map[pid],
            'category': category,
            'image_url': get_product_image_url(pid, category),
            'alert_type': str(row['alert_type']) if pd.notna(row.get('alert_type')) else 'Normal',
            'current_stock': curr_stock,
            'predicted_demand_over_lead_time': pred_demand,
            'recommended_action': str(row['recommended_action']) if pd.notna(row.get('recommended_action')) else 'Monitor',
            'recommended_quantity': rec_qty,
            'urgency_level': str(row['urgency_level']) if pd.notna(row.get('urgency_level')) else 'Low'
        })
    return jsonify(res)

@app.route('/api/events')
def api_events():
    res_events = []
    event_rows = calendar_df[calendar_df['event'].notna() & (calendar_df['event'] != '')].copy()
    
    event_meta = {
        'Public_Holiday': {'name': 'Public Holiday Promo', 'type': 'Holiday', 'mult': '+15%', 'cats': 'All Categories', 'color': 'primary'},
        'Pongal': {'name': 'Pongal Festival Offer', 'type': 'Festival', 'mult': '+35%', 'cats': 'Staples, Dairy, Sweets', 'color': 'tertiary'},
        'Local_Market': {'name': 'Local Market Fair', 'type': 'Local Event', 'mult': '+20%', 'cats': 'Fresh Produce, Bakery', 'color': 'secondary'},
        'Independence_Day_Weekend': {'name': 'Freedom Weekend Sale', 'type': 'Promotion', 'mult': '+25%', 'cats': 'Beverages, Snacks, Staples', 'color': 'primary'},
        'Diwali': {'name': 'Diwali Super Saver', 'type': 'Festival', 'mult': '+45%', 'cats': 'Sweets, Staples, Personal Care', 'color': 'tertiary'},
        'Deepavali_Weekend': {'name': 'Deepavali Grand Sale', 'type': 'Promotion', 'mult': '+40%', 'cats': 'All Categories', 'color': 'secondary'}
    }
    
    for idx, row in event_rows.iterrows():
        dt_str = str(row['date'])
        ev_key = str(row['event'])
        meta = event_meta.get(ev_key, {
            'name': ev_key.replace('_', ' '),
            'type': 'Event',
            'mult': '+15%',
            'cats': 'Staples, Snacks',
            'color': 'primary'
        })
        
        if dt_str < '2026-08-01':
            status = 'Completed'
        elif dt_str <= '2026-08-31':
            status = 'Active'
        else:
            status = 'Upcoming'
            
        res_events.append({
            'date': dt_str,
            'event_name': meta['name'],
            'event_type': meta['type'],
            'multiplier': meta['mult'],
            'categories': meta['cats'],
            'color': meta['color'],
            'status': status,
            'raw_event': ev_key
        })
        
    return jsonify({
        'events': res_events,
        'summary': {
            'active_promos': len([e for e in res_events if e['status'] == 'Active']),
            'upcoming_promos': len([e for e in res_events if e['status'] == 'Upcoming']),
            'avg_demand_lift': '+28.5%',
            'top_performing': 'Diwali Super Saver (+45%)',
            'current_date': '2026-08-28'
        }
    })

@app.route('/api/whatif')
def api_whatif():
    pid = request.args.get('product_id', 'P01')
    date = request.args.get('date', '2028-01-13')
    override = request.args.get('override_event', None)
    if override == 'None' or override == '':
        override = None
        
    sim_demand = simulate_whatif(pid, date, override_event=override)
    
    # Get original forecast
    orig_row = forecast_df[(forecast_df['product_id'] == pid) & (forecast_df['date'] == date)]
    orig_demand = float(orig_row['predicted_demand'].iloc[0]) if len(orig_row) > 0 else 0.0
    
    # Calculate factors used in simulator
    profile_row = profiles_df[profiles_df['product_id'] == pid].iloc[0]
    base = float(profile_row['baseline_demand'])
    
    d = datetime.strptime(date, '%Y-%m-%d')
    dow = d.strftime('%A')
    dow_factors = json.loads(profile_row['weekday_factors'])
    dow_f = float(dow_factors.get(dow, 1.0))
    
    event_mult = sim_demand / (base * dow_f) if (base * dow_f) > 0 else 1.0
    
    # Get product details for simulation calculations
    prod_row = products_df[products_df['product_id'] == pid].iloc[0]
    unit_price = float(prod_row['unit_price'])
    
    last_sales = sales_df[sales_df['product_id'] == pid].sort_values('date').iloc[-1]
    current_stock = int(last_sales['stock_available_end_of_day'])
    
    # Calculate simulated metrics
    original_revenue = orig_demand * unit_price
    simulated_revenue = sim_demand * unit_price
    
    original_stockout_risk = min(100, max(5, int((orig_demand / max(1, current_stock)) * 100)))
    simulated_stockout_risk = min(100, max(5, int((sim_demand / max(1, current_stock)) * 100)))
    
    return jsonify({
        'product_id': pid,
        'date': date,
        'day_of_week': dow,
        'simulated_demand': sim_demand,
        'original_demand': orig_demand,
        'baseline': base,
        'day_factor': dow_f,
        'event_multiplier': round(event_mult, 4),
        'unit_price': unit_price,
        'current_stock': current_stock,
        'original_revenue': original_revenue,
        'simulated_revenue': simulated_revenue,
        'original_stockout_risk': original_stockout_risk,
        'simulated_stockout_risk': simulated_stockout_risk
    })

# ----------------------------------------------------
# PAGE SERVING ROUTES
# ----------------------------------------------------
@app.route('/')
def dashboard():
    return serve_page('executive_dashboard', 'dashboard')

@app.route('/products')
def products():
    return serve_page('product_inventory_catalog', 'products')

@app.route('/sales')
def sales():
    return serve_page('sales_data_analysis', 'sales')

@app.route('/forecast')
def forecast():
    return serve_page('demand_forecast_analysis', 'forecast')

@app.route('/inventory')
def inventory():
    return serve_page('inventory_urgency_list', 'inventory')

@app.route('/events')
def events():
    return serve_page('events_promotions_calendar', 'events')

@app.route('/whatif')
def whatif():
    return serve_page('what_if_simulator_environment', 'whatif')

def serve_page(folder_name, active_page):
    path = os.path.join(UI_DIR, folder_name, 'code.html')
    if not os.path.exists(path):
        return f"File not found: {path}", 404
        
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
        
    # Inject JavaScript and CSS enhancements without changing the design
    html = inject_common_js(html, active_page)
    
    response = make_response(html)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

# ----------------------------------------------------
# JAVASCRIPT INJECTION LOGIC
# ----------------------------------------------------
def inject_common_js(html_content, active_page):
    script = f"""
    <!-- Add Chart.js for smooth interactive charts -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
    document.addEventListener("DOMContentLoaded", function() {{
        // 1. Rewrite sidebar and header links dynamically and attach navigation click handlers
        const navLinks = document.querySelectorAll("aside a, nav a");
        navLinks.forEach(link => {{
            if (link.classList.contains("tab-btn") || (link.getAttribute("onclick") && link.getAttribute("onclick").includes("switchTab"))) return;
            const text = link.textContent.trim();
            let targetUrl = null;
            let pageKey = null;
            
            if (text.includes("Dashboard")) {{ targetUrl = "/"; pageKey = "dashboard"; }}
            else if (text.includes("Products")) {{ targetUrl = "/products"; pageKey = "products"; }}
            else if (text.includes("Sales")) {{ targetUrl = "/sales"; pageKey = "sales"; }}
            else if (text.includes("Demand Forecast")) {{ targetUrl = "/forecast"; pageKey = "forecast"; }}
            else if (text.includes("Inventory")) {{ targetUrl = "/inventory"; pageKey = "inventory"; }}
            else if (text.includes("Events & Promotions")) {{ targetUrl = "/events"; pageKey = "events"; }}
            else if (text.includes("What-If Simulator")) {{ targetUrl = "/whatif"; pageKey = "whatif"; }}
            
            if (targetUrl) {{
                link.href = targetUrl;
                setupLinkState(link, "{active_page}" === pageKey);
                link.addEventListener("click", function(e) {{
                    e.preventDefault();
                    window.location.href = targetUrl;
                }});
            }}
        }});
        
        function setupLinkState(link, isActive) {{
            if (isActive) {{
                link.className = "flex items-center gap-3 px-4 py-3 rounded-DEFAULT border-l-4 border-primary bg-primary/10 text-primary font-semibold cursor-pointer active:scale-95 duration-150";
                if (link.querySelector("span")) {{
                    link.querySelector("span").style.fontVariationSettings = "'FILL' 1";
                }}
            }} else {{
                link.className = "flex items-center gap-3 px-4 py-3 rounded-DEFAULT border-l-4 border-transparent text-on-surface-variant hover:bg-surface-container-low hover:text-primary transition-colors cursor-pointer active:scale-95 duration-150";
                if (link.querySelector("span")) {{
                    link.querySelector("span").style.fontVariationSettings = "'FILL' 0";
                }}
            }}
        }}
        
        // 2. Bind layout header info
        const headerTitle = document.querySelector("header h2");
        if (headerTitle) {{
            headerTitle.textContent = "GroceryStore Pro Analytics - Westside Market";
        }}
        
        const headerDate = document.querySelector("header span:nth-child(2)");
        if (headerDate) {{
            const today = new Date();
            const options = {{ month: 'short', day: 'numeric', year: 'numeric' }};
            headerDate.innerHTML = `<span class="material-symbols-outlined text-[16px]">calendar_today</span> ${{today.toLocaleDateString("en-US", options)}}`;
        }}
        
        // 3. Load page-specific data
        loadPageData();
    }});
    
    // Page Data Loaders
    function loadPageData() {{
        const page = "{active_page}";
        if (page === "dashboard") {{
            loadDashboardData();
        }} else if (page === "products") {{
            loadProductsData();
        }} else if (page === "sales") {{
            loadSalesData();
        }} else if (page === "forecast") {{
            loadForecastData();
        }} else if (page === "inventory") {{
            loadInventoryData();
        }} else if (page === "events") {{
            loadEventsData();
        }} else if (page === "whatif") {{
            loadWhatIfData();
        }}
    }}
    
    // ----------------------------------------------------
    // DASHBOARD PAGE BINDINGS
    // ----------------------------------------------------
    function loadDashboardData(category = "All Categories") {{
        fetch('/api/dashboard?category=' + encodeURIComponent(category))
        .then(r => r.json())
        .then(data => {{
            // KPI Metrics
            const kpiCards = document.querySelectorAll("div.grid-cols-1.md\\\\:grid-cols-2.lg\\\\:grid-cols-4 > div");
            if (kpiCards.length >= 4) {{
                kpiCards[0].querySelector("span.font-h1").textContent = data.total_sales;
                kpiCards[1].querySelector("span.font-h1").textContent = data.stockout_risk;
                kpiCards[2].querySelector("span.font-h1").textContent = data.overstocked;
                kpiCards[3].querySelector("span.font-h1").textContent = data.confidence + '%';
                kpiCards[3].querySelector("div.bg-primary").style.width = data.confidence + '%';
                kpiCards[3].querySelector("span.text-on-surface-variant").textContent = data.confidence_label;
            }}
            
            // Sales Performance Table
            const tbody = document.querySelector("tbody.font-data-tabular");
            if (tbody) {{
                tbody.innerHTML = "";
                data.sales_performance.forEach((item, index) => {{
                    const bgClass = index % 2 === 1 ? 'bg-[#F6F7F9]' : '';
                    const deltaColor = item.delta >= 0 ? 'text-primary' : 'text-error';
                    const deltaIcon = item.delta >= 0 ? 'arrow_upward' : 'arrow_downward';
                    tbody.innerHTML += `
                        <tr class="${{bgClass}} border-b border-[#E3E6EA] hover:bg-surface-container-low transition-colors cursor-pointer" onclick="window.location.href='/products#' + '${{item.product_id}}'">
                            <td class="px-6 py-3 font-body-md text-on-surface flex items-center gap-3">
                                <div class="w-8 h-8 rounded overflow-hidden shrink-0 border border-outline-variant shadow-sm">
                                    <img src="${{item.image_url}}" class="w-full h-full object-cover" />
                                </div>
                                <span>${{item.product_name}}</span>
                            </td>
                            <td class="px-6 py-3 text-right font-data-tabular">${{item.units_sold}}</td>
                            <td class="px-6 py-3 text-right text-on-surface-variant font-data-tabular">${{item.predicted_demand}}</td>
                            <td class="px-6 py-3 text-right ${{deltaColor}} font-semibold flex items-center justify-end gap-1">
                                <span class="material-symbols-outlined text-[16px]">${{deltaIcon}}</span> ${{Math.abs(item.delta)}}
                            </td>
                        </tr>
                    `;
                }});
            }}
            
            // Stock-out Alerts
            const soHeader = document.querySelector("h3.text-error + span");
            if (soHeader) soHeader.textContent = data.stockout_risk + " CRITICAL";
            const stockoutContainer = document.querySelector("h3.text-error")?.closest("div.bg-white, div.bg-surface-container-lowest")?.querySelector("div.p-padding-card");
            if (stockoutContainer) {{
                stockoutContainer.innerHTML = "";
                data.stockout_alerts.forEach(alert => {{
                    stockoutContainer.innerHTML += `
                        <div class="border border-[#E3E6EA] border-l-4 border-l-error rounded p-3 flex justify-between items-center bg-error/5 hover:bg-error/10 transition-colors cursor-pointer" onclick="window.location.href='/products#' + '${{alert.product_id}}'">
                            <div class="flex items-center gap-3 flex-1">
                                <div class="w-10 h-10 rounded overflow-hidden shrink-0 border border-outline-variant shadow-sm">
                                    <img src="${{alert.image_url}}" class="w-full h-full object-cover" />
                                </div>
                                <div class="flex-1">
                                    <p class="font-body-md text-body-md font-semibold text-on-surface">${{alert.product_name}}</p>
                                    <p class="font-body-sm text-body-sm text-on-surface-variant">${{alert.recommended_action}}</p>
                                </div>
                            </div>
                            <button class="bg-white border border-[#E3E6EA] text-on-surface px-3 py-1.5 rounded text-body-sm font-semibold hover:bg-surface transition-colors shadow-sm" onclick="event.stopPropagation(); window.location.href='/products#' + '${{alert.product_id}}'">Reorder</button>
                        </div>
                    `;
                }});
            }}
            
            // Overstock Alerts
            const osHeader = document.querySelector("h3[class*='8B5CF6'] + span");
            if (osHeader) osHeader.textContent = data.overstocked + " REVIEW";
            const overstockContainer = document.querySelector("h3[class*='8B5CF6']")?.closest("div.bg-white, div.bg-surface-container-lowest")?.querySelector("div.p-padding-card");
            if (overstockContainer) {{
                overstockContainer.innerHTML = "";
                data.overstock_alerts.forEach(alert => {{
                    overstockContainer.innerHTML += `
                        <div class="border border-[#E3E6EA] border-l-4 border-l-[#8B5CF6] rounded p-3 flex justify-between items-center bg-[#8B5CF6]/5 hover:bg-[#8B5CF6]/10 transition-colors cursor-pointer" onclick="window.location.href='/products#' + '${{alert.product_id}}'">
                            <div class="flex items-center gap-3 flex-1">
                                <div class="w-10 h-10 rounded overflow-hidden shrink-0 border border-outline-variant shadow-sm">
                                    <img src="${{alert.image_url}}" class="w-full h-full object-cover" />
                                </div>
                                <div class="flex-1">
                                    <p class="font-body-md text-body-md font-semibold text-on-surface">${{alert.product_name}}</p>
                                    <p class="font-body-sm text-body-sm text-on-surface-variant">${{alert.recommended_action}}</p>
                                </div>
                            </div>
                            <button class="bg-white border border-[#E3E6EA] text-on-surface px-3 py-1.5 rounded text-body-sm font-semibold hover:bg-surface transition-colors shadow-sm" onclick="event.stopPropagation(); window.location.href='/products#' + '${{alert.product_id}}'">Details</button>
                        </div>
                    `;
                }});
            }}
            
            // Render interactive dashboard chart
            const chartHeader = Array.from(document.querySelectorAll("h3")).find(h => h.textContent.includes("Predicted Demand"));
            if (chartHeader) {{
                const chartArea = chartHeader.closest("div.bg-white, div.bg-surface-container-lowest").querySelector("div.p-padding-card");
                chartArea.className = "p-padding-card";
                chartArea.style.height = "260px";
                chartArea.innerHTML = '<canvas id="dashboardChart" style="width: 100%; height: 100%;"></canvas>';
                
                const ctx = document.getElementById('dashboardChart').getContext('2d');
                if (window.dashboardChartInstance) {{
                    window.dashboardChartInstance.destroy();
                }}
                window.dashboardChartInstance = new Chart(ctx, {{
                    type: 'line',
                    data: {{
                        labels: data.chart_data.labels,
                        datasets: [{{
                            label: category + ' Forecast',
                            data: data.chart_data.values,
                            borderColor: '#003735',
                            backgroundColor: 'rgba(0, 55, 53, 0.1)',
                            borderWidth: 2.5,
                            fill: true,
                            tension: 0.3,
                            pointRadius: 4,
                            pointBackgroundColor: '#003735'
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {{
                            x: {{ grid: {{ display: false }} }},
                            y: {{ beginAtZero: true }}
                        }},
                        plugins: {{
                            legend: {{ display: false }}
                        }}
                    }}
                }});
            }}
            
            // Bind category change listener on dashboard
            const dashboardCatSelect = document.getElementById("dashboardCategorySelect");
            if (dashboardCatSelect && !dashboardCatSelect.hasListener) {{
                dashboardCatSelect.hasListener = true;
                dashboardCatSelect.addEventListener("change", function() {{
                    loadDashboardData(this.value);
                }});
            }}
        }});
    }}
    
    // ----------------------------------------------------
    // PRODUCTS PAGE BINDINGS
    // ----------------------------------------------------
    let allProductsData = [];
    function loadProductsData(highlightPid) {{
        // Setup Search and Filters
        const searchInput = document.querySelector("input[placeholder*='Search']");
        const categorySelect = document.querySelector("select");
        
        if (searchInput && !searchInput.hasListener) {{
            searchInput.hasListener = true;
            searchInput.addEventListener("input", filterProductsList);
        }}
        if (categorySelect && !categorySelect.hasListener) {{
            categorySelect.hasListener = true;
            categorySelect.addEventListener("change", filterProductsList);
        }}
        
        fetch('/api/products')
        .then(r => r.json())
        .then(data => {{
            allProductsData = data;
            
            // Populate category select dynamically with all unique categories
            if (categorySelect) {{
                const currentVal = categorySelect.value || "All Categories";
                const uniqueCats = Array.from(new Set(data.map(p => p.category))).sort();
                categorySelect.innerHTML = `<option value="All Categories">All Categories</option>` + 
                    uniqueCats.map(c => `<option value="${{c}}" ${{c === currentVal ? 'selected' : ''}}>${{c}}</option>`).join('');
            }}
            
            renderProductsList(data, highlightPid);
            
            // Check if there is an active hash deep link or highlightPid on load
            const targetPid = highlightPid || (window.location.hash ? window.location.hash.substring(1) : null);
            if (targetPid) {{
                setTimeout(() => {{
                    showProductDetails(targetPid);
                    scrollToProductRow(targetPid);
                }}, 150);
            }}
        }});
        
        // Listen for hashchange events for seamless deep linking navigation
        if (!window.hasHashListener) {{
            window.hasHashListener = true;
            window.addEventListener("hashchange", function() {{
                if (window.location.hash) {{
                    const pid = window.location.hash.substring(1);
                    showProductDetails(pid);
                    scrollToProductRow(pid);
                }}
            }});
        }}
    }}
    
    function scrollToProductRow(pid) {{
        const row = document.getElementById("product-row-" + pid);
        if (row) {{
            row.scrollIntoView({{ behavior: "smooth", block: "center" }});
            row.classList.add("bg-primary/20", "ring-2", "ring-primary");
            setTimeout(() => {{
                row.classList.remove("bg-primary/20", "ring-2", "ring-primary");
            }}, 3500);
        }}
    }}
    
    function renderProductsList(products, highlightPid) {{
        const tbody = document.querySelector("tbody");
        if (!tbody) return;
        tbody.innerHTML = "";
        
        products.forEach((prod, index) => {{
            const isHighlighted = highlightPid && prod.product_id === highlightPid;
            const bgClass = isHighlighted ? 'bg-primary/20 ring-2 ring-primary' : (index % 2 === 1 ? 'bg-[#F6F7F9]' : '');
            const velocityClass = prod.velocity === 'Fast Mover' 
                ? 'bg-primary/15 text-primary border border-primary/20' 
                : 'bg-outline-variant/30 text-on-surface-variant border border-outline-variant';
                
            tbody.innerHTML += `
                <tr id="product-row-${{prod.product_id}}" class="border-b border-outline-variant hover:bg-surface-container-low transition-colors cursor-pointer ${{bgClass}}" onclick="showProductDetails('${{prod.product_id}}')">
                    <td class="py-2 px-4 flex items-center gap-3">
                        <div class="w-8 h-8 rounded overflow-hidden shrink-0 border border-outline-variant shadow-sm">
                            <img src="${{prod.image_url}}" class="w-full h-full object-cover" />
                        </div>
                        <div>
                            <div class="font-semibold text-on-surface">${{prod.product_name}}</div>
                            <div class="font-data-tabular text-data-tabular text-on-surface-variant text-[12px]">ID: ${{prod.product_id}}</div>
                        </div>
                    </td>
                    <td class="py-2 px-4 text-on-surface-variant">${{prod.category}}</td>
                    <td class="py-2 px-4 font-data-tabular text-data-tabular text-right text-on-surface">${{prod.current_stock}} units</td>
                    <td class="py-2 px-4 font-data-tabular text-data-tabular text-right text-on-surface">${{prod.avg_daily_sales}} units</td>
                    <td class="py-2 px-4 text-center">
                        <span class="inline-flex items-center px-2 py-0.5 rounded-full font-label-caps text-[10px] ${{velocityClass}}">${{prod.velocity}}</span>
                    </td>
                    <td class="py-2 px-4 text-center">
                        <span class="inline-flex items-center px-2 py-0.5 rounded-full font-label-caps text-[10px] bg-secondary/15 text-secondary border border-secondary/20">${{prod.confidence}}</span>
                    </td>
                </tr>
            `;
        }});
        
        // Update pagination product count label accurately
        const paginationLabel = Array.from(document.querySelectorAll("span")).find(s => s.textContent.includes("Showing") || s.textContent.includes("products") || s.textContent.includes("SKU"));
        if (paginationLabel) {{
            paginationLabel.textContent = `Showing 1 to ${{products.length}} of ${{products.length}} products`;
        }}
    }}
    
    function filterProductsList() {{
        const query = document.querySelector("input[placeholder*='Search']").value.toLowerCase();
        const cat = document.querySelector("select").value;
        
        let filtered = allProductsData;
        if (query) {{
            filtered = filtered.filter(p => p.product_name.toLowerCase().includes(query) || p.product_id.toLowerCase().includes(query));
        }}
        if (cat && cat !== "All Categories" && cat !== "Status: All") {{
            filtered = filtered.filter(p => p.category === cat || (cat === "New" && p.product_id >= "P21") || (cat === "Established" && p.product_id < "P21"));
        }}
        renderProductsList(filtered);
    }}
    
    // Global show detail panel mapping
    window.showProductDetails = function(pid) {{
        const panel = document.getElementById("detail-panel");
        if (!panel) return;
        
        fetch('/api/product/' + pid)
        .then(r => r.json())
        .then(data => {{
            panel.classList.remove("hidden");
            panel.classList.add("flex");
            
            // Fill details
            panel.querySelector("h3 + div").textContent = `ID: ${{data.product_id}}`;
            panel.querySelector("div.text-lg").textContent = data.product_name;
            panel.querySelector("span.text-on-surface-variant").textContent = data.category;
            panel.querySelector("div.text-on-surface.font-semibold").innerHTML = `${{data.current_stock}} <span class="text-xs font-normal text-on-surface-variant">units</span>`;
            
            // Detail product image binding
            const detailImg = document.getElementById("detail-product-img");
            const iconContainer = document.getElementById("detail-product-icon-container");
            if (data.image_url) {{
                detailImg.src = data.image_url;
                detailImg.classList.remove("hidden");
                iconContainer.classList.add("hidden");
            }} else {{
                detailImg.classList.add("hidden");
                iconContainer.classList.remove("hidden");
            }}
            
            // Update panel sections
            const stats = panel.querySelectorAll("div.grid-cols-2 > div");
            stats[0].querySelector("div.text-on-surface").innerHTML = `${{data.current_stock}} <span class="text-xs font-normal text-on-surface-variant">units</span>`;
            stats[1].querySelector("div.text-on-surface").innerHTML = `${{data.avg_daily_sales}} <span class="text-xs font-normal text-on-surface-variant">units/day</span>`;
            
            // Badges
            const velocityBadge = Array.from(panel.querySelectorAll("span.font-label-caps")).find(el => el.textContent.includes("Mover") || el.textContent.includes("Fast") || el.textContent.includes("Slow")) || panel.querySelector("span.font-label-caps");
            if (velocityBadge) {{
                velocityBadge.textContent = data.velocity;
            }}
            
            // Alert recommendations
            const alertText = panel.querySelector("p.text-on-surface-variant");
            if (alertText) {{
                alertText.innerHTML = `
                    <strong>Status:</strong> ${{data.alert_type}}<br/>
                    <strong>Urgency:</strong> ${{data.urgency_level}}<br/>
                    <strong>Recommendation:</strong> ${{data.recommended_action}}<br/>
                    <strong>Confidence Details:</strong> ${{data.confidence_reason}}
                `;
            }}
            
            // Load sales history and forecast for sparkline
            fetch('/api/sales/' + pid)
            .then(r => r.json())
            .then(salesData => {{
                const sparklineCanvas = document.getElementById("detailSparklineChart");
                if (sparklineCanvas) {{
                    // Destroy previous chart if it exists
                    if (window.detailSparklineInstance) {{
                        window.detailSparklineInstance.destroy();
                    }}
                    
                    const historySlice = salesData.history.slice(-14);
                    const labels = [...historySlice.map(h => h.date), ...salesData.forecast.map(f => f.date)];
                    const salesValues = [...historySlice.map(h => h.sales), ...Array(salesData.forecast.length).fill(null)];
                    
                    const lastHistVal = historySlice.length > 0 ? historySlice[historySlice.length - 1].sales : (salesData.forecast.length > 0 ? salesData.forecast[0].predicted : 0);
                    const paddingCount = Math.max(0, historySlice.length - 1);
                    const forecastValues = [...Array(paddingCount).fill(null), lastHistVal, ...salesData.forecast.map(f => f.predicted)];
                    
                    const ctx = sparklineCanvas.getContext('2d');
                    window.detailSparklineInstance = new Chart(ctx, {{
                        type: 'line',
                        data: {{
                            labels: labels,
                            datasets: [
                                {{
                                    label: 'Historical Sales',
                                    data: salesValues,
                                    borderColor: '#707978',
                                    borderWidth: 1.5,
                                    pointRadius: 0,
                                    fill: false
                                }},
                                {{
                                    label: 'Forecast',
                                    data: forecastValues,
                                    borderColor: '#003735',
                                    borderWidth: 2,
                                    borderDash: [3, 3],
                                    pointRadius: 0,
                                    fill: false
                                }}
                            ]
                        }},
                        options: {{
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {{
                                x: {{ display: true, ticks: {{ font: {{ size: 10 }} }} }},
                                y: {{ 
                                    display: true, 
                                    ticks: {{ 
                                        font: {{ size: 10 }},
                                        callback: function(val) {{ return val + ' units'; }}
                                    }} 
                                }}
                            }},
                            plugins: {{
                                legend: {{ display: true, position: 'top' }},
                                tooltip: {{
                                    callbacks: {{
                                        label: function(ctx) {{
                                            return ctx.dataset.label + ': ' + ctx.parsed.y + ' units';
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }});
                }}
            }});
        }});
    }}
    
    window.togglePanel = function(sku) {{
        const panel = document.getElementById("detail-panel");
        if (panel) {{
            panel.classList.add("hidden");
            panel.classList.remove("flex");
        }}
    }}
    
    // Dynamic Product Image Upload handler
    window.uploadProductImage = function(input) {{
        const file = input.files[0];
        if (!file) return;
        
        const panel = document.getElementById("detail-panel");
        if (!panel) return;
        const pidText = panel.querySelector("h3 + div").textContent;
        const pid = pidText.replace("ID:", "").trim();
        
        const formData = new FormData();
        formData.append("image", file);
        
        fetch(`/api/product/${{pid}}/upload_image`, {{
            method: "POST",
            body: formData
        }})
        .then(r => r.json())
        .then(res => {{
            if (res.success) {{
                const detailImg = document.getElementById("detail-product-img");
                const iconContainer = document.getElementById("detail-product-icon-container");
                detailImg.src = res.image_url;
                detailImg.classList.remove("hidden");
                iconContainer.classList.add("hidden");
                loadProductsData();
            }}
        }});
    }}
    
    // ----------------------------------------------------
    // SALES ANALYSIS PAGE BINDINGS
    // ----------------------------------------------------
    function loadSalesData() {{
        // 1. Setup product dropdown for Add Sale form
        fetch('/api/products')
        .then(r => r.json())
        .then(products => {{
            const addProductSelect = document.getElementById("sale-product-select");
            if (addProductSelect) {{
                addProductSelect.innerHTML = products.map(p => `<option value="${{p.product_id}}">${{p.product_id}} - ${{p.product_name}} (₹${{p.unit_price}})</option>`).join('');
                
                // Update unit price field automatically when product changes
                addProductSelect.addEventListener("change", function() {{
                    const selectedProd = products.find(p => p.product_id === this.value);
                    const priceInput = document.getElementById("sale-unit-price");
                    if (selectedProd && priceInput) {{
                        priceInput.value = selectedProd.unit_price;
                    }}
                }});
                
                // Trigger initial price sync
                if (products.length > 0) {{
                    const priceInput = document.getElementById("sale-unit-price");
                    if (priceInput) priceInput.value = products[0].unit_price;
                }}
            }}
            
            // 2. Setup Category filter for Historical Sales tab
            const historyFilterSelect = document.querySelector("#tab-history select");
            if (historyFilterSelect) {{
                const cats = ["All Categories", ...new Set(products.map(p => p.category))].sort();
                historyFilterSelect.innerHTML = cats.map(c => `<option value="${{c}}">${{c}}</option>`).join('') +
                    `<optgroup label="Products">` +
                    products.map(p => `<option value="${{p.product_id}}">${{p.product_id}} - ${{p.product_name}}</option>`).join('') +
                    `</optgroup>`;
                    
                if (!historyFilterSelect.hasListener) {{
                    historyFilterSelect.hasListener = true;
                    historyFilterSelect.addEventListener("change", function() {{
                        loadHistoricalSalesTable(this.value);
                        loadSalesAnalysisCharts(this.value);
                    }});
                }}
            }}
            
            // Initial load
            const currentFilter = historyFilterSelect ? historyFilterSelect.value : "All Categories";
            loadHistoricalSalesTable(currentFilter);
            loadSalesAnalysisCharts(currentFilter);
        }});
        
        // 3. Bind Add Sale submit form
        const addSaleForm = document.querySelector("#tab-add form");
        if (addSaleForm && !addSaleForm.hasListener) {{
            addSaleForm.hasListener = true;
            addSaleForm.addEventListener("submit", function(e) {{
                e.preventDefault();
                submitAddSale();
            }});
        }}
    }}
    
    window.submitAddSale = function() {{
        const pidSelect = document.getElementById("sale-product-select");
        const dateInput = document.getElementById("sale-date");
        const qtyInput = document.getElementById("sale-qty");
        const priceInput = document.getElementById("sale-unit-price");
        
        if (!pidSelect || !dateInput || !qtyInput) return;
        
        const payload = {{
            product_id: pidSelect.value,
            date: dateInput.value,
            units_sold: parseInt(qtyInput.value, 10),
            unit_price: parseFloat(priceInput.value || 0)
        }};
        
        fetch('/api/sales/add', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(payload)
        }})
        .then(r => r.json())
        .then(res => {{
            if (res.success) {{
                alert(res.message || "Sale recorded successfully!");
                qtyInput.value = "1";
                // Refresh historical table and analysis charts
                const filterSelect = document.querySelector("#tab-history select");
                const currentFilter = filterSelect ? filterSelect.value : "All Categories";
                loadHistoricalSalesTable(currentFilter);
                loadSalesAnalysisCharts(currentFilter);
            }} else {{
                alert(res.error || "Failed to record sale.");
            }}
        }})
        .catch(err => alert("Network error while submitting sale."));
    }}
    
    function loadHistoricalSalesTable(categoryOrPid = "All Categories") {{
        let url = '/api/sales/history';
        if (categoryOrPid && categoryOrPid !== "All Categories" && categoryOrPid !== "All Products") {{
            if (categoryOrPid.startsWith("P")) {{
                url += '?product_id=' + encodeURIComponent(categoryOrPid);
            }} else {{
                url += '?category=' + encodeURIComponent(categoryOrPid);
            }}
        }}
        
        fetch(url)
        .then(r => r.json())
        .then(records => {{
            const tbody = document.querySelector("#tab-history tbody");
            if (!tbody) return;
            
            const displayRecords = records.slice(0, 100);
            const rowsHtml = displayRecords.map((row, idx) => {{
                const bgClass = idx % 2 === 1 ? 'bg-surface-bright' : '';
                return `
                    <tr class="${{bgClass}} border-b border-outline-variant hover:bg-surface-container-low/50 transition-colors h-[40px]">
                        <td class="px-4 py-2 text-on-surface-variant font-data-tabular">${{row.sale_id}}</td>
                        <td class="px-4 py-2 font-data-tabular">${{row.date}}</td>
                        <td class="px-4 py-2 font-body-md text-body-md font-medium">${{row.product_name}} <span class="text-xs text-on-surface-variant">(${{row.category}})</span></td>
                        <td class="px-4 py-2 text-right font-data-tabular">${{row.units_sold}} units</td>
                        <td class="px-4 py-2 text-right font-data-tabular">₹${{row.unit_price.toFixed(2)}}</td>
                        <td class="px-4 py-2 text-right font-data-tabular font-medium">₹${{row.total_amount.toFixed(2)}}</td>
                        <td class="px-4 py-2 text-center">
                            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-wide uppercase bg-primary/15 text-primary">Recorded</span>
                        </td>
                    </tr>
                `;
            }}).join('');
            
            tbody.innerHTML = rowsHtml;
            
            const paginationSpan = document.querySelector("#tab-history .p-3.border-t span");
            if (paginationSpan) {{
                paginationSpan.textContent = `Showing 1-${{displayRecords.length}} of ${{records.length}} records`;
            }}
        }});
    }}
    
    function loadSalesAnalysisCharts(categoryOrPid = "All Categories") {{
        let url = '/api/sales/analysis';
        if (categoryOrPid && categoryOrPid !== "All Categories" && categoryOrPid !== "All Products") {{
            if (categoryOrPid.startsWith("P")) {{
                url += '?product_id=' + encodeURIComponent(categoryOrPid);
            }} else {{
                url += '?category=' + encodeURIComponent(categoryOrPid);
            }}
        }}
        
        fetch(url)
        .then(r => r.json())
        .then(data => {{
            // 1. Revenue Trends Chart
            const trendHeader = Array.from(document.querySelectorAll("#tab-analysis h3")).find(h => h.textContent.includes("Revenue Trends"));
            if (trendHeader) {{
                const trendCard = trendHeader.closest("div.bg-surface-container-lowest");
                const container = trendCard.querySelector("div.flex-1");
                container.className = "flex-1 relative w-full pt-4";
                container.style.height = "300px";
                container.innerHTML = '<canvas id="salesRevenueTrendChart" style="width: 100%; height: 100%;"></canvas>';
                
                const ctx = document.getElementById('salesRevenueTrendChart').getContext('2d');
                if (window.salesRevenueChartInstance) window.salesRevenueChartInstance.destroy();
                window.salesRevenueChartInstance = new Chart(ctx, {{
                    type: 'line',
                    data: {{
                        labels: data.trend_labels,
                        datasets: [
                            {{
                                label: 'Revenue (₹)',
                                data: data.revenue_values,
                                borderColor: '#003735',
                                backgroundColor: 'rgba(0, 55, 53, 0.1)',
                                borderWidth: 2,
                                fill: true,
                                tension: 0.3,
                                yAxisID: 'y'
                            }},
                            {{
                                label: 'Volume (units)',
                                data: data.unit_values,
                                borderColor: '#2c6292',
                                borderWidth: 2,
                                borderDash: [4, 4],
                                fill: false,
                                tension: 0.3,
                                yAxisID: 'y1'
                            }}
                        ]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {{ mode: 'index', intersect: false }},
                        scales: {{
                            x: {{ grid: {{ display: false }} }},
                            y: {{ type: 'linear', display: true, position: 'left', ticks: {{ callback: v => '₹' + v }} }},
                            y1: {{ type: 'linear', display: true, position: 'right', grid: {{ drawOnChartArea: false }}, ticks: {{ callback: v => v + ' units' }} }}
                        }},
                        plugins: {{
                            tooltip: {{
                                callbacks: {{
                                    label: function(ctx) {{
                                        return ctx.dataset.yAxisID === 'y' 
                                            ? ctx.dataset.label + ': ₹' + ctx.parsed.y 
                                            : ctx.dataset.label + ': ' + ctx.parsed.y + ' units';
                                    }}
                                }}
                            }}
                        }}
                    }}
                }});
            }}
            
            // 2. Time Series Decomposition Chart
            const decompHeader = Array.from(document.querySelectorAll("#tab-analysis h3")).find(h => h.textContent.includes("Decomposition"));
            if (decompHeader) {{
                const decompCard = decompHeader.closest("div.bg-surface-container-lowest");
                const container = decompCard.querySelector("div.flex-1");
                container.className = "flex-1 relative w-full pt-4";
                container.style.height = "300px";
                container.innerHTML = '<canvas id="salesDecompChart" style="width: 100%; height: 100%;"></canvas>';
                
                const ctx2 = document.getElementById('salesDecompChart').getContext('2d');
                if (window.salesDecompChartInstance) window.salesDecompChartInstance.destroy();
                window.salesDecompChartInstance = new Chart(ctx2, {{
                    type: 'line',
                    data: {{
                        labels: data.decomp_labels,
                        datasets: [
                            {{ label: 'Trend Component', data: data.trend, borderColor: '#00e5ff', borderWidth: 2, fill: false }},
                            {{ label: 'Seasonality Factor', data: data.seasonality, borderColor: '#ffc107', borderWidth: 1.5, fill: false }},
                            {{ label: 'Event Impact', data: data.event, borderColor: '#ff334b', borderWidth: 1.5, fill: false }}
                        ]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {{
                            x: {{ grid: {{ display: false }} }},
                            y: {{ beginAtZero: false }}
                        }}
                    }}
                }});
            }}
            
            // 3. Sales by Weekday Breakdown
            const weekdayHeader = Array.from(document.querySelectorAll("#tab-analysis h3")).find(h => h.textContent.includes("Weekday"));
            if (weekdayHeader) {{
                const weekdayCard = weekdayHeader.closest("div.bg-surface-container-lowest");
                const container = document.getElementById("salesWeekdayContainer") || (weekdayCard ? weekdayCard.querySelector("div.flex-1") : null);
                if (container) {{
                    container.innerHTML = "";
                    data.weekday_breakdown.forEach(item => {{
                        const barWidth = Math.max(5, item.percentage);
                        container.innerHTML += `
                            <div class="flex items-center gap-3">
                                <span class="w-8 text-right font-body-sm text-body-sm text-on-surface-variant">${{item.day}}</span>
                                <div class="flex-1 h-5 bg-surface-container-high rounded-sm overflow-hidden">
                                    <div class="h-full bg-secondary rounded-sm transition-all duration-500" style="width: ${{barWidth}}%"></div>
                                </div>
                                <span class="w-16 text-right font-data-tabular text-[12px] text-on-surface font-medium">${{item.units}} units (${{item.percentage}}%)</span>
                            </div>
                        `;
                    }});
                }}
            }}
        }});
    }}
    
    // ----------------------------------------------------
    // FORECAST PAGE BINDINGS
    // ----------------------------------------------------
    function loadForecastData() {{
        const select = document.getElementById("forecast-product-select") || document.querySelector("select");
        const dateInput = document.getElementById("forecast-date-input");
        
        if (select) {{
            select.innerHTML = "";
            fetch('/api/products')
            .then(r => r.json())
            .then(products => {{
                products.forEach(p => {{
                    select.innerHTML += `<option value="${{p.product_id}}">${{p.product_id}} - ${{p.product_name}}</option>`;
                }});
                select.addEventListener("change", () => updateForecastPage(select.value, dateInput ? dateInput.value : null));
                if (dateInput) dateInput.addEventListener("change", () => updateForecastPage(select.value, dateInput.value));
                updateForecastPage(select.value, dateInput ? dateInput.value : null);
            }});
        }}
    }}
    
    function updateForecastPage(pid, targetDate) {{
        fetch('/api/sales/' + pid)
        .then(r => r.json())
        .then(data => {{
            if (!data.forecast || data.forecast.length === 0) return;
            
            let matchedF = data.forecast[0];
            if (targetDate) {{
                const found = data.forecast.find(f => f.date === targetDate);
                if (found) matchedF = found;
            }}
            
            // 1. Update Main Predicted Demand Card
            const predVal = document.getElementById("forecast-predicted-value");
            if (predVal) predVal.innerHTML = `${{Math.round(matchedF.predicted)}} <span class="text-h2 font-normal text-on-surface-variant ml-2">units</span>`;
            
            const predDesc = document.getElementById("forecast-predicted-desc");
            if (predDesc) predDesc.textContent = `Expected to sell on ${{matchedF.date}}. This calculation uses baseline demand (${{matchedF.baseline.toFixed(1)}} units), day factor (${{matchedF.day_factor.toFixed(2)}}x), and event multiplier (${{matchedF.event_multiplier.toFixed(2)}}x) from your dataset.`;
            
            const confText = document.getElementById("forecast-confidence-text");
            if (confText) confText.textContent = `High Confidence (92%)`;
            
            // 2. Calculation Breakdown Cards
            const mathSection = document.getElementById("forecastBreakdownContainer") || document.querySelector("div.flex-col.lg\\\\:flex-row");
            if (mathSection) {{
                mathSection.innerHTML = `
                    <div class="flex flex-col items-center p-4 bg-surface-container rounded-lg border border-outline-variant w-full lg:w-48 text-center relative shadow-sm">
                        <span class="font-label-caps text-label-caps text-on-surface-variant mb-2">Baseline (Y)</span>
                        <span class="font-h2 text-h2 text-on-surface font-semibold font-data-tabular text-data-tabular">${{matchedF.baseline.toFixed(1)}}</span>
                        <span class="font-body-sm text-body-sm text-on-surface-variant mt-1">30-day Avg</span>
                    </div>
                    <span class="material-symbols-outlined text-outline lg:rotate-0 rotate-90">close</span>
                    <div class="flex flex-col items-center p-4 bg-surface-container rounded-lg border border-outline-variant w-full lg:w-48 text-center relative shadow-sm">
                        <span class="font-label-caps text-label-caps text-on-surface-variant mb-2">Day Factor (Z)</span>
                        <span class="font-h2 text-h2 text-secondary font-semibold font-data-tabular text-data-tabular">${{matchedF.day_factor.toFixed(2)}}x</span>
                        <span class="font-body-sm text-body-sm text-on-surface-variant mt-1">Weekday Multiplier</span>
                    </div>
                    <span class="material-symbols-outlined text-outline lg:rotate-0 rotate-90">close</span>
                    <div class="flex flex-col items-center p-4 bg-surface-container rounded-lg border border-outline-variant w-full lg:w-48 text-center relative shadow-sm">
                        <span class="font-label-caps text-label-caps text-on-surface-variant mb-2">Event (W)</span>
                        <span class="font-h2 text-h2 text-tertiary-container font-semibold font-data-tabular text-data-tabular">${{matchedF.event_multiplier.toFixed(2)}}x</span>
                        <span class="font-body-sm text-body-sm text-on-surface-variant mt-1">Promo Multiplier</span>
                    </div>
                    <span class="material-symbols-outlined text-outline lg:rotate-0 rotate-90">drag_handle</span>
                    <div class="flex flex-col items-center p-4 bg-primary/10 rounded-lg border-2 border-primary w-full lg:w-48 text-center relative shadow-sm">
                        <span class="font-label-caps text-label-caps text-primary mb-2">Result</span>
                        <span class="font-h2 text-h2 text-primary font-bold font-data-tabular text-data-tabular">${{Math.round(matchedF.predicted)}}</span>
                        <span class="font-body-sm text-body-sm text-primary mt-1">Units</span>
                    </div>
                `;
            }}
            
            // 3. Trajectory Chart
            const chartContainer = document.getElementById("forecastChartContainer");
            if (chartContainer) {{
                chartContainer.className = "flex-1 relative w-full pt-4 min-h-[300px]";
                chartContainer.innerHTML = '<canvas id="trajectoryChart" style="width: 100%; height: 100%;"></canvas>';
                
                const histDates = data.history.slice(-30).map(h => h.date);
                const histSales = data.history.slice(-30).map(h => h.sales);
                
                const foreDates = data.forecast.map(f => f.date);
                const forePreds = data.forecast.map(f => f.predicted);
                
                const combinedLabels = [...histDates, ...foreDates];
                
                const ctx = document.getElementById('trajectoryChart').getContext('2d');
                if (window.trajectoryChartInstance) window.trajectoryChartInstance.destroy();
                window.trajectoryChartInstance = new Chart(ctx, {{
                    type: 'line',
                    data: {{
                        labels: combinedLabels,
                        datasets: [
                            {{
                                label: 'Actual Historical Sales (units)',
                                data: [...histSales, ...Array(forePreds.length).fill(null)],
                                borderColor: '#707978',
                                backgroundColor: 'rgba(112, 121, 120, 0.1)',
                                borderWidth: 2,
                                fill: true,
                                tension: 0.3
                            }},
                            {{
                                label: 'Predicted Demand (units)',
                                data: [...Array(histSales.length - 1).fill(null), histSales[histSales.length - 1], ...forePreds],
                                borderColor: '#003735',
                                backgroundColor: 'rgba(0, 55, 53, 0.15)',
                                borderWidth: 2.5,
                                borderDash: [5, 5],
                                fill: true,
                                tension: 0.3
                            }}
                        ]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{ position: 'top' }},
                            tooltip: {{
                                callbacks: {{
                                    label: function(ctx) {{
                                        return ctx.dataset.label + ': ' + ctx.parsed.y + ' units';
                                    }}
                                }}
                            }}
                        }},
                        scales: {{
                            x: {{ grid: {{ display: false }} }},
                            y: {{
                                beginAtZero: true,
                                title: {{ display: true, text: 'Volume (units)' }}
                            }}
                        }}
                    }}
                }});
            }}
        }});
    }}
    
    // ----------------------------------------------------
    // INVENTORY PAGE BINDINGS
    // ----------------------------------------------------
    let allAlertsData = [];
    let currentInventoryFilter = "All";
    
    function loadInventoryData() {{
        const searchInput = document.querySelector("input[placeholder*='Search']");
        if (searchInput) {{
            searchInput.addEventListener("input", filterAlertsList);
        }}
        
        fetch('/api/alerts')
        .then(r => r.json())
        .then(data => {{
            allAlertsData = data;
            filterAlertsList();
        }});
    }}
    
    window.setInventoryFilter = function(filterType, btnEl) {{
        currentInventoryFilter = filterType;
        document.querySelectorAll(".inv-filter-chip").forEach(btn => {{
            btn.className = "inv-filter-chip px-4 py-1.5 rounded-full bg-surface-container-lowest text-on-surface border border-outline-variant font-label-caps text-label-caps hover:bg-surface-variant transition-colors cursor-pointer";
        }});
        if (btnEl) {{
            btnEl.className = "inv-filter-chip px-4 py-1.5 rounded-full bg-primary text-on-primary font-label-caps text-label-caps border border-primary transition-colors cursor-pointer";
        }}
        filterAlertsList();
    }};
    
    function filterAlertsList() {{
        const searchEl = document.querySelector("input[placeholder*='Search']");
        const query = searchEl ? searchEl.value.toLowerCase().trim() : "";
        
        let filtered = allAlertsData;
        if (query) {{
            filtered = filtered.filter(p => p.product_name.toLowerCase().includes(query) || p.product_id.toLowerCase().includes(query) || p.category.toLowerCase().includes(query));
        }}
        if (currentInventoryFilter === "Stock-out Risk") {{
            filtered = filtered.filter(p => p.alert_type === "STOCKOUT_RISK");
        }} else if (currentInventoryFilter === "Overstock") {{
            filtered = filtered.filter(p => p.alert_type === "OVERSTOCK");
        }} else if (currentInventoryFilter === "Healthy") {{
            filtered = filtered.filter(p => p.alert_type === "Normal");
        }}
        
        renderAlertsList(filtered);
    }}
    
    function renderAlertsList(alerts) {{
        const tbody = document.querySelector("tbody");
        if (!tbody) return;
        tbody.innerHTML = "";
        
        alerts.forEach((alert, index) => {{
            const bgClass = index % 2 === 1 ? 'bg-surface-bright' : '';
            
            let statusBadge = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full bg-surface-variant text-on-surface-variant font-label-caps text-label-caps">Healthy</span>';
            let stockColor = 'text-on-surface';
            
            if (alert.alert_type === 'STOCKOUT_RISK') {{
                statusBadge = alert.urgency_level === 'CRITICAL' ? 
                    '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full bg-error-container text-on-error-container font-label-caps text-label-caps font-semibold">Stock-out Imminent</span>' : 
                    '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full bg-tertiary-container text-on-tertiary-container font-label-caps text-label-caps font-semibold">Low Stock</span>';
                stockColor = 'text-error font-semibold';
            }} else if (alert.alert_type === 'OVERSTOCK') {{
                statusBadge = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full bg-secondary-container text-on-secondary-container font-label-caps text-label-caps font-semibold">Overstock</span>';
                stockColor = 'text-secondary font-semibold';
            }}
            
            const recQtyStr = alert.recommended_quantity > 0 ? `+${{alert.recommended_quantity}}` : '0';
            const recColor = alert.recommended_quantity > 0 ? 'text-primary font-semibold' : 'text-on-surface-variant';
            
            tbody.innerHTML += `
                <tr class="border-b border-outline-variant/50 hover:bg-surface-container-low transition-colors h-10 group ${{bgClass}}">
                    <td class="py-2 px-4 flex items-center gap-3">
                        <div class="w-8 h-8 rounded bg-surface-variant overflow-hidden shrink-0 border border-outline-variant shadow-sm">
                            <img src="${{alert.image_url}}" class="w-full h-full object-cover" />
                        </div>
                        <div>
                            <div class="font-semibold text-on-surface">${{alert.product_name}}</div>
                            <div class="text-[10px] text-on-surface-variant">${{alert.product_id}} (${{alert.category}})</div>
                        </div>
                    </td>
                    <td class="py-2 px-4 text-right font-data-tabular text-data-tabular ${{stockColor}}">${{alert.current_stock}}</td>
                    <td class="py-2 px-4 text-right font-data-tabular text-data-tabular text-on-surface">${{Math.round(alert.predicted_demand_over_lead_time)}}</td>
                    <td class="py-2 px-4 text-center">${{statusBadge}}</td>
                    <td class="py-2 px-4 text-on-surface">${{alert.recommended_action}}</td>
                    <td class="py-2 px-4 text-right font-data-tabular text-data-tabular ${{recColor}}">${{recQtyStr}}</td>
                </tr>
            `;
        }});
        
        const pagSpan = document.getElementById("inventory-pagination-text");
        if (pagSpan) {{
            pagSpan.textContent = `Showing 1-${{alerts.length}} of ${{allAlertsData.length}} items`;
        }}
    }}
    
    // ----------------------------------------------------
    // EVENTS & PROMOTIONS PAGE BINDINGS
    // ----------------------------------------------------
    let allEventsData = [];
    
    function loadEventsData() {{
        fetch('/api/events')
        .then(r => r.json())
        .then(res => {{
            allEventsData = res.events;
            
            const monthSelect = document.getElementById("events-month-select");
            if (monthSelect) {{
                monthSelect.addEventListener("change", function() {{
                    renderEventsCalendar(this.value);
                }});
            }}
            
            renderEventsCalendar("2026-08");
            renderUpcomingEventsList(allEventsData);
        }});
    }}
    
    function renderEventsCalendar(yearMonthStr) {{
        const grid = document.getElementById("events-calendar-grid");
        if (!grid) return;
        
        const parts = yearMonthStr.split("-");
        const year = parseInt(parts[0]);
        const month = parseInt(parts[1]) - 1;
        
        const firstDay = new Date(year, month, 1).getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        
        let html = `
            <div class="calendar-cell header font-label-caps text-label-caps text-on-surface-variant">SUN</div>
            <div class="calendar-cell header font-label-caps text-label-caps text-on-surface-variant">MON</div>
            <div class="calendar-cell header font-label-caps text-label-caps text-on-surface-variant">TUE</div>
            <div class="calendar-cell header font-label-caps text-label-caps text-on-surface-variant">WED</div>
            <div class="calendar-cell header font-label-caps text-label-caps text-on-surface-variant">THU</div>
            <div class="calendar-cell header font-label-caps text-label-caps text-on-surface-variant">FRI</div>
            <div class="calendar-cell header font-label-caps text-label-caps text-on-surface-variant">SAT</div>
        `;
        
        for (let i = 0; i < firstDay; i++) {{
            html += `<div class="calendar-cell inactive"><span class="font-data-tabular text-data-tabular"></span></div>`;
        }}
        
        for (let day = 1; day <= daysInMonth; day++) {{
            const monthPadded = String(month + 1).padStart(2, '0');
            const dayPadded = String(day).padStart(2, '0');
            const fullDateStr = `${{year}}-${{monthPadded}}-${{dayPadded}}`;
            
            const matches = allEventsData.filter(e => e.date === fullDateStr);
            const isToday = fullDateStr === "2026-08-28";
            
            const cellClass = isToday ? 'bg-primary/5 ring-1 ring-inset ring-primary' : '';
            const dayNumClass = isToday ? 'font-bold text-primary' : 'text-on-surface';
            
            let eventsHtml = '';
            matches.forEach(ev => {{
                let colorClass = 'border-primary text-primary bg-primary/10';
                if (ev.color === 'secondary') colorClass = 'border-secondary text-secondary bg-secondary/10';
                if (ev.color === 'tertiary') colorClass = 'border-tertiary text-tertiary bg-tertiary/10';
                
                eventsHtml += `
                    <div class="calendar-event ${{colorClass}} mt-1 font-semibold" title="${{ev.event_name}} (${{ev.multiplier}})">
                        ${{ev.event_name}}
                    </div>
                `;
            }});
            
            html += `
                <div class="calendar-cell ${{cellClass}}">
                    <span class="font-data-tabular text-data-tabular ${{dayNumClass}}">${{day}}</span>
                    ${{eventsHtml}}
                </div>
            `;
        }}
        
        grid.innerHTML = html;
    }}
    
    function renderUpcomingEventsList(events) {{
        const container = document.getElementById("upcoming-events-container");
        if (!container) return;
        container.innerHTML = "";
        
        events.forEach(ev => {{
            let borderBg = 'bg-primary';
            let textCol = 'text-primary';
            if (ev.color === 'secondary') {{ borderBg = 'bg-secondary'; textCol = 'text-secondary'; }}
            if (ev.color === 'tertiary') {{ borderBg = 'bg-tertiary'; textCol = 'text-tertiary'; }}
            
            container.innerHTML += `
                <div class="group border border-outline-variant rounded-DEFAULT p-3 hover:border-primary transition-colors bg-surface relative overflow-hidden shadow-sm">
                    <div class="absolute top-0 left-0 w-1 h-full ${{borderBg}}"></div>
                    <div class="flex justify-between items-start ml-2">
                        <div>
                            <div class="font-label-caps text-label-caps ${{textCol}} mb-0.5">${{ev.date}} • ${{ev.event_type}}</div>
                            <div class="font-h3 text-h3 text-on-surface font-semibold">${{ev.event_name}}</div>
                        </div>
                        <span class="bg-surface-container-low text-on-surface px-2 py-0.5 rounded font-data-tabular text-data-tabular text-xs font-semibold">${{ev.multiplier}}</span>
                    </div>
                    <div class="mt-2 ml-2 pt-2 border-t border-outline-variant border-dashed">
                        <div class="font-body-sm text-body-sm text-on-surface-variant mb-1">Target Categories</div>
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined ${{textCol}} text-sm">trending_up</span>
                            <span class="font-data-tabular text-data-tabular font-medium text-on-surface">${{ev.categories}}</span>
                        </div>
                    </div>
                </div>
            `;
        }});
    }}
    
    // ----------------------------------------------------
    // WHAT-IF SIMULATOR PAGE BINDINGS
    // ----------------------------------------------------
    function loadWhatIfData() {{
        // Setup Form Widgets
        const selectProd = document.querySelector("select");
        const selectEvent = document.querySelectorAll("select")[1];
        const dateInput = document.querySelector("input[type='date']");
        const simButton = Array.from(document.querySelectorAll("button")).find(b => b.textContent.includes("Run Simulation"));
        
        if (selectProd && simButton) {{
            selectProd.innerHTML = "";
            fetch('/api/products')
            .then(r => r.json())
            .then(products => {{
                products.forEach(p => {{
                    selectProd.innerHTML += `<option value="${{p.product_id}}">${{p.product_id}} - ${{p.product_name}}</option>`;
                }});
                
                // Initialize default date in widget (early Jan 2028)
                if (dateInput) {{
                    dateInput.value = "2028-01-13";
                    dateInput.min = "2028-01-01";
                    dateInput.max = "2028-01-14";
                }}
                
                simButton.addEventListener("click", runWhatIfSimulation);
            }});
        }}
    }}
    
    function runWhatIfSimulation() {{
        const pid = document.querySelector("select").value;
        const date = document.querySelector("input[type='date']").value;
        const ev = document.querySelectorAll("select")[1].value;
        
        let override = ev;
        if (ev === "None" || ev.includes("Default")) override = "None";
        if (ev.includes("Promo")) override = "promo";
        
        fetch(`/api/whatif?product_id=${{pid}}&date=${{date}}&override_event=${{override}}`)
        .then(r => r.json())
        .then(data => {{
            // Display Results in DOM for 2-column cards layout
            const cards = document.querySelectorAll("div.grid-cols-1.md\\\\:grid-cols-2 > div");
            if (cards.length >= 2) {{
                const baselineCard = cards[0];
                const simulatedCard = cards[1];
                
                // 1. Update Baseline card elements
                const baseDemandVal = Math.round(data.original_demand);
                const baseRevVal = data.original_revenue.toFixed(2);
                const baseRiskVal = data.original_stockout_risk;
                
                baselineCard.querySelectorAll("p.font-data-tabular")[0].innerHTML = `${{baseDemandVal}} <span class="text-sm font-normal text-outline">units</span>`;
                baselineCard.querySelectorAll("p.font-data-tabular")[1].textContent = `$${{parseFloat(baseRevVal).toLocaleString('en-US', {{minimumFractionDigits: 2, maximumFractionDigits: 2}})}}`;
                baselineCard.querySelector("span.font-data-tabular").textContent = `${{baseRiskVal}}%`;
                
                const baseProgressBar = baselineCard.querySelector("div.h-2 div");
                if (baseProgressBar) {{
                    baseProgressBar.style.width = `${{baseRiskVal}}%`;
                    baseProgressBar.className = `h-full ${{baseRiskVal > 50 ? 'bg-error' : 'bg-outline'}}`;
                }}
                
                // 2. Update Simulated card elements
                const simDemandVal = Math.round(data.simulated_demand);
                const simRevVal = data.simulated_revenue.toFixed(2);
                const simRiskVal = data.simulated_stockout_risk;
                
                simulatedCard.querySelectorAll("p.font-data-tabular")[0].innerHTML = `${{simDemandVal}} <span class="text-sm font-normal text-outline">units</span>`;
                
                const demandDiffPct = data.original_demand > 0 ? Math.round(((data.simulated_demand - data.original_demand) / data.original_demand) * 100) : 0;
                const demandBadge = simulatedCard.querySelector("div.flex.items-end span.font-data-tabular");
                if (demandBadge) {{
                    demandBadge.textContent = `${{demandDiffPct >= 0 ? '+' : ''}}${{demandDiffPct}}%`;
                }}
                
                simulatedCard.querySelectorAll("p.font-data-tabular")[1].textContent = `₹${{parseFloat(simRevVal).toLocaleString('en-US', {{minimumFractionDigits: 2, maximumFractionDigits: 2}})}}`;
                
                const revDiffVal = data.simulated_revenue - data.original_revenue;
                const revBadge = simulatedCard.querySelectorAll("div.flex.items-end span.font-data-tabular")[1];
                if (revBadge) {{
                    const revBadgeText = revDiffVal >= 0 ? `+₹${{Math.round(revDiffVal)}}` : `-₹${{Math.round(Math.abs(revDiffVal))}}`;
                    revBadge.textContent = revBadgeText;
                }}
                
                const simRiskSpan = simulatedCard.querySelector("span.font-data-tabular");
                if (simRiskSpan) {{
                    simRiskSpan.textContent = `${{simRiskVal}}%`;
                    simRiskSpan.className = `font-data-tabular text-data-tabular font-semibold ${{simRiskVal > 50 ? 'text-error' : 'text-primary'}}`;
                }}
                
                const simProgressBar = simulatedCard.querySelector("div.h-2 div");
                if (simProgressBar) {{
                    simProgressBar.style.width = `${{simRiskVal}}%`;
                    simProgressBar.className = `h-full ${{simRiskVal > 50 ? 'bg-error' : 'bg-primary'}}`;
                }}
                
                const warningMsg = simulatedCard.querySelector("p.text-error");
                if (warningMsg) {{
                    if (simRiskVal > 50) {{
                        warningMsg.style.display = "flex";
                        warningMsg.innerHTML = '<span class="material-symbols-outlined text-[14px]">warning</span> Warning: High probability of stockout before end of horizon.';
                    }} else {{
                        warningMsg.style.display = "none";
                    }}
                }}
            }}
            
            // 3. Update Top Highlight / Summary delta metrics
            const highlightCards = document.querySelectorAll("div.bg-surface-variant span.font-bold");
            if (highlightCards.length >= 2) {{
                const demandDiff = Math.round(data.simulated_demand - data.original_demand);
                const revDiff = data.simulated_revenue - data.original_revenue;
                
                highlightCards[0].textContent = `${{demandDiff >= 0 ? '+' : ''}}${{demandDiff}}`;
                highlightCards[1].textContent = `${{revDiff >= 0 ? '+' : ''}}₹${{Math.round(revDiff).toLocaleString()}}`;
            }}
        }});
    }}

    </script>
    """
    return html_content.replace("</body>", f"{script}</body>")

if __name__ == '__main__':
    print("Starting Flask Backend Server on port 8080...")
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)

