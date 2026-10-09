import math
import random
import streamlit as st
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
import geonamescache

st.title("Closest or Farthest? The Flight Game")
st.write("You are the pilot! We pick 4 mystery cities from 4 different countries. "
         "Can you guess which one is the CLOSEST to you and which one is the FARTHEST?")

# load real cities (offline). The biggest city wins when two share a name.
gc = geonamescache.GeonamesCache()
countries = gc.get_countries()
big_cities = [city for city in gc.get_cities().values() if city["population"] >= 3_000_000]
cities = {city["name"]: city for city in sorted(big_cities, key=lambda city: city["population"])}

# a ready-made helper that measures the real distance in km on the ROUND Earth
def real_distance(place_a, place_b):
    lat1, lat2 = math.radians(place_a["latitude"]), math.radians(place_b["latitude"])
    lon_gap = math.radians(place_b["longitude"] - place_a["longitude"])
    x = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(lon_gap / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(x))

# 1. Where are you? (the target button from class, or choose your city)
st.subheader("Where are you?")
st.write("Press the small target button and allow your browser to share your location.")
my_place = streamlit_geolocation()
if my_place["latitude"] is not None:
    me = {"latitude": my_place["latitude"], "longitude": my_place["longitude"]}
else:
    home_name = st.selectbox("No GPS? Choose the big city nearest to you.", sorted(cities), index=None, placeholder="Choose your city")
    if home_name is None:
        st.info("Press the target button, or choose your city, to start the game!")
        st.stop()                                                    # wait until we know where you are
    me = cities[home_name]
my_city = min(cities.values(), key=lambda city: real_distance(me, city))
st.success(f"Your nearest big city is {my_city['name']}, {countries[my_city['countrycode']]['name']}. This app does not save your location.")

# 2. The button picks 4 random cities from 4 different countries (not your own country)
other_cities = {city["countrycode"]: name for name, city in cities.items() if city["countrycode"] != my_city["countrycode"]}
if st.button("Pick 4 mystery cities"):
    st.session_state.mystery = random.sample(list(other_cities.values()), 4)
if "mystery" not in st.session_state:
    st.stop()                                                        # wait for the first pick
mystery = st.session_state.mystery
distances = {name: real_distance(me, cities[name]) for name in mystery}
closest = min(distances, key=distances.get)
farthest = max(distances, key=distances.get)

# a map you can draw twice: first with no answers, later with the answers
def draw_map(show_answers):
    game_map = folium.Map(tiles=None)
    folium.TileLayer("Esri.WorldImagery", no_wrap=True, bounds=[[-90, -180], [90, 180]]).add_to(game_map)     # one world only
    folium.Marker([me["latitude"], me["longitude"]], icon=folium.Icon(color="black", icon="user", prefix="fa"),
                  tooltip=folium.Tooltip("You", permanent=True)).add_to(game_map)
    for name in mystery:
        pin_colour = {closest: "green", farthest: "red"}.get(name, "blue") if show_answers else "blue"
        folium.Marker([cities[name]["latitude"], cities[name]["longitude"]], icon=folium.Icon(color=pin_colour),
                      tooltip=folium.Tooltip(name, permanent=True)).add_to(game_map)
    game_map.fit_bounds(game_map.get_bounds(), max_zoom=6, padding=(40, 40))
    st_folium(game_map, height=440, key=f"map {show_answers}", returned_objects=[], use_container_width=True)

# 3. Look at the map, then guess
st.subheader("Which is closest? Which is farthest?")
draw_map(False)
closest_guess = st.radio("The CLOSEST city to you is...", mystery, index=None, horizontal=True, key=f"closest {mystery}")
farthest_guess = st.radio("The FARTHEST city from you is...", mystery, index=None, horizontal=True, key=f"farthest {mystery}")
if closest_guess is None or farthest_guess is None:
    st.stop()                                                        # wait for both guesses

# 4. The answers
st.subheader("The answers")
for label, guess, answer in [("Closest", closest_guess, closest), ("Farthest", farthest_guess, farthest)]:
    if guess == answer:
        st.success(f"{label}: {answer}. You were right!")
    else:
        st.error(f"{label}: it is {answer}, not {guess}.")
draw_map(True)
st.dataframe([{"City": name, "Country": countries[cities[name]["countrycode"]]["name"], "Distance (km)": round(distances[name]),
               "Flying time (hours)": round(distances[name] / 900, 1)} for name in sorted(distances, key=distances.get)], hide_index=True)
st.caption("Green pin = closest, red pin = farthest. Flying time is for a plane that flies 900 km every hour. Press the button again for 4 new cities!")
