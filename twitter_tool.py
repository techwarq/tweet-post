"""All-in-one Twitter scraper and post generator optimized for personal info and viral tweets."""
import os
import json
import re
import time
import logging
import requests
from langchain_groq import ChatGroq
from config import DATA_DIR, TAVILY_API_KEY

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("twitter_tool.log"), logging.StreamHandler()]
)
logger = logging.getLogger("TwitterTool")

class TwitterTool:
    """Twitter tool that handles user info storage, scraping and post generation."""
    
    def __init__(self, api_key: str, llm: ChatGroq, data_dir: str = DATA_DIR):
        """Initialize the Twitter tool."""
        self.api_key = api_key
        self.llm = llm
        self.data_dir = data_dir
        self.extract_api_url = "https://api.tavily.com/extract"
        self.search_api_url = "https://api.tavily.com/search"
        
        # Create data directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Create user_info directory
        self.user_info_dir = os.path.join(self.data_dir, "user_info")
        os.makedirs(self.user_info_dir, exist_ok=True)
        
        logger.info("TwitterTool initialized with data directory: %s", self.data_dir)
    
    def save_user_info(self, user_id: str, info: dict) -> dict:
        """Save user information to be used in tweet generation."""
        try:
            # Create a dedicated file for user info
            filename = os.path.join(self.user_info_dir, f"{user_id}_info.json")
            
            # If file exists, load and merge with new info
            existing_info = {}
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    existing_info = json.load(f)
            
            # Merge existing info with new info
            merged_info = {**existing_info, **info}
            
            # Save the merged info
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(merged_info, f, indent=4)
            
            logger.info("Successfully saved user information for %s", user_id)
            return {
                "success": True,
                "message": f"Successfully saved user information for {user_id}",
                "user_info": merged_info
            }
        except Exception as e:
            logger.error("Error saving user information: %s", str(e))
            return {
                "success": False,
                "message": f"Error saving user information: {str(e)}"
            }
    
    def get_user_info(self, user_id: str) -> dict:
        """Get saved user information."""
        try:
            filename = os.path.join(self.user_info_dir, f"{user_id}_info.json")
            if not os.path.exists(filename):
                logger.warning("No information found for %s", user_id)
                return {
                    "success": False,
                    "message": f"No information found for {user_id}",
                    "user_info": {}
                }
            
            with open(filename, 'r', encoding='utf-8') as f:
                user_info = json.load(f)
            
            logger.info("Successfully retrieved user information for %s", user_id)
            return {
                "success": True,
                "message": f"Successfully retrieved user information for {user_id}",
                "user_info": user_info
            }
        except Exception as e:
            logger.error("Error retrieving user information: %s", str(e))
            return {
                "success": False,
                "message": f"Error retrieving user information: {str(e)}",
                "user_info": {}
            }
    
    def _extract_tweets(self, url: str, username: str, extract_depth: str = "advanced") -> list:
        """Extract tweets from a given URL using Tavily API.
        
        Args:
            url: The URL to extract tweets from
            username: Twitter username to extract tweets for
            extract_depth: Extraction depth - must be either "basic" or "advanced"
            
        Returns:
            List of tweet dictionaries
        """
        # Validate extract_depth to prevent 422 errors
        if extract_depth not in ["basic", "advanced"]:
            logger.warning("Invalid extract_depth '%s'. Using 'advanced' instead.", extract_depth)
            extract_depth = "advanced"
            
        try:
            logger.info("Extracting tweets from %s with depth %s", url, extract_depth)
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "urls": [url],
                "include_images": False,
                "extract_depth": extract_depth
            }
            
            response = requests.post(
                self.extract_api_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"API Error: {response.status_code} - {response.text}")
                return []
            
            extract_response = response.json()
            if not extract_response.get('results'):
                logger.warning("No results returned from extraction API for %s", url)
                return []
            
            raw_content = extract_response['results'][0]['raw_content']
            tweets = self._process_raw_content_to_tweets(username, raw_content)
            logger.info("Extracted %d tweets from %s", len(tweets), url)
            return tweets
            
        except Exception as e:
            logger.error("Error extracting from %s: %s", url, str(e))
            return []
    
    def _deduplicate_tweets(self, tweets: list) -> list:
        """Remove duplicate tweets based on text content."""
        unique_tweets = []
        seen_texts = set()
        
        for tweet in tweets:
            text = tweet.get("text", "").strip().lower()
            if text and text not in seen_texts:
                seen_texts.add(text)
                unique_tweets.append(tweet)
        
        logger.info("Deduplicated %d tweets to %d unique tweets", len(tweets), len(unique_tweets))
        return unique_tweets
    
    def scrape_profile(self, username: str) -> dict:
        """Scrape tweets from a Twitter profile using Tavily extract API."""
        try:
            logger.info("Starting scrape_profile for %s", username)
            
            # Get profile URL and timeline URL
            profile_url = f"https://x.com/{username}"
            
            
            # Extract from both profile and timeline
            profile_tweets = self._extract_tweets(profile_url, username)
           
            
            # Combine and deduplicate tweets
            all_tweets = profile_tweets
            unique_tweets = self._deduplicate_tweets(all_tweets)
            
            # If we don't have enough tweets, try again with advanced extraction
            if len(unique_tweets) < 30:
                logger.info("Not enough tweets found (%d). Trying advanced extraction.", len(unique_tweets))
                # Use "advanced" instead of "deep" to avoid 422 error
                advanced_tweets = self._extract_tweets(profile_url, username, extract_depth="advanced")
                unique_tweets = self._deduplicate_tweets(unique_tweets + advanced_tweets)
            
            # Sort by engagement and take top 30
            unique_tweets.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)
            final_tweets = unique_tweets[:30]
            
            # Save and analyze
            self.save_data(username, final_tweets, "tweets")
            analysis = self.analyze_tweets(username, final_tweets)
            
            logger.info("Successfully scraped %d tweets from @%s", len(final_tweets), username)
            return {
                "success": True,
                "message": f"Successfully scraped {len(final_tweets)} tweets from @{username}",
                "tweet_count": len(final_tweets),
                "performance_analysis": analysis,
                "tweets": final_tweets[:10]  # Preview
            }
            
        except Exception as e:
            logger.error("Error scraping profile: %s", str(e))
            return {"success": False, "message": f"Error scraping profile: {str(e)}"}
    
    def _process_raw_content_to_tweets(self, username: str, raw_content: str) -> list:
        """Process raw HTML content to extract tweets."""
        try:
            logger.info("Processing raw content for tweets from @%s", username)
            
            prompt = f"""
            Extract ALL tweets from this Twitter/X profile content for @{username}.
            
            For each tweet, extract:
            1. Full text content (including any threads)
            2. Engagement metrics (likes, retweets, views)
            3. Calculate engagement_score = likes + (retweets * 2)
            
            Return a JSON array with these fields for each tweet:
            - text: complete tweet text
            - likes: number (convert K/M to thousands/millions)
            - retweets: number 
            - views: number
            - url: tweet URL if available
            - engagement_score: calculated score
            
            Raw content:
            {raw_content[:15000]}  # First 15k chars to avoid token limits
            """
            
            response = self.llm.invoke(prompt)
            tweets = self.parse_json_from_response(response.content)
            
            # Ensure we have a list of tweets
            if not isinstance(tweets, list):
                logger.warning("LLM response was not a list. Converting to list.")
                if isinstance(tweets, dict):
                    tweets = [tweets]
                else:
                    tweets = []
            
            # Ensure we have proper engagement scores
            for tweet in tweets:
                if "engagement_score" not in tweet:
                    likes = tweet.get("likes", 0) or 0  # Convert None to 0
                    retweets = tweet.get("retweets", 0) or 0  # Convert None to 0
                    tweet["engagement_score"] = likes + (retweets * 2)
            
            logger.info("Processed %d tweets from raw content", len(tweets))
            return tweets
            
        except Exception as e:
            logger.error("Error processing content: %s", str(e))
            return []
    
    def _clean_post_text(self, text: str) -> str:
        """Clean post text by removing markdown, HTML tags, and extra whitespace."""
        if not text:
            return ""
        
        # Remove HTML tags if any
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove markdown formatting
        text = re.sub(r'[*_`#]', '', text)
        
        # Remove JSON artifacts if present
        text = re.sub(r'\\"', '"', text)
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    def _format_hashtag(self, tag: str) -> str:
        """Format a hashtag string to be clean and consistent."""
        if not tag:
            return ""
        
        # Remove any # symbols and whitespace
        tag = re.sub(r'[#\s]', '', tag)
        
        # Convert to lowercase for consistency
        return tag.lower()
    
    def analyze_tweets(self, username: str, tweets: list) -> dict:
        """Analyze tweets to identify patterns for successful posts."""
        if not tweets:
            logger.warning("No tweets available for analysis for %s", username)
            return {"success": False, "message": "No tweets available for analysis"}
        
        try:
            logger.info("Analyzing %d tweets for @%s", len(tweets), username)
            
            # Sort by engagement score
            tweets_by_engagement = sorted(tweets, key=lambda x: x.get("engagement_score", 0), reverse=True)
            
            # Get top performing tweets
            top_tweets = tweets_by_engagement[:min(10, len(tweets_by_engagement))]
            
            # Create analysis prompt
            prompt = f"""
            Analyze these top performing tweets for @{username} and identify patterns that make them successful.
            
            Top tweets:
            {json.dumps(top_tweets, indent=2)}
            
            Return a JSON object with these keys:
            1. "content_patterns": List of 3-5 specific content patterns that appear in successful tweets
            2. "style_elements": List of 3-5 writing style elements that contribute to success
            3. "optimal_format": Brief description of the ideal tweet format based on these examples
            4. "recommendations": 3-5 specific, actionable recommendations for creating viral tweets
            
            Return ONLY the JSON object without any explanation.
            """
            
            # Get analysis from LLM
            analysis_response = self.llm.invoke(prompt)
            
            # Parse the result
            try:
                analysis_result = self.parse_json_from_response(analysis_response.content)
                
                if not analysis_result or not isinstance(analysis_result, dict):
                    raise ValueError("Invalid analysis result format")
                    
                analysis_result["success"] = True
                
                # Ensure all required fields exist
                for field in ["content_patterns", "style_elements", "optimal_format", "recommendations"]:
                    if field not in analysis_result:
                        analysis_result[field] = []
                        if field in ["optimal_format"]:
                            analysis_result[field] = "Not provided by analysis"
                
                # Save the analysis
                self.save_data(username, analysis_result, "analysis")
                logger.info("Analysis completed successfully for @%s", username)
                
                return analysis_result
                    
            except Exception as e:
                # Detailed error for debugging
                logger.error("Analysis parsing error: %s", str(e))
                
                # Fallback if parsing fails
                fallback_analysis = {
                    "success": True,
                    "content_patterns": [
                        "Sharing unique technical projects",
                        "Relatable tech frustrations",
                        "Short, impactful statements"
                    ],
                    "style_elements": [
                        "Direct, concise language",
                        "Technical authenticity",
                        "Occasional humor"
                    ],
                    "optimal_format": "Short, clear statements with technical substance or relatable observations",
                    "recommendations": [
                        "Share unique technical insights",
                        "Keep tweets concise and to the point",
                        "Include specific technical details",
                        "Address common pain points in tech"
                    ],
                    "message": "Analysis completed but couldn't be structured as JSON"
                }
                
                # Save the fallback analysis
                self.save_data(username, fallback_analysis, "analysis")
                
                return fallback_analysis
                
        except Exception as e:
            logger.error("Error in tweet analysis: %s", str(e))
            return {
                "success": False,
                "message": f"Error analyzing tweets: {str(e)}",
                "content_patterns": ["Error in analysis"],
                "style_elements": ["Error in analysis"],
                "optimal_format": "Error in analysis",
                "recommendations": ["Error in analysis"]
            }

    def generate_post(self, username: str, topic: str, length: str = "Medium", user_id: str = None) -> dict:
        """Generate a Twitter post based on analysis and personal info if available."""
        try:
            logger.info("Generating post for @%s on topic '%s' with length '%s'", username, topic, length)
            
            # Load tweets
            tweets = self.load_data(username, "tweets")
            if not tweets:
                logger.warning("No tweets found for @%s", username)
            
            # Load analysis
            analysis = self.load_data(username, "analysis")
            if not analysis:
                logger.warning("No analysis found for @%s", username)
            
            # Load user info if provided
            user_info = {}
            if user_id:
                user_info_response = self.get_user_info(user_id)
                if user_info_response.get("success"):
                    user_info = user_info_response.get("user_info", {})
                    logger.info("Loaded user info for %s", user_id)
                else:
                    logger.warning("Failed to load user info for %s", user_id)
            
            # Sort tweets by engagement
            if tweets:
                tweets.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)
            
            # Create generation prompt
            length_guidelines = {
                "Short": "under 20 words",
                "Medium": "40 words",
                "Long": "100 words (full tweet thread)"
            }
            
            # Build prompt with user info if available
            user_info_section = ""
            if user_info:
                user_info_section = f"""
                User's personal information:
                {json.dumps(user_info, indent=2)}
                
                Incorporate this personal information naturally into the tweet when appropriate.
                """
            
            prompt = f"""
            Generate a Twitter post for a user on the topic of {topic}.
            
            Length: {length} ({length_guidelines.get(length)})
            
            {user_info_section}
            
            User's tweet style reference (from @{username}):
            {json.dumps(tweets[:5] if tweets else [], indent=2)}
            
            Performance analysis:
            {json.dumps(analysis, indent=2) if analysis else "Not available"}
            
            Return a JSON object with these fields:
            - post: the generated tweet text
            - hashtags: relevant hashtags to include (0-3)
            - best_time: suggested posting time
            - viral_elements: key viral elements incorporated in this post
            - engagement_prediction: expected engagement level (high/medium/low)
            
            Return ONLY the JSON object without any explanation.
            """
            
            # Get post from LLM
            logger.info("Sending prompt to LLM for post generation")
            post_response = self.llm.invoke(prompt)
            
            # Parse the result with robust error handling
            try:
                result = self.parse_json_from_response(post_response.content)
                
                if not result:
                    raise ValueError("Empty result from LLM response parsing")
                
                # Clean up result
                if isinstance(result, list) and len(result) > 0:
                    result = result[0]
                
                # Ensure required fields are present
                required_fields = {
                    "post": "Generated post not available",
                    "hashtags": [],
                    "best_time": "8-10 AM or 6-8 PM local time",
                    "viral_elements": ["authenticity", "relevance"],
                    "engagement_prediction": "medium"
                }
                
                for field, default in required_fields.items():
                    if field not in result:
                        result[field] = default
                
                # Clean post text
                if "post" in result:
                    result["post"] = self._clean_post_text(result["post"])
                
                # Clean hashtags
                if "hashtags" in result:
                    if isinstance(result["hashtags"], str):
                        # Handle case where hashtags is a string
                        result["hashtags"] = [self._format_hashtag(result["hashtags"])]
                    elif isinstance(result["hashtags"], list):
                        result["hashtags"] = [self._format_hashtag(tag) for tag in result["hashtags"] if tag]
                    else:
                        result["hashtags"] = []
                else:
                    result["hashtags"] = []
                
                # Add estimated engagement with error handling
                try:
                    result["estimated_metrics"] = self.estimate_engagement(
                        result.get("engagement_prediction", "medium"), 
                        tweets
                    )
                except Exception as e:
                    logger.error("Error estimating engagement: %s", str(e))
                    result["estimated_metrics"] = {
                        "likes": "100-300", 
                        "retweets": "10-50", 
                        "views": "1K-3K"
                    }
                
                result["success"] = True  # <-- Added fix here
                logger.info("Successfully generated post for @%s", username)
                return result
                
            except Exception as e:
                logger.error("Error parsing post generation response: %s", str(e))
                # Fallback with cleaned post text
                clean_post = self._clean_post_text(post_response.content)
                return {
                    "post": clean_post,
                    "hashtags": [],
                    "best_time": "8-10 AM or 6-8 PM local time",
                    "viral_elements": ["authenticity", "relevance"],
                    "engagement_prediction": "medium",
                    "estimated_metrics": {
                        "likes": "100-300", 
                        "retweets": "10-50", 
                        "views": "1K-3K"
                    },
                    "error": f"Generation error: {str(e)}"
                }
                
        except Exception as e:
            logger.error("Critical error in generate_post: %s", str(e))
            return {
                "post": f"Could not generate post due to an error: {str(e)}",
                "hashtags": [],
                "best_time": "8-10 AM or 6-8 PM local time",
                "viral_elements": ["authenticity", "relevance"],
                "engagement_prediction": "medium",
                "estimated_metrics": {
                    "likes": "100-300", 
                    "retweets": "10-50", 
                    "views": "1K-3K"
                }
            }
    
    def estimate_engagement(self, engagement_level: str, tweets: list) -> dict:
        """Estimate engagement metrics based on sample tweets."""
        try:
            if not tweets:
                return {"likes": "100-300", "retweets": "10-50", "views": "1K-3K"}
            
            # Extract engagement metrics with proper None handling
            likes = [tweet.get("likes", 0) or 0 for tweet in tweets]  # Convert None to 0
            retweets = [tweet.get("retweets", 0) or 0 for tweet in tweets]  # Convert None to 0
            views = [tweet.get("views", 0) or 0 for tweet in tweets]  # Convert None to 0
            
            # Filter out zeros if you only want to consider tweets with engagement
            likes = [like for like in likes if like > 0] or [200]  # Default to 200 if no likes
            retweets = [rt for rt in retweets if rt > 0] or [30]    # Default to 30 if no retweets
            views = [view for view in views if view > 0] or [2000]  # Default to 2000 if no views
            
            # Calculate averages
            avg_likes = sum(likes) / len(likes)
            avg_retweets = sum(retweets) / len(retweets)
            avg_views = sum(views) / len(views)
            
            # Adjust based on engagement level
            multiplier = 1.5 if engagement_level.lower() == "high" else (0.5 if engagement_level.lower() == "low" else 1.0)
            
            # Format numbers for display
            def format_number(num):
                if num >= 1000000:
                    return f"{num/1000000:.1f}M"
                elif num >= 1000:
                    return f"{num/1000:.1f}K"
                else:
                    return str(int(num))
            
            likes_est = avg_likes * multiplier
            retweets_est = avg_retweets * multiplier
            views_est = avg_views * multiplier
            
            return {
                "likes": f"{format_number(likes_est * 0.7)}-{format_number(likes_est * 1.3)}",
                "retweets": f"{format_number(retweets_est * 0.7)}-{format_number(retweets_est * 1.3)}",
                "views": f"{format_number(views_est * 0.7)}-{format_number(views_est * 1.3)}"
            }
        except Exception as e:
            logger.error("Error in estimate_engagement: %s", str(e))
            return {"likes": "100-300", "retweets": "10-50", "views": "1K-3K"}
    
    def save_data(self, username: str, data: dict or list, data_type: str) -> None:
        """Save data to a file."""
        try:
            filename = os.path.join(self.data_dir, f"{username}_{data_type}.json")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            logger.info("Saved %s data for %s", data_type, username)
        except Exception as e:
            logger.error("Error saving %s data for %s: %s", data_type, username, str(e))
    
    def load_data(self, username: str, data_type: str) -> dict or list:
        """Load data from a file."""
        filename = os.path.join(self.data_dir, f"{username}_{data_type}.json")
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info("Loaded %s data for %s", data_type, username)
            return data
        except FileNotFoundError:
            logger.warning("%s data not found for %s", data_type.capitalize(), username)
            return [] if data_type == "tweets" else {}
        except json.JSONDecodeError:
            logger.error("Invalid JSON in %s data file for %s", data_type, username)
            return [] if data_type == "tweets" else {}
    
    def parse_json_from_response(self, text: str) -> list or dict:
        """Unified method to parse JSON from LLM responses."""
        try:
            # Try direct JSON parsing first
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
                
            # Try to find JSON in code blocks
            code_block_match = re.search(r'```(?:json)?\n([\s\S]*?)\n```', text)
            if code_block_match:
                return json.loads(code_block_match.group(1))
                
            # Try to find any JSON object or array
            json_pattern = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text, re.DOTALL)
            if json_pattern:
                return json.loads(json_pattern.group(1))
                
            # If we reach here, no JSON was found
            logger.warning("No valid JSON found in response")
            
            # Return a default structure based on content hinting
            if "tweet" in text.lower() or "text" in text.lower():
                if "engagement" in text.lower():
                    return [{"text": "Parsing error", "engagement_score": 0}]
                else:
                    return {"post": text.strip(), "hashtags": []}
            else:
                return {"post": "JSON parsing error", "hashtags": []}
                
        except Exception as e:
            logger.error("JSON parsing error: %s", str(e))
            return {"error": f"JSON parsing error: {str(e)}"}