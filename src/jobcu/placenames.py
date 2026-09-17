"""Which country a free-text job location is in ("Dublin, Ireland", "Cambridge, MA", "München").

Company career systems and some job boards give locations only as text. Jobcu recognises
country names (in English and the local languages), regions and the bigger towns of the
supported countries, and also well-known places elsewhere, so "Cambridge, MA" isn't taken for
the English Cambridge. It only needs to be good enough to pick jobs in the countries searched;
the smart location filter (Phase 2) uses real map data.
"""

import re
from functools import cache

from jobcu.text import normalise

OTHER = "other"  # a place outside the supported countries

# Country names and regions. Longer names are matched first, so "Northern Ireland" is the UK.
_NAMES: dict[str, str] = {
    "AT": "Austria|Österreich|Oesterreich|Vienna|Wien|Graz|Linz|Salzburg|Innsbruck|Klagenfurt"
          "|Villach|Wels|Sankt Pölten|St. Pölten|Dornbirn|Steyr|Leoben|Tirol|Tyrol|Vorarlberg"
          "|Kärnten|Carinthia|Steiermark|Styria|Niederösterreich|Oberösterreich|Burgenland",
    "BE": "Belgium|Belgique|België|Belgie|Belgien|Brussels|Bruxelles|Brussel|Antwerp|Antwerpen"
          "|Anvers|Ghent|Gent|Gand|Charleroi|Liège|Liege|Luik|Bruges|Brugge|Namur|Leuven|Louvain"
          "|Mons|Mechelen|Aalst|Hasselt|Kortrijk|Ostend|Oostende|Wavre|Mont-Saint-Guibert"
          "|Zaventem|Diegem|Flanders|Vlaanderen|Wallonia|Wallonie",
    "HR": "Croatia|Hrvatska|Zagreb|Split|Rijeka|Osijek|Zadar|Pula|Varaždin|Varazdin",
    "CY": "Cyprus|Κύπρος|Kypros|Nicosia|Lefkosia|Limassol|Lemesos|Larnaca|Paphos",
    "CZ": "Czechia|Czech Republic|Česko|Česká republika|Ceska republika|Prague|Praha|Brno|Ostrava"
          "|Plzeň|Plzen|Pilsen|Liberec|Olomouc|České Budějovice|Hradec Králové|Pardubice|Zlín",
    "DK": "Denmark|Danmark|Copenhagen|København|Kobenhavn|Aarhus|Århus|Odense|Aalborg|Esbjerg"
          "|Kolding|Vejle|Horsens|Randers|Roskilde|Lyngby|Ballerup|Billund|Silkeborg|Herning",
    "EE": "Estonia|Eesti|Tallinn|Tartu|Narva|Pärnu|Parnu",
    "FI": "Finland|Suomi|Helsinki|Helsingfors|Espoo|Tampere|Vantaa|Oulu|Turku|Åbo|Jyväskylä"
          "|Jyvaskyla|Lahti|Kuopio|Pori|Lappeenranta|Vaasa|Joensuu",
    "FR": "France|Paris|Marseille|Lyon|Toulouse|Nice|Nantes|Strasbourg|Montpellier|Bordeaux"
          "|Lille|Rennes|Reims|Grenoble|Dijon|Angers|Le Mans|Clermont-Ferrand|Brest|Tours"
          "|Limoges|Amiens|Metz|Besançon|Perpignan|Orléans|Orleans|Rouen|Caen|Nancy|Sophia"
          "|Antipolis|Valbonne|Aix-en-Provence|Saclay|Massy|Vélizy|Velizy|Boulogne-Billancourt"
          "|La Défense|La Defense|Nanterre|Courbevoie|Issy-les-Moulineaux|Saint-Denis"
          "|Île-de-France|Ile-de-France|Auvergne-Rhône-Alpes|Occitanie|Provence|Bretagne"
          "|Brittany|Normandie|Normandy|Hauts-de-France|Nouvelle-Aquitaine|Grand Est",
    "DE": "Germany|Deutschland|Bundesrepublik|Berlin|Hamburg|Munich|München|Muenchen|Cologne|Köln"
          "|Koeln|Frankfurt|Stuttgart|Düsseldorf|Duesseldorf|Dusseldorf|Leipzig|Dortmund|Essen"
          "|Bremen|Dresden|Hannover|Hanover|Nuremberg|Nürnberg|Nuernberg|Duisburg|Bochum"
          "|Wuppertal|Bielefeld|Bonn|Münster|Muenster|Mannheim|Karlsruhe|Augsburg|Wiesbaden"
          "|Mönchengladbach|Gelsenkirchen|Aachen|Braunschweig|Brunswick|Kiel|Chemnitz"
          "|Halle (Saale)|Magdeburg|Freiburg|Krefeld|Mainz|Lübeck|Luebeck|Erfurt|Oberhausen"
          "|Rostock|Kassel|Hagen|Potsdam|Saarbrücken|Saarbruecken|Hamm|Ludwigshafen|Oldenburg"
          "|Mülheim|Osnabrück|Osnabrueck|Leverkusen|Heidelberg|Darmstadt|Solingen|Regensburg"
          "|Herne|Paderborn|Neuss|Ingolstadt|Offenbach|Fürth|Würzburg|Wuerzburg|Ulm|Heilbronn"
          "|Pforzheim|Wolfsburg|Göttingen|Goettingen|Bottrop|Reutlingen|Koblenz|Erlangen"
          "|Bremerhaven|Remscheid|Trier|Recklinghausen|Jena|Moers|Salzgitter|Siegen|Gütersloh"
          "|Hildesheim|Garching|Unterschleißheim|Unterschleissheim|Ottobrunn|Taufkirchen"
          "|Oberpfaffenhofen|Weßling|Wessling|Gilching|Friedrichshafen|Immenstaad|Walldorf"
          "|Sindelfingen|Böblingen|Boeblingen|Ludwigsburg|Esslingen|Gerlingen|Renningen"
          "|Leonberg|Weilheim|Rosenheim|Landshut|Passau|Bamberg|Bayreuth|Schweinfurt"
          "|Aschaffenburg|Neubiberg|Eschborn|Bad Homburg|Rüsselsheim|Hanau|Wetzlar|Gießen"
          "|Giessen|Marburg|Fulda|Konstanz|Tübingen|Tuebingen|Villingen-Schwenningen|Lörrach"
          "|Offenburg|Baden-Baden|Rastatt|Bruchsal|Kaiserslautern|Emden|Wilhelmshaven"
          "|Flensburg|Norderstedt|Lüneburg|Celle|Cottbus|Görlitz|Zwickau|Weimar|Gera|Dessau"
          "|Schwerin|Greifswald|Stralsund|Wismar|Idar-Oberstein|Neckarsulm|Crailsheim"
          "|Schwäbisch Hall|Aalen|Heidenheim|Oberkochen|Jena|Ilmenau|Freising|Dachau"
          "|Fürstenfeldbruck|Starnberg|Penzberg|Kempten|Memmingen|Donauwörth|Manching"
          "|Bavaria|Bayern|Baden-Württemberg|Baden-Wuerttemberg|Nordrhein-Westfalen"
          "|North Rhine-Westphalia|NRW|Hessen|Hesse|Niedersachsen|Lower Saxony|Sachsen-Anhalt"
          "|Saxony-Anhalt|Sachsen|Saxony|Thüringen|Thuringia|Brandenburg|Schleswig-Holstein"
          "|Rheinland-Pfalz|Rhineland-Palatinate|Saarland|Mecklenburg-Vorpommern",
    "GR": "Greece|Hellas|Ελλάδα|Ellada|Athens|Αθήνα|Athina|Thessaloniki|Patras|Heraklion"
          "|Larissa|Volos|Ioannina|Chania",
    "HU": "Hungary|Magyarország|Magyarorszag|Budapest|Debrecen|Szeged|Miskolc|Pécs|Pecs|Győr"
          "|Gyor|Nyíregyháza|Kecskemét|Kecskemet|Székesfehérvár",
    "IS": "Iceland|Ísland|Reykjavík|Reykjavik|Kópavogur|Hafnarfjörður|Akureyri",
    "IE": "Ireland|Republic of Ireland|Éire|Eire|Dublin|Cork|Limerick|Galway|Waterford|Drogheda"
          "|Dundalk|Swords|Bray|Navan|Kilkenny|Ennis|Carlow|Tralee|Newbridge|Portlaoise"
          "|Balbriggan|Naas|Athlone|Mullingar|Letterkenny|Sligo|Shannon|Leixlip|Maynooth"
          "|Blanchardstown|Sandyford|Tallaght|Clonmel|Wexford|Castlebar|Carrigtwohill"
          "|Ringaskiddy|Little Island|Ballincollig|Dún Laoghaire|Dun Laoghaire|Celbridge"
          "|Greystones|Arklow|Tullamore|Longford|Cavan|Monaghan|Roscommon|Nenagh|Thurles"
          "|Tipperary|Kildare|Wicklow|Meath|Louth|Westmeath|Offaly|Laois|Donegal|Mayo"
          "|Leitrim|Kerry|Clare|Killarney|Oranmore|Parkmore|Grange Castle|Clonee|Mallow"
          "|Midleton|Cobh|Youghal|Fermoy|Dungarvan|Tramore|Gorey|Enniscorthy|Birr|Tuam",
    "IT": "Italy|Italia|Rome|Roma|Milan|Milano|Naples|Napoli|Turin|Torino|Palermo|Genoa|Genova"
          "|Bologna|Florence|Firenze|Bari|Catania|Venice|Venezia|Verona|Messina|Padua|Padova"
          "|Trieste|Brescia|Parma|Taranto|Prato|Modena|Reggio Emilia|Perugia|Livorno|Cagliari"
          "|Pisa|Bergamo|Vicenza|Trento|Bolzano|Monza|Pavia|Lombardia|Lombardy|Piemonte"
          "|Piedmont|Lazio|Veneto|Toscana|Tuscany|Emilia-Romagna|Campania|Sicilia|Sicily",
    "LV": "Latvia|Latvija|Riga|Rīga|Daugavpils|Liepāja|Liepaja|Jelgava",
    "LT": "Lithuania|Lietuva|Vilnius|Kaunas|Klaipėda|Klaipeda|Šiauliai|Siauliai|Panevėžys",
    "LU": "Luxembourg|Lëtzebuerg|Luxemburg|Esch-sur-Alzette|Differdange|Dudelange"
          "|Bettembourg|Leudelange|Munsbach|Strassen|Bertrange|Capellen|Betzdorf",
    "MT": "Malta|Valletta|Birkirkara|Mosta|Qormi|Sliema|St Julian's|St. Julian's|San Ġwann"
          "|Msida|Gżira|Gzira|Ta' Xbiex|Mriehel|Hal Far|Luqa|Marsa",
    "NL": "Netherlands|The Netherlands|Nederland|Holland|Amsterdam|Rotterdam|The Hague"
          "|Den Haag|'s-Gravenhage|Utrecht|Eindhoven|Groningen|Tilburg|Almere|Breda|Nijmegen"
          "|Apeldoorn|Haarlem|Arnhem|Enschede|Amersfoort|Zaanstad|Hoofddorp|Delft|Leiden"
          "|Maastricht|Zwolle|Veldhoven|Schiphol|Amstelveen|Noordwijk|Hilversum|Den Bosch"
          "|'s-Hertogenbosch|Deventer|Wageningen|Nieuwegein|Zoetermeer|Dordrecht|Leeuwarden"
          "|Noord-Holland|Zuid-Holland|North Holland|South Holland|Noord-Brabant|North Brabant",
    "NO": "Norway|Norge|Noreg|Oslo|Bergen|Trondheim|Stavanger|Drammen|Fredrikstad|Kristiansand"
          "|Sandnes|Tromsø|Tromso|Sarpsborg|Skien|Ålesund|Alesund|Sandvika|Lysaker|Fornebu"
          "|Asker|Bærum|Baerum|Kongsberg|Horten|Bodø|Bodo|Haugesund|Moss|Hamar|Lillestrøm",
    "PL": "Poland|Polska|Warsaw|Warszawa|Kraków|Krakow|Cracow|Łódź|Lodz|Wrocław|Wroclaw"
          "|Poznań|Poznan|Gdańsk|Gdansk|Szczecin|Bydgoszcz|Lublin|Białystok|Bialystok"
          "|Katowice|Gdynia|Częstochowa|Radom|Toruń|Torun|Rzeszów|Rzeszow|Kielce|Gliwice"
          "|Olsztyn|Bielsko-Biała|Opole|Sopot|Mazowieckie|Małopolskie|Śląskie",
    "PT": "Portugal|Lisbon|Lisboa|Porto|Oporto|Braga|Coimbra|Aveiro|Funchal|Faro|Setúbal"
          "|Setubal|Guimarães|Guimaraes|Évora|Evora|Leiria|Matosinhos|Oeiras|Amadora|Sintra"
          "|Cascais|Almada|Vila Nova de Gaia|Maia",
    "RO": "Romania|România|Bucharest|București|Bucuresti|Cluj-Napoca|Cluj|Timișoara|Timisoara"
          "|Iași|Iasi|Constanța|Constanta|Craiova|Brașov|Brasov|Galați|Galati|Ploiești"
          "|Ploiesti|Oradea|Sibiu|Arad|Pitești|Pitesti|Bacău|Bacau|Târgu Mureș",
    "SK": "Slovakia|Slovensko|Bratislava|Košice|Kosice|Prešov|Presov|Žilina|Zilina|Nitra"
          "|Banská Bystrica|Trnava|Trenčín|Trencin",
    "SI": "Slovenia|Slovenija|Ljubljana|Maribor|Celje|Kranj|Koper|Novo Mesto|Velenje",
    "ES": "Spain|España|Espana|Madrid|Barcelona|Valencia|Seville|Sevilla|Zaragoza|Málaga"
          "|Malaga|Murcia|Palma|Las Palmas|Bilbao|Alicante|Córdoba|Cordoba|Valladolid|Vigo"
          "|Gijón|Gijon|L'Hospitalet|A Coruña|La Coruña|Coruna|Vitoria|Gasteiz|Granada|Elche"
          "|Oviedo|Santa Cruz de Tenerife|Badalona|Cartagena|Terrassa|Jerez|Sabadell|Móstoles"
          "|Alcalá de Henares|Pamplona|Almería|Almeria|Getafe|Leganés|Leganes|Santander"
          "|Castellón|San Sebastián|San Sebastian|Donostia|Tarragona|Girona|Salamanca"
          "|Catalonia|Cataluña|Catalunya|Andalusia|Andalucía|Basque Country|País Vasco"
          "|Comunidad de Madrid|Galicia|Canary Islands|Islas Canarias|Balearic Islands",
    "SE": "Sweden|Sverige|Stockholm|Gothenburg|Göteborg|Goteborg|Malmö|Malmo|Uppsala|Västerås"
          "|Vasteras|Örebro|Orebro|Linköping|Linkoping|Helsingborg|Jönköping|Jonkoping"
          "|Norrköping|Norrkoping|Lund|Umeå|Umea|Gävle|Gavle|Borås|Boras|Södertälje"
          "|Sodertalje|Eskilstuna|Karlstad|Täby|Växjö|Vaxjo|Halmstad|Sundsvall|Luleå|Lulea"
          "|Kista|Solna|Sundbyberg|Trollhättan|Karlskrona|Skövde",
    "CH": "Switzerland|Schweiz|Suisse|Svizzera|Svizra|Zürich|Zurich|Zuerich|Geneva|Genève"
          "|Geneve|Genf|Ginevra|Basel|Bâle|Bern|Berne|Lausanne|Winterthur|Lucerne|Luzern"
          "|St. Gallen|St Gallen|Sankt Gallen|Lugano|Biel|Bienne|Thun|Köniz|La Chaux-de-Fonds"
          "|Fribourg|Freiburg im Üechtland|Schaffhausen|Chur|Neuchâtel|Neuchatel|Sion|Zug"
          "|Baar|Baden|Aarau|Olten|Solothurn|Wil|Rapperswil|Dübendorf|Duebendorf|Schlieren"
          "|Opfikon|Glattbrugg|Wallisellen|Kloten|Rotkreuz|Villigen|Yverdon|Nyon|Vevey"
          "|Montreux|Martigny|Bellinzona|Locarno|Mendrisio|Ticino|Tessin|Valais|Wallis"
          "|Vaud|Waadt|Aargau|Thurgau|Graubünden|Grisons",
    "GB": "United Kingdom|UK|U.K.|Great Britain|Britain|England|Scotland|Wales|Cymru"
          "|Northern Ireland|London|Manchester|Birmingham|Leeds|Glasgow|Edinburgh|Bristol"
          "|Liverpool|Sheffield|Cardiff|Belfast|Newcastle upon Tyne|Newcastle|Nottingham"
          "|Leicester|Southampton|Portsmouth|Brighton|Reading|Oxford|Cambridge|Milton Keynes"
          "|Coventry|Bath|York|Aberdeen|Dundee|Swansea|Exeter|Plymouth|Norwich|Ipswich"
          "|Guildford|Basingstoke|Bracknell|Slough|Watford|Stevenage|Crawley|Swindon"
          "|Gloucester|Cheltenham|Warwick|Derby|Stoke-on-Trent|Hull|Kingston upon Hull"
          "|Bradford|Sunderland|Preston|Bolton|Wolverhampton|Chester|Lincoln|Luton"
          "|Farnborough|Harwell|Newport|Inverness|Stirling|Livingston|Glenrothes|Crewe"
          "|Warrington|Salford|Stockport|Leamington Spa|Royal Leamington Spa|Solihull"
          "|Wokingham|Maidenhead|Cirencester|Filton|Yeovil|Barrow-in-Furness|Lancaster"
          "|Durham|County Durham|Middlesbrough|Darlington|Chelmsford|Colchester"
          "|Southend-on-Sea|Bournemouth|Poole|Winchester|Salisbury|Canterbury|Maidstone"
          "|Tunbridge Wells|Horsham|Woking|Egham|Staines|Uxbridge|Hemel Hempstead|St Albans"
          "|Hatfield|Harlow|Letchworth|Bedford|Northampton|Peterborough|Kettering"
          "|Loughborough|Worcester|Hereford|Shrewsbury|Telford|Taunton|Truro|Derry"
          "|Londonderry|Lisburn|Newry|Craigavon|Antrim|Armagh|Tyrone|Fermanagh|Paisley"
          "|East Kilbride|Dunfermline|Falkirk|Motherwell|Wrexham|Bridgend|Chippenham"
          "|Stansted|Heathrow|Gatwick|Canary Wharf|Greater London|Greater Manchester"
          "|West Midlands|East Midlands|West Yorkshire|South Yorkshire|North Yorkshire"
          "|Yorkshire|Surrey|Kent|Hampshire|Berkshire|Oxfordshire|Cambridgeshire"
          "|Hertfordshire|Essex|Lancashire|Cheshire|Somerset|Devon|Cornwall|Dorset|Wiltshire"
          "|Gloucestershire|Warwickshire|Leicestershire|Nottinghamshire|Derbyshire"
          "|Staffordshire|Shropshire|Lincolnshire|Norfolk|Suffolk|West Sussex|East Sussex"
          "|Sussex|Buckinghamshire|Bedfordshire|Northamptonshire|Merseyside|Tyne and Wear"
          "|Midlothian|West Lothian|Fife|Lanarkshire",
    OTHER: "United States|United States of America|USA|U.S.A.|U.S.|US|America|Canada|Mexico"
           "|Brazil|Argentina|Chile|Colombia|Peru|India|China|Japan|South Korea|Korea"
           "|Singapore|Australia|New Zealand|Israel|Turkey|Türkiye|Turkiye|UAE"
           "|United Arab Emirates|Dubai|Abu Dhabi|Saudi Arabia|Riyadh|Qatar|Doha|Egypt|Cairo"
           "|South Africa|Nigeria|Kenya|Philippines|Vietnam|Indonesia|Malaysia|Thailand"
           "|Taiwan|Hong Kong|Serbia|Belgrade|Ukraine|Kyiv|Kiev|Bulgaria|Sofia|Russia|Moscow"
           "|Belarus|Minsk|Bosnia|Sarajevo|Albania|Tirana|North Macedonia|Skopje|Montenegro"
           "|Moldova|Chisinau|Armenia|Yerevan|Azerbaijan|Baku|Kazakhstan|Pakistan|Bangladesh"
           "|Sri Lanka|Morocco|Tunisia|Uruguay|Costa Rica|Puerto Rico|Liechtenstein|Monaco"
           "|Andorra|San Marino|Georgia|Tbilisi|New York|NYC|San Francisco|Bay Area"
           "|Silicon Valley|Seattle|Austin|Boston|Chicago|Los Angeles|San Diego|San Jose"
           "|Palo Alto|Mountain View|Sunnyvale|Santa Clara|Menlo Park|Redmond|Denver|Atlanta"
           "|Dallas|Houston|Miami|Washington, D.C.|Washington DC|Philadelphia|Pittsburgh"
           "|Phoenix|Portland|Salt Lake City|Raleigh|Toronto|Vancouver|Montreal|Montréal"
           "|Ottawa|Calgary|Waterloo, ON|Bangalore|Bengaluru|Hyderabad|Chennai|Pune|Mumbai"
           "|Delhi|Gurgaon|Gurugram|Noida|Sydney|Melbourne|Brisbane|Perth|Auckland|Tokyo"
           "|Osaka|Seoul|Shanghai|Beijing|Shenzhen|Tel Aviv|Haifa|Istanbul|Ankara|São Paulo"
           "|Sao Paulo|Mexico City|Buenos Aires|Bogotá|Bogota|Manila|Jakarta|Kuala Lumpur"
           "|Bangkok|Ho Chi Minh|Taipei|Alabama|Alaska|Arizona|Arkansas|California|Colorado"
           "|Connecticut|Delaware|Florida|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky"
           "|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri"
           "|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|North Carolina"
           "|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina"
           "|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|West Virginia|Wisconsin"
           "|Wyoming|Ontario|Quebec|Québec|British Columbia|Alberta|Manitoba|Nova Scotia"
           "|New South Wales|Victoria, Australia|Queensland",
}

