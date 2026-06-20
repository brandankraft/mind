#!/usr/bin/env python3
"""
One-shot: remap generic 'App. A' references in the topical index
to the specific sub-appendix (App. A1 - App. A12) based on topic keywords.

Only rewrites the specific *entry line*; leaves Chapter refs alone.
Uses case-insensitive keyword matching on the bolded topic portion
(the '**topic**' before the ' -- App. A' reference).
"""

import re
import sys
from pathlib import Path

INDEX = Path("/Users/brandankraft/Anna/Mind/appendix-q-topical-index.md")

# Topic-keyword -> specific sub-appendix. First match wins.
# Keywords are matched case-insensitively against the entire entry line.
RULES = [
    # A1 God and Creation
    ("A1", ["attributes of god", "person of the holy spirit", "holy spirit, person",
            "inspiration and authority of scripture", "scripture.*authority",
            "the fall", "fall as revelation", "fall of adam",
            "effectual calling", "repentance, legal", "god's rest", "sabbath",
            "many thoughts", "one thought",
            "mud and spit", "john 9", "lawgiver",
            "animals in the framework", "big bang",
            "genealogies", "age of the earth", "tower of babel", "the flood",
            "augustine and the inherited", "act and potency", "aristotel",
            "become as one of us", "made subject to vanity",
            "adam created sinful", "author of evil",
            "flood, the",
            "image of god",
            "covenant of works"]),
    # A2 Spirit World
    ("A2", ["spirits, angels, demons", "satan's fate", "nephilim",
            "demons (created", "demon possession", "spiritual warfare",
            "angels that sinned", "condemnation of the devil",
            "devil and his angels", "false teachers as \"angels\"",
            "revelation 12:", "satan as lightning",
            "malware and quarantine", "elect angels"]),
    # A3 Salvation Applied
    ("A3", ["means and regeneration", "those who never hear", "infants who die",
            "mentally disabled", "suicide", "assurance of salvation",
            "apostasy and perseverance", "preservation of the saints",
            "unforgivable sin", "intermediate state", "degrees of reward",
            "common grace (denied)", "two wills of god",
            "permission and the dog", "secondary causes",
            "perpetual virginity", "faith is assurance",
            "root access",
            "^- \\*\\*apostasy \\(elect cannot",
            "federal headship",
            "circumcision of the heart"]),
    # A4 Spirit's Gifts
    ("A4", ["baptism of the holy spirit", "tongues and spiritual gifts",
            "^- \\*\\*conscience\\*\\*", "trichotomy", "dichotomy",
            "head and heart", "filling of the spirit",
            "cessationism", "continuationism",
            "^- \\*\\*charismatic gifts",
            "^- \\*\\*tongues"]),
    # A5 Church
    ("A5", ["ordination", "plural eldership", "clerical titles",
            "paid preachers", "church discipline",
            "creeds and confessions", "antilegomena", "council of trent",
            "music in worship", "religious relics", "evangelism and soul",
            "great commission", "itinerant preaching",
            "deriving instead of defending",
            "^- \\*\\*evangelism / preaching",
            "^- \\*\\*westminster confession",
            "^- \\*\\*canons of dort",
            "^- \\*\\*heidelberg catechism",
            "^- \\*\\*london baptist confession"]),
    # A6 Eschatology
    ("A6", ["origins of dispensationalism", "full preterism", "hymenaeus",
            "the rapture", "^- \\*\\*rapture", "tribulation",
            "antichrist", "great apostasy", "number of the beast",
            "binding and loosing of satan", "satan's binding",
            "second coming", "living as worship in the new creation",
            "marital sexuality and the eschatological bed",
            "covenant companion", "marriage persisting into the new creation",
            "new heavens and new earth",
            "dispensationalism",
            "heaven enlarged", "god's delight in the saints",
            "reduction of heaven to disembodied choir"]),
    # A7 Personal Ethics
    ("A7", ["divorce and remarriage", "marriage and submission",
            "homosexuality", "premarital sex", "pornography",
            "masturbation", "singleness", "birth control",
            "corporal punishment", "alcohol and drug",
            "smoking and tobacco", "obesity", "euthanasia",
            "abuse in marriage",
            "cannabis", "drugs / pharmakeia", "drunkenness",
            "pharmakeia", "quiverfull", "humanae vitae",
            "death with dignity", "tobacco use", "vaping",
            "nicotine pouches", "spurgeon and tobacco",
            "gluttony", "modern food environment", "glp-1",
            "eating disorders", "fat acceptance", "fat-shaming",
            "alcohol \\(moderation", "theology of wine",
            "exorcism",
            "prohibitionism", "family size", "infertility",
            "^- \\*\\*parenting", "paul likely married"]),
    # A8 Society and Civil Life
    ("A8", ["government and politics", "capital punishment",
            "^- \\*\\*war", "gun control", "self-defense",
            "wealth and poverty", "tithing", "ufos", "aliens from another",
            "extraterrestrial life", "ancient astronauts",
            "dual sword", "pacifism",
            "giving \\(voluntary", "defending the household",
            "prosperity gospel",
            "^- \\*\\*political engagement",
            "stewardship / wealth"]),
    # A9 Hard Questions
    ("A9", ["suffering and theodicy", "theodicy / problem",
            "natural disasters", "communication with the dead",
            "other religions", "^- \\*\\*judas", "^- \\*\\*pharaoh",
            "hardening of hearts", "balaam's donkey",
            "ai consciousness", "christianity in the age of ai",
            "calculator and mathematician",
            "lord's prayer",
            "ai, christianity",
            "^- \\*\\*prayer\\*\\*"]),
    # A10 Christian Life
    ("A10", ["lydia and the moment", "doubt and assurance",
             "grief and lament", "comforting the grieving",
             "oj the cat", "theology as a weapon",
             "^- \\*\\*shibboleth", "heresy hunting",
             "^- \\*\\*gatekeeping"]),
    # A11 Bedside
    ("A11", ["sentence at the bedside", "death of a child",
             "^- \\*\\*abortion", "child with disabilities",
             "struggling marriage", "watching someone you love reject",
             "forgiving someone who will not apologize",
             "pastoral care for the struggling",
             "practical applications of the sentence",
             "purpose and calling", "why was i born this way",
             "^- \\*\\*suffering",
             "suffering is not punishment",
             "hurt by the church", "^- \\*\\*loneliness",
             "when god feels silent", "guilt after sin", "sexual shame",
             "fear of man", "born a certain way", "^- \\*\\*addiction",
             "anxiety about the future", "^- \\*\\*depression",
             "on suffering", "credentials, irrelevance",
             "aging and losing capacity", "death, fear of",
             "^- \\*\\*doubt", "dying well", "watching a loved one die",
             "forgiveness \\(when they won't apologize",
             "pastoral care for the struggling",
             "practical applications of the sentence",
             "purpose and calling", "why was i born this way",
             "^- \\*\\*suffering",
             "suffering is not punishment"]),
    # A12 Framework-only
    ("A12", ["framework itself", "time travel", "^- \\*\\*dreams",
             "deja vu", "multiverse", "depression.*firmware",
             "adhd", "neurodivergence",
             "discernment vs\\. judgment",
             "gender dysphoria", "new creative work in heaven",
             "children who die young",
             "knowing each other in heaven"]),
]

