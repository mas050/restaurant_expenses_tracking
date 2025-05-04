import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.oauth2 import service_account
import os

# Set page config for better appearance
st.set_page_config(
    page_title="Restaurant Tracker",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling and improved readability
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #FF4B4B;
        margin-bottom: 0.5rem;
        font-weight: 600;
    }
    .subheader {
        font-size: 1.5rem;
        color: #FF4B4B;
        margin-bottom: 1rem;
        font-weight: 500;
    }
    .card {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .summary-box {
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        text-align: center;
        font-weight: 600;
    }
    .footer {
        margin-top: 3rem;
        text-align: center;
        color: #444444;
        font-size: 0.9rem;
    }
    .metric-card {
        background-color: #f5f5f5;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.08);
        padding: 18px;
        text-align: center;
        border: 1px solid #e0e0e0;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: bold;
        color: #333333;
    }
    .metric-label {
        color: #222222;
        font-size: 1rem;
        font-weight: 500;
        margin-top: 5px;
    }
    /* Improve data table readability */
    div[data-testid="stDataFrame"] td, div[data-testid="stDataFrame"] th {
        padding: 8px !important;
        font-size: 1rem !important;
        background-color: #f9f9f9;
        border: 1px solid #e0e0e0;
    }
    /* Hide number input arrows */
    input[type=number]::-webkit-inner-spin-button, 
    input[type=number]::-webkit-outer-spin-button { 
        -webkit-appearance: none; 
        margin: 0; 
    }
    input[type=number] {
        -moz-appearance: textfield;
    }
    /* Style for empty input */
    .empty-input:placeholder-shown {
        border-color: #ccc !important;
    }
</style>
""", unsafe_allow_html=True)

# Set up Google Sheets credentials - using the same code as before
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1QrUs7dCZefWxPbhNcn_h99VN2DE3AQaBlZz0G9haxXE'
RANGE_NAME = 'Sheet1!A:D'

# ===== Google Sheets functions remain the same =====
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

def get_sheet_id(service):
    """Get the sheet ID of the first sheet in the spreadsheet."""
    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        return spreadsheet['sheets'][0]['properties']['sheetId']
    except Exception as e:
        st.error(f"Error getting sheet ID: {str(e)}")
        return None

def delete_row(service, row_index):
    """Delete a row from the Google Sheet."""
    sheet_id = get_sheet_id(service)
    if sheet_id is None:
        return False

    try:
        request = {
            "deleteDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": row_index - 1,  # Convert to 0-based index
                    "endIndex": row_index
                }
            }
        }
        
        body = {"requests": [request]}
        
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body=body
        ).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting row: {str(e)}")
        return False

def update_cell(service, row_index, col_index, value):
    """Update a specific cell in the Google Sheet."""
    try:
        # Get the A1 notation range for the cell
        col_letter = chr(65 + col_index)  # A=0, B=1, etc.
        cell_range = f'Sheet1!{col_letter}{row_index}'
        
        # Update the value
        body = {
            'values': [[value]]
        }
        
        result = service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=cell_range,
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        
        # Verify the update
        verify = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=cell_range
        ).execute()
        
        if 'values' in verify and verify['values'][0][0] == value:
            return True
        else:
            st.error("Cell update verification failed")
            return False
            
    except Exception as e:
        st.error(f"Error updating cell: {str(e)}")
        return False

# ===== Enhanced Data Processing Functions =====

def create_summary_table(data):
    if not data or len(data) < 2:
        return pd.DataFrame(), pd.DataFrame()
    
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
    
    # Calculate differences and running balance
    amount_pivot['Monthly Difference'] = amount_pivot['Katy'] - amount_pivot['Sebastien']
    amount_pivot['Running Balance'] = amount_pivot['Monthly Difference'].cumsum()
    count_pivot['Count Difference'] = count_pivot['Katy'] - count_pivot['Sebastien']
    
    # Rename count columns
    count_cols = {
        'Katy': 'Katy (Count)',
        'Sebastien': 'Sebastien (Count)',
    }
    count_pivot = count_pivot.rename(columns=count_cols)
    
    # Combine amount and count pivots
    final_table = pd.concat([
        amount_pivot[['Katy', 'Sebastien', 'Monthly Difference', 'Running Balance']],
        count_pivot[['Katy (Count)', 'Sebastien (Count)', 'Count Difference']]
    ], axis=1)
    
    # Sort by Month-Year
    final_table = final_table.sort_index(ascending=False)
    
    # Add total row
    total_row = pd.Series({
        'Katy': final_table['Katy'].sum(),
        'Sebastien': final_table['Sebastien'].sum(),
        'Monthly Difference': final_table['Monthly Difference'].sum(),
        'Running Balance': final_table['Running Balance'].iloc[-1],
        'Katy (Count)': final_table['Katy (Count)'].sum(),
        'Sebastien (Count)': final_table['Sebastien (Count)'].sum(),
        'Count Difference': final_table['Count Difference'].sum()
    })
    final_table.loc['Total'] = total_row
    
    # Reorder columns for better readability
    column_order = [
        'Katy',
        'Sebastien',
        'Monthly Difference',
        'Running Balance',
        'Katy (Count)',
        'Sebastien (Count)',
        'Count Difference'
    ]
    final_table = final_table[column_order]
    
    # For charts - create a copy of the dataframe without the Total row
    chart_df = df.copy()
    
    return final_table, chart_df

def prepare_chart_data(df):
    """Prepare dataframes for various charts"""
    # Monthly spending by person
    monthly_by_person = df.copy()
    monthly_by_person['Month'] = monthly_by_person['Date'].dt.strftime('%Y-%m')
    monthly_by_person = monthly_by_person.groupby(['Month', 'Name'])['Amount'].sum().reset_index()
    
    # Restaurant frequency
    restaurant_count = df.groupby('Restaurant').size().reset_index(name='Count')
    restaurant_count = restaurant_count.sort_values('Count', ascending=False)
    
    # Spending by restaurant
    restaurant_amount = df.groupby('Restaurant')['Amount'].sum().reset_index()
    restaurant_amount = restaurant_amount.sort_values('Amount', ascending=False)
    
    # Recent trends (last 3 months)
    three_months_ago = datetime.now() - timedelta(days=90)
    recent_df = df[df['Date'] > pd.Timestamp(three_months_ago)]
    
    return {
        'monthly_by_person': monthly_by_person,
        'restaurant_count': restaurant_count,
        'restaurant_amount': restaurant_amount,
        'recent': recent_df
    }

def calculate_balance(summary_table):
    """Calculate who owes who based on the summary table"""
    if 'Total' in summary_table.index and 'Running Balance' in summary_table.columns:
        # Get the total amounts spent by each person
        katy_total = summary_table.loc['Total', 'Katy']
        sebastien_total = summary_table.loc['Total', 'Sebastien']
        
        # Calculate the overall total
        overall_total = katy_total + sebastien_total
        
        # Each person should pay half of the overall total
        half_total = overall_total / 2
        
        # Calculate how much each person has paid vs should have paid
        katy_diff = katy_total - half_total
        sebastien_diff = sebastien_total - half_total
        
        if abs(katy_diff) < 0.01:  # Essentially even
            return "Even", 0, "neutral"
        elif katy_diff > 0:
            # Katy paid more than her share
            return "Sebastien owes Katy", abs(katy_diff), "positive"
        else:
            # Sebastien paid more than his share
            return "Katy owes Sebastien", abs(katy_diff), "negative"
    
    return "Cannot calculate balance", 0, "neutral"

# ===== Main App Function =====
def main():
    # Initialize session state variables for deletion confirmation
    if 'confirm_deletion' not in st.session_state:
        st.session_state.confirm_deletion = False
    if 'rows_to_delete' not in st.session_state:
        st.session_state.rows_to_delete = []
    if 'delete_success' not in st.session_state:
        st.session_state.delete_success = False
    if 'delete_message' not in st.session_state:
        st.session_state.delete_message = ""
    
    # Initialize functions for handling deletion confirmation
    def set_confirm_deletion():
        st.session_state.confirm_deletion = True
        
    def cancel_deletion():
        st.session_state.confirm_deletion = False
        st.session_state.rows_to_delete = []
        
    def perform_deletion():
        try:
            deleted_count = 0
            # Delete in reverse order to maintain correct indices
            for idx in sorted(st.session_state.rows_to_delete, reverse=True):
                if delete_row(service, idx + 2):  # +2 because of header and 0-based index
                    deleted_count += 1
            
            st.session_state.delete_success = True
            st.session_state.delete_message = f"✅ Successfully deleted {deleted_count} transaction(s)"
            st.session_state.confirm_deletion = False
            st.session_state.rows_to_delete = []
            
        except Exception as e:
            st.session_state.delete_success = True
            st.session_state.delete_message = f"❌ Error deleting rows: {str(e)}"
            st.session_state.confirm_deletion = False
    
    # App Header
    st.markdown('<p style="font-size: 1.5rem; font-weight: 600; color: #FF4B4B; margin-bottom: 0.3rem; text-align: left; margin-left: 0; padding-left: 0;">Restaurant Expense Tracker</p>', unsafe_allow_html=True)
    st.markdown('<p style="font-size: 1.1rem; font-weight: 400; color: white; margin-top: 0; text-align: left; margin-left: 0; padding-left: 0; text-shadow: 0px 0px 1px rgba(0,0,0,0.2);">Keep track of shared dining expenses between Katy & Sebastien</p>', unsafe_allow_html=True)
    
    # Initialize service early
    try:
        service = setup_google_sheets()
        sheet_data = fetch_sheet_data(service)
        
        if sheet_data and len(sheet_data) > 1:
            summary_table, chart_df = create_summary_table(sheet_data)
            chart_data = prepare_chart_data(chart_df)
            
            # Calculate the actual total difference
            total_katy = summary_table.loc['Total', 'Katy']
            total_sebastien = summary_table.loc['Total', 'Sebastien']
            total_amount = total_katy + total_sebastien
            should_have_paid = total_amount / 2
            amount_diff = total_katy - should_have_paid  # Positive means Katy paid more
            
            # Determine who owes who based on the amount difference
            if abs(amount_diff) < 0.01:  # Essentially zero
                balance_text = "Even"
                balance_class = "neutral"
                balance_amount = 0
            elif amount_diff > 0:
                # Katy paid more
                balance_text = "Sebastien owes Katy"
                balance_class = "positive"
                balance_amount = abs(amount_diff)
            else:
                # Sebastien paid more
                balance_text = "Katy owes Sebastien"
                balance_class = "negative"
                balance_amount = abs(amount_diff)
            
            # Remove the standalone Current Balance box and add it to the metrics row
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 1rem; color: black; font-weight: 500; margin-bottom: 8px;">{balance_text}</div>
                    <div class="metric-value">${balance_amount:.2f}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 1rem; color: black; font-weight: 500; margin-bottom: 8px;">Katy's Total Spending</div>
                    <div class="metric-value">${summary_table.loc['Total', 'Katy']:.2f}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 1rem; color: black; font-weight: 500; margin-bottom: 8px;">Sebastien's Total Spending</div>
                    <div class="metric-value">${summary_table.loc['Total', 'Sebastien']:.2f}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 1rem; color: black; font-weight: 500; margin-bottom: 8px;">Katy's Meals</div>
                    <div class="metric-value">{int(summary_table.loc['Total', 'Katy (Count)'])}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col5:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 1rem; color: black; font-weight: 500; margin-bottom: 8px;">Sebastien's Meals</div>
                    <div class="metric-value">{int(summary_table.loc['Total', 'Sebastien (Count)'])}</div>
                </div>
                """, unsafe_allow_html=True)
        
    except Exception as e:
        st.error(f"Error initializing data: {str(e)}")
        sheet_data = []
        summary_table = pd.DataFrame()
        chart_df = pd.DataFrame()
        chart_data = {}
    
    # Create tabs with nice icons
    tab1, tab2, tab3 = st.tabs(["➕ Add Expense", "🔍 View/Edit Transactions", "📊 Analytics"])
    
    # Tab 1: Add Expense
    with tab1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<p class="subheader">Add New Expense</p>', unsafe_allow_html=True)
        
        # Get recent restaurants for autocomplete
        recent_restaurants = []
        try:
            if 'chart_data' in locals() and 'restaurant_count' in chart_data:
                recent_restaurants = chart_data['restaurant_count']['Restaurant'].tolist()
        except:
            recent_restaurants = ["Imperial", "Ramen", "Baton Rouge", "Marathon", "Miss Pho", "Indian", "Starbucks"]
        
        # Store last used values in session state for convenience
        if 'last_name' not in st.session_state:
            st.session_state.last_name = ""
        if 'last_restaurant' not in st.session_state:
            st.session_state.last_restaurant = ""
        
        col1, col2 = st.columns(2)
        
        with col1:
            name_options = ["", "Katy", "Sebastien"]
            default_name = st.selectbox(
                "Select your name", 
                name_options, 
                index=name_options.index(st.session_state.last_name) if st.session_state.last_name in name_options else 0,
                key="tab1_name"
            )
            
            if default_name == "":
                user_name = st.text_input("Or enter a custom name", key="tab1_custom_name")
            else:
                user_name = default_name
                st.session_state.last_name = default_name
        
        with col2:
            # Add empty option to the restaurant list
            restaurant_options = [""] + recent_restaurants
            # Make sure we don't have duplicates
            restaurant_options = list(dict.fromkeys(restaurant_options))
            
            default_restaurant = st.selectbox(
                "Select restaurant", 
                restaurant_options, 
                index=restaurant_options.index(st.session_state.last_restaurant) if st.session_state.last_restaurant in restaurant_options else 0,
                key="tab1_restaurant"
            )
            
            if default_restaurant == "":
                restaurant = st.text_input("Or enter a custom restaurant", key="tab1_custom_restaurant")
            else:
                restaurant = default_restaurant
                st.session_state.last_restaurant = default_restaurant
        
        date = st.date_input("Select date", value=datetime.now())
        
        # FIX 2: Changed bill amount input to not show 0.00 by default
        # Using an empty label with markdown label above
        st.markdown('<label>Enter total bill amount</label>', unsafe_allow_html=True)
        bill_amount = st.number_input(" ", min_value=0.0, step=0.01, value=None, label_visibility="collapsed")
        
        # Preview expense entry - check if bill_amount is not None before comparing
        if user_name and restaurant and bill_amount is not None and bill_amount > 0:
            st.info(f"Ready to add: ${bill_amount:.2f} paid by {user_name} at {restaurant} on {date.strftime('%Y-%m-%d')}")
        
        # Submit button with better styling
        submit_button = st.button("➕ Add Expense", type="primary", use_container_width=True)
        
        if submit_button:
            final_name = user_name if user_name else default_name
            final_restaurant = restaurant if restaurant else default_restaurant
            
            if final_name and final_restaurant and bill_amount is not None and bill_amount > 0:
                try:
                    values = [
                        date.strftime('%Y-%m-%d'),
                        final_name,
                        final_restaurant,
                        str(bill_amount)
                    ]
                    result = update_sheet(service, values)
                    
                    # Success message with animation
                    # Show success message
                    st.success(f"✅ Successfully added ${bill_amount:.2f} expense at {final_restaurant}!")
                    
                    # Randomly select between the two available animations
                    if np.random.choice([True, False]):
                        st.balloons()
                    else:
                        st.snow()
                    # Auto-refresh after 2 seconds
                    import time
                    time.sleep(2)
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
            else:
                st.warning("Please fill in all fields and ensure bill amount is greater than 0")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Display analytics charts relevant to adding expenses
        if 'chart_data' in locals() and chart_data and not chart_df.empty:
            st.markdown('<p class="subheader">Recent Spending Patterns</p>', unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.subheader("Top Restaurants")
                
                # Create a bar chart for top restaurants by count
                if 'restaurant_count' in chart_data and not chart_data['restaurant_count'].empty:
                    top_restaurants = chart_data['restaurant_count'].head(5)
                    
                    chart = alt.Chart(top_restaurants).mark_bar().encode(
                        x=alt.X('Count:Q', title='Visit Count'),
                        y=alt.Y('Restaurant:N', title='Restaurant', sort='-x'),
                        color=alt.Color('Count:Q', scale=alt.Scale(scheme='blues')),
                        tooltip=['Restaurant', 'Count']
                    ).properties(
                        title='Most Visited Restaurants'
                    )
                    
                    st.altair_chart(chart, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col2:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.subheader("Recent Spending")
                
                # Create a line chart for recent spending trends
                if 'monthly_by_person' in chart_data and not chart_data['monthly_by_person'].empty:
                    # Get most recent 6 months of data
                    recent_months = chart_data['monthly_by_person'].sort_values('Month', ascending=False)
                    if len(recent_months['Month'].unique()) > 6:
                        last_6_months = recent_months['Month'].unique()[:6]
                        recent_months = recent_months[recent_months['Month'].isin(last_6_months)]
                    
                    if not recent_months.empty:
                        # Create a list of months in chronological order for sorting
                        month_order = sorted(recent_months['Month'].unique())
                        
                        chart = alt.Chart(recent_months).mark_line(point=True).encode(
                            x=alt.X('Month:N', title='Month', sort=month_order),  # Sort in chronological order
                            y=alt.Y('Amount:Q', title='Amount ($)'),
                            color=alt.Color('Name:N', title='Person'),
                            tooltip=['Month', 'Name', alt.Tooltip('Amount:Q', format='$.2f')]
                        ).properties(
                            title='Monthly Spending Trends'
                        )
                        
                        st.altair_chart(chart, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
    
    # Tab 2: View and Edit Transactions
    with tab2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<p class="subheader">Transaction History</p>', unsafe_allow_html=True)
        
        # Show success message if deletion was successful
        if st.session_state.delete_success:
            st.success(st.session_state.delete_message)
            # Reset the success flag
            st.session_state.delete_success = False
        
        try:
            if sheet_data and len(sheet_data) > 1:
                # Create DataFrame with proper column names
                df = pd.DataFrame(sheet_data[1:], columns=sheet_data[0])
                
                # Ensure date column is properly converted to datetime
                try:
                    df[sheet_data[0][0]] = pd.to_datetime(df[sheet_data[0][0]])
                except Exception as e:
                    st.warning(f"Warning: Could not convert dates properly. Please check date formats. Error: {str(e)}")
                
                # Add search and filter options
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    search_term = st.text_input("🔍 Search by restaurant", placeholder="Type to search...")
                
                with col2:
                    filter_options = ["All", "Katy", "Sebastien"]
                    name_filter = st.selectbox("Filter by person", filter_options)
                
                with col3:
                    # Get unique months from data
                    if pd.api.types.is_datetime64_any_dtype(df[sheet_data[0][0]]):
                        df['Month'] = df[sheet_data[0][0]].dt.strftime('%Y-%m')
                    else:
                        # Fallback in case date conversion failed
                        try:
                            temp_dates = pd.to_datetime(df[sheet_data[0][0]])
                            df['Month'] = temp_dates.dt.strftime('%Y-%m')
                        except:
                            df['Month'] = 'Unknown'
                    
                    months = ["All"] + sorted([m for m in df['Month'].unique().tolist() if m != 'Unknown'], reverse=True)
                    if 'Unknown' in df['Month'].unique():
                        months.append('Unknown')
                    month_filter = st.selectbox("Filter by month", months)
                
                # Apply filters
                filtered_df = df.copy()
                
                if search_term:
                    filtered_df = filtered_df[filtered_df[sheet_data[0][2]].str.contains(search_term, case=False)]
                
                if name_filter != "All":
                    filtered_df = filtered_df[filtered_df[sheet_data[0][1]] == name_filter]
                
                if month_filter != "All":
                    filtered_df = filtered_df[filtered_df['Month'] == month_filter]
                
                # Display record count
                st.write(f"Showing {len(filtered_df)} of {len(df)} records")
                
                # Add row selection column for deletion
                filtered_df['Select'] = False
                
                # Display the dataframe with editable cells and selection column
                # Determine the appropriate column configuration for the date column
                date_col_config = {}
                if pd.api.types.is_datetime64_any_dtype(filtered_df[sheet_data[0][0]]):
                    # If conversion succeeded, use DateColumn
                    date_col_config = {
                        sheet_data[0][0]: st.column_config.DateColumn(
                            "Date",
                            help="Transaction date",
                            format="YYYY-MM-DD",
                        )
                    }
                else:
                    # If dates are still strings, use TextColumn
                    date_col_config = {
                        sheet_data[0][0]: st.column_config.TextColumn(
                            "Date",
                            help="Transaction date (format: YYYY-MM-DD)"
                        )
                    }
                    
                # Build complete column configuration
                column_config = {
                    "Select": st.column_config.CheckboxColumn(
                        "Select",
                        help="Select rows to delete",
                        default=False,
                    ),
                    sheet_data[0][1]: st.column_config.SelectboxColumn(
                        "Name",
                        help="User name",
                        options=["Katy", "Sebastien"],
                        required=True
                    ),
                    sheet_data[0][2]: st.column_config.TextColumn(
                        "Restaurant",
                        help="Restaurant name",
                    ),
                    sheet_data[0][3]: st.column_config.NumberColumn(
                        "Bill Amount",
                        help="Edit the bill amount",
                        min_value=0.0,
                        step=0.01,
                        format="$%.2f"
                    ),
                    "Month": st.column_config.Column(
                        "Month",
                        help="Month of transaction",
                        disabled=True
                    )
                }
                
                # Merge the date column configuration
                column_config.update(date_col_config)
                
                # Create data editor with appropriate configuration
                try:
                    edited_df = st.data_editor(
                        filtered_df,
                        use_container_width=True,
                        num_rows="fixed",
                        column_config=column_config,
                        hide_index=True,
                        height=400,
                        key="transaction_editor"
                    )
                except Exception as e:
                    st.error(f"Error displaying data editor: {str(e)}")
                    # Fallback to non-editable display
                    st.warning("Displaying transactions in read-only mode due to data type issues")
                    st.dataframe(filtered_df.drop(columns=["Select"], errors="ignore"), 
                                use_container_width=True,
                                hide_index=True)
                
                # Get selected rows for deletion
                selected_rows = edited_df[edited_df['Select']].index.tolist()
                
                # FIX 1: Improved calculation of selected indices
                selected_indices = []
                for idx in selected_rows:
                    if idx < len(edited_df):
                        # Extract the date from the selected row
                        selected_date = edited_df.iloc[idx][sheet_data[0][0]]
                        selected_name = edited_df.iloc[idx][sheet_data[0][1]]
                        selected_restaurant = edited_df.iloc[idx][sheet_data[0][2]]
                        
                        # Find matching row in original df
                        for i, row in df.iterrows():
                            if (row[sheet_data[0][0]] == selected_date and 
                                row[sheet_data[0][1]] == selected_name and 
                                row[sheet_data[0][2]] == selected_restaurant):
                                selected_indices.append(i)
                                break
                
                # Detect changes in edited_df vs original df
                changes_made = False
                changes = []
                
                for idx, row in edited_df.iterrows():
                    # Find matching row in original df
                    orig_idx = df.index[df[sheet_data[0][0]] == row[sheet_data[0][0]]].tolist()
                    if orig_idx:
                        orig_row = df.iloc[orig_idx[0]]
                        
                        # Check each field for changes
                        for col in [sheet_data[0][1], sheet_data[0][2], sheet_data[0][3]]:
                            if str(row[col]) != str(orig_row[col]):
                                changes_made = True
                                changes.append({
                                    'row': orig_idx[0],
                                    'col': col,
                                    'col_idx': sheet_data[0].index(col),
                                    'old_value': orig_row[col],
                                    'new_value': row[col]
                                })
                
                # Add spacing
                st.write("")
                
                # Action buttons in two columns
                col1, col2 = st.columns(2)
                
                # Submit modifications button
                with col1:
                    if changes_made:
                        st.info(f"{len(changes)} changes detected. Click to save.")
                    
                    submit_button = st.button(
                        "💾 Save Changes", 
                        key="submit_mods", 
                        disabled=not changes_made,
                        use_container_width=True,
                        type="primary"
                    )
                    
                    if submit_button and changes:
                        updated_count = 0
                        try:
                            for change in changes:
                                # Get the actual row number in the sheet (adding 2 for header and 1-based indexing)
                                sheet_row = change['row'] + 2
                                
                                # Update the cell
                                success = update_cell(
                                    service, 
                                    sheet_row,
                                    change['col_idx'],
                                    str(change['new_value'])
                                )
                                
                                if success:
                                    updated_count += 1
                            
                            if updated_count > 0:
                                st.success(f"✅ Successfully updated {updated_count} field(s)")
                                st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error updating cells: {str(e)}")
                
                # FIX 1: Completely revised deletion process using session state
                with col2:
                    # Display info about selected rows
                    if selected_rows:
                        st.info(f"{len(selected_rows)} rows selected for deletion.")
                    
                    # If we're in confirmation mode, show the confirmation dialog
                    if st.session_state.confirm_deletion:
                        st.warning(f"Are you sure you want to delete {len(st.session_state.rows_to_delete)} transaction(s)?")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.button("Yes, Delete", on_click=perform_deletion, key="confirm_delete", type="primary")
                        with col2:
                            st.button("Cancel", on_click=cancel_deletion, key="cancel_delete")
                    else:
                        # Normal delete button
                        delete_button = st.button(
                            "🗑️ Delete Selected", 
                            key="delete_rows",
                            disabled=not selected_indices,
                            use_container_width=True,
                            type="secondary" if not selected_indices else "primary"
                        )
                        
                        if delete_button and selected_indices:
                            # Save rows to delete and set confirmation mode
                            st.session_state.rows_to_delete = selected_indices
                            st.session_state.confirm_deletion = True
                            st.rerun()
            else:
                st.info("No transactions available.")
                
        except Exception as e:
            st.error(f"Error loading transactions: {str(e)}")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Tab 3: Analytics (New Tab)
    with tab3:
        if 'chart_data' in locals() and chart_data and not chart_df.empty:
            # Split into two columns for charts
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.subheader("Monthly Spending by Person")
                
                if 'monthly_by_person' in chart_data and not chart_data['monthly_by_person'].empty:
                    # Sort months in chronological order
                    month_order = sorted(chart_data['monthly_by_person']['Month'].unique())
                    
                    monthly_chart = alt.Chart(chart_data['monthly_by_person']).mark_bar().encode(
                        x=alt.X('Month:N', title='Month', sort=month_order),
                        y=alt.Y('Amount:Q', title='Amount ($)'),
                        color=alt.Color('Name:N', title='Person'),
                        tooltip=['Month', 'Name', alt.Tooltip('Amount:Q', format='$.2f')]
                    ).properties(
                        title='Monthly Spending Comparison'
                    )
                    
                    st.altair_chart(monthly_chart, use_container_width=True)
                else:
                    st.info("Not enough data for this chart")
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.subheader("Spending by Restaurant")
                
                if 'restaurant_amount' in chart_data and not chart_data['restaurant_amount'].empty:
                    # Limit to top 5 restaurants
                    top_restaurants_amount = chart_data['restaurant_amount'].head(5)
                    
                    restaurant_chart = alt.Chart(top_restaurants_amount).mark_bar().encode(
                        x=alt.X('Amount:Q', title='Total Spent ($)'),
                        y=alt.Y('Restaurant:N', title='Restaurant', sort='-x'),
                        color=alt.Color('Amount:Q', scale=alt.Scale(scheme='greens')),
                        tooltip=['Restaurant', alt.Tooltip('Amount:Q', format='$.2f')]
                    ).properties(
                        title='Top 5 Restaurants by Spending'
                    )
                    
                    st.altair_chart(restaurant_chart, use_container_width=True)
                else:
                    st.info("Not enough data for this chart")
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col2:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.subheader("Summary Table")
                
                if not summary_table.empty:
                    # Create formatters for different columns
                    formatters = {
                        'Katy': '${:,.2f}',
                        'Sebastien': '${:,.2f}',
                        'Monthly Difference': '${:,.2f}',
                        'Running Balance': '${:,.2f}',
                        'Katy (Count)': '{:.0f}',
                        'Sebastien (Count)': '{:.0f}',
                        'Count Difference': '{:.0f}'
                    }
                    
                    # Apply conditional formatting - fixed to work with pandas styling
                    def highlight_amount_diff(s):
                        return ['background-color: #e6ffe6; color: #006600' if v > 0 
                                else 'background-color: #ffe6e6; color: #990000' if v < 0
                                else '' for v in s]
                    
                    def highlight_count_diff(s):
                        return ['background-color: #e6ffe6; color: #006600' if v > 0 
                                else 'background-color: #ffe6e6; color: #990000' if v < 0
                                else '' for v in s]
                    
                    styled_table = summary_table.style.format(formatters)\
                        .apply(highlight_amount_diff, subset=['Monthly Difference', 'Running Balance'])\
                        .apply(highlight_count_diff, subset=['Count Difference'])
                    
                    st.dataframe(styled_table, use_container_width=True, height=400)
                else:
                    st.info("No data available yet.")
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Donut chart for visit distribution
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.subheader("Visit Distribution")
                
                # Create a donut chart for visit distribution by person
                visit_data = pd.DataFrame({
                    'Person': ['Katy', 'Sebastien'],
                    'Visits': [
                        summary_table.loc['Total', 'Katy (Count)'] if not summary_table.empty else 0,
                        summary_table.loc['Total', 'Sebastien (Count)'] if not summary_table.empty else 0
                    ]
                })
                
                if not visit_data.empty and sum(visit_data['Visits']) > 0:
                    # Calculate percentage
                    total_visits = sum(visit_data['Visits'])
                    visit_data['Percentage'] = visit_data['Visits'] / total_visits
                    
                    # Create the chart
                    visit_chart = alt.Chart(visit_data).mark_arc(innerRadius=50).encode(
                        theta=alt.Theta(field="Visits", type="quantitative"),
                        color=alt.Color(field="Person", type="nominal", scale=alt.Scale(range=['#FF9AA2', '#86C7F3'])),
                        tooltip=['Person', 'Visits', alt.Tooltip('Percentage:Q', format='.1%')]
                    ).properties(
                        title='Restaurant Visits by Person',
                        width=300,
                        height=300
                    )
                    
                    # Add text in the center
                    text = alt.Chart(pd.DataFrame({'text': [f'Total: {int(total_visits)}']})).mark_text(
                        fontSize=20,
                        font='Arial',
                        align='center'
                    ).encode(
                        text='text:N'
                    )
                    
                    st.altair_chart(visit_chart + text, use_container_width=True)
                else:
                    st.info("Not enough data for this chart")
                st.markdown('</div>', unsafe_allow_html=True)
        
        else:
            st.info("No data available for analytics. Please add some expenses first.")
    
    # Footer
    st.markdown("""
    <div class="footer">
        Restaurant Expense Tracker • Updated March 2025
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
