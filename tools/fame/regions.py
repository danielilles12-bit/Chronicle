"""
Coarse country -> region mapping for the Relic universe-of-objects harvester.
Regions used: Europe, East Asia, Southeast Asia, South Asia, Central Asia,
Middle East, Africa, North America, South America, Oceania.
"""

COUNTRY_REGION = {
    # Europe
    "Albania": "Europe", "Andorra": "Europe", "Armenia": "Europe",
    "Austria": "Europe", "Azerbaijan": "Europe", "Belarus": "Europe",
    "Belgium": "Europe", "Bosnia and Herzegovina": "Europe",
    "Bulgaria": "Europe", "Croatia": "Europe", "Cyprus": "Europe",
    "Czechia": "Europe", "Czech Republic": "Europe", "Denmark": "Europe",
    "Estonia": "Europe", "Finland": "Europe", "France": "Europe",
    "Georgia": "Europe", "Germany": "Europe", "Greece": "Europe",
    "Hungary": "Europe", "Iceland": "Europe", "Ireland": "Europe",
    "Italy": "Europe", "Kosovo": "Europe", "Latvia": "Europe",
    "Liechtenstein": "Europe", "Lithuania": "Europe", "Luxembourg": "Europe",
    "Malta": "Europe", "Moldova": "Europe", "Monaco": "Europe",
    "Montenegro": "Europe", "Netherlands": "Europe",
    "North Macedonia": "Europe", "Norway": "Europe", "Poland": "Europe",
    "Portugal": "Europe", "Romania": "Europe", "Russia": "Europe",
    "San Marino": "Europe", "Serbia": "Europe", "Slovakia": "Europe",
    "Slovenia": "Europe", "Spain": "Europe", "Sweden": "Europe",
    "Switzerland": "Europe", "Ukraine": "Europe",
    "United Kingdom": "Europe", "Vatican City": "Europe",
    "Holy See": "Europe",

    # Middle East
    "Bahrain": "Middle East", "Iran": "Middle East", "Iraq": "Middle East",
    "Israel": "Middle East", "Jordan": "Middle East", "Kuwait": "Middle East",
    "Lebanon": "Middle East", "Oman": "Middle East", "Palestine": "Middle East",
    "Qatar": "Middle East", "Saudi Arabia": "Middle East",
    "Syria": "Middle East", "Turkey": "Middle East",
    "United Arab Emirates": "Middle East", "Yemen": "Middle East",

    # Central Asia
    "Kazakhstan": "Central Asia", "Kyrgyzstan": "Central Asia",
    "Tajikistan": "Central Asia", "Turkmenistan": "Central Asia",
    "Uzbekistan": "Central Asia", "Mongolia": "Central Asia",
    "Afghanistan": "Central Asia",

    # South Asia
    "Bangladesh": "South Asia", "Bhutan": "South Asia", "India": "South Asia",
    "Maldives": "South Asia", "Nepal": "South Asia", "Pakistan": "South Asia",
    "Sri Lanka": "South Asia",

    # East Asia
    "China": "East Asia", "Hong Kong": "East Asia", "Macau": "East Asia",
    "Japan": "East Asia", "North Korea": "East Asia",
    "South Korea": "East Asia", "Taiwan": "East Asia",

    # Southeast Asia
    "Brunei": "Southeast Asia", "Cambodia": "Southeast Asia",
    "Indonesia": "Southeast Asia", "Laos": "Southeast Asia",
    "Malaysia": "Southeast Asia", "Myanmar": "Southeast Asia",
    "Philippines": "Southeast Asia", "Singapore": "Southeast Asia",
    "Thailand": "Southeast Asia", "Timor-Leste": "Southeast Asia",
    "Vietnam": "Southeast Asia",

    # Africa
    "Algeria": "Africa", "Angola": "Africa", "Benin": "Africa",
    "Botswana": "Africa", "Burkina Faso": "Africa", "Burundi": "Africa",
    "Cabo Verde": "Africa", "Cape Verde": "Africa", "Cameroon": "Africa",
    "Central African Republic": "Africa", "Chad": "Africa",
    "Comoros": "Africa", "Congo": "Africa",
    "Democratic Republic of the Congo": "Africa",
    "Republic of the Congo": "Africa", "Djibouti": "Africa",
    "Egypt": "Africa", "Equatorial Guinea": "Africa", "Eritrea": "Africa",
    "Eswatini": "Africa", "Ethiopia": "Africa", "Gabon": "Africa",
    "Gambia": "Africa", "Ghana": "Africa", "Guinea": "Africa",
    "Guinea-Bissau": "Africa", "Ivory Coast": "Africa",
    "Cote d'Ivoire": "Africa", "Côte d'Ivoire": "Africa", "Kenya": "Africa",
    "Lesotho": "Africa", "Liberia": "Africa", "Libya": "Africa",
    "Madagascar": "Africa", "Malawi": "Africa", "Mali": "Africa",
    "Mauritania": "Africa", "Mauritius": "Africa", "Morocco": "Africa",
    "Mozambique": "Africa", "Namibia": "Africa", "Niger": "Africa",
    "Nigeria": "Africa", "Rwanda": "Africa",
    "Sao Tome and Principe": "Africa", "São Tomé and Príncipe": "Africa",
    "Senegal": "Africa", "Seychelles": "Africa", "Sierra Leone": "Africa",
    "Somalia": "Africa", "South Africa": "Africa", "South Sudan": "Africa",
    "Sudan": "Africa", "Tanzania": "Africa", "Togo": "Africa",
    "Tunisia": "Africa", "Uganda": "Africa", "Zambia": "Africa",
    "Zimbabwe": "Africa",

    # North America (incl. Central America & Caribbean)
    "Antigua and Barbuda": "North America", "Bahamas": "North America",
    "Barbados": "North America", "Belize": "North America",
    "Canada": "North America", "Costa Rica": "North America",
    "Cuba": "North America", "Dominica": "North America",
    "Dominican Republic": "North America", "El Salvador": "North America",
    "Grenada": "North America", "Guatemala": "North America",
    "Haiti": "North America", "Honduras": "North America",
    "Jamaica": "North America", "Mexico": "North America",
    "Nicaragua": "North America", "Panama": "North America",
    "Saint Kitts and Nevis": "North America", "Saint Lucia": "North America",
    "Saint Vincent and the Grenadines": "North America",
    "Trinidad and Tobago": "North America", "United States": "North America",
    "United States of America": "North America",

    # South America
    "Argentina": "South America", "Bolivia": "South America",
    "Brazil": "South America", "Chile": "South America",
    "Colombia": "South America", "Ecuador": "South America",
    "Guyana": "South America", "Paraguay": "South America",
    "Peru": "South America", "Suriname": "South America",
    "Uruguay": "South America", "Venezuela": "South America",

    # Oceania
    "Australia": "Oceania", "Fiji": "Oceania", "Kiribati": "Oceania",
    "Marshall Islands": "Oceania", "Micronesia": "Oceania",
    "Nauru": "Oceania", "New Zealand": "Oceania", "Palau": "Oceania",
    "Papua New Guinea": "Oceania", "Samoa": "Oceania",
    "Solomon Islands": "Oceania", "Tonga": "Oceania", "Tuvalu": "Oceania",
    "Vanuatu": "Oceania",
}


