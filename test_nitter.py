# test_nitter_scraper.py
"""Test the Nitter scraper directly"""
import requests
from bs4 import BeautifulSoup
import re

def test_nitter_scraping(username):
    """Test scraping a Nitter profile."""
    url = f"https://nitter.net/{username}"
    print(f"Testing: {url}\n")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response Length: {len(response.text)} bytes")
        
        if response.status_code != 200:
            print(f"Error: Got status code {response.status_code}")
            return
        
        # Save the response
        with open(f"test_nitter_{username}.html", 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"Saved to test_nitter_{username}.html\n")
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check for error
        error = soup.find('div', class_='error-panel')
        if error:
            print(f"Error Panel: {error.get_text(strip=True)}")
            return
        
        # Check for profile
        profile = soup.find('div', class_='profile-banner') or soup.find('div', class_='profile-card')
        if profile:
            print("✓ Profile found")
            
        # Look for timeline
        timeline = soup.find('div', class_='timeline')
        if timeline:
            print("✓ Timeline found")
        else:
            print("✗ No timeline found")
            
        # Try to find tweets
        print("\nLooking for tweets...")
        
        # Method 1: timeline-item
        timeline_items = soup.find_all('div', class_='timeline-item')
        print(f"Found {len(timeline_items)} timeline-item divs")
        
        if timeline_items:
            print("\nFirst tweet preview:")
            first = timeline_items[0]
            
            # Get text
            content = first.find('div', class_='tweet-content') or first
            text = content.get_text(strip=True)
            print(f"Text: {text[:100]}...")
            
            # Get stats
            stats = first.find('div', class_='tweet-stats')
            if stats:
                print(f"Stats: {stats.get_text(strip=True)}")
        
        # Method 2: Look for any element with tweet in class
        tweet_elements = soup.find_all(attrs={'class': re.compile('tweet')})
        print(f"\nFound {len(tweet_elements)} elements with 'tweet' in class")
        
        # Method 3: Look for conversation IDs
        conv_elements = soup.find_all(attrs={'data-conversation-id': True})
        print(f"Found {len(conv_elements)} elements with data-conversation-id")
        
        # Try to extract actual tweets
        tweets = []
        elements_to_check = timeline_items or tweet_elements or conv_elements
        
        for elem in elements_to_check[:5]:  # Check first 5
            text_elem = elem.find('div', class_='tweet-content') or \
                       elem.find('div', class_='content') or \
                       elem.find('p')
            
            if text_elem:
                text = text_elem.get_text(strip=True)
                if len(text) > 20:  # Skip short texts
                    tweets.append(text)
        
        print(f"\nExtracted {len(tweets)} tweets:")
        for i, tweet in enumerate(tweets):
            print(f"{i+1}. {tweet[:80]}...")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    # Test with a known user
    test_nitter_scraping("elonmusk")  # Known active user
    print("\n" + "="*50 + "\n")
    test_nitter_scraping("mrsiipa")   # The user we're trying to scrape