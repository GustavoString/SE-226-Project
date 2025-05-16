import requests
from bs4 import BeautifulSoup
import re
import json
import os
import time

class MovieManager:
    def __init__(self):
        """Initialize the MovieManager with empty movie collection."""
        self.movies = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.base_url = "https://www.imdb.com/chart/top/"

    def fetch_top_movies(self, limit=10, force_refresh=False):
        """
        Fetch the top N movies from IMDb and store them in the movies dictionary.

        Args:
            limit (int): Number of top movies to fetch (default: 10)
            force_refresh (bool): Whether to refresh existing movies

        Returns:
            dict: Dictionary of movies indexed by rank
        """

        # If movies are already fetched and no forced refresh, return subset
        if self.movies and not force_refresh:
            return {k: v for k, v in self.movies.items() if k <= limit}

        try:

            # Send HTTP GET request to IMDb top movies page
            response = requests.get(self.base_url, headers=self.headers)
            # Raise an error for bad HTTP responses
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            movie_containers = soup.select(".ipc-metadata-list-summary-item")

            if not movie_containers:
                movie_containers = soup.select(".ipc-metadata-list-item")
            if not movie_containers:
                movie_containers = soup.select("[data-testid='chart-layout-main-column'] .ipc-metadata-list-item")
            if not movie_containers:
                movie_containers = soup.select(".ipc-title-link-wrapper")

            # Raise exception if no movie elements found on the page
            if not movie_containers:
                raise Exception("Failed to find movie elements on the page")

            # Clear existing movies if forced refresh requested
            if force_refresh:
                self.movies = {}

            for i, movie in enumerate(movie_containers[:limit]):
                rank = i + 1
                title_element = movie.select_one(".ipc-title__text")
                if not title_element:
                    title_element = movie.select_one(".ipc-metadata-list-item__label")
                if not title_element:
                    title_element = movie.select_one("a")

                if title_element:
                    title = title_element.text.strip()
                    if '. ' in title and title[0].isdigit():
                        title = title.split('. ', 1)[1]

                    self.movies[rank] = {
                        "rank": rank,
                        "title": title,
                        "details_fetched": False
                    }

            if len(self.movies) < limit:
                print(f"Warning: Only found {len(self.movies)} movies, expected {limit}")

            return {k: v for k, v in self.movies.items() if k <= limit}

        except Exception as e:
            print(f"Error fetching top movies: {e}")
            raise

    def get_movie_details(self, movie_title, retry_delay=2, max_retries=3):
        """
        Fetch detailed information for a movie by title.

        Args:
            movie_title (str): The title of the movie
            retry_delay (int): Seconds to wait between retries
            max_retries (int): Maximum number of retry attempts

        Returns:
            dict: Movie details dictionary
        """
        for attempt in range(max_retries):
            try:
                #Search movie on IMDb using query parameterized URL
                search_url = f"https://www.imdb.com/find/?q={movie_title.replace(' ', '+')}"
                search_response = requests.get(search_url, headers=self.headers)
                search_response.raise_for_status()
                search_soup = BeautifulSoup(search_response.text, 'html.parser')

                movie_link = search_soup.select_one("a[href*='/title/tt']")
                if not movie_link:
                    raise Exception(f"Could not find movie: {movie_title}")

                movie_id_match = re.search(r'/title/(tt\d+)', movie_link['href'])
                if not movie_id_match:
                    raise Exception(f"Could not extract movie ID for: {movie_title}")

                movie_id = movie_id_match.group(1)

                #Fetch movie details page using movie ID and scrape key data points
                movie_url = f"https://www.imdb.com/title/{movie_id}/"
                movie_response = requests.get(movie_url, headers=self.headers)
                movie_response.raise_for_status()
                movie_soup = BeautifulSoup(movie_response.text, 'html.parser')

                movie_details = {
                    "title": movie_title,
                    "imdb_id": movie_id,
                    "url": movie_url,
                    "year": "N/A",
                    "director": "N/A",
                    "rating": "N/A",
                    "genre": "N/A",
                    "description": "N/A",
                    "storyline": "N/A",
                    "poster_url": None,
                    "details_fetched": True
                }

                year_element = movie_soup.select_one("[data-testid='title-details-releasedate']")
                if year_element:
                    year_match = re.search(r'\d{4}', year_element.text)
                    if year_match:
                        movie_details["year"] = year_match.group(0)

                director_element = movie_soup.select_one(
                    "[data-testid='title-pc-principal-credit']:has(a[href*='director'])")
                if director_element:
                    director_name = director_element.select_one("a")
                    if director_name:
                        movie_details["director"] = director_name.text.strip()

                rating_element = movie_soup.select_one("[data-testid='hero-rating-bar__aggregate-rating__score']")
                if rating_element:
                    rating_text = rating_element.text.strip()
                    movie_details["rating"] = rating_text

                genre_element = movie_soup.select_one("[data-testid='genres']")
                if genre_element:
                    genres = genre_element.select("a")
                    if genres:
                        movie_details["genre"] = ", ".join([g.text.strip() for g in genres])

                plot_element = movie_soup.select_one("[data-testid='plot']")
                if plot_element:
                    movie_details["description"] = plot_element.text.strip()

                poster_element = movie_soup.select_one("[data-testid='hero-media__poster'] img")
                if poster_element and 'src' in poster_element.attrs:
                    movie_details["poster_url"] = poster_element['src']

                #Fallback to plot description if storyline extraction fails
                try:
                    movie_details["storyline"] = self._get_movie_storyline(movie_id)
                except Exception as e:
                    print(f"Could not fetch storyline, using plot summary: {e}")
                    movie_details["storyline"] = movie_details["description"]

                return movie_details

            except Exception as e:
                # Print retry info and raise exception on last attempt
                print(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print(f"Failed to fetch details after {max_retries} attempts")
                    raise Exception(f"Failed to get details for {movie_title}: {e}")

    def _get_movie_storyline(self, movie_id):
        """
        Helper method to get a movie's storyline using its IMDb ID.

        Args:
            movie_id (str): IMDb ID (e.g., 'tt0111161')

        Returns:
            str: Full storyline text
        """
        plot_url = f"https://www.imdb.com/title/{movie_id}/plotsummary/"
        plot_response = requests.get(plot_url, headers=self.headers)
        plot_response.raise_for_status()
        plot_soup = BeautifulSoup(plot_response.text, 'html.parser')

        storyline_elements = plot_soup.select(".ipc-html-content-inner-div")

        if len(storyline_elements) >= 2:
            return storyline_elements[2].text.strip()

        raise Exception(f"Could not find storyline for movie ID: {movie_id}")

    def fetch_movie_details_by_rank(self, rank):
        """
        Fetch detailed information for a movie by its rank.

        Args:
            rank (int): The rank of the movie to fetch details for

        Returns:
            dict: Updated movie details dictionary
        """
        if rank not in self.movies:
            self.fetch_top_movies(limit=rank)

        if rank not in self.movies:
            raise Exception(f"No movie found with rank {rank}")

        movie = self.movies[rank]

        if movie.get("details_fetched", False):
            return movie

        details = self.get_movie_details(movie["title"])
        details["rank"] = rank
        self.movies[rank] = details

        return details

    def fetch_all_details(self, max_rank=None):
        """
        Fetch details for all movies up to max_rank.

        Args:
            max_rank (int): Maximum rank to fetch details for (default: all)

        Returns:
            dict: Updated dictionary of movies
        """
        if not self.movies:
            self.fetch_top_movies(limit=max_rank or 10)

        ranks = sorted(self.movies.keys())
        if max_rank:
            ranks = [r for r in ranks if r <= max_rank]

        for rank in ranks:
            if not self.movies[rank].get("details_fetched", False):
                try:
                    print(f"Fetching details for rank {rank}: {self.movies[rank]['title']}")
                    self.fetch_movie_details_by_rank(rank)
                    time.sleep(1)
                except Exception as e:
                    print(f"Error fetching details for rank {rank}: {e}")

        return {k: v for k, v in self.movies.items() if k in ranks}

    def save_to_file(self, filename="movie_data.json"):
        """
        Save movie data to a JSON file.

        Args:
            filename (str): Path to save the JSON file

        Returns:
            bool: True if successful
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.movies, f, indent=2, ensure_ascii=False)
            print(f"Successfully saved movie data to {filename}")
            return True
        except Exception as e:
            print(f"Error saving movie data: {e}")
            return False

    def load_from_file(self, filename="movie_data.json"):
        """
        Load movie data from a JSON file.

        Args:
            filename (str): Path to the JSON file

        Returns:
            dict: Loaded movie dictionary
        """
        try:
            if not os.path.exists(filename):
                print(f"File {filename} does not exist")
                return {}

            with open(filename, 'r', encoding='utf-8') as f:
                self.movies = json.load(f)

            self.movies = {int(k): v for k, v in self.movies.items()}
            print(f"Successfully loaded {len(self.movies)} movies from {filename}")
            return self.movies
        except Exception as e:
            print(f"Error loading movie data: {e}")
            return {}

    def fetch_movie_details(self, imdb_id):
        """Fetch detailed information for a specific movie by IMDb ID."""
        try:
            url = f"https://www.imdb.com/title/{imdb_id}/"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            poster_elem = soup.select_one('div[data-testid="hero-media__poster"] img')
            poster_url = poster_elem['src'] if poster_elem and 'src' in poster_elem.attrs else None

            return {
                'poster_url': poster_url
            }
        except Exception as e:
            print(f"Error fetching movie details for {imdb_id}: {e}")
            return {}
