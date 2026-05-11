"""
Seed list of UK news outlets covering Great Britain.

Geographic regions follow the standard UK regions plus subdivisions for Scotland and Wales.
Tiers: 'national', 'regional', 'local', 'hyperlocal', 'specialist', 'broadcast'

Email patterns use placeholders:
  {first}      - first name lowercase
  {last}       - last name lowercase
  {f}          - first initial lowercase
  {l}          - last initial lowercase
  {first.last} - shorthand for {first}.{last}
  {firstlast}  - first + last concatenated, no separator

Multiple patterns separated by | mean "try all of these in order".
'unknown' means we have no pattern; we'll guess generic fallbacks.

Group ownership matters for syndication detection: a byline appearing across many
titles in the same group in the same week is almost certainly a network reporter,
not a local staffer.
"""

OUTLETS = [
    # =========================================================================
    # NATIONAL — UK-WIDE
    # =========================================================================
    {"name": "The Guardian", "domain": "theguardian.com", "tier": "national", "region": "UK", "group": "Guardian Media Group", "email_pattern": "{first}.{last}@theguardian.com", "team_urls": ["https://www.theguardian.com/profile"], "rss": ["https://www.theguardian.com/uk/rss"]},
    {"name": "The Times", "domain": "thetimes.co.uk", "tier": "national", "region": "UK", "group": "News UK", "email_pattern": "{first}.{last}@thetimes.co.uk", "team_urls": [], "rss": ["https://www.thetimes.co.uk/rss"]},
    {"name": "The Sunday Times", "domain": "thetimes.co.uk", "tier": "national", "region": "UK", "group": "News UK", "email_pattern": "{first}.{last}@sunday-times.co.uk", "team_urls": [], "rss": []},
    {"name": "The Telegraph", "domain": "telegraph.co.uk", "tier": "national", "region": "UK", "group": "Telegraph Media Group", "email_pattern": "{first}.{last}@telegraph.co.uk", "team_urls": ["https://www.telegraph.co.uk/authors/"], "rss": ["https://www.telegraph.co.uk/rss.xml"]},
    {"name": "The Independent", "domain": "independent.co.uk", "tier": "national", "region": "UK", "group": "Independent Digital News and Media", "email_pattern": "{f}.{last}@independent.co.uk", "team_urls": ["https://www.independent.co.uk/author"], "rss": ["https://www.independent.co.uk/news/uk/rss"]},
    {"name": "The i Paper", "domain": "inews.co.uk", "tier": "national", "region": "UK", "group": "DMG Media", "email_pattern": "{first}.{last}@inews.co.uk", "team_urls": [], "rss": ["https://inews.co.uk/feed"]},
    {"name": "Daily Mail", "domain": "dailymail.co.uk", "tier": "national", "region": "UK", "group": "DMG Media", "email_pattern": "{first}.{last}@mailonline.co.uk|{first}.{last}@dailymail.co.uk", "team_urls": [], "rss": ["https://www.dailymail.co.uk/articles.rss"]},
    {"name": "The Mirror", "domain": "mirror.co.uk", "tier": "national", "region": "UK", "group": "Reach plc", "email_pattern": "{first}.{last}@mirror.co.uk|{first}.{last}@reachplc.com", "team_urls": ["https://www.mirror.co.uk/authors/"], "rss": ["https://www.mirror.co.uk/news/?service=rss"]},
    {"name": "The Sun", "domain": "thesun.co.uk", "tier": "national", "region": "UK", "group": "News UK", "email_pattern": "{first}.{last}@the-sun.co.uk|{first}.{last}@news.co.uk", "team_urls": [], "rss": ["https://www.thesun.co.uk/feed/"]},
    {"name": "Daily Express", "domain": "express.co.uk", "tier": "national", "region": "UK", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com|{first}.{last}@express.co.uk", "team_urls": ["https://www.express.co.uk/authors"], "rss": ["https://www.express.co.uk/posts/rss/1"]},
    {"name": "Daily Star", "domain": "dailystar.co.uk", "tier": "national", "region": "UK", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com|{first}.{last}@dailystar.co.uk", "team_urls": ["https://www.dailystar.co.uk/authors/"], "rss": []},
    {"name": "Financial Times", "domain": "ft.com", "tier": "national", "region": "UK", "group": "Nikkei", "email_pattern": "{first}.{last}@ft.com", "team_urls": [], "rss": ["https://www.ft.com/rss/home/uk"]},
    {"name": "The Observer", "domain": "observer.co.uk", "tier": "national", "region": "UK", "group": "Tortoise Media", "email_pattern": "{first}.{last}@observer.co.uk", "team_urls": [], "rss": []},
    {"name": "Metro", "domain": "metro.co.uk", "tier": "national", "region": "UK", "group": "DMG Media", "email_pattern": "{first}.{last}@metro.co.uk", "team_urls": ["https://metro.co.uk/author/"], "rss": ["https://metro.co.uk/feed/"]},
    {"name": "Morning Star", "domain": "morningstaronline.co.uk", "tier": "national", "region": "UK", "group": "PPPS", "email_pattern": "newsdesk@peoples-press.com", "team_urls": [], "rss": ["https://morningstaronline.co.uk/rss.xml"]},

    # =========================================================================
    # NATIONAL BROADCAST
    # =========================================================================
    {"name": "BBC News", "domain": "bbc.co.uk", "tier": "broadcast", "region": "UK", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk|{first}.{last}@bbc.com", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/rss.xml"]},
    {"name": "ITV News (National)", "domain": "itv.com", "tier": "broadcast", "region": "UK", "group": "ITV", "email_pattern": "{first}.{last}@itv.com|{first}.{last}@itn.co.uk", "team_urls": ["https://www.itv.com/news/meet-the-team"], "rss": []},
    {"name": "ITV News London", "domain": "itv.com", "tier": "broadcast", "region": "London", "group": "ITV", "email_pattern": "{first}.{last}@itv.com", "team_urls": [], "rss": []},
    {"name": "ITV News Granada", "domain": "itv.com", "tier": "broadcast", "region": "North West", "group": "ITV", "email_pattern": "{first}.{last}@itv.com", "team_urls": [], "rss": []},
    {"name": "ITV News Tyne Tees", "domain": "itv.com", "tier": "broadcast", "region": "North East", "group": "ITV", "email_pattern": "{first}.{last}@itv.com", "team_urls": [], "rss": []},
    {"name": "ITV News Calendar", "domain": "itv.com", "tier": "broadcast", "region": "Yorkshire", "group": "ITV", "email_pattern": "{first}.{last}@itv.com", "team_urls": [], "rss": []},
    {"name": "ITV News Anglia", "domain": "itv.com", "tier": "broadcast", "region": "East of England", "group": "ITV", "email_pattern": "{first}.{last}@itv.com", "team_urls": [], "rss": []},
    {"name": "ITV News Central", "domain": "itv.com", "tier": "broadcast", "region": "Midlands", "group": "ITV", "email_pattern": "{first}.{last}@itv.com", "team_urls": [], "rss": []},
    {"name": "ITV News Meridian", "domain": "itv.com", "tier": "broadcast", "region": "South East", "group": "ITV", "email_pattern": "{first}.{last}@itv.com", "team_urls": [], "rss": []},
    {"name": "ITV News West Country", "domain": "itv.com", "tier": "broadcast", "region": "South West", "group": "ITV", "email_pattern": "{first}.{last}@itv.com", "team_urls": [], "rss": []},
    {"name": "ITV News Border", "domain": "itv.com", "tier": "broadcast", "region": "North West - Cumbria/Borders", "group": "ITV", "email_pattern": "{first}.{last}@itv.com", "team_urls": [], "rss": []},
    {"name": "Channel 4 News", "domain": "channel4.com", "tier": "broadcast", "region": "UK", "group": "ITN", "email_pattern": "{first}.{last}@itn.co.uk", "team_urls": [], "rss": []},
    {"name": "Channel 5 News", "domain": "channel5.com", "tier": "broadcast", "region": "UK", "group": "ITN", "email_pattern": "{first}.{last}@itn.co.uk|{first}.{last}@channel5.com", "team_urls": [], "rss": []},
    {"name": "Sky News", "domain": "news.sky.com", "tier": "broadcast", "region": "UK", "group": "Sky/Comcast", "email_pattern": "{first}.{last}@sky.uk", "team_urls": [], "rss": ["https://feeds.skynews.com/feeds/rss/uk.xml"]},
    {"name": "GB News", "domain": "gbnews.com", "tier": "broadcast", "region": "UK", "group": "GB News", "email_pattern": "{first}.{last}@gbnews.com", "team_urls": [], "rss": []},
    {"name": "LBC", "domain": "lbc.co.uk", "tier": "broadcast", "region": "UK", "group": "Global", "email_pattern": "{first}.{last}@global.com", "team_urls": [], "rss": []},
    {"name": "TalkTV", "domain": "talk.tv", "tier": "broadcast", "region": "UK", "group": "News UK", "email_pattern": "{first}.{last}@news.co.uk", "team_urls": [], "rss": []},

    # =========================================================================
    # SCOTLAND
    # =========================================================================
    {"name": "The Herald", "domain": "heraldscotland.com", "tier": "regional", "region": "Scotland", "group": "Newsquest", "email_pattern": "{first}.{last}@heraldscotland.com|{first}.{last}@newsquest.co.uk", "team_urls": ["https://www.heraldscotland.com/author/profile/"], "rss": ["https://www.heraldscotland.com/news/rss/"]},
    {"name": "The Scotsman", "domain": "scotsman.com", "tier": "regional", "region": "Scotland", "group": "National World", "email_pattern": "{first}.{last}@scotsman.com|{first}.{last}@nationalworld.com", "team_urls": [], "rss": ["https://www.scotsman.com/rss"]},
    {"name": "The National", "domain": "thenational.scot", "tier": "regional", "region": "Scotland", "group": "Newsquest", "email_pattern": "{first}.{last}@thenational.scot|{first}.{last}@newsquest.co.uk", "team_urls": ["https://www.thenational.scot/author/profile/"], "rss": ["https://www.thenational.scot/news/rss/"]},
    {"name": "Daily Record", "domain": "dailyrecord.co.uk", "tier": "regional", "region": "Scotland", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com|{first}.{last}@dailyrecord.co.uk", "team_urls": ["https://www.dailyrecord.co.uk/authors/"], "rss": ["https://www.dailyrecord.co.uk/?service=rss"]},
    {"name": "The Press and Journal", "domain": "pressandjournal.co.uk", "tier": "regional", "region": "Scotland - Aberdeen/North", "group": "DC Thomson", "email_pattern": "{first}.{last}@pressandjournal.co.uk|{first}.{last}@dctmedia.co.uk", "team_urls": [], "rss": ["https://www.pressandjournal.co.uk/feed/"]},
    {"name": "The Courier", "domain": "thecourier.co.uk", "tier": "regional", "region": "Scotland - Dundee/Tayside", "group": "DC Thomson", "email_pattern": "{first}.{last}@thecourier.co.uk|{first}.{last}@dctmedia.co.uk", "team_urls": [], "rss": ["https://www.thecourier.co.uk/feed/"]},
    {"name": "Edinburgh Evening News", "domain": "edinburghnews.scotsman.com", "tier": "local", "region": "Scotland - Edinburgh", "group": "National World", "email_pattern": "{first}.{last}@scotsman.com", "team_urls": [], "rss": []},
    {"name": "Glasgow Times", "domain": "glasgowtimes.co.uk", "tier": "local", "region": "Scotland - Glasgow", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": ["https://www.glasgowtimes.co.uk/news/rss/"]},
    {"name": "BBC Scotland", "domain": "bbc.co.uk", "tier": "broadcast", "region": "Scotland", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/scotland/rss.xml"]},
    {"name": "STV News", "domain": "stv.tv", "tier": "broadcast", "region": "Scotland", "group": "STV", "email_pattern": "{first}.{last}@stv.tv", "team_urls": [], "rss": []},
    {"name": "The Ferret", "domain": "theferret.scot", "tier": "specialist", "region": "Scotland", "group": "Independent", "email_pattern": "{first}@theferret.scot|hello@theferret.scot", "team_urls": ["https://theferret.scot/about/"], "rss": ["https://theferret.scot/feed/"]},
    {"name": "Bella Caledonia", "domain": "bellacaledonia.org.uk", "tier": "specialist", "region": "Scotland", "group": "Independent", "email_pattern": "unknown", "team_urls": [], "rss": []},
    {"name": "The Shetland Times", "domain": "shetlandtimes.co.uk", "tier": "hyperlocal", "region": "Scotland - Shetland", "group": "Independent", "email_pattern": "editorial@shetlandtimes.co.uk", "team_urls": [], "rss": []},
    {"name": "The Orcadian", "domain": "orcadian.co.uk", "tier": "hyperlocal", "region": "Scotland - Orkney", "group": "Orkney Media Group", "email_pattern": "news@orcadian.co.uk", "team_urls": [], "rss": []},
    {"name": "West Highland Free Press", "domain": "whfp.com", "tier": "hyperlocal", "region": "Scotland - Highlands & Islands", "group": "Independent", "email_pattern": "editor@whfp.com", "team_urls": [], "rss": []},
    {"name": "Stornoway Gazette", "domain": "stornowaygazette.co.uk", "tier": "hyperlocal", "region": "Scotland - Western Isles", "group": "National World", "email_pattern": "{first}.{last}@nationalworld.com", "team_urls": [], "rss": []},
    {"name": "John o'Groat Journal", "domain": "johnogroat-journal.co.uk", "tier": "hyperlocal", "region": "Scotland - Caithness", "group": "Highland News & Media", "email_pattern": "editor@nornews.co.uk", "team_urls": [], "rss": []},
    {"name": "Inverness Courier", "domain": "inverness-courier.co.uk", "tier": "local", "region": "Scotland - Highlands", "group": "Highland News & Media", "email_pattern": "editor@hnmedia.co.uk", "team_urls": [], "rss": []},
    {"name": "Dumfries and Galloway Standard", "domain": "dailyrecord.co.uk/dumfries-galloway", "tier": "local", "region": "Scotland - Dumfries & Galloway", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": [], "rss": []},

    # =========================================================================
    # WALES
    # =========================================================================
    {"name": "WalesOnline", "domain": "walesonline.co.uk", "tier": "regional", "region": "Wales", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com|{first}.{last}@walesonline.co.uk|{first}.{last}@mediawales.co.uk", "team_urls": ["https://www.walesonline.co.uk/authors/"], "rss": ["https://www.walesonline.co.uk/news/?service=rss"]},
    {"name": "Western Mail", "domain": "walesonline.co.uk", "tier": "regional", "region": "Wales", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": [], "rss": []},
    {"name": "Daily Post (North Wales)", "domain": "dailypost.co.uk", "tier": "regional", "region": "Wales - North", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com|{first}.{last}@dailypost.co.uk", "team_urls": ["https://www.dailypost.co.uk/authors/"], "rss": ["https://www.dailypost.co.uk/news/?service=rss"]},
    {"name": "Nation.Cymru", "domain": "nation.cymru", "tier": "regional", "region": "Wales", "group": "Independent", "email_pattern": "{first}@nation.cymru|news@nation.cymru", "team_urls": ["https://nation.cymru/about/"], "rss": ["https://nation.cymru/feed/"]},
    {"name": "BBC Wales", "domain": "bbc.co.uk", "tier": "broadcast", "region": "Wales", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/wales/rss.xml"]},
    {"name": "ITV Wales", "domain": "itv.com/news/wales", "tier": "broadcast", "region": "Wales", "group": "ITV", "email_pattern": "{first}.{last}@itv.com", "team_urls": [], "rss": []},
    {"name": "The Pembrokeshire Herald", "domain": "pembrokeshire-herald.com", "tier": "hyperlocal", "region": "Wales - Pembrokeshire", "group": "Herald", "email_pattern": "newsdesk@pembrokeshire-herald.com", "team_urls": [], "rss": []},
    {"name": "Cambrian News", "domain": "cambrian-news.co.uk", "tier": "local", "region": "Wales - Mid", "group": "Tindle", "email_pattern": "newsdesk@cambrian-news.co.uk", "team_urls": [], "rss": []},
    {"name": "South Wales Argus", "domain": "southwalesargus.co.uk", "tier": "local", "region": "Wales - Newport/Gwent", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": ["https://www.southwalesargus.co.uk/news/rss/"]},
    {"name": "Caerphilly Observer", "domain": "caerphilly.observer", "tier": "hyperlocal", "region": "Wales - Caerphilly", "group": "Independent", "email_pattern": "news@caerphilly.observer", "team_urls": [], "rss": []},
    {"name": "Y Cymro", "domain": "ycymro.cymru", "tier": "specialist", "region": "Wales", "group": "Independent", "email_pattern": "golygydd@ycymro.cymru", "team_urls": [], "rss": []},
    {"name": "Golwg", "domain": "golwg.360.cymru", "tier": "specialist", "region": "Wales", "group": "Golwg", "email_pattern": "newyddion@golwg.cymru", "team_urls": [], "rss": []},

    # =========================================================================
    # NORTH EAST ENGLAND
    # =========================================================================
    {"name": "ChronicleLive (Newcastle)", "domain": "chroniclelive.co.uk", "tier": "regional", "region": "North East", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com|{first}.{last}@trinitymirror.com", "team_urls": ["https://www.chroniclelive.co.uk/authors/"], "rss": ["https://www.chroniclelive.co.uk/news/?service=rss"]},
    {"name": "The Northern Echo", "domain": "thenorthernecho.co.uk", "tier": "regional", "region": "North East", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk|{first}.{last}@nne.co.uk", "team_urls": [], "rss": ["https://www.thenorthernecho.co.uk/news/rss/"]},
    {"name": "TeessideLive", "domain": "gazettelive.co.uk", "tier": "local", "region": "North East - Teesside", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.gazettelive.co.uk/authors/"], "rss": ["https://www.gazettelive.co.uk/news/?service=rss"]},
    {"name": "The Shields Gazette", "domain": "shieldsgazette.com", "tier": "local", "region": "North East - South Tyneside", "group": "National World", "email_pattern": "{first}.{last}@nationalworld.com", "team_urls": [], "rss": []},
    {"name": "Sunderland Echo", "domain": "sunderlandecho.com", "tier": "local", "region": "North East - Sunderland", "group": "National World", "email_pattern": "{first}.{last}@nationalworld.com", "team_urls": [], "rss": []},
    {"name": "Hartlepool Mail", "domain": "hartlepoolmail.co.uk", "tier": "local", "region": "North East - Hartlepool", "group": "National World", "email_pattern": "{first}.{last}@nationalworld.com", "team_urls": [], "rss": []},
    {"name": "BBC Newcastle", "domain": "bbc.co.uk", "tier": "broadcast", "region": "North East", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/tyne_and_wear/rss.xml"]},

    # =========================================================================
    # NORTH WEST ENGLAND
    # =========================================================================
    {"name": "Manchester Evening News", "domain": "manchestereveningnews.co.uk", "tier": "regional", "region": "North West - Greater Manchester", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com|{first}.{last}@men-news.co.uk", "team_urls": ["https://www.manchestereveningnews.co.uk/authors/"], "rss": ["https://www.manchestereveningnews.co.uk/news/?service=rss"]},
    {"name": "Liverpool Echo", "domain": "liverpoolecho.co.uk", "tier": "regional", "region": "North West - Merseyside", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com|{first}.{last}@liverpool.com", "team_urls": ["https://www.liverpoolecho.co.uk/authors/"], "rss": ["https://www.liverpoolecho.co.uk/news/?service=rss"]},
    {"name": "Lancashire Telegraph", "domain": "lancashiretelegraph.co.uk", "tier": "regional", "region": "North West - Lancashire", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": ["https://www.lancashiretelegraph.co.uk/news/rss/"]},
    {"name": "LancsLive", "domain": "lancs.live", "tier": "regional", "region": "North West - Lancashire", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.lancs.live/authors/"], "rss": ["https://www.lancs.live/news/?service=rss"]},
    {"name": "CheshireLive", "domain": "cheshire-live.co.uk", "tier": "local", "region": "North West - Cheshire", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.cheshire-live.co.uk/authors/"], "rss": []},
    {"name": "The Bolton News", "domain": "theboltonnews.co.uk", "tier": "local", "region": "North West - Bolton", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": ["https://www.theboltonnews.co.uk/news/rss/"]},
    {"name": "Lancashire Post", "domain": "lep.co.uk", "tier": "local", "region": "North West - Preston", "group": "National World", "email_pattern": "{first}.{last}@nationalworld.com|{first}.{last}@jpress.co.uk", "team_urls": [], "rss": []},
    {"name": "Blackpool Gazette", "domain": "blackpoolgazette.co.uk", "tier": "local", "region": "North West - Blackpool", "group": "National World", "email_pattern": "{first}.{last}@nationalworld.com", "team_urls": [], "rss": []},
    {"name": "News and Star (Carlisle)", "domain": "newsandstar.co.uk", "tier": "local", "region": "North West - Cumbria", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk|{first}.{last}@cnmedia.co.uk", "team_urls": [], "rss": []},
    {"name": "Westmorland Gazette", "domain": "thewestmorlandgazette.co.uk", "tier": "local", "region": "North West - Cumbria", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": ["https://www.thewestmorlandgazette.co.uk/news/rss/"]},
    {"name": "BBC North West", "domain": "bbc.co.uk", "tier": "broadcast", "region": "North West", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/manchester/rss.xml"]},
    {"name": "The Mill (Manchester)", "domain": "manchestermill.co.uk", "tier": "specialist", "region": "North West - Manchester", "group": "Mill Media", "email_pattern": "{first}@manchestermill.co.uk", "team_urls": ["https://manchestermill.co.uk/about"], "rss": ["https://manchestermill.co.uk/feed"]},
    {"name": "The Post (Liverpool)", "domain": "liverpoolpost.co.uk", "tier": "specialist", "region": "North West - Liverpool", "group": "Mill Media", "email_pattern": "{first}@liverpoolpost.co.uk", "team_urls": [], "rss": ["https://liverpoolpost.co.uk/feed"]},

    # =========================================================================
    # YORKSHIRE & THE HUMBER
    # =========================================================================
    {"name": "Yorkshire Post", "domain": "yorkshirepost.co.uk", "tier": "regional", "region": "Yorkshire", "group": "National World", "email_pattern": "{first}.{last}@nationalworld.com|{first}.{last}@ypn.co.uk", "team_urls": [], "rss": ["https://www.yorkshirepost.co.uk/rss"]},
    {"name": "Yorkshire Evening Post", "domain": "yorkshireeveningpost.co.uk", "tier": "regional", "region": "Yorkshire - Leeds", "group": "National World", "email_pattern": "{first}.{last}@nationalworld.com", "team_urls": [], "rss": []},
    {"name": "LeedsLive", "domain": "leeds-live.co.uk", "tier": "local", "region": "Yorkshire - Leeds", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.leeds-live.co.uk/authors/"], "rss": ["https://www.leeds-live.co.uk/news/?service=rss"]},
    {"name": "The Star (Sheffield)", "domain": "thestar.co.uk", "tier": "local", "region": "Yorkshire - Sheffield", "group": "National World", "email_pattern": "{first}.{last}@nationalworld.com", "team_urls": [], "rss": []},
    {"name": "Telegraph & Argus (Bradford)", "domain": "thetelegraphandargus.co.uk", "tier": "local", "region": "Yorkshire - Bradford", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": ["https://www.thetelegraphandargus.co.uk/news/rss/"]},
    {"name": "Hull Daily Mail", "domain": "hulldailymail.co.uk", "tier": "local", "region": "Yorkshire - Hull/Humber", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.hulldailymail.co.uk/authors/"], "rss": []},
    {"name": "York Press", "domain": "yorkpress.co.uk", "tier": "local", "region": "Yorkshire - York", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": ["https://www.yorkpress.co.uk/news/rss/"]},
    {"name": "Examiner Live (Huddersfield)", "domain": "examinerlive.co.uk", "tier": "local", "region": "Yorkshire - Huddersfield", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.examinerlive.co.uk/authors/"], "rss": []},
    {"name": "Doncaster Free Press", "domain": "doncasterfreepress.co.uk", "tier": "local", "region": "Yorkshire - Doncaster", "group": "National World", "email_pattern": "{first}.{last}@nationalworld.com", "team_urls": [], "rss": []},
    {"name": "Grimsby Live", "domain": "grimsbytelegraph.co.uk", "tier": "local", "region": "Yorkshire - Grimsby", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": [], "rss": []},
    {"name": "Scarborough News", "domain": "thescarboroughnews.co.uk", "tier": "local", "region": "Yorkshire - Scarborough", "group": "National World", "email_pattern": "{first}.{last}@nationalworld.com", "team_urls": [], "rss": []},
    {"name": "BBC Yorkshire", "domain": "bbc.co.uk", "tier": "broadcast", "region": "Yorkshire", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/leeds/rss.xml"]},
    {"name": "The Tribune (Sheffield)", "domain": "sheffieldtribune.co.uk", "tier": "specialist", "region": "Yorkshire - Sheffield", "group": "Mill Media", "email_pattern": "{first}@sheffieldtribune.co.uk", "team_urls": [], "rss": ["https://sheffieldtribune.co.uk/feed"]},

    # =========================================================================
    # WEST MIDLANDS
    # =========================================================================
    {"name": "Birmingham Mail", "domain": "birminghammail.co.uk", "tier": "regional", "region": "West Midlands - Birmingham", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com|{first}.{last}@birminghammail.co.uk", "team_urls": ["https://www.birminghammail.co.uk/authors/"], "rss": ["https://www.birminghammail.co.uk/news/?service=rss"]},
    {"name": "BirminghamLive", "domain": "birminghammail.co.uk", "tier": "regional", "region": "West Midlands", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": [], "rss": []},
    {"name": "Express & Star", "domain": "expressandstar.com", "tier": "regional", "region": "West Midlands - Wolverhampton", "group": "MNA", "email_pattern": "{first}.{last}@expressandstar.co.uk|newsdesk@expressandstar.co.uk", "team_urls": [], "rss": ["https://www.expressandstar.com/news/feed/"]},
    {"name": "Coventry Telegraph", "domain": "coventrytelegraph.net", "tier": "local", "region": "West Midlands - Coventry", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.coventrytelegraph.net/authors/"], "rss": ["https://www.coventrytelegraph.net/news/?service=rss"]},
    {"name": "Worcester News", "domain": "worcesternews.co.uk", "tier": "local", "region": "West Midlands - Worcester", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": ["https://www.worcesternews.co.uk/news/rss/"]},
    {"name": "Stoke Sentinel", "domain": "stokesentinel.co.uk", "tier": "local", "region": "West Midlands - Staffordshire", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.stokesentinel.co.uk/authors/"], "rss": []},
    {"name": "Shropshire Star", "domain": "shropshirestar.com", "tier": "local", "region": "West Midlands - Shropshire", "group": "MNA", "email_pattern": "{first}.{last}@shropshirestar.co.uk", "team_urls": [], "rss": ["https://www.shropshirestar.com/news/feed/"]},
    {"name": "Hereford Times", "domain": "herefordtimes.com", "tier": "local", "region": "West Midlands - Herefordshire", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": ["https://www.herefordtimes.com/news/rss/"]},
    {"name": "Warwickshire World", "domain": "warwickshireworld.com", "tier": "local", "region": "West Midlands - Warwickshire", "group": "National World", "email_pattern": "{first}.{last}@nationalworld.com", "team_urls": [], "rss": []},
    {"name": "BBC Birmingham/WM", "domain": "bbc.co.uk", "tier": "broadcast", "region": "West Midlands", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/birmingham_and_black_country/rss.xml"]},
    {"name": "The Dispatch (Birmingham)", "domain": "birminghamdispatch.co.uk", "tier": "specialist", "region": "West Midlands - Birmingham", "group": "Mill Media", "email_pattern": "{first}@birminghamdispatch.co.uk", "team_urls": [], "rss": []},

    # =========================================================================
    # EAST MIDLANDS
    # =========================================================================
    {"name": "Nottingham Post", "domain": "nottinghampost.com", "tier": "regional", "region": "East Midlands - Nottingham", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.nottinghampost.com/authors/"], "rss": ["https://www.nottinghampost.com/news/?service=rss"]},
    {"name": "Leicester Mercury", "domain": "leicestermercury.co.uk", "tier": "regional", "region": "East Midlands - Leicester", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.leicestermercury.co.uk/authors/"], "rss": []},
    {"name": "Derby Telegraph", "domain": "derbytelegraph.co.uk", "tier": "regional", "region": "East Midlands - Derby", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.derbytelegraph.co.uk/authors/"], "rss": []},
    {"name": "Lincolnshire Live", "domain": "lincolnshirelive.co.uk", "tier": "regional", "region": "East Midlands - Lincolnshire", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.lincolnshirelive.co.uk/authors/"], "rss": []},
    {"name": "Northamptonshire Telegraph", "domain": "northantstelegraph.co.uk", "tier": "local", "region": "East Midlands - Northamptonshire", "group": "National World", "email_pattern": "{first}.{last}@nationalworld.com", "team_urls": [], "rss": []},
    {"name": "Northampton Chronicle", "domain": "northamptonchron.co.uk", "tier": "local", "region": "East Midlands - Northampton", "group": "National World", "email_pattern": "{first}.{last}@nationalworld.com", "team_urls": [], "rss": []},
    {"name": "Lincolnshire Echo", "domain": "lincolnshirelive.co.uk", "tier": "local", "region": "East Midlands - Lincoln", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": [], "rss": []},
    {"name": "BBC East Midlands", "domain": "bbc.co.uk", "tier": "broadcast", "region": "East Midlands", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/nottingham/rss.xml"]},

    # =========================================================================
    # EAST OF ENGLAND
    # =========================================================================
    {"name": "Eastern Daily Press", "domain": "edp24.co.uk", "tier": "regional", "region": "East of England - Norfolk", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk|{first}.{last}@archant.co.uk", "team_urls": [], "rss": []},
    {"name": "East Anglian Daily Times", "domain": "eadt.co.uk", "tier": "regional", "region": "East of England - Suffolk", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": []},
    {"name": "Cambridge News", "domain": "cambridge-news.co.uk", "tier": "regional", "region": "East of England - Cambridgeshire", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.cambridge-news.co.uk/authors/"], "rss": []},
    {"name": "EssexLive", "domain": "essexlive.news", "tier": "regional", "region": "East of England - Essex", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.essexlive.news/authors/"], "rss": ["https://www.essexlive.news/news/?service=rss"]},
    {"name": "HertsLive", "domain": "hertfordshiremercury.co.uk", "tier": "regional", "region": "East of England - Hertfordshire", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": [], "rss": []},
    {"name": "BedfordshireLive", "domain": "bedfordshirelive.co.uk", "tier": "regional", "region": "East of England - Bedfordshire", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": [], "rss": []},
    {"name": "Norwich Evening News", "domain": "eveningnews24.co.uk", "tier": "local", "region": "East of England - Norwich", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": []},
    {"name": "Ipswich Star", "domain": "ipswichstar.co.uk", "tier": "local", "region": "East of England - Ipswich", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": []},
    {"name": "Peterborough Telegraph", "domain": "peterboroughtoday.co.uk", "tier": "local", "region": "East of England - Peterborough", "group": "National World", "email_pattern": "{first}.{last}@nationalworld.com", "team_urls": [], "rss": []},
    {"name": "BBC East", "domain": "bbc.co.uk", "tier": "broadcast", "region": "East of England", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/cambridgeshire/rss.xml"]},

    # =========================================================================
    # LONDON
    # =========================================================================
    {"name": "Evening Standard", "domain": "standard.co.uk", "tier": "regional", "region": "London", "group": "Evgeny Lebedev/DMG", "email_pattern": "{first}.{last}@standard.co.uk|{first}.{last}@eslmedia.co.uk", "team_urls": [], "rss": ["https://www.standard.co.uk/rss/news"]},
    {"name": "MyLondon", "domain": "mylondon.news", "tier": "regional", "region": "London", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.mylondon.news/authors/"], "rss": ["https://www.mylondon.news/news/?service=rss"]},
    {"name": "Time Out London", "domain": "timeout.com/london", "tier": "specialist", "region": "London", "group": "Time Out", "email_pattern": "{first}.{last}@timeout.com", "team_urls": [], "rss": []},
    {"name": "City AM", "domain": "cityam.com", "tier": "specialist", "region": "London", "group": "City AM", "email_pattern": "{first}.{last}@cityam.com", "team_urls": [], "rss": ["https://www.cityam.com/feed/"]},
    {"name": "BBC London", "domain": "bbc.co.uk", "tier": "broadcast", "region": "London", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/london/rss.xml"]},
    {"name": "The Londoner", "domain": "thelondoner.co.uk", "tier": "specialist", "region": "London", "group": "Mill Media", "email_pattern": "{first}@thelondoner.co.uk", "team_urls": [], "rss": []},
    {"name": "Hackney Citizen", "domain": "hackneycitizen.co.uk", "tier": "hyperlocal", "region": "London - Hackney", "group": "Independent", "email_pattern": "newsdesk@hackneycitizen.co.uk", "team_urls": [], "rss": ["https://www.hackneycitizen.co.uk/feed/"]},
    {"name": "Brixton Blog/Buzz", "domain": "brixtonbuzz.com", "tier": "hyperlocal", "region": "London - Lambeth", "group": "Independent", "email_pattern": "info@brixtonbuzz.com", "team_urls": [], "rss": []},

    # =========================================================================
    # SOUTH EAST ENGLAND
    # =========================================================================
    {"name": "KentLive", "domain": "kentlive.news", "tier": "regional", "region": "South East - Kent", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.kentlive.news/authors/"], "rss": ["https://www.kentlive.news/news/?service=rss"]},
    {"name": "Kent Online", "domain": "kentonline.co.uk", "tier": "regional", "region": "South East - Kent", "group": "KM Media", "email_pattern": "{first}.{last}@thekmgroup.co.uk", "team_urls": [], "rss": ["https://www.kentonline.co.uk/rss"]},
    {"name": "The Argus (Brighton)", "domain": "theargus.co.uk", "tier": "regional", "region": "South East - Sussex", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": ["https://www.theargus.co.uk/news/rss/"]},
    {"name": "SussexLive", "domain": "sussexlive.co.uk", "tier": "regional", "region": "South East - Sussex", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": [], "rss": []},
    {"name": "Surrey Live", "domain": "getsurrey.co.uk", "tier": "regional", "region": "South East - Surrey", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.getsurrey.co.uk/authors/"], "rss": []},
    {"name": "BerkshireLive", "domain": "getreading.co.uk", "tier": "regional", "region": "South East - Berkshire", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": [], "rss": []},
    {"name": "HampshireLive", "domain": "hampshirelive.news", "tier": "regional", "region": "South East - Hampshire", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": [], "rss": []},
    {"name": "The News (Portsmouth)", "domain": "portsmouth.co.uk", "tier": "local", "region": "South East - Portsmouth", "group": "National World", "email_pattern": "{first}.{last}@nationalworld.com", "team_urls": [], "rss": []},
    {"name": "Daily Echo (Southampton)", "domain": "dailyecho.co.uk", "tier": "local", "region": "South East - Southampton", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": ["https://www.dailyecho.co.uk/news/rss/"]},
    {"name": "Oxford Mail", "domain": "oxfordmail.co.uk", "tier": "local", "region": "South East - Oxfordshire", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": ["https://www.oxfordmail.co.uk/news/rss/"]},
    {"name": "Buckinghamshire Live", "domain": "buckinghamshirelive.com", "tier": "local", "region": "South East - Buckinghamshire", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": [], "rss": []},
    {"name": "Isle of Wight County Press", "domain": "iwcp.co.uk", "tier": "local", "region": "South East - Isle of Wight", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": []},
    {"name": "BBC South East", "domain": "bbc.co.uk", "tier": "broadcast", "region": "South East", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/sussex/rss.xml"]},

    # =========================================================================
    # SOUTH WEST ENGLAND
    # =========================================================================
    {"name": "Bristol Post / BristolLive", "domain": "bristolpost.co.uk", "tier": "regional", "region": "South West - Bristol", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.bristolpost.co.uk/authors/"], "rss": ["https://www.bristolpost.co.uk/news/?service=rss"]},
    {"name": "Plymouth Live", "domain": "plymouthherald.co.uk", "tier": "regional", "region": "South West - Plymouth", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.plymouthherald.co.uk/authors/"], "rss": []},
    {"name": "DevonLive", "domain": "devonlive.com", "tier": "regional", "region": "South West - Devon", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.devonlive.com/authors/"], "rss": []},
    {"name": "CornwallLive", "domain": "cornwalllive.com", "tier": "regional", "region": "South West - Cornwall", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": ["https://www.cornwalllive.com/authors/"], "rss": []},
    {"name": "Somerset Live", "domain": "somersetlive.co.uk", "tier": "regional", "region": "South West - Somerset", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": [], "rss": []},
    {"name": "Gloucestershire Live", "domain": "gloucestershirelive.co.uk", "tier": "regional", "region": "South West - Gloucestershire", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": [], "rss": []},
    {"name": "Dorset Echo", "domain": "dorsetecho.co.uk", "tier": "local", "region": "South West - Dorset", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": ["https://www.dorsetecho.co.uk/news/rss/"]},
    {"name": "Wiltshire Times", "domain": "wiltshiretimes.co.uk", "tier": "local", "region": "South West - Wiltshire", "group": "Newsquest", "email_pattern": "{first}.{last}@newsquest.co.uk", "team_urls": [], "rss": []},
    {"name": "Western Daily Press", "domain": "westerndailypress.co.uk", "tier": "regional", "region": "South West", "group": "Reach plc", "email_pattern": "{first}.{last}@reachplc.com", "team_urls": [], "rss": []},
    {"name": "BBC South West", "domain": "bbc.co.uk", "tier": "broadcast", "region": "South West", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/devon/rss.xml"]},
    {"name": "BBC Cumbria", "domain": "bbc.co.uk", "tier": "broadcast", "region": "North West - Cumbria", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/cumbria/rss.xml"]},
    {"name": "BBC Lancashire", "domain": "bbc.co.uk", "tier": "broadcast", "region": "North West - Lancashire", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/lancashire/rss.xml"]},
    {"name": "BBC Merseyside", "domain": "bbc.co.uk", "tier": "broadcast", "region": "North West - Merseyside", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/merseyside/rss.xml"]},
    {"name": "BBC Tees", "domain": "bbc.co.uk", "tier": "broadcast", "region": "North East - Teesside", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/tees/rss.xml"]},
    {"name": "BBC Humberside", "domain": "bbc.co.uk", "tier": "broadcast", "region": "Yorkshire - Hull/Humber", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/humberside/rss.xml"]},
    {"name": "BBC Sheffield/South Yorkshire", "domain": "bbc.co.uk", "tier": "broadcast", "region": "Yorkshire - Sheffield", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/south_yorkshire/rss.xml"]},
    {"name": "BBC Stoke & Staffordshire", "domain": "bbc.co.uk", "tier": "broadcast", "region": "West Midlands - Staffordshire", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/stoke_and_staffordshire/rss.xml"]},
    {"name": "BBC Hereford & Worcester", "domain": "bbc.co.uk", "tier": "broadcast", "region": "West Midlands - Herefordshire/Worcestershire", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/hereford_and_worcester/rss.xml"]},
    {"name": "BBC Coventry & Warwickshire", "domain": "bbc.co.uk", "tier": "broadcast", "region": "West Midlands - Coventry", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/coventry_and_warwickshire/rss.xml"]},
    {"name": "BBC Derby", "domain": "bbc.co.uk", "tier": "broadcast", "region": "East Midlands - Derby", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/derby/rss.xml"]},
    {"name": "BBC Leicester", "domain": "bbc.co.uk", "tier": "broadcast", "region": "East Midlands - Leicester", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/leicester/rss.xml"]},
    {"name": "BBC Lincolnshire", "domain": "bbc.co.uk", "tier": "broadcast", "region": "East Midlands - Lincolnshire", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/lincolnshire/rss.xml"]},
    {"name": "BBC Northampton", "domain": "bbc.co.uk", "tier": "broadcast", "region": "East Midlands - Northamptonshire", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/northamptonshire/rss.xml"]},
    {"name": "BBC Norfolk", "domain": "bbc.co.uk", "tier": "broadcast", "region": "East of England - Norfolk", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/norfolk/rss.xml"]},
    {"name": "BBC Suffolk", "domain": "bbc.co.uk", "tier": "broadcast", "region": "East of England - Suffolk", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/suffolk/rss.xml"]},
    {"name": "BBC Three Counties", "domain": "bbc.co.uk", "tier": "broadcast", "region": "East of England - Beds/Herts/Bucks", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/beds_bucks_and_herts/rss.xml"]},
    {"name": "BBC Essex", "domain": "bbc.co.uk", "tier": "broadcast", "region": "East of England - Essex", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/essex/rss.xml"]},
    {"name": "BBC Kent", "domain": "bbc.co.uk", "tier": "broadcast", "region": "South East - Kent", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/kent/rss.xml"]},
    {"name": "BBC Surrey", "domain": "bbc.co.uk", "tier": "broadcast", "region": "South East - Surrey", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/surrey/rss.xml"]},
    {"name": "BBC Berkshire", "domain": "bbc.co.uk", "tier": "broadcast", "region": "South East - Berkshire", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/berkshire/rss.xml"]},
    {"name": "BBC Oxford", "domain": "bbc.co.uk", "tier": "broadcast", "region": "South East - Oxfordshire", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/oxford/rss.xml"]},
    {"name": "BBC Hampshire", "domain": "bbc.co.uk", "tier": "broadcast", "region": "South East - Hampshire", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/hampshire/rss.xml"]},
    {"name": "BBC Sussex", "domain": "bbc.co.uk", "tier": "broadcast", "region": "South East - Sussex", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/sussex/rss.xml"]},
    {"name": "BBC Wiltshire", "domain": "bbc.co.uk", "tier": "broadcast", "region": "South West - Wiltshire", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/wiltshire/rss.xml"]},
    {"name": "BBC Bristol", "domain": "bbc.co.uk", "tier": "broadcast", "region": "South West - Bristol", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/bristol/rss.xml"]},
    {"name": "BBC Somerset", "domain": "bbc.co.uk", "tier": "broadcast", "region": "South West - Somerset", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/somerset/rss.xml"]},
    {"name": "BBC Gloucester", "domain": "bbc.co.uk", "tier": "broadcast", "region": "South West - Gloucestershire", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/gloucestershire/rss.xml"]},
    {"name": "BBC Cornwall", "domain": "bbc.co.uk", "tier": "broadcast", "region": "South West - Cornwall", "group": "BBC", "email_pattern": "{first}.{last}@bbc.co.uk", "team_urls": [], "rss": ["http://feeds.bbci.co.uk/news/england/cornwall/rss.xml"]},
    {"name": "The Bristol Cable", "domain": "thebristolcable.org", "tier": "specialist", "region": "South West - Bristol", "group": "Co-operative", "email_pattern": "{first}@thebristolcable.org", "team_urls": ["https://thebristolcable.org/team/"], "rss": ["https://thebristolcable.org/feed/"]},

    # =========================================================================
    # SPECIALIST / INVESTIGATIVE / ENVIRONMENT
    # (relevant to Rupert's GBF work)
    # =========================================================================
    {"name": "ENDS Report", "domain": "endsreport.com", "tier": "specialist", "region": "UK", "group": "Haymarket", "email_pattern": "{first}.{last}@haymarket.com", "team_urls": [], "rss": []},
    {"name": "Resource (waste/recycling)", "domain": "resource.co", "tier": "specialist", "region": "UK", "group": "Resource", "email_pattern": "{first}@resource.co", "team_urls": [], "rss": []},
    {"name": "Farmers Weekly", "domain": "fwi.co.uk", "tier": "specialist", "region": "UK", "group": "Mark Allen Group", "email_pattern": "{first}.{last}@markallengroup.com|{first}.{last}@rbi.co.uk", "team_urls": [], "rss": []},
    {"name": "The Grocer", "domain": "thegrocer.co.uk", "tier": "specialist", "region": "UK", "group": "William Reed", "email_pattern": "{first}.{last}@thegrocer.co.uk|{first}.{last}@william-reed.com", "team_urls": [], "rss": []},
    {"name": "Fish Farmer Magazine", "domain": "fishfarmermagazine.com", "tier": "specialist", "region": "UK", "group": "Special Publications", "email_pattern": "editor@fishfarmer-magazine.com", "team_urls": [], "rss": []},
    {"name": "DeSmog UK", "domain": "desmog.com", "tier": "specialist", "region": "UK", "group": "DeSmog", "email_pattern": "{first}@desmog.com", "team_urls": ["https://www.desmog.com/team/"], "rss": ["https://www.desmog.com/feed/"]},
    {"name": "Bureau of Investigative Journalism", "domain": "thebureauinvestigates.com", "tier": "specialist", "region": "UK", "group": "TBIJ", "email_pattern": "{first}.{last}@tbij.com", "team_urls": ["https://www.thebureauinvestigates.com/team"], "rss": ["https://www.thebureauinvestigates.com/rss"]},
    {"name": "openDemocracy", "domain": "opendemocracy.net", "tier": "specialist", "region": "UK", "group": "openDemocracy", "email_pattern": "{first}.{last}@opendemocracy.net", "team_urls": ["https://www.opendemocracy.net/en/about/"], "rss": ["https://www.opendemocracy.net/feed"]},
    {"name": "Byline Times", "domain": "bylinetimes.com", "tier": "specialist", "region": "UK", "group": "Byline", "email_pattern": "{first}@bylinetimes.com", "team_urls": ["https://bylinetimes.com/about/"], "rss": ["https://bylinetimes.com/feed/"]},
    {"name": "The Canary", "domain": "thecanary.co", "tier": "specialist", "region": "UK", "group": "The Canary", "email_pattern": "{first}@thecanary.co", "team_urls": [], "rss": ["https://www.thecanary.co/feed/"]},
    {"name": "Press Gazette", "domain": "pressgazette.co.uk", "tier": "specialist", "region": "UK", "group": "New Statesman Media Group", "email_pattern": "{first}.{last}@pressgazette.co.uk", "team_urls": [], "rss": ["https://pressgazette.co.uk/feed/"]},

    # =========================================================================
    # AGENCIES
    # =========================================================================
    {"name": "Press Association / PA Media", "domain": "pa.media", "tier": "specialist", "region": "UK", "group": "PA Media", "email_pattern": "{first}.{last}@pa.media|{first}.{last}@pamediagroup.com", "team_urls": [], "rss": []},
    {"name": "Reuters UK", "domain": "reuters.com", "tier": "specialist", "region": "UK", "group": "Reuters", "email_pattern": "{first}.{last}@thomsonreuters.com", "team_urls": [], "rss": []},
]


def outlets_by_region(region_filter=None):
    if region_filter is None:
        return OUTLETS
    return [o for o in OUTLETS if region_filter.lower() in o["region"].lower()]


def outlets_by_tier(tier):
    return [o for o in OUTLETS if o["tier"] == tier]


def outlets_by_group(group):
    return [o for o in OUTLETS if o["group"] == group]


if __name__ == "__main__":
    from collections import Counter
    print(f"Total outlets: {len(OUTLETS)}")
    print(f"\nBy tier: {Counter(o['tier'] for o in OUTLETS)}")
    print(f"\nBy group: {Counter(o['group'] for o in OUTLETS).most_common(10)}")
    print(f"\nRegions: {len(set(o['region'] for o in OUTLETS))} unique")
