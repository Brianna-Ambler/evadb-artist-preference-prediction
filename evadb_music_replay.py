# -*- coding: utf-8 -*-
"""EvaDB Music Replay

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1qNmJFXhX_HSA048XIsNoEZI3FgV_KtO3

# Project Management Tool for Task Delegation
In this tutorial, we use EvaDB + ChatGPT to categorize tasks and effectively assign them to members of a team project based on their strengths and weaknesses.

<table align="left">
  <td>
    <a target="_blank" href="https://colab.research.google.com/github/georgia-tech-db/eva/blob/staging/tutorials/14-food-review-tone-analysis-and-response.ipynb"><img src="https://www.tensorflow.org/images/colab_logo_32px.png" /> Run on Google Colab</a>
  </td>
  <td>
    <a target="_blank" href="https://github.com/georgia-tech-db/eva/blob/staging/tutorials/14-food-review-tone-analysis-and-response.ipynb"><img src="https://www.tensorflow.org/images/GitHub-Mark-32px.png" /> View source on GitHub</a>
  </td>
  <td>
    <a target="_blank" href="https://github.com/georgia-tech-db/eva/raw/staging/tutorials/14-food-review-tone-analysis-and-response.ipynb"><img src="https://www.tensorflow.org/images/download_logo_32px.png" /> Download notebook</a>
  </td>
</table><br><br>

## Start Postgres
"""

!apt install postgresql
!service postgresql start

"""## Create User and Database"""

!sudo -u postgres psql -c "CREATE USER eva WITH SUPERUSER PASSWORD 'myPassword'"
!sudo -u postgres psql -c "CREATE DATABASE evadb"

import csv
import psycopg2

"""## Install EvaDB"""

# Commented out IPython magic to ensure Python compatibility.
# %pip install --quiet "evadb[document]"
# %pip install psycopg2

import evadb
cursor = evadb.connect().cursor()

import warnings
warnings.filterwarnings("ignore")

from IPython.core.display import display, HTML
def pretty_print(df):
    return display(HTML( df.to_html().replace("\\n","<br>")))

import pandas as pd
pd.set_option('display.max_colwidth', None)

# Commented out IPython magic to ensure Python compatibility.
# %pip install evadb[sklearn]

# Commented out IPython magic to ensure Python compatibility.
# %pip install "flaml[automl]"

# Commented out IPython magic to ensure Python compatibility.
# %pip install evadb[ludwig]

# Download ChatGPT UDF if needed
!wget -nc https://raw.githubusercontent.com/georgia-tech-db/eva/master/evadb/functions/chatgpt.py -O chatgpt.py

"""## Create Data Source in EvaDB
We use data source to connect EvaDB directly to underlying database systems like Postgres.
"""

params = {
    "user": "eva",
    "password": "myPassword",
    "host": "localhost",
    "port": "5432",
    "database": "evadb",
}
query  = """Drop database if exists apple_music;"""
cursor.query(query).df()
query = f"CREATE DATABASE apple_music WITH ENGINE = 'postgres', PARAMETERS = {params};"
cursor.query(query).df()

# Commented out IPython magic to ensure Python compatibility.
# %pip freeze > requirements.txt

"""## Creating a Cursor for the PostgreSQL Database"""

conn = psycopg2.connect(database="evadb",
                        user='eva', password='myPassword',
                        host='localhost', port='5432'
)

conn.autocommit = True
cursor2 = conn.cursor()

"""## Setting the OpenAI Key"""

import os
os.environ["OPENAI_API_KEY"] = "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"

"""# Defining the Database Schema

### Artists Played by the User
"""

# Creating the artists table
cursor.query("""USE apple_music {
  DROP TABLE IF EXISTS artists
}""").df()

cursor.query("""
USE apple_music {
  CREATE TABLE artists (artist_id INT NOT NULL, artist_name VARCHAR(500) NOT NULL, hours_listened FLOAT, rank INT, duration VARCHAR(500), age INT, genre VARCHAR(500), dominant_era VARCHAR(500), preference INT)
}
""").df()

