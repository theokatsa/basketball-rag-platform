"""Externally written questions: a third test set, frozen before the system was run on it.

Sources (read 2026-11-26), every question kept in its original wording:
  hf        huggingface.co/datasets/awsomedod/text-to-sql-nba, all 50 rows (no author or licence given)
  stathead  faq.sports-reference.com/portal/en/kb/articles/sample-searches-basketball, every example
            outside the college sections (WNBA, ABA and historical ones stay in as "should decline")
  scout     basketball.com.au/news/step-by-step-how-to-scout-a-basketball-player (all questions),
            betterbasketball.com/?p=5197 (all questions), noceilingsnba.com/p/the-matrix-of-scouting
            (questions about the player being evaluated; the ones addressed to the reader are listed
            in SCOUT_EXCLUDED)

Rules, fixed before any answer key was computed:
1. The database holds the 2024-25 regular season only, so "a season" / "in a single season" means it.
2. A question needing other seasons, careers, franchise history, playoffs, awards, the draft, college,
   WNBA/ABA, or something not stored (games started, handedness, birthplace, the score at a moment,
   points by quarter for a player) should be declined.
3. Per-game averages and percentages without a stated minimum use the NBA.com leaderboard minimums:
   58 games (70% of 82); FG% 300 made, 3P% 82 made, FT% 125 made. A stated minimum replaces them all.
   A condition on a per-game average ("averaged 5 assists") also uses the 58-game minimum.
4. For "who leads" any player tied for first counts. An empty answer key is passed only by saying that
   nobody qualifies (or declining).
5. Teenager = season age 19 or less; rookie = career starts in 2024; "7'0" or taller" = 84+ inches;
   centre = position starting with "Center". A game is played when the player logged minutes.
6. Scouting questions name no player, so the reference ("he", "they", "this player") is replaced with a
   player taken in order from those with 58+ games and 20+ minutes, sorted by md5 of the name. They have
   no SQL truth: "decline" ones must be declined, "judge" ones are saved for a human to read.

check: "lead" first player or team named is in the key, "names" every key name is in the answer,
       "num" the answer contains the number, "text" the answer contains the text, "decline", "judge".
"""

E = []


def add(source, ref, original, check, sql=None, text=None, reason=None):
    E.append({"id": len(E) + 1, "source": source, "ref": ref, "original": original, "text": text or original, "check": check, "sql": sql, "reason": reason})


def no(source, ref, original, reason, text=None):
    add(source, ref, original, "decline", text=text, reason=reason)


SEASON = """(select p.full_name, b.player_id, count(*) gp, sum(b.minutes) mins, avg(b.minutes) mpg, sum(b.points) pts, avg(b.points) ppg,
 sum(b.reb) reb, avg(b.reb) rpg, sum(b.oreb) oreb, sum(b.dreb) dreb, sum(b.ast) ast, avg(b.ast) apg, avg(b.stl) spg, avg(b.blk) bpg,
 sum(b.stl) stl, sum(b.blk) blk, sum(b.tov) tov, sum(b.pf) pf, sum(b.fgm) fgm, sum(b.fga) fga, sum(b.tpm) tpm, sum(b.tpa) tpa,
 sum(b.ftm) ftm, sum(b.fta) fta from player_box_scores b join players p on p.id = b.player_id where b.minutes > 0 group by 1, 2) s
 left join player_profiles pp on pp.player_id = s.player_id left join player_advanced_stats a on a.player_id = s.player_id"""
GAME = """player_box_scores b join players p on p.id = b.player_id left join player_profiles pp on pp.player_id = b.player_id
 left join player_advanced_stats a on a.player_id = b.player_id
 join team_box_scores g on g.nba_game_id = b.nba_game_id and g.nba_team_id = b.nba_team_id
 join teams t on t.nba_team_id = b.nba_team_id join teams o on o.nba_team_id = g.opponent_nba_team_id"""
TEAMS = "team_box_scores g join teams t on t.nba_team_id = g.nba_team_id join teams o on o.nba_team_id = g.opponent_nba_team_id"
OT = "exists (select 1 from team_period_scores q where q.nba_game_id = g.nba_game_id and q.period = 5)"
QUAL = "s.gp >= 58"
AGE = "a.season_age"
INCH = "(split_part(nullif(pp.height, ''), '-', 1)::int * 12 + split_part(nullif(pp.height, ''), '-', 2)::int)"
ROOKIE = "split_part(pp.season, '-', 1) = '2024'"
TD = "((b.points>=10)::int + (b.reb>=10)::int + (b.ast>=10)::int + (b.stl>=10)::int + (b.blk>=10)::int) >= 3"
DD = "((b.points>=10)::int + (b.reb>=10)::int + (b.ast>=10)::int + (b.stl>=10)::int + (b.blk>=10)::int) >= 2"


def r(x, y):
    return f"({x})::float / nullif({y}, 0)"


def best(inner, asc=False):
    """Every name tied for first."""
    return f"select distinct name from (select name, v, {'min' if asc else 'max'}(v) over () m from ({inner}) i where v is not null) x where v = m"


def p_best(v, where="true", asc=False):
    return best(f"select s.full_name name, {v} v from {SEASON} where {where}", asc)


def p_top(v, n, where="true", asc=False):
    return f"select s.full_name from {SEASON} where {where} and {v} is not null order by {v} {'asc' if asc else 'desc'} limit {n}"


def p_all(where):
    return f"select s.full_name from {SEASON} where {where}"


def p_val(expr, where):
    return f"select {expr} from {SEASON} where {where}"


def g_best(v, where="true"):
    return best(f"select p.full_name name, {v} v from {GAME} where b.minutes > 0 and {where}")


def g_count(where):
    return best(f"select p.full_name name, count(*) v from {GAME} where b.minutes > 0 and {where} group by p.id, p.full_name")


def t_best(v, where="true", asc=False):
    return best(f"select t.full_name name, {v} v from {TEAMS} where {where} group by t.full_name", asc)


