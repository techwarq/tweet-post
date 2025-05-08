# app.py
import streamlit as st
import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API URL - change this in production
API_URL = "http://localhost:8000"

# App title and description
st.title("Personal Twitter Post Generator")
st.markdown("Generate viral Twitter posts based on your information and favorite accounts")

# Custom CSS for better tweet display
st.markdown("""
<style>
.tweet-part {
    border-left: 4px solid #1DA1F2;
    padding-left: 12px;
    margin-bottom: 16px;
}
.long-tweet {
    background-color: #f5f8fa;
    padding: 16px;
    border-radius: 8px;
    margin-bottom: 16px;
}
.thread-container {
    background-color: #f5f8fa;
    padding: 16px;
    border-radius: 8px;
    margin-bottom: 16px;
}
.thread-part {
    border-left: 4px solid #1DA1F2;
    padding: 12px;
    margin-bottom: 12px;
    background-color: white;
    border-radius: 4px;
}
.user-info-section {
    background-color: #000000;
    padding: 16px;
    border-radius: 8px;
    margin-bottom: 16px;
}
</style>
""", unsafe_allow_html=True)

# Set up the sidebar
with st.sidebar:
    st.header("About")
    st.markdown(
        """
        This tool creates personalized viral tweets by combining:
        
        1. Your personal information
        2. Analysis of successful Twitter/X accounts
        3. Viral tweet patterns
        
        The more you tell us about yourself, the more personalized your tweets will be!
        """
    )
    
    st.header("Length Options")
    st.markdown("""
    - **Short**: Under 15 words
    - **Medium**: 15-40 words
    - **Long**: 40-280 words (full thread)
    """)
    
    st.header("Credits")
    st.markdown("Built with Tavily, Groq, and FastAPI")

def format_long_tweet(post_text):
    """Format long tweets or threads for better display."""
    if not post_text:
        return ""
    
    # Check if this is potentially a thread (contains multiple paragraphs)
    paragraphs = [p for p in post_text.split('\n\n') if p.strip()]
    
    # For threads with clear parts
    if len(paragraphs) > 1:
        formatted_parts = []
        for i, part in enumerate(paragraphs):
            formatted_parts.append(f"""
            <div class="thread-part">
                <strong>Part {i+1}/{len(paragraphs)}</strong>
                <p>{part}</p>
            </div>
            """)
        
        return f"""
        <div class="thread-container">
            <h4>Tweet Thread:</h4>
            {''.join(formatted_parts)}
        </div>
        """
    
    # For single long tweets that aren't threads
    return f"""
    <div class="long-tweet">
        <h4>Long Tweet:</h4>
        <p>{post_text}</p>
    </div>
    """

# Initialize session state for user info if it doesn't exist
if "user_info" not in st.session_state:
    st.session_state["user_info"] = {}

# Main app layout with three tabs
tab1, tab2, tab3 = st.tabs(["Your Info", "Scrape Profile", "Generate Posts"])

