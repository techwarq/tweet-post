"""Simplified post generation service optimized for virality."""
import os
import json
import re
from langchain_core.output_parsers import JsonOutputParser
from langchain_groq import ChatGroq
from config import DATA_DIR

class PostGenerator:
    """Service for generating viral Twitter posts based on performance analysis."""
    
    def __init__(self, llm: ChatGroq, data_dir: str = DATA_DIR):
        """Initialize the post generator."""
        self.llm = llm
        self.data_dir = data_dir
    
    def load_tweets(self, username: str) -> list:
        """Load saved tweets for a username."""
        filename = os.path.join(self.data_dir, f"{username}_tweets.json")
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                tweets = json.load(f)
                
                # Ensure all tweets have an engagement score
                for tweet in tweets:
                    if "engagement_score" not in tweet:
                        likes = tweet.get("likes", 0)
                        retweets = tweet.get("retweets", 0)
                        tweet["engagement_score"] = likes + (retweets * 2)
                
                return tweets
        except FileNotFoundError:
            return []
    
    def load_analysis(self, username: str) -> dict:
        """Load saved tweet performance analysis."""
        # First try to load it from the analysis-specific file
        try:
            filename = os.path.join(self.data_dir, f"{username}_analysis.json")
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            pass
        
        # Next, try to find it in scrape results
        try:
            filename = os.path.join(self.data_dir, f"{username}_scrape_results.json")
            with open(filename, 'r', encoding='utf-8') as f:
                results = json.load(f)
                if "performance_analysis" in results:
                    return results["performance_analysis"]
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        
        return {}
    
    def categorize_length(self, text: str) -> str:
        """Categorize tweet length."""
        word_count = len(text.split())
        if word_count < 15:
            return "Short"
        elif 15 <= word_count <= 30:
            return "Medium"
        else:
            return "Long"
    
    def get_top_tweets(self, username: str, topic: str = None, count: int = 5) -> list:
        """Get top performing tweets, optionally filtered by topic."""
        tweets = self.load_tweets(username)
        
        if not tweets:
            return []
        
        # Sort by engagement score
        tweets.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)
        
        # Filter by topic if provided
        if topic and topic.lower() not in ["any", "general"]:
            filtered_tweets = []
            topic_terms = topic.lower().split()
            
            for tweet in tweets:
                text_lower = tweet["text"].lower()
                # Count topic term matches
                term_matches = sum(1 for term in topic_terms if term in text_lower)
                # Include if at least one term matches
                if term_matches > 0:
                    filtered_tweets.append(tweet)
            
            # If we have enough topic-filtered tweets, use them
            if len(filtered_tweets) >= 2:
                return filtered_tweets[:count]
            
            # Otherwise, just return top tweets
        
        return tweets[:count]
    
    def generate_post(
        self, 
        username: str, 
        topic: str, 
        length: str = "Medium", 
        optimize_for_virality: bool = True
    ) -> dict:
        """Generate a Twitter post based on performance analysis and top tweets.
        
        Args:
            username: Twitter username to emulate
            topic: Topic of the post
            length: Length category (Short, Medium, Long)
            optimize_for_virality: Whether to optimize for virality
            
        Returns:
            Generated post object
        """
        # Get top tweets as examples
        top_tweets = self.get_top_tweets(username, topic)
        
        # Get performance analysis
        analysis = self.load_analysis(username)
        
        # Determine length guidance
        if length == "Short":
            length_guidance = "under 15 words"
        elif length == "Medium":
            length_guidance = "15-25 words"
        else:  # Long
            length_guidance = "25-40 words"
        
        # Prepare examples section
        examples_text = ""
        if top_tweets:
            examples_text = "Examples of user's top performing tweets:\n\n"
            for i, tweet in enumerate(top_tweets):
                engagement = f"Likes: {tweet.get('likes', 0)}, Retweets: {tweet.get('retweets', 0)}"
                if "views" in tweet and tweet["views"] > 0:
                    engagement += f", Views: {tweet['views']}"
                examples_text += f"Example {i+1} ({engagement}):\n{tweet['text']}\n\n"
        
        # Create generation prompt
        prompt = f"""
        Generate a Twitter post that sounds like @{username} on the topic of {topic}.
        
        Length: {length_guidance}
        Optimize for virality: {optimize_for_virality}
        
        """
        
        # Add performance analysis if available
        if analysis and "success" in analysis and analysis["success"]:
            prompt += f"""
            Performance analysis of user's successful tweets:
            {json.dumps(analysis, indent=2)}
            
            """
        
        # Add examples and generation guidance
        prompt += f"""
        {examples_text}
        
        Key elements to include:
        1. Match the user's authentic voice and style
        2. Focus on the requested topic
        3. Incorporate elements that drive high engagement
        4. Create a sense of urgency or interest to maximize views
        
        Return a JSON object with these fields:
        - post: the generated tweet text
        - hashtags: relevant hashtags to include (0-3)
        - best_time: suggested posting time
        - viral_elements: key viral elements incorporated in this post
        - engagement_prediction: expected engagement level (high/medium/low)
        
        Return ONLY the JSON object with no other text.
        """
        
        # Generate the post
        response = self.llm.invoke(prompt)
        
        try:
            # Parse the JSON response
            json_parser = JsonOutputParser()
            result = json_parser.parse(response.content)
            
            # Clean up result
            if "post" in result:
                result["post"] = result["post"].strip()
            
            # Add estimated engagement
            if "engagement_prediction" in result:
                result["estimated_metrics"] = self.estimate_engagement(result["engagement_prediction"], top_tweets)
            
            return result
        except Exception:
            # Fallback if JSON parsing fails
            try:
                # Try to extract JSON using regex
                json_pattern = r'{.*}'
                match = re.search(json_pattern, response.content, re.DOTALL)
                
                if match:
                    result = json.loads(match.group(0))
                    
                    # Add estimated engagement
                    if "engagement_prediction" in result:
                        result["estimated_metrics"] = self.estimate_engagement(result["engagement_prediction"], top_tweets)
                    
                    return result
            except:
                pass
            
            # Last resort fallback
            return {
                "post": response.content.strip(),
                "hashtags": [],
                "best_time": "8-10 AM or 6-8 PM local time",
                "viral_elements": ["authenticity", "relevance"],
                "engagement_prediction": "medium",
                "estimated_metrics": self.estimate_engagement("medium", top_tweets)
            }
    
    def estimate_engagement(self, engagement_level: str, sample_tweets: list) -> dict:
        """Estimate engagement metrics based on sample tweets."""
        if not sample_tweets:
            return {
                "likes": "100-300",
                "retweets": "10-50",
                "views": "1K-3K"
            }
        
        # Extract engagement metrics
        likes = [tweet.get("likes", 0) for tweet in sample_tweets if tweet.get("likes", 0) > 0]
        retweets = [tweet.get("retweets", 0) for tweet in sample_tweets if tweet.get("retweets", 0) > 0]
        views = [tweet.get("views", 0) for tweet in sample_tweets if tweet.get("views", 0) > 0]
        
        # Calculate averages and max values
        avg_likes = sum(likes) / len(likes) if likes else 200
        max_likes = max(likes) if likes else 500
        
        avg_retweets = sum(retweets) / len(retweets) if retweets else 30
        max_retweets = max(retweets) if retweets else 100
        
        avg_views = sum(views) / len(views) if views else 2000
        max_views = max(views) if views else 5000
        
        # Estimate based on engagement level
        if engagement_level.lower() == "high":
            likes_lower = int(max_likes * 0.7)
            likes_upper = int(max_likes * 1.3)
            
            retweets_lower = int(max_retweets * 0.7)
            retweets_upper = int(max_retweets * 1.3)
            
            views_lower = int(max_views * 0.7)
            views_upper = int(max_views * 1.3)
        elif engagement_level.lower() == "medium":
            likes_lower = int(avg_likes * 0.7)
            likes_upper = int(avg_likes * 1.2)
            
            retweets_lower = int(avg_retweets * 0.7)
            retweets_upper = int(avg_retweets * 1.2)
            
            views_lower = int(avg_views * 0.7)
            views_upper = int(avg_views * 1.2)
        else:  # low
            likes_lower = int(avg_likes * 0.3)
            likes_upper = int(avg_likes * 0.7)
            
            retweets_lower = int(avg_retweets * 0.3)
            retweets_upper = int(avg_retweets * 0.7)
            
            views_lower = int(avg_views * 0.3)
            views_upper = int(avg_views * 0.7)
        
        # Format numbers for display
        def format_number(num):
            if num >= 1000000:
                return f"{num/1000000:.1f}M"
            elif num >= 1000:
                return f"{num/1000:.1f}K"
            else:
                return str(num)
        
        return {
            "likes": f"{format_number(likes_lower)}-{format_number(likes_upper)}",
            "retweets": f"{format_number(retweets_lower)}-{format_number(retweets_upper)}",
            "views": f"{format_number(views_lower)}-{format_number(views_upper)}"
        }