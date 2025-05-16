import os
import json
import re
import logging
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from langchain_groq import ChatGroq
from config import DATA_DIR
from typing import List, Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("twitter_tool.log"), logging.StreamHandler()]
)
logger = logging.getLogger("TwitterTool")

class TwitterTool:
    def __init__(self, llm: ChatGroq, data_dir: str = DATA_DIR):
        self.llm = llm
        self.data_dir = data_dir
        
        os.makedirs(self.data_dir, exist_ok=True)
        self.user_info_dir = os.path.join(self.data_dir, "user_info")
        os.makedirs(self.user_info_dir, exist_ok=True)
        
        logger.info("TwitterTool initialized with data directory: %s", self.data_dir)
    
    def save_user_info(self, user_id: str, info: dict) -> dict:
        try:
            filename = os.path.join(self.user_info_dir, f"{user_id}_info.json")
            existing_info = {}
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    existing_info = json.load(f)
            
            merged_info = {**existing_info, **info}
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
    
    async def scrape_with_playwright(self, username: str, max_results: int = 20) -> List[Dict]:
        logger.info("Starting Playwright async scrape for @%s", username)
        print(f"\n[DEBUG] Starting Playwright async scrape for @{username} with max {max_results} tweets")
        
        tweets = []
        sources = [
            ("X.com (primary)", "https://x.com/{username}", "xcom"),
            ("Nitter (primary)", "https://nitter.net/{username}", "nitter"),
            ("Nitter (fallback)", "https://nitter.tiekoetter.com/{username}", "nitter")
        ]
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Referer': 'https://www.google.com/'
                }
            )
            page = await context.new_page()
            
            for source_name, base_url, source_type in sources:
                if len(tweets) >= max_results:
                    print(f"[DEBUG] Reached target of {max_results} tweets, stopping scrape")
                    break
                
                url = base_url.format(username=username)
                print(f"[DEBUG] Attempting {source_name}: {url}")
                
                retries = 2
                for attempt in range(retries + 1):
                    try:
                        response = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                        await page.wait_for_load_state('networkidle', timeout=30000)
                        await page.wait_for_timeout(8000)
                        
                        status_code = response.status if response else None
                        print(f"[DEBUG] HTTP Status Code for {source_name}: {status_code}")
                        
                        error_selectors = {
                            "nitter": '.error-panel',
                            "xcom": 'div[data-testid="error-detail"]'
                        }
                        error_elem = await page.query_selector(error_selectors[source_type])
                        if error_elem:
                            error_text = await error_elem.text_content()
                            logger.error(f"Error on {source_name}: {error_text}")
                            print(f"[DEBUG] Error found on {source_name}: {error_text}")
                            break
                        
                        if source_type == "xcom":
                            title = await page.title()
                            content = await page.content()
                            if "Verifying" in title or "Challenge" in title or "Login" in title.lower() or "Sign in to X" in content:
                                logger.warning(f"Verification challenge or login prompt detected on {source_name}")
                                print(f"[DEBUG] Verification challenge or login prompt detected on {source_name}: {title}")
                                break
                        
                        if source_type == "nitter":
                            tweet_selector = '.timeline-item'
                            alt_tweet_selector = '[class*="tweet"]'
                            content_selector = '.tweet-content'
                            stats_selector = '.tweet-stats'
                            date_selector = '.tweet-date'
                            link_selector = f'a[href*="/{username}/status/"]'
                        else:
                            tweet_selector = 'article[data-testid="tweet"]'
                            alt_tweet_selector = 'div[data-testid="tweetText"]'
                            content_selector = 'div[data-testid="tweetText"]'
                            stats_selector = 'div[data-testid="like"], div[data-testid="retweet"], div[data-testid="reply"]'
                            date_selector = 'time'
                            link_selector = f'a[href*="/{username}/status/"]'
                        
                        try:
                            await page.wait_for_selector(tweet_selector, timeout=15000)
                        except PlaywrightTimeoutError:
                            print(f"[DEBUG] No timeline items found on {source_name}, trying alternative selectors")
                            try:
                                await page.wait_for_selector(alt_tweet_selector, timeout=5000)
                            except PlaywrightTimeoutError:
                                page_content = await page.content()
                                print(f"[DEBUG] No tweets found on {source_name}. Page content sample:")
                                print(page_content[:500])
                                logger.warning(f"No tweets found for @%s on {source_name}", username)
                                break
                        
                        scroll_attempts = 10
                        for i in range(scroll_attempts):
                            if len(tweets) >= max_results:
                                break
                            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                            await page.wait_for_timeout(3000)
                            print(f"[DEBUG] Scroll attempt {i+1}/{scroll_attempts} on {source_name}")
                        
                        tweet_elements = await page.query_selector_all(tweet_selector)
                        print(f"[DEBUG] Found {len(tweet_elements)} tweet elements on {source_name}")
                        
                        for i, element in enumerate(tweet_elements):
                            if len(tweets) >= max_results:
                                break
                            try:
                                text_elem = await element.query_selector(content_selector)
                                if not text_elem:
                                    continue
                                text = (await text_elem.text_content()).strip()
                                text = re.sub(r'\s+', ' ', text)
                                if len(text) < 10:
                                    continue
                                
                                stats = {'likes': 0, 'retweets': 0, 'replies': 0}
                                if source_type == "nitter":
                                    stats_elem = await element.query_selector(stats_selector)
                                    if stats_elem:
                                        stat_spans = await stats_elem.query_selector_all('span.tweet-stat')
                                        for span in stat_spans:
                                            span_text = await span.text_content()
                                            num_match = re.search(r'(\d+)', span_text)
                                            if num_match:
                                                num = int(num_match.group(1))
                                                if '♥' in span_text or 'like' in span_text.lower():
                                                    stats['likes'] = num
                                                elif '🔁' in span_text or 'retweet' in span_text.lower():
                                                    stats['retweets'] = num
                                                elif 'reply' in span_text.lower() or 'comment' in span_text.lower():
                                                    stats['replies'] = num
                                else:
                                    for stat_type in ['like', 'retweet', 'reply']:
                                        stat_elem = await element.query_selector(f'div[data-testid="{stat_type}"]')
                                        if stat_elem:
                                            stat_text = await stat_elem.text_content()
                                            num_match = re.search(r'(\d+)', stat_text.strip())
                                            stats[stat_type + 's'] = int(num_match.group(1)) if num_match else 0
                                
                                date_elem = await element.query_selector(date_selector)
                                date = (await date_elem.get_attribute('datetime')) if date_elem else datetime.now().isoformat()
                                
                                tweet_id = None
                                link_elem = await element.query_selector(link_selector)
                                if link_elem:
                                    href = await link_elem.get_attribute('href')
                                    id_match = re.search(r'/status/(\d+)', href)
                                    if id_match:
                                        tweet_id = id_match.group(1)
                                
                                tweet = {
                                    "id": tweet_id or f"{source_type}_{i}",
                                    "text": text[:280],
                                    "likes": stats['likes'],
                                    "retweets": stats['retweets'],
                                    "replies": stats['replies'],
                                    "views": (stats['likes'] + stats['retweets']) * 10,
                                    "date": date,
                                    "user": username,
                                    "engagement_score": stats['likes'] + (stats['retweets'] * 2) + (stats['replies'] * 0.5)
                                }
                                
                                tweets.append(tweet)
                                print(f"[DEBUG] Scraped tweet #{len(tweets)} from {source_name}: {text[:50]}...")
                                print(f"  Stats: {stats['likes']} likes, {stats['retweets']} retweets, {stats['replies']} replies")
                                
                            except Exception as e:
                                print(f"[DEBUG] Error extracting tweet {i} from {source_name}: {str(e)}")
                                continue
                        
                        print(f"[DEBUG] Collected {len(tweets)}/{max_results} tweets from {source_name}")
                        break
                    
                    except PlaywrightError as e:
                        logger.error(f"Playwright error during scraping from {source_name} (attempt {attempt+1}/{retries+1}): {str(e)}")
                        print(f"[DEBUG] Playwright error during scraping from {source_name} (attempt {attempt+1}/{retries+1}): {str(e)}")
                        if attempt == retries:
                            continue
                        await page.wait_for_timeout(2000)
                    except Exception as e:
                        logger.error(f"Unexpected error during scraping from {source_name} (attempt {attempt+1}/{retries+1}): {str(e)}")
                        print(f"[DEBUG] Unexpected error during scrolling from {source_name} (attempt {attempt+1}/{retries+1}): {str(e)}")
                        if attempt == retries:
                            continue
                        await page.wait_for_timeout(2000)
            
            await browser.close()
        
        if not tweets:
            print(f"[DEBUG] No tweets found for @{username} across all sources")
        elif len(tweets) < max_results:
            print(f"[DEBUG] Collected only {len(tweets)}/{max_results} tweets for @{username} across all sources")
        else:
            print(f"[DEBUG] Successfully collected {len(tweets)}/{max_results} tweets for @{username}")
        return tweets
    
    async def scrape_profile(self, username: str, max_tweets: int = 20) -> dict:
        try:
            logger.info("Starting profile scrape for %s", username)
            print(f"\n[DEBUG] =================")
            print(f"[DEBUG] STARTING PROFILE SCRAPE FOR @{username}")
            print(f"[DEBUG] Max tweets requested: {max_tweets}")
            print(f"[DEBUG] =================\n")
            
            tweets = await self.scrape_with_playwright(username, max_tweets)
            print(f"\n[DEBUG] Total tweets scraped: {len(tweets)}")
            
            if not tweets:
                logger.warning("No tweets found for @%s", username)
                print(f"[DEBUG] No tweets found")
                return {
                    "success": False,
                    "message": f"No tweets found for @{username}. The user may not exist, have no public tweets, or the sources may be unavailable.",
                    "tweet_count": 0,
                    "top_tweets_count": 0,
                    "performance_analysis": {},
                    "sample_tweets": [],
                    "tweets": []
                }
            
            print(f"\n[DEBUG] First 3 tweets:")
            for i, tweet in enumerate(tweets[:3]):
                print(f"[DEBUG] Tweet {i+1}:")
                print(f"  - Text: {tweet.get('text', '')[:100]}...")
                print(f"  - Engagement score: {tweet.get('engagement_score', 0)}")
                print(f"  - Likes: {tweet.get('likes', 0)}, Retweets: {tweet.get('retweets', 0)}")
            
            unique_tweets = self._deduplicate_tweets(tweets)
            print(f"\n[DEBUG] After deduplication: {len(unique_tweets)} tweets")
            
            unique_tweets.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)
            top_tweets = unique_tweets[:30]
            
            print(f"[DEBUG] Selected top {len(top_tweets)} tweets by engagement")
            print(f"[DEBUG] Top tweet engagement score: {top_tweets[0].get('engagement_score', 0) if top_tweets else 0}")
            
            self.save_data(username, top_tweets, "tweets")
            
            print(f"\n[DEBUG] Analyzing tweets...")
            analysis = self.analyze_tweets(username, top_tweets)
            
            logger.info("Successfully scraped profile for @%s", username)
            print(f"\n[DEBUG] PROFILE SCRAPE COMPLETE for @{username}")
            print(f"[DEBUG] =================\n")
            
            return {
                "success": True,
                "message": f"Successfully scraped profile for @{username}",
                "tweet_count": len(unique_tweets),
                "top_tweets_count": len(top_tweets),
                "performance_analysis": analysis,
                "sample_tweets": top_tweets[:5],
                "tweets": top_tweets[:10]
            }
            
        except Exception as e:
            logger.error("Error scraping profile: %s", str(e))
            print(f"[DEBUG] ERROR in scrape_profile: {str(e)}")
            return {
                "success": False,
                "message": f"Error scraping profile: {str(e)}",
                "tweet_count": 0,
                "top_tweets_count": 0,
                "performance_analysis": {},
                "sample_tweets": [],
                "tweets": []
            }
    
    def _deduplicate_tweets(self, tweets: list) -> list:
        unique_tweets = []
        seen_texts = set()
        
        for tweet in tweets:
            text = tweet.get("text", "").strip().lower()
            if text and text not in seen_texts:
                seen_texts.add(text)
                unique_tweets.append(tweet)
        
        logger.info("Deduplicated %d tweets to %d unique tweets", len(tweets), len(unique_tweets))
        return unique_tweets
    
    def analyze_tweets(self, username: str, tweets: list) -> dict:
        if not tweets:
            logger.warning("No tweets available for analysis for %s", username)
            return {"success": False, "message": "No tweets available for analysis"}
        
        try:
            logger.info("Analyzing %d tweets for @%s", len(tweets), username)
            
            tweets_by_engagement = sorted(tweets, key=lambda x: x.get("engagement_score", 0), reverse=True)
            top_tweets = tweets_by_engagement[:min(10, len(tweets_by_engagement))]
            
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
            
            analysis_response = self.llm.invoke(prompt)
            
            try:
                analysis_result = self.parse_json_from_response(analysis_response.content)
                
                if not analysis_result or not isinstance(analysis_result, dict):
                    raise ValueError("Invalid analysis result format")
                    
                analysis_result["success"] = True
                
                for field in ["content_patterns", "style_elements", "optimal_format", "recommendations"]:
                    if field not in analysis_result:
                        analysis_result[field] = [] if field != "optimal_format" else "Not provided by analysis"
                
                self.save_data(username, analysis_result, "analysis")
                logger.info("Analysis completed successfully for @%s", username)
                
                return analysis_result
                    
            except Exception as e:
                logger.error("Analysis parsing error: %s", str(e))
                fallback_analysis = {
                    "success": True,
                    "content_patterns": [
                        "Sharing unique insights and perspectives",
                        "Addressing common pain points",
                        "Using concise, impactful language"
                    ],
                    "style_elements": [
                        "Direct and authentic voice",
                        "Clear and concise messaging",
                        "Strategic use of punctuation"
                    ],
                    "optimal_format": "Short, clear statements with substance or relatable observations",
                    "recommendations": [
                        "Share unique insights and perspectives",
                        "Keep tweets concise and focused",
                        "Include specific details when relevant",
                        "Address common pain points or interests"
                    ]
                }
                
                self.save_data(username, fallback_analysis, "analysis")
                return fallback_analysis
                
        except Exception as e:
            logger.error("Error in tweet analysis: %s", str(e))
            return {
                "success": False,
                "message": f"Error analyzing tweets: {str(e)}"
            }

    def generate_post(self, username: str, topic: str, length: str = "Medium", user_id: str = None) -> dict:
        try:
            logger.info("Generating post for @%s on topic '%s' with length '%s'", username, topic, length)

            tweets = self.load_data(username, "tweets") or []
            analysis = self.load_data(username, "analysis") or {
                "content_patterns": ["Sharing bold insights", "Provoking thought", "Relatable content"],
                "style_elements": ["Direct", "Bold", "Engaging"],
                "optimal_format": "Short, impactful statements with a strong hook",
                "recommendations": ["Use provocative questions", "Add emotional appeal", "Include actionable challenges"]
            }

            user_info = self.get_user_info(user_id).get("user_info", {}) if user_id else {}
            user_location = user_info.get("location", "unknown")
            user_profession = user_info.get("profession", "unknown")

            tweets.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)

            # Length-specific instructions
            length_guidelines = {
                "Short": {
                    "description": "15-25 words",
                    "instruction": "Write a short, punchy tweet. Use a bold statement or provocative question, add emotional appeal, and end with a call to action."
                },
                "Medium": {
                    "description": "40-70 words",
                    "instruction": "Write a single tweet with a bold insight, a relatable element, and a challenge or question."
                },
                "Long": {
                    "description": "3-5 tweet thread (~200-280 words total)",
                    "instruction": """Create a Twitter thread with 3-5 tweets:
1/ Start with a provocative hook.
2/ Add a personal/relatable insight.
3/ Provide a surprising fact or context.
4/ Deliver actionable advice or an opinion.
5/ End with a bold takeaway or challenge."""
                }
            }
            guidelines = length_guidelines.get(length, length_guidelines["Medium"])

            # Detect user tone from top tweets
            tone = "bold"
            if tweets:
                sample_texts = [tweet.get("text", "") for tweet in tweets[:5]]
                tone_prompt = f"""
Analyze the tone of these tweets by @{username}:
{json.dumps(sample_texts, indent=2)}
Return ONLY one word (e.g., humorous, serious, bold, inspirational).
"""
                tone = self.llm.invoke(tone_prompt).content.strip().lower() or "bold"

            # Trending context + hashtags
            trending_context = self.llm.invoke(
                f"Topic: {topic}. Date: May 15, 2025. Provide 1-2 sentence trending context."
            ).content.strip()

            hashtags_response = self.llm.invoke(
                f"Topic: {topic}. Date: May 15, 2025. Return JSON list of 1-3 trending hashtags in SNAKE_CASE."
            ).content.strip()

            try:
                hashtags = json.loads(hashtags_response)
                if not isinstance(hashtags, list):
                    hashtags = []
            except Exception:
                hashtags = []

            prompt = f"""
Generate a {length.lower()} Twitter {"thread" if length == "Long" else "post"} for @{username} on topic: {topic}.

Instructions:
- {guidelines['instruction']}
- Emphasize a {tone} tone.
- Use trending context: {trending_context}
- Add 1-3 relevant hashtags: {json.dumps(hashtags)}
- Include a challenge, poll, or question at the end.
- If a thread, format like ["1/5 ...", "2/5 ...", ..., "5/5 ..."]

User info:
- Location: {user_location}
- Profession: {user_profession}
{json.dumps(user_info, indent=2)}

Top tweets:
{json.dumps(tweets[:5], indent=2)}

Analysis:
{json.dumps(analysis, indent=2)}

Return ONLY this JSON format:
{{
  "post": <string OR array of tweets>,
  "hashtags": <array>,
  "best_time": <string>,
  "viral_elements": <array>,
  "engagement_prediction": <string>
}}
"""
            logger.info("Sending prompt to LLM")
            llm_response = self.llm.invoke(prompt)
            result = self.parse_json_from_response(llm_response.content)

            if isinstance(result, list) and len(result) == 1:
                result = result[0]

            # Fill missing fields with defaults
            result = result or {}
            result.setdefault("post", "Could not generate post.")
            result.setdefault("hashtags", hashtags or [self._format_hashtag(topic.lower().replace(" ", "_"))])
            result.setdefault("best_time", self._get_best_time(user_location, length))
            result.setdefault("viral_elements", ["emotional appeal", "provocative question", "challenge"])
            result.setdefault("engagement_prediction", "high")

            # Format hashtags
            result["hashtags"] = [self._format_hashtag(tag) for tag in result["hashtags"] if tag]

            # Clean and estimate
            result["post"] = self._clean_post_text(result["post"])
            result["estimated_metrics"] = self.estimate_engagement(result["engagement_prediction"], tweets)
            result["success"] = True

            return result

        except Exception as e:
            logger.exception("Post generation failed: %s", str(e))
            return {"success": False, "error": str(e)}
    
    def _get_best_time(self, location: str, length: str) -> str:
        if "india" in location.lower() or "bengaluru" in location.lower():
            return "Post at 9 AM IST or 6 PM IST" if length != "Long" else "Post at 9 AM IST, follow-ups every 2-3 minutes"
        elif "us" in location.lower() or "america" in location.lower():
            return "Post at 8 AM PST or 5 PM PST" if length != "Long" else "Post at 8 AM PST, follow-ups every 2-3 minutes"
        else:
            return "Post at 8-10 AM or 6-8 PM local time" if length != "Long" else "Post at 8 AM local time, follow-ups every 2-3 minutes"
    
    def _clean_post_text(self, text: str) -> str:
        if not text:
            return ""
        
        if isinstance(text, list):
            return [self._clean_post_text(item) for item in text]
        
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'[*_`#]', '', text)
        text = re.sub(r'\\"', '"', text)
        text = ' '.join(text.split())
        return text.strip()
    
    def _format_hashtag(self, tag: str) -> str:
        if not tag:
            return ""
        
        tag = re.sub(r'[#\s]', '', tag)
        return tag.lower()
    
    def estimate_engagement(self, engagement_level: str, tweets: list) -> dict:
        try:
            if not tweets:
                return {"likes": "100-300", "retweets": "10-50", "views": "1K-3K"}
            
            likes = [tweet.get("likes", 0) or 0 for tweet in tweets]
            retweets = [tweet.get("retweets", 0) or 0 for tweet in tweets]
            views = [tweet.get("views", 0) or 0 for tweet in tweets]
            
            likes = [like for like in likes if like > 0] or [200]
            retweets = [rt for rt in retweets if rt > 0] or [30]
            views = [view for view in views if view > 0] or [2000]
            
            avg_likes = sum(likes) / len(likes)
            avg_retweets = sum(retweets) / len(retweets)
            avg_views = sum(views) / len(views)
            
            multiplier = 1.5 if engagement_level.lower() == "high" else (0.5 if engagement_level.lower() == "low" else 1.0)
            
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
        try:
            filename = os.path.join(self.data_dir, f"{username}_{data_type}.json")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logger.info("Saved %s data for %s", data_type, username)
        except Exception as e:
            logger.error("Error saving %s data for %s: %s", data_type, username, str(e))
    
    def load_data(self, username: str, data_type: str) -> dict or list:
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
        try:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
                
            code_block_match = re.search(r'```(?:json)?\n([\s\S]*?)\n```', text)
            if code_block_match:
                return json.loads(code_block_match.group(1))
                
            json_pattern = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text, re.DOTALL)
            if json_pattern:
                return json.loads(json_pattern.group(1))
                
            logger.warning("No valid JSON found in response")
            return {"post": "JSON parsing error", "hashtags": []}
                
        except Exception as e:
            logger.error("JSON parsing error: %s", str(e))
            return {"error": f"JSON parsing error: {str(e)}"}