# Tab 1: User Information
with tab1:
    st.header("Your Personal Information")
    st.markdown("Add details about yourself to personalize your tweets. This information will be used to generate more authentic content.")
    
    # User ID for storage
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = "default_user"  # You can implement actual user authentication
    
    # Personal info form
    with st.form("personal_info_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Name", value=st.session_state["user_info"].get("name", ""))
            profession = st.text_input("Profession/Industry", value=st.session_state["user_info"].get("profession", ""))
            interests = st.text_area("Interests (comma separated)", value=st.session_state["user_info"].get("interests", ""))
        
        with col2:
            expertise = st.text_area("Areas of Expertise", value=st.session_state["user_info"].get("expertise", ""))
            style = st.selectbox("Your Preferred Style", 
                                ["Professional", "Casual", "Humorous", "Technical", "Inspirational"],
                                index=["Professional", "Casual", "Humorous", "Technical", "Inspirational"].index(
                                    st.session_state["user_info"].get("style", "Professional")))
        
        # Additional information in an expander
        with st.expander("Additional Information"):
            education = st.text_input("Education", value=st.session_state["user_info"].get("education", ""))
            location = st.text_input("Location", value=st.session_state["user_info"].get("location", ""))
            achievements = st.text_area("Key Achievements", value=st.session_state["user_info"].get("achievements", ""))
            audience = st.text_input("Target Audience", value=st.session_state["user_info"].get("audience", ""))
            topics_to_avoid = st.text_area("Topics to Avoid", value=st.session_state["user_info"].get("topics_to_avoid", ""))
        
        submitted = st.form_submit_button("Save Your Information")
        
    if submitted:
        # Collect all the form data
        user_info = {
            "name": name,
            "profession": profession,
            "interests": [interest.strip() for interest in interests.split(",") if interest.strip()],
            "expertise": expertise,
            "style": style,
            "education": education,
            "location": location,
            "achievements": achievements,
            "audience": audience,
            "topics_to_avoid": topics_to_avoid
        }
        
        # Save to session state
        st.session_state["user_info"] = user_info
        
        # Call API to save user info
        try:
            response = requests.post(
                f"{API_URL}/save-user-info/{st.session_state['user_id']}",
                json={"user_info": user_info}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    st.success("Your information has been saved and will be used to personalize your tweets!")
                else:
                    st.error(result.get("message", "Unknown error occurred"))
            else:
                st.error(f"Error: {response.text}")
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {str(e)}")
            st.info("Your information has been saved locally but couldn't be saved to the server.")
    
    # Display current info if available
    if st.session_state["user_info"]:
        st.subheader("Current Saved Information")
        
        # Format interests as string for display
        info_for_display = st.session_state["user_info"].copy()
        if isinstance(info_for_display.get("interests"), list):
            info_for_display["interests"] = ", ".join(info_for_display["interests"])
            
        # Display the info in a nice format
        with st.container():
            st.markdown("""
            <div class="user-info-section">
                <h4>Saved Profile Information</h4>
                <p>This information will be used to personalize your tweets.</p>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Name:** {info_for_display.get('name', '')}")
                st.markdown(f"**Profession:** {info_for_display.get('profession', '')}")
                st.markdown(f"**Interests:** {info_for_display.get('interests', '')}")
                st.markdown(f"**Style:** {info_for_display.get('style', '')}")
            
            with col2:
                st.markdown(f"**Expertise:** {info_for_display.get('expertise', '')}")
                if info_for_display.get('location'):
                    st.markdown(f"**Location:** {info_for_display.get('location', '')}")
                if info_for_display.get('education'):
                    st.markdown(f"**Education:** {info_for_display.get('education', '')}")
        
        st.markdown("---")
        st.info("Go to the 'Generate Posts' tab to create personalized tweets!")

# Tab 2: Scrape Profile
with tab2:
    st.header("Scrape Twitter Profile")
    st.markdown("Analyze successful Twitter accounts to learn from their style. These accounts will serve as inspiration for your tweets.")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        username = st.text_input("Enter Twitter Username (without @)", key="scrape_username")
    
    with col2:
        scrape_button = st.button("Scrape Profile")
    
    if scrape_button and username:
        with st.spinner(f"Scraping @{username}'s profile..."):
            # Call the API to scrape the profile
            response = requests.post(
                f"{API_URL}/scrape-profile",
                json={"username": username}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    st.success(result["message"])
                    # Store username in session state
                    st.session_state["username"] = username
                    st.session_state["scraped_data"] = result
                    
                    # Display performance analysis if available
                    analysis = result.get("performance_analysis", {})
                    if analysis and isinstance(analysis, dict):
                        st.subheader("Tweet Performance Analysis")
                        
                        # Display content patterns
                        if "content_patterns" in analysis and isinstance(analysis["content_patterns"], list):
                            st.markdown("**Content Patterns:**")
                            for pattern in analysis["content_patterns"]:
                                st.markdown(f"- {pattern}")
                        
                        # Display style elements
                        if "style_elements" in analysis and isinstance(analysis["style_elements"], list):
                            st.markdown("**Style Elements:**")
                            for element in analysis["style_elements"]:
                                st.markdown(f"- {element}")
                        
                        # Display optimal format
                        if "optimal_format" in analysis:
                            st.markdown(f"**Optimal Format:** {analysis['optimal_format']}")
                        
                        # Display recommendations
                        if "recommendations" in analysis and isinstance(analysis["recommendations"], list):
                            st.markdown("**Recommendations for Virality:**")
                            for rec in analysis["recommendations"]:
                                st.markdown(f"- {rec}")
                    
                    # Display tweet preview if available
                    tweets = result.get("tweets", [])
                    if tweets and isinstance(tweets, list):
                        st.subheader("Top Tweets Preview")
                        for i, tweet in enumerate(tweets[:3]):
                            with st.expander(f"Tweet {i+1} - {tweet.get('engagement_score', 0)} engagement"):
                                tweet_text = tweet.get("text", "")
                                if len(tweet_text.split()) > 40:  # Long tweet
                                    st.markdown(format_long_tweet(tweet_text), unsafe_allow_html=True)
                                else:
                                    st.markdown(tweet_text)
                                
                                metrics_text = []
                                if "likes" in tweet and tweet["likes"] > 0:
                                    metrics_text.append(f"👍 {tweet['likes']}")
                                if "retweets" in tweet and tweet["retweets"] > 0:
                                    metrics_text.append(f"🔁 {tweet['retweets']}")
                                if "views" in tweet and tweet["views"] > 0:
                                    metrics_text.append(f"👀 {tweet['views']}")
                                
                                if metrics_text:
                                    st.markdown(" | ".join(metrics_text))
                    
                    st.markdown("**Go to the 'Generate Posts' tab to create tweets!**")
                else:
                    st.error(result.get("message", "Unknown error occurred"))
            else:
                st.error(f"Error: {response.text}")

# Tab 3: Generate Posts
with tab3:
    st.header("Generate Personalized Twitter Posts")
    
    # Check if we have user info
    has_user_info = bool(st.session_state.get("user_info"))
    
    # Check if we have a scraped profile
    if "username" not in st.session_state:
        st.session_state["username"] = ""
    
    # Display user info status
    if has_user_info:
        st.success("✅ Personal information will be used to customize your tweets")
    else:
        st.warning("No personal information found. Add your details in the 'Your Info' tab for personalized tweets.")
    
    # Username input
    username = st.text_input("Twitter Account for Style Reference", value=st.session_state["username"], 
                             help="Enter a Twitter account to use as style inspiration", key="generate_username")
    
    if not username:
        st.info("Enter a Twitter username to use as style inspiration, or scrape a profile in the 'Scrape Profile' tab.")
    
    # Create columns for the form
    col1, col2 = st.columns(2)
    
    with col1:
        # Topic input
        topic = st.text_input("Topic", value="Technology", 
                            help="Enter a topic for your tweet (e.g., AI, Technology, Politics)")
        
    with col2:
        # Length selection with improved descriptions
        length_options = ["Short", "Medium", "Long"]
        length_descriptions = {
            "Short": "Under 15 words - Quick one-liners",
            "Medium": "15-40 words - Standard tweets",
            "Long": "40-280 words - Extended posts or threads"
        }
        selected_length = st.selectbox(
            "Length", 
            options=length_options,
            format_func=lambda x: length_descriptions[x],
            help="Select the desired length for your generated post"
        )
    
    # Advanced options
    with st.expander("Advanced Options"):
        style = st.selectbox(
            "Override Style", 
            ["Use My Personal Style", "Professional", "Casual", "Humorous", "Technical", "Inspirational"],
            help="Select a specific style or use your personal style from profile"
        )
        
        include_hashtags = st.checkbox("Include Hashtags", value=True)
        include_cta = st.checkbox("Include Call-to-Action", value=False)
        
        # Debug information - toggle to see request details
        if st.checkbox("Show Debug Info", value=False):
            st.info(f"Length parameter being sent: '{selected_length}'")
            if has_user_info:
                st.json(st.session_state["user_info"])
    
    # Generate button
    generate_button = st.button("Generate Post")
    if generate_button:
        # Validate inputs
        if not username and not has_user_info:
            st.error("Please either enter a Twitter username or add your personal information first.")
        else:
            with st.spinner(f"Generating {selected_length.lower()} post on {topic}..."):
                # Prepare request data
                request_data = {
                    "topic": topic,
                    "length": selected_length,
                    "include_hashtags": include_hashtags,
                    "include_cta": include_cta,
                    "user_id": st.session_state.get("user_id") if has_user_info else None
                }
                
                if style != "Use My Personal Style":
                    request_data["style"] = style
                
                # Log the request data for debugging
                print(f"Sending request data: {json.dumps(request_data)}")
                
                # Call the API to generate a post
                try:
                    response = requests.post(
                        f"{API_URL}/generate-post/{username}",
                        json=request_data,
                        timeout=120  # Increased timeout for long posts
                    )
                    
                    if response.status_code == 200:
                        post_data = response.json()
                        
                        # Display the raw response for debugging if enabled
                        if st.session_state.get("debug_mode"):
                            st.json(post_data)
                        
                        # Display area
                        st.subheader("Generated Post")
                        
                        # Get the post text with fallback
                        post_text = post_data.get("post", "")
                        if not post_text and "error" in post_data:
                            st.error(f"Error in post generation: {post_data['error']}")
                            st.stop()
                        
                        # Display the post with appropriate formatting based on length
                        if selected_length == "Long":
                            # For longer tweets or threads, use the formatting function
                            st.markdown(format_long_tweet(post_text), unsafe_allow_html=True)
                        else:
                            st.markdown(f"**{selected_length} Tweet:**")
                            st.markdown(f"<div class='tweet-part'>{post_text}</div>", unsafe_allow_html=True)
                        
                        # Create columns for metadata
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Display hashtags if available
                            if post_data.get("hashtags") and isinstance(post_data["hashtags"], list):
                                hashtags = [tag for tag in post_data["hashtags"] if tag]
                                if hashtags:
                                    st.markdown("**Suggested Hashtags:**")
                                    st.markdown(" ".join([f"#{tag}" for tag in hashtags]))
                            
                            # Display best time to post
                            if "best_time" in post_data:
                                st.markdown(f"**Best Posting Time:** {post_data['best_time']}")
                        
                        with col2:
                            # Display engagement prediction
                            if "engagement_prediction" in post_data:
                                engagement = post_data['engagement_prediction'].upper()
                                st.markdown(f"**Engagement Prediction:** {engagement}")
                            
                            # Display estimated metrics if available
                            estimated_metrics = post_data.get("estimated_metrics", {})
                            if estimated_metrics and isinstance(estimated_metrics, dict):
                                st.markdown("**Estimated Engagement:**")
                                if "likes" in estimated_metrics:
                                    st.markdown(f"- Likes: {estimated_metrics['likes']}")
                                if "retweets" in estimated_metrics:
                                    st.markdown(f"- Retweets: {estimated_metrics['retweets']}")
                                if "views" in estimated_metrics:
                                    st.markdown(f"- Views: {estimated_metrics['views']}")
                        
                        # Full post for copying
                        st.subheader("Copy Ready Version")
                        full_post = post_text
                        if post_data.get("hashtags") and isinstance(post_data["hashtags"], list):
                            hashtags = [tag for tag in post_data["hashtags"] if tag]
                            if hashtags:
                                hashtag_text = " ".join([f"#{tag}" for tag in hashtags])
                                full_post += f"\n\n{hashtag_text}"
                        
                        st.text_area("Copy Post", value=full_post, height=150)
                        
                        # Add a regenerate button
                        if st.button("Regenerate Post"):
                            st.experimental_rerun()
                    
                    elif response.status_code == 404:
                        st.error("No data found for this Twitter account. Please scrape the profile first in the 'Scrape Profile' tab.")
                    else:
                        st.error(f"Error generating post: {response.text}")
                except requests.exceptions.RequestException as e:
                    st.error(f"Connection error: {str(e)}")
        
# Add a debug toggle in the sidebar
with st.sidebar:
    st.header("Developer Options")
    debug_mode = st.checkbox("Enable Debug Mode", value=False)
    if debug_mode:
        st.session_state["debug_mode"] = True
    else:
        st.session_state["debug_mode"] = False

# Run the Streamlit app
if __name__ == "__main__":
    pass