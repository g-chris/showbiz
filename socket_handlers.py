"""
Socket.IO event handlers for Hollywood Moguls
"""
from flask import request
from flask_socketio import emit
import game_logic

def register_handlers(socketio, game_state):
    """Register all socket event handlers"""
    
    def broadcast_game_state():
        """Broadcast current game state to all clients"""
        socketio.emit('game_update', game_state.to_dict())
    
    @socketio.on('connect')
    def handle_connect():
        print(f'Client connected: {request.sid}')
    
    @socketio.on('join_game')
    def handle_join(data):
        player_name = data['name']
        game_state.players[request.sid] = {
            'name': player_name,
            'money': 100,
            'score': 0,
            'roles': [],
            'films': []
        }
        print(f'{player_name} joined the game')
        emit('joined')
        broadcast_game_state()
    
    @socketio.on('start_phase0')
    def handle_start_phase0():
        print("Starting Phase 0: Talent Naming")
        game_state.phase = 'phase0_naming'
        game_state.naming_progress = {
            'submissions': {
                sid: {'screenwriter': [], 'director': [], 'star': [], 'complete': False}
                for sid in game_state.players.keys()
            }
        }
        broadcast_game_state()
    
    @socketio.on('submit_talent_name')
    def handle_talent_name(data):
        name = data['name']
        prog = game_state.naming_progress
        
        if request.sid not in prog['submissions']:
            return
        
        player_prog = prog['submissions'][request.sid]
        
        if player_prog['complete']:
            return
        
        # Determine which role type to add to
        if len(player_prog['screenwriter']) < 3:
            role_type = 'screenwriter'
            player_prog['screenwriter'].append(name)
        elif len(player_prog['director']) < 3:
            role_type = 'director'
            player_prog['director'].append(name)
        elif len(player_prog['star']) < 5:
            role_type = 'star'
            player_prog['star'].append(name)
        else:
            return
        
        print(f"{game_state.players[request.sid]['name']} submitted {role_type}: {name}")
        
        # Generate stats
        talent = game_logic.generate_talent_stats(role_type, name)
        game_state.talent_pool.append(talent)
        
        # Check if this player is done
        if (len(player_prog['screenwriter']) == 3 and
            len(player_prog['director']) == 3 and
            len(player_prog['star']) == 5):
            player_prog['complete'] = True
            print(f"{game_state.players[request.sid]['name']} completed Phase 0!")
            
            # Check if ALL players are done
            if all(p['complete'] for p in prog['submissions'].values()):
                game_logic.handle_duplicate_names(game_state.talent_pool)
                game_state.phase = 'phase0_complete'
                print("Phase 0 complete! All talent generated.")
        
        broadcast_game_state()
    
    @socketio.on('start_phase1')
    def handle_start_phase1():
        print("Starting Phase 1: Winter Production")
        game_state.phase = 'phase1_production'
        game_state.year = 1
        game_state.turn = 1
        start_new_turn()
        broadcast_game_state()
    
    def start_new_turn():
        """Generate cards for the current turn"""
        game_state.player_selections = {}
        game_state.bidding_war = None
        
        cards = game_logic.generate_turn_cards(game_state)
        game_state.current_turn_cards = cards
        
        print(f"\n=== Turn {game_state.turn} ===")
        print(f"Generated {len(cards)} cards:")
        for i, card in enumerate(cards):
            print(f"  Card {i}: {card['name']} ({card['role']})")
    
    @socketio.on('select_card')
    def handle_select_card(data):
        selection = data['index']
        player = game_state.players[request.sid]
        player_name = player['name']
        
        # Check affordability
        if selection != 'pass':
            if selection >= len(game_state.current_turn_cards):
                emit('selection_error', {'message': 'Invalid card selection!'})
                return
            
            card = game_state.current_turn_cards[selection]
            print(f"{player_name} selecting card {selection}: {card['name']} (${card['salary']}M)")
            
            if player['money'] < card['salary']:
                print(f"  -> BLOCKED: Cannot afford!")
                emit('selection_error', {'message': f"Can't afford {card['name']}!"})
                return
        
        game_state.player_selections[request.sid] = selection
        
        if selection == 'pass':
            print(f"{player_name} passed")
        else:
            print(f"{player_name} selected {card['name']}")
        
        # Check if all players have selected
        if len(game_state.player_selections) == len(game_state.players):
            resolve_selections()
        else:
            broadcast_game_state()
    
    def resolve_selections():
        """Check for bidding wars and award cards"""
        selections = game_state.player_selections
        
        print(f"\n=== Resolving Turn {game_state.turn} ===")
        for sid, sel in selections.items():
            player_name = game_state.players[sid]['name']
            if sel == 'pass':
                print(f"  {player_name}: PASS")
            else:
                card = game_state.current_turn_cards[sel]
                print(f"  {player_name}: {card['name']}")
        
        # Group players by selection
        selection_groups = {}
        for sid, selection in selections.items():
            if selection != 'pass':
                if selection not in selection_groups:
                    selection_groups[selection] = []
                selection_groups[selection].append(sid)
        
        # Check for bidding wars
        bidding_wars = {idx: players for idx, players in selection_groups.items() if len(players) > 1}
        
        if bidding_wars:
            # TODO: Implement bidding war
            card_index = list(bidding_wars.keys())[0]
            print(f"\n💥 BIDDING WAR for card {card_index} - NOT YET IMPLEMENTED")
            # For now, nobody gets it
            advance_turn()
        else:
            # Award cards directly
            print("\n✓ No conflicts, awarding cards...")
            for card_index, player_list in selection_groups.items():
                if len(player_list) == 1:
                    award_card_to_player(player_list[0], card_index)
            
            advance_turn()
    
    def award_card_to_player(player_sid, card_index, extra_bid=0):
        """Give a card to a player and deduct cost"""
        card = game_state.current_turn_cards[card_index]
        player = game_state.players[player_sid]
        
        total_cost = card['salary'] + extra_bid
        
        print(f"  → Awarding {card['name']} to {player['name']} for ${total_cost}M")
        print(f"     Money: ${player['money']}M → ${player['money'] - total_cost}M")
        
        player['money'] -= total_cost
        player['roles'].append(card.copy())
    
    def advance_turn():
        """Move to next turn or phase"""
        game_state.turn += 1
        
        # Determine which phase we're in
        current_phase = game_state.phase
        
        if game_state.turn <= 5:
            # Continue current production phase
            if current_phase == 'phase1_production':
                game_state.phase = 'phase1_production'
                print(f"\n=== Starting Turn {game_state.turn} ===\n")
            elif current_phase == 'phase2_production':
                game_state.phase = 'phase2_production'
                print(f"\n=== Starting Turn {game_state.turn} ===\n")
            start_new_turn()
        else:
            # Move to packaging phase
            if current_phase == 'phase1_production':
                game_state.phase = 'phase1_packaging'
                print("\n=== Winter production complete! Packaging phase ===\n")
            elif current_phase == 'phase2_production':
                game_state.phase = 'phase2_packaging'
                print("\n=== Summer production complete! Packaging phase ===\n")
            
            for sid, player in game_state.players.items():
                role_count = len(player.get('roles', []))
                print(f"  {player['name']} has {role_count} roles")
        
        broadcast_game_state()
    
    @socketio.on('request_update')
    def handle_request_update():
        broadcast_game_state()
    
    @socketio.on('greenlight_film')
    def handle_greenlight_film(data):
        player = game_state.players[request.sid]
        role_indices = data['roleIndices']
        title = data['title'].strip()
        teaser = data.get('teaser', '').strip()
        
        if not player.get('roles'):
            return
        
        if not title:
            emit('package_error', {'message': 'Film title is required!'})
            return
        
        # Extract roles
        roles = [player['roles'][i] for i in role_indices if i < len(player['roles'])]
        
        # Validate package
        if not game_logic.validate_film_package(roles):
            emit('package_error', {'message': 'Invalid package! Need Producer, Screenwriter, Director, and Star'})
            return
        
        # Calculate film stats
        stats = game_logic.calculate_film_stats(roles)
        
        film = {
            'title': title,
            'teaser': teaser if teaser else f"A {stats['genre']} film for {stats['audience']}",
            'roles': roles,
            **stats
        }
        
        if 'films' not in player:
            player['films'] = []
        player['films'].append(film)
        
        # Remove roles
        for idx in sorted(role_indices, reverse=True):
            if idx < len(player['roles']):
                player['roles'].pop(idx)
        
        print(f"{player['name']} greenlit '{title}' (Heat: {stats['heat']}, Prestige: {stats['prestige']})")
        broadcast_game_state()
    
    @socketio.on('finish_packaging')
    def handle_finish_packaging():
        player = game_state.players[request.sid]
        
        # Refund remaining roles
        if player.get('roles'):
            refund = sum(r['salary'] for r in player['roles']) // 2
            player['money'] += refund
            print(f"{player['name']} released {len(player['roles'])} roles for ${refund}M")
            player['roles'] = []
        
        # Determine which phase we're in
        if game_state.phase == 'phase1_packaging':
            player['spring_ready'] = True
            # Check if all players ready
            if all(p.get('spring_ready', False) for p in game_state.players.values()):
                start_releases('Spring', 'phase1_releases')
        elif game_state.phase == 'phase2_packaging':
            player['holiday_ready'] = True
            # Check if all players ready
            if all(p.get('holiday_ready', False) for p in game_state.players.values()):
                start_releases('Holiday', 'phase2_releases')
        
        broadcast_game_state()
    
    def start_releases(season_name, phase_name):
        """Generic function to handle any release phase"""
        game_state.phase = phase_name
        game_logic.process_film_releases(game_state.players, season_name)
        broadcast_game_state()
    
    @socketio.on('continue_to_summer')
    def handle_continue_to_summer():
        """Start Phase 2: Summer Production"""
        print("\n=== Starting Phase 2: Summer Production ===\n")
        game_state.phase = 'phase2_production'
        game_state.turn = 1
        
        # Reset ready flags
        for player in game_state.players.values():
            player['spring_ready'] = False
            player['holiday_ready'] = False
        
        start_new_turn()
        broadcast_game_state()
    
    @socketio.on('disconnect')
    def handle_disconnect():
        if request.sid in game_state.players:
            player_name = game_state.players[request.sid]['name']
            del game_state.players[request.sid]
            print(f'{player_name} left the game')
            broadcast_game_state()