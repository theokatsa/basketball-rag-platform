"""A fourth test set: questions taken from the web on 2026-11-26, frozen before any system was run on it.

The StatQuery contract (app/services/stat_query.py) was written before these questions were collected,
and no rule or prompt was changed while they were collected. Every question keeps its original wording.

Sources
  usc       huggingface.co/USC-Applied-NLP-Group/SQL-Generation, file gpt_4_test.tsv (150 questions about
            team games written for the Kaggle NBA database). Every third question, rows 1, 4, 7, ... 148:
            50 questions. Where the wording is ambiguous the authors' own SQL in that file decides.
  statmuse  statmuse.com/nba/ask pages: queries typed by StatMuse users, as the page titles show them.
            Every result of the searches in WEB_SEARCHES that asks for something with one answer, in the
            order found, plus the "related searches" on statmuse.com/nba/ask/2024-25-nba-best-record
            (the first link of each section). Left out, with the reason, in WEB_EXCLUDED.
  quiz      sporcle.com/games/Zipcity/nba-2425 (all 21 clues), sporcle.com/games/BigAl03/random-nba-advanced-stats
            (all 10 clues), sporcle.com/games/Feely/2025nbaneverscoreless, and two yardbarker.com quizzes
            (2024-25 triple-doubles, 2024-25 assist leaders). A clue keeps its words, after the quiz title.

Rules, fixed before any answer key was computed (1-6 are those of external_questions.py):
1. The database holds the 2024-25 regular season only.
2. Other seasons, careers, franchise history, playoffs, awards, the draft, or data that is not stored
   must be declined. Not stored here: fast-break points, second-chance points, points in the paint,
   points off turnovers, lead changes, times tied, largest lead, team rebounds, and-ones, PER, box
   plus-minus, betting lines, fantasy points, and the NBA Cup final (not a regular-season game).
3. Per-game averages and other rates without a stated minimum use 58 games (NBA.com); FG% 300 made,
   3P% 82 made, FT% 125 made. A stated minimum replaces them all.
4. For "who leads" any tied leader counts. An empty key is passed only by saying nobody qualifies (or declining).
5. Rookie = career starts in 2024. The All-Star break of 2025 ended on 16 February 2025.
6. Questions with no season, or "this season", "the dataset", "the database", mean the stored season.
   A named other season ("2020", "1996", "last season", "2026-27", "current"), a decade, "ever",
   "all-time", "in history", or a question needing several seasons ("in which season") is declined.
   A year alone names the season that ends in it: "2025" is 2024-25.
7. An "average" of a percentage over games may be the mean of the games or the season ratio: both
   values are accepted ("nums"). A number that may be a fraction or a percentage is accepted in both forms.

check: "lead" first player or team named is in the key, "names" every key name is in the answer,
       "num" the answer contains the number, "nums" it contains one of the numbers, "decline", "judge".
"""

from evaluation.external_questions import GAME, QUAL, ROOKIE, SEASON, TD, TEAMS, best, g_best, g_count, p_all, p_best, r, t_best

W = []


def add(source, ref, original, check, sql=None, text=None, reason=None):
    W.append({"id": len(W) + 1, "source": source, "ref": ref, "original": original, "text": text or original, "check": check, "sql": sql, "reason": reason})


def no(source, ref, original, reason, text=None):
    add(source, ref, original, "decline", text=text, reason=reason)


TS = r("s.pts", "2 * (s.fga + 0.44 * s.fta)")
WINS, LOSSES = "sum(g.won::int)", "sum((not g.won)::int)"


def team_val(expr, team, where="true", digits=1):
    return f"select round(({expr})::numeric, {digits}) from {TEAMS} where t.full_name = '{team}' and {where}"


def both(*queries):
    """Several accepted values, for "nums"."""
    return " union all ".join(f"select * from ({q}) x{i}" for i, q in enumerate(queries))


# ------------------------------------------------------------------ usc: gpt_4_test.tsv, every third row
U = "usc"
add(U, 1, "What is the average number of fg_pct in home games by the Chicago Bulls?", "nums", both(
    team_val("avg(100.0 * g.fgm / g.fga)", "Chicago Bulls", "g.is_home"), team_val("100.0 * sum(g.fgm) / sum(g.fga)", "Chicago Bulls", "g.is_home")))
