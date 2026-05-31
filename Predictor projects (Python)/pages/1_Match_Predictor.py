import pandas as pd
import streamlit as st
from scipy.stats import poisson

# --- 1. APP CONFIGURATION & TITLE ---
st.set_page_config(page_title="PL Predictor Engine Pro", page_icon="🏆")
st.title("🏆 Premier League Match Predictor")
st.write("The ultimate league analysis dashboard blending long/short term form, clean sheet data, real-time market data, fixture congestion and derby variance.")

# --- 2. LOAD & CLEAN DATA ---
@st.cache_data
def load_data():
    url = "https://www.football-data.co.uk/mmz4281/2526/E0.csv"
    df = pd.read_csv(url, storage_options={'User-Agent': 'Mozilla/5.0'})
    
    # NEW: Include Date to calculate resting schedules
    clean_df = df[['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'B365H', 'B365D', 'B365A']].copy()
    clean_df.columns = ['Date', 'HomeTeam', 'AwayTeam', 'HomeGoals', 'AwayGoals', 'B365H', 'B365D', 'B365A']
    clean_df['Date'] = pd.to_datetime(clean_df['Date'], format='%d/%m/%Y')
    return clean_df.dropna()

clean_df = load_data()

# --- 3. CALCULATE INTEL BASELINES & MASTER STATS SHEET ---
avg_home_goals = clean_df['HomeGoals'].mean()
avg_away_goals = clean_df['AwayGoals'].mean()

# A. Calculate Season Averages
home_stats = clean_df.groupby('HomeTeam')['HomeGoals'].mean().reset_index().rename(columns={'HomeTeam': 'Team', 'HomeGoals': 'AvgGoalsScoredHome'})
home_conceded = clean_df.groupby('HomeTeam')['AwayGoals'].mean().reset_index().rename(columns={'HomeTeam': 'Team', 'AwayGoals': 'AvgGoalsConcededHome'})
away_stats = clean_df.groupby('AwayTeam')['AwayGoals'].mean().reset_index().rename(columns={'AwayTeam': 'Team', 'AwayGoals': 'AvgGoalsScoredAway'})
away_conceded = clean_df.groupby('AwayTeam')['HomeGoals'].mean().reset_index().rename(columns={'AwayTeam': 'Team', 'HomeGoals': 'AvgGoalsConcededAway'})

# B. Calculate Clean Sheet Percentages
clean_df['HomeCleanSheet'] = clean_df['AwayGoals'] == 0
clean_df['AwayCleanSheet'] = clean_df['HomeGoals'] == 0
home_cs = clean_df.groupby('HomeTeam')['HomeCleanSheet'].mean().reset_index().rename(columns={'HomeTeam': 'Team', 'HomeCleanSheet': 'HomeCS_Pct'})
away_cs = clean_df.groupby('AwayTeam')['AwayCleanSheet'].mean().reset_index().rename(columns={'AwayTeam': 'Team', 'AwayCleanSheet': 'AwayCS_Pct'})

# C. Calculate Recent Form, Market Confidence, and Last Match Date
all_matches = []
for index, row in clean_df.iterrows():
    home_implied_win = 1 / row['B365H'] if row['B365H'] > 0 else 0
    all_matches.append({'Team': row['HomeTeam'], 'Date': row['Date'], 'GoalsScored': row['HomeGoals'], 'GoalsConceded': row['AwayGoals'], 'MarketWinConfidence': home_implied_win})
    away_implied_win = 1 / row['B365A'] if row['B365A'] > 0 else 0
    all_matches.append({'Team': row['AwayTeam'], 'Date': row['Date'], 'GoalsScored': row['AwayGoals'], 'GoalsConceded': row['HomeGoals'], 'MarketWinConfidence': away_implied_win})

form_df = pd.DataFrame(all_matches).sort_values(by='Date')

# Pull out the very last recorded match date for each team to find current rest status
last_match_dates = form_df.groupby('Team')['Date'].max().reset_index().rename(columns={'Date': 'LastMatchDate'})

recent_form = form_df.groupby('Team').tail(5).groupby('Team').agg({
    'GoalsScored': 'mean',
    'GoalsConceded': 'mean',
    'MarketWinConfidence': 'mean'
}).reset_index()
recent_form.columns = ['Team', 'FormGoalsScored', 'FormGoalsConceded', 'MarketConfidence']

# D. Merge everything into Master Engine DataFrame
team_stats = pd.merge(home_stats, home_conceded, on='Team')
team_stats = pd.merge(team_stats, away_stats, on='Team')
team_stats = pd.merge(team_stats, away_conceded, on='Team')
team_stats = pd.merge(team_stats, home_cs, on='Team')
team_stats = pd.merge(team_stats, away_cs, on='Team')
team_stats = pd.merge(team_stats, recent_form, on='Team')
team_stats = pd.merge(team_stats, last_match_dates, on='Team')

# --- 4. APP INTERFACE INTERACTION ---
sorted_teams = sorted(team_stats['Team'].unique())
col1, col2 = st.columns(2)

with col1:
    home_team = st.selectbox("Select Home Team", sorted_teams, index=sorted_teams.index('Arsenal') if 'Arsenal' in sorted_teams else 0)
with col2:
    away_team = st.selectbox("Select Away Team", sorted_teams, index=sorted_teams.index('Chelsea') if 'Chelsea' in sorted_teams else 1)

# --- 5. THE MULTI-LAYERED SIMULATION ENGINE ---
if st.button("Simulate Match Outcome", type="primary"):
    if home_team == away_team:
        st.error("A team cannot play against itself! Please select two different teams.")
    else:
        home_profile = team_stats[team_stats['Team'] == home_team].iloc[0]
        away_profile = team_stats[team_stats['Team'] == away_team].iloc[0]
        
        # --- FEATURE ENGINEERING LAYER A: FATIGUE TAX (REST DAYS) ---
        # We calculate the mock gap between games based on their last recorded season outings
        home_rest = (clean_df['Date'].max() - home_profile['LastMatchDate']).days
        away_rest = (clean_df['Date'].max() - away_profile['LastMatchDate']).days
        
        # Default modifiers
        home_fatigue_mod = 1.0
        away_fatigue_mod = 1.0
        
        # If a team has under 4 days of rest, hit their performance with a 8% efficiency penalty
        if home_rest < 4: home_fatigue_mod = 0.92
        if away_rest < 4: away_fatigue_mod = 0.92

        # --- FEATURE ENGINEERING LAYER B: DERBY TRACKER ---
        derbies = [
            {'Arsenal', 'Tottenham'}, {'Liverpool', 'Everton'}, 
            {'Man City', 'Man United'}, {'Newcastle', 'Sunderland'},
            {'Arsenal', 'Chelsea'}, {'Chelsea', 'Tottenham'}
        ]
        is_derby = {home_team, away_team} in derbies
        
        # Core Expected Goals calculations
        base_home_xG = (home_profile['AvgGoalsScoredHome'] * away_profile['AvgGoalsConcededAway']) / avg_home_goals
        base_away_xG = (away_profile['AvgGoalsScoredAway'] * home_profile['AvgGoalsConcededHome']) / avg_away_goals
        form_home_xG = (home_profile['FormGoalsScored'] * away_profile['FormGoalsConceded']) / avg_home_goals
        form_away_xG = (away_profile['FormGoalsScored'] * home_profile['FormGoalsConceded']) / avg_away_goals
        
        # Apply fatigue modifiers straight to baseline expectations
        expected_home_goals = ((base_home_xG * 0.7) + (form_home_xG * 0.3)) * home_fatigue_mod
        expected_away_goals = ((base_away_xG * 0.7) + (form_away_xG * 0.3)) * away_fatigue_mod
        
        # Market Wisdom
        market_ratio = home_profile['MarketConfidence'] / (away_profile['MarketConfidence'] if away_profile['MarketConfidence'] > 0 else 1)
        if market_ratio > 1.1:
            expected_home_goals *= 1.05; expected_away_goals *= 0.95
        elif market_ratio < 0.9:
            expected_home_goals *= 0.95; expected_away_goals *= 1.05
            
        # --- POISSON PROBABILITY MATRIX ---
        home_win_prob, draw_prob, away_win_prob = 0, 0, 0
        
        for h_goals in range(7):
            for a_goals in range(7):
                p_home = poisson.pmf(h_goals, expected_home_goals)
                p_away = poisson.pmf(a_goals, expected_away_goals)
                joint_prob = p_home * p_away
                
                if h_goals > a_goals: home_win_prob += joint_prob
                elif a_goals > h_goals: away_win_prob += joint_prob
                else: draw_prob += joint_prob

        # Normalise
        total_p = home_win_prob + draw_prob + away_win_prob
        home_win_prob /= total_p; draw_prob /= total_p; away_win_prob /= total_p
        
        # Apply engineered Derby adjustments (boost draw probability by 15%, squeezing the gaps)
        if is_derby:
            draw_inflation = draw_prob * 0.15
            draw_prob += draw_inflation
            home_win_prob -= (draw_inflation / 2)
            away_win_prob -= (draw_inflation / 2)

        # Intelligent Capping & Clean Sheet Threshold Logic
        predicted_home_score = round(expected_home_goals)
        predicted_away_score = round(expected_away_goals)
        
        if expected_home_goals > 0.35 and predicted_home_score == 0 and away_profile['AwayCS_Pct'] < 0.25: predicted_home_score = 1
        if expected_away_goals > 0.35 and predicted_away_score == 0 and home_profile['HomeCS_Pct'] < 0.25: predicted_away_score = 1
        if away_profile['AwayCS_Pct'] >= 0.40 and expected_home_goals < 1.1: predicted_home_score = 0
        if home_profile['HomeCS_Pct'] >= 0.40 and expected_away_goals < 1.1: predicted_away_score = 0
        if predicted_home_score > 4: predicted_home_score = 4
        if predicted_away_score > 4: predicted_away_score = 4
        
        # --- DISPLAY RESULTS PANEL ---
        st.markdown("---")
        st.subheader("🔮 MATCH PREDICTION RESULT")
        
        if is_derby:
            st.warning("🚨 **Local Derby Detected!** Match variance increased, draw probability inflated contextually.")
            
        st.write("**Match Outcome Probabilities:**")
        p_col1, p_col2, p_col3 = st.columns(3)
        p_col1.metric(label=f"🏠 {home_team} Win", value=f"{home_win_prob*100:.1f}%")
        p_col2.metric(label=f"🤝 Draw Probability", value=f"{draw_prob*100:.1f}%")
        p_col3.metric(label=f"🚌 {away_team} Win", value=f"{away_win_prob*100:.1f}%")
        
        st.markdown("---")
        st.write(f"**Data Engine Insights:**")
        st.caption(f"Historical Implied Market Win Confidence: **{home_team}** ({home_profile['MarketConfidence']*100:.1f}%) | **{away_team}** ({away_profile['MarketConfidence']*100:.1f}%)")
        st.caption(f"Estimated Rest Schedule: **{home_team}** ({home_rest if home_rest < 30 else 'Fully Rested'} days) | **{away_team}** ({away_rest if away_rest < 30 else 'Fully Rested'} days)")
        
        metric_col1, metric_col2 = st.columns(2)
        metric_col1.metric(label=f"{home_team} Adjusted Expected Goals (xG)", value=f"{expected_home_goals:.2f}")
        metric_col2.metric(label=f"{away_team} Adjusted Expected Goals (xG)", value=f"{expected_away_goals:.2f}")
        
        st.info(f"### Predicted Score: **{home_team} {predicted_home_score} - {predicted_away_score} {away_team}**")
        
        if predicted_home_score > predicted_away_score: st.success(f"Outcome: **{home_team} Win!** 🏠")
        elif predicted_away_score > predicted_home_score: st.success(f"Outcome: **{away_team} Win!** 🚌")
        else: st.warning("Outcome: **It's a projected Draw!** 🤝")