# Loading the artists table
command = '''COPY artists(artist_id, artist_name, hours_listened, rank, duration, age, genre, dominant_era, preference)
FROM '/content/artists.csv'
DELIMITER ','
CSV HEADER;'''
cursor2.execute(command)

"""### Artists Unplayed by the User

"""

# Creating the suggested artists table
cursor.query("""USE apple_music {
  DROP TABLE IF EXISTS suggested_artists
}""").df()

cursor.query("""
USE apple_music {
  CREATE TABLE suggested_artists (artist_id INT NOT NULL, artist_name VARCHAR(500) NOT NULL, age INT, genre VARCHAR(500), dominant_era VARCHAR(500), preference INT)
}
""").df()

# Loading the suggested artists table
command = '''COPY suggested_artists(artist_id, artist_name,  age, genre, dominant_era, preference)
FROM '/content/suggested_artists.csv'
DELIMITER ','
CSV HEADER;'''
cursor2.execute(command)

"""### Genres Played by the User"""

# Creating the genres table
cursor.query("""USE apple_music {
  DROP TABLE IF EXISTS genres
}""").df()

cursor.query("""
USE apple_music {
  CREATE TABLE genres (genre_id INT NOT NULL, genre VARCHAR(500) NOT NULL, hours_listened FLOAT, rank INT, duration VARCHAR(500))
}
""").df()

# Loading the genres table
command = '''COPY genres(genre_id, genre, hours_listened, rank, duration)
FROM '/content/genres.csv'
DELIMITER ','
CSV HEADER;'''
cursor2.execute(command)

## Previewing the table
cursor.query("Select * from apple_music.genres limit 3;").df();

"""### Songs Played by the User"""

# Creating the songs table
cursor.query("""USE apple_music {
  DROP TABLE IF EXISTS songs
}""").df()

cursor.query("""
USE apple_music {
  CREATE TABLE songs (song_id INT NOT NULL, song_name VARCHAR(500) NOT NULL, sentiment_rating FLOAT)
}
""").df()

# Loading the songs table
command = '''COPY songs(song_id, song_name, sentiment_rating)
FROM '/content/songs.csv'
DELIMITER ','
CSV HEADER;'''
cursor2.execute(command)

## Previewing the table
cursor.query("Select * from apple_music.songs limit 3;").df();

"""# Rate the positivity of the user's music"""

prompt = f"""
SELECT song_name, ChatGPT(
  "Using your knowledge of this song track, I want you to evaluate its sentiment. If you are unable to provide a rating, respond with -1 . Otherwise, on a scale of 1-10 (1 being sad/negative, 5 being neutral, and 10 being happy/positive), how would you rate the sentiment of this song t? Only respond with the rating! Only respond with numbers.
", song_name) FROM apple_music.songs limit 10;
"""
cursor.query(prompt).df()

"""# Suggest Artists

### Training the Model on the User's Artist Preferences
"""

cursor.query("""
  CREATE OR REPLACE FUNCTION PredictArtistCompatibility FROM
  ( SELECT age, genre, dominant_era, preference FROM apple_music.artists )
  TYPE Ludwig
  PREDICT 'preference'
  TIME_LIMIT 240;
""").df()

"""### Testing the Model's Predictions on the User's Played Artists"""

cursor.query("""
  SELECT preference, predicted_preference FROM apple_music.artists
  JOIN LATERAL PredictArtistCompatibility(age, genre, dominant_era, preference) AS Predicted(predicted_preference) LIMIT 10;
""").df()

"""### Testing the model on the user's unplayed artists"""

cursor.query("SELECT artist_name, PredictArtistCompatibility(age, genre, dominant_era, preference) FROM apple_music.suggested_artists LIMIT 11;").df()