def p_streak(ok, rows="true"):
    run = f"""select b.player_id, ({ok}) ok, row_number() over (partition by b.player_id order by b.game_date)
      - row_number() over (partition by b.player_id, ({ok}) order by b.game_date) grp from {GAME} where b.minutes > 0 and {rows}"""
    return best(f"select p.full_name name, max(c) v from (select player_id, grp, count(*) c from ({run}) r where ok group by 1, 2) y join players p on p.id = y.player_id group by p.full_name")


def t_streak(ok, rows="true"):
    run = f"""select g.nba_team_id, ({ok}) ok, row_number() over (partition by g.nba_team_id order by g.game_date)
      - row_number() over (partition by g.nba_team_id, ({ok}) order by g.game_date) grp from {TEAMS} where {rows}"""
    return best(f"select t.full_name name, max(c) v from (select nba_team_id, grp, count(*) c from ({run}) r where ok group by 1, 2) y join teams t on t.nba_team_id = y.nba_team_id group by t.full_name")


def record(a, b):
    return f"select sum(g.won::int) || '-' || sum((not g.won)::int) from {TEAMS} where t.nickname = '{a}' and o.nickname = '{b}'"


def versus(player, opponent):
    return f"select round(avg(b.points), 1) from {GAME} where b.minutes > 0 and p.full_name = '{player}' and o.nickname = '{opponent}'"


# ------------------------------------------------------------------ hf: awsomedod/text-to-sql-nba
H = "hf"
add(H, 1, "Who are the top 5 players with the highest field goal percentage among players who have played at least 50 games in a season?", "names", p_top(r("s.fgm", "s.fga"), 5, "s.gp >= 50"))
add(H, 2, "What is the average age of players who have averaged a triple-double (at least 10 in points, rebounds, and assists) in a season?", "num", p_val(f"round(avg({AGE}), 1)", f"{QUAL} and s.ppg >= 10 and s.rpg >= 10 and s.apg >= 10"))
add(H, 3, "what are the names and positions of players who have played 82 games in a season and averaged at least 20 points per game", "names", p_all("s.gp >= 82 and s.ppg >= 20"))
add(H, 4, "Who are the top 3 most well-rounded players, based on the sum of their points, rebounds, and assists per game?", "names", p_top("s.ppg + s.rpg + s.apg", 3, QUAL))
add(H, 5, "who has the highest three-point percentage among players who attempted at least 200 three-pointers in a season?", "lead", p_best(r("s.tpm", "s.tpa"), "s.tpa >= 200"))
add(H, 6, "What is the name and position of the player with the most blocks per game?", "lead", p_best("s.bpg", QUAL))
add(H, 7, "Who has the highest assist-to-turnover ratio among players with at least 5 assists per game?", "lead", p_best(r("s.ast", "s.tov"), f"{QUAL} and s.apg >= 5"))
add(H, 8, "What is the average number of games played by players who averaged a triple-double?", "num", p_val("round(avg(s.gp), 1)", f"{QUAL} and s.ppg >= 10 and s.rpg >= 10 and s.apg >= 10"))
add(H, 9, "who has the most offensive rebound among players who played at least 50 games", "lead", p_best("s.oreb", "s.gp >= 50"))
add(H, 10, "Who are the top 3 players with the highest free throw percentage among those who attempted at least 200 free throws?", "names", p_top(r("s.ftm", "s.fta"), 3, "s.fta >= 200"))
add(H, 11, "What is the average number of steals per game for players who also average at least 20 points per game?", "num", p_val("round(avg(s.spg), 2)", f"{QUAL} and s.ppg >= 20"))
no(H, 12, "What is the name and position of the player with the most games started in a season?", "not stored: games started")
add(H, 13, "What is the average age of players who have a field goal percentage above 55% and attempted at least 500 field goals in a season?", "num", p_val(f"round(avg({AGE}), 1)", f"s.fga >= 500 and {r('s.fgm', 's.fga')} > 0.55"))
add(H, 14, "Who has the highest ratio of blocks to personal fouls among players with at least 50 blocks in a season?", "lead", p_best(r("s.blk", "s.pf"), "s.blk >= 50"))
add(H, 15, "What is the name and number of games played for the player with the most total rebounds in a season?", "lead", p_best("s.reb"))
add(H, 16, "Who are the top 3 players with the highest percentage of points from three-pointers?", "names", p_top(r("3 * s.tpm", "s.pts"), 3, QUAL))
add(H, 17, "What is the average number of minutes played by players who average at least 1 block and 1 steal per game?", "num", p_val("round(avg(s.mpg), 1)", f"{QUAL} and s.bpg >= 1 and s.spg >= 1"))
add(H, 18, "Who has the highest ratio of assists to field goal attempts among players with at least 200 assists?", "lead", p_best(r("s.ast", "s.fga"), "s.ast >= 200"))
add(H, 19, "What are the names and positions of players who have a higher three-point percentage than free throw percentage (minimum 100 attempts in a season each)?", "names", p_all(f"s.tpa >= 100 and s.fta >= 100 and {r('s.tpm', 's.tpa')} > {r('s.ftm', 's.fta')}"))
add(H, 20, "Who has the highest effective field goal percentage (eFG%) among players who have attempted at least 1,000 field goals in a season?", "lead", p_best(r("s.fgm + 0.5 * s.tpm", "s.fga"), "s.fga >= 1000"))
add(H, 21, "What is the name and position of the player with the most total rebounds in a single season?", "lead", p_best("s.reb"))
add(H, 22, "Who are the top 3 players with the highest free throw attempt rate (FTA/FGA) among players with at least 500 field goal attempts?", "names", p_top(r("s.fta", "s.fga"), 3, "s.fga >= 500"))
add(H, 23, "Who has the highest steal percentage (steals per minute) among players who have played at least 2,000 minutes in a season?", "lead", p_best(r("s.stl", "s.mins"), "s.mins >= 2000"))
add(H, 24, "Who has the highest total points scored among players who have played in at least 70 games in a season?", "lead", p_best("s.pts", "s.gp >= 70"))
add(H, 25, "What is the name and three-point percentage of the player with the highest three-point percentage who has attempted at least 300 three-pointers?", "lead", p_best(r("s.tpm", "s.tpa"), "s.tpa >= 300"))
add(H, 26, "Who are the top 5 players with the highest offensive rebounding percentage (ORB / (ORB + DRB)) that averaged more than 6 rebounds per game?", "names", p_top(r("s.oreb", "s.oreb + s.dreb"), 5, f"{QUAL} and s.rpg > 6"))
add(H, 27, "Who are the top 3 players with the highest defensive rebounding percentage (DRB / (ORB + DRB)) that averaged at least 8 rebounds per game?", "names", p_top(r("s.dreb", "s.oreb + s.dreb"), 3, f"{QUAL} and s.rpg >= 8"))
add(H, 28, "What is the name and total minutes played of the player with the most total minutes played in a season?", "lead", p_best("s.mins"))
add(H, 29, "What is the name and points per game of the player with the highest scoring average among those who played at least 82 games?", "lead", p_best("s.ppg", "s.gp >= 82"))
add(H, 30, "What is the name and effective field goal percentage (eFG%) of the player with the highest eFG% who played at least 75 games?", "lead", p_best(r("s.fgm + 0.5 * s.tpm", "s.fga"), "s.gp >= 75"))
add(H, 31, "Who are the top 3 players with the highest assist percentage (AST / (FGA + 0.44 * FTA + AST)) among players who averaged at least 5 assists per game?", "names", p_top(r("s.ast", "s.fga + 0.44 * s.fta + s.ast"), 3, f"{QUAL} and s.apg >= 5"))
add(H, 32, "What is the name and turnover percentage (TOV / (FGA + 0.44 * FTA + TOV)) of the player with the lowest turnover percentage among players who averaged at least 20 points per game?", "lead", p_best(r("s.tov", "s.fga + 0.44 * s.fta + s.tov"), f"{QUAL} and s.ppg >= 20", asc=True))
no(H, 33, "What is the name and career games played of the player with the most career games played?", "career")
no(H, 34, "Who played more games in their career,  Michael Jordan or LeBron James", "career")
add(H, 35, "Nba players to average 30+ points per game with 60+ fg% in a single season", "names", p_all(f"{QUAL} and s.ppg >= 30 and {r('s.fgm', 's.fga')} >= 0.6"))
no(H, 36, "Tim Duncan career average stats", "career")
no(H, 37, "Lebron James season stats for every season", "other seasons")
add(H, 38, "Chris Paul most assists averaged in a single season", "num", p_val("round(s.apg, 1)", "s.full_name = 'Chris Paul'"))
add(H, 39, "Chris Paul most total assists in a single season", "num", p_val("s.ast", "s.full_name = 'Chris Paul'"))
no(H, 40, "What player has the most seasons where they average 20+ points per game?", "other seasons")
no(H, 41, "Which player has the most seasons with at least 2 blocks per game?", "other seasons")
no(H, 42, "List the top 3 players with the highest career free throw percentage (minimum 100 free throw attempts)", "career")
add(H, 43, "Lebron James 3p%", "num", p_val(f"round((100 * {r('s.tpm', 's.tpa')})::numeric, 1)", "s.full_name = 'LeBron James'"))
no(H, 44, "Which player has the most career fouls that played less than 10 seasons?", "career")
no(H, 45, "Find the player with the highest career 3-point percentage who played at least 5 seasons", "career")
no(H, 46, "Find the player with the highest assist to turnover ratio who played at least 7 seasons", "career")
no(H, 47, "Find the player with the most career blocks who played fewer than 12 seasons", "career")
no(H, 48, "Find the player with the most career defensive rebounds who played fewer than 8 seasons", "career")
no(H, 49, "Find the player with the highest career effective field goal percentage who played at least 12 seasons", "career")
no(H, 50, "Which player has the most career points who played less than 10 seasons?", "career")

