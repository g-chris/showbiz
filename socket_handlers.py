"""
Socket.IO event handlers for Hollywood Moguls
"""
from flask import request
from flask_socketio import emit
import functools
import game_logic
import threading

def register_handlers(socketio, game_state):
    """Register all socket event handlers"""

    # Socket handlers and timer threads all mutate game_state. Serialize them so a
    # timer firing at the same moment as a player's click can't resolve a phase twice.
    state_lock = threading.RLock()

    def locked(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            with state_lock:
                return fn(*args, **kwargs)
        return wrapper

    # Reconnect tokens are kept out of game_state so they're never broadcast
    player_tokens = {}       # {player_name: token}
    connected_sids = set()

    def broadcast_game_state():
        """Broadcast current game state to all clients"""
        socketio.emit('game_update', game_state.to_dict())

    def current_player():
        """Player record for the calling socket, or None (host / stale socket)"""
        return game_state.players.get(request.sid)

    @socketio.on('connect')
    @locked
    def handle_connect():
        connected_sids.add(request.sid)
        print(f'Client connected: {request.sid}')
        # Bring a freshly (re)loaded page up to date immediately
        emit('game_update', game_state.to_dict())

    def remap_sid(old_sid, new_sid):
        """Point every per-player reference in game_state at a player's new socket id"""
        def move_key(d):
            if isinstance(d, dict) and old_sid in d:
                d[new_sid] = d.pop(old_sid)

        game_state.players[new_sid] = game_state.players.pop(old_sid)
        move_key(game_state.naming_progress.get('submissions'))
        move_key(game_state.player_selections)

        bw = game_state.bidding_war
        bw['participants'] = [new_sid if s == old_sid else s for s in bw.get('participants', [])]
        move_key(bw.get('bids'))
        bw.get('disconnect_times', {}).pop(old_sid, None)
        bw['conflicts_queue'] = [
            (card_idx, [new_sid if s == old_sid else s for s in sids])
            for card_idx, sids in bw.get('conflicts_queue', [])
        ]
        for sids in bw.get('uncontested_cards', {}).values():
            for i, s in enumerate(sids):
                if s == old_sid:
                    sids[i] = new_sid

        if game_state.awards:
            for category in game_state.awards['categories'].values():
                move_key(category['votes'])
                for film in category['nominees']:
                    if film.get('player_sid') == old_sid:
                        film['player_sid'] = new_sid

    @socketio.on('join_game')
    @locked
    def handle_join(data):
        player_name = str(data.get('name', '')).strip()[:40]
        token = data.get('token')
        if not player_name:
            emit('join_error', {'message': 'Please enter a studio name.'})
            return

        # Check if a player with this name already exists (RECONNECTION)
        existing_sid = None
        for sid, player in game_state.players.items():
            if player['name'] == player_name:
                existing_sid = sid
                break

        if existing_sid == request.sid:
            pass  # Duplicate join from the same socket - nothing to transfer
        elif existing_sid:
            # Someone else is actively using this name from a different browser
            known_token = player_tokens.get(player_name)
            if existing_sid in connected_sids and known_token and token != known_token:
                emit('join_error', {'message': f'"{player_name}" is already taken. Pick another studio name.'})
                return

            # RECONNECTION - transfer player data to new socket.id
            print(f'🔄 {player_name} reconnecting (old: {existing_sid[:8]}, new: {request.sid[:8]})')
            remap_sid(existing_sid, request.sid)
            player_data = game_state.players[request.sid]
            print(f'  ✅ Restored: ${player_data["money"]}M, {player_data["score"]} pts, {len(player_data.get("roles", []))} roles, {len(player_data.get("films", []))} films')
        elif game_state.phase != 'lobby':
            emit('join_error', {'message': 'This game is already in progress. Wait for the next one!'})
            return
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

        if token:
            player_tokens[player_name] = token
        game_state.players[request.sid]['connected'] = True
        emit('joined', {'name': player_name})
        broadcast_game_state()

    @socketio.on('heartbeat')
    def handle_heartbeat(data=None):
        """Keep connection alive - mobile browsers kill idle connections"""
        pass  # Just acknowledge - the connection staying alive is the point

    @socketio.on('start_phase0')
    @locked
    def handle_start_phase0():
        if game_state.phase != 'lobby' or not game_state.players:
            print(f"⚠️  Ignoring start_phase0 in phase {game_state.phase} with {len(game_state.players)} players")
            return
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
    @locked
    def handle_talent_name(data):
        if game_state.phase != 'phase0_naming':
            return
        name = str(data.get('name', '')).strip()[:40]
        if not name:
            return
        if add_talent_name(request.sid, name):
            broadcast_game_state()

    def add_talent_name(sid, name):
        """Add one talent name for a player. Returns True if it was accepted."""
        prog = game_state.naming_progress

        if sid not in prog['submissions']:
            return False

        player_prog = prog['submissions'][sid]

        if player_prog['complete']:
            return False

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
            return False

        print(f"{game_state.players[sid]['name']} submitted {role_type}: {name}")

        # Generate stats
        talent = game_logic.generate_talent_stats(role_type, name)
        game_state.talent_pool.append(talent)

        # Check if this player is done
        if (len(player_prog['screenwriter']) == 3 and
            len(player_prog['director']) == 3 and
            len(player_prog['star']) == 5):
            player_prog['complete'] = True
            print(f"{game_state.players[sid]['name']} completed Phase 0!")

            # Check if ALL players are done
            if all(p['complete'] for p in prog['submissions'].values()):
                game_logic.handle_duplicate_names(game_state.talent_pool)
                game_state.phase = 'phase0_complete'
                print("Phase 0 complete! All talent generated.")

                # AUTO-PROGRESS: Start Phase 1 after 3 seconds
                threading.Timer(3.0, handle_start_phase1).start()

        return True

    @socketio.on('start_phase1')
    @locked
    def handle_start_phase1():
        if game_state.phase != 'phase0_complete':
            print(f"⚠️  Ignoring start_phase1 in phase {game_state.phase}")
            return
        print("Starting Phase 1: Winter Production")
        game_state.selected_roles_this_phase = []
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

        # Start 1-minute timer for talent selection
        start_timer('talent_selection', 60, game_state.phase, 'pass')

    @socketio.on('select_card')
    @locked
    def handle_select_card(data):
        player = current_player()
        if not player or game_state.phase not in ('phase1_production', 'phase2_production'):
            return

        # Prevent re-selection during same turn
        if request.sid in game_state.player_selections:
            emit('selection_error', {'message': 'You have already made your selection for this turn!'})
            return

        selection = data.get('index')
        player_name = player['name']

        # Check affordability
        if selection != 'pass':
            if (not isinstance(selection, int) or isinstance(selection, bool) or
                    not 0 <= selection < len(game_state.current_turn_cards)):
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
        # Clear talent selection timer since all players have selected
        clear_timer()

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

        # Start 30-second timer for bidding
        start_timer('bidding', 30, game_state.phase, 'bid_zero')

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

        # Start 20-second continue timer
        start_timer('continue', 20, game_state.phase, 'auto_ready')

        broadcast_game_state()
    
    def continue_after_bidding_results():
        """
        Called after showing bidding results.
        Either starts the next bidding war or continues the turn.
        """
        uncontested_cards = game_state.bidding_war.get('uncontested_cards', {})
        
        # Reset active bidding war
        game_state.bidding_war['active'] = False

        # CRITICAL FIX: Clear player selections BEFORE returning to production phase
        # This prevents the UI from showing stale "selected" status
        game_state.player_selections = {}

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
    @locked
    def handle_submit_bid(data):
        """
        Handle a player's bid submission during a bidding war.
        Validates affordability and automatically resolves when all bids are in.
        """
        bid_amount = data.get('bid_amount', 0)
        if not isinstance(bid_amount, int) or isinstance(bid_amount, bool):
            emit('bid_error', {'message': 'Invalid bid!'})
            return

        # Validation checks
        if not game_state.bidding_war.get('active') or not game_state.phase.endswith('_bidding'):
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

    def schedule_auto_bid(disconnected_sid, player_name):
        """
        Schedule an automatic $0 bid for a disconnected participant.
        If they reconnect before the timeout, this will be cancelled.
        """
        import threading
        import time

        @locked
        def submit_if_still_needed():
            # Check if still needed (player might have reconnected and bid)
            if not game_state.bidding_war.get('active') or not game_state.phase.endswith('_bidding'):
                print(f'  ⏭️ Auto-bid cancelled: bidding war already resolved')
                return

            if disconnected_sid not in game_state.bidding_war['participants']:
                print(f'  ⏭️ Auto-bid cancelled: participant reconnected with new ID')
                return

            if disconnected_sid in game_state.bidding_war['bids']:
                print(f'  ⏭️ Auto-bid cancelled: {player_name} already submitted bid')
                return

            # Still disconnected after timeout - auto-submit $0 bid
            print(f'\n⏰ TIMEOUT: Auto-submitting $0 bid for disconnected player {player_name}')
            game_state.bidding_war['bids'][disconnected_sid] = 0

            # Check if this completes the bidding
            num_bids = len(game_state.bidding_war['bids'])
            num_participants = len(game_state.bidding_war['participants'])

            if num_bids == num_participants:
                print(f"✓ All {num_participants} participants have now submitted bids (including auto-bids)!")
                resolve_bidding_war()
            else:
                print(f"  Waiting for {num_participants - num_bids} more bid(s)...")
                broadcast_game_state()

        def auto_submit_bid():
            # Wait 60 seconds for reconnection (outside the lock)
            time.sleep(60)
            submit_if_still_needed()

        # Start timeout thread
        timeout_thread = threading.Thread(target=auto_submit_bid, daemon=True)
        timeout_thread.start()

    def award_card_to_player(player_sid, card_index, extra_bid=0):
        """Give a card to a player and deduct cost"""
        card = game_state.current_turn_cards[card_index]
        player = game_state.players[player_sid]
        
        total_cost = card['salary'] + extra_bid
        
        print(f"  â†’ Awarding {card['name']} to {player['name']} for ${total_cost}M")
        print(f"     Money: ${player['money']}M â†’ ${player['money'] - total_cost}M")
        
        player['money'] -= total_cost
        player['roles'].append(card.copy())

        if card['name'] not in game_state.selected_roles_this_phase:
            game_state.selected_roles_this_phase.append(card['name'])
    
    def advance_turn():
        """Move to next turn or phase"""
        # Prevent multiple calls during the same turn resolution
        if game_state.advancing_turn:
            print("⚠️  advance_turn() already in progress, skipping duplicate call")
            return

        game_state.advancing_turn = True

        try:
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
        finally:
            # Always reset the flag, even if an exception occurs
            game_state.advancing_turn = False

    # ============================================================================
    # TIMER MANAGEMENT SYSTEM
    # ============================================================================

    def start_timer(timer_type, duration_seconds, phase, auto_action):
        """Start a server-synchronized timer"""
        import time
        import uuid
        token = str(uuid.uuid4())
        game_state.active_timer = {
            'type': timer_type,
            'duration': duration_seconds,
            'start_time': time.time(),
            'phase': phase,
            'auto_action': auto_action,
            'token': token
        }
        print(f"\n⏱️  TIMER STARTED: {timer_type} ({duration_seconds}s) for {phase}\n")
        broadcast_game_state()

        # Schedule auto-action after duration, passing the token so stale threads can self-cancel
        threading.Timer(duration_seconds, handle_timer_expiry, args=[token]).start()

    @locked
    def handle_timer_expiry(token=None):
        """Called when timer reaches 0"""
        if not game_state.active_timer['type']:
            print("⏱️  Timer expired but was already cancelled")
            return  # Timer was cancelled

        # Token check: if a new timer has started since this thread was scheduled,
        # the stored token will differ. Ignore stale threads to prevent wrong auto-actions.
        if token and game_state.active_timer.get('token') != token:
            print(f"⏱️  Stale timer thread fired (token mismatch), ignoring")
            return

        timer_type = game_state.active_timer['type']
        print(f"\n⏰ TIMER EXPIRED: {timer_type}\n")

        # Silently clear FIRST so auto-actions can start new timers without being overwritten.
        # Do NOT broadcast here - the action functions handle broadcasting with the correct new state.
        game_state.active_timer = {
            'type': None,
            'duration': 0,
            'start_time': None,
            'phase': None,
            'auto_action': None,
            'token': None
        }

        # Trigger auto-action (may start new timers - that is fine now that we cleared first)
        if timer_type == 'talent_selection':
            auto_submit_talent_passes()
        elif timer_type == 'bidding':
            auto_submit_missing_bids()
        elif timer_type == 'continue':
            auto_ready_all_players()
        elif timer_type == 'voting':
            auto_submit_missing_votes()

    def clear_timer():
        """Reset timer state"""
        if game_state.active_timer['type']:
            print(f"⏱️  Timer cleared: {game_state.active_timer['type']}")
        game_state.active_timer = {
            'type': None,
            'duration': 0,
            'start_time': None,
            'phase': None,
            'auto_action': None,
            'token': None
        }
        broadcast_game_state()

    def auto_submit_talent_passes():
        """Auto-pass for players who haven't selected"""
        for sid, player in game_state.players.items():
            if sid not in game_state.player_selections:
                # Auto-pass for this player
                game_state.player_selections[sid] = 'pass'
                print(f"⏰ AUTO-PASS: {player['name']} (timer expired)")

        # Trigger resolution
        if len(game_state.player_selections) == len(game_state.players):
            resolve_selections()

    def auto_submit_missing_bids():
        """Auto-submit $0 bid for participants who haven't bid"""
        if not game_state.bidding_war.get('active', False):
            print("⚠️  Cannot auto-submit bids: no active bidding war")
            return

        for sid in game_state.bidding_war['participants']:
            if sid not in game_state.bidding_war['bids']:
                game_state.bidding_war['bids'][sid] = 0
                player_name = game_state.players[sid]['name']
                print(f"⏰ AUTO-BID $0: {player_name} (timer expired)")

        # Trigger resolution
        resolve_bidding_war()

    def auto_submit_missing_votes():
        """Auto-vote for players who haven't voted (on timer expiry or eligible-voter completion)"""
        if not game_state.awards or game_state.phase != 'awards_voting':
            print("⚠️  Cannot auto-vote: not in awards voting phase")
            return

        current_cat_key = game_state.awards['current_category']
        category = game_state.awards['categories'][current_cat_key]
        nominees = category['nominees']

        for sid, player in game_state.players.items():
            if sid in category['votes']:
                continue  # Already voted

            voter_studio = player['name']
            # Auto-vote for the first nominee the player is eligible for
            voted = False
            for i, film in enumerate(nominees):
                if film.get('studio') != voter_studio:
                    category['votes'][sid] = i
                    print(f"⏰ AUTO-VOTE: {player['name']} → {film['title']}")
                    voted = True
                    break

            if not voted:
                print(f"⏰ AUTO-VOTE SKIP: {player['name']} owns all nominees, cannot vote")

        calculate_award_winner(current_cat_key)

    def auto_ready_all_players():
        """Auto-ready players who haven't clicked continue and trigger progression"""
        phase = game_state.phase
        print(f"\n⏰ AUTO-READY triggered for phase: {phase}\n")

        # Set flags for all players based on phase
        if phase == 'phase1_releases':
            # Spring Releases → Summer Production
            for player in game_state.players.values():
                if not player.get('spring_releases_ready', False):
                    player['spring_releases_ready'] = True
                    print(f"⏰ AUTO-READY: {player['name']} (Spring releases)")

            # Trigger progression to Summer
            print("\n=== All players auto-readied - Starting Phase 2: Summer Production ===\n")
            game_state.phase = 'phase2_production'
            game_state.turn = 1
            game_state.selected_roles_this_phase = []

            # Reset ready flags
            for p in game_state.players.values():
                p['spring_ready'] = False
                p['holiday_ready'] = False
                p['spring_releases_ready'] = False

            start_new_turn()

        elif phase == 'phase2_releases':
            # Holiday Releases → Award Season
            for player in game_state.players.values():
                if not player.get('holiday_releases_ready', False):
                    player['holiday_releases_ready'] = True
                    print(f"⏰ AUTO-READY: {player['name']} (Holiday releases)")

            # Trigger progression to Awards
            print("\n=== All players auto-readied - Starting Award Season ===\n")

            # Reset ready flag
            for p in game_state.players.values():
                p['holiday_releases_ready'] = False

            # Set up awards
            awards_data = game_logic.setup_awards(game_state.players, active_categories=['best_picture'])

            if not awards_data:
                print("Not enough films for awards! Skipping to final results.")
                game_state.phase = 'game_complete'
            else:
                game_state.awards = awards_data
                game_state.phase = 'awards_voting'
                start_timer('voting', 60, 'awards_voting', 'auto_vote')

        elif phase == 'awards_results':
            # Awards Results → Game Complete
            for player in game_state.players.values():
                if not player.get('awards_results_ready', False):
                    player['awards_results_ready'] = True
                    print(f"⏰ AUTO-READY: {player['name']} (Awards results)")

            # Trigger game completion
            print("\n=== All players auto-readied - GAME COMPLETE ===\n")

            # Reset ready flags
            for p in game_state.players.values():
                p['awards_results_ready'] = False

            game_state.phase = 'game_complete'

        elif 'bidding_results' in phase:
            # Bidding Results → Next conflict or continue turn
            for player in game_state.players.values():
                if not player.get('bidding_results_ready', False):
                    player['bidding_results_ready'] = True
                    print(f"⏰ AUTO-READY: {player['name']} (Bidding results)")

            # Reset ready flags
            for p in game_state.players.values():
                p['bidding_results_ready'] = False

            # Trigger progression
            continue_after_bidding_results()
        else:
            print(f"⚠️  Cannot auto-ready: unknown phase {phase}")
            return

        broadcast_game_state()

    @socketio.on('continue_after_bidding')
    @locked
    def handle_continue_after_bidding():
        """
        Socket handler for when players/host continue after viewing bidding results.
        Proceeds to next conflict or continues turn.
        """
        player = current_player()
        if not player or not game_state.phase.endswith('_bidding_results'):
            return
        player['bidding_results_ready'] = True
        
        player_name = player['name']
        ready_count = sum(1 for p in game_state.players.values() if p.get('bidding_results_ready', False))
        total_count = len(game_state.players)
        print(f"  {player_name} ready to continue ({ready_count}/{total_count})")
        
        # Check if all players ready
        if all(p.get('bidding_results_ready', False) for p in game_state.players.values()):
            # Clear continue timer since all players are ready
            clear_timer()

            # Reset ready flags
            for p in game_state.players.values():
                p['bidding_results_ready'] = False

            continue_after_bidding_results()
        else:
            broadcast_game_state()
    
    @socketio.on('request_update')
    @locked
    def handle_request_update():
        # Only the asking client needs a fresh copy
        emit('game_update', game_state.to_dict())

    @socketio.on('greenlight_film')
    @locked
    def handle_greenlight_film(data):
        player = current_player()
        if not player or game_state.phase not in ('phase1_packaging', 'phase2_packaging'):
            return
        role_indices = data.get('roleIndices', [])
        title = str(data.get('title', '')).strip()[:80]
        teaser = str(data.get('teaser', '')).strip()[:200]

        if not title:
            emit('package_error', {'message': 'Film title is required!'})
            return

        if (not isinstance(role_indices, list) or
                not all(isinstance(i, int) and not isinstance(i, bool) for i in role_indices) or
                len(set(i for i in role_indices if i >= 0)) != len([i for i in role_indices if i >= 0])):
            emit('package_error', {'message': 'Invalid package!'})
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

        # Charge for no-name talent (purchased talent was already paid at selection time)
        no_name_array = list(no_name_talent.values())
        no_name_cost = sum(
            no_name_array[abs(idx) - 1]['salary']
            for idx in role_indices
            if idx < 0 and abs(idx) - 1 < len(no_name_array)
        )
        if no_name_cost > 0:
            if player['money'] < no_name_cost:
                emit('package_error', {'message': f"Can't afford no-name talent (costs ${no_name_cost}M)!"})
                return
            player['money'] -= no_name_cost
            print(f"  {player['name']} paid ${no_name_cost}M for no-name talent")

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
    @locked
    def handle_finish_packaging():
        player = current_player()
        if not player or game_state.phase not in ('phase1_packaging', 'phase2_packaging'):
            return
        finish_packaging_for(player)
        check_packaging_complete()
        broadcast_game_state()

    def finish_packaging_for(player):
        """Release a player's leftover roles (half refund) and mark them done packaging"""
        if player.get('roles'):
            refund = sum(r['salary'] for r in player['roles']) // 2
            player['money'] += refund
            print(f"{player['name']} released {len(player['roles'])} roles for ${refund}M")
            player['roles'] = []

        if game_state.phase == 'phase1_packaging':
            player['spring_ready'] = True
        elif game_state.phase == 'phase2_packaging':
            player['holiday_ready'] = True

    def check_packaging_complete():
        if game_state.phase == 'phase1_packaging':
            if all(p.get('spring_ready', False) for p in game_state.players.values()):
                start_releases('Spring', 'phase1_releases')
        elif game_state.phase == 'phase2_packaging':
            if all(p.get('holiday_ready', False) for p in game_state.players.values()):
                start_releases('Holiday', 'phase2_releases')

    @socketio.on('host_skip_waiting')
    @locked
    def handle_host_skip_waiting():
        """
        Host override for the two untimed phases (naming, packaging) so a player who
        has left for good can't hold the game hostage.
        """
        if request.sid in game_state.players:
            return  # Players can't use the host override
        phase = game_state.phase

        if phase == 'phase0_naming':
            for sid, prog in game_state.naming_progress['submissions'].items():
                if prog['complete']:
                    continue
                print(f"⏭️  HOST SKIP: auto-naming talent for {game_state.players[sid]['name']}")
                while not prog['complete'] and game_state.phase == 'phase0_naming':
                    counts = {r: len(prog[r]) for r in ('screenwriter', 'director', 'star')}
                    role = next(r for r, limit in (('screenwriter', 3), ('director', 3), ('star', 5))
                                if counts[r] < limit)
                    pool = game_logic.DEFAULT_NAMES[role]
                    add_talent_name(sid, pool[counts[role] % len(pool)])
        elif phase in ('phase1_packaging', 'phase2_packaging'):
            ready_flag = 'spring_ready' if phase == 'phase1_packaging' else 'holiday_ready'
            for player in game_state.players.values():
                if not player.get(ready_flag):
                    print(f"⏭️  HOST SKIP: finishing packaging for {player['name']}")
                    finish_packaging_for(player)
            check_packaging_complete()
        else:
            return

        broadcast_game_state()

    @socketio.on('reset_game')
    @locked
    def handle_reset_game():
        """Host starts a new game, keeping the current roster of studios"""
        if request.sid in game_state.players or game_state.phase != 'game_complete':
            return
        roster = {sid: p for sid, p in game_state.players.items()}
        game_state.reset()  # Also clears the timer token, so any stale timer thread is ignored
        for sid, p in roster.items():
            game_state.players[sid] = {
                'name': p['name'],
                'money': 100,
                'score': 0,
                'roles': [],
                'films': [],
                'connected': p.get('connected', False)
            }
        print(f"\n🔁 NEW GAME - back to lobby with {len(roster)} studios\n")
        broadcast_game_state()

    def start_releases(season_name, phase_name):
        """Generic function to handle any release phase"""
        game_state.phase = phase_name
        game_logic.process_film_releases(game_state.players, season_name)

        # Start 20-second continue timer for releases screen
        start_timer('continue', 20, phase_name, 'auto_ready')

        broadcast_game_state()
    
    @socketio.on('continue_to_summer')
    @locked
    def handle_continue_to_summer():
        """Start Phase 2: Summer Production - wait for all players"""
        player = current_player()
        if not player or game_state.phase != 'phase1_releases':
            return
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
            game_state.selected_roles_this_phase = []

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
    @locked
    def handle_start_awards():
        """Start Award Season - wait for all players"""
        player = current_player()
        if not player or game_state.phase != 'phase2_releases':
            return
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
                clear_timer()
                game_state.phase = 'game_complete'
                broadcast_game_state()
                return
            
            game_state.phase = 'awards_voting'
            game_state.awards = awards_data

            print(f"Award Season initialized with categories: {awards_data['active_categories']}")
            print(f"Nominees: {len(awards_data['categories']['best_picture']['nominees'])} films")

            # Start 60-second voting timer (auto-votes for any non-voters on expiry)
            start_timer('voting', 60, 'awards_voting', 'auto_vote')

            broadcast_game_state()
        else:
            broadcast_game_state()
    
    @socketio.on('vote_for_nominee')
    @locked
    def handle_vote(data):
        """Player votes for a nominee"""
        nominee_index = data.get('nominee_index')

        if not game_state.awards or game_state.phase != 'awards_voting' or not current_player():
            return

        current_cat_key = game_state.awards['current_category']
        category = game_state.awards['categories'][current_cat_key]
        nominees = category['nominees']

        # Validate vote
        if (not isinstance(nominee_index, int) or isinstance(nominee_index, bool) or
                not 0 <= nominee_index < len(nominees)):
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

        # Check if all *eligible* voters have voted.
        # A player is eligible if at least one nominee isn't their own film.
        eligible_voter_sids = [
            sid for sid, player in game_state.players.items()
            if any(film.get('studio') != player['name'] for film in nominees)
        ]

        all_eligible_voted = bool(eligible_voter_sids) and all(
            sid in category['votes'] for sid in eligible_voter_sids
        )
        no_one_eligible = not eligible_voter_sids

        if all_eligible_voted or no_one_eligible:
            calculate_award_winner(current_cat_key)
        else:
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

        # Start 20-second continue timer for awards results
        start_timer('continue', 20, 'awards_results', 'auto_ready')

        broadcast_game_state()
    
    @socketio.on('continue_from_awards')
    @locked
    def handle_continue_from_awards():
        """Handle continuing from awards results to game complete"""
        player = current_player()
        if not player or game_state.phase != 'awards_results':
            return
        player['awards_results_ready'] = True
        
        player_name = player['name']
        ready_count = sum(1 for p in game_state.players.values() if p.get('awards_results_ready', False))
        total_count = len(game_state.players)
        print(f"  {player_name} ready to end game ({ready_count}/{total_count})")
        
        # Check if all players ready
        if all(p.get('awards_results_ready', False) for p in game_state.players.values()):
            # Clear continue timer since all players are ready
            clear_timer()

            print("\n=== GAME COMPLETE ===\n")
            
            # Reset ready flags
            for p in game_state.players.values():
                p['awards_results_ready'] = False
            
            game_state.phase = 'game_complete'
            broadcast_game_state()
        else:
            broadcast_game_state()
    
    @socketio.on('disconnect')
    @locked
    def handle_disconnect():
        connected_sids.discard(request.sid)
        if request.sid in game_state.players:
            player_name = game_state.players[request.sid]['name']
            game_state.players[request.sid]['connected'] = False
            print(f'📱 {player_name} disconnected (socket: {request.sid[:8]})')
            print(f'  💾 Player data preserved for reconnection')
            # Let the host see who has dropped
            broadcast_game_state()

            # Track disconnect during active bidding war
            if game_state.bidding_war.get('active'):
                if request.sid in game_state.bidding_war['participants']:
                    if request.sid not in game_state.bidding_war['bids']:
                        # They disconnected without submitting a bid
                        print(f'  ⚠️ {player_name} disconnected during bidding war without submitting bid')

                        # Add to bidding_war state to track disconnect time
                        if 'disconnect_times' not in game_state.bidding_war:
                            game_state.bidding_war['disconnect_times'] = {}

                        import time
                        game_state.bidding_war['disconnect_times'][request.sid] = time.time()

                        # Schedule auto-bid after timeout
                        schedule_auto_bid(request.sid, player_name)

                        # Broadcast updated state to show disconnect status
                        broadcast_game_state()

        # DON'T delete the player - keep their data for reconnection
        # When they reconnect, join_game will update their socket.id
        # This prevents losing progress when mobile phones go to sleep