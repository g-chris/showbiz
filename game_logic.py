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
        self.bidding_war = {
            'active': False,
            'card_index': None,           # Which card is being fought over
            'card_data': {},              # Copy of the card itself
            'participants': [],           # List of player SIDs competing
            'bids': {},                   # {sid: bid_amount}
            'conflicts_queue': []         # List of (card_index, [sids]) to resolve
        }
        self.no_name_talent = {}
    
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
            'bidding_war': self.bidding_war,
            'no_name_talent': self.no_name_talent
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
    num_cards = num_players + 2  # Changed from +1 to +2 for more options
    
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

def calculate_box_office(film):
    """
    Calculate box office revenue for a film.
    PLACEHOLDER: Heat * random multiplier (0.1 to 2.5)
    This is where we'll update the formula when we refine the game balance.
    """
    import random
    multiplier = random.uniform(0.1, 2.5)
    box_office = int(film['heat'] * multiplier)
    
    return {
        'box_office': box_office,
        'multiplier': round(multiplier, 2)
    }

def process_film_releases(players, season_name='Spring'):
    """
    Process all film releases for a season and calculate box office.
    This is the single source of truth for release calculations.
    
    Args:
        players: Dictionary of player objects
        season_name: String name of the season (for logging)
    
    Returns:
        List of all films with box office results
    """
    import random
    
    print(f"\n=== {season_name.upper()} RELEASES ===\n")
    
    all_films = []
    
    for sid, player in players.items():
        if player.get('films'):
            for film in player['films']:
                # Only calculate box office if not already calculated
                if 'box_office' not in film:
                    # Calculate box office using our single formula
                    results = calculate_box_office(film)
                    film.update(results)
                    
                    # Add earnings to player
                    player['money'] += film['box_office']
                    player['score'] += film['box_office']
                    
                    print(f"{player['name']}: '{film['title']}'")
                    print(f"  Heat: {film['heat']} x {film['multiplier']:.2f} = ${film['box_office']}M")
                    print(f"  New balance: ${player['money']}M")
                    
                all_films.append({
                    **film,
                    'studio': player['name'],
                    'season': season_name
                })
        
        # IMPORTANT: Clear any leftover roles after releases
        # Players should never carry roles between production phases
        player['roles'] = []
        print(f"  {player['name']}'s unused roles cleared")
    
    print(f"\n=== {season_name.upper()} BOX OFFICE COMPLETE ===\n")
    return all_films

# ============================================================================
# AWARD SEASON SYSTEM
# ============================================================================

class AwardCategory:
    """Represents an award category with its rules"""
    
    def __init__(self, name, nominees_count=5, scoring_attribute='prestige', 
                 can_vote_for_own=False, points_value=50):
        self.name = name
        self.nominees_count = nominees_count
        self.scoring_attribute = scoring_attribute
        self.can_vote_for_own = can_vote_for_own
        self.points_value = points_value
    
    def get_nominees(self, all_films):
        """
        Get the top nominees for this category.
        Returns list of films sorted by the scoring attribute.
        """
        # Sort films by the scoring attribute (e.g., prestige)
        sorted_films = sorted(
            all_films, 
            key=lambda f: f.get(self.scoring_attribute, 0), 
            reverse=True
        )
        
        # Return top N, or all films if there aren't enough
        return sorted_films[:min(self.nominees_count, len(sorted_films))]
    
    def calculate_winner(self, votes, nominees):
        """
        Calculate the winner based on votes.
        
        Args:
            votes: Dict of {player_sid: film_index}
            nominees: List of nominated films
        
        Returns:
            Winning film or None if no votes
        """
        if not votes:
            return None
        
        # Count votes for each film
        vote_counts = {}
        for film_index in votes.values():
            vote_counts[film_index] = vote_counts.get(film_index, 0) + 1
        
        # Find max votes
        max_votes = max(vote_counts.values())
        
        # Get all films with max votes (for tie-breaking)
        tied_films = [idx for idx, count in vote_counts.items() if count == max_votes]
        
        if len(tied_films) == 1:
            return nominees[tied_films[0]]
        else:
            # Tie-breaker: highest prestige
            winner_idx = max(
                tied_films, 
                key=lambda idx: nominees[idx].get(self.scoring_attribute, 0)
            )
            return nominees[winner_idx]

# Define available award categories
AWARD_CATEGORIES = {
    'best_picture': AwardCategory(
        name='Best Picture',
        nominees_count=5,
        scoring_attribute='prestige',
        can_vote_for_own=False,
        points_value=50
    ),
    'best_actor': AwardCategory(
        name='Best Actor',
        nominees_count=5,
        scoring_attribute='prestige',  # Could be customized later
        can_vote_for_own=False,
        points_value=30
    ),
    'best_screenplay': AwardCategory(
        name='Best Screenplay',
        nominees_count=5,
        scoring_attribute='prestige',
        can_vote_for_own=False,
        points_value=30
    )
}

def get_all_films_from_players(players):
    """Collect all films from all players"""
    all_films = []
    for sid, player in players.items():
        if player.get('films'):
            for film in player['films']:
                all_films.append({
                    **film,
                    'studio': player['name'],
                    'player_sid': sid
                })
    return all_films

def generate_no_name_talent():
    """
    Generate "No Name" talent that players can use to fill gaps in their films.
    These are budget indie talent with low heat but decent prestige.
    Returns a dict with one of each role type.
    """
    import random
    
    no_name_roles = {
        'producer': {
            'name': 'No Name Producer',
            'role': 'producer',
            'heat': 0,
            'heat_bucket': 'Unknown',
            'prestige': 50,
            'prestige_bucket': 'Artist',
            'salary': 1,
            'genre': random.choice(GENRES)
        },
        'screenwriter': {
            'name': 'No Name Screenwriter',
            'role': 'screenwriter',
            'heat': 0,
            'heat_bucket': 'Unknown',
            'prestige': 50,
            'prestige_bucket': 'Artist',
            'salary': 1,
            'audience': random.choice(AUDIENCES)
        },
        'director': {
            'name': 'No Name Director',
            'role': 'director',
            'heat': 0,
            'heat_bucket': 'Unknown',
            'prestige': 50,
            'prestige_bucket': 'Artist',
            'salary': 1
        },
        'star': {
            'name': 'No Name Star',
            'role': 'star',
            'heat': 0,
            'heat_bucket': 'Unknown',
            'prestige': 50,
            'prestige_bucket': 'Artist',
            'salary': 1
        }
    }
    
    return no_name_roles

def setup_awards(players, active_categories=['best_picture']):
    """
    Set up award season with specified categories.
    
    Args:
        players: Dictionary of player objects
        active_categories: List of category keys to activate this season
    
    Returns:
        Dictionary with award setup info, or None if not enough films
    """
    all_films = get_all_films_from_players(players)
    
    # Need at least 2 films for awards to make sense
    if len(all_films) < 2:
        return None
    
    awards_data = {
        'categories': {},
        'current_category': None,
        'current_category_index': 0,
        'active_categories': active_categories
    }
    
    # Set up each active category
    for cat_key in active_categories:
        category = AWARD_CATEGORIES[cat_key]
        nominees = category.get_nominees(all_films)
        
        awards_data['categories'][cat_key] = {
            'name': category.name,
            'nominees': nominees,
            'votes': {},  # {player_sid: nominee_index}
            'winner': None,
            'points_value': category.points_value
        }
    
    # Start with first category
    if active_categories:
        awards_data['current_category'] = active_categories[0]
    
    return awards_data