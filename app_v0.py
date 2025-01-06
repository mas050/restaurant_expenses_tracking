import streamlit as st
import pandas as pd
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.oauth2 import service_account
import json

# Set up Google Sheets credentials
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
# Replace with your credentials file path
SERVICE_ACCOUNT_FILE = '/Users/sebastien.martineau/Python/restaurant_tracker/gen-lang-client-0627468750-2eb0f811339b.json'
# Replace with your Google Sheet ID
SPREADSHEET_ID = '1QrUs7dCZefWxPbhNcn_h99VN2DE3AQaBlZz0G9haxXE'
RANGE_NAME = 'Sheet1!A:D'  # Assuming you want to write to the first sheet

def setup_google_sheets():
    # Create credentials dictionary from secrets
    credentials = {
        "type": st.secrets["gcp_service_account"]["type"],
        "project_id": st.secrets["gcp_service_account"]["project_id"],
        "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
        "private_key": st.secrets["gcp_service_account"]["private_key"],
        "client_email": st.secrets["gcp_service_account"]["client_email"],
        "client_id": st.secrets["gcp_service_account"]["client_id"],
        "auth_uri": st.secrets["gcp_service_account"]["auth_uri"],
        "token_uri": st.secrets["gcp_service_account"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["gcp_service_account"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"]
    }
    
    creds = service_account.Credentials.from_service_account_info(
        credentials, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    return service

def update_sheet(service, values):
    body = {
        'values': [values]
    }
    result = service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME,
        valueInputOption='USER_ENTERED',
        body=body
    ).execute()
    return result

def fetch_sheet_data(service):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME
    ).execute()
    values = result.get('values', [])
    return values

def create_summary_table(data):
    if not data:
        return pd.DataFrame()
    
    # Create DataFrame from sheet data
    df = pd.DataFrame(data[1:], columns=['Date', 'Name', 'Restaurant', 'Amount'])
    
    # Convert Amount to float
    df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
    
    # Convert Date to datetime
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Create Month-Year column
    df['Month-Year'] = df['Date'].dt.strftime('%Y-%m')
    
    # Create pivot table for amounts
    amount_pivot = pd.pivot_table(
        df,
        values='Amount',
        index='Month-Year',
        columns='Name',
        aggfunc='sum',
        fill_value=0
    )
    
    # Create pivot table for count of entries
    count_pivot = pd.pivot_table(
        df,
        values='Amount',
        index='Month-Year',
        columns='Name',
        aggfunc='count',
        fill_value=0
    )
    
    # Ensure Katy and Sebastien columns exist in both pivots
    for pivot in [amount_pivot, count_pivot]:
        for name in ['Katy', 'Sebastien']:
            if name not in pivot.columns:
                pivot[name] = 0
    
    # Calculate differences
    amount_pivot['Amount Difference (Katy - Sebastien)'] = amount_pivot['Katy'] - amount_pivot['Sebastien']
    count_pivot['Count Difference (Katy - Sebastien)'] = count_pivot['Katy'] - count_pivot['Sebastien']
    
    # Rename count columns
    count_cols = {
        'Katy': 'Katy (Count)',
        'Sebastien': 'Sebastien (Count)',
    }
    count_pivot = count_pivot.rename(columns=count_cols)
    
    # Combine amount and count pivots
    final_table = pd.concat([
        amount_pivot[['Katy', 'Sebastien', 'Amount Difference (Katy - Sebastien)']],
        count_pivot[['Katy (Count)', 'Sebastien (Count)', 'Count Difference (Katy - Sebastien)']]
    ], axis=1)
    
    # Sort by Month-Year
    final_table = final_table.sort_index(ascending=False)
    
    # Add total row
    total_row = pd.Series({
        'Katy': final_table['Katy'].sum(),
        'Sebastien': final_table['Sebastien'].sum(),
        'Amount Difference (Katy - Sebastien)': final_table['Amount Difference (Katy - Sebastien)'].sum(),
        'Katy (Count)': final_table['Katy (Count)'].sum(),
        'Sebastien (Count)': final_table['Sebastien (Count)'].sum(),
        'Count Difference (Katy - Sebastien)': final_table['Count Difference (Katy - Sebastien)'].sum()
    })
    final_table.loc['Total'] = total_row
    
    # Reorder columns for better readability
    column_order = [
        'Katy',
        'Sebastien',
        'Amount Difference (Katy - Sebastien)',
        'Katy (Count)',
        'Sebastien (Count)',
        'Count Difference (Katy - Sebastien)'
    ]
    final_table = final_table[column_order]
    
    return final_table

# Streamlit app
def main():
    st.title("Restaurant Expense Tracker")

    # Define the options for dropdowns
    name_options = ["", "Katy", "Sebastien"]
    restaurant_options = ["", "Imperial", "Ramen", "Baton Rouge", "Marathon", "Miss Pho", "Indian","Starbucks"]

    col1, col2 = st.columns(2)
    
    with col1:
        default_name = st.selectbox("Select your name", name_options)
        if default_name == "":
            user_name = st.text_input("Or enter a custom name")
        else:
            user_name = default_name

    with col2:
        default_restaurant = st.selectbox("Select restaurant", restaurant_options)
        if default_restaurant == "":
            restaurant = st.text_input("Or enter a custom restaurant")
        else:
            restaurant = default_restaurant

    date = st.date_input("Select date")
    bill_amount = st.number_input("Enter total bill amount", min_value=0.0, step=0.01)

    if st.button("Submit"):
        final_name = user_name if user_name else default_name
        final_restaurant = restaurant if restaurant else default_restaurant
        
        if final_name and final_restaurant and bill_amount > 0:
            try:
                service = setup_google_sheets()
                values = [
                    date.strftime('%Y-%m-%d'),
                    final_name,
                    final_restaurant,
                    str(bill_amount)
                ]
                result = update_sheet(service, values)
                st.success("Successfully added to the spreadsheet!")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
        else:
            st.warning("Please fill in all fields and ensure bill amount is greater than 0")

    # Add a separator
    st.markdown("---")
    st.subheader("Monthly Summary by User")

    # Fetch and display summary table
    try:
        service = setup_google_sheets()
        sheet_data = fetch_sheet_data(service)

        if sheet_data:
            summary_table = create_summary_table(sheet_data)
            if not summary_table.empty:
                # Create two different formatters
                formatters = {
                    'Katy': '${:,.2f}',
                    'Sebastien': '${:,.2f}',
                    'Amount Difference (Katy - Sebastien)': '${:,.2f}',
                    'Katy (Count)': '{:.0f}',
                    'Sebastien (Count)': '{:.0f}',
                    'Count Difference (Katy - Sebastien)': '{:.0f}'
                }
                
                # Apply formatting
                formatted_table = summary_table.style.format(formatters)
                st.dataframe(formatted_table, use_container_width=True)
            else:
                st.info("No data available yet.")
    except Exception as e:
        st.error(f"Error loading summary table: {str(e)}")

if __name__ == "__main__":
    main()