# "Dublin, CA" or "Cambridge, MA": a US state or Canadian province code after a comma.
_REGION_CODES = set(
    "AL AK AZ AR CA CO CT FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM "
    "NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC ON QC BC AB MB SK NS NB NL PE"
    .split()
)
# Two-letter country codes after a comma ("Berlin, DE"). "DE" means Germany here, not Delaware.
_COUNTRY_CODES = {"UK": "GB", "GB": "GB", "IE": "IE", "DE": "DE", "AT": "AT", "CH": "CH",
                  "FR": "FR", "NL": "NL", "BE": "BE", "ES": "ES", "IT": "IT", "PL": "PL",
                  "PT": "PT", "SE": "SE", "DK": "DK", "NO": "NO", "FI": "FI", "CZ": "CZ",
                  "US": OTHER, "USA": OTHER, "IN": OTHER}
_SEGMENTS = re.compile(r"\s*(?:;|\||\n| / | or | oder | und )\s*")
_CODE_AFTER_COMMA = re.compile(r",\s*([A-Z]{2,3})\b")
_REGIONAL = re.compile(r"\b(emea|europe|european union|eu|dach)\b")


@cache
def _patterns() -> list[tuple[re.Pattern, str]]:
    entries = []
    for code, names in _NAMES.items():
        for name in names.split("|"):
            normal = normalise(name)
            if normal:
                entries.append((normal, code))
    # Longest names first, so "northern ireland" wins over "ireland" and "new york" over "york".
    entries.sort(key=lambda entry: -len(entry[0]))
    return [(re.compile(rf"\b{re.escape(name)}\b"), code) for name, code in entries]


def _segment_countries(segment: str) -> set[str]:
    found: set[str] = set()
    for match in _CODE_AFTER_COMMA.finditer(segment):
        code = match.group(1)
        if code in _COUNTRY_CODES:
            found.add(_COUNTRY_CODES[code])
        elif code in _REGION_CODES:
            found.add(OTHER)
    text = normalise(segment)
    for pattern, code in _patterns():
        if pattern.search(text):
            found.add(code)
            text = pattern.sub(" ", text)
    supported = found - {OTHER}
    # A town name next to a foreign country or state ("Dublin, Ohio") is that foreign place.
    if OTHER in found and supported:
        return {OTHER}
    return found


def countries_in(location_text: str | None) -> set[str]:
    """The supported country codes a location names; OTHER marks places outside them."""
    found: set[str] = set()
    for segment in _SEGMENTS.split(location_text or ""):
        if segment.strip():
            found |= _segment_countries(segment)
    return found


def is_europe_wide(location_text: str | None) -> bool:
    """"Remote - EMEA", "Europe": no single country, but open to the supported countries."""
    return _REGIONAL.search(normalise(location_text)) is not None
