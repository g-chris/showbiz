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
    
        # Check if a player with this name already exists (RECONNECTION)
        existing_sid = None
        for sid, player in game_state.players.items():
            if player['name'] == player_name:
                existing_sid = sid
                break
        
        if existing_sid:
            # RECONNECTION - transfer player data to new socket.id
            print(f'🔄 {player_name} reconnecting (old: {existing_sid[:8]}, new: {request.sid[:8]})')
            player_data = game_state.players[existing_sid]
            
            # Remove old socket.id entry
            del game_state.players[existing_sid]
            
            # Add player with NEW socket.id but PRESERVE their data
            game_state.players[request.sid] = player_data
            
            # Update naming progress if in Phase 0
            if game_state.phase.startswith('phase0') and existing_sid in game_state.naming_progress.get('submissions', {}):
                prog_data = game_state.naming_progress['submissions'][existing_sid]
                del game_state.naming_progress['submissions'][existing_sid]
                game_state.naming_progress['submissions'][request.sid] = prog_data
            
            print(f'  ✅ Restored: ${player_data["money"]}M, {player_data["score"]} pts, {len(player_data.get("roles", []))} roles, {len(player_data.get("films", []))} films')
        else:
            # NEW PLAYER
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

    @socketio.on('heartbeat')
    def handle_heartbeat(data):
        """Keep connection alive - mobile browsers kill idle connections"""
        pass  # Just acknowledge - the connection staying alive is the point
    
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
        
        # Reset bidding war state
        game_state.bidding_war = {
            'active': False,
            'card_index': None,
            'card_data': {},
            'participants': [],
            'bids': {},
            'conflicts_queue': []
        }
        
        cards = game_logic.generate_turn_cards(game_state)
        game_state.current_turn_cards = cards
        
        print(f"\n=== Turn {game_state.turn} ===")
        print(f"Generated {len(cards)} cards:")
        for i, card in enumerate(cards):
            print(f"  Card {i}: {card['name']} ({card['role']})")
    
    @socketio.on('select_card')
    def handle_select_card(data):
        # Prevent re-selection during same turn
        if request.sid in game_state.player_selections:
            emit('selection_error', {'message': 'You have already made your selection for this turn!'})
            return
        
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
        
        # Separate contested cards from uncontested ones
        contested_cards = {}    # {card_index: [sids]}
        uncontested_cards = {}  # {card_index: [sid]}
        
        for card_index, player_list in selection_groups.items():
            if len(player_list) > 1:
                contested_cards[card_index] = player_list
            else:
                uncontested_cards[card_index] = player_list
        
        # Check if we have any bidding wars
        if contested_cards:
            # Build the conflicts queue
            game_state.bidding_war['conflicts_queue'] = [
                (card_idx, players) for card_idx, players in contested_cards.items()
            ]
            
            print(f"\n💥 {len(contested_cards)} BIDDING WAR(S) DETECTED!")
            for card_idx, players in contested_cards.items():
                card = game_state.current_turn_cards[card_idx]
                player_names = [game_state.players[sid]['name'] for sid in players]
                print(f"  Card {card_idx} ({card['name']}): {', '.join(player_names)}")
            
            # Start processing the first conflict
            start_next_bidding_war(uncontested_cards)
        else:
            # No conflicts - award all cards directly
            print("\nNo conflicts, awarding cards...")
            for card_index, player_list in uncontested_cards.items():
                award_card_to_player(player_list[0], card_index)
            
            advance_turn()
    
    # ============================================================================
    # BIDDING WAR SYSTEM
    # ============================================================================
    
    def start_next_bidding_war(uncontested_cards):
        """
        Start the next bidding war from the conflicts queue.
        If queue is empty, award uncontested cards and advance turn.
        
        Args:
            uncontested_cards: Dict of {card_index: [sid]} for cards with single bidders
        """
        if not game_state.bidding_war['conflicts_queue']:
            # No more conflicts - award uncontested cards and move on
            print("\n✓ All bidding wars resolved!")
            for card_index, player_list in uncontested_cards.items():
                award_card_to_player(player_list[0], card_index)
            advance_turn()
            return
        
        # Get the next conflict from the queue
        card_index, participants = game_state.bidding_war['conflicts_queue'].pop(0)
        card_data = game_state.current_turn_cards[card_index].copy()
        
        # Set up the bidding war state
        game_state.bidding_war['active'] = True
        game_state.bidding_war['card_index'] = card_index
        game_state.bidding_war['card_data'] = card_data
        game_state.bidding_war['participants'] = participants
        game_state.bidding_war['bids'] = {}  # Reset bids
        
        # Determine which phase we're in for UI
        if game_state.phase == 'phase1_production':
            game_state.phase = 'phase1_bidding'
        elif game_state.phase == 'phase2_production':
            game_state.phase = 'phase2_bidding'
        
        player_names = [game_state.players[sid]['name'] for sid in participants]
        print(f"\n🎬 STARTING BIDDING WAR for {card_data['name']}")
        print(f"   Participants: {', '.join(player_names)}")
        
        # Store uncontested_cards for later use
        game_state.bidding_war['uncontested_cards'] = uncontested_cards
        
        broadcast_game_state()
    
    def resolve_bidding_war():
        """
        Determine the winner of a bidding war and award the card.
        Called after all participants have submitted bids.
        """
        bids = game_state.bidding_war['bids']
        participants = game_state.bidding_war['participants']
        card_data = game_state.bidding_war['card_data']
        card_index = game_state.bidding_war['card_index']
        
        print(f"\n🎬 RESOLVING BIDDING WAR for {card_data['name']}")
        
        # Show all bids
        for sid in participants:
            player_name = game_state.players[sid]['name']
            bid = bids.get(sid, 0)
            print(f"   {player_name}: ${bid}M")
        
        # Find the highest bid
        max_bid = max(bids.values())
        winners = [sid for sid, bid in bids.items() if bid == max_bid]
        
        if len(winners) > 1:
            # TIE - Nobody gets the card!
            print(f"\n💔 TIE at ${max_bid}M!")
            print(f"   {card_data['name']} is disgusted by studio politicking!")
            print(f"   Nobody gets the role, bids refunded.")
        else:
            # We have a winner!
            winner_sid = winners[0]
            winner_name = game_state.players[winner_sid]['name']
            print(f"\n🏆 WINNER: {winner_name} with bid of ${max_bid}M!")
            
            # Award the card with the extra bid
            award_card_to_player(winner_sid, card_index, extra_bid=max_bid)
        
        # Move to results phase
        if game_state.phase == 'phase1_bidding':
            game_state.phase = 'phase1_bidding_results'
        elif game_state.phase == 'phase2_bidding':
            game_state.phase = 'phase2_bidding_results'
        
        broadcast_game_state()
    
    def continue_after_bidding_results():
        """
        Called after showing bidding results.
        Either starts the next bidding war or continues the turn.
        """
        uncontested_cards = game_state.bidding_war.get('uncontested_cards', {})
        
        # Reset active bidding war
        game_state.bidding_war['active'] = False
        
        # Return to production phase
        if 'phase1' in game_state.phase:
            game_state.phase = 'phase1_production'
        elif 'phase2' in game_state.phase:
            game_state.phase = 'phase2_production'
        
        # Check if there are more conflicts
        start_next_bidding_war(uncontested_cards)
    
    # ============================================================================
    # BIDDING WAR - BID SUBMISSION
    # ============================================================================
    
    @socketio.on('submit_bid')
    def handle_submit_bid(data):
        """
        Handle a player's bid submission during a bidding war.
        Validates affordability and automatically resolves when all bids are in.
        """
        bid_amount = data.get('bid_amount', 0)
        
        # Validation checks
        if not game_state.bidding_war.get('active'):
            emit('bid_error', {'message': 'No active bidding war!'})
            return
        
        if request.sid not in game_state.bidding_war['participants']:
            emit('bid_error', {'message': 'You are not a participant in this bidding war!'})
            return
        
        if request.sid in game_state.bidding_war['bids']:
            emit('bid_error', {'message': 'You have already submitted your bid!'})
            return
        
        # Validate bid amount
        if bid_amount < 0:
            emit('bid_error', {'message': 'Bid cannot be negative!'})
            return
        
        # Check affordability: player must be able to pay base salary + bid
        player = game_state.players[request.sid]
        card_data = game_state.bidding_war['card_data']
        base_salary = card_data['salary']
        total_cost = base_salary + bid_amount
        
        if player['money'] < total_cost:
            emit('bid_error', {'message': f'Cannot afford! Total cost: ${total_cost}M, Your budget: ${player["money"]}M'})
            return
        
        # Bid is valid - record it
        game_state.bidding_war['bids'][request.sid] = bid_amount
        player_name = player['name']
        
        print(f"  💰 {player_name} bid ${bid_amount}M (Total: ${total_cost}M)")
        
        # Check if all participants have bid
        num_bids = len(game_state.bidding_war['bids'])
        num_participants = len(game_state.bidding_war['participants'])
        
        if num_bids == num_participants:
            print(f"\n✓ All {num_participants} participants have submitted bids!")
            resolve_bidding_war()
        else:
            print(f"  Waiting for {num_participants - num_bids} more bid(s)...")
            broadcast_game_state()
    
    def award_card_to_player(player_sid, card_index, extra_bid=0):
        """Give a card to a player and deduct cost"""
        card = game_state.current_turn_cards[card_index]
        player = game_state.players[player_sid]
        
        total_cost = card['salary'] + extra_bid
        
        print(f"  â†’ Awarding {card['name']} to {player['name']} for ${total_cost}M")
        print(f"     Money: ${player['money']}M â†’ ${player['money'] - total_cost}M")
        
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
            # Move to packaging phase and provide no-name talent
            if current_phase == 'phase1_production':
                game_state.phase = 'phase1_packaging'
                print("\n=== Winter production complete! Packaging phase ===\n")
            elif current_phase == 'phase2_production':
                game_state.phase = 'phase2_packaging'
                print("\n=== Summer production complete! Packaging phase ===\n")
            
            # Give each player access to no-name talent
            no_name_talent = game_logic.generate_no_name_talent()
            game_state.no_name_talent = no_name_talent
            
            for sid, player in game_state.players.items():
                role_count = len(player.get('roles', []))
                print(f"  {player['name']} has {role_count} roles + no-name talent available")
        
        broadcast_game_state()
    
    @socketio.on('continue_after_bidding')
    def handle_continue_after_bidding():
        """
        Socket handler for when players/host continue after viewing bidding results.
        Proceeds to next conflict or continues turn.
        """
        player = game_state.players[request.sid]
        player['bidding_results_ready'] = True
        
        player_name = player['name']
        ready_count = sum(1 for p in game_state.players.values() if p.get('bidding_results_ready', False))
        total_count = len(game_state.players)
        print(f"  {player_name} ready to continue ({ready_count}/{total_count})")
        
        # Check if all players ready
        if all(p.get('bidding_results_ready', False) for p in game_state.players.values()):
            # Reset ready flags
            for p in game_state.players.values():
                p['bidding_results_ready'] = False
            
            continue_after_bidding_results()
        else:
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
        
        if not title:
            emit('package_error', {'message': 'Film title is required!'})
            return
        
        # Extract roles (handle both regular and no-name talent)
        roles = []
        no_name_talent = game_state.no_name_talent
        
        for idx in role_indices:
            if idx < 0:
                # No-name talent (negative index)
                no_name_array = list(no_name_talent.values())
                role_idx = abs(idx) - 1
                if role_idx < len(no_name_array):
                    roles.append(no_name_array[role_idx].copy())
            else:
                # Regular purchased role
                if player.get('roles') and idx < len(player['roles']):
                    roles.append(player['roles'][idx])
        
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
        
        # Remove ONLY purchased roles (not no-name talent)
        purchased_indices = [idx for idx in role_indices if idx >= 0]
        for idx in sorted(purchased_indices, reverse=True):
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
        """Start Phase 2: Summer Production - wait for all players"""
        player = game_state.players[request.sid]
        player['spring_releases_ready'] = True
        
        player_name = player['name']
        ready_count = sum(1 for p in game_state.players.values() if p.get('spring_releases_ready', False))
        total_count = len(game_state.players)
        print(f"  {player_name} ready for Summer ({ready_count}/{total_count})")
        
        # Check if all players ready
        if all(p.get('spring_releases_ready', False) for p in game_state.players.values()):
            print("\n=== Starting Phase 2: Summer Production ===\n")
            game_state.phase = 'phase2_production'
            game_state.turn = 1
            
            # Reset ready flags
            for p in game_state.players.values():
                p['spring_ready'] = False
                p['holiday_ready'] = False
                p['spring_releases_ready'] = False
            
            start_new_turn()
            broadcast_game_state()
        else:
            broadcast_game_state()
    
    @socketio.on('start_awards')
    def handle_start_awards():
        """Start Award Season - wait for all players"""
        player = game_state.players[request.sid]
        player['holiday_releases_ready'] = True
        
        player_name = player['name']
        ready_count = sum(1 for p in game_state.players.values() if p.get('holiday_releases_ready', False))
        total_count = len(game_state.players)
        print(f"  {player_name} ready for Awards ({ready_count}/{total_count})")
        
        # Check if all players ready
        if all(p.get('holiday_releases_ready', False) for p in game_state.players.values()):
            print("\n=== Starting Award Season ===\n")
            
            # Reset ready flag
            for p in game_state.players.values():
                p['holiday_releases_ready'] = False
            
            # Set up awards (just Best Picture for now)
            awards_data = game_logic.setup_awards(game_state.players, active_categories=['best_picture'])
            
            if not awards_data:
                print("Not enough films for awards! Skipping to final results.")
                game_state.phase = 'game_complete'
                broadcast_game_state()
                return
            
            game_state.phase = 'awards_voting'
            game_state.awards = awards_data
            
            print(f"Award Season initialized with categories: {awards_data['active_categories']}")
            print(f"Nominees: {len(awards_data['categories']['best_picture']['nominees'])} films")
            
            broadcast_game_state()
        else:
            broadcast_game_state()
    
    @socketio.on('vote_for_nominee')
    def handle_vote(data):
        """Player votes for a nominee"""
        nominee_index = data['nominee_index']
        
        if not hasattr(game_state, 'awards') or not game_state.awards:
            return
        
        current_cat_key = game_state.awards['current_category']
        category = game_state.awards['categories'][current_cat_key]
        nominees = category['nominees']
        
        # Validate vote
        if nominee_index >= len(nominees):
            emit('vote_error', {'message': 'Invalid nominee selection!'})
            return
        
        # Check if voting for own film
        selected_film = nominees[nominee_index]
        voter_studio = game_state.players[request.sid]['name']
        
        if selected_film.get('studio') == voter_studio:
            emit('vote_error', {'message': 'Cannot vote for your own film!'})
            return
        
        # Record vote
        category['votes'][request.sid] = nominee_index
        player_name = game_state.players[request.sid]['name']
        print(f"{player_name} voted for nominee {nominee_index}: {selected_film['title']}")
        
        # Check if all players have voted
        if len(category['votes']) == len(game_state.players):
            calculate_award_winner(current_cat_key)
        
        broadcast_game_state()
    
    def calculate_award_winner(category_key):
        """Calculate the winner for a category"""
        category_data = game_state.awards['categories'][category_key]
        category = game_logic.AWARD_CATEGORIES[category_key]
        
        winner = category.calculate_winner(
            category_data['votes'], 
            category_data['nominees']
        )
        
        if winner:
            category_data['winner'] = winner
            
            # Award points to the studio
            winner_studio = winner.get('studio')
            for sid, player in game_state.players.items():
                if player['name'] == winner_studio:
                    player['score'] += category.points_value
                    print(f"\nðŸ† {category.name} WINNER: {winner['title']} ({winner_studio})")
                    print(f"   +{category.points_value} points awarded!")
                    break
        
        # Move to results phase
        game_state.phase = 'awards_results'
        broadcast_game_state()
    
    @socketio.on('continue_from_awards')
    def handle_continue_from_awards():
        """Handle continuing from awards results to game complete"""
        player = game_state.players[request.sid]
        player['awards_results_ready'] = True
        
        player_name = player['name']
        ready_count = sum(1 for p in game_state.players.values() if p.get('awards_results_ready', False))
        total_count = len(game_state.players)
        print(f"  {player_name} ready to end game ({ready_count}/{total_count})")
        
        # Check if all players ready
        if all(p.get('awards_results_ready', False) for p in game_state.players.values()):
            print("\n=== GAME COMPLETE ===\n")
            
            # Reset ready flags
            for p in game_state.players.values():
                p['awards_results_ready'] = False
            
            game_state.phase = 'game_complete'
            broadcast_game_state()
        else:
            broadcast_game_state()
    
    @socketio.on('disconnect')

    def handle_disconnect():
        if request.sid in game_state.players:
            player_name = game_state.players[request.sid]['name']
            print(f'📱 {player_name} disconnected (socket: {request.sid[:8]})')
            print(f'  💾 Player data preserved for reconnection')
        
        # DON'T delete the player - keep their data for reconnection
        # When they reconnect, join_game will update their socket.id
        # This prevents losing progress when mobile phones go to sleep