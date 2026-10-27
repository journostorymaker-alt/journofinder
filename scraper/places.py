"""
Place-name lookup used to work out a journalist's working patch.

Each patch area (roughly a county, city region or Scottish council area)
lists the towns and cities that point to it. The top-level region matches
the region names the dashboard already uses, so patches slot into the same
region tree.

Rules for adding places:
  - Skip names that are also common English words or surnames that crop up
    in headlines a lot (Reading, March, Deal, Street, Wells, Sale, Bury,
    Ware, Hope, Eye, Washington, Lincoln is fine). Wrong matches are worse
    than missing ones.
  - Skip names shared by two very different places unless one is far more
    common in UK news (Newport goes to Gwent, Richmond is skipped).

This is about where people WORK and what they cover. It is never used for
anything about where a journalist lives.
"""

# patch area -> (top region, [towns and cities, including the area name itself])
PATCHES = {
    # ---------------- Scotland ----------------
    "Glasgow & Clyde": ("Scotland", [
        "Glasgow", "Paisley", "Greenock", "Clydebank", "Renfrewshire", "Inverclyde",
        "East Kilbride", "Motherwell", "Wishaw", "Coatbridge", "Airdrie",
        "Cumbernauld", "Lanarkshire", "Dumbarton", "Kilmarnock", "Ayr", "Ayrshire",
        "Irvine", "Largs", "Troon", "Helensburgh",
    ]),
    "Edinburgh & Lothians": ("Scotland", [
        "Edinburgh", "Leith", "Livingston", "Musselburgh", "Dalkeith", "Midlothian",
        "West Lothian", "East Lothian", "Haddington", "Bathgate", "North Berwick",
    ]),
    "Fife & Central": ("Scotland", [
        "Fife", "Dunfermline", "Kirkcaldy", "Glenrothes", "St Andrews", "Stirling",
        "Falkirk", "Grangemouth", "Alloa", "Clackmannanshire",
    ]),
    "Tayside": ("Scotland", [
        "Dundee", "Perth", "Perthshire", "Angus", "Arbroath", "Forfar", "Montrose",
        "Pitlochry", "Crieff", "Blairgowrie",
    ]),
    "Aberdeen & North East Scotland": ("Scotland", [
        "Aberdeen", "Aberdeenshire", "Peterhead", "Fraserburgh", "Stonehaven",
        "Inverurie", "Ellon", "Banff", "Moray", "Elgin", "Buckie", "Forres",
    ]),
    "Highlands": ("Scotland", [
        "Inverness", "Highlands", "Fort William", "Nairn", "Aviemore",
        "Dingwall", "Ullapool", "Skye", "Portree", "Lochaber", "Sutherland",
        "Wick", "Thurso", "Caithness",
    ]),
    "Argyll & Islands": ("Scotland", [
        "Argyll", "Oban", "Campbeltown", "Dunoon", "Islay", "Mull", "Bute",
        "Rothesay", "Arran", "Kintyre", "Lochgilphead",
    ]),
    "Western Isles": ("Scotland", [
        "Western Isles", "Outer Hebrides", "Stornoway",
        "North Uist", "South Uist", "Isle of Lewis", "Isle of Harris", "Benbecula", "Barra",
    ]),
    "Orkney": ("Scotland", ["Orkney", "Kirkwall", "Stromness"]),
    "Shetland": ("Scotland", ["Shetland", "Lerwick", "Unst", "Scalloway"]),
    "Dumfries & Galloway": ("Scotland", [
        "Dumfries", "Galloway", "Stranraer", "Castle Douglas", "Annan",
        "Kirkcudbright", "Lockerbie", "Newton Stewart",
    ]),
    "Scottish Borders": ("Scotland", [
        "Scottish Borders", "Galashiels", "Hawick", "Kelso", "Peebles",
        "Jedburgh", "Selkirk", "Melrose", "Eyemouth",
    ]),

    # ---------------- Wales ----------------
    "Cardiff & Vale": ("Wales", [
        "Cardiff", "Penarth", "Vale of Glamorgan", "Cowbridge",
    ]),
    "Swansea & Neath Port Talbot": ("Wales", [
        "Swansea", "Gower", "Neath", "Port Talbot", "Llanelli",
    ]),
    "South Wales Valleys": ("Wales", [
        "Rhondda", "Merthyr Tydfil", "Merthyr", "Aberdare", "Pontypridd",
        "Caerphilly", "Bridgend", "Ebbw Vale", "Blaenau Gwent", "Tredegar",
        "Maesteg", "Porthcawl",
    ]),
    "Newport & Gwent": ("Wales", [
        "Newport", "Gwent", "Cwmbran", "Torfaen", "Pontypool", "Monmouthshire",
        "Monmouth", "Abergavenny", "Chepstow", "Caldicot",
    ]),
    "West Wales": ("Wales", [
        "Carmarthen", "Carmarthenshire", "Pembrokeshire", "Haverfordwest",
        "Pembroke", "Tenby", "Milford Haven", "Fishguard", "Ceredigion",
        "Aberystwyth", "Cardigan",
    ]),
    "Mid Wales": ("Wales", [
        "Powys", "Newtown", "Welshpool", "Brecon", "Llandrindod Wells",
        "Machynlleth", "Builth Wells",
    ]),
    "North Wales": ("Wales", [
        "Wrexham", "Flintshire", "Mold", "Denbighshire", "Rhyl", "Prestatyn",
        "Conwy", "Llandudno", "Colwyn Bay", "Bangor", "Gwynedd", "Caernarfon",
        "Anglesey", "Holyhead", "Snowdonia", "Eryri", "Pwllheli",
    ]),

    # ---------------- North East ----------------
    "Tyneside": ("North East", [
        "Newcastle", "Gateshead", "Tyneside", "South Shields", "North Shields",
        "Tynemouth", "Whitley Bay", "Jarrow", "Wallsend",
    ]),
    "Sunderland": ("North East", ["Sunderland",]),
    "County Durham": ("North East", [
        "County Durham", "Durham", "Darlington", "Bishop Auckland", "Consett",
        "Chester-le-Street", "Peterlee", "Seaham", "Newton Aycliffe",
    ]),
    "Teesside": ("North East", [
        "Middlesbrough", "Teesside", "Stockton", "Hartlepool", "Redcar",
        "Billingham", "Guisborough", "Thornaby",
    ]),
    "Northumberland": ("North East", [
        "Northumberland", "Morpeth", "Hexham", "Blyth", "Cramlington",
        "Ashington", "Alnwick", "Berwick", "Berwick-upon-Tweed",
    ]),

    # ---------------- North West ----------------
    "Greater Manchester": ("North West", [
        "Manchester", "Salford", "Stockport", "Oldham", "Rochdale", "Bolton",
        "Wigan", "Trafford", "Tameside", "Ashton-under-Lyne", "Altrincham", "Stretford", "Eccles", "Heywood",
    ]),
    "Merseyside": ("North West", [
        "Liverpool", "Merseyside", "Birkenhead", "Wirral", "St Helens",
        "Southport", "Bootle", "Knowsley", "Sefton", "Kirkby", "Huyton",
        "Wallasey", "Formby",
    ]),
    "Lancashire": ("North West", [
        "Lancashire", "Preston", "Blackpool", "Blackburn", "Burnley",
        "Lancaster", "Morecambe", "Chorley", "Accrington", "Fleetwood",
        "Lytham St Annes", "Ormskirk", "Skelmersdale", "Clitheroe",
        "Darwen", "Leyland", "Rossendale",
    ]),
    "Cheshire": ("North West", [
        "Cheshire", "Chester", "Warrington", "Crewe", "Macclesfield",
        "Northwich", "Runcorn", "Widnes", "Ellesmere Port", "Nantwich",
        "Wilmslow", "Congleton", "Knutsford",
    ]),
    "Cumbria": ("North West", [
        "Cumbria", "Carlisle", "Barrow", "Barrow-in-Furness", "Kendal",
        "Penrith", "Workington", "Whitehaven", "Keswick", "Windermere",
        "Ulverston", "Lake District", "Cockermouth", "Maryport", "Sellafield",
    ]),

    # ---------------- Yorkshire ----------------
    "Leeds & West Yorkshire": ("Yorkshire", [
        "Leeds", "Wakefield", "Huddersfield", "Halifax", "Calderdale",
        "Kirklees", "Dewsbury", "Batley", "Pontefract", "Castleford",
        "Morley", "Otley", "Pudsey", "Brighouse", "Hebden Bridge", "Ossett",
        "West Yorkshire", "Bradford", "Keighley", "Shipley", "Bingley", "Ilkley",
    ]),
    "Sheffield & South Yorkshire": ("Yorkshire", [
        "Sheffield", "Rotherham", "Barnsley", "Doncaster", "South Yorkshire",
        "Mexborough", "Penistone",
    ]),
    "Hull & East Yorkshire": ("Yorkshire", [
        "Hull", "East Yorkshire", "East Riding", "Beverley", "Bridlington",
        "Goole", "Driffield", "Hornsea", "Withernsea",
    ]),
    "Grimsby & Scunthorpe": ("Yorkshire", [
        "Grimsby", "Cleethorpes", "Scunthorpe", "North Lincolnshire",
        "North East Lincolnshire", "Immingham", "Brigg", "Barton-upon-Humber",
    ]),
    "York & North Yorkshire": ("Yorkshire", [
        "York", "North Yorkshire", "Harrogate", "Scarborough", "Whitby",
        "Selby", "Ripon", "Skipton", "Northallerton", "Thirsk", "Malton",
        "Knaresborough", "Pickering", "Tadcaster", "Settle", "Filey",
        "Yorkshire Dales", "Tockwith",
    ]),

    # ---------------- West Midlands ----------------
    "Birmingham & Black Country": ("West Midlands", [
        "Birmingham", "Solihull", "Sutton Coldfield", "Wolverhampton",
        "Walsall", "Dudley", "West Bromwich", "Sandwell", "Black Country",
        "Smethwick", "Oldbury", "Halesowen", "Stourbridge",
    ]),
    "Coventry & Warwickshire": ("West Midlands", [
        "Coventry", "Warwickshire", "Warwick", "Leamington", "Leamington Spa",
        "Nuneaton", "Stratford-upon-Avon", "Bedworth", "Kenilworth",
    ]),
    "Staffordshire": ("West Midlands", [
        "Staffordshire", "Stoke", "Stoke-on-Trent", "Stafford", "Newcastle-under-Lyme", "Burton upon Trent", "Lichfield", "Tamworth", "Cannock",
        "Leek", "Uttoxeter",
    ]),
    "Shropshire": ("West Midlands", [
        "Shropshire", "Shrewsbury", "Telford", "Oswestry", "Ludlow",
        "Bridgnorth", "Market Drayton", "Whitchurch",
    ]),
    "Herefordshire & Worcestershire": ("West Midlands", [
        "Herefordshire", "Hereford", "Leominster", "Ross-on-Wye", "Ledbury",
        "Worcestershire", "Worcester", "Kidderminster", "Redditch",
        "Bromsgrove", "Malvern", "Evesham", "Droitwich",
    ]),

    # ---------------- East Midlands ----------------
    "Nottinghamshire": ("East Midlands", [
        "Nottingham", "Nottinghamshire", "Mansfield", "Newark", "Worksop",
        "Retford", "Beeston", "Hucknall", "West Bridgford",
        "Sutton-in-Ashfield",
    ]),
    "Derbyshire": ("East Midlands", [
        "Derby", "Derbyshire", "Chesterfield", "Buxton", "Matlock", "Ilkeston",
        "Glossop", "Belper", "Ashbourne", "Swadlincote", "Peak District",
    ]),
    "Leicestershire & Rutland": ("East Midlands", [
        "Leicester", "Leicestershire", "Loughborough", "Hinckley",
        "Melton Mowbray", "Market Harborough", "Coalville", "Rutland",
        "Oakham",
    ]),
    "Lincolnshire": ("East Midlands", [
        "Lincolnshire", "Lincoln", "Grantham", "Spalding",
        "Skegness", "Louth", "Stamford", "Sleaford", "Gainsborough",
        "Mablethorpe", "Horncastle",
    ]),
    "Northamptonshire": ("East Midlands", [
        "Northamptonshire", "Northampton", "Kettering", "Corby",
        "Wellingborough", "Daventry", "Rushden", "Towcester",
    ]),

    # ---------------- East of England ----------------
    "Norfolk": ("East of England", [
        "Norfolk", "Norwich", "Great Yarmouth", "King's Lynn", "Kings Lynn",
        "Thetford", "Dereham", "Cromer", "Wymondham", "Swaffham",
        "Fakenham", "Diss", "North Walsham", "Attleborough", "Downham Market",
    ]),
    "Suffolk": ("East of England", [
        "Suffolk", "Ipswich", "Bury St Edmunds", "Lowestoft", "Felixstowe",
        "Sudbury", "Newmarket", "Stowmarket", "Haverhill", "Woodbridge",
        "Aldeburgh", "Southwold", "Mildenhall",
    ]),
    "Cambridgeshire": ("East of England", [
        "Cambridgeshire", "Cambridge", "Peterborough", "Huntingdon", "Ely",
        "St Neots", "Wisbech", "Fenland",
    ]),
    "Essex": ("East of England", [
        "Essex", "Chelmsford", "Colchester", "Southend", "Southend-on-Sea",
        "Basildon", "Harlow", "Brentwood", "Clacton", "Braintree",
        "Witham", "Maldon", "Harwich", "Grays", "Thurrock", "Billericay",
        "Rayleigh", "Canvey Island", "Saffron Walden",
    ]),
    "Hertfordshire": ("East of England", [
        "Hertfordshire", "Watford", "St Albans", "Stevenage", "Hemel Hempstead",
        "Hatfield", "Welwyn Garden City", "Hertford", "Hitchin", "Letchworth",
        "Bishop's Stortford", "Borehamwood", "Royston",
    ]),
    "Bedfordshire": ("East of England", [
        "Bedfordshire", "Bedford", "Luton", "Dunstable", "Leighton Buzzard",
        "Biggleswade", "Ampthill",
    ]),

    # ---------------- London ----------------
    "London": ("London", [
        "London", "Westminster", "Camden", "Islington", "Hackney", "Tower Hamlets",
        "Southwark", "Lambeth", "Lewisham", "Greenwich", "Croydon", "Bromley",
        "Barnet", "Brent", "Ealing", "Hounslow", "Hillingdon", "Harrow",
        "Enfield", "Haringey", "Waltham Forest", "Redbridge", "Newham",
        "Barking", "Dagenham", "Havering", "Bexley", "Sutton", "Merton",
        "Wandsworth", "Kingston upon Thames", "Hammersmith", "Fulham",
        "Kensington", "Chelsea", "Brixton", "Peckham",
        "Stratford", "Walthamstow", "Tottenham", "Romford", "Ilford",
        "Heathrow", "Canary Wharf",
    ]),

    # ---------------- South East ----------------
    "Kent": ("South East", [
        "Kent", "Maidstone", "Canterbury", "Ashford", "Dover", "Folkestone",
        "Margate", "Ramsgate", "Broadstairs", "Thanet", "Sevenoaks",
        "Tonbridge", "Tunbridge Wells", "Dartford", "Gravesend", "Medway",
        "Chatham", "Rochester", "Gillingham", "Sittingbourne", "Faversham",
        "Whitstable", "Herne Bay", "Swanley", "Sheppey", "Sheerness",
    ]),
    "Sussex": ("South East", [
        "Sussex", "Brighton", "Hove", "Worthing", "Crawley", "Eastbourne",
        "Hastings", "Chichester", "Horsham", "Bognor Regis", "Littlehampton",
        "Lewes", "Bexhill", "Burgess Hill", "Haywards Heath", "East Grinstead",
        "Uckfield", "Rye", "Shoreham", "Seaford", "Newhaven",
    ]),
    "Surrey": ("South East", [
        "Surrey", "Guildford", "Woking", "Epsom", "Redhill", "Reigate",
        "Camberley", "Farnham", "Staines", "Leatherhead", "Godalming",
        "Weybridge", "Dorking", "Esher", "Caterham",
    ]),
    "Berkshire": ("South East", [
        "Berkshire", "Slough", "Bracknell", "Wokingham", "Newbury", "Windsor",
        "Maidenhead", "Thatcham",
    ]),
    "Hampshire": ("South East", [
        "Hampshire", "Southampton", "Portsmouth", "Winchester", "Basingstoke",
        "Eastleigh", "Fareham", "Gosport", "Havant", "Aldershot", "Farnborough",
        "Andover", "Petersfield", "Romsey", "Lymington",
        "New Forest", "Alton", "Waterlooville", "Southsea",
    ]),
    "Isle of Wight": ("South East", [
        "Isle of Wight", "Ryde", "Cowes", "Shanklin", "Sandown", "Ventnor",
    ]),
    "Oxfordshire": ("South East", [
        "Oxfordshire", "Oxford", "Banbury", "Bicester", "Abingdon", "Witney",
        "Didcot", "Henley", "Wallingford", "Thame", "Wantage", "Chipping Norton",
    ]),
    "Buckinghamshire": ("South East", [
        "Buckinghamshire", "Milton Keynes", "High Wycombe", "Aylesbury",
        "Amersham", "Beaconsfield", "Chesham", "Marlow", "Buckingham",
    ]),

    # ---------------- South West ----------------
    "Bristol & Bath": ("South West", [
        "Bristol", "Bath", "Weston-super-Mare", "North Somerset",
        "South Gloucestershire", "Keynsham", "Portishead", "Clevedon",
        "Yate", "Thornbury", "Avonmouth",
    ]),
    "Gloucestershire": ("South West", [
        "Gloucestershire", "Gloucester", "Cheltenham", "Stroud", "Cirencester",
        "Tewkesbury", "Forest of Dean", "Cotswolds", "Tetbury", "Lydney",
        "Stow-on-the-Wold", "Coleford",
    ]),
    "Wiltshire": ("South West", [
        "Wiltshire", "Swindon", "Salisbury", "Chippenham", "Trowbridge",
        "Devizes", "Malmesbury", "Marlborough", "Melksham", "Warminster",
        "Corsham", "Calne", "Royal Wootton Bassett", "Amesbury", "Bradford on Avon",
        "Westbury",
    ]),
    "Somerset": ("South West", [
        "Somerset", "Taunton", "Yeovil", "Bridgwater",
        "Frome", "Minehead", "Chard", "Burnham-on-Sea", "Shepton Mallet",
    ]),
    "Dorset": ("South West", [
        "Dorset", "Bournemouth", "Poole", "Christchurch", "Weymouth",
        "Dorchester", "Bridport", "Swanage", "Wimborne", "Blandford",
        "Sherborne", "Shaftesbury",
    ]),
    "Devon": ("South West", [
        "Devon", "Exeter", "Plymouth", "Torquay", "Paignton", "Torbay",
        "Barnstaple", "Newton Abbot", "Exmouth", "Tiverton", "Bideford",
        "Ilfracombe", "Totnes", "Dartmouth", "Okehampton", "Tavistock",
        "Brixham", "Dartmoor", "Sidmouth", "Honiton",
    ]),
    "Cornwall": ("South West", [
        "Cornwall", "Truro", "Falmouth", "Penzance", "Newquay", "St Austell",
        "Bodmin", "Camborne", "Redruth", "Launceston", "Bude", "Liskeard",
        "Helston", "St Ives", "Saltash", "Isles of Scilly",
    ]),
}

