import random

# Market dictionary
MARKETS = {
    # Geography
    "Number of streets in Boston": 25923,
    "Total length of the Great Wall of China in miles": 13171,
    "Population of Tokyo in 2023 (millions)": 37.4,
    "Depth of the Mariana Trench in feet": 36201,
    "Height of Mount Everest in feet": 29032,
    "Surface area of the Moon in square miles": 14600000,
    "Distance from Earth to the Sun in miles": 93000000,
    "Area of the Sahara Desert in square miles": 3600000,
    "Length of the Amazon River in miles": 4345,
    "Number of islands in the Philippines": 7641,
    "Population of Canada in 2023 (millions)": 38.25,
    "Area of Russia in square miles": 6633000,
    "Population of Australia in 2023 (millions)": 26.1,
    "Number of bridges in Venice": 391,
    "Number of countries in the world": 195,
    "Length of the Nile River in miles": 4132,
    "Number of volcanoes in Indonesia": 147,
    "Population of India in 2023 (millions)": 1420,
    "Population of the USA in 2023 (millions)": 331.9,
    "Area of Antarctica in square miles": 5500000,

    # Science
    "Speed of light in miles per second": 186282,
    "Age of the Earth in years (billions)": 4.54,
    "Age of the universe in years (billions)": 13.8,
    "Number of bones in the human body": 206,
    "Calories in a Big Mac": 563,
    "Number of elements in the periodic table": 118,
    "Weight of an average elephant in pounds": 13000,
    "Number of cells in the human body (trillions)": 37.2,
    "Volume of water in the Pacific Ocean in cubic miles": 187000000,
    "Temperature at the Sun's core in Fahrenheit": 27000000,
    "Number of teeth in a great white shark": 300,
    "Wavelength of visible light in nanometers": 380,
    "Density of gold in grams per cubic centimeter": 19.32,
    "Number of chromosomes in humans": 46,
    "Circumference of Earth in miles": 24901,
    "Length of a DNA molecule in a human cell in feet": 6.5,
    "Acceleration due to gravity on Earth in m/s^2": 9.8,
    "Number of moons orbiting Jupiter": 95,
    "Distance to the nearest star (Proxima Centauri) in light years": 4.24,

    # History
    "Year the Declaration of Independence was signed": 1776,
    "Number of US presidents as of 2023": 46,
    "Year the Berlin Wall fell": 1989,
    "Length of World War II in years": 6,
    "Number of pyramids in Egypt": 138,
    "Year the Titanic sank": 1912,
    "Population of the Roman Empire at its peak (millions)": 56,
    "Number of monarchs in British history": 62,
    "Year the first moon landing occurred": 1969,
    "Number of years the Ming Dynasty ruled China": 276,
    "Length of the Hundred Years' War in years": 116,
    "Year the US Civil War ended": 1865,
    "Year Christopher Columbus arrived in America": 1492,
    "Number of nations involved in World War I": 32,
    "Year the Great Fire of London occurred": 1666,
    "Number of years the Ottoman Empire lasted": 623,
    "Number of US states that fought for the Union in the Civil War": 20,
    "Year the Great Depression started": 1929,
    "Number of years Nelson Mandela was imprisoned": 27,

    # Sports
    "Number of players on a soccer field (both teams)": 22,
    "Number of NBA teams": 30,
    "Number of Super Bowls played as of 2023": 57,
    "Length of an Olympic swimming pool in meters": 50,
    "Number of tennis Grand Slam titles won by Serena Williams": 23,
    "Number of laps in the Indianapolis 500": 200,
    "Height of a basketball hoop in feet": 10,
    "Length of a football field in yards": 100,
    "Number of FIFA World Cups held as of 2023": 22,
    "Number of Olympic gold medals won by Michael Phelps": 23,
    "Number of baseball teams in MLB": 30,
    "Number of holes on a standard golf course": 18,
    "Length of a marathon in miles": 26.2,
    "Number of players on an American football team roster": 53,
    "Number of minutes in a hockey game": 60,
    "Height of a volleyball net in feet": 7.4,
    "Number of strokes in a perfect bowling game": 12,
    "Number of times the Olympics have been canceled due to war": 3,
    "Number of races in the 2023 Formula 1 season": 23,

    # General Trivia
    "Number of Starbucks locations worldwide (2023)": 36000,
    "Number of McDonald's restaurants worldwide (2023)": 40000,
    "Population of New York City in 2023 (millions)": 8.8,
    "Area of the Amazon Rainforest in square miles": 2110000,
    "Number of novels written by Jane Austen": 6,
    "Number of symphonies composed by Beethoven": 9,
    "Number of seats in the US House of Representatives": 435,
    "Number of official languages in India": 22,
    "Number of planets in the solar system": 8,
    "Weight of an average blue whale in pounds": 300000,
    "Number of legs on a spider": 8,
    "Number of seconds in a day": 86400,
    "Number of piano keys": 88,
    "Number of floors in the Empire State Building": 102,
    "Number of books in the Harry Potter series": 7,
    "Length of the Great Barrier Reef in miles": 1429,
    "Population of London in 2023 (millions)": 9.5,
    "Number of bones in a giraffe's neck": 7,
    "Number of Oscars won by Meryl Streep": 3,
}

def get_random_market():
    """
    Returns a random market question and its correct answer.
    """
    question = random.choice(list(MARKETS.keys()))
    answer = MARKETS[question]
    return question, answer

def get_market_answer(market_question):
    """
    Returns the correct answer for a specific market question.
    """
    return MARKETS.get(market_question, None)

def get_all_markets():
    """
    Returns the entire dictionary of markets.
    """
    return MARKETS

def add_market(question, answer):
    """
    Adds a new market question and answer to the dictionary.
    Ensures no duplicates.
    """
    if question in MARKETS:
        raise ValueError("Market question already exists.")
    MARKETS[question] = answer