# ------------------------------------------------------------------ stathead: sample searches (non-college)
S = "stathead"
DIVISIONS = """(values ('BOS','A'),('BKN','A'),('NYK','A'),('PHI','A'),('TOR','A'),('CHI','C'),('CLE','C'),('DET','C'),('IND','C'),('MIL','C'),
 ('ATL','SE'),('CHA','SE'),('MIA','SE'),('ORL','SE'),('WAS','SE'),('DEN','NW'),('MIN','NW'),('OKC','NW'),('POR','NW'),('UTA','NW'),
 ('GSW','P'),('LAC','P'),('LAL','P'),('PHX','P'),('SAC','P'),('DAL','SW'),('HOU','SW'),('MEM','SW'),('NOP','SW'),('SAS','SW')) d(ab, division)"""
LAST_PLACE = f"""select ab from (select d.ab, rank() over (partition by d.division order by w.wins) rk from {DIVISIONS}
 join (select t.abbreviation ab, sum(g.won::int) wins from team_box_scores g join teams t on t.nba_team_id = g.nba_team_id group by 1) w on w.ab = d.ab) x where rk = 1"""
HALF = "(select nba_game_id, nba_team_id, sum(points) filter (where period <= {p}) pts from team_period_scores group by 1, 2)"

add(S, "Player Season Finder", "Most Points in a season", "lead", p_best("s.pts"))
no(S, "Player Season Finder", "Most 3-point FG made by a left-handed player in a season", "not stored: handedness")
no(S, "Player Season Finder", "At least 700 Points and 200 Rebounds in a season by a WNBA player", "WNBA")
no(S, "Player Season Finder", "Most Win Shares in a season by a guard in the ABA", "ABA")
add(S, "Player Season Finder", "Players with at least a 90% FT pct, 50% FG pct and 40% 3-point FG pct", "names", p_all(f"s.fgm >= 300 and s.tpm >= 82 and s.ftm >= 125 and {r('s.ftm', 's.fta')} >= 0.9 and {r('s.fgm', 's.fga')} >= 0.5 and {r('s.tpm', 's.tpa')} >= 0.4"))
add(S, "Player Season Finder", "Most Minutes Played in a season by a teenager", "lead", p_best("s.mins", f"{AGE} <= 19"))
no(S, "Player Season Finder", "Fewest Points per Game in MVP-winning season", "awards")
add(S, "Player Season Finder", "Most Assists in a season by a player 7’0” or taller", "lead", p_best("s.ast", f"{INCH} >= 84"))
no(S, "Player Season Finder", "Most Field Goal Attempts per Game in a single postseason (min. 3 games)", "playoffs")
no(S, "Player Season Finder", "Most minutes played in 2022-23 season by players taken after first round of 2022 Draft", "other seasons, draft")
no(S, "Player Season Finder", "Players with at least 10 PPG, 10 APG and 10 RPG in a single postseason", "playoffs")
add(S, "Player Season Finder", "Highest Points Per Game in a season by player on a last-place team", "lead",
    p_best("s.ppg", f"{QUAL} and (select t.abbreviation from player_season_stats ss join teams t on t.id = ss.team_id where ss.player_id = s.player_id limit 1) in ({LAST_PLACE})"))
