import certifi
import airportsdata
import pycountry
import re
from dotenv import load_dotenv
import os

os.environ["SSL_CERT_FILE"]=certifi.where()

os.environ["REQUEST_CA_BUNDLE"]=certifi.where()
DEFAULT_ORIGIN_IATA=os.getenv("DEFAULT_ORIGIN_IATA","DAC")
BASE_URL="https://api.aviationstack.com/v1/flights"

AIRPORTS=airportsdata.load("IATA")

COUNTRY_ALIASES = {
	"usa": "US",
	"u.s.a.": "US",
	"u.s.": "US",
	"america": "US",
	"united states": "US",
	"uk": "GB",
	"u.k.": "GB",
	"britain": "GB",
	"england": "GB",
	"uae": "AE",
	"dubai": "AE",
	"south korea": "KR",
	"korea": "KR",
	"russia": "RU",
	"vietnam": "VN",
	"bangladesh": "BD",
	"india": "IN",
}

COUNTRY_MAIN_AIRPORT = {
	"US": "JFK",
	"GB": "LHR",
	"AE": "DXB",
	"KR": "ICN",
	"RU": "SVO",
	"VN": "SGN",
	"BD": "DAC",
	"IN": "DEL",
	"JP": "NRT",
}

CITY_MAIN_AIRPORT = {
	"tokyo": "NRT",
}


def clean_text(text: str) -> str:
	text = text.lower().strip()
	text = re.sub(r"[^a-z0-9\s]", " ", text)
	text = re.sub(r"\s+", " ", text)
	stop_words = {
		"flight", "flights", "ticket", "tickets", "trip", "travel",
		"plan", "complete", "days", "day", "including", "hotel",
		"hotels", "sightseeing", "under", "budget", "info", "information",
	}
	words = [word for word in text.split() if word not in stop_words]
	return " ".join(words).strip()


def country_name_to_code(text: str) -> str | None:
	text = clean_text(text)
	if not text:
		return None

	if text in COUNTRY_ALIASES:
		return COUNTRY_ALIASES[text]

	for alias, country_code in COUNTRY_ALIASES.items():
		cleaned_alias = clean_text(alias)
		if cleaned_alias and f" {cleaned_alias} " in f" {text} ":
			return country_code

	try:
		country = pycountry.countries.lookup(text)
		return country.alpha_2
	except LookupError:
		pass

	for country in pycountry.countries:
		country_name = clean_text(country.name)
		if country_name and f" {country_name} " in f" {text} ":
			return country.alpha_2

	return None


def airport_country_matches(airport: dict, country_code: str) -> bool:
	return str(airport.get("country", "")).upper() == country_code.upper()


def get_best_airport_for_country(country_code: str) -> str | None:
	country_code = country_code.upper()
	preferred = COUNTRY_MAIN_AIRPORT.get(country_code)
	if preferred and preferred in AIRPORTS and airport_country_matches(AIRPORTS[preferred], country_code):
		return preferred

	candidates = []
	for iata, airport in AIRPORTS.items():
		if not iata:
			continue

		if airport_country_matches(airport, country_code):
			name = str(airport.get("name", "")).lower()
			city = str(airport.get("city", "")).lower()
			score = 0
			if "international" in name:
				score += 2
			if city and city in name:
				score += 1
			candidates.append((score, iata))

	if not candidates:
		return None

	candidates.sort(key=lambda candidate: (-candidate[0], candidate[1]))
	return candidates[0][1]


def resolve_location_to_iata(location: str) -> str | None:
	"""Convert a country, city, airport name, or IATA code to an IATA code."""
	if not location:
		return None

	raw_location = location.strip()
	if not raw_location:
		return None

	if re.fullmatch(r"[A-Za-z]{3}", raw_location):
		code = raw_location.upper()
		if code in AIRPORTS:
			return code

	cleaned_location = clean_text(raw_location)
	if not cleaned_location:
		return None

	preferred_city = CITY_MAIN_AIRPORT.get(cleaned_location)
	if preferred_city and preferred_city in AIRPORTS:
		return preferred_city

	country_code = country_name_to_code(cleaned_location)
	if country_code:
		airport_code = get_best_airport_for_country(country_code)
		if airport_code:
			return airport_code

	candidates = []
	for iata, airport in AIRPORTS.items():
		city = clean_text(str(airport.get("city", "")))
		name = clean_text(str(airport.get("name", "")))
		location_text = f" {cleaned_location} "

		if cleaned_location == city:
			score = 100
		elif cleaned_location == name:
			score = 90
		elif city and f" {city} " in location_text:
			score = 60
		elif name and f" {name} " in location_text:
			score = 50
		else:
			continue

		if "international" in name:
			score += 5
		candidates.append((score, iata))

	if not candidates:
		return None

	candidates.sort(key=lambda candidate: (-candidate[0], candidate[1]))
	return candidates[0][1]