no(U, 4, "What is the maximum number of team rebounds recorded by the Dallas Mavericks in away games where they committed more than 20 fouls?", "not_recorded")
add(U, 7, "Which team has the nickname 'Celtics'?", "lead", "select full_name from teams where nickname = 'Celtics'")
no(U, 10, "Which team had the most fast break points in a single home game during the 2020 season?", "other_season_or_career")
no(U, 13, "Which team had the best three-point shooting percentage in home games during the 2020 season?", "other_season_or_career")
no(U, 16, "What was the average number of fastbreak points scored by the Houston Rockets in games they won by more than 15 points at home?", "not_recorded")
no(U, 19, "Which team played the most total games (home + away) between 1995 and 2005?", "other_season_or_career")
no(U, 22, "What is the total second chance points by the Miami Heat at home?\"", "not_recorded")
no(U, 25, "In which season did the Chicago Bulls have the highest average ft_pct at home?", "other_season_or_career")
no(U, 28, "What was the highest combined steals and blocks total for the Toronto Raptors in any home game during their championship season?", "other_season_or_career")
no(U, 31, "What is the largest margin of victory the Miami Heat have ever had in an away game?", "other_season_or_career")
add(U, 34, "What was the highest total rebound count by an away team in a game?", "num", "select max(g.reb) from team_box_scores g where not g.is_home")
no(U, 37, "What is the highest fast break points by the Houston Rockets at home?", "not_recorded")
add(U, 40, "Which home team had the most games with a positive plus-minus but still lost?", "lead", f"select distinct t.full_name from {TEAMS} where g.is_home and not g.won and g.points > g.opponent_points")
no(U, 43, "What was the average points scored by the Denver Nuggets in home games during the 2019 season?", "other_season_or_career")
add(U, 46, "What is the average number of ast in away games by the Los Angeles Lakers?", "num", team_val("avg(g.ast)", "Los Angeles Lakers", "not g.is_home"))
no(U, 49, "What is the total points in the paint by the Chicago Bulls at home in games they lost in 1996?", "other_season_or_career")
no(U, 52, "List all games where the Houston Rockets and Dallas Mavericks played each other in the 2015 season.", "other_season_or_career")
add(U, 55, "What is the lowest plus-minus score for the New York Knicks away?", "num", team_val("min(g.points - g.opponent_points)", "New York Knicks", "not g.is_home", 0))
add(U, 58, "What was the average points difference in home games won by the Denver Nuggets?", "num", team_val("avg(g.points - g.opponent_points)", "Denver Nuggets", "g.is_home and g.won"))
no(U, 61, "In the 2020 season, what was the average number of second chance points allowed by the New Orleans Pelicans in games they won by less than 5 points?", "other_season_or_career")
no(U, 64, "What is the average number of three-pointers made by the Golden State Warriors at home in the 2018 season?", "other_season_or_career")
no(U, 67, "How many points did the home team score in the game with the most lead changes and the fewest total fouls?", "not_recorded")
no(U, 70, "What is the average points in the paint by the Utah Jazz away when they won?", "not_recorded")
add(U, 73, "What is the highest three-point percentage the Phoenix Suns achieved in an away game?", "nums", both(
    team_val("max(100.0 * g.tpm / nullif(g.tpa, 0))", "Phoenix Suns", "not g.is_home"), team_val("max(1.0 * g.tpm / nullif(g.tpa, 0))", "Phoenix Suns", "not g.is_home", 3)))
no(U, 76, "How many free throws did the Houston Rockets attempt in away games they won during the 2020 season?", "other_season_or_career")
add(U, 79, "What is the average number of tov in away games by the Los Angeles Lakers?", "num", team_val("avg(g.tov)", "Los Angeles Lakers", "not g.is_home"))
no(U, 82, "How many times did the Miami Heat score more than 120 points at home in the 2015 season?", "other_season_or_career")
no(U, 85, "What was the highest number of steals by the Detroit Pistons in a single game during the 2004 season?", "other_season_or_career")
add(U, 88, "What is the highest number of three-pointers made in a single game by the Houston Rockets at home?", "num", team_val("max(g.tpm)", "Houston Rockets", "g.is_home", 0))
no(U, 91, "How many total offensive rebounds did the Houston Rockets have in away games during the 2018 season?", "other_season_or_career")
add(U, 94, "How many points did the Phoenix Suns score in the highest scoring away game they played?", "num", team_val("max(g.points)", "Phoenix Suns", "not g.is_home", 0))
no(U, 97, "In which season did the Milwaukee Bucks have the highest average fg_pct at home?", "other_season_or_career")
add(U, 100, "What is the average scoring ouput for home teams. Round to 2 decimal places.", "num", "select round(avg(g.points)::numeric, 2) from team_box_scores g where g.is_home")
LAKER_FT = f"""from team_box_scores g join teams t on t.nba_team_id = g.nba_team_id
 join team_box_scores x on x.nba_game_id = g.nba_game_id and x.nba_team_id <> g.nba_team_id where t.full_name = 'Los Angeles Lakers'"""
