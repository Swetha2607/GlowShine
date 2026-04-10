"""
Health Tracker — Water, Meals, Calories, Steps & Kidney Health
==============================================================
A personal health tracking web app.

Features:
  - Water intake reminders & logging
  - Meal logging (breakfast, lunch, dinner, snacks)
  - Calorie calculation with built-in food database
  - Daily step recommendations based on calorie intake
  - Kidney health tips & hydration targets

Run:
    python app.py
    Open http://localhost:5000
"""

import os, json, sqlite3, math, random
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash

app = Flask(__name__)
app.secret_key = "health-tracker-secret-key-change-me"

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "health.db"))

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS water_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        amount_ml   INTEGER NOT NULL DEFAULT 250
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS meal_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        meal_type   TEXT NOT NULL,
        food_name   TEXT NOT NULL,
        quantity    REAL NOT NULL DEFAULT 1.0,
        unit        TEXT NOT NULL DEFAULT 'serving',
        calories    REAL NOT NULL DEFAULT 0,
        protein_g   REAL NOT NULL DEFAULT 0,
        carbs_g     REAL NOT NULL DEFAULT 0,
        fat_g       REAL NOT NULL DEFAULT 0,
        sodium_mg   REAL NOT NULL DEFAULT 0,
        potassium_mg REAL NOT NULL DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS todo (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        task        TEXT NOT NULL,
        done        INTEGER NOT NULL DEFAULT 0,
        priority    TEXT NOT NULL DEFAULT 'medium',
        created     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        due_date    TEXT DEFAULT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS expense_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        amount      REAL NOT NULL,
        note        TEXT DEFAULT ''
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS pantry (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name   TEXT NOT NULL UNIQUE,
        quantity    INTEGER NOT NULL DEFAULT 0,
        unit        TEXT NOT NULL DEFAULT 'pieces',
        category    TEXT NOT NULL DEFAULT 'fruit',
        low_stock   INTEGER NOT NULL DEFAULT 2,
        added_date  TEXT NOT NULL DEFAULT (date('now','localtime')),
        updated     TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS habit_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT NOT NULL,
        habit_name  TEXT NOT NULL,
        done        INTEGER NOT NULL DEFAULT 0,
        note        TEXT DEFAULT '',
        UNIQUE(date, habit_name)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS step_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT NOT NULL,
        steps       INTEGER NOT NULL DEFAULT 0,
        UNIQUE(date)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS user_profile (
        id              INTEGER PRIMARY KEY CHECK (id = 1),
        name            TEXT NOT NULL DEFAULT '',
        weight_kg       REAL NOT NULL DEFAULT 70,
        height_cm       REAL NOT NULL DEFAULT 170,
        age             INTEGER NOT NULL DEFAULT 30,
        gender          TEXT NOT NULL DEFAULT 'female',
        activity_level  TEXT NOT NULL DEFAULT 'moderate',
        kidney_concern  INTEGER NOT NULL DEFAULT 1,
        water_goal_ml   INTEGER NOT NULL DEFAULT 2500,
        calorie_goal    INTEGER NOT NULL DEFAULT 2000,
        water_reminder_min INTEGER NOT NULL DEFAULT 60
    )""")
    conn.commit()
    # Insert default profile if not exists
    cur = conn.execute("SELECT COUNT(*) FROM user_profile")
    if cur.fetchone()[0] == 0:
        conn.execute("""INSERT INTO user_profile
            (id, name, weight_kg, height_cm, age, gender, activity_level,
             kidney_concern, water_goal_ml, calorie_goal, water_reminder_min)
            VALUES (1, '', 70, 170, 25, 'female', 'moderate', 1, 2500, 2000, 60)""")
    else:
        # Add name column if upgrading from old schema
        try:
            conn.execute("ALTER TABLE user_profile ADD COLUMN name TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Word of the Day — Professional + Gen Z vocabulary
# ---------------------------------------------------------------------------

PROFESSIONAL_WORDS = [
    {"word": "Synergy", "meaning": "Combined effort producing a greater result than individual parts",
     "example": "The synergy between design and engineering teams led to a breakthrough product."},
    {"word": "Bandwidth", "meaning": "Capacity to handle tasks or workload",
     "example": "I don't have the bandwidth to take on another project this week."},
    {"word": "Leverage", "meaning": "To use something to maximum advantage",
     "example": "Let's leverage our existing customer base to launch the new feature."},
    {"word": "Pivot", "meaning": "To change direction or strategy",
     "example": "After the market feedback, we decided to pivot our approach."},
    {"word": "Scalable", "meaning": "Able to grow or expand efficiently",
     "example": "We need a scalable solution that works for 100 or 100,000 users."},
    {"word": "Deliverable", "meaning": "A tangible outcome or product to be delivered",
     "example": "The key deliverable for Q2 is the mobile app redesign."},
    {"word": "Stakeholder", "meaning": "Person with interest or concern in a project",
     "example": "We need to align with all stakeholders before the release."},
    {"word": "Cadence", "meaning": "Regular rhythm or pace of activities",
     "example": "We follow a bi-weekly sprint cadence for feature releases."},
    {"word": "Actionable", "meaning": "Able to be acted upon; practical",
     "example": "Please provide actionable feedback, not just general complaints."},
    {"word": "Paradigm", "meaning": "A model or framework of thinking",
     "example": "This new AI tool represents a paradigm shift in how we work."},
    {"word": "Robust", "meaning": "Strong, well-built, able to withstand pressure",
     "example": "We need a more robust testing framework before launch."},
    {"word": "Efficacy", "meaning": "The ability to produce a desired result",
     "example": "The efficacy of our new onboarding flow is clear from the retention data."},
    {"word": "Holistic", "meaning": "Considering the whole rather than individual parts",
     "example": "We need a holistic approach that considers UX, performance, and security."},
    {"word": "Iterate", "meaning": "To refine through repeated cycles",
     "example": "Let's iterate on this design based on user feedback."},
    {"word": "Proactive", "meaning": "Acting in advance to deal with expected issues",
     "example": "Being proactive about code reviews saves time in the long run."},
    {"word": "Benchmark", "meaning": "A standard of measurement for comparison",
     "example": "Our response time is well below the industry benchmark of 200ms."},
    {"word": "Streamline", "meaning": "To make more efficient by simplifying",
     "example": "We need to streamline the approval process — it takes too long."},
    {"word": "Granular", "meaning": "Detailed, broken down into small parts",
     "example": "Can we get a more granular breakdown of the metrics by region?"},
    {"word": "Catalyst", "meaning": "Something that triggers or accelerates change",
     "example": "The new CTO was a catalyst for the company's digital transformation."},
    {"word": "Pragmatic", "meaning": "Dealing with things realistically and practically",
     "example": "Let's take a pragmatic approach and fix the critical bugs first."},
    {"word": "Circumspect", "meaning": "Careful, considering all circumstances",
     "example": "Be circumspect when reviewing the contract terms before signing."},
    {"word": "Elucidate", "meaning": "To make something clear; explain",
     "example": "Could you elucidate the reasoning behind this architectural decision?"},
    {"word": "Impetus", "meaning": "The force or motivation behind an action",
     "example": "The customer complaints were the impetus for redesigning the UI."},
    {"word": "Cogent", "meaning": "Clear, logical, and convincing",
     "example": "She presented a cogent argument for adopting the new framework."},
    {"word": "Meticulous", "meaning": "Showing great attention to detail",
     "example": "His meticulous code reviews catch bugs before they reach production."},
    {"word": "Precedent", "meaning": "An earlier event used as a guide for future decisions",
     "example": "This sets a good precedent for how we handle security incidents."},
    {"word": "Ubiquitous", "meaning": "Found everywhere; widespread",
     "example": "Smartphones have become ubiquitous in daily life and work."},
    {"word": "Tenacious", "meaning": "Persistent, determined, not giving up easily",
     "example": "Her tenacious debugging finally uncovered the race condition."},
    {"word": "Equitable", "meaning": "Fair and impartial",
     "example": "We need an equitable workload distribution across the team."},
    {"word": "Lucid", "meaning": "Expressed clearly; easy to understand",
     "example": "His documentation is always lucid — even new hires can follow it."},
]

GENZ_WORDS = [
    {"word": "Slay", "meaning": "To do something exceptionally well",
     "example": "You absolutely slayed that presentation. Everyone was impressed."},
    {"word": "No cap", "meaning": "No lie; I'm being completely honest",
     "example": "No cap, this is the best biryani I've ever had."},
    {"word": "Bussin'", "meaning": "Really good, especially food",
     "example": "This dal makhani is bussin' — your mom's recipe hits different."},
    {"word": "It's giving", "meaning": "It has the vibe/energy of...",
     "example": "Your new haircut? It's giving main character energy."},
    {"word": "Bet", "meaning": "Okay / agreement / I'm in",
     "example": "'Want to grab lunch?' 'Bet, let's go.'"},
    {"word": "Vibe check", "meaning": "Assessing the mood or energy of a situation",
     "example": "Vibe check on the team meeting — was it productive or chaotic?"},
    {"word": "Stan", "meaning": "To be an enthusiastic fan of something/someone",
     "example": "I stan green tea — it's been a game changer for my energy."},
    {"word": "Lowkey", "meaning": "Somewhat / secretly / not obviously",
     "example": "I'm lowkey addicted to tracking my water intake now."},
    {"word": "Highkey", "meaning": "Very much / openly / obviously",
     "example": "I'm highkey proud of hitting 10K steps today."},
    {"word": "Periodt", "meaning": "End of discussion; emphasizes a point",
     "example": "Water is the best drink for your kidneys. Periodt."},
    {"word": "Hits different", "meaning": "Feels uniquely special or better than usual",
     "example": "Morning walks when the weather is cool just hits different."},
    {"word": "Rent free", "meaning": "Can't stop thinking about it",
     "example": "That motivational quote is living rent free in my head."},
    {"word": "Main character", "meaning": "Acting like the protagonist; owning your life",
     "example": "Going to the gym at 6 AM — full main character energy."},
    {"word": "Understood the assignment", "meaning": "Nailed it; did exactly what was needed",
     "example": "Your meal prep this week? You understood the assignment."},
    {"word": "Era", "meaning": "A phase or period you're in",
     "example": "I'm in my health era — gym, clean eating, 8 hours sleep."},
    {"word": "Ate", "meaning": "Did exceptionally well (similar to slay)",
     "example": "You ate that workout today, absolutely crushed it."},
    {"word": "Ick", "meaning": "Something that gives you an instant turnoff feeling",
     "example": "People who don't drink water? That's an ick."},
    {"word": "Snatched", "meaning": "Looking really good; on point",
     "example": "After 30 days of the routine, your skin is going to look snatched."},
    {"word": "IYKYK", "meaning": "If You Know, You Know — insider reference",
     "example": "Methi water in the morning... IYKYK."},
    {"word": "Delulu", "meaning": "Delusional (used humorously)",
     "example": "Thinking I can eat 3 samosas and still be in calorie deficit — delulu is the solulu."},
    {"word": "Rizz", "meaning": "Charisma; ability to charm",
     "example": "His confidence in that meeting was pure unspoken rizz."},
    {"word": "Fire", "meaning": "Amazing; excellent",
     "example": "This playlist is straight fire for a morning workout."},
    {"word": "Sus", "meaning": "Suspicious; questionable",
     "example": "That email asking for my password looks pretty sus."},
    {"word": "Drip", "meaning": "Stylish outfit or appearance",
     "example": "New gym outfit? That's some serious drip."},
    {"word": "W / L", "meaning": "Win / Loss — used to rate outcomes",
     "example": "Hitting your step goal every day this week? That's a massive W."},
    {"word": "Touch grass", "meaning": "Go outside; take a break from screens",
     "example": "You've been coding for 6 hours straight. Go touch grass."},
    {"word": "Caught in 4K", "meaning": "Caught red-handed with clear evidence",
     "example": "Said you're on a diet but caught in 4K eating ice cream at 11 PM."},
    {"word": "Goated", "meaning": "The greatest of all time at something",
     "example": "Your mom's cooking is goated — no restaurant compares."},
    {"word": "Sending me", "meaning": "Making me laugh uncontrollably",
     "example": "The way you described that bug report is sending me."},
    {"word": "Yeet", "meaning": "To throw with force; also used as an exclamation",
     "example": "Time to yeet those junk foods out of the pantry."},
]


def get_words_of_the_day():
    """Get consistent word-of-the-day based on date (changes daily)."""
    day_seed = int(date.today().strftime("%Y%m%d"))
    rng = random.Random(day_seed)
    pro_word = rng.choice(PROFESSIONAL_WORDS)
    gen_word = rng.choice(GENZ_WORDS)
    return pro_word, gen_word


# ---------------------------------------------------------------------------
# Food database (common Indian + international foods, per serving)
# ---------------------------------------------------------------------------

FOOD_DB = {
    # -- Breakfast --
    "idli (1 piece)":           {"cal": 39,  "protein": 1.5, "carbs": 7.5,  "fat": 0.2, "sodium": 45,  "potassium": 25,  "unit": "piece"},
    "dosa (1 plain)":           {"cal": 120, "protein": 3.0, "carbs": 18,   "fat": 4.0, "sodium": 130, "potassium": 60,  "unit": "piece"},
    "masala dosa":              {"cal": 250, "protein": 5.0, "carbs": 32,   "fat": 12,  "sodium": 250, "potassium": 180, "unit": "piece"},
    "upma (1 cup)":             {"cal": 210, "protein": 5.0, "carbs": 30,   "fat": 8.0, "sodium": 350, "potassium": 100, "unit": "cup"},
    "poha (1 cup)":             {"cal": 180, "protein": 4.0, "carbs": 32,   "fat": 5.0, "sodium": 300, "potassium": 90,  "unit": "cup"},
    "paratha (1 plain)":        {"cal": 180, "protein": 4.0, "carbs": 24,   "fat": 7.0, "sodium": 200, "potassium": 80,  "unit": "piece"},
    "aloo paratha":             {"cal": 300, "protein": 6.0, "carbs": 38,   "fat": 14,  "sodium": 350, "potassium": 250, "unit": "piece"},
    "puri (1 piece)":           {"cal": 100, "protein": 2.0, "carbs": 12,   "fat": 5.0, "sodium": 120, "potassium": 40,  "unit": "piece"},
    "vada (1 piece)":           {"cal": 130, "protein": 4.0, "carbs": 14,   "fat": 7.0, "sodium": 180, "potassium": 90,  "unit": "piece"},
    "pongal (1 cup)":           {"cal": 200, "protein": 5.0, "carbs": 30,   "fat": 7.0, "sodium": 250, "potassium": 120, "unit": "cup"},
    "toast (1 slice)":          {"cal": 75,  "protein": 2.5, "carbs": 13,   "fat": 1.0, "sodium": 130, "potassium": 40,  "unit": "slice"},
    "bread (1 slice)":          {"cal": 75,  "protein": 2.5, "carbs": 13,   "fat": 1.0, "sodium": 130, "potassium": 40,  "unit": "slice"},
    "omelette (2 eggs)":        {"cal": 180, "protein": 12,  "carbs": 1.0,  "fat": 14,  "sodium": 320, "potassium": 140, "unit": "serving"},
    "boiled egg":               {"cal": 78,  "protein": 6.3, "carbs": 0.6,  "fat": 5.3, "sodium": 62,  "potassium": 63,  "unit": "piece"},
    "oatmeal (1 cup)":          {"cal": 150, "protein": 5.0, "carbs": 27,   "fat": 2.5, "sodium": 0,   "potassium": 140, "unit": "cup"},
    "cornflakes (1 cup)":       {"cal": 100, "protein": 2.0, "carbs": 24,   "fat": 0.2, "sodium": 200, "potassium": 30,  "unit": "cup"},
    "milk (1 cup)":             {"cal": 120, "protein": 8.0, "carbs": 12,   "fat": 5.0, "sodium": 100, "potassium": 350, "unit": "cup"},
    "tea (1 cup)":              {"cal": 30,  "protein": 0.5, "carbs": 5.0,  "fat": 1.0, "sodium": 10,  "potassium": 50,  "unit": "cup"},
    "coffee (1 cup)":           {"cal": 35,  "protein": 0.5, "carbs": 5.0,  "fat": 1.5, "sodium": 15,  "potassium": 60,  "unit": "cup"},
    "banana":                   {"cal": 105, "protein": 1.3, "carbs": 27,   "fat": 0.4, "sodium": 1,   "potassium": 422, "unit": "piece"},
    "apple":                    {"cal": 95,  "protein": 0.5, "carbs": 25,   "fat": 0.3, "sodium": 2,   "potassium": 195, "unit": "piece"},
    "orange":                   {"cal": 62,  "protein": 1.2, "carbs": 15,   "fat": 0.2, "sodium": 0,   "potassium": 237, "unit": "piece"},
    "yogurt (1 cup)":           {"cal": 100, "protein": 17,  "carbs": 6.0,  "fat": 0.7, "sodium": 65,  "potassium": 240, "unit": "cup"},
    "curd (1 cup)":             {"cal": 100, "protein": 8.0, "carbs": 8.0,  "fat": 4.0, "sodium": 60,  "potassium": 230, "unit": "cup"},
    "pancake (1 piece)":        {"cal": 90,  "protein": 2.5, "carbs": 11,   "fat": 4.0, "sodium": 170, "potassium": 50,  "unit": "piece"},

    # -- Rice & Roti --
    "rice (1 cup cooked)":      {"cal": 206, "protein": 4.3, "carbs": 45,   "fat": 0.4, "sodium": 1,   "potassium": 55,  "unit": "cup"},
    "chapati / roti":           {"cal": 104, "protein": 3.0, "carbs": 18,   "fat": 3.0, "sodium": 120, "potassium": 50,  "unit": "piece"},
    "naan (1 piece)":           {"cal": 260, "protein": 8.0, "carbs": 42,   "fat": 5.0, "sodium": 460, "potassium": 80,  "unit": "piece"},
    "biryani (1 plate)":        {"cal": 500, "protein": 18,  "carbs": 60,   "fat": 20,  "sodium": 700, "potassium": 300, "unit": "plate"},

    # -- Curries & Dals --
    "dal (1 cup)":              {"cal": 180, "protein": 12,  "carbs": 28,   "fat": 2.0, "sodium": 400, "potassium": 500, "unit": "cup"},
    "sambar (1 cup)":           {"cal": 130, "protein": 7.0, "carbs": 20,   "fat": 3.0, "sodium": 500, "potassium": 350, "unit": "cup"},
    "rasam (1 cup)":            {"cal": 60,  "protein": 2.0, "carbs": 10,   "fat": 1.5, "sodium": 600, "potassium": 200, "unit": "cup"},
    "paneer butter masala":     {"cal": 400, "protein": 15,  "carbs": 16,   "fat": 30,  "sodium": 700, "potassium": 200, "unit": "serving"},
    "chole / chana masala":     {"cal": 250, "protein": 12,  "carbs": 35,   "fat": 8.0, "sodium": 600, "potassium": 400, "unit": "serving"},
    "rajma (1 cup)":            {"cal": 210, "protein": 13,  "carbs": 36,   "fat": 1.5, "sodium": 450, "potassium": 600, "unit": "cup"},
    "chicken curry":            {"cal": 300, "protein": 25,  "carbs": 10,   "fat": 18,  "sodium": 650, "potassium": 350, "unit": "serving"},
    "fish curry":               {"cal": 250, "protein": 22,  "carbs": 8,    "fat": 14,  "sodium": 550, "potassium": 400, "unit": "serving"},
    "egg curry (2 eggs)":       {"cal": 280, "protein": 16,  "carbs": 12,   "fat": 18,  "sodium": 500, "potassium": 250, "unit": "serving"},
    "palak paneer":             {"cal": 320, "protein": 14,  "carbs": 12,   "fat": 24,  "sodium": 550, "potassium": 450, "unit": "serving"},
    "aloo gobi":                {"cal": 180, "protein": 5.0, "carbs": 22,   "fat": 9.0, "sodium": 400, "potassium": 350, "unit": "serving"},
    "mixed veg curry":          {"cal": 150, "protein": 4.0, "carbs": 18,   "fat": 7.0, "sodium": 350, "potassium": 300, "unit": "serving"},

    # -- Snacks --
    "samosa (1 piece)":         {"cal": 250, "protein": 4.0, "carbs": 25,   "fat": 15,  "sodium": 350, "potassium": 100, "unit": "piece"},
    "bhaji / pakora (5 pcs)":   {"cal": 200, "protein": 4.0, "carbs": 18,   "fat": 13,  "sodium": 400, "potassium": 100, "unit": "serving"},
    "biscuit (1 piece)":        {"cal": 50,  "protein": 0.6, "carbs": 7.0,  "fat": 2.0, "sodium": 50,  "potassium": 15,  "unit": "piece"},
    "chips (small pack)":       {"cal": 150, "protein": 2.0, "carbs": 15,   "fat": 10,  "sodium": 180, "potassium": 350, "unit": "pack"},
    "peanuts (1/4 cup)":        {"cal": 210, "protein": 9.0, "carbs": 6.0,  "fat": 18,  "sodium": 5,   "potassium": 200, "unit": "quarter-cup"},
    "almonds (10 pieces)":      {"cal": 70,  "protein": 2.6, "carbs": 2.5,  "fat": 6.0, "sodium": 0,   "potassium": 80,  "unit": "10 pieces"},
    "dates (2 pieces)":         {"cal": 55,  "protein": 0.4, "carbs": 15,   "fat": 0.0, "sodium": 0,   "potassium": 130, "unit": "2 pieces"},

    # -- International --
    "sandwich":                 {"cal": 350, "protein": 15,  "carbs": 35,   "fat": 16,  "sodium": 700, "potassium": 250, "unit": "piece"},
    "burger":                   {"cal": 500, "protein": 25,  "carbs": 40,   "fat": 26,  "sodium": 800, "potassium": 300, "unit": "piece"},
    "pizza (1 slice)":          {"cal": 270, "protein": 12,  "carbs": 33,   "fat": 10,  "sodium": 600, "potassium": 180, "unit": "slice"},
    "pasta (1 plate)":          {"cal": 400, "protein": 12,  "carbs": 56,   "fat": 14,  "sodium": 600, "potassium": 220, "unit": "plate"},
    "fried rice (1 plate)":     {"cal": 350, "protein": 8.0, "carbs": 50,   "fat": 13,  "sodium": 800, "potassium": 150, "unit": "plate"},
    "noodles (1 plate)":        {"cal": 350, "protein": 8.0, "carbs": 48,   "fat": 14,  "sodium": 900, "potassium": 130, "unit": "plate"},
    "salad (1 bowl)":           {"cal": 80,  "protein": 3.0, "carbs": 12,   "fat": 2.0, "sodium": 50,  "potassium": 350, "unit": "bowl"},
    "soup (1 bowl)":            {"cal": 120, "protein": 6.0, "carbs": 15,   "fat": 4.0, "sodium": 800, "potassium": 250, "unit": "bowl"},
    "grilled chicken breast":   {"cal": 165, "protein": 31,  "carbs": 0,    "fat": 3.6, "sodium": 74,  "potassium": 256, "unit": "serving"},
    "fried chicken (1 piece)":  {"cal": 250, "protein": 18,  "carbs": 8,    "fat": 16,  "sodium": 500, "potassium": 200, "unit": "piece"},

    # -- Drinks --
    "water (1 glass)":          {"cal": 0,   "protein": 0,   "carbs": 0,    "fat": 0,   "sodium": 5,   "potassium": 0,   "unit": "glass"},
    "coconut water":            {"cal": 45,  "protein": 1.7, "carbs": 9.0,  "fat": 0.5, "sodium": 250, "potassium": 600, "unit": "cup"},
    "buttermilk (1 glass)":     {"cal": 40,  "protein": 3.0, "carbs": 5.0,  "fat": 1.0, "sodium": 150, "potassium": 200, "unit": "glass"},
    "lassi (1 glass)":          {"cal": 160, "protein": 5.0, "carbs": 25,   "fat": 5.0, "sodium": 80,  "potassium": 250, "unit": "glass"},
    "juice (1 glass)":          {"cal": 110, "protein": 1.0, "carbs": 26,   "fat": 0.3, "sodium": 5,   "potassium": 350, "unit": "glass"},
    "soft drink (1 can)":       {"cal": 140, "protein": 0,   "carbs": 39,   "fat": 0,   "sodium": 45,  "potassium": 0,   "unit": "can"},
    "energy drink":             {"cal": 110, "protein": 0,   "carbs": 28,   "fat": 0,   "sodium": 200, "potassium": 10,  "unit": "can"},

    # -- Desserts --
    "gulab jamun (1 piece)":    {"cal": 150, "protein": 2.0, "carbs": 22,   "fat": 6.0, "sodium": 50,  "potassium": 40,  "unit": "piece"},
    "rasgulla (1 piece)":       {"cal": 120, "protein": 2.5, "carbs": 24,   "fat": 1.5, "sodium": 30,  "potassium": 30,  "unit": "piece"},
    "jalebi (1 piece)":         {"cal": 150, "protein": 1.0, "carbs": 25,   "fat": 6.0, "sodium": 20,  "potassium": 15,  "unit": "piece"},
    "ice cream (1 scoop)":      {"cal": 140, "protein": 2.5, "carbs": 16,   "fat": 7.0, "sodium": 50,  "potassium": 130, "unit": "scoop"},
    "chocolate (1 bar)":        {"cal": 230, "protein": 3.0, "carbs": 25,   "fat": 13,  "sodium": 30,  "potassium": 170, "unit": "bar"},
    "cake (1 slice)":           {"cal": 350, "protein": 4.0, "carbs": 50,   "fat": 15,  "sodium": 300, "potassium": 80,  "unit": "slice"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_profile(conn=None):
    close = conn is None
    if close:
        conn = get_db()
    row = conn.execute("SELECT * FROM user_profile WHERE id=1").fetchone()
    if close:
        conn.close()
    return dict(row) if row else {}


def calc_bmr(profile):
    """Mifflin-St Jeor equation."""
    w, h, a = profile["weight_kg"], profile["height_cm"], profile["age"]
    if profile["gender"] == "male":
        return 10 * w + 6.25 * h - 5 * a + 5
    return 10 * w + 6.25 * h - 5 * a - 161


def calc_tdee(profile):
    """Total Daily Energy Expenditure."""
    bmr = calc_bmr(profile)
    factors = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55,
               "active": 1.725, "very_active": 1.9}
    return bmr * factors.get(profile["activity_level"], 1.55)


def calc_steps_needed(calories_consumed, profile):
    """
    Steps to walk to burn excess calories.
    Rule of thumb: ~0.04 cal per step per kg body weight (walking ~4 km/h).
    Steps/cal = 1 / (0.04 * weight_kg).
    """
    tdee = calc_tdee(profile)
    excess = max(0, calories_consumed - tdee)
    cal_per_step = 0.04 * profile["weight_kg"] / 1000 * 30  # ~0.04 cal/step for 70 kg
    # More accurate: about 0.03-0.06 cal/step depending on weight
    cal_per_step = 0.04 + (profile["weight_kg"] - 50) * 0.0005
    if cal_per_step <= 0:
        cal_per_step = 0.04
    steps_for_excess = int(excess / cal_per_step) if excess > 0 else 0
    # Minimum daily steps recommendation (kidney health: 5000-8000)
    base_steps = 7000 if profile.get("kidney_concern") else 5000
    return max(base_steps, base_steps + steps_for_excess), excess, tdee


def get_today_str():
    return date.today().isoformat()


def kidney_tips(daily_sodium, daily_potassium, daily_water_ml, profile):
    """Generate kidney health tips based on intake."""
    tips = []
    # Sodium: kidney patients should keep < 2000 mg/day
    if daily_sodium > 2000:
        tips.append(("warning", f"Sodium intake ({daily_sodium:.0f} mg) exceeds 2000 mg. "
                     "High sodium strains kidneys. Reduce salt, pickles, processed food."))
    elif daily_sodium > 1500:
        tips.append(("caution", f"Sodium at {daily_sodium:.0f} mg. Try to keep below 1500 mg "
                     "for optimal kidney health."))
    else:
        tips.append(("good", f"Sodium intake ({daily_sodium:.0f} mg) is in a healthy range."))

    # Potassium: moderate concern for kidney issues (< 2700 mg if CKD)
    if profile.get("kidney_concern") and daily_potassium > 2700:
        tips.append(("caution", f"Potassium ({daily_potassium:.0f} mg) is high. "
                     "If you have CKD, consult your doctor about potassium limits. "
                     "Reduce bananas, potatoes, coconut water."))
    elif daily_potassium < 2000:
        tips.append(("info", f"Potassium ({daily_potassium:.0f} mg) is low. "
                     "If kidneys are healthy, consider more fruits & veggies."))

    # Water
    goal = profile.get("water_goal_ml", 2500)
    if daily_water_ml < goal * 0.5:
        tips.append(("warning", f"Water intake ({daily_water_ml} ml) is very low! "
                     f"Target: {goal} ml. Dehydration increases kidney stone risk."))
    elif daily_water_ml < goal:
        remaining = goal - daily_water_ml
        tips.append(("caution", f"Water: {daily_water_ml} ml / {goal} ml. "
                     f"Drink {remaining} ml more today."))
    else:
        tips.append(("good", f"Water intake ({daily_water_ml} ml) meets your {goal} ml goal!"))

    # Protein (excess protein stresses kidneys)
    return tips


def get_daily_summary(conn, day_str):
    """Return summary dict for a given date."""
    # Water
    water_rows = conn.execute(
        "SELECT SUM(amount_ml) AS total FROM water_log WHERE date(timestamp)=?",
        (day_str,)).fetchone()
    total_water = water_rows["total"] or 0

    # Meals
    meals = conn.execute(
        "SELECT * FROM meal_log WHERE date(timestamp)=? ORDER BY timestamp",
        (day_str,)).fetchall()
    total_cal = sum(m["calories"] * m["quantity"] for m in meals)
    total_protein = sum(m["protein_g"] * m["quantity"] for m in meals)
    total_carbs = sum(m["carbs_g"] * m["quantity"] for m in meals)
    total_fat = sum(m["fat_g"] * m["quantity"] for m in meals)
    total_sodium = sum(m["sodium_mg"] * m["quantity"] for m in meals)
    total_potassium = sum(m["potassium_mg"] * m["quantity"] for m in meals)

    # Group meals by type
    grouped = {"breakfast": [], "lunch": [], "dinner": [], "snack": []}
    for m in meals:
        mt = m["meal_type"]
        if mt in grouped:
            grouped[mt].append(dict(m))

    # Steps
    step_row = conn.execute(
        "SELECT steps FROM step_log WHERE date=?", (day_str,)).fetchone()
    steps_done = step_row["steps"] if step_row else 0

    profile = get_profile(conn)
    rec_steps, excess_cal, tdee = calc_steps_needed(total_cal, profile)
    tips = kidney_tips(total_sodium, total_potassium, total_water, profile)

    # Water logs for timeline
    water_logs = conn.execute(
        "SELECT * FROM water_log WHERE date(timestamp)=? ORDER BY timestamp",
        (day_str,)).fetchall()

    return {
        "date": day_str,
        "total_water_ml": total_water,
        "water_logs": [dict(w) for w in water_logs],
        "meals": [dict(m) for m in meals],
        "grouped_meals": grouped,
        "total_cal": total_cal,
        "total_protein": total_protein,
        "total_carbs": total_carbs,
        "total_fat": total_fat,
        "total_sodium": total_sodium,
        "total_potassium": total_potassium,
        "steps_done": steps_done,
        "steps_recommended": rec_steps,
        "excess_calories": excess_cal,
        "tdee": tdee,
        "kidney_tips": tips,
        "profile": profile,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/water", methods=["POST"])
def log_water():
    amount = int(request.form.get("amount", 250))
    conn = get_db()
    conn.execute("INSERT INTO water_log (amount_ml) VALUES (?)", (amount,))
    conn.commit()
    conn.close()
    flash(f"Logged {amount} ml water!", "success")
    return redirect(url_for("index"))


@app.route("/water/delete/<int:wid>", methods=["POST"])
def delete_water(wid):
    conn = get_db()
    conn.execute("DELETE FROM water_log WHERE id=?", (wid,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/meal", methods=["POST"])
def log_meal():
    meal_type = request.form.get("meal_type", "snack")
    food_name = request.form.get("food_name", "").strip().lower()
    quantity = float(request.form.get("quantity", 1))
    custom_cal = request.form.get("custom_calories", "").strip()

    if food_name in FOOD_DB:
        info = FOOD_DB[food_name]
        cal = info["cal"]
        protein = info["protein"]
        carbs = info["carbs"]
        fat = info["fat"]
        sodium = info["sodium"]
        potassium = info["potassium"]
        unit = info["unit"]
    elif custom_cal:
        cal = float(custom_cal)
        protein = float(request.form.get("custom_protein", 0))
        carbs = float(request.form.get("custom_carbs", 0))
        fat = float(request.form.get("custom_fat", 0))
        sodium = float(request.form.get("custom_sodium", 0))
        potassium = float(request.form.get("custom_potassium", 0))
        unit = request.form.get("custom_unit", "serving")
    else:
        flash(f"Food '{food_name}' not in database. Please enter calories manually.", "error")
        return redirect(url_for("index"))

    conn = get_db()
    conn.execute("""INSERT INTO meal_log
        (meal_type, food_name, quantity, unit, calories, protein_g, carbs_g, fat_g, sodium_mg, potassium_mg)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (meal_type, food_name, quantity, unit, cal, protein, carbs, fat, sodium, potassium))
    conn.commit()
    conn.close()
    flash(f"Logged {quantity}x {food_name} ({cal*quantity:.0f} cal) for {meal_type}!", "success")
    return redirect(url_for("index"))


@app.route("/meal/delete/<int:mid>", methods=["POST"])
def delete_meal(mid):
    conn = get_db()
    conn.execute("DELETE FROM meal_log WHERE id=?", (mid,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/steps", methods=["POST"])
def log_steps():
    steps = int(request.form.get("steps", 0))
    today = get_today_str()
    conn = get_db()
    conn.execute("""INSERT INTO step_log (date, steps) VALUES (?, ?)
                    ON CONFLICT(date) DO UPDATE SET steps=?""",
                 (today, steps, steps))
    conn.commit()
    conn.close()
    flash(f"Updated steps to {steps}!", "success")
    return redirect(url_for("index"))


@app.route("/profile", methods=["GET", "POST"])
def profile():
    conn = get_db()
    if request.method == "POST":
        conn.execute("""UPDATE user_profile SET
            weight_kg=?, height_cm=?, age=?, gender=?, activity_level=?,
            kidney_concern=?, water_goal_ml=?, calorie_goal=?, water_reminder_min=?
            WHERE id=1""", (
            float(request.form["weight_kg"]),
            float(request.form["height_cm"]),
            int(request.form["age"]),
            request.form["gender"],
            request.form["activity_level"],
            1 if request.form.get("kidney_concern") else 0,
            int(request.form["water_goal_ml"]),
            int(request.form["calorie_goal"]),
            int(request.form.get("water_reminder_min", 60)),
        ))
        conn.commit()
        flash("Profile updated!", "success")
        conn.close()
        return redirect(url_for("profile"))
    p = get_profile(conn)
    tdee = calc_tdee(p)
    conn.close()
    return render_template("profile.html", p=p, tdee=tdee, active_page="more")


@app.route("/history")
def history():
    conn = get_db()
    # Last 30 days
    days = []
    for i in range(30):
        d = (date.today() - timedelta(days=i)).isoformat()
        s = get_daily_summary(conn, d)
        if s["total_cal"] > 0 or s["total_water_ml"] > 0 or s["steps_done"] > 0:
            days.append(s)
    conn.close()
    return render_template("history.html", days=days, active_page="more")


@app.route("/api/foods")
def api_foods():
    q = request.args.get("q", "").lower()
    results = {k: v for k, v in FOOD_DB.items() if q in k}
    return jsonify(results)


@app.route("/kidney")
def kidney_info():
    return render_template("kidney.html", active_page="more")


@app.route("/water")
def water_page():
    conn = get_db()
    summary = get_daily_summary(conn, get_today_str())
    conn.close()
    return render_template("water.html", s=summary, active_page="water")


@app.route("/meals")
def meals_page():
    conn = get_db()
    summary = get_daily_summary(conn, get_today_str())
    conn.close()
    return render_template("meals.html", s=summary, foods=sorted(FOOD_DB.keys()),
                           active_page="meals")


@app.route("/steps")
def steps_page():
    conn = get_db()
    summary = get_daily_summary(conn, get_today_str())
    conn.close()
    return render_template("steps.html", s=summary, active_page="home")


@app.route("/fasting")
def fasting_page():
    return render_template("fasting.html", active_page="home")


@app.route("/more")
def more_page():
    return render_template("more.html", active_page="more")


# ---------------------------------------------------------------------------
# Habits / Daily Routines
# ---------------------------------------------------------------------------

DEFAULT_HABITS = [
    ("Apply hair oil & scalp massage", "hair"),
    ("Apply rosemary spray to hair", "hair"),
    ("Eat eggs (evening)", "nutrition"),
    ("Eat dal / lentils", "nutrition"),
    ("Eat fruits (apple/amla/berries)", "nutrition"),
    ("Eat nuts (almonds/walnuts)", "nutrition"),
    ("Drink green tea", "health"),
    ("Walk after meals (15 min)", "fitness"),
    ("Morning exercise (30 min)", "fitness"),
    ("No sugar today", "sugar_cut"),
    ("Drink warm lemon water (morning)", "health"),
    ("Turmeric milk (evening)", "health"),
    ("Soaked methi seeds (morning)", "health"),
    ("Sleep by 10 PM", "health"),
]


@app.route("/habits")
def habits():
    conn = get_db()
    today = get_today_str()
    # Ensure all default habits exist for today
    for habit_name, _ in DEFAULT_HABITS:
        conn.execute("""INSERT OR IGNORE INTO habit_log (date, habit_name, done)
                        VALUES (?, ?, 0)""", (today, habit_name))
    conn.commit()
    rows = conn.execute(
        "SELECT * FROM habit_log WHERE date=? ORDER BY id", (today,)).fetchall()
    habits_list = [dict(r) for r in rows]

    # Calculate streak for each habit (consecutive days done)
    for h in habits_list:
        streak = 0
        for i in range(1, 365):
            d = (date.today() - timedelta(days=i)).isoformat()
            prev = conn.execute(
                "SELECT done FROM habit_log WHERE date=? AND habit_name=?",
                (d, h["habit_name"])).fetchone()
            if prev and prev["done"]:
                streak += 1
            else:
                break
        h["streak"] = streak

    done_count = sum(1 for h in habits_list if h["done"])
    total = len(habits_list)
    conn.close()
    return render_template("habits.html", habits=habits_list,
                           done_count=done_count, total=total, today=today,
                           categories={"hair": "Hair Care", "nutrition": "Nutrition",
                                       "health": "Health", "fitness": "Fitness",
                                       "sugar_cut": "Sugar Cut"}, active_page="habits")


@app.route("/habit/toggle/<int:hid>", methods=["POST"])
def toggle_habit(hid):
    conn = get_db()
    row = conn.execute("SELECT done FROM habit_log WHERE id=?", (hid,)).fetchone()
    if row:
        new_val = 0 if row["done"] else 1
        conn.execute("UPDATE habit_log SET done=? WHERE id=?", (new_val, hid))
        conn.commit()
    conn.close()
    return redirect(url_for("habits"))


@app.route("/habit/add", methods=["POST"])
def add_habit():
    name = request.form.get("habit_name", "").strip()
    if name:
        conn = get_db()
        conn.execute("""INSERT OR IGNORE INTO habit_log (date, habit_name, done)
                        VALUES (?, ?, 0)""", (get_today_str(), name))
        conn.commit()
        conn.close()
        flash(f"Added habit: {name}", "success")
    return redirect(url_for("habits"))


# ---------------------------------------------------------------------------
# Habits in daily summary (for index page)
# ---------------------------------------------------------------------------

@app.route("/onboarding", methods=["GET", "POST"])
def onboarding():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            conn = get_db()
            conn.execute("UPDATE user_profile SET name=? WHERE id=1", (name,))
            conn.commit()
            conn.close()
        return redirect(url_for("index"))
    return render_template("onboarding.html")


@app.route("/")
def index():
    conn = get_db()
    profile = conn.execute("SELECT * FROM user_profile WHERE id=1").fetchone()
    if not profile or not profile["name"]:
        conn.close()
        return redirect(url_for("onboarding"))
    today = get_today_str()
    summary = get_daily_summary(conn, today)

    # Get today's habits
    for habit_name, _ in DEFAULT_HABITS:
        conn.execute("""INSERT OR IGNORE INTO habit_log (date, habit_name, done)
                        VALUES (?, ?, 0)""", (today, habit_name))
    conn.commit()
    habits = conn.execute(
        "SELECT * FROM habit_log WHERE date=? ORDER BY id", (today,)).fetchall()
    summary["habits"] = [dict(h) for h in habits]
    summary["habits_done"] = sum(1 for h in habits if h["done"])
    summary["habits_total"] = len(habits)

    # Pantry low-stock alerts
    low_stock = conn.execute(
        "SELECT * FROM pantry WHERE quantity <= low_stock").fetchall()
    summary["low_stock"] = [dict(i) for i in low_stock]

    # Today's expenses
    today_exp = conn.execute(
        "SELECT COALESCE(SUM(amount),0) AS total FROM expense_log WHERE date(timestamp)=?",
        (today,)).fetchone()["total"]
    summary["today_expenses"] = today_exp

    # Pending todos
    pending_todos = conn.execute("SELECT COUNT(*) AS cnt FROM todo WHERE done=0").fetchone()["cnt"]
    summary["pending_todos"] = pending_todos

    conn.close()
    pro_word, gen_word = get_words_of_the_day()
    return render_template("index.html", s=summary, foods=sorted(FOOD_DB.keys()),
                           today=today, pro_word=pro_word, gen_word=gen_word,
                           active_page="home", username=profile["name"])


# ---------------------------------------------------------------------------
# Pantry / Fruit Inventory
# ---------------------------------------------------------------------------

@app.route("/pantry")
def pantry():
    conn = get_db()
    items = conn.execute("SELECT * FROM pantry ORDER BY category, item_name").fetchall()
    items = [dict(i) for i in items]
    low_stock = [i for i in items if i["quantity"] <= i["low_stock"]]
    conn.close()
    return render_template("pantry.html", items=items, low_stock=low_stock, active_page="more")


@app.route("/pantry/add", methods=["POST"])
def pantry_add():
    name = request.form.get("item_name", "").strip().lower()
    qty = int(request.form.get("quantity", 1))
    unit = request.form.get("unit", "pieces")
    category = request.form.get("category", "fruit")
    low = int(request.form.get("low_stock", 2))
    if name:
        conn = get_db()
        existing = conn.execute("SELECT id, quantity FROM pantry WHERE item_name=?", (name,)).fetchone()
        if existing:
            conn.execute("UPDATE pantry SET quantity=quantity+?, updated=datetime('now','localtime') WHERE id=?",
                         (qty, existing["id"]))
            flash(f"Added {qty} {name} (total: {existing['quantity']+qty})", "success")
        else:
            conn.execute("INSERT INTO pantry (item_name, quantity, unit, category, low_stock) VALUES (?,?,?,?,?)",
                         (name, qty, unit, category, low))
            flash(f"Added {qty} {unit} of {name}", "success")
        conn.commit()
        conn.close()
    return redirect(url_for("pantry"))


@app.route("/pantry/eat/<int:pid>", methods=["POST"])
def pantry_eat(pid):
    """Decrease quantity by 1 (ate one)."""
    conn = get_db()
    conn.execute("UPDATE pantry SET quantity=MAX(0, quantity-1), updated=datetime('now','localtime') WHERE id=?", (pid,))
    conn.commit()
    item = conn.execute("SELECT * FROM pantry WHERE id=?", (pid,)).fetchone()
    if item and item["quantity"] <= item["low_stock"]:
        flash(f"Low stock: {item['item_name']} — only {item['quantity']} left! Time to buy more.", "error")
    conn.close()
    return redirect(url_for("pantry"))


@app.route("/pantry/delete/<int:pid>", methods=["POST"])
def pantry_delete(pid):
    conn = get_db()
    conn.execute("DELETE FROM pantry WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return redirect(url_for("pantry"))


# ---------------------------------------------------------------------------
# Expense Tracker
# ---------------------------------------------------------------------------

@app.route("/expenses")
def expenses():
    conn = get_db()
    today = get_today_str()
    # Today's expenses
    today_rows = conn.execute(
        "SELECT * FROM expense_log WHERE date(timestamp)=? ORDER BY timestamp DESC",
        (today,)).fetchall()
    today_total = sum(r["amount"] for r in today_rows)

    # This week
    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    week_total = conn.execute(
        "SELECT COALESCE(SUM(amount),0) AS total FROM expense_log WHERE date(timestamp)>=?",
        (week_start,)).fetchone()["total"]

    # This month
    month_start = date.today().replace(day=1).isoformat()
    month_total = conn.execute(
        "SELECT COALESCE(SUM(amount),0) AS total FROM expense_log WHERE date(timestamp)>=?",
        (month_start,)).fetchone()["total"]

    # Last 7 days breakdown
    daily_totals = []
    for i in range(7):
        d = (date.today() - timedelta(days=i)).isoformat()
        t = conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS total FROM expense_log WHERE date(timestamp)=?",
            (d,)).fetchone()["total"]
        daily_totals.append({"date": d, "total": t})

    conn.close()
    return render_template("expenses.html", today_expenses=[dict(r) for r in today_rows],
                           today_total=today_total, week_total=week_total,
                           month_total=month_total, daily_totals=daily_totals, today=today,
                           active_page="more")


@app.route("/expense/add", methods=["POST"])
def expense_add():
    amount = request.form.get("amount", "").strip()
    note = request.form.get("note", "").strip()
    if amount:
        conn = get_db()
        conn.execute("INSERT INTO expense_log (amount, note) VALUES (?, ?)",
                     (float(amount), note))
        conn.commit()
        conn.close()
        flash(f"Logged expense: {amount}", "success")
    return redirect(url_for("expenses"))


@app.route("/expense/delete/<int:eid>", methods=["POST"])
def expense_delete(eid):
    conn = get_db()
    conn.execute("DELETE FROM expense_log WHERE id=?", (eid,))
    conn.commit()
    conn.close()
    return redirect(url_for("expenses"))


# ---------------------------------------------------------------------------
# To-Do List
# ---------------------------------------------------------------------------

@app.route("/todos")
def todos():
    conn = get_db()
    pending = conn.execute(
        "SELECT * FROM todo WHERE done=0 ORDER BY "
        "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, created").fetchall()
    completed = conn.execute(
        "SELECT * FROM todo WHERE done=1 ORDER BY created DESC LIMIT 20").fetchall()
    conn.close()
    return render_template("todos.html", pending=[dict(t) for t in pending],
                           completed=[dict(t) for t in completed],
                           today=get_today_str(), active_page="todos")


@app.route("/todo/add", methods=["POST"])
def todo_add():
    task = request.form.get("task", "").strip()
    priority = request.form.get("priority", "medium")
    due_date = request.form.get("due_date", "").strip() or None
    if task:
        conn = get_db()
        conn.execute("INSERT INTO todo (task, priority, due_date) VALUES (?,?,?)",
                     (task, priority, due_date))
        conn.commit()
        conn.close()
        flash(f"Added: {task}", "success")
    return redirect(url_for("todos"))


@app.route("/todo/toggle/<int:tid>", methods=["POST"])
def todo_toggle(tid):
    conn = get_db()
    row = conn.execute("SELECT done FROM todo WHERE id=?", (tid,)).fetchone()
    if row:
        conn.execute("UPDATE todo SET done=? WHERE id=?", (0 if row["done"] else 1, tid))
        conn.commit()
    conn.close()
    return redirect(url_for("todos"))


@app.route("/todo/delete/<int:tid>", methods=["POST"])
def todo_delete(tid):
    conn = get_db()
    conn.execute("DELETE FROM todo WHERE id=?", (tid,))
    conn.commit()
    conn.close()
    return redirect(url_for("todos"))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

init_db()

if __name__ == "__main__":
    print("\n  Health Tracker running at http://localhost:5000\n")
    print("  Features: Water | Meals | Calories | Steps | Habits | Fasting")
    print("  Health:   Kidney | Diabetes | Obesity | Hair Growth | Sugar Cut")
    print("  Mobile:   Open on phone browser using your PC's IP address\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
