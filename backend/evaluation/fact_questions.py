"""Factual questions over every page, with the expected answer computed by SQL on raw tables.

check "num":   the answer contains this number (tolerance 0.06 when it has decimals)
check "lead":  this is the first player or team the answer names
check "names": every one of these names is in the answer
check "text":  the answer contains this text
"""

F = []


def ask(split, page, text, check, sql):
    F.append({"id": len(F) + 1, "split": split, "page": page, "text": text, "check": check, "sql": sql})


BOX = "from player_box_scores b join players p on p.id = b.player_id join teams o on o.nba_team_id = (select opponent_nba_team_id from team_box_scores x where x.nba_game_id = b.nba_game_id and x.nba_team_id = b.nba_team_id) join team_box_scores g on g.nba_game_id = b.nba_game_id and g.nba_team_id = b.nba_team_id join teams t on t.nba_team_id = b.nba_team_id"
TEAM = "from team_box_scores g join teams t on t.nba_team_id = g.nba_team_id join teams o on o.nba_team_id = g.opponent_nba_team_id join team_box_scores a on a.nba_game_id = g.nba_game_id and a.nba_team_id = g.opponent_nba_team_id"
ADV = "from player_advanced_stats a join players p on p.id = a.player_id join (select player_id, count(*) as gp, sum(minutes) as mins, avg(minutes) as mpg, sum(fga) as fga, sum(tpa) as tpa, sum(fta) as fta, sum(tpm) as tpm, sum(ftm) as ftm, sum(points) as pts from player_box_scores group by 1) s on s.player_id = a.player_id left join player_profiles pp on pp.player_id = a.player_id left join player_season_stats ss on ss.player_id = a.player_id left join teams t on t.id = ss.team_id"
ROT = "s.gp >= 20 and s.mpg >= 12"


def one(expr, player, where="true"):
    return f"select {expr} {BOX} where p.full_name = '{player}' and {where}"


def team(expr, nick, where="true"):
    return f"select {expr} {TEAM} where t.nickname = '{nick}' and {where}"


def best_team(expr, where="true", order="desc"):
    return f"select t.full_name {TEAM} where {where} group by t.full_name order by {expr} {order} limit 1"


def best_player(expr, where="true", having="count(*) >= 20", order="desc"):
    return f"select p.full_name {BOX} where {where} group by p.id, p.full_name having {having} order by {expr} {order} limit 1"


def adv(order, where=ROT):
    return f"select p.full_name {ADV} where {where} order by {order} limit 1"


POSS, OPOSS = "sum(g.fga + 0.44*g.fta - g.oreb + g.tov)", "sum(a.fga + 0.44*a.fta - a.oreb + a.tov)"
INCH = "(split_part(pp.height,'-',1)::int*12 + split_part(pp.height,'-',2)::int)"
GMSC = "(b.points + 0.4*b.fgm - 0.7*b.fga - 0.4*(b.fta-b.ftm) + 0.7*b.oreb + 0.3*b.dreb + b.stl + 0.7*b.ast + 0.7*b.blk - 0.4*b.pf - b.tov)"
WIN = "sum(g.won::int)"
STREAK = "select max(c) from (select count(*) c from (select won, row_number() over (order by game_date, nba_game_id) - row_number() over (partition by won order by game_date, nba_game_id) as grp from team_box_scores g join teams t on t.nba_team_id = g.nba_team_id where t.nickname = '{nick}') x where {won} group by grp) y"

