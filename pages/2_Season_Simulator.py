import pandas as pd
import streamlit as st
import numpy as np
from scipy.stats import poisson

st.set_page_config(page_title="Season Simulator ", page_icon="📊", layout="wide")
st.title("📊 Premier League End-of-Season Simulator")
st.write("This engine simulates all remaining fixtures of the 2025/26 season using our multi-layered Poisson model to project the final table standings.")

# --- LOAD DATA ---
@st.cache_data
def load_data():
    url = "https://www.football-data.co.uk/mmz4281/2526/E0.csv"
    df = pd.read_csv(url, storage_options={'User-Agent': 'Mozilla/5.0'})
    clean_df = df[['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'B365H', 'B365D', 'B365A']].copy()
    clean_df.columns = ['HomeTeam', 'AwayTeam', 'HomeGoals', 'AwayGoals', 'B365H', 'B365D', 'B365A']
    return clean_df.dropna()

clean_df = load_data()

# --- REUSE GENERATED MASTER SHEET STATS ---
avg_home_goals = clean_df['HomeGoals'].mean()
avg_away_goals = clean_df['AwayGoals'].mean()

home_stats = clean_df.groupby('HomeTeam')['HomeGoals'].mean().reset_index().rename(columns={'HomeTeam': 'Team', 'HomeGoals': 'AvgGoalsScoredHome'})
home_conceded = clean_df.groupby('HomeTeam')['AwayGoals'].mean().reset_index().rename(columns={'HomeTeam': 'Team', 'AwayGoals': 'AvgGoalsConcededHome'})
away_stats = clean_df.groupby('AwayTeam')['AwayGoals'].mean().reset_index().rename(columns={'AwayTeam': 'Team', 'AwayGoals': 'AvgGoalsScoredAway'})
away_conceded = clean_df.groupby('AwayTeam')['HomeGoals'].mean().reset_index().rename(columns={'AwayTeam': 'Team', 'HomeGoals': 'AvgGoalsConcededAway'})

all_matches = []
for index, row in clean_df.iterrows():
    all_matches.append({'Team': row['HomeTeam'], 'GoalsScored': row['HomeGoals'], 'GoalsConceded': row['AwayGoals']})
    all_matches.append({'Team': row['AwayTeam'], 'GoalsScored': row['AwayGoals'], 'GoalsConceded': row['HomeGoals']})

form_df = pd.DataFrame(all_matches)
recent_form = form_df.groupby('Team').tail(5).groupby('Team').mean().reset_index()
recent_form.columns = ['Team', 'FormGoalsScored', 'FormGoalsConceded']

team_stats = pd.merge(home_stats, home_conceded, on='Team')
team_stats = pd.merge(team_stats, away_stats, on='Team')
team_stats = pd.merge(team_stats, away_conceded, on='Team')
team_stats = pd.merge(team_stats, recent_form, on='Team')

# --- CALCULATE CURRENT ACTUAL LEAGUE TABLE ---
teams = sorted(team_stats['Team'].unique())
current_table = {team: {'P': 0, 'W': 0, 'D': 0, 'L': 0, 'GF': 0, 'GA': 0, 'GD': 0, 'Pts': 0} for team in teams}

for index, row in clean_df.iterrows():
    h, a, hg, ag = row['HomeTeam'], row['AwayTeam'], int(row['HomeGoals']), int(row['AwayGoals'])
    current_table[h]['P'] += 1; current_table[a]['P'] += 1
    current_table[h]['GF'] += hg; current_table[h]['GA'] += ag
    current_table[a]['GF'] += ag; current_table[a]['GA'] += hg
    
    if hg > ag:
        current_table[h]['W'] += 1; current_table[h]['Pts'] += 3; current_table[a]['L'] += 1
    elif ag > hg:
        current_table[a]['W'] += 1; current_table[a]['Pts'] += 3; current_table[h]['L'] += 1
    else:
        current_table[h]['D'] += 1; current_table[h]['Pts'] += 1
        current_table[a]['D'] += 1; current_table[a]['Pts'] += 1

for team in teams:
    current_table[team]['GD'] = current_table[team]['GF'] - current_table[team]['GA']

# --- GENERATE REMAINING FIXTURES (THEORETICAL OVERALL MATRIX) ---
# In a production app, we would load an unplayed fixture list. 
# For this data science algorithm, we generate all missing pairings in the double round-robin.
played_fixtures = set(zip(clean_df['HomeTeam'], clean_df['AwayTeam']))
remaining_fixtures = [(h, a) for h in teams for a in teams if h != a and (h, a) not in played_fixtures]

st.subheader("Current Season Progress")
st.write(f"Matches Played So Far: **{len(clean_df)}** | Estimated Remaining Fixtures to Simulate: **{len(remaining_fixtures)}**")

# --- SIMULATION TRIGGER ---
if st.button("🚀 Run Monte Carlo Season Simulation", type="primary"):
    # Copy current real table standings as our baseline starting point
    sim_table = {team: data.copy() for team, data in current_table.items()}
    
    # Progress bar to visualize loop speed
    progress_bar = st.progress(0)
    
    for idx, (home, away) in enumerate(remaining_fixtures):
        home_profile = team_stats[team_stats['Team'] == home].iloc[0]
        away_profile = team_stats[team_stats['Team'] == away].iloc[0]
        
        # Calculate Expected Goals (xG Blend)
        base_home_xG = (home_profile['AvgGoalsScoredHome'] * away_profile['AvgGoalsConcededAway']) / avg_home_goals
        base_away_xG = (away_profile['AvgGoalsScoredAway'] * home_profile['AvgGoalsConcededHome']) / avg_away_goals
        form_home_xG = (home_profile['FormGoalsScored'] * away_profile['FormGoalsConceded']) / avg_home_goals
        form_away_xG = (away_profile['FormGoalsScored'] * home_profile['FormGoalsConceded']) / avg_away_goals
        
        expected_home_goals = (base_home_xG * 0.7) + (form_home_xG * 0.3)
        expected_away_goals = (base_away_xG * 0.7) + (form_away_xG * 0.3)
        
        # Monte Carlo sampling: Pick a realistic scoreline based on the calculated Poisson distributions
        sim_hg = np.random.poisson(expected_home_goals)
        sim_ag = np.random.poisson(expected_away_goals)
        
        # Update simulation records
        sim_table[home]['P'] += 1; sim_table[away]['P'] += 1
        sim_table[home]['GF'] += sim_hg; sim_table[home]['GA'] += sim_ag
        sim_table[away]['GF'] += sim_ag; sim_table[away]['GA'] += sim_hg
        
        if sim_hg > sim_ag:
            sim_table[home]['W'] += 1; sim_table[home]['Pts'] += 3; sim_table[away]['L'] += 1
        elif sim_ag > sim_hg:
            sim_table[away]['W'] += 1; sim_table[away]['Pts'] += 3; sim_table[home]['L'] += 1
        else:
            sim_table[home]['D'] += 1; sim_table[home]['Pts'] += 1
            sim_table[away]['D'] += 1; sim_table[away]['Pts'] += 1
            
        progress_bar.progress((idx + 1) / len(remaining_fixtures))
        
    # Format and present final table
    for team in teams:
        sim_table[team]['GD'] = sim_table[team]['GF'] - sim_table[team]['GA']
        
    final_df = pd.DataFrame.from_dict(sim_table, orient='index').reset_index().rename(columns={'index': 'Team'})
    final_df = final_df.sort_values(by=['Pts', 'GD', 'GF'], ascending=False).reset_index(drop=True)
    final_df.index += 1  # Standard 1-20 indexing position
    
    st.success("Simulation Complete!")
    st.dataframe(final_df[['Team', 'P', 'W', 'D', 'L', 'GF', 'GA', 'GD', 'Pts']], use_container_width=True)