import streamlit as st
import pandas as pd
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.oauth2 import service_account
import os

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
        
        # First, get the current values
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=cell_range
        ).execute()
        
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

def main():
    st.title("Restaurant Expense Tracker")
    
    # Create tabs
    tab1, tab2 = st.tabs(["Add Expense", "View/Edit Transactions"])
    
    # Tab 1: Add Expense
    with tab1:
        name_options = ["", "Katy", "Sebastien"]
        restaurant_options = ["", "Imperial", "Ramen", "Baton Rouge", "Marathon", "Miss Pho", "Indian", "Starbucks"]

        col1, col2 = st.columns(2)
        
        with col1:
            default_name = st.selectbox("Select your name", name_options, key="tab1_name")
            if default_name == "":
                user_name = st.text_input("Or enter a custom name", key="tab1_custom_name")
            else:
                user_name = default_name

        with col2:
            default_restaurant = st.selectbox("Select restaurant", restaurant_options, key="tab1_restaurant")
            if default_restaurant == "":
                restaurant = st.text_input("Or enter a custom restaurant", key="tab1_custom_restaurant")
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
                    # Create formatters for different columns
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
    
    # Tab 2: View and Edit Transactions
    with tab2:
        try:
            service = setup_google_sheets()
            sheet_data = fetch_sheet_data(service)
            
            if sheet_data:
                # Create DataFrame with proper column names
                df = pd.DataFrame(sheet_data[1:], columns=sheet_data[0])
                
                # Display editable dataframe
                st.subheader("All Transactions")
                st.write("Click on cells to edit values. All changes will be saved when you click 'Submit Modifications'")
                
                # Add row selection column for deletion
                df['Select'] = False
                
                # Display the dataframe with editable cells and selection column
                edited_df = st.data_editor(
                    df,
                    use_container_width=True,
                    num_rows="fixed",
                    hide_index=True,
                    column_config={
                        "Select": st.column_config.CheckboxColumn(
                            "Select",
                            help="Select rows to delete",
                            default=False,
                        ),
                        "date": st.column_config.DateColumn(
                            "Date",
                            help="Transaction date",
                            disabled=True
                        ),
                        "user_name": st.column_config.TextColumn(
                            "Name",
                            help="User name",
                            disabled=True
                        ),
                        "restaurant": st.column_config.TextColumn(
                            "Restaurant",
                            help="Restaurant name",
                            disabled=True
                        ),
                        "bill_amount": st.column_config.NumberColumn(
                            "Bill Amount",
                            help="Edit the bill amount",
                            min_value=0.0,
                            step=0.01,
                            format="$%.2f"
                        )
                    },
                    key="transaction_editor"
                )
                
                # Get selected rows for deletion
                selected_rows = edited_df[edited_df['Select']].index.tolist()

                # Convert bill_amount to numeric, dropping any non-numeric values
                edited_df['bill_amount'] = pd.to_numeric(edited_df['bill_amount'], errors='coerce')
                df['bill_amount'] = pd.to_numeric(df['bill_amount'], errors='coerce')
                
                col1, col2 = st.columns(2)
                
                # Submit modifications button
                with col1:
                    # Check if there are any actual changes in the bill amounts
                    changes_made = False
                    changes = []
                    
                    for idx in range(len(df)):
                        if df.iloc[idx]['bill_amount'] != edited_df.iloc[idx]['bill_amount']:
                            changes_made = True
                            changes.append({
                                'row': idx,
                                'old_value': df.iloc[idx]['bill_amount'],
                                'new_value': edited_df.iloc[idx]['bill_amount']
                            })
                    
                    if st.button("Submit Modifications", key="submit_mods", disabled=not changes_made):
                        updated_count = 0
                        try:
                            for change in changes:
                                # Get the actual row number in the sheet (adding 2 for header and 1-based indexing)
                                sheet_row = change['row'] + 2
                                
                                # Update the cell
                                success = update_cell(
                                    service, 
                                    sheet_row,
                                    3,  # bill_amount column (D)
                                    str(change['new_value'])
                                )
                                
                                if success:
                                    updated_count += 1
                                    st.success(f"✓ Updated amount: ${change['old_value']:.2f} → ${change['new_value']:.2f}")
                                else:
                                    st.error(f"Failed to update row {sheet_row}")
                            
                            if updated_count > 0:
                                st.success(f"Successfully updated {updated_count} amount(s)")
                                st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error updating cells: {str(e)}")

                
                # Delete selected rows button
                with col2:
                    if selected_rows and st.button("Delete Selected Rows", key="delete_rows"):
                        try:
                            deleted_count = 0
                            # Delete in reverse order to maintain correct indices
                            for idx in sorted(selected_rows, reverse=True):
                                if delete_row(service, idx + 2):  # +2 because of header and 0-based index
                                    deleted_count += 1
                            
                            if deleted_count > 0:
                                st.success(f"Successfully deleted {deleted_count} row(s)")
                                st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error deleting rows: {str(e)}")
                    
            else:
                st.info("No transactions available.")
                
        except Exception as e:
            st.error(f"Error loading transactions: {str(e)}")

if __name__ == "__main__":
    main()