# ------------------------------------------------------------------ development
ask("dev", "player", "How many points per game did Anthony Edwards average?", "num", one("round(avg(b.points),1)", "Anthony Edwards"))
ask("dev", "player", "How many 30-point games did LeBron James have?", "num", one("count(*)", "LeBron James", "b.points >= 30"))
ask("dev", "player", "What was Jalen Brunson's season high in points?", "num", one("max(b.points)", "Jalen Brunson"))
ask("dev", "player", "What did Nikola Jokic average against the Lakers?", "num", one("round(avg(b.points),1)", "Nikola Jokić", "o.nickname='Lakers'"))
ask("dev", "player", "How many triple-doubles did Nikola Jokic have?", "num", one("count(*)", "Nikola Jokić", "((b.points>=10)::int+(b.reb>=10)::int+(b.ast>=10)::int+(b.stl>=10)::int+(b.blk>=10)::int)>=3"))
ask("dev", "player", "How tall is Victor Wembanyama?", "text", "select replace(height,'-','''') from player_profiles pp join players p on p.id=pp.player_id where p.full_name='Victor Wembanyama'")
ask("dev", "player", "How many points did Stephen Curry average at home?", "num", one("round(avg(b.points),1)", "Stephen Curry", "g.is_home"))
ask("dev", "player", "Jayson Tatum's rebounds per game in January", "num", one("round(avg(b.reb),1)", "Jayson Tatum", "extract(month from b.game_date)=1"))
ask("dev", "player", "How many points did Tyrese Maxey score in his last 5 games in total?", "num", "select sum(points) from (select b.points from player_box_scores b join players p on p.id=b.player_id where p.full_name='Tyrese Maxey' order by b.game_date desc limit 5) x")
ask("dev", "player", "What is Rudy Gobert's usage rate?", "num", "select round((a.usg_pct*100)::numeric,1) from player_advanced_stats a join players p on p.id=a.player_id where p.full_name='Rudy Gobert'")
ask("dev", "top", "Who made the most three-pointers this season?", "lead", best_player("sum(b.tpm)"))
ask("dev", "top", "Which player has the highest true shooting percentage?", "lead", adv("s.pts/(2*(s.fga+0.44*s.fta)) desc", "s.fga>=200"))
ask("dev", "top", "Who had the most double-doubles?", "lead", best_player("sum((((b.points>=10)::int+(b.reb>=10)::int+(b.ast>=10)::int+(b.stl>=10)::int+(b.blk>=10)::int)>=2)::int)"))
ask("dev", "top", "Who scored the most points in a single game?", "lead", "select p.full_name from player_box_scores b join players p on p.id=b.player_id order by b.points desc limit 1")
ask("dev", "top", "Who has the best assist to turnover ratio?", "lead", adv("a.ast_to desc", "s.mins>=500"))
ask("dev", "top", "Which player had the most games with at least 40 points?", "lead", best_player("count(*)", "b.points>=40", "true"))
ask("dev", "top", "Who is the tallest player?", "num", "select max(" + INCH + ")/12 from player_profiles pp join player_season_stats s using (player_id)")
ask("dev", "young", "Best scorer aged 20 or younger", "lead", adv("ss.points desc", "a.season_age<=20 and " + ROT))
ask("dev", "teams", "What is the Knicks' record on the road?", "text", team("sum(g.won::int)||'-'||sum((not g.won)::int)", "Knicks", "not g.is_home"))
ask("dev", "teams", "Which team allowed the fewest points per game?", "lead", best_team("avg(a.points)", order="asc"))
ask("dev", "teams", "Who finished first in the West?", "lead", best_team(WIN, "t.abbreviation in ('DAL','DEN','GSW','HOU','LAC','LAL','MEM','MIN','NOP','OKC','PHX','POR','SAC','SAS','UTA')"))
ask("dev", "teams", "How many games did the Pistons win?", "num", team(WIN, "Pistons"))
ask("dev", "teams", "What was Miami's pace?", "num", "select round((48*avg(poss)/(avg(mins)/5))::numeric,1) from (select ((g.fga+0.44*g.fta-g.oreb+g.tov)+(a.fga+0.44*a.fta-a.oreb+a.tov))/2 as poss, g.minutes as mins " + TEAM + " where t.nickname='Heat') x")
ask("dev", "teams", "Which team had the best record in close games?", "lead", best_team("avg(g.won::int)", "abs(g.points-g.opponent_points)<=5"))
ask("dev", "teams", "What was the longest winning streak of the Cavaliers?", "num", STREAK.format(nick="Cavaliers", won="won"))
ask("dev", "games", "What was the highest scoring game by a team?", "lead", f"select t.full_name {TEAM} order by g.points desc limit 1")
ask("dev", "games", "How many games went to overtime?", "num", "select count(distinct nba_game_id) from team_period_scores where period=5")
ask("dev", "games", "What was the biggest win of the season?", "lead", f"select t.full_name {TEAM} order by g.points-g.opponent_points desc limit 1")
ask("dev", "games", "How many times did the Celtics beat the Knicks?", "num", team(WIN, "Celtics", "o.nickname='Knicks'"))
ask("dev", "games", "Which team scores the most points in the fourth quarter?", "lead", "select t.full_name from team_period_scores q join teams t on t.nba_team_id=q.nba_team_id where period=4 group by 1 order by avg(points) desc limit 1")
ask("dev", "shots", "How many dunks did Giannis Antetokounmpo make?", "num", "select sum(shot_made::int) from shot_charts s join players p on p.id=s.player_id where p.full_name='Giannis Antetokounmpo' and action_type ilike '%dunk%'")
ask("dev", "shots", "Who made the most corner threes?", "lead", "select p.full_name from shot_charts s join players p on p.id=s.player_id where shot_type like '3%' and loc_y<=89 and abs(loc_x)>=200 group by 1 order by sum(shot_made::int) desc limit 1")
ask("dev", "shots", "How many step-back shots did Luka Doncic take?", "num", "select count(*) from shot_charts s join players p on p.id=s.player_id where p.full_name='Luka Dončić' and action_type ilike '%step back%'")
ask("dev", "pairs", "What is the net rating of Jayson Tatum and Jaylen Brown together?", "num", "select round(net_rating::numeric,1) from player_pairs x join players a on a.id=x.player_a join players b on b.id=x.player_b where (a.full_name,b.full_name) in (('Jayson Tatum','Jaylen Brown'),('Jaylen Brown','Jayson Tatum'))")
ask("dev", "matchup", "How many points did Devin Booker score when guarded by Luguentz Dort?", "num", "select round(points::numeric,0) from player_matchups m join players a on a.id=m.off_player_id join players b on b.id=m.def_player_id where a.full_name='Devin Booker' and b.full_name='Luguentz Dort'")
ask("dev", "compare", "Who averages more assists, Trae Young or James Harden?", "lead", best_player("avg(b.ast)", "p.full_name in ('Trae Young','James Harden')"))
ask("dev", "compare", "Who shoots better from three, Klay Thompson or Buddy Hield?", "lead", best_player("sum(b.tpm)::float/sum(b.tpa)", "p.full_name in ('Klay Thompson','Buddy Hield')"))
ask("dev", "team", "Who is the leading scorer of the Hornets?", "lead", adv("ss.points desc", "t.nickname='Hornets' and s.gp>=20"))
ask("dev", "team", "How many players on the Spurs averaged 10 or more points?", "num", f"select count(*) {ADV} where t.nickname='Spurs' and ss.points>=10 and s.gp>=10 and s.mpg>=8")
ask("dev", "league", "What is the league average for three-point percentage?", "num", "select round((100.0*sum(tpm)/sum(tpa))::numeric,1) from team_box_scores")

