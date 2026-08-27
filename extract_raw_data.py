import pandas as pd
import numpy as np
import os

excel_path = 'RETAIL_DEMAND_DATASET_SYNTHETIC_2026_2027/Retail_Demand_Synthetic_2026_2027.xlsx'
output_dir = '.'

print("Reading PRODUCT_MASTER sheet...")
prod_df = pd.read_excel(excel_path, sheet_name='PRODUCT_MASTER')
products_csv = pd.DataFrame({
    'product_id': prod_df['Product_ID'],
    'product_name': prod_df['Product_Name'],
    'category': prod_df['Category'],
    'unit_price': prod_df['Price'],
    'launch_date': pd.to_datetime(prod_df['Launch_Date']).dt.strftime('%Y-%m-%d')
})
products_csv.to_csv(os.path.join(output_dir, 'products.csv'), index=False)
print("Saved products.csv")

print("Reading EVENT_CALENDAR sheet...")
cal_df = pd.read_excel(excel_path, sheet_name='EVENT_CALENDAR')
cal_dates = pd.to_datetime(cal_df['Date'])
day_of_week = cal_dates.dt.day_name()
is_weekend = day_of_week.isin(['Saturday', 'Sunday']).astype(int)

# Construct 'event' column:
# 1. If Festival is not 'No', use Festival name.
# 2. Else if Local_Event is not 'No', use Local_Event name.
# 3. Else if Holiday is 'Yes' and it is not a weekend, use 'Public_Holiday'.
# Otherwise empty string.
events = []
for idx, row in cal_df.iterrows():
    fest = row['Festival']
    le = row['Local_Event']
    hol = row['Holiday']
    dow = day_of_week.iloc[idx]
    
    if fest != 'No':
        events.append(fest)
    elif le != 'No':
        events.append(le)
    elif hol == 'Yes' and dow not in ['Saturday', 'Sunday']:
        events.append('Public_Holiday')
    else:
        events.append('')

calendar_csv = pd.DataFrame({
    'date': cal_dates.dt.strftime('%Y-%m-%d'),
    'day_of_week': day_of_week,
    'is_weekend': is_weekend,
    'is_salary_period': (cal_df['Salary_Period'] == 'Yes').astype(int),
    'event': events,
    'weather': cal_df['Weather']
})
calendar_csv.to_csv(os.path.join(output_dir, 'calendar.csv'), index=False)
print("Saved calendar.csv")

print("Reading SALES_2026 and SALES_2027 sheets...")
sales_2026 = pd.read_excel(excel_path, sheet_name='SALES_2026')
sales_2027 = pd.read_excel(excel_path, sheet_name='SALES_2027')
sales_all = pd.concat([sales_2026, sales_2027], ignore_index=True)

sales_csv = pd.DataFrame({
    'date': pd.to_datetime(sales_all['Date']).dt.strftime('%Y-%m-%d'),
    'product_id': sales_all['Product_ID'],
    'units_sold': sales_all['Units_Sold'],
    'stock_available_end_of_day': sales_all['Stock_Available'],
    'promotion_flag': (sales_all['Promotion'] != 'No').astype(int),
    'unit_price': sales_all['Price']
})
# Sort sales by product_id and date
sales_csv = sales_csv.sort_values(by=['product_id', 'date']).reset_index(drop=True)
sales_csv.to_csv(os.path.join(output_dir, 'sales.csv'), index=False)
print("Saved sales.csv")
print("Extraction complete!")