# Places to never match, because they are ordinary words or very common
# in headlines for other reasons. Kept here so nobody re-adds them by accident.
NEVER_MATCH = {
    "Reading", "March", "Deal", "Street", "Wells", "Sale", "Bury", "Ware",
    "Hope", "Eye", "Washington", "Richmond", "Wellington", "Bridgend Road",
    "Stone Age", "Nelson Mandela", "Boston Marathon", "Boston Celtics",
    "Perth Australia", "Sutton Hoo", "Hamilton musical", "Lewis Hamilton",
    "Chelsea FC", "Barry Island",
}

# Phrases that mean the place is NOT about the journalist's patch,
# e.g. a famous person's surname or a sports club playing away.
FALSE_FRIENDS = [
    "Lewis Hamilton", "Hamilton musical", "Boston Marathon", "Boston Celtics",
    "New York", "Perth, Australia", "Perth Scorchers", "Victoria Derbyshire",
    "Lord Nelson", "Leigh-on-Sea", "Newark, New Jersey",
]


def build_lookup():
    """Return {place_name: patch_area} and {patch_area: top_region}."""
    place_to_patch = {}
    patch_region = {}
    for patch, (top, places) in PATCHES.items():
        patch_region[patch] = top
        for p in places:
            if p in NEVER_MATCH:
                continue
            # First one wins if a name is listed twice
            place_to_patch.setdefault(p, patch)
    return place_to_patch, patch_region


PLACE_TO_PATCH, PATCH_REGION = build_lookup()

NATIONS = {"Scotland", "Wales"}
