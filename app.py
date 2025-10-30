from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hollywood-game-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Game state
game_state = {
    'phase': 'lobby',  # lobby, phase0_naming, phase1_production, etc.
    'players': {},  # {session_id: {'name': str, 'money': int, 'score': int}}
    'talent_pool': [],  # All generated talent
    'naming_progress': {  # Track Phase 0 naming
        'submissions': {}  # {player_sid: {'screenwriter': [], 'director': [], 'star': [], 'complete': bool}}
    },
    'year': 0,
    'turn': 0,
    'current_turn_cards': [],  # Cards available this turn
    'player_selections': {},  # {player_sid: card_index or 'pass'}
    'bidding_war': None,  # {card_index: int, players: [sids], bids: {sid: amount}}
}

ROLE_TYPES = {
    'screenwriter': {'count': 3, 'label': 'Screenwriters'},
    'director': {'count': 3, 'label': 'Directors'},
    'star': {'count': 5, 'label': 'Stars'},
    'producer': {'count': 0, 'label': 'Producers'}  # Generated separately
}

GENRES = ['Action', 'Comedy', 'Drama', 'Horror', 'Romance', 'Sci-Fi', 'Thriller', 'Western']
AUDIENCES = ['Kids', 'Teens', 'Adults', 'Families', 'Art House']

# Pre-generated names for Phase 0 (Goldman era-inspired)
DEFAULT_NAMES = {
    'screenwriter': [
        'Bobby Goldman',
        'Nora Ephron Jr.',
        'Paddy Chayefsky II',
        'Alvin Sargent',
        'Frank Pierson',
        'Ernest Lehman III',
        'Ruth Prawer',
        'Horton Foote Jr.',
        'Robert Towne II',
        'Lorenzo Semple'
    ],
    'director': [
        'Stevie Screensberg',
        'Frankie Coppola',
        'Marty Scorcese',
        'Bobby Altman',
        'Mike Nichols Jr.',
        'Billy Wilder II',
        'Stanley Kubrick III',
        'Arthur Penn',
        'Sydney Pollack Jr.',
        'Hal Ashby'
    ],
    'star': [
        'Dusty Hoffman',
        'Bobby DeNiro',
        'Jackie Nicholson',
        'Meryl Streepleton',
        'Robbie Redford',
        'Warren Beatty Jr.',
        'Faye Dunaway II',
        'Al Pacino III',
        'Diane Keaton',
        'Gene Hackman Jr.'
    ]
}

def get_default_name(role_type, count):
    """Get a default name for a role type based on count"""
    names = DEFAULT_NAMES.get(role_type, [])
    if count < len(names):
        return names[count]
    return ""  # Return empty if we run out

