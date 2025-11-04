"""
Game logic and state management for Hollywood Moguls
"""
import random

# Constants
GENRES = ['Action', 'Comedy', 'Drama', 'Horror', 'Romance', 'Sci-Fi', 'Thriller', 'Western']
AUDIENCES = ['Kids', 'Teens', 'Adults', 'Families', 'Art House']

DEFAULT_NAMES = {
    'screenwriter': [
        'Bobby Goldman', 'Nora Ephron Jr.', 'Paddy Chayefsky II', 'Alvin Sargent',
        'Frank Pierson', 'Ernest Lehman III', 'Ruth Prawer', 'Horton Foote Jr.',
        'Robert Towne II', 'Lorenzo Semple'
    ],
    'director': [
        'Stevie Screensberg', 'Frankie Coppola', 'Marty Scorcese', 'Bobby Altman',
        'Mike Nichols Jr.', 'Billy Wilder II', 'Stanley Kubrick III', 'Arthur Penn',
        'Sydney Pollack Jr.', 'Hal Ashby'
    ],
    'star': [
        'Dusty Hoffman', 'Bobby DeNiro', 'Jackie Nicholson', 'Meryl Streepleton',
        'Robbie Redford', 'Warren Beatty Jr.', 'Faye Dunaway II', 'Al Pacino III',
        'Diane Keaton', 'Gene Hackman Jr.'
    ]
}

class GameState:
    """Manages the game state"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset game to initial state"""
        self.phase = 'lobby'
        self.players = {}
        self.talent_pool = []
        self.naming_progress = {'submissions': {}}
        self.year = 0
        self.turn = 0
        self.current_turn_cards = []
        self.player_selections = {}
        self.bidding_war = None
    
    def to_dict(self):
        """Convert state to dictionary for broadcasting"""
        return {
            'phase': self.phase,
            'players': self.players,
            'talent_pool': self.talent_pool,
            'naming_progress': self.naming_progress,
            'year': self.year,
            'turn': self.turn,
            'current_turn_cards': self.current_turn_cards,
            'player_selections': self.player_selections,
            'bidding_war': self.bidding_war
        }

# Utility functions

def get_heat_bucket(heat):
    """Convert heat value to bucket"""
    if heat < 64:
        return "Unknown"
    elif heat < 128:
        return "Building"
    elif heat < 192:
        return "Buzzing"
    else:
        return "Superstar"

def get_prestige_bucket(prestige):
    """Convert prestige value to bucket"""
    if prestige < 34:
        return "Mainstream"
    elif prestige < 67:
        return "Artist"
    else:
        return "Auteur"

def generate_talent_stats(role_type, name, is_producer=False):
    """Generate Heat, Prestige, and Salary for a talent"""
    heat = random.randint(1, 255)
    prestige = random.randint(1, 100)
    
    if is_producer:
        if random.random() < 0.7:  # 70% basic producers
            heat = 0
            prestige = 0
            salary = random.randint(1, 3)
        else:  # 30% premium producers
            if random.random() < 0.5:
                heat = random.randint(50, 100)
                prestige = 0
                salary = random.randint(8, 15)
            else:
                heat = 0
                prestige = random.randint(50, 80)
                salary = random.randint(8, 15)
        
        genre = random.choice(GENRES)
        return {
            'name': name,
            'role': 'producer',
            'heat': heat,
            'heat_bucket': get_heat_bucket(heat) if heat > 0 else 'None',
            'prestige': prestige,
            'prestige_bucket': get_prestige_bucket(prestige) if prestige > 0 else 'None',
            'salary': salary,
            'genre': genre
        }
    
    # Calculate salary based on role type
    if role_type == 'star':
        salary = (heat // 10) + random.randint(1, 5)
    elif role_type == 'director':
        salary = (heat // 10) + random.randint(1, 5)
        prestige = max(1, 100 - (heat // 3) + random.randint(-10, 10))
    elif role_type == 'screenwriter':
        salary = (prestige // 10) + random.randint(1, 3)
    
    result = {
        'name': name,
        'role': role_type,
        'heat': heat,
        'heat_bucket': get_heat_bucket(heat),
        'prestige': prestige,
        'prestige_bucket': get_prestige_bucket(prestige),
        'salary': salary
    }
    
    if role_type == 'screenwriter':
        result['audience'] = random.choice(AUDIENCES)
    
    return result

def handle_duplicate_names(talent_list):
    """Append Jr., II, III, etc. to duplicate names"""
    name_counts = {}
    for talent in talent_list:
        base_name = talent['name']
        if base_name in name_counts:
            name_counts[base_name] += 1
            if name_counts[base_name] == 2:
                talent['name'] = f"{base_name} Jr."
            else:
                suffixes = ['II', 'III', 'IV', 'V']
                talent['name'] = f"{base_name} {suffixes[name_counts[base_name]-2]}"
        else:
            name_counts[base_name] = 1

def generate_turn_cards(game_state):
    """Generate cards for the current turn"""
    num_players = len(game_state.players)
    num_cards = num_players + 1
    
    cards = []
    
    # Add existing talent
    available_talent = [t.copy() for t in game_state.talent_pool]
    if len(available_talent) >= num_cards - 1:
        cards = random.sample(available_talent, num_cards - 1)
    else:
        cards = available_talent.copy()
    
    # Add a producer
    producer_names = ['Avi Goldstein', 'Rachel Chen', 'Marcus Thompson', 'Sofia Rodriguez',
                      'David Kim', 'Emma Watson', 'James O\'Brien', 'Priya Patel']
    producer = generate_talent_stats('producer', random.choice(producer_names), is_producer=True)
    cards.append(producer)
    
    random.shuffle(cards)
    return cards

def validate_film_package(roles):
    """Check if a set of roles forms a valid film"""
    role_types = [r['role'] for r in roles]
    return ('producer' in role_types and 
            'screenwriter' in role_types and
            'director' in role_types and 
            'star' in role_types)

def calculate_film_stats(roles):
    """Calculate Heat and Prestige for a film"""
    total_heat = sum(r['heat'] for r in roles)
    avg_prestige = sum(r['prestige'] for r in roles) // len(roles)
    genre = next((r['genre'] for r in roles if r['role'] == 'producer'), 'Unknown')
    audience = next((r['audience'] for r in roles if r['role'] == 'screenwriter'), 'Unknown')
    
    return {
        'heat': total_heat,
        'prestige': avg_prestige,
        'genre': genre,
        'audience': audience
    }