no(S, "Player Season Finder", "Most win shares in a single season by a No. 1 overall pick", "draft")
no(S, "Player Season Finder (combined)", "Most Points Scored in a player’s first 3 seasons", "other seasons")
no(S, "Player Season Finder (combined)", "Most career Assists in ABA history", "ABA, career")
no(S, "Player Season Finder (combined)", "Most career Win Shares by a player born in Australia", "career, not stored: birthplace")
no(S, "Player Season Finder (combined)", "All players drafted from Indiana University, sorted by Field Goals Made", "draft, college")
no(S, "Player Season Finder (combined)", "Players with at least 20,000 career points and 10,000 career assists", "career")
no(S, "Player Season Finder (combined)", "Most career Minutes played in WNBA history", "WNBA")
no(S, "Player Season Finder (combined)", "Most career points scored by undrafted player", "career, draft")
no(S, "Player Season Finder (most seasons)", "Most seasons averaging 25 PPG and 10 APG", "other seasons")
no(S, "Player Season Finder (most seasons)", "Most seasons with at least 300 Assists by a player 7’0” or taller", "other seasons")
no(S, "Player Season Finder (most seasons)", "Most career All-Star selections", "awards")
add(S, "Player Season Finder (players in a season)", "Most qualifying players to average 20 PPG in a season", "num", p_val("count(*)", f"{QUAL} and s.ppg >= 20"))
add(S, "Player Season Finder (players in a season)", "Most players with at least 100 Steals in a season", "num", p_val("count(*)", "s.stl >= 100"))
no(S, "Player Season Finder (players in a season)", "Most players age 35 or older with at least 40 Games Started in a season", "not stored: games started")
no(S, "Player Season Finder (players on a team)", "Most (future) Hall of Famers on a team in a season", "awards")
add(S, "Player Season Finder (players on a team)", "Most qualified players to average at least 10 PPG on a team in a season", "lead",
    best("select t.full_name name, count(*) v from (select b.player_id, b.nba_team_id from player_box_scores b where b.minutes > 0 group by 1, 2 having count(*) >= 58 and avg(b.points) >= 10) x join teams t on t.nba_team_id = x.nba_team_id group by 1"))
no(S, "Player Season Finder (players on a team)", "Most players selected to All-Star team on a team in a season", "awards")
no(S, "Player Season Finder (players on a team)", "Teams in 2022-23 season that had the most former 1st round picks start 40+ games", "other seasons, draft")
no(S, "Player Season Finder (players for a team, careers)", "Teams with the most players with at least 500 career 3-point FG", "career")
no(S, "Player Season Finder (players for a team, careers)", "Teams with the most players with at least 50 career Win Shares", "career")
no(S, "Player Season Finder (players for a team, careers)", "Teams with the most players who went to Indiana", "college")
add(S, "Team Season Finder", "Highest Win-Loss Percentage in a season", "lead", t_best("avg(g.won::int)"))
no(S, "Team Season Finder", "Highest Average Margin of Victory in the Shot Clock Era", "history")
no(S, "Team Season Finder", "Highest Turnover Percentage by a team that made playoffs", "playoffs")
no(S, "Team Season Finder", "Highest 3-pt FG% by a WNBA team in a season", "WNBA")
no(S, "Team Season Finder", "Fewest Losses by a team in a single postseason", "playoffs")
no(S, "Team Season Finder", "Highest Win Percentage by a team that missed the playoffs", "playoffs")
no(S, "Team Season Finder (franchise)", "Most Postseason Wins for a franchise", "playoffs, history")
no(S, "Team Season Finder (franchise)", "Best Offensive Rating since the 2018-19 season", "other seasons")
no(S, "Team Season Finder (franchise)", "Most Losses for a franchise in WNBA history", "WNBA")
add(S, "Player Game Finder", "Most Points in a game with fewer than 20 minutes played", "lead", g_best("b.points", "b.minutes < 20"))
no(S, "Player Game Finder", "Highest Game Score in a game on the player’s birthday", "not stored: birthdays")
add(S, "Player Game Finder", "At least 50 Points and 25 Rebounds in a game", "names", f"select distinct p.full_name from {GAME} where b.points >= 50 and b.reb >= 25")
no(S, "Player Game Finder", "Most made Field Goals in Finals Game 7", "playoffs")
add(S, "Player Game Finder", "Most Assists in a Triple-Double", "lead", g_best("b.ast", TD))
no(S, "Player Game Finder", "Most Free Throw Attempts by a player that didn’t start the game", "not stored: starters")
add(S, "Player Game Finder", "At least 70 Points in a loss", "names", f"select distinct p.full_name from {GAME} where b.points >= 70 and not g.won")
add(S, "Player Game Finder", "Most Assists in a game by a Center", "lead", g_best("b.ast", "pp.position like 'Center%'"))
no(S, "Player Game Finder", "Worst Field Goal Pct in an overtime game in ABA (min. 20 att)", "ABA")
no(S, "Player Game Finder", "Most Turnovers in a game with 10+ Assists in WNBA history", "WNBA")
add(S, "Player Game Finder", "Most Field Goals in a game by a player on team that finished with win percentage below .400", "lead",
    g_best("b.fgm", "b.nba_team_id in (select nba_team_id from team_box_scores group by 1 having avg(won::int) < 0.4)"))