def pick_subappendix(line_lower):
    for sub, keywords in RULES:
        for kw in keywords:
            # If keyword already contains intentional regex (^, \\, etc.), use as-is.
            # Otherwise escape literal parens and other metachars.
            if kw.startswith("^") or "\\" in kw:
                pattern = kw
            else:
                pattern = re.escape(kw)
            if re.search(pattern, line_lower):
                return sub
    return None

def main():
    text = INDEX.read_text()
    lines = text.split("\n")
    changes = 0
    out = []
    for line in lines:
        # Only target lines that contain 'App. A' but not 'App. A<digit>'
        if "App. A" in line and not re.search(r"App\. A\d", line):
            # Don't touch the header text at the top
            if "abbreviations:" in line.lower() or "appendixes m" in line.lower():
                out.append(line)
                continue
            sub = pick_subappendix(line.lower())
            if sub:
                # Replace the standalone 'App. A' with 'App. A<sub>'
                # Guard against replacing 'App. Acknowledgments' or similar
                new = re.sub(r"App\. A(?![a-zA-Z0-9])", f"App. {sub}", line)
                if new != line:
                    changes += 1
                    out.append(new)
                    continue
        out.append(line)
    INDEX.write_text("\n".join(out))
    print(f"Updated {changes} lines.")

if __name__ == "__main__":
    main()