# Historical polities / former states / cities that show up as Wikidata
# P17/P131 values for older or well-known objects.
HISTORICAL_OR_CITY_ALIASES = {
    "British Empire": "Europe", "Kingdom of England": "Europe",
    "Kingdom of Great Britain": "Europe", "German Reich": "Europe",
    "Weimar Republic": "Europe", "Nazi Germany": "Europe",
    "East Germany": "Europe", "West Germany": "Europe",
    "Kingdom of Italy": "Europe", "Kingdom of France": "Europe",
    "Kingdom of Spain": "Europe", "Kingdom of Prussia": "Europe",
    "Russian Empire": "Europe", "Soviet Union": "Europe",
    "Austria-Hungary": "Europe", "Austrian Empire": "Europe",
    "Holy Roman Empire": "Europe", "Republic of Venice": "Europe",
    "Grand Duchy of Tuscany": "Europe", "Kingdom of Poland": "Europe",
    "Polish People's Republic": "Europe", "Czechoslovakia": "Europe",
    "Yugoslavia": "Europe", "Byzantine Empire": "Europe",
    "Ottoman Empire": "Middle East", "Persian Empire": "Middle East",
    "Achaemenid Empire": "Middle East", "Sasanian Empire": "Middle East",
    "Mamluk Sultanate": "Middle East",
    "People's Republic of China": "East Asia",
    "Republic of China": "East Asia", "Qing dynasty": "East Asia",
    "Ming dynasty": "East Asia", "Empire of Japan": "East Asia",
    "Joseon": "East Asia", "Khmer Empire": "Southeast Asia",
    "Dutch East Indies": "Southeast Asia",
    "British Raj": "South Asia", "Mughal Empire": "South Asia",
    "Federated States of Micronesia": "Oceania",
    "Confederate States of America": "North America",
    "New Spain": "North America", "New France": "North America",
    "Inca Empire": "South America", "Aztec Empire": "North America",
    "Ancient Egypt": "Africa", "Kingdom of Kush": "Africa",
    "Aksumite Empire": "Africa",
    # major cities used as a P131 fallback when no country claim exists
    "New York City": "North America", "London": "Europe",
    "Paris": "Europe", "Beijing": "East Asia", "Tokyo": "East Asia",
    "Moscow": "Europe", "Rome": "Europe", "Cairo": "Africa",
    "Washington, D.C.": "North America",
}


def region_for_country(name):
    if not name:
        return None
    name = name.strip()
    if name in COUNTRY_REGION:
        return COUNTRY_REGION[name]
    if name in HISTORICAL_OR_CITY_ALIASES:
        return HISTORICAL_OR_CITY_ALIASES[name]
    # try stripping leading "the "
    if name.lower().startswith("the "):
        stripped = name[4:]
        if stripped in COUNTRY_REGION:
            return COUNTRY_REGION[stripped]
        if stripped in HISTORICAL_OR_CITY_ALIASES:
            return HISTORICAL_OR_CITY_ALIASES[stripped]
    return None