add(U, 103, "What is the highest combined ft_pct in any game involving the Los Angeles Lakers?", "nums", both(
    f"select round(max(1.0 * g.ftm / nullif(g.fta, 0) + 1.0 * x.ftm / nullif(x.fta, 0))::numeric, 3) {LAKER_FT}",
    f"select round(max(100.0 * g.ftm / nullif(g.fta, 0) + 100.0 * x.ftm / nullif(x.fta, 0))::numeric, 1) {LAKER_FT}"))
no(U, 106, "What was the difference in average free throw attempts between the Brooklyn Nets and their opponents in home games during the 2020 season?", "other_season_or_career")
no(U, 109, "What was the lowest-scoring game involving the Indiana Pacers in the 1994 season?", "other_season_or_career")
no(U, 112, "What was the difference in second-chance points between the Chicago Bulls and their opponents in their closest home game of the 2016 season?", "other_season_or_career")
add(U, 115, "How many points did the away team score in the only game where the home team had exactly 69 field goal attempts?", "nums",
    "select a.points from team_box_scores h join team_box_scores a on a.nba_game_id = h.nba_game_id and a.nba_team_id <> h.nba_team_id where h.is_home and h.fga = 69")
add(U, 118, "Which team had the most games where both teams scored over 110 points?", "lead", t_best("count(*)", "g.points > 110 and g.opponent_points > 110"))
no(U, 121, "What is the average number of assists per game for the Golden State Warriors when they won during the 2018 season?", "other_season_or_career")
no(U, 124, "Which team had the highest average free throw percentage at home in the 2016 season?", "other_season_or_career")
no(U, 127, "What is the highest number of points the Golden State Warriors have ever scored in a single home game?", "other_season_or_career")
no(U, 130, "How many three-pointers did the Golden State Warriors make in total during the 2016 season?", "other_season_or_career")
no(U, 133, "How many points did the home team score in the game with the most second chance points?", "not_recorded")
add(U, 136, "Which team is based in the city of Chicago?", "lead", "select full_name from teams where city = 'Chicago'")
no(U, 139, "How many home games did the Los Angeles Lakers play in the 2022 season?", "other_season_or_career")
add(U, 142, "What is the average number of pts in away games by the Portland Trail Blazers?", "num", team_val("avg(g.points)", "Portland Trail Blazers", "not g.is_home"))
no(U, 145, "How many times were games tied when the Indiana Pacers played away?", "not_recorded")
add(U, 148, "Which game had the highest total points scored by both teams when the Los Angeles Lakers played at home?", "num", team_val("max(g.points + g.opponent_points)", "Los Angeles Lakers", "g.is_home", 0))

