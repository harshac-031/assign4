import math
import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import geonamescache

st.title("My Trip Around the World")
st.write("Plan a trip! Start at your home city, visit 3 other cities, and find out how far you travel. "
         "Then see how wrong a flat map would be.")

# Step 1: load real cities (offline). The biggest city wins when two share a name.
gc = geonamescache.GeonamesCache()
big_cities = [city for city in gc.get_cities().values() if city["population"] >= 1_000_000]
cities = {city["name"]: city for city in sorted(big_cities, key=lambda city: city["population"])}
city_names = sorted(cities, key=lambda name: cities[name]["population"], reverse=True)   # biggest city first (type to search!)

# Step 2: three ready-made helpers (the same ones you used in class)
def real_distance(city_a, city_b):
    """Distance in km on the ROUND Earth."""
    lat1, lat2 = math.radians(city_a["latitude"]), math.radians(city_b["latitude"])
    lon_gap = math.radians(city_b["longitude"] - city_a["longitude"])
    x = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(lon_gap / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(x))

def flat_map_distance(city_a, city_b):
    """A flat-map guess in km: treat the Earth like a sheet of paper (1 degree is about 111 km)."""
    return math.hypot(city_a["latitude"] - city_b["latitude"], city_a["longitude"] - city_b["longitude"]) * 111

def curved_path(city_a, city_b):
    """Points along the shortest path on the globe, so we can draw it as a curve on the map."""
    lat1, lon1 = math.radians(city_a["latitude"]), math.radians(city_a["longitude"])
    lat2, lon2 = math.radians(city_b["latitude"]), math.radians(city_b["longitude"])
    angle = real_distance(city_a, city_b) / 6371
    path, last_longitude = [], city_a["longitude"]
    for step in range(41):
        fraction = step / 40
        weight_a = math.sin((1 - fraction) * angle) / math.sin(angle)
        weight_b = math.sin(fraction * angle) / math.sin(angle)
        x = weight_a * math.cos(lat1) * math.cos(lon1) + weight_b * math.cos(lat2) * math.cos(lon2)
        y = weight_a * math.cos(lat1) * math.sin(lon1) + weight_b * math.cos(lat2) * math.sin(lon2)
        z = weight_a * math.sin(lat1) + weight_b * math.sin(lat2)
        longitude = math.degrees(math.atan2(y, x))
        longitude += 360 * round((last_longitude - longitude) / 360)       # do not jump across the map edge
        path.append([math.degrees(math.atan2(z, math.hypot(x, y))), longitude])
        last_longitude = longitude
    return path

# Step 3: the student plans the trip
home_name = st.selectbox("Your home city (click here and type to search)", city_names, index=None, placeholder="Choose your home city")
first_box, second_box, third_box = st.columns(3)
stop_one = first_box.selectbox("Stop 1", city_names, index=None, placeholder="Choose a city")
stop_two = second_box.selectbox("Stop 2", city_names, index=None, placeholder="Choose a city")
stop_three = third_box.selectbox("Stop 3", city_names, index=None, placeholder="Choose a city")
come_home = st.radio("Do you fly back home at the end?", ["Yes", "No"], horizontal=True)

if home_name is None or stop_one is None or stop_two is None or stop_three is None:
    st.info("Choose your home city and all 3 stops to see your trip!")
    st.stop()                                                # wait until all 4 cities are chosen

if home_name in [stop_one, stop_two, stop_three] or stop_one in [stop_two, stop_three] or stop_two == stop_three:
    st.warning("Pick 4 different cities for your trip!")
    st.stop()                                                # wait until all 4 cities are different
trip_names = [home_name, stop_one, stop_two, stop_three]
if come_home == "Yes":
    trip_names = trip_names + [home_name]                    # add the flight back home

# Step 4: measure every leg of the trip, in both ways
legs = []
for number in range(len(trip_names) - 1):
    start_city, end_city = cities[trip_names[number]], cities[trip_names[number + 1]]
    legs.append({"name": f"{number + 1}. {start_city['name']} to {end_city['name']}",
                 "start": start_city, "end": end_city,
                 "real_km": round(real_distance(start_city, end_city)),
                 "flat_km": round(flat_map_distance(start_city, end_city))})

total_real_km = sum(leg["real_km"] for leg in legs)
total_flat_km = sum(leg["flat_km"] for leg in legs)
longest_leg = max(legs, key=lambda leg: leg["real_km"])
percent_wrong = 100 * (total_flat_km - total_real_km) / total_real_km

# Step 5: the trip report
first, second, third = st.columns(3)
first.metric("Real distance of your trip", f"{total_real_km:,} km")
second.metric("Flying time (at 900 km per hour)", f"{total_real_km / 900:.1f} hours")
third.metric("Flat-map guess", f"{total_flat_km:,} km", f"{percent_wrong:+.0f}% compared with real", delta_color="off")
st.write(f"Your longest leg is **{longest_leg['name']}**: {longest_leg['real_km']:,} km.")
if percent_wrong >= 10 or percent_wrong <= -10:
    st.warning(f"A flat map would get your trip WRONG by {percent_wrong:+.0f}%! Flat maps stretch the far North and South.")
else:
    st.success("The flat map was close this time. Try a trip with cities far to the North or South!")

# Step 6: bars (green = real, red = flat-map guess) next to the satellite map
bars = pd.DataFrame([{"Leg": leg["name"], "Measure": measure, "Distance (km)": leg[key]}
                     for leg in legs
                     for measure, key in (("Real distance", "real_km"), ("Flat-map guess", "flat_km"))])
bar_chart = px.bar(bars, x="Leg", y="Distance (km)", color="Measure", barmode="group", text_auto=True,
                   color_discrete_map={"Real distance": "#2ecc71", "Flat-map guess": "#e74c3c"},
                   title="How long is each leg of your trip?")
bar_chart.update_layout(height=450, legend_title_text="")

trip_map = folium.Map(tiles="Esri.WorldImagery")
all_points = []
for leg in legs:
    path = curved_path(leg["start"], leg["end"])
    folium.PolyLine(path, color="yellow", weight=4, tooltip=f"{leg['name']}: {leg['real_km']:,} km").add_to(trip_map)
    folium.CircleMarker(path[-1], radius=7, color="cyan", fill=True,
                        tooltip=folium.Tooltip(leg["end"]["name"], permanent=True)).add_to(trip_map)
    all_points += path
home = cities[home_name]
folium.Marker([home["latitude"], home["longitude"]], icon=folium.Icon(color="red", icon="home"),
              tooltip=folium.Tooltip(home_name, permanent=True)).add_to(trip_map)
trip_map.fit_bounds([[min(point[0] for point in all_points), min(point[1] for point in all_points)],
                     [max(point[0] for point in all_points), max(point[1] for point in all_points)]])

chart_box, map_box = st.columns(2)
chart_box.plotly_chart(bar_chart)
with map_box:
    st_folium(trip_map, height=450, returned_objects=[])
