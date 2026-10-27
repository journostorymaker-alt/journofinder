"""Short and full forms of first names, shared by the finder's scripts."""

# Short and full forms of first names. Lists like the Parliament register use
# the full form ("Timothy Baker") while outlets use the short one ("Tim Baker").
NICKNAMES = {
    "tom": "thomas", "tim": "timothy", "ben": "benjamin", "sam": "samuel",
    "dan": "daniel", "nick": "nicholas", "rob": "robert", "bob": "robert",
    "alex": "alexander", "ali": "alison", "liz": "elizabeth", "beth": "elizabeth",
    "jim": "james", "jamie": "james", "mike": "michael", "chris": "christopher",
    "will": "william", "bill": "william", "ed": "edward", "ted": "edward",
    "fred": "frederick", "harry": "henry", "jon": "jonathan", "jo": "joanna",
    "kate": "katherine", "katie": "katherine", "becky": "rebecca", "andy": "andrew", "drew": "andrew", "sue": "susan", "jenny": "jennifer", "vicky": "victoria", "nicky": "nicola", "jess": "jessica", "jack": "john", "johnny": "john", "danny": "daniel", "freddie": "frederick", "ollie": "oliver", "olly": "oliver", "rosie": "rosemary", "debbie": "deborah", "gill": "gillian", "theo": "theodore", "max": "maxwell", "nathan": "nathaniel", "tash": "natasha", "mandy": "amanda", "penny": "penelope", "sandy": "alexander",
    "matt": "matthew", "pete": "peter", "steve": "stephen", "tony": "anthony",
    "rich": "richard", "dick": "richard", "jen": "jennifer", "abi": "abigail",
    "nat": "natalie", "charlie": "charles", "greg": "gregory", "dave": "david",
    "phil": "philip", "joe": "joseph", "josh": "joshua", "zach": "zachary",
}


# Full form -> the usual short form (first one listed above wins)
SHORT_FORM = {}
for _short, _full in NICKNAMES.items():
    SHORT_FORM.setdefault(_full, _short)


def other_forms(first):
    """Other forms of a first name worth trying in an email address.
    Andy -> [andrew], Andrew -> [andy]."""
    f = (first or "").lower().strip()
    out = []
    if f in NICKNAMES:
        out.append(NICKNAMES[f])
    if f in SHORT_FORM and SHORT_FORM[f] != f:
        out.append(SHORT_FORM[f])
    return out