no(S, "Player Game Finder (season totals)", "Most total Points scored in a Conference Finals series", "playoffs")
add(S, "Player Game Finder (season totals)", "Most Field Goals made in the month of February in a season", "lead",
    best(f"select p.full_name name, sum(b.fgm) v from {GAME} where extract(month from b.game_date) = 2 group by p.id, p.full_name"))
add(S, "Player Game Finder (season totals)", "Most Overtime Games played in a season", "lead", g_count(OT))
no(S, "Player Game Finder (careers)", "Most 3-pt Field Goals made in a player’s first 100 career games", "career")
no(S, "Player Game Finder (careers)", "Most career Points scored by a player drafted in 2014", "career, draft")
no(S, "Player Game Finder (careers)", "Most Points scored against the Celtics since the 2016-17 season", "other seasons")
add(S, "Player Game Finder (games in a season)", "Most 50-point games in a season", "lead", g_count("b.points >= 50"))
add(S, "Player Game Finder (games in a season)", "Most Triple-Doubles in a season", "lead", g_count(TD))
add(S, "Player Game Finder (games in a season)", "Most games with at least 40 Minutes Played as a rookie", "lead", g_count(f"b.minutes >= 40 and {ROOKIE}"))
add(S, "Player Game Finder (games, careers)", "Most games with at least 30 Points as a teenager", "lead", g_count(f"b.points >= 30 and {AGE} <= 19"))
no(S, "Player Game Finder (games, careers)", "Most career games with at least 10 3-pt shots made", "career")
no(S, "Player Game Finder (games, careers)", "Most games with at least 10 Assists in a player’s first 100 career games", "career")
add(S, "Player Game Finder (team player games)", "Teams with the most games with a player scoring at least 20 Points in a season", "lead",
    best("select t.full_name name, count(*) v from player_box_scores b join teams t on t.nba_team_id = b.nba_team_id where b.points >= 20 group by 1"))
no(S, "Player Game Finder (team player games)", "Teams with the most games with a player having at least 20 Rebounds in a postseason", "playoffs")
add(S, "Player Game Finder (team player games)", "Teams with the most games with a rookie having at least 5 Blocks in a season", "lead",
    best(f"select t.full_name name, count(*) v from {GAME} where b.blk >= 5 and {ROOKIE} group by 1"))
no(S, "Player Game Finder (seasons)", "Seasons where the most players had a 50+ Point game", "other seasons")
no(S, "Player Game Finder (seasons)", "Seasons where the most players had a Triple-Double in a game", "other seasons")
no(S, "Player Game Finder (seasons)", "Seasons where the most players had at least 20 Points in a game on their birthday", "other seasons, not stored: birthdays")
add(S, "Player Game Finder (players on a team in a game)", "Most players with at least 40 Points in a game for a team", "lead",
    best(f"select t.full_name name, count(*) v from {GAME} where b.points >= 40 group by t.full_name, b.nba_game_id"))
no(S, "Player Game Finder (players on a team in a game)", "Most players with at least 10 Rebounds that didn’t start the game for a team", "not stored: starters")
add(S, "Player Game Finder (players on a team in a game)", "Most players under age 25 with a Double-Double for a team in a game", "lead",
    best(f"select t.full_name name, count(*) v from {GAME} where {DD} and {AGE} < 25 group by t.full_name, b.nba_game_id"))
no(S, "Team Game Finder", "Most Points in a game before the Shot Clock (pre 1953-54 season)", "history")
add(S, "Team Game Finder", "Biggest advantage in Free Throw Attempts in a game", "lead",
    best("select t.full_name name, g.fta - x.fta v from team_box_scores g join team_box_scores x on x.nba_game_id = g.nba_game_id and x.nba_team_id = g.opponent_nba_team_id join teams t on t.nba_team_id = g.nba_team_id"))
no(S, "Team Game Finder", "Worst regular-season loss by a team that won the championship", "playoffs")
add(S, "Team Game Finder", "Biggest win in an overtime game", "lead", best(f"select t.full_name name, g.points - g.opponent_points v from {TEAMS} where {OT}"))
no(S, "Team Game Finder", "Best True Shooting Percentage in an NBA Finals game", "playoffs")
no(S, "Team Game Finder", "Most turnovers in a regular season game by a team that lost in the Finals", "playoffs")
add(S, "Team Game Finder", "Teams that scored 50+ points in any quarter", "names",
    "select distinct t.full_name from team_period_scores q join teams t on t.nba_team_id = q.nba_team_id where q.period <= 4 and q.points >= 50")
add(S, "Team Game Finder", "Teams that led by 35+ points at halftime", "names",
    f"select distinct t.full_name from {HALF.format(p=2)} a join {HALF.format(p=2)} b on b.nba_game_id = a.nba_game_id and b.nba_team_id <> a.nba_team_id join teams t on t.nba_team_id = a.nba_team_id where a.pts - b.pts >= 35")
add(S, "Team Game Finder", "Teams to overcome a deficit of 25+ points at the start of 4th quarter and win", "names",
    f"select distinct t.full_name from {HALF.format(p=3)} a join {HALF.format(p=3)} b on b.nba_game_id = a.nba_game_id and b.nba_team_id <> a.nba_team_id join team_box_scores g on g.nba_game_id = a.nba_game_id and g.nba_team_id = a.nba_team_id join teams t on t.nba_team_id = a.nba_team_id where b.pts - a.pts >= 25 and g.won")
