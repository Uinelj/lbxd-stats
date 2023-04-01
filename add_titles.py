from watchlist import Watchlist
import json

wl = Watchlist("res/watchlist.json")

new_wl = dict()
for movie in wl.watchlist:
    try:
        with open(f"res/movie_data/{movie}.json") as f:
            movieinfo = json.load(f)
            print(movieinfo)
            new_wl[movie] = movieinfo["title"]
    except FileNotFoundError:
        new_wl[movie] = movie

with open("res/watchlist_new.json", "w") as f:
    json.dump(new_wl, f, indent=2)