def generate_talent_stats(role_type, name, is_producer=False):
    """Generate Heat, Prestige, and Salary for a talent"""
    heat = random.randint(1, 255)
    prestige = random.randint(1, 100)
    
    # Producer generation (during Phase 1)
    if is_producer:
        # Most producers are cheap and provide no stats
        if random.random() < 0.7:  # 70% are basic producers
            heat = 0
            prestige = 0
            salary = random.randint(1, 3)
        else:  # 30% are premium producers
            if random.random() < 0.5:  # Half provide Heat
                heat = random.randint(50, 100)
                prestige = 0
                salary = random.randint(8, 15)
            else:  # Half provide Prestige
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
        # Directors: high heat = high salary, prestige inversely related to heat
        salary = (heat // 10) + random.randint(1, 5)
        prestige = max(1, 100 - (heat // 3) + random.randint(-10, 10))
    elif role_type == 'screenwriter':
        # Screenwriters: prestige-driven salary
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
    
    # Add audience for screenwriters
    if role_type == 'screenwriter':
        result['audience'] = random.choice(AUDIENCES)
    
    return result

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
                talent['name'] = f"{base_name} {['II', 'III', 'IV', 'V'][name_counts[base_name]-2]}"
        else:
            name_counts[base_name] = 1

@app.route('/')
def index():
    """Host view"""
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Hollywood Game - Host</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        body { font-family: Arial; max-width: 1200px; margin: 20px auto; padding: 20px; background: #1a1a1a; color: #fff; }
        h1 { color: #e50914; }
        .player-card { border: 2px solid #e50914; padding: 15px; margin: 10px; display: inline-block; background: #2a2a2a; }
        button { padding: 12px 24px; margin: 5px; font-size: 16px; background: #e50914; color: white; border: none; cursor: pointer; }
        button:hover { background: #f40612; }
        .phase-info { background: #2a2a2a; padding: 20px; margin: 20px 0; border-left: 4px solid #e50914; }
        .talent-card { background: #333; padding: 15px; margin: 10px; border-radius: 5px; display: inline-block; min-width: 200px; }
        .submissions { background: #2a2a2a; padding: 15px; margin: 10px 0; }
    </style>
</head>
<body>
    <h1>🎬 Hollywood Moguls - Host View</h1>
    <p>Players connect at: <strong>http://YOUR_LOCAL_IP:8080/player</strong></p>
    
    <div class="phase-info">
        <h2>Phase: <span id="phase">Lobby</span></h2>
        <div id="phase-details"></div>
    </div>
    
    <div id="players"></div>
    
    <div id="controls">
        <button onclick="startPhase0()" id="start-btn">Start Game (Phase 0)</button>
    </div>
    
    <div id="content"></div>
    
    <script>
        const socket = io();
        
        socket.on('game_update', (data) => {
            updateDisplay(data);
        });
        
        function updateDisplay(state) {
            document.getElementById('phase').textContent = state.phase;
            
            // Update players
            const playersDiv = document.getElementById('players');
            playersDiv.innerHTML = '<h2>Players:</h2>';
            for (let [sid, player] of Object.entries(state.players)) {
                playersDiv.innerHTML += `
                    <div class="player-card">
                        <h3>${player.name}</h3>
                        <p>💰 Budget: $${player.money}M</p>
                        <p>⭐ Score: ${player.score}</p>
                    </div>
                `;
            }
            
            // Phase-specific content
            const contentDiv = document.getElementById('content');
            const detailsDiv = document.getElementById('phase-details');
            
            if (state.phase === 'phase0_naming') {
                const prog = state.naming_progress;
                let completedCount = 0;
                for (let sid in prog.submissions) {
                    if (prog.submissions[sid].complete) completedCount++;
                }
                detailsDiv.innerHTML = `
                    <p>Players naming talent...</p>
                    <p>${completedCount} of ${Object.keys(state.players).length} players finished</p>
                `;
                
                contentDiv.innerHTML = '<div class="submissions"><h3>Player Progress:</h3>';
                for (let [sid, player] of Object.entries(state.players)) {
                    const playerProg = prog.submissions[sid];
                    if (playerProg && playerProg.complete) {
                        contentDiv.innerHTML += `<p>✅ ${player.name} - Complete!</p>`;
                    } else if (playerProg) {
                        const total = playerProg.screenwriter.length + playerProg.director.length + playerProg.star.length;
                        contentDiv.innerHTML += `<p>⏳ ${player.name} - ${total}/11 names submitted</p>`;
                    } else {
                        contentDiv.innerHTML += `<p>⏳ ${player.name} - Starting...</p>`;
                    }
                }
                contentDiv.innerHTML += '</div>';
            } else if (state.phase === 'phase0_complete') {
                detailsDiv.innerHTML = '<p>All talent generated! Ready to start production.</p>';
                contentDiv.innerHTML = '<h3>Talent Pool:</h3>';
                
                const byRole = {screenwriter: [], director: [], star: []};
                state.talent_pool.forEach(t => byRole[t.role].push(t));
                
                for (let [role, talents] of Object.entries(byRole)) {
                    contentDiv.innerHTML += `<h4>${role.toUpperCase()}S:</h4>`;
                    talents.forEach(t => {
                        contentDiv.innerHTML += `
                            <div class="talent-card">
                                <strong>${t.name}</strong><br>
                                Heat: ${t.heat_bucket} | Prestige: ${t.prestige_bucket}<br>
                                Salary: $${t.salary}M
                            </div>
                        `;
                    });
                }
                
                document.getElementById('start-btn').innerHTML = 'Start Phase 1 (Production)';
                document.getElementById('start-btn').onclick = startPhase1;
            } else if (state.phase === 'phase1_production') {
                detailsDiv.innerHTML = `<p>Year ${state.year}, Turn ${state.turn} of 4</p>`;
                contentDiv.innerHTML = '<h3>Available Roles This Turn:</h3>';
                
                state.current_turn_cards.forEach((card, i) => {
                    contentDiv.innerHTML += `
                        <div class="talent-card">
                            <strong>${card.name}</strong> (${card.role.toUpperCase()})<br>
                            Heat: ${card.heat_bucket} | Prestige: ${card.prestige_bucket}<br>
                            Salary: ${card.salary}M<br>
                            ${card.genre ? `Genre: ${card.genre}<br>` : ''}
                            ${card.audience ? `Audience: ${card.audience}<br>` : ''}
                        </div>
                    `;
                });
                
                contentDiv.innerHTML += '<h3>Player Selections:</h3><div class="submissions">';
                const numPlayers = Object.keys(state.players).length;
                const numSelections = Object.keys(state.player_selections).length;
                
                for (let [sid, player] of Object.entries(state.players)) {
                    const selected = state.player_selections[sid] !== undefined ? '✓' : '⏳';
                    contentDiv.innerHTML += `<p>${selected} ${player.name}</p>`;
                }
                contentDiv.innerHTML += `</div><p>${numSelections}/${numPlayers} players have selected</p>`;
            }
        }
        
        function startPhase0() {
            socket.emit('start_phase0');
        }
        
        function startPhase1() {
            socket.emit('start_phase1');
        }
    </script>
</body>
</html>
    ''')

@app.route('/player')
def player():
    """Player view"""
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Hollywood Game - Player</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        body { font-family: Arial; padding: 20px; background: #1a1a1a; color: white; margin: 0; }
        input, button { width: 100%; padding: 15px; margin: 10px 0; font-size: 18px; box-sizing: border-box; }
        button { background: #e50914; color: white; border: none; cursor: pointer; }
        button:hover { background: #f40612; }
        button:disabled { background: #666; cursor: not-allowed; }
        input { background: #333; color: white; border: 1px solid #666; }
        .screen { display: none; }
        .screen.active { display: block; }
        .info-box { background: #2a2a2a; padding: 15px; margin: 15px 0; border-radius: 5px; }
        h1, h2 { color: #e50914; margin-top: 0; }
    </style>
</head>
<body>
    <!-- Join Screen -->
    <div id="join-screen" class="screen active">
        <h1>🎬 Join Game</h1>
        <input type="text" id="playerName" placeholder="Your Studio Name">
        <button onclick="joinGame()">Join Game</button>
    </div>
    
    <!-- Lobby Screen -->
    <div id="lobby-screen" class="screen">
        <h1>🎬 Lobby</h1>
        <div class="info-box">
            <h2 id="studioName"></h2>
            <p>💰 Budget: $<span id="lobbyMoney">100</span>M</p>
        </div>
        <p>Waiting for host to start the game...</p>
    </div>
    
    <!-- Phase 0 Naming Screen -->
    <div id="naming-screen" class="screen">
        <h1>🎬 Name the Talent</h1>
        <div class="info-box">
            <h2>Name your <span id="roleType"></span></h2>
            <p id="roleProgress"></p>
            <p style="font-size: 14px; color: #aaa;">A name is suggested - edit it or submit as-is!</p>
        </div>
        <input type="text" id="talentName" placeholder="Enter name">
        <button onclick="submitName()" id="submit-btn">Submit</button>
    </div>
    
    <!-- Phase 0 Complete Screen -->
    <div id="phase0-complete-screen" class="screen">
        <h1>🎬 Talent Pool Created!</h1>
        <div class="info-box">
            <p>All talent has been generated and assigned stats.</p>
            <p>Waiting for host to start production phase...</p>
        </div>
    </div>
    
    <!-- Phase 1 Production Screen -->
    <div id="phase1-screen" class="screen">
        <h1>🎬 Year <span id="year">1</span>, Turn <span id="turnNum">1</span></h1>
        <div class="info-box">
            <h2 id="studioNameP1"></h2>
            <p>💰 Budget: $<span id="p1Money">100</span>M</p>
            <p id="roleInventory"></p>
        </div>
        <div id="cards-area"></div>
        <div id="selection-status"></div>
    </div>
    
    <!-- Phase 1 Packaging Screen -->
    <div id="packaging-screen" class="screen">
        <h1>🎬 Package Your Spring Films</h1>
        <div class="info-box">
            <h2 id="studioNamePkg"></h2>
            <p>💰 Budget: $<span id="pkgMoney">100</span>M</p>
            <p id="pkgRoleInventory"></p>
        </div>
        
        <h3>Your Available Roles:</h3>
        <div id="available-roles"></div>
        
        <h3>Current Film Package:</h3>
        <div id="current-package" class="info-box">
            <p><em>Select roles below to add to your film...</em></p>
        </div>
        
        <div id="package-actions" style="display:none;">
            <input type="text" id="filmTitle" placeholder="Film Title" style="margin: 10px 0;">
            <textarea id="filmTeaser" placeholder="Short teaser (optional)" 
                      style="width: 100%; height: 60px; padding: 10px; background: #333; color: white; border: 1px solid #666; margin: 10px 0;"></textarea>
            <button onclick="greenlight()">Greenlight This Film!</button>
            <button onclick="clearPackage()" style="background: #666;">Clear Package</button>
        </div>
        
        <h3>Your Greenlit Films:</h3>
        <div id="greenlit-films"></div>
        
        <button onclick="finishPackaging()" id="finish-pkg-btn">Done Packaging (Releases Remaining Roles)</button>
    </div>
    
    <script>
        const socket = io();
        let myName = '';
        let currentPackage = []; // Roles being assembled into current film
        let greenlitFilms = []; // Completed films ready for release
        
        function joinGame() {
            myName = document.getElementById('playerName').value.trim();
            if (myName) {
                socket.emit('join_game', {name: myName});
            }
        }
        
        socket.on('joined', () => {
            showScreen('lobby-screen');
            document.getElementById('studioName').textContent = myName;
            document.getElementById('studioNameP1').textContent = myName;
            document.getElementById('studioNamePkg').textContent = myName;
        });
        
        socket.on('selection_error', (data) => {
            alert(data.message);
        });
        
        socket.on('game_update', (data) => {
            const myData = data.players[socket.id];
            if (!myData) return;
            
            // Update money displays
            document.getElementById('lobbyMoney').textContent = myData.money;
            document.getElementById('p1Money').textContent = myData.money;
            document.getElementById('pkgMoney').textContent = myData.money;
            
            // Update greenlit films from server data
            if (myData.films) {
                greenlitFilms = myData.films;
            }
            
            // Handle phase transitions
            if (data.phase === 'phase0_naming') {
                showScreen('naming-screen');
                
                const myProg = data.naming_progress.submissions[socket.id];
                if (!myProg) {
                    // Player not initialized yet
                    return;
                }
                
                if (myProg.complete) {
                    // Already finished
                    document.getElementById('roleType').textContent = 'All Done!';
                    document.getElementById('roleProgress').textContent = 'Waiting for other players...';
                    document.getElementById('submit-btn').disabled = true;
                    document.getElementById('talentName').disabled = true;
                    return;
                }
                
                // Determine what they should name next
                let currentRole, currentCount, maxCount;
                if (myProg.screenwriter.length < 3) {
                    currentRole = 'screenwriter';
                    currentCount = myProg.screenwriter.length;
                    maxCount = 3;
                } else if (myProg.director.length < 3) {
                    currentRole = 'director';
                    currentCount = myProg.director.length;
                    maxCount = 3;
                } else if (myProg.star.length < 5) {
                    currentRole = 'star';
                    currentCount = myProg.star.length;
                    maxCount = 5;
                } else {
                    // Should be complete, but just in case
                    document.getElementById('roleType').textContent = 'All Done!';
                    document.getElementById('roleProgress').textContent = 'Waiting for other players...';
                    document.getElementById('submit-btn').disabled = true;
                    document.getElementById('talentName').disabled = true;
                    return;
                }
                
                const roleLabels = {
                    'screenwriter': 'Screenwriter',
                    'director': 'Director',
                    'star': 'Star'
                };
                
                document.getElementById('roleType').textContent = roleLabels[currentRole];
                document.getElementById('roleProgress').textContent = 
                    `${currentCount + 1} of ${maxCount}`;
                document.getElementById('submit-btn').disabled = false;
                document.getElementById('talentName').disabled = false;
                
                // Pre-fill with default name
                const defaultName = getDefaultName(currentRole, currentCount);
                document.getElementById('talentName').value = defaultName;
                document.getElementById('talentName').select(); // Select text for easy replacement
                document.getElementById('talentName').focus();
                
            } else if (data.phase === 'phase0_complete') {
                showScreen('phase0-complete-screen');
            } else if (data.phase === 'phase1_production') {
                showScreen('phase1-screen');
                document.getElementById('year').textContent = data.year;
                document.getElementById('turnNum').textContent = data.turn;
                
                // Debug
                console.log('Phase 1 - Current turn cards:', data.current_turn_cards);
                console.log('Phase 1 - Card count:', data.current_turn_cards ? data.current_turn_cards.length : 0);
                
                // Update role inventory
                updateRoleInventory(myData.roles || [], 'roleInventory');
                
                // Display cards
                const cardsArea = document.getElementById('cards-area');
                cardsArea.innerHTML = '<h3>Select a Role:</h3>';
                
                data.current_turn_cards.forEach((card, index) => {
                    const selected = data.player_selections[socket.id] === index;
                    const disabled = data.player_selections[socket.id] !== undefined;
                    
                    cardsArea.innerHTML += `
                        <div class="info-box" style="margin: 10px 0; ${selected ? 'border: 2px solid #e50914;' : ''}">
                            <h3>${card.name}</h3>
                            <p><strong>${card.role.toUpperCase()}</strong></p>
                            <p>Heat: ${card.heat_bucket} | Prestige: ${card.prestige_bucket}</p>
                            <p>Salary: ${card.salary}M</p>
                            ${card.genre ? `<p>Genre: ${card.genre}</p>` : ''}
                            ${card.audience ? `<p>Audience: ${card.audience}</p>` : ''}
                            <button onclick="selectCard(${index})" ${disabled ? 'disabled' : ''}>
                                ${selected ? 'Selected ✓' : 'Select'}
                            </button>
                        </div>
                    `;
                });
                
                // Pass button
                const passDisabled = data.player_selections[socket.id] !== undefined;
                const passSelected = data.player_selections[socket.id] === 'pass';
                cardsArea.innerHTML += `
                    <button onclick="selectPass()" ${passDisabled ? 'disabled' : ''} 
                            style="background: #666; margin-top: 10px;">
                        ${passSelected ? 'Passed ✓' : 'Pass This Turn'}
                    </button>
                `;
                
                // Status
                const statusDiv = document.getElementById('selection-status');
                if (data.player_selections[socket.id] !== undefined) {
                    statusDiv.innerHTML = '<p style="color: #e50914;">✓ Selection made! Waiting for other players...</p>';
                } else {
                    statusDiv.innerHTML = '';
                }
            } else if (data.phase === 'phase1_packaging') {
                showScreen('packaging-screen');
                
                // Debug: log what we're receiving
                console.log('Packaging phase - my roles:', myData.roles);
                console.log('Packaging phase - my films:', myData.films);
                
                updatePackagingView(data, myData);
            }
        });
        
        function submitName() {
            const name = document.getElementById('talentName').value.trim();
            if (name) {
                socket.emit('submit_talent_name', {name: name});
            }
        }
        
        function selectCard(index) {
            socket.emit('select_card', {index: index});
        }
        
        function selectPass() {
            socket.emit('select_card', {index: 'pass'});
        }
        
        function updatePackagingView(gameData, playerData) {
            const availableRoles = playerData.roles || [];
            const rolesDiv = document.getElementById('available-roles');
            rolesDiv.innerHTML = '';
            
            if (availableRoles.length === 0) {
                rolesDiv.innerHTML = '<p><em>No roles available (you can still finish packaging)</em></p>';
            } else {
                availableRoles.forEach((role, index) => {
                    const inPackage = currentPackage.includes(index);
                    rolesDiv.innerHTML += `
                        <div class="info-box" style="margin: 10px 0; ${inPackage ? 'opacity: 0.5;' : ''}">
                            <strong>${role.name}</strong> (${role.role.toUpperCase()})<br>
                            Heat: ${role.heat_bucket} | Prestige: ${role.prestige_bucket}<br>
                            Salary: ${role.salary}M<br>
                            ${role.genre ? `Genre: ${role.genre}<br>` : ''}
                            ${role.audience ? `Audience: ${role.audience}<br>` : ''}
                            <button onclick="toggleRole(${index})" ${inPackage ? 'disabled' : ''}>
                                ${inPackage ? 'In Package' : 'Add to Film'}
                            </button>
                        </div>
                    `;
                });
            }
            
            updatePackageDisplay(availableRoles);
            updateGreenlitDisplay();
        }
        
        function toggleRole(index) {
            if (currentPackage.includes(index)) {
                // Remove from package
                currentPackage = currentPackage.filter(i => i !== index);
            } else {
                // Add to package
                currentPackage.push(index);
            }
            // Trigger re-render
            const event = new CustomEvent('package-changed');
            document.dispatchEvent(event);
        }
        
        // Listen for package changes to re-render
        document.addEventListener('package-changed', () => {
            socket.emit('request_update');
        });
        
        function updatePackageDisplay(availableRoles) {
            const packageDiv = document.getElementById('current-package');
            const actionsDiv = document.getElementById('package-actions');
            
            if (currentPackage.length === 0) {
                packageDiv.innerHTML = '<p><em>Select roles below to add to your film...</em></p>';
                actionsDiv.style.display = 'none';
                return;
            }
            
            // Count role types
            let hasProducer = false, hasWriter = false, hasDirector = false, hasStar = false;
            let totalHeat = 0, totalPrestige = 0, roleCount = 0;
            
            packageDiv.innerHTML = '<h4>Roles in this film:</h4>';
            currentPackage.forEach(idx => {
                const role = availableRoles[idx];
                packageDiv.innerHTML += `<p>• ${role.name} (${role.role.toUpperCase()})</p>`;
                
                if (role.role === 'producer') hasProducer = true;
                if (role.role === 'screenwriter') hasWriter = true;
                if (role.role === 'director') hasDirector = true;
                if (role.role === 'star') hasStar = true;
                
                totalHeat += role.heat;
                totalPrestige += role.prestige;
                roleCount++;
            });
            
            const avgPrestige = Math.round(totalPrestige / roleCount);
            packageDiv.innerHTML += `<p><strong>Total Heat:</strong> ${totalHeat}</p>`;
            packageDiv.innerHTML += `<p><strong>Avg Prestige:</strong> ${avgPrestige}</p>`;
            
            // Check if valid package
            const isValid = hasProducer && hasWriter && hasDirector && hasStar;
            if (isValid) {
                packageDiv.innerHTML += '<p style="color: #4CAF50;">✓ Valid film package!</p>';
                actionsDiv.style.display = 'block';
            } else {
                packageDiv.innerHTML += '<p style="color: #ff9800;">⚠ Need: Producer, Screenwriter, Director, and at least 1 Star</p>';
                actionsDiv.style.display = 'none';
            }
        }
        
        function clearPackage() {
            currentPackage = [];
            socket.emit('request_update');
        }
        
        function greenlight() {
            const title = document.getElementById('filmTitle').value.trim();
            const teaser = document.getElementById('filmTeaser').value.trim();
            
            if (!title) {
                alert('Please enter a film title!');
                return;
            }
            
            socket.emit('greenlight_film', {
                roleIndices: currentPackage,
                title: title,
                teaser: teaser
            });
            
            // Clear for next film
            currentPackage = [];
            document.getElementById('filmTitle').value = '';
            document.getElementById('filmTeaser').value = '';
        }
        
        function updateGreenlitDisplay() {
            const greenlitDiv = document.getElementById('greenlit-films');
            if (greenlitFilms.length === 0) {
                greenlitDiv.innerHTML = '<p><em>No films greenlit yet</em></p>';
            } else {
                greenlitDiv.innerHTML = '';
                greenlitFilms.forEach(film => {
                    greenlitDiv.innerHTML += `
                        <div class="info-box" style="margin: 10px 0; border: 2px solid #4CAF50;">
                            <h4>${film.title}</h4>
                            <p>${film.teaser}</p>
                            <p>${film.roles.length} roles</p>
                        </div>
                    `;
                });
            }
        }
        
        function finishPackaging() {
            if (confirm('Release all remaining roles and move to Spring releases?')) {
                socket.emit('finish_packaging');
            }
        }
        
        function showScreen(screenId) {
            document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
            document.getElementById(screenId).classList.add('active');
        }
        
        function getRoleCount(role) {
            const counts = {'screenwriter': 3, 'director': 3, 'star': 5};
            return counts[role];
        }
        
        function getDefaultName(roleType, count) {
            const names = {
                'screenwriter': [
                    'Bobby Goldman',
                    'Nora Ephron Jr.',
                    'Paddy Chayefsky II',
                    'Alvin Sargent',
                    'Frank Pierson',
                    'Ernest Lehman III',
                    'Ruth Prawer',
                    'Horton Foote Jr.',
                    'Robert Towne II',
                    'Lorenzo Semple'
                ],
                'director': [
                    'Stevie Screensberg',
                    'Frankie Coppola',
                    'Marty Scorcese',
                    'Bobby Altman',
                    'Mike Nichols Jr.',
                    'Billy Wilder II',
                    'Stanley Kubrick III',
                    'Arthur Penn',
                    'Sydney Pollack Jr.',
                    'Hal Ashby'
                ],
                'star': [
                    'Dusty Hoffman',
                    'Bobby DeNiro',
                    'Jackie Nicholson',
                    'Meryl Streepleton',
                    'Robbie Redford',
                    'Warren Beatty Jr.',
                    'Faye Dunaway II',
                    'Al Pacino III',
                    'Diane Keaton',
                    'Gene Hackman Jr.'
                ]
            };
            
            const roleNames = names[roleType] || [];
            return count < roleNames.length ? roleNames[count] : '';
        }
        
        // Allow Enter key to submit
        document.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                if (document.getElementById('join-screen').classList.contains('active')) {
                    joinGame();
                } else if (document.getElementById('naming-screen').classList.contains('active')) {
                    submitName();
                }
            }
        });
    </script>
</body>
</html>
    ''')

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')

@socketio.on('join_game')
def handle_join(data):
    player_name = data['name']
    game_state['players'][request.sid] = {
        'name': player_name,
        'money': 100,
        'score': 0,
        'roles': []
    }
    print(f'{player_name} joined the game')
    emit('joined')
    broadcast_game_state()

@socketio.on('start_phase0')
def handle_start_phase0():
    print("Starting Phase 0: Talent Naming")
    game_state['phase'] = 'phase0_naming'
    # Initialize empty submissions for each player
    game_state['naming_progress'] = {
        'submissions': {
            sid: {'screenwriter': [], 'director': [], 'star': [], 'complete': False}
            for sid in game_state['players'].keys()
        }
    }
    broadcast_game_state()

@socketio.on('submit_talent_name')
def handle_talent_name(data):
    name = data['name']
    prog = game_state['naming_progress']
    
    # Check if player exists in submissions (handle reconnects)
    if request.sid not in prog['submissions']:
        return
    
    player_prog = prog['submissions'][request.sid]
    
    # Check if already complete
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
        return  # Already done
    
    print(f"{game_state['players'][request.sid]['name']} submitted {role_type}: {name}")
    
    # Generate stats for this talent
    talent = generate_talent_stats(role_type, name)
    game_state['talent_pool'].append(talent)
    
    # Check if this player is done (after adding the name)
    if (len(player_prog['screenwriter']) == 3 and 
        len(player_prog['director']) == 3 and 
        len(player_prog['star']) == 5):
        player_prog['complete'] = True
        print(f"{game_state['players'][request.sid]['name']} completed Phase 0!")
        
        # Check if ALL players are done
        all_complete = all(p['complete'] for p in prog['submissions'].values())
        if all_complete:
            handle_duplicate_names(game_state['talent_pool'])
            game_state['phase'] = 'phase0_complete'
            print("Phase 0 complete! All talent generated.")
    
    broadcast_game_state()

@socketio.on('start_phase1')
def handle_start_phase1():
    print("Starting Phase 1: Winter Production")
    game_state['phase'] = 'phase1_production'
    game_state['year'] = 1
    game_state['turn'] = 1
    start_new_turn()
    broadcast_game_state()

def start_new_turn():
    """Generate cards for the current turn"""
    num_players = len(game_state['players'])
    num_cards = num_players + 1
    
    # Reset selections
    game_state['player_selections'] = {}
    game_state['bidding_war'] = None
    
    # Generate random cards from talent pool + new producers
    cards = []
    
    # Add some existing talent (make sure we have a copy, not reference)
    available_talent = [t.copy() for t in game_state['talent_pool']]
    
    print(f"  Available talent pool size: {len(available_talent)}")
    print(f"  Need {num_cards} cards for this turn")
    
    if len(available_talent) >= num_cards - 1:
        cards = random.sample(available_talent, num_cards - 1)
    else:
        cards = available_talent.copy()
    
    # Add a producer (generated on the fly)
    producer_names = ['Avi Goldstein', 'Rachel Chen', 'Marcus Thompson', 'Sofia Rodriguez', 
                      'David Kim', 'Emma Watson', 'James O\'Brien', 'Priya Patel']
    producer = generate_talent_stats('producer', random.choice(producer_names), is_producer=True)
    cards.append(producer)
    
    # Shuffle cards
    random.shuffle(cards)
    
    game_state['current_turn_cards'] = cards
    print(f"  Generated {len(cards)} cards for Turn {game_state['turn']}")
    for i, card in enumerate(cards):
        print(f"    Card {i}: {card['name']} ({card['role']})")

@socketio.on('select_card')
def handle_select_card(data):
    """Player selects a card (or passes)"""
    selection = data['index']  # Can be int or 'pass'
    player_name = game_state['players'][request.sid]['name']
    player = game_state['players'][request.sid]
    
    # Check affordability before allowing selection
    if selection != 'pass':
        # Validate card index
        if selection >= len(game_state['current_turn_cards']):
            emit('selection_error', {'message': 'Invalid card selection!'})
            return
            
        card = game_state['current_turn_cards'][selection]
        print(f"{player_name} attempting to select card {selection}: {card['name']} (${card['salary']}M) - Player has ${player['money']}M")
        
        if player['money'] < card['salary']:
            # Can't afford this card
            print(f"  -> BLOCKED: Cannot afford!")
            emit('selection_error', {'message': f"Can't afford {card['name']}! Need ${card['salary']}M but only have ${player['money']}M"})
            return
    
    game_state['player_selections'][request.sid] = selection
    
    if selection == 'pass':
        print(f"{player_name} passed")
    else:
        card = game_state['current_turn_cards'][selection]
        print(f"{player_name} selected {card['name']} (will pay ${card['salary']}M if won)")
    
    # Check if all players have selected
    if len(game_state['player_selections']) == len(game_state['players']):
        resolve_selections()
    else:
        # Just broadcast the selection update, don't change game state
        broadcast_game_state()

def resolve_selections():
    """Check for bidding wars and award cards"""
    selections = game_state['player_selections']
    
    print(f"\n=== Resolving Turn {game_state['turn']} ===")
    for sid, sel in selections.items():
        player_name = game_state['players'][sid]['name']
        if sel == 'pass':
            print(f"  {player_name}: PASS")
        else:
            card = game_state['current_turn_cards'][sel]
            print(f"  {player_name}: {card['name']} (card index {sel})")
    
    # Group players by their selection
    selection_groups = {}
    for sid, selection in selections.items():
        if selection != 'pass':
            if selection not in selection_groups:
                selection_groups[selection] = []
            selection_groups[selection].append(sid)
    
    # Check for bidding wars (multiple players picked same card)
    bidding_wars = {idx: players for idx, players in selection_groups.items() if len(players) > 1}
    
    if bidding_wars:
        # Start bidding war with first conflict
        card_index = list(bidding_wars.keys())[0]
        players_in_war = bidding_wars[card_index]
        game_state['bidding_war'] = {
            'card_index': card_index,
            'players': players_in_war,
            'bids': {}
        }
        game_state['phase'] = 'phase1_bidding'
        card = game_state['current_turn_cards'][card_index]
        print(f"\n💥 BIDDING WAR for {card['name']}!")
        print(f"   Players: {[game_state['players'][p]['name'] for p in players_in_war]}")
    else:
        # No conflicts, award cards directly
        print("\n✓ No conflicts, awarding cards...")
        for card_index, player_list in selection_groups.items():
            if len(player_list) == 1:
                award_card_to_player(player_list[0], card_index)
        
        # Move to next turn
        advance_turn()

def award_card_to_player(player_sid, card_index, extra_bid=0):
    """Give a card to a player and deduct cost"""
    card = game_state['current_turn_cards'][card_index]
    player = game_state['players'][player_sid]
    
    total_cost = card['salary'] + extra_bid
    
    print(f"  → Awarding {card['name']} to {player['name']}")
    print(f"     Cost: ${card['salary']}M + ${extra_bid}M bid = ${total_cost}M")
    print(f"     Player money before: ${player['money']}M")
    
    player['money'] -= total_cost
    
    print(f"     Player money after: ${player['money']}M")
    
    # Add card to player's roles
    if 'roles' not in player:
        player['roles'] = []
    player['roles'].append(card.copy())

def advance_turn():
    """Move to the next turn or phase"""
    game_state['turn'] += 1
    
    if game_state['turn'] <= 5:
        # Continue Winter production
        game_state['phase'] = 'phase1_production'
        start_new_turn()
        print(f"\n=== Starting Turn {game_state['turn']} ===\n")
    else:
        # Move to Spring packaging
        game_state['phase'] = 'phase1_packaging'
        print("\n=== Winter production complete! Time to package films for Spring release ===\n")
        
        # Debug: show what roles each player has
        for sid, player in game_state['players'].items():
            role_count = len(player.get('roles', []))
            print(f"  {player['name']} has {role_count} roles")
    
    broadcast_game_state()

@socketio.on('request_update')
def handle_request_update():
    """Player requests a game state update (for UI refresh)"""
    broadcast_game_state()

@socketio.on('greenlight_film')
def handle_greenlight_film(data):
    """Player greenlights a film package"""
    player = game_state['players'][request.sid]
    role_indices = data['roleIndices']
    title = data['title']
    teaser = data.get('teaser', '')
    
    # Validate indices
    if not player.get('roles'):
        return
    
    # Extract roles
    roles = [player['roles'][i] for i in role_indices if i < len(player['roles'])]
    
    # Validate package (1 producer, 1 writer, 1 director, 1+ stars)
    role_types = [r['role'] for r in roles]
    if ('producer' not in role_types or 'screenwriter' not in role_types or 
        'director' not in role_types or 'star' not in role_types):
        emit('package_error', {'message': 'Invalid package! Need Producer, Screenwriter, Director, and Star'})
        return
    
    # Calculate film stats
    total_heat = sum(r['heat'] for r in roles)
    avg_prestige = sum(r['prestige'] for r in roles) // len(roles)
    
    # Get genre and audience
    genre = next((r['genre'] for r in roles if r['role'] == 'producer'), 'Unknown')
    audience = next((r['audience'] for r in roles if r['role'] == 'screenwriter'), 'Unknown')
    
    film = {
        'title': title,
        'teaser': teaser,
        'roles': roles,
        'heat': total_heat,
        'prestige': avg_prestige,
        'genre': genre,
        'audience': audience
    }
    
    # Add to player's films
    if 'films' not in player:
        player['films'] = []
    player['films'].append(film)
    
    # Remove roles from player's available roles (in reverse order to preserve indices)
    for idx in sorted(role_indices, reverse=True):
        if idx < len(player['roles']):
            player['roles'].pop(idx)
    
    print(f"{player['name']} greenlit '{title}' - Heat: {total_heat}, Prestige: {avg_prestige}")
    broadcast_game_state()

@socketio.on('finish_packaging')
def handle_finish_packaging():
    """Player finishes packaging and releases remaining roles"""
    player = game_state['players'][request.sid]
    
    # Release remaining roles (get back half salary)
    if player.get('roles'):
        refund = sum(r['salary'] for r in player['roles']) // 2
        player['money'] += refund
        print(f"{player['name']} released {len(player['roles'])} roles for ${refund}M refund")
        player['roles'] = []
    
    player['spring_ready'] = True
    
    # Check if all players are ready
    if all(p.get('spring_ready', False) for p in game_state['players'].values()):
        game_state['phase'] = 'phase1_releases'
        print("\n=== All players ready! Moving to Spring releases ===\n")
    
    broadcast_game_state()
def handle_disconnect():
    if request.sid in game_state['players']:
        player_name = game_state['players'][request.sid]['name']
        del game_state['players'][request.sid]
        print(f'{player_name} left the game')
        broadcast_game_state()

def broadcast_game_state():
    socketio.emit('game_update', game_state)

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🎬 HOLLYWOOD MOGULS SERVER")
    print("="*50)
    print("\nHost view: http://localhost:8080")
    print("Players connect to: http://YOUR_LOCAL_IP:8080/player")
    print("\nTo find your local IP:")
    print("  Mac/Linux: ifconfig | grep inet")
    print("  Windows: ipconfig")
    print("="*50 + "\n")
    socketio.run(app, host='0.0.0.0', port=8080, debug=True)