no(S, "Team Game Finder (season totals)", "Worst home Win Percentage by a team that made the playoffs", "playoffs")
add(S, "Team Game Finder (season totals)", "Best Point Differential in road games in a season", "lead", t_best("sum(g.points - g.opponent_points)", "not g.is_home"))
no(S, "Team Game Finder (season totals)", "Most Field Goal Attempts in a Conference Finals", "playoffs")
no(S, "Team Game Finder (franchise)", "Best Win Percentage in Road Overtime games by a franchise", "history")
no(S, "Team Game Finder (franchise)", "Most Wins by a WNBA team since 2010", "WNBA")
no(S, "Team Game Finder (franchise)", "Highest 3-pt FG percentage by a franchise", "history")
add(S, "Team Game Finder (games in a season)", "Most Games with at least 100 Points Allowed in a season", "lead", t_best("sum((g.opponent_points >= 100)::int)"))
add(S, "Team Game Finder (games in a season)", "Most Losses by at least 20 Points in a season", "lead", t_best("sum((g.opponent_points - g.points >= 20)::int)"))
add(S, "Team Game Finder (games in a season)", "Most Overtime Games played in a season", "lead", t_best(f"sum(({OT})::int)"))
no(S, "Team Game Finder (games in a season)", "Team W-L when trailing at the start of the 4th quarter in 2022-23", "other seasons")
no(S, "Team Game Finder (games in a season)", "Teams with the most losses when leading by 10+ at end of the first quarter in 2021-22", "other seasons")
no(S, "Team Game Finder (franchise games)", "Most Playoff games as a No. 1 seed since the 1976-77 merger", "playoffs, history")
no(S, "Team Game Finder (franchise games)", "Most games with at least 20 3-pt FG made by a franchise", "history")
no(S, "Team Game Finder (franchise games)", "Most season-opening losses by a franchise", "history")
no(S, "Team Game Finder (seasons)", "Seasons with the most games decided by at least 20 points", "other seasons")
no(S, "Team Game Finder (seasons)", "Seasons with the most team games with at least 30 Free Throw Attempts", "other seasons")
no(S, "Team Game Finder (seasons)", "Seasons with the most games played on Sundays", "other seasons")
add(S, "Versus Finder", "Kevin Durant vs. Ja Morant", "judge")
add(S, "Versus Finder", "Jimmy Butler vs. LeBron James", "judge")
no(S, "Versus Finder", "Magic Johnson vs. Michael Jordan", "history")
no(S, "Versus Finder", "Seimone Augustus vs. Tina Thompson", "WNBA")
no(S, "Versus Finder", "Angel McCoughtry vs. Nneka Ogwumike", "WNBA")
add(S, "Versus Finder", "Giannis Antetokounmpo vs. Houston Rockets", "num", versus("Giannis Antetokounmpo", "Rockets"))
add(S, "Versus Finder", "Stephen Curry vs. Phoenix Suns", "num", versus("Stephen Curry", "Suns"))
add(S, "Versus Finder", "James Harden vs. Denver Nuggets", "num", versus("James Harden", "Nuggets"))
no(S, "Versus Finder", "Larry Bird vs. New Jersey Nets", "history")
no(S, "Versus Finder", "Diana Taurasi vs. Seattle Storm", "WNBA")
add(S, "Versus Finder", "Cleveland Cavaliers vs. Detroit Pistons", "text", record("Cavaliers", "Pistons"))
add(S, "Versus Finder", "Denver Nuggets vs. Utah Jazz", "text", record("Nuggets", "Jazz"))
add(S, "Versus Finder", "Brooklyn Nets vs. Toronto Raptors", "text", record("Nets", "Raptors"))
add(S, "Versus Finder", "Boston Celtics vs. Miami Heat", "text", record("Celtics", "Heat"))
no(S, "Versus Finder", "Connecticut Sun vs. Las Vegas Aces", "WNBA")
add(S, "Streak Finder", "Most consecutive games with at least 20 Points", "lead", p_streak("b.points >= 20"))
add(S, "Streak Finder", "Most consecutive games with a Triple-Double", "lead", p_streak(TD))
add(S, "Streak Finder", "Most consecutive home games with a field goal percentage of 50% or higher", "lead", p_streak("b.fga > 0 and b.fgm::float / b.fga >= 0.5", "g.is_home"))
add(S, "Streak Finder", "Most consecutive games to start a season with at least 1 Block", "lead",
    best("select p.full_name name, coalesce(min(rn) filter (where blk = 0) - 1, count(*)) v from (select player_id, blk, row_number() over (partition by player_id order by game_date) rn from player_box_scores where minutes > 0) x join players p on p.id = x.player_id group by p.full_name"))
no(S, "Streak Finder", "Most consecutive game to start a career with at least 30 Minutes Played", "career")
add(S, "Streak Finder (team)", "Longest streak of games with at least 120 Points Scored", "lead", t_streak("g.points >= 120"))
add(S, "Streak Finder (team)", "Most consecutive home wins by at least 10 Points", "lead", t_streak("g.points - g.opponent_points >= 10", "g.is_home"))
no(S, "Streak Finder (team)", "Longest losing streak by a team that went on to win the Championship", "playoffs")
add(S, "Streak Finder (team)", "Most consecutive games with at least 20 3-point field goals and 20 free throws made", "lead", t_streak("g.tpm >= 20 and g.ftm >= 20"))
no(S, "Streak Finder (team)", "Longest win streak to start a season in WNBA History", "WNBA")
no(S, "Span Finder", "Most Double-Doubles in first 20 games of a career", "career")
add(S, "Span Finder", "Most Assists in any 5-game span by a teenager", "lead",
    best(f"select name, s5 v from (select p.full_name name, sum(b.ast) over w s5, count(*) over w n from {GAME} where b.minutes > 0 and {AGE} <= 19 window w as (partition by b.player_id order by b.game_date rows between 4 preceding and current row)) x where n = 5"))
no(S, "Span Finder", "Most 3-point Field Goals made in first 10 games with a franchise", "career")
no(S, "Span Finder", "Most Points in a 5-game span in WNBA History", "WNBA")
add(S, "Span Finder", "At least 50 Points and 50 Rebounds in any 2-gam span", "names",
    f"select distinct name from (select p.full_name name, sum(b.points) over w pts, sum(b.reb) over w reb, count(*) over w n from {GAME} where b.minutes > 0 window w as (partition by b.player_id order by b.game_date rows between 1 preceding and current row)) x where n = 2 and pts >= 50 and reb >= 50")
add(S, "Span Finder (team)", "Most Wins in first 25 games of a season", "lead",
    best("select t.full_name name, sum(won::int) v from (select nba_team_id, won, row_number() over (partition by nba_team_id order by game_date) rn from team_box_scores) x join teams t on t.nba_team_id = x.nba_team_id where rn <= 25 group by 1"))
no(S, "Span Finder (team)", "Worst 30-game Win Percentage by a team that made playoffs since 1976-77 merger", "playoffs, history")
add(S, "Span Finder (team)", "Biggest Point Differential in any 3-game span", "lead",
    best("select name, d v from (select t.full_name name, sum(g.points - g.opponent_points) over w d, count(*) over w n from team_box_scores g join teams t on t.nba_team_id = g.nba_team_id window w as (partition by g.nba_team_id order by g.game_date rows between 2 preceding and current row)) x where n = 3"))
no(S, "Span Finder (team)", "Most Points in any 5-game span in ABA History", "ABA")
add(S, "Span Finder (team)", "Teams to end the season on a win streak of at least 10 games", "names",
    "select t.full_name from (select nba_team_id, max(game_date) filter (where not won) last_loss from team_box_scores group by 1) l join teams t on t.nba_team_id = l.nba_team_id where (select count(*) from team_box_scores g where g.nba_team_id = l.nba_team_id and g.game_date > coalesce(l.last_loss, '1900-01-01')) >= 10")
no(S, "Quarter Finder", "Most Points Scored in any single quarter", "not stored: player points by quarter")
no(S, "Quarter Finder", "Most total Free Throws made in the 4th quarter in 2021-22 season", "other seasons")
no(S, "Quarter Finder", "Most quarters with 20+ points in a single season", "not stored: player points by quarter")
no(S, "Quarter Finder", "Players with 10+ points and 10+ rebounds in a quarter", "not stored: player points by quarter")
add(S, "Quarter Finder", "Most Field Goal Attempts in an OT period", "lead",
    best("select p.full_name name, count(*) v from shot_charts c join players p on p.id = c.player_id where c.period >= 5 group by p.full_name, c.nba_game_id, c.period"))
add(S, "Shot Finder", "Most Dunks made in a season", "lead",
    best("select p.full_name name, count(*) v from shot_charts c join players p on p.id = c.player_id where c.action_type ilike '%dunk%' and c.shot_made group by p.full_name"))
no(S, "Shot Finder", "Most Field Goals made in clutch time (4Q/OT, < 5 minutes left, scoring margin between -5 and +5) in a season", "not stored: score at a moment")
no(S, "Shot Finder", "Worst FG% on shots 5 ft or closer in 2021-22 season (min. 50 attempts)", "other seasons")
add(S, "Shot Finder", "All Shots Made from 60 ft or further", "names",
    "select distinct p.full_name from shot_charts c join players p on p.id = c.player_id where c.shot_distance >= 60 and c.shot_made")
no(S, "Shot Finder", "Most Shots Made to take lead in 4th quarter with less than 1 minute left in a season", "not stored: score at a moment")

# ------------------------------------------------------------------ scout: scouting guides
C = "scout"
SUBJECTS = ["DeMar DeRozan", "Josh Hart", "Jake LaRavia", "Amen Thompson", "Franz Wagner", "Evan Mobley", "AJ Green", "Isaiah Collier", "Jordan Poole", "De'Aaron Fox",
            "Nic Claxton", "Caris LeVert", "Deni Avdija", "Royce O'Neale", "Kris Dunn", "Dorian Finney-Smith", "Terance Mann", "Goga Bitadze", "Bam Adebayo", "Davion Mitchell",
            "Fred VanVleet", "Kel'el Ware", "Dillon Brooks", "Corey Kispert", "Pascal Siakam", "Andrew Wiggins", "LeBron James", "Donte DiVincenzo", "Darius Garland", "Jamal Murray",
            "Desmond Bane", "Kentavious Caldwell-Pope", "Santi Aldama", "Kevin Huerter", "Kyshawn George", "Kyle Filipowski", "Derrick White", "Jaylen Wells", "Zaccharie Risacher", "Scotty Pippen Jr.",
            "Keldon Johnson", "Dyson Daniels", "Stephen Curry", "Klay Thompson", "Miles Bridges", "Duncan Robinson", "Jalen Duren", "Donovan Mitchell", "Zach Edey", "Isaiah Joe", "Nikola Jokić"]
_who = iter(SUBJECTS)


def scout(ref, original, check, template, reason=None):
    add(C, ref, original, check, text=template.format(next(_who)), reason=reason)


AU, BB, NC = "basketball.com.au", "betterbasketball.com", "noceilingsnba.com"
scout(AU, "How does this player stack up against others at the same position or level?", "judge", "How does {} stack up against others at the same position or level?")
scout(AU, "Are they a standout or system-dependent?", "judge", "Is {} a standout or system-dependent?")
scout(AU, "What's their maximum potential, and what's their worst-case trajectory?", "decline", "What's {}'s maximum potential, and what's his worst-case trajectory?", "future")
scout(AU, "Could this player thrive in an up-tempo system?", "judge", "Could {} thrive in an up-tempo system?")
scout(AU, "Do they need shooters around them?", "judge", "Does {} need shooters around him?")
scout(AU, "Can they guard multiple positions?", "judge", "Can {} guard multiple positions?")
scout(AU, "Play multiple roles?", "judge", "Can {} play multiple roles?")
for q, t in [
    ("What was your very first impression of him?", "What was your very first impression of {}?"),
    ("Did you see any red flags?", "Did you see any red flags with {}?"),
    ("Did you enjoy being around him?", "Did you enjoy being around {}?"),
    ("Was he always on time?", "Was {} always on time?"),
    ("Was he likable?", "Was {} likable?"),
    ("Was he coachable?", "Was {} coachable?"),
    ("Was he an energy giver?", "Was {} an energy giver?"),
    ("Did he love to play?", "Did {} love to play?"),
    ("Did he love to workout?", "Did {} love to workout?"),
    ("How was his attitude?", "How was {}'s attitude?"),
    ("How was his work ethic?", "How was {}'s work ethic?"),
    ("Was he a gym rat?", "Was {} a gym rat?"),
    ("What was the best part about working with him?", "What was the best part about working with {}?"),
    ("Was there anything difficult about working with him?", "Was there anything difficult about working with {}?"),
    ("Was he respectful?", "Was {} respectful?"),
    ("Was he self-motivated?", "Was {} self-motivated?"),
    ("Did he act entitled?", "Did {} act entitled?"),
    ("Was he selfish?", "Was {} selfish?"),
    ("Was he mature?", "Was {} mature?"),
    ("Was he competitive?", "Was {} competitive?"),
    ("Was he a leader?", "Was {} a leader?"),
    ("Would you let your daughter marry him?", "Would you let your daughter marry {}?"),
]:
    scout(BB, q, "decline", t, "character, from people who worked with him")
for q, check, t, why in [
    ("Does that player look bigger in person compared to tape?", "decline", "Does {} look bigger in person compared to tape?", "seen in person"),
    ("Does he look like he's going to have a plus wingspan?", "decline", "Does {} look like he's going to have a plus wingspan?", "not stored: wingspan"),
    ("Does he move more fluidly on the court in-person compared to the player you've been fascinating over on tape?", "decline", "Does {} move more fluidly on the court in-person compared to the player you've been fascinating over on tape?", "seen in person"),
    ("How does he look in warm-ups?", "decline", "How does {} look in warm-ups?", "seen in person"),
    ("Are they working on game shots?", "decline", "Is {} working on game shots?", "seen in person"),
    ("Is there a specific process in their pre-game routine?", "decline", "Is there a specific process in {}'s pre-game routine?", "seen in person"),
    ("Where did they develop?", "decline", "Where did {} develop?", "not stored: background"),
    ("If they weren't shooting the ball well at the beginning of the year, what changed?", "judge", "If {} wasn't shooting the ball well at the beginning of the year, what changed?", None),
    ("Does it look like his form has improved, and could he have potentially been putting in extra practice reps to work on his shot?", "decline", "Does it look like {}'s form has improved, and could he have potentially been putting in extra practice reps to work on his shot?", "seen in person"),
    ("Is he impacting the game in other ways?", "judge", "Is {} impacting the game in other ways?", None),
    ("Is he stepping up his ability on the defensive side of the ball?", "judge", "Is {} stepping up his ability on the defensive side of the ball?", None),
    ("Is he realizing that his outside shot isn't falling so he's making an effort to get to the basket and create free-throw opportunities?", "judge", "Is {} realizing that his outside shot isn't falling so he's making an effort to get to the basket and create free-throw opportunities?", None),
    ("Is he working to put his teammates in position to succeed instead by using his playmaking ability?", "judge", "Is {} working to put his teammates in position to succeed instead by using his playmaking ability?", None),
    ("Is he sulking and depressed because he can't find a rhythm when it comes to his shooting?", "decline", "Is {} sulking and depressed because he can't find a rhythm when it comes to his shooting?", "mood"),
    ("Is he engaged when he's on the bench and still attentive towards helping his team in a hostile environment?", "decline", "Is {} engaged when he's on the bench and still attentive towards helping his team in a hostile environment?", "seen in person"),
    ("If that player was a poker player, what is the best hand they could play?", "judge", "If {} was a poker player, what is the best hand he could play?", None),
    ("Why is a potential NBA organization going to invest a draft selection in their ability on the basketball court?", "decline", "Why is a potential NBA organization going to invest a draft selection in {}'s ability on the basketball court?", "draft"),
    ("If a player projects to be a \"3-and-D\" type of asset, has he proven himself in both of those areas?", "judge", "If {} projects to be a \"3-and-D\" type of asset, has he proven himself in both of those areas?", None),
    ("Is that \"strength\" something that can get him early minutes in a rotation or are his weaknesses glaring enough that he will need to limit them before he sees the floor?", "decline", "Is {}'s \"strength\" something that can get him early minutes in a rotation or are his weaknesses glaring enough that he will need to limit them before he sees the floor?", "future"),
    ("Has that prospect shown the tools to impact a number of different areas when his team has needed him to?", "judge", "Has {} shown the tools to impact a number of different areas when his team has needed him to?", None),
    ("If he's made a reputation for being a floor spacer, does he also have the ability to put the ball on the floor and create in traffic?", "judge", "If {} has made a reputation for being a floor spacer, does he also have the ability to put the ball on the floor and create in traffic?", None),
    ("If defenses are creeping up on him, does he have the awareness to suddenly turn into a playmaking asset for his team?", "judge", "If defenses are creeping up on {}, does he have the awareness to suddenly turn into a playmaking asset for his team?", None),
]:
    scout(NC, q, check, t, why)

# Questions on noceilingsnba.com not used: addressed to the reader, rhetorical, quoted inside a sentence,
# or a follow-on that only makes sense after the previous question.
SCOUT_EXCLUDED = [
    "Why you might ask?",
    "Or has his cold shooting night just completely taken him out of the game?",
    "Or are we simply just suggesting that he could become that?",
    "But what if that player has the ability to adapt to his surroundings?",
    "What if a certain player has the tools to adjust to whatever his next team needs him to be?",
    "could he give Chet Holmgren a run for the first overall selection?",
    "Wow, you're probably talking about the jump in rebounding?",
    "Think Jaden Ivey is the best prospect in this Draft?",
    "Not sold on Johnny Davis becoming a Top-5 selection?",
]
