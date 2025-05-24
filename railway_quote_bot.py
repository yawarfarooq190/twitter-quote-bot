#!/usr/bin/env python3
"""
Railway Twitter Quote Bot
Sequential version - posts rows in order without duplicates
"""

import os
import json
import logging
from datetime import datetime
import tweepy
import gspread
from google.oauth2.service_account import Credentials

# Set up logging for Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]  # Only console logging for Railway
)
logger = logging.getLogger(__name__)

class RailwayQuoteBot:
    def __init__(self):
        """Initialize the Railway Quote Bot"""
        self.setup_twitter()
        self.setup_google_sheets()
        
    def setup_twitter(self):
        """Initialize Twitter API connection"""
        try:
            self.twitter_client = tweepy.Client(
                bearer_token=os.getenv('TWITTER_BEARER_TOKEN'),
                consumer_key=os.getenv('TWITTER_CONSUMER_KEY'),
                consumer_secret=os.getenv('TWITTER_CONSUMER_SECRET'),
                access_token=os.getenv('TWITTER_ACCESS_TOKEN'),
                access_token_secret=os.getenv('TWITTER_ACCESS_TOKEN_SECRET'),
                wait_on_rate_limit=True
            )
            
            # Test connection
            me = self.twitter_client.get_me()
            logger.info(f"Twitter API connected successfully! User: @{me.data.username}")
            
        except Exception as e:
            logger.error(f"Twitter API connection failed: {str(e)}")
            raise
    
    def setup_google_sheets(self):
        """Initialize Google Sheets API connection"""
        try:
            # Get service account info from environment variable
            service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
            if not service_account_json:
                raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON environment variable not set")
            
            # Parse JSON and create credentials
            service_account_info = json.loads(service_account_json)
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            credentials = Credentials.from_service_account_info(
                service_account_info, 
                scopes=scopes
            )
            
            # Initialize Google Sheets client
            self.gc = gspread.authorize(credentials)
            
            # Open spreadsheet
            sheets_id = os.getenv('GOOGLE_SHEETS_ID')
            worksheet_name = os.getenv('GOOGLE_WORKSHEET_NAME', 'Sheet1')
            
            self.sheet = self.gc.open_by_key(sheets_id)
            self.worksheet = self.sheet.worksheet(worksheet_name)
            
            logger.info("Google Sheets API connected successfully!")
            
        except Exception as e:
            logger.error(f"Google Sheets API connection failed: {str(e)}")
            raise
    
    def get_current_row_index(self):
        """Get the current row index from tracking sheet or column"""
        try:
            # Try to get tracking sheet first
            try:
                tracking_sheet = self.sheet.worksheet('tracking')
                current_row = tracking_sheet.cell(1, 1).value
                return int(current_row) if current_row else 2  # Start from row 2 (after headers)
            except:
                # If tracking sheet doesn't exist, create it
                logger.info("Creating tracking sheet...")
                tracking_sheet = self.sheet.add_worksheet(title='tracking', rows=1, cols=1)
                tracking_sheet.update('A1', '2')  # Start from row 2
                return 2
                
        except Exception as e:
            logger.error(f"Error getting current row index: {str(e)}")
            return 2  # Default to row 2
    
    def update_current_row_index(self, new_row):
        """Update the current row index in tracking sheet"""
        try:
            tracking_sheet = self.sheet.worksheet('tracking')
            tracking_sheet.update('A1', str(new_row))
            logger.info(f"Updated current row to: {new_row}")
        except Exception as e:
            logger.error(f"Error updating current row index: {str(e)}")
    
    def get_next_quote(self):
        """Get the next quote in sequence"""
        try:
            # Get current row index
            current_row = self.get_current_row_index()
            
            # Get all data to check total rows
            all_data = self.worksheet.get_all_values()
            total_rows = len(all_data)
            
            # If we've gone past the last row, reset to row 2 (after headers)
            if current_row > total_rows:
                current_row = 2
                logger.info("Reached end of sheet, resetting to beginning")
            
            # Get the specific row data
            if current_row <= total_rows:
                row_data = all_data[current_row - 1]  # Convert to 0-based index
                
                # Parse the row data (assuming first column is quote, second is author)
                quote_text = row_data[0].strip() if len(row_data) > 0 and row_data[0] else None
                author = row_data[1].strip() if len(row_data) > 1 and row_data[1] else None
                
                if quote_text:
                    # Update to next row for next execution
                    next_row = current_row + 1
                    if next_row > total_rows:
                        next_row = 2  # Reset to beginning
                    
                    self.update_current_row_index(next_row)
                    
                    return {
                        'text': quote_text,
                        'author': author,
                        'row': current_row
                    }
            
            logger.error(f"No valid quote found at row {current_row}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting next quote: {str(e)}")
            return None
    
    def format_tweet(self, quote_data):
        """Format quote into tweet (without hashtags as per your original code)"""
        quote_text = quote_data['text']
        author = quote_data.get('author')
        
        # Start with quoted text
        tweet = f'{quote_text}'
        
        # Add author if available
        if author:
            tweet += f' - {author}'
        
        # Ensure tweet fits Twitter's 280 character limit
        if len(tweet) > 280:
            max_quote_length = 280 - len(' - ') - len(author or '') - 2
            if max_quote_length > 50:
                quote_text = quote_text[:max_quote_length-3] + '...'
                tweet = f'{quote_text}'
                if author:
                    tweet += f' - {author}'
        
        return tweet
    
    def post_quote(self):
        """Main function to select and post the next quote in sequence"""
        try:
            logger.info("Starting sequential quote posting process...")
            
            # Get next quote in sequence
            quote_data = self.get_next_quote()
            
            if not quote_data:
                logger.error("No quote found to post!")
                return False
            
            logger.info(f"Selected quote from row {quote_data['row']}: {quote_data['text'][:50]}...")
            
            # Format tweet
            tweet_text = self.format_tweet(quote_data)
            
            # Post to Twitter
            response = self.twitter_client.create_tweet(text=tweet_text)
            
            if response.data:
                tweet_id = response.data['id']
                logger.info(f"Tweet posted successfully!")
                logger.info(f"Tweet ID: {tweet_id}")
                logger.info(f"Tweet content: {tweet_text}")
                return True
            else:
                logger.error("Failed to post tweet - no response data")
                return False
                
        except Exception as e:
            logger.error(f"Error posting quote: {str(e)}")
            return False

def main():
    """Main function for Railway execution"""
    try:
        logger.info("=== Railway Quote Bot Starting (Sequential Mode) ===")
        logger.info(f"Execution time: {datetime.now()}")
        
        # Initialize and run bot
        bot = RailwayQuoteBot()
        success = bot.post_quote()
        
        if success:
            logger.info("=== Bot execution completed successfully! ===")
        else:
            logger.error("=== Bot execution failed ===")
            exit(1)
            
    except Exception as e:
        logger.error(f"Bot crashed: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