# ------------------------------------------------------------------ statmuse: page titles, in the order found
S = "statmuse"
WEB_SEARCHES = [
    "2024-25 NBA season trivia questions and answers stats leaders",
    "statmuse 2024-25 NBA most points in a game this season",
    "statmuse nba ask this season leaders 2024-25",
    "statmuse nba ask most this season 2025 players",
    "statmuse nba ask 2024-25 regular season team record",
    "statmuse nba ask who has the highest this season 2024-25",
    "statmuse nba ask 2024-25 per game",
    "statmuse nba ask in a game 2024-25",
    "statmuse nba ask 2024-25 percentage minimum",
    "statmuse nba ask rookies 2024-25",
    "statmuse nba ask 2024-25 total season",
    "statmuse nba ask 2024-25 vs team games",
]
no(S, "td3-leaders-last-season", "td3 leaders last season", "other_season_or_career")
no(S, "highest-per", "highest per", "not_recorded")
no(S, "best-per-in-league", "best per in league", "not_recorded")
add(S, "2025-nba-league-leaders-in-points", "2025 nba league leaders in points", "lead", p_best("s.ppg", QUAL))
add(S, "most-pts-in-a-game-2025", "most pts in a game 2025", "lead", g_best("b.points"))
no(S, "who-had-the-most-points-in-a-game-last-season", "who had the most points in a game last season", "other_season_or_career")
add(S, "highest-game-point", "highest game point", "lead", g_best("b.points"))
add(S, "most-points-scored-in-the-nba-in-a-game-this-season", "most points scored in the nba in a game this season", "lead", g_best("b.points"))
add(S, "highest-scoring-games-by-lebron-2025", "highest scoring games by lebron 2025", "num", f"select max(b.points) from {GAME} where b.minutes > 0 and p.full_name = 'LeBron James'")
add(S, "most-points-in-home-game", "most points in home game", "lead", g_best("b.points", "g.is_home"))
add(S, "players-with-the-most-25-point-games-this-season-in-the-nba", "players with the most 25 point games this season in the nba", "lead", g_count("b.points >= 25"))
add(S, "highest-scoring-games-this-season", "highest scoring games this season", "judge")
no(S, "most-60-point-games-last-seasons", "most 60 point games last seasons", "other_season_or_career")
add(S, "points-stat-leaders-in-the-2024-2025-nba-season", "Points Stat Leaders In The 2024-2025 NBA Season", "lead", p_best("s.ppg", QUAL))
add(S, "nba-scoring-leaders-2025-season", "NBA Scoring Leaders 2025 Season", "lead", p_best("s.ppg", QUAL))
no(S, "nba-player-with-most-and-ones-this-season", "NBA Player With Most And Ones This Season", "not_recorded")
add(S, "most-points-this-season", "Most Points This Season", "lead", p_best("s.pts"))
add(S, "nba-players-top-scorers-list-this-season", "NBA Players Top Scorers List This Season", "lead", p_best("s.ppg", QUAL))
no(S, "nba-player-per-rankings", "NBA Player Per Rankings", "not_recorded")
no(S, "who-has-the-most-and-ones-this-season", "Who Has The Most And Ones This Season", "not_recorded")
no(S, "every-nba-team-ats-record-in-2025", "Every NBA Team Ats Record In 2025", "not_recorded")
add(S, "best-nba-record-2025", "Best NBA Record 2025", "lead", t_best(WINS))
add(S, "2024-25-nba-best-record", "2024 25 NBA Best Record", "lead", t_best(WINS))
add(S, "nba-teams-with-worst-record-in-2025", "NBA Teams With Worst Record In 2025", "lead", t_best(WINS, asc=True))
add(S, "best-nba-teams-by-record", "Best NBA Teams By Record", "lead", t_best(WINS))
add(S, "best-record-on-the-nba", "Best Record On The NBA", "lead", t_best(WINS))
add(S, "highest-scoring-nba-games-2024-2025", "Highest Scoring NBA Games 2024 2025", "judge")
add(S, "highest-scoring-nba-teams-in-2024-25", "Highest Scoring NBA Teams In 2024 25", "lead", t_best("avg(g.points)"))
add(S, "leader+in+true+shooting+2024/2025", "Leader In True Shooting 2024/2025", "lead", p_best(TS, QUAL))
no(S, "nba-per-leaders-2024-2025", "NBA Per Leaders 2024 2025", "not_recorded")
add(S, "2024-25+nba+teams+possessions+per+game", "2024-25 NBA Teams Possessions Per Game", "lead", t_best("avg(g.fga + 0.44 * g.fta - g.oreb + g.tov)"))
add(S, "average+nba+team+points+per+game+in+2024-2025", "Average NBA Team Points Per Game In 2024-2025", "num", "select round(avg(g.points)::numeric, 1) from team_box_scores g")
add(S, "nba-team-scoring-per-game-leaders-2024-2025", "NBA Team Scoring Per Game Leaders 2024 2025", "lead", t_best("avg(g.points)"))
add(S, "nba-most-minutes-played-per-game-in-2024-2025", "NBA Most Minutes Played Per Game In 2024 2025", "lead", p_best("s.mpg", QUAL))
no(S, "mpg-stats-last-season", "Mpg Stats Last Season", "other_season_or_career")
add(S, "ppg-leaders-2025", "Ppg Leaders 2025", "lead", p_best("s.ppg", QUAL))
add(S, "most+assists+per+game+2024-25+nba", "Most Assists Per Game 2024-25 NBA", "lead", p_best("s.apg", QUAL))
no(S, "current-nba-games", "Current NBA Games", "other_season_or_career")
add(S, "nba+true+shooting+percentage+leaders+2024-2025+minimum+21+ppg", "NBA True Shooting Percentage Leaders 2024-2025 Minimum 21 Ppg", "lead", p_best(TS, "s.ppg >= 21"))
add(S, "nba+ts%25+leaders+2024-25", "NBA Ts% Leaders 2024-25", "lead", p_best(TS, QUAL))
add(S, "worst+true+shooting+percentage+24-25+qualified+players+nba", "Worst True Shooting Percentage 24-25 Qualified Players NBA", "lead", p_best(TS, QUAL, asc=True))
add(S, "nba+2025+rookies+scoring+record+since+all-star+break", "NBA 2025 Rookies Scoring Record Since All-star Break", "lead",
    best(f"select p.full_name name, sum(b.points) v from {GAME} where b.minutes > 0 and {ROOKIE} and b.game_date > '2025-02-16' group by p.full_name"))
