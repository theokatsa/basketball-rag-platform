"""Training data for the paraphrase router: ways people ask about a statistic without naming it.

Written by hand. A random quarter is never trained on and is used to compare methods (the split
is by hash, so it does not move when phrases are added). The four paraphrases of the retrieval
test set are deliberately not in here.
"""

import hashlib

# class -> (plain words the question reader understands, phrases)
PHRASES: dict[str, tuple[str, list[str]]] = {
    "points": ("points", [
        "go-to bucket getters", "who can get you a bucket whenever he wants", "best offensive weapon", "players who light up the scoreboard", "guys who fill it up every night", "walking bucket", "who carries the scoring load",
        "most dangerous offensive threats", "players who can drop forty on anyone", "volume scoring machine", "who is unstoppable with the ball", "first option on offense", "who pours it in", "who lights it up", "guys that get buckets", "which star lit it up the most", "number one scoring option",
    ]),
    "rebounds": ("rebounds", [
        "who owns the boards", "dominant on the glass", "who crashes the boards", "glass cleaners", "who grabs every missed shot", "monsters on the backboards", "players who vacuum up misses", "who secures possession after a miss", "who pulls down the ball after missed shots",
        "strongest board men", "windex men", "who gets the ball off the rim", "best at collecting misses", "who controls the paint on missed shots", "who hauls in the most boards",
    ]),
    "assists": ("assists", [
        "floor generals", "who sets up teammates best", "table setters", "best court vision", "who makes his teammates better with passes", "dimes", "who dishes it out", "pass-first point guards", "who runs the offense", "creators for others", "who finds the open man", "best facilitator",
        "maestro of the offense", "who feeds the shooters", "players who see the floor well", "who threads the needle", "distributors", "quarterback of the offense",
    ]),
    "steals": ("steals", [
        "thieves on defense", "best hands on defense", "who picks pockets", "who strips the ball", "ball hawks", "who intercepts the most passes", "who jumps the passing lanes the best", "who disrupts ball handlers", "quick hands on the perimeter", "who takes the ball away", "who creates turnovers on defense",
        "who robs opponents", "pest on the perimeter", "who pokes the ball loose",
    ]),
    "blocks": ("blocks", [
        "who protects the rim", "paint protector", "shot swatters", "who rejects shots", "who sends shots into the stands", "who erases shots at the rim", "intimidating presence in the paint", "who guards the basket", "eraser in the middle", "who alters and denies layups", "no layups allowed against him",
        "who stuffs opponents", "the best rim deterrent", "who swats everything away",
    ]),
    "turnovers": ("turnovers", [
        "careless with the ball", "who gives the ball away", "sloppy ball handlers", "who loses the ball the most", "who coughs it up", "who throws bad passes", "who makes the most mistakes with the ball", "reckless passers", "loose with the basketball", "who gives away possessions",
        "butterfingers", "who commits ball handling errors",
    ]),
    "tpm": ("threes", [
        "snipers from downtown", "who bombs away from deep", "who rains threes", "who lets it fly from long range", "long range bombers", "who drains shots from beyond the arc", "who launches from deep the most", "perimeter gunners", "splash brothers type shooters", "who cashes in from way out",
        "who makes it rain", "flamethrowers from distance", "who knocks down triples",
    ]),
    "three_pct": ("three-point percentage", [
        "deadliest marksman from long range", "most accurate from outside", "most reliable outside shooter", "knockdown shooters", "pure shooter from distance", "who rarely misses from deep", "best stroke from outside", "sharpshooter accuracy", "who cannot be left open behind the arc", "floor spacers with accuracy", "catch and shoot specialists",
        "who converts outside shots at the best rate",
    ]),
    "ft_pct": ("free throw percentage", [
        "automatic at the stripe", "who never misses foul shots", "best from the charity stripe", "ice cold at the line", "who can you trust at the line late", "most reliable at the foul line", "who makes his foul shots", "perfect from the line", "who is money at the stripe", "most dependable when fouled",
    ]),
    "fta": ("free throws attempted", [
        "who lives at the line", "foul magnets", "who gets fouled the most", "who draws contact", "who earns trips to the line", "who baits defenders into fouls", "who gets to the stripe", "foul merchant", "who forces whistles", "who absorbs contact and gets the call",
    ]),
    "fg_pct": ("field goal percentage", [
        "who rarely misses", "highest conversion rate on shots", "who converts his looks", "best finisher", "who makes the highest share of his shots", "most accurate overall shooter", "who hardly ever misses a shot", "best shot converter",
    ]),
    "ts": ("true shooting", [
        "who gets the most out of his shots", "who wastes the fewest possessions when scoring", "economical scorers", "best bang for the buck scorers", "who needs few shots to score a lot", "most points for each shot taken", "best overall shooting value including free throws", "who scores without wasting shots",
    ]),
    "minutes": ("minutes", [
        "workhorses", "who never comes off the floor", "who is on the court the longest", "iron men who play all night", "who gets the heaviest workload", "who rarely rests", "most time on the hardwood", "who does his coach lean on for long stretches", "who logs the longest nights",
    ]),
    "games": ("most games played", [
        "who never misses a night", "most durable players", "iron man availability", "who was always available", "who suited up every night", "who was never injured", "who appeared most often", "who showed up all season",
    ]),
    "fouls": ("fouls", [
        "who hacks the most", "who gets into foul trouble", "undisciplined defenders", "who is whistled the most", "who cannot stay on the floor because of the referees", "hackers", "who gets called by the refs most", "who plays too physical for the refs",
    ]),
    "oreb": ("offensive rebounds", [
        "second chance specialists", "who keeps possessions alive", "who extends possessions after his own team misses", "putback machines on the glass", "best at getting extra possessions", "who wins the ball back after a teammate misses", "crashes the offensive glass", "who creates second chances",
    ]),
    "usg_pct": ("usage rate", [
        "ball dominant players", "whose hands is the ball always in", "who monopolizes the ball", "ball hogs", "who ends the most possessions", "who takes over the offense", "who has the offense run through him", "heliocentric stars", "who dominates the ball",
    ]),
    "ast_to": ("assist to turnover ratio", [
        "safest hands", "who takes care of the ball while passing", "careful playmakers", "who passes without mistakes", "most reliable ball handler", "who creates without giving it away", "steady point guards", "low risk passers", "who rarely throws it away",
    ]),
    "plus_minus": ("plus-minus", [
        "whose team outscores opponents when he plays", "best score difference with him on the court", "who wins his minutes", "who swings the scoreboard", "team is ahead when he is on the floor", "biggest scoreboard impact",
    ]),
    "net_rating": ("net rating", [
        "who helps his team outperform per possession", "best impact per hundred possessions", "with whom is a team most dominant", "who lifts his team's efficiency on both ends", "strongest on-court efficiency difference", "per possession dominance",
    ]),
    "defense_score": ("defense score", [
        "lockdown guys", "stoppers", "who clamps opponents", "who shuts people down", "who makes life difficult for scorers", "best two-way stopper", "who puts the clamps on", "who locks up stars", "toughest to score on", "perimeter clamps", "who is a nightmare for scorers",
    ]),
    "overall_score": ("overall score", [
        "who is the king of the league", "superstar of the season", "who is the best in the world right now", "top dog in the league", "the most complete player", "who dominates every part of the game", "best of the best", "who does it all", "goat this year",
    ]),
    "double_doubles": ("double-doubles", [
        "who hits double figures in two categories most", "two categories in double digits", "points and boards in double figures most nights", "who reaches ten in two stats",
    ]),
    "triple_doubles": ("triple-doubles", [
        "who fills every column of the box score", "three categories in double digits", "stat sheet stuffers with ten ten ten", "who reaches ten in three stats", "stuffs the stat sheet across three categories",
    ]),
    "height": ("tallest", [
        "biggest giants", "who towers over everyone", "seven footers", "who is the biggest man in height", "longest body", "the giant of the league", "who has to duck under doors",
    ]),
    "weight": ("heaviest", [
        "bulkiest players", "biggest body", "who has the most mass", "strongest build by pounds", "who tips the scales the most", "the biggest bruiser by pounds",
    ]),
    "age": ("oldest", [
        "veteran elders of the league", "who has been alive the longest", "the grandpa of the league", "closest to retirement by birthday", "most senior by birth date", "old heads",
    ]),
    "experience": ("most experience", [
        "who has been in the league the longest", "most seasoned", "longest serving players", "who entered the league first", "most years as a pro", "who has the longest career",
    ]),
    "dunks": ("most dunks", [
        "high flyers", "who throws it down", "posterizers", "who hammers it home", "above the rim finishers", "who jams the most", "lob threats", "rim rattlers", "best leapers finishing with power",
    ]),
    "midrange": ("most mid-range shots", [
        "masters of the in-between game", "who lives in the fifteen foot range", "old school two point jump shooters", "who loves the long two", "pull up from the elbow type scorers", "who operates between the arc and the paint",
    ]),
    "floaters": ("most floaters", [
        "who loves the teardrop", "runner specialists in the lane", "soft touch over big men", "who flips it over the shot blocker",
    ]),
    "layups": ("most layups", [
        "who attacks the basket", "slashers", "who drives to the hoop constantly", "downhill attackers", "who gets to the rack", "who penetrates the lane to score",
    ]),
    "clutch_none": ("", [
        "what arena does the team play in", "who won the championship", "how much money does he make", "which college did he attend", "what is the weather today", "tell me a joke", "who is the coach", "when is the next game", "how do I create an account", "what are the rules of basketball", "who owns the team",
        "which shoes does he wear", "what is his nationality", "who was drafted first", "how many titles do they have", "best movie about basketball", "who sings the anthem", "where can I buy tickets", "explain the salary cap", "who is injured tonight", "write a poem", "which city is the largest",
        "who got traded", "is he married", "what time is it", "which team has the nicest jersey", "give me the latest news", "how is the weather in miami", "what happened in the world cup", "who is the referee",
    ]),
}
NONE = "clutch_none"


def held_out(phrase: str) -> bool:
    return int(hashlib.sha256(phrase.encode()).hexdigest(), 16) % 4 == 0


def split() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    pairs = [(phrase, label) for label, (_, phrases) in PHRASES.items() for phrase in phrases]
    return [p for p in pairs if not held_out(p[0])], [p for p in pairs if held_out(p[0])]
