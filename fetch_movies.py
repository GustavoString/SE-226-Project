import requests
from bs4 import BeautifulSoup
import re
import json
import os
import time

class MovieManager:
    def __init__(self):
        """Initialize the MovieManager with empty movie collection."""
        self.movies = {}  # Dictionary to store movies by rank
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
        if self.movies and not force_refresh:
            return {k: v for k, v in self.movies.items() if k <= limit}

        try:
            response = requests.get(self.base_url, headers=self.headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Try multiple selectors to find movie containers
            movie_containers = soup.select(".ipc-metadata-list-summary-item")

            # Try alternative selectors if needed
            if not movie_containers:
                movie_containers = soup.select(".ipc-metadata-list-item")
            if not movie_containers:
                movie_containers = soup.select("[data-testid='chart-layout-main-column'] .ipc-metadata-list-item")
            if not movie_containers:
                movie_containers = soup.select(".ipc-title-link-wrapper")

            if not movie_containers:
                raise Exception("Failed to find movie elements on the page")

            # Clear existing entries if refreshing
            if force_refresh:
                self.movies = {}

            # Process the movies up to limit
            for i, movie in enumerate(movie_containers[:limit]):
                rank = i + 1

                # Try different ways to find the title
                title_element = movie.select_one(".ipc-title__text")
                if not title_element:
                    title_element = movie.select_one(".ipc-metadata-list-item__label")
                if not title_element:
                    title_element = movie.select_one("a")

                if title_element:
                    title = title_element.text.strip()
                    # Remove rank number if present
                    if '. ' in title and title[0].isdigit():
                        title = title.split('. ', 1)[1]

                    # Store basic info, details will be fetched separately
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
                # Search for the movie on IMDb
                search_url = f"https://www.imdb.com/find/?q={movie_title.replace(' ', '+')}"
                search_response = requests.get(search_url, headers=self.headers)
                search_response.raise_for_status()
                search_soup = BeautifulSoup(search_response.text, 'html.parser')

                # Find the first movie result
                movie_link = search_soup.select_one("a[href*='/title/tt']")
                if not movie_link:
                    raise Exception(f"Could not find movie: {movie_title}")

                # Extract the movie ID
                movie_id_match = re.search(r'/title/(tt\d+)', movie_link['href'])
                if not movie_id_match:
                    raise Exception(f"Could not extract movie ID for: {movie_title}")

                movie_id = movie_id_match.group(1)

                # Get the movie page
                movie_url = f"https://www.imdb.com/title/{movie_id}/"
                movie_response = requests.get(movie_url, headers=self.headers)
                movie_response.raise_for_status()
                movie_soup = BeautifulSoup(movie_response.text, 'html.parser')

                # Initialize movie details
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

                # Extract year
                year_element = movie_soup.select_one("[data-testid='title-details-releasedate']")
                if year_element:
                    year_match = re.search(r'\d{4}', year_element.text)
                    if year_match:
                        movie_details["year"] = year_match.group(0)

                # Extract director
                director_element = movie_soup.select_one(
                    "[data-testid='title-pc-principal-credit']:has(a[href*='director'])")
                if director_element:
                    director_name = director_element.select_one("a")
                    if director_name:
                        movie_details["director"] = director_name.text.strip()

                # Extract rating
                rating_element = movie_soup.select_one("[data-testid='hero-rating-bar__aggregate-rating__score']")
                if rating_element:
                    rating_text = rating_element.text.strip()
                    movie_details["rating"] = rating_text

                # Extract genre
                genre_element = movie_soup.select_one("[data-testid='genres']")
                if genre_element:
                    genres = genre_element.select("a")
                    if genres:
                        movie_details["genre"] = ", ".join([g.text.strip() for g in genres])

                # Extract description (plot summary from main page)
                plot_element = movie_soup.select_one("[data-testid='plot']")
                if plot_element:
                    movie_details["description"] = plot_element.text.strip()

                # Extract poster URL
                poster_element = movie_soup.select_one("[data-testid='hero-media__poster'] img")
                if poster_element and 'src' in poster_element.attrs:
                    movie_details["poster_url"] = poster_element['src']

                # Get full storyline from plot summary page
                try:
                    movie_details["storyline"] = self._get_movie_storyline(movie_id)
                except Exception as e:
                    print(f"Could not fetch storyline, using plot summary: {e}")
                    movie_details["storyline"] = movie_details["description"]

                return movie_details

            except Exception as e:
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

        # Try to find storyline elements
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
            # If rank not in dictionary, try to fetch top movies first
            self.fetch_top_movies(limit=rank)

        if rank not in self.movies:
            raise Exception(f"No movie found with rank {rank}")

        movie = self.movies[rank]

        # Skip if details already fetched
        if movie.get("details_fetched", False):
            return movie

        # Get details and update the dictionary
        details = self.get_movie_details(movie["title"])
        details["rank"] = rank  # Ensure rank is preserved
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
        # Get basic info for all movies if not already fetched
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
                    # Add a small delay to avoid overwhelming the server
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

            # Convert string keys to integers
            self.movies = {int(k): v for k, v in self.movies.items()}
            print(f"Successfully loaded {len(self.movies)} movies from {filename}")
            return self.movies
        except Exception as e:
            print(f"Error loading movie data: {e}")
            return {}


# Example usage
if __name__ == "__main__":
    manager = MovieManager()

    # Load existing data or fetch new data
    if os.path.exists("movie_data.json"):
        manager.load_from_file()
    else:
        # Fetch top 10 movies
        movies = manager.fetch_top_movies(limit=10)
        print(f"Fetched {len(movies)} top movies")

        # Fetch details for all movies
        manager.fetch_all_details()

        # Save to file
        manager.save_to_file()

    # Display the top movies with details
    for rank in sorted(manager.movies.keys()):
        movie = manager.movies[rank]
        print(f"{rank}. {movie['title']} ({movie.get('year', 'N/A')}) - Rating: {movie.get('rating', 'N/A')}")
        print(f"   Director: {movie.get('director', 'N/A')}")
        print(f"   Genre: {movie.get('genre', 'N/A')}")
        print(f"   Description: {movie.get('description', 'N/A')[:100]}...")
        print(f"   Storyline: {movie.get('storyline', 'N/A')[:100]}...")