add(S, "nba-rookie-top-scoring-leaders-2024-2025", "NBA Rookie Top Scoring Leaders 2024 2025", "lead", p_best("s.ppg", f"{QUAL} and {ROOKIE}"))
add(S, "jayson+tatum+24%2F25+season", "Jayson Tatum 24/25 Season", "num",
    "select round(avg(b.points)::numeric, 1) from player_box_scores b join players p on p.id = b.player_id where p.full_name = 'Jayson Tatum' and b.minutes > 0")
add(S, "2024-2025-nba-team-standing", "2024 2025 NBA Team Standing", "lead", t_best(WINS))
add(S, "what+is+the+highest+scoring+nba+game+in+2024-25+by+a+team", "What Is The Highest Scoring NBA Game In 2024-25 By A Team", "lead", t_best("max(g.points)"))
add(S, "celtics+record+vs+every+team+2024-25", "Celtics Record Vs Every Team 2024-25", "judge")
# Related searches on statmuse.com/nba/ask/2024-25-nba-best-record, then the first link of each later section.
no(S, "related:1", "Most threes by a team in a loss all-time", "other_season_or_career")
no(S, "related:2", "Who won the NBA Finals in 2024-25?", "playoffs")
no(S, "related:3", "Largest margin of victory by a team in a playoff game", "playoffs")
no(S, "leaders:1", "ppg leaders 2026-27", "other_season_or_career")
no(S, "rankings:1", "team ortg rankings 2026-27", "other_season_or_career")
no(S, "fantasy:1", "most fanduel points 2026-27", "other_season_or_career")
no(S, "betting:1", "best record ats 2026-27", "other_season_or_career")

WEB_EXCLUDED = {
    "a table with no single answer": [
        "nba 2025 season leaders", "nba stat leaders 2025", "Stat Leaders In The NBA 2024 2025", "NBA Stat Leaders 24-25", "NBA Stat Leaders For 2024-25",
        "NBA Player Stats 2024 25", "NBA Season Leaders 2025", "2024 NBA Season Stat Leaders", "2025 NBA Stats Leaders", "2024 NBA Players Stats",
        "NBA Player Stat Leaders This Season", "NBA Player Stats Leaders This Season", "Every NBA Players Stats This Season", "Best NBA Team Stats",
        "2025 NBA Team Stats", "NBA Statistic Leaders Per Game 2024-25", "NBA Games 2024 25", "2024-2025 NBA Stats", "NBA Schedule For 2024-25",
        "NBA Schedule 2024 2025", "NBA Schedule 2024-25", "NBA 2024-25 Stats All Players Played Games", "NBA Players Stats 2024-2025",
        "Rookie Stats NBA 2024-2025", "NBA Rookies 2024-25 Stats", "NBA Rookies Stats Leaders 2024 2025", "NBA Rookie Rankings This Season",
        "Team Opponent Stats", "NBA Stats 2024", "All NBA Player Stats For This Season", "Game Score Stat",
    ],
    "garbled": ["most points in 191", "leaders lasta season", "Standings Of Player With Most It This Season", "24-25 NBA Players Total -"],
    "the same request as one kept, only the season or a word written differently": [
        "Highest Scoring NBA Teams In 2024-2025", "Highest Scoring NBA Teams In 2025", "NBA Minutes Per Game Leaders 2024 2025",
        "True Shooting Percentage Leaders NBA 2024-25", "True Shooting Percentage Leaders 2024-25", "Ts% Leaders 2024-2025", "Ts% Leaders 2024-25",
        "Jayson Tatum 2025 Season Stats", "Jayson Tatum 2024-25 Season Stats",
    ],
}