# ------------------------------------------------------------------ held-out test
ask("test", "player", "What is Donovan Mitchell's scoring average?", "num", one("round(avg(b.points),1)", "Donovan Mitchell"))
ask("test", "player", "How many times did Kevin Durant score 35 or more?", "num", one("count(*)", "Kevin Durant", "b.points>=35"))
ask("test", "player", "Most assists in a game by Tyrese Haliburton", "num", one("max(b.ast)", "Tyrese Haliburton"))
ask("test", "player", "How did Paolo Banchero shoot from three?", "num", one("round(100.0*sum(b.tpm)/sum(b.tpa),1)", "Paolo Banchero"))
ask("test", "player", "How many minutes does Mikal Bridges play per game?", "num", one("round(avg(b.minutes),1)", "Mikal Bridges"))
ask("test", "player", "Total rebounds of Domantas Sabonis this season", "num", one("sum(b.reb)", "Domantas Sabonis"))
ask("test", "player", "How many points did Shai Gilgeous-Alexander average on the road?", "num", one("round(avg(b.points),1)", "Shai Gilgeous-Alexander", "not g.is_home"))
ask("test", "player", "Damian Lillard's scoring in February", "num", one("round(avg(b.points),1)", "Damian Lillard", "extract(month from b.game_date)=2"))
ask("test", "player", "What does Anthony Davis average in rebounds when his team wins?", "num", one("round(avg(b.reb),1)", "Anthony Davis", "g.won"))
ask("test", "player", "How many games did Ja Morant play?", "num", one("count(*)", "Ja Morant"))
ask("test", "player", "What is Evan Mobley's defensive rating?", "num", "select round(a.def_rating::numeric,1) from player_advanced_stats a join players p on p.id=a.player_id where p.full_name='Evan Mobley'")
ask("test", "player", "How old is Scottie Barnes?", "num", "select season_age from player_advanced_stats a join players p on p.id=a.player_id where p.full_name='Scottie Barnes'")
ask("test", "player", "How much does Zion Williamson weigh?", "num", "select weight::int from player_profiles pp join players p on p.id=pp.player_id where p.full_name='Zion Williamson'")
ask("test", "player", "Franz Wagner points per game against Boston", "num", one("round(avg(b.points),1)", "Franz Wagner", "o.nickname='Celtics'"))
ask("test", "player", "How many double-doubles did Karl-Anthony Towns record?", "num", one("count(*)", "Karl-Anthony Towns", "((b.points>=10)::int+(b.reb>=10)::int+(b.ast>=10)::int+(b.stl>=10)::int+(b.blk>=10)::int)>=2"))
ask("test", "player", "Bam Adebayo average points over the last 15 games", "num", "select round(avg(points),1) from (select b.points from player_box_scores b join players p on p.id=b.player_id where p.full_name='Bam Adebayo' order by b.game_date desc limit 15) x")
ask("test", "player", "What is Jimmy Butler's plus-minus per game?", "num", one("round(avg(b.plus_minus),1)", "Jimmy Butler III"))
ask("test", "player", "Where does Cade Cunningham rank in assists per game?", "num", "select rk from (select p.full_name, rank() over (order by avg(b.ast) desc) rk from player_box_scores b join players p on p.id=b.player_id group by p.id,p.full_name having count(*)>=20 and avg(b.minutes)>=12) x where full_name='Cade Cunningham'")
ask("test", "top", "Who grabbed the most offensive rebounds per game?", "lead", best_player("avg(b.oreb)", having="count(*)>=20 and avg(b.minutes)>=12"))
ask("test", "top", "Best free throw shooter in the league", "lead", best_player("sum(b.ftm)::float/sum(b.fta)", having="sum(b.fta)>=75"))
ask("test", "top", "Who commits the most fouls per game?", "lead", best_player("avg(b.pf)", having="count(*)>=20 and avg(b.minutes)>=12"))
ask("test", "top", "Which player has the highest usage rate?", "lead", adv("a.usg_pct desc", "s.mins>=500"))
ask("test", "top", "Highest net rating in the league", "lead", adv("a.net_rating desc", "s.mins>=500"))
ask("test", "top", "Who had the most rebounds in one game?", "lead", "select p.full_name from player_box_scores b join players p on p.id=b.player_id order by b.reb desc limit 1")
ask("test", "top", "Who played the most total minutes?", "lead", best_player("sum(b.minutes)"))
ask("test", "top", "Most 20 point 10 rebound games", "lead", best_player("count(*)", "b.points>=20 and b.reb>=10", "true"))
ask("test", "top", "Who was the best performer by game score in a single game?", "lead", f"select p.full_name from player_box_scores b join players p on p.id=b.player_id order by {GMSC} desc limit 1")
ask("test", "top", "Best effective field goal percentage among guards", "lead", adv("a.efg_pct desc", "s.fga>=200 and pp.position like '%Guard%'"))
ask("test", "top", "Who scores the most at home?", "lead", best_player("avg(b.points)", "g.is_home", "count(*)>=10"))
ask("test", "young", "Which player under 22 averages the most rebounds?", "lead", adv("ss.rebounds desc", "a.season_age<22 and " + ROT))
ask("test", "young", "Oldest player in the league", "lead", "select p.full_name from player_advanced_stats a join players p on p.id=a.player_id order by season_age desc, p.id limit 1")
ask("test", "teams", "What was the Warriors' home record?", "text", team("sum(g.won::int)||'-'||sum((not g.won)::int)", "Warriors", "g.is_home"))
ask("test", "teams", "How many games did Utah lose?", "num", team("sum((not g.won)::int)", "Jazz"))
ask("test", "teams", "Which team grabs the most rebounds?", "lead", best_team("avg(g.reb)"))
ask("test", "teams", "Which team plays at the fastest pace?", "lead", best_team(f"({POSS}+{OPOSS})/sum(g.minutes)"))
ask("test", "teams", "Which team has the best net rating?", "lead", best_team(f"sum(g.points)/{POSS} - sum(a.points)/{OPOSS}"))
ask("test", "teams", "Which team forces the most turnovers?", "lead", best_team(f"sum(a.tov)/{OPOSS}"))
ask("test", "teams", "Grizzlies points per game", "num", team("round(avg(g.points),1)", "Grizzlies"))
ask("test", "teams", "What place did the Bulls finish in the East?", "num", "select rk from (select t.nickname, row_number() over (order by sum(g.won::int) desc, avg(g.points-g.opponent_points) desc) rk " + TEAM + " where t.abbreviation in ('ATL','BOS','BKN','CHA','CHI','CLE','DET','IND','MIA','MIL','NYK','ORL','PHI','TOR','WAS') group by 1) x where nickname='Bulls'")
ask("test", "teams", "Which team had the lowest opponent three-point percentage?", "lead", best_team("sum(a.tpm)::float/sum(a.tpa)", order="asc"))
ask("test", "teams", "How did the Rockets do in their last 10 games?", "text", "select sum(won::int)||'-'||sum((not won)::int) from (select g.won " + TEAM + " where t.nickname='Rockets' order by g.game_date desc limit 10) x")
ask("test", "teams", "What was the Timberwolves' record in March?", "text", team("sum(g.won::int)||'-'||sum((not g.won)::int)", "Timberwolves", "extract(month from g.game_date)=3"))
ask("test", "teams", "Which Eastern team scored the most points per game?", "lead", best_team("avg(g.points)", "t.abbreviation in ('ATL','BOS','BKN','CHA','CHI','CLE','DET','IND','MIA','MIL','NYK','ORL','PHI','TOR','WAS')"))
ask("test", "teams", "Longest losing streak of the Wizards", "num", STREAK.format(nick="Wizards", won="not won"))
ask("test", "games", "How many overtime games did the Kings play?", "num", "select count(*) from team_period_scores q join teams t on t.nba_team_id=q.nba_team_id where period=5 and t.nickname='Kings'")
ask("test", "games", "What was the score when the Nuggets hosted the Suns?", "num", "select g.points from team_box_scores g join teams t on t.nba_team_id=g.nba_team_id join teams o on o.nba_team_id=g.opponent_nba_team_id where t.nickname='Nuggets' and o.nickname='Suns' and g.is_home order by g.game_date limit 1")
ask("test", "games", "Which team scored the fewest points in a game?", "lead", f"select t.full_name {TEAM} order by g.points limit 1")
ask("test", "games", "Which team is best in the first quarter?", "lead", "select t.full_name from team_period_scores q join teams t on t.nba_team_id=q.nba_team_id where period=1 group by 1 order by avg(points) desc limit 1")
ask("test", "games", "What was the largest margin of victory for the Magic?", "num", team("max(g.points-g.opponent_points)", "Magic"))
ask("test", "games", "Who won on Christmas Day between the Lakers and Warriors?", "lead", "select t.full_name " + TEAM + " where g.won and g.game_date='2024-12-25' and t.nickname in ('Lakers','Warriors')")
ask("test", "shots", "How many floaters did Trae Young make?", "num", "select sum(shot_made::int) from shot_charts s join players p on p.id=s.player_id where p.full_name='Trae Young' and action_type ilike '%floating%'")
ask("test", "shots", "Who took the most mid-range shots?", "lead", "select p.full_name from shot_charts s join players p on p.id=s.player_id where shot_zone_basic='Mid-Range' group by 1 order by count(*) desc limit 1")
ask("test", "shots", "Who dunked the most?", "lead", "select p.full_name from shot_charts s join players p on p.id=s.player_id where action_type ilike '%dunk%' group by 1 order by sum(shot_made::int) desc limit 1")
ask("test", "shots", "What percentage does Kevin Durant shoot from mid-range?", "num", "select round(100.0*sum(shot_made::int)/count(*),1) from shot_charts s join players p on p.id=s.player_id where p.full_name='Kevin Durant' and shot_zone_basic='Mid-Range'")
ask("test", "shots", "Which team attempted the most corner threes?", "lead", "select t.full_name from shot_charts s join teams t on t.id=s.team_id where shot_type like '3%' and loc_y<=89 and abs(loc_x)>=200 group by 1 order by count(*) desc limit 1")
ask("test", "pairs", "Which duo has the best net rating in the league?", "names", "select unnest(array[a.full_name,b.full_name]) from (select * from player_pairs where minutes>=200 order by net_rating desc limit 1) x join players a on a.id=x.player_a join players b on b.id=x.player_b")
ask("test", "pairs", "How many minutes did Nikola Jokic and Jamal Murray play together?", "num", "select round(minutes::numeric,0) from player_pairs x join players a on a.id=x.player_a join players b on b.id=x.player_b where a.full_name in ('Nikola Jokić','Jamal Murray') and b.full_name in ('Nikola Jokić','Jamal Murray')")
ask("test", "matchup", "How did Jalen Brunson do against Derrick White as his defender?", "num", "select round(points::numeric,0) from player_matchups m join players a on a.id=m.off_player_id join players b on b.id=m.def_player_id where a.full_name='Jalen Brunson' and b.full_name='Derrick White'")
ask("test", "compare", "Who is taller, Chet Holmgren or Evan Mobley?", "lead", f"select p.full_name from player_profiles pp join players p on p.id=pp.player_id where p.full_name in ('Chet Holmgren','Evan Mobley') order by {INCH} desc limit 1")
ask("test", "compare", "Who blocks more shots, Walker Kessler or Brook Lopez?", "lead", best_player("avg(b.blk)", "p.full_name in ('Walker Kessler','Brook Lopez')"))
ask("test", "compare", "Who won more games, the Clippers or the Lakers?", "lead", best_team(WIN + ", avg(g.points-g.opponent_points)", "t.nickname in ('Clippers','Lakers')"))
ask("test", "team", "Who is the best rebounder on the Pelicans?", "lead", adv("ss.rebounds desc", "t.nickname='Pelicans' and s.gp>=20"))
ask("test", "team", "Which Pacers player has the best three-point percentage?", "lead", adv("s.tpm::float/s.tpa desc", "t.nickname='Pacers' and s.tpa>=100"))
ask("test", "league", "How many players averaged at least 20 points per game?", "num", f"select count(*) {ADV} where ss.points>=20 and s.gp>=10 and s.mpg>=8")
ask("test", "league", "What is the average points per game of a team?", "num", "select round(avg(points),1) from team_box_scores")
ask("test", "lineup", "How would a lineup of Stephen Curry, Devin Booker, Jayson Tatum, Giannis Antetokounmpo and Nikola Jokic do?", "text", "select 'net'")
ask("test", "fit", "Who would be an ideal teammate for Luka Doncic?", "text", "select 'teammate'")
