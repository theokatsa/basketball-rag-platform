"""Greek questions, put into the English words that the question reader understands.

Not a translator: basketball questions use a small vocabulary, and the reader looks for words and
not for grammar, so replacing the known words is enough. Unknown words are left as they are.
"""

from __future__ import annotations

import re
import unicodedata

NAMES = {
    "γιαννης αντετοκουνμπο": "Giannis Antetokounmpo", "αντετοκουνμπο": "Giannis Antetokounmpo", "γιαννης": "Giannis Antetokounmpo", "γιαννη": "Giannis Antetokounmpo", "λεμπρον τζειμς": "LeBron James", "λεμπρον": "LeBron James",
    "στεφεν καρι": "Stephen Curry", "στεφ καρι": "Stephen Curry", "καρι": "Stephen Curry", "νικολα γιοκιτς": "Nikola Jokić", "γιοκιτς": "Nikola Jokić", "λουκα ντοντσιτς": "Luka Dončić", "ντοντσιτς": "Luka Dončić", "λουκα": "Luka Dončić",
    "κεβιν ντουραντ": "Kevin Durant", "ντουραντ": "Kevin Durant", "τζεισον τειτουμ": "Jayson Tatum", "τειτουμ": "Jayson Tatum", "τζοελ εμπιντ": "Joel Embiid", "εμπιντ": "Joel Embiid", "σαι γκιλτζους αλεξαντερ": "Shai Gilgeous-Alexander", "σαι": "Shai Gilgeous-Alexander",
    "βικτορ ουεμπανιαμα": "Victor Wembanyama", "ουεμπανιαμα": "Victor Wembanyama", "γουεμπανιαμα": "Victor Wembanyama", "αντονι εντουαρντς": "Anthony Edwards", "εντουαρντς": "Anthony Edwards", "τζεισον μπραουν": "Jaylen Brown", "τζειλεν μπραουν": "Jaylen Brown",
    "ντεβιν μπουκερ": "Devin Booker", "μπουκερ": "Devin Booker", "τζα μοραντ": "Ja Morant", "μοραντ": "Ja Morant", "τρεϊ γιανγκ": "Trae Young", "τρει γιανγκ": "Trae Young", "ντειμιαν λιλαρντ": "Damian Lillard", "λιλαρντ": "Damian Lillard",
    "αντονι ντεϊβις": "Anthony Davis", "αντονι ντειβις": "Anthony Davis", "ντονοβαν μιτσελ": "Donovan Mitchell", "μιτσελ": "Donovan Mitchell", "τζεϊλεν μπρανσον": "Jalen Brunson", "τζειλεν μπρανσον": "Jalen Brunson", "μπρανσον": "Jalen Brunson",
    "τζειμς χαρντεν": "James Harden", "χαρντεν": "James Harden", "ρουντι γκομπερ": "Rudy Gobert", "γκομπερ": "Rudy Gobert", "τζιμι μπατλερ": "Jimmy Butler III", "μπατλερ": "Jimmy Butler III", "κρις πολ": "Chris Paul", "ζιον ουιλιαμσον": "Zion Williamson", "ζιον": "Zion Williamson",
    "πασκαλ σιακαμ": "Pascal Siakam", "σιακαμ": "Pascal Siakam", "ντομαντας σαμπονις": "Domantas Sabonis", "σαμπονις": "Domantas Sabonis", "κριστιανο πορζινγκις": "Kristaps Porziņģis", "πορζινγκις": "Kristaps Porziņģis", "αλπερεν σενγκουν": "Alperen Sengun", "σενγκουν": "Alperen Sengun",
}
TEAMS = {
    "χοκς": "Hawks", "σελτικς": "Celtics", "βοστωνη": "Boston Celtics", "νετς": "Nets", "χορνετς": "Hornets", "μπουλς": "Bulls", "καβαλιερς": "Cavaliers", "καβς": "Cavaliers", "μαβερικς": "Mavericks", "μαβς": "Mavericks", "ναγκετς": "Nuggets", "πιστονς": "Pistons", "ουοριορς": "Warriors",
    "γουοριορς": "Warriors", "ροκετς": "Rockets", "πεϊσερς": "Pacers", "πεισερς": "Pacers", "κλιπερς": "Clippers", "λεϊκερς": "Lakers", "λεικερς": "Lakers", "γκριζλις": "Grizzlies", "χιτ": "Heat", "μπακς": "Bucks", "τιμπεργουλβς": "Timberwolves", "πελικανς": "Pelicans", "νικς": "Knicks", "θαντερ": "Thunder",
    "ματζικ": "Magic", "σιξερς": "76ers", "σανς": "Suns", "μπλεϊζερς": "Trail Blazers", "μπλειζερς": "Trail Blazers", "κινγκς": "Kings", "σπερς": "Spurs", "ραπτορς": "Raptors", "τζαζ": "Jazz", "ουιζαρντς": "Wizards",
}
# Longer phrases first: what they consume is not read again.
WORDS = [
    (r"ποσο ψηλ\w+", "how tall"), (r"ποσο βαρυ\w*|ποσα κιλα", "how much does weigh"), (r"ποσων (?:ετων|χρονων)", "how old"), (r"ποσ(?:α|ους|ες|οι|ο)", "how many"), (r"ποια (?:ειναι )?(?:η )?ομαδα", "which team"), (r"ποιες ομαδες", "which teams"), (r"ποιοι παικτες|ποιους παικτες", "which players"), (r"ποιος παικτης", "which player"),
    (r"ποιοι(?= (?:γκαρντ|φοργουορντ|σεντερ))", "which"), (r"ποιος|ποιον|ποιοι|ποιους", "who"), (r"ποια|ποιο|ποιες|ποιας", "which"), (r"που σουταρ\w+", "where does shoot"), (r"πως τα (?:πηγε|πηγαν)", "how did do"), (r"τι εκαν\w+", "how did do"),
    (r"κατα μεσο ορο|μεσο ορο|μεσος ορος|μεσο ορου", "average"), (r"(?:ανα|σε καθε|τον|το) (?:αγωνα|παιχνιδι|ματς)", "per game"), (r"σε ενα(?:ν)? (?:αγωνα|παιχνιδι|ματς)", "in a single game"), (r"ρεκορ σεζον|σεζον ρεκορ", "season high"),
    (r"παρομοι\w* στυλ(?: παιχνιδιου)?(?: με(?: τον| την)?)?", "similar to"), (r"παρομοι\w*(?: με(?: τον)?)?|μοιαζ\w*(?: με(?: τον)?| στον)?|σαν(?: τον)?|ιδι\w* στυλ με(?: τον)?", "similar to"), (r"στυλ(?: παιχνιδιου)?", "style"),
    (r"κατω (?:των|απο)", "under"), (r"ανω των|πανω απο|περισσοτερ\w+ απο", "over"), (r"λιγοτερ\w+ απο", "fewer than"), (r"τουλαχιστον", "at least"), (r"και ανω|και πανω", "or more"), (r"νεοτερ\w+ (?:των|απο)", "younger than"),
    (r"εντος(?: εδρας)?|στην? εδρα\w*", "at home"), (r"εκτος(?: εδρας)?", "on the road"), (r"εναντιον|απεναντι(?: σε| στους)?|κοντρα(?: σε| στους)?", "against"), (r"στις νικες", "in wins"), (r"στις ηττες", "in losses"),
    (r"τριπλ\w* νταμπλ|τριπλ νταμπλ\w*", "triple-doubles"), (r"νταμπλ νταμπλ\w*|διπλ\w* νταμπλ", "double-doubles"), (r"ποσοστ\w* (?:στα )?τριποντ\w+|ευστοχ\w+ στα τριποντ\w+", "three-point percentage"), (r"ποσοστ\w* (?:στις )?βολ\w+", "free throw percentage"), (r"ποσοστ\w+", "percentage"),
    (r"επιθετικ\w* ριμπαουντ", "offensive rebounds"), (r"αμυντικ\w* ριμπαουντ", "defensive rebounds"), (r"ριμπαουντ\w*", "rebounds"), (r"τριποντ\w*", "three-pointers"), (r"ποντ\w+", "points"), (r"ασιστ\w*|τελικ\w* πασ\w+", "assists"), (r"κλεψιμ\w+", "steals"), (r"κοψιμ\w+|ταπες|μπλοκ", "blocks"), (r"λαθ(?:η|ων|ος)", "turnovers"),
    (r"βολ(?:ες|ων|η)", "free throws"), (r"φαουλ", "fouls"), (r"λεπτ(?:α|ων)", "minutes"), (r"καρφωμα\w*", "dunks"), (r"σουτ απο μεσαια αποσταση|μεσαια\w* αποστασ\w*", "mid-range"), (r"γωνι\w+", "corner"), (r"σουτερ", "shooters"), (r"σκορερ", "scorers"), (r"σκοραρ\w+|σκοραρει", "scored"), (r"πασερ|δημιουργ\w+", "playmakers"),
    (r"αμυντικ\w*|αμυν\w*", "defense"), (r"επιθετικ\w*|επιθεσ\w*", "offense"), (r"ρυθμ\w*", "pace"), (r"καλυτερ\w*", "best"), (r"χειροτερ\w*", "worst"), (r"περισσοτερ\w*|παραπανω", "most"), (r"λιγοτερ\w*", "fewest"), (r"μεγαλυτερ\w* ηλικια\w*|γηραιοτερ\w*", "oldest"), (r"μεγαλυτερ\w*", "biggest"), (r"υψηλοτερ\w*", "highest"), (r"χαμηλοτερ\w*", "lowest"),
    (r"ψηλοτερ\w*", "tallest"), (r"βαρυτερ\w*", "heaviest"), (r"νεοτερ\w*|νεαροτερ\w*", "youngest"), (r"νεαρ\w*|νεοι", "young"), (r"ομαδ\w*", "team"), (r"παικτ\w*|παιχτ\w*", "players"), (r"συμπαικτ\w*", "teammate"), (r"ιδανικ\w*", "ideal"), (r"διδυμ\w*|δυαδ\w*", "duo"), (r"γκαρντ", "guards"), (r"φοργουορντ", "forwards"), (r"σεντερ", "centers"), (r"ρουκι", "rookies"),
    (r"μαρκαρ\w*|φυλα\w*", "guards"), (r"ρεκορ", "record"), (r"κερδισ\w*|νικησ\w*", "won"), (r"νικ(?:ες|η|ων)", "wins"), (r"ηττ\w*|εχασ\w*", "losses"), (r"σερι", "streak"), (r"παρατασ\w*", "overtime"), (r"περιοδ\w*|δεκαλεπτ\w*", "quarter"), (r"πρωτ\w*", "first"), (r"δευτερ\w*", "second"), (r"τριτ\w*", "third"), (r"τεταρτ\w*", "fourth"),
    (r"αγων\w*|παιχνιδι\w*|ματς", "games"), (r"συνολ\w*", "total"), (r"συγκριν\w*|συγκρισ\w*", "compare"), (r"σεζον", "season"), (r"τελευται\w*", "last"), (r"φορμα", "form"), (r"ηλικια\w*", "age"), (r"υψος", "height"), (r"βαρος", "weight"), (r"δυτικ\w*|δυση\w*", "western"), (r"ανατολικ\w*|ανατολη\w*", "eastern"), (r"περιφερει\w*", "conference"), (r"πρωταθληματ\w*|λιγκα\w*", "league"),
    (r"ιανουαρι\w*", "january"), (r"φεβρουαρι\w*", "february"), (r"μαρτι\w*", "march"), (r"απριλι\w*", "april"), (r"οκτωβρι\w*", "october"), (r"νοεμβρι\w*", "november"), (r"δεκεμβρι\w*", "december"),
    (r"εχει|ειχε|εχουν|ειχαν|εβαλε|εβαλαν|εκανε|εκαναν|μαζεψε|μοιρασε|πετυχε|πετυχαν", "had"), (r"και|με", "and"), (r"ή|ή|η(?= [A-Z])", "or"), (r"ο|η|τις|στον|στην|στους|στις|στα|στο|των|τους|τον|την|της|του|τα|το|οι|απο|για|σε|που|ειναι|ηταν|να", ""),
]


def is_greek(question: str) -> bool:
    return bool(re.search(r"[Ͱ-Ͽἀ-῿]", question))


def _plain(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c) or c == "̈").replace("ς", "σ")


def to_english(question: str) -> str:
    """The question with Greek basketball words replaced. English text passes through unchanged."""
    if not is_greek(question):
        return question
    out = unicodedata.normalize("NFC", _plain(question)).replace(";", "?")
    out = re.sub(r"[Ͱ-Ͽ]+", lambda m: m.group().lower(), out)
    for table in (NAMES, TEAMS):
        for greek in sorted(table, key=len, reverse=True):
            out = re.sub(rf"(?<!\w){re.escape(_plain(greek))}(?!\w)", table[greek], out)
    for pattern, english in WORDS:
        out = re.sub(rf"(?<!\w)(?:{_plain(pattern)})(?!\w)", english, out)
    out = re.sub(r"\s+", " ", out).strip()
    # Greek puts no article in front of a team; the reader does not need one either.
    return out[:1].upper() + out[1:]