# ------------------------------------------------------------------ quiz: Sporcle and Yardbarker, clue after the quiz title
Q = "quiz"
ALMANAC = "NBA Almanac - 2024-25"
for clue, reason in [("Champions", "playoffs"), ("Eastern Conference Champions", "playoffs"), ("Western Conference Champions", "playoffs"), ("Finals MVP", "awards_or_draft"), ("NBA Cup", "not_recorded")]:
    no(Q, f"almanac:{clue}", clue, reason, text=f"{ALMANAC}: {clue}")
add(Q, "almanac:Most Wins (Team)", "Most Wins (Team)", "lead", t_best(WINS), text=f"{ALMANAC}: Most Wins (Team)")
add(Q, "almanac:Most Losses (Team)", "Most Losses (Team)", "lead", t_best(LOSSES), text=f"{ALMANAC}: Most Losses (Team)")
for clue in ["Most Valuable Player", "Defensive Player of the Year", "Rookie of the Year", "Sixth Man of the Year", "Coach of the Year"]:
    no(Q, f"almanac:{clue}", clue, "awards_or_draft", text=f"{ALMANAC}: {clue}")
for clue, sql in [
    ("Scoring Leader", p_best("s.ppg", QUAL)), ("Rebounds Leader", p_best("s.rpg", QUAL)), ("Assists Leader", p_best("s.apg", QUAL)),
    ("Steals Leader", p_best("s.spg", QUAL)), ("Blocks Leader", p_best("s.bpg", QUAL)), ("Highest FG%", p_best(r("s.fgm", "s.fga"), "s.fgm >= 300")),
    ("Highest FT%", p_best(r("s.ftm", "s.fta"), "s.ftm >= 125")), ("Highest 3PT%", p_best(r("s.tpm", "s.tpa"), "s.tpm >= 82")),
]:
    add(Q, f"almanac:{clue}", clue, "lead", sql, text=f"{ALMANAC}: {clue}")
no(Q, "almanac:#1 Overall Draft Pick", "#1 Overall Draft Pick", "awards_or_draft", text=f"{ALMANAC}: #1 Overall Draft Pick")
add(Q, "never-scoreless", "Can you name the NBA players who scored in every game they appeared in during the 2024-25 regular season?", "judge")
ADVANCED = "Random NBA Advanced Stat Leaders 2024-25"
for clue, check, sql, reason in [
    ("True Shooting Pct", "lead", p_best(TS, QUAL), None),
    ("Player Efficiency Rating", "decline", None, "not_recorded"),
    ("Defensive Rating", "lead", p_best("a.def_rating", QUAL, asc=True), None),
    ("Turnover Pct (Lowest)", "lead", p_best("a.tov_pct", QUAL, asc=True), None),
    ("Personal Fouls Per 100 pos", "lead", p_best(r("s.pf * 100", "a.possessions"), QUAL), None),
    ("3-Pt Field Goals Per 36 Min", "lead", p_best(r("s.tpm * 36", "s.mins"), QUAL), None),
    ("Total Minutes Played", "lead", p_best("s.mins"), None),
    ("Free Throw Attempt Rate", "lead", p_best(r("s.fta", "s.fga"), QUAL), None),
    ("Defensive +/- Per 100 pos (Lowest)", "decline", None, "not_recorded"),
    ("Usage Pct", "lead", p_best("a.usg_pct", QUAL), None),
]:
    add(Q, f"advanced:{clue}", clue, check, sql, text=f"{ADVANCED}: {clue}", reason=reason)
add(Q, "yardbarker:triple-doubles", "Can you name every player to record a triple-double in the 2024-25 NBA season?", "names",
    f"select distinct p.full_name from {GAME} where b.minutes > 0 and {TD}")
add(Q, "yardbarker:assists", "Can you name the NBA players with at least 400 assists in the 2024-25 season?", "names", p_all("s.ast >= 400"))
