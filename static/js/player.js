// Player screen logic for Hollywood Moguls

const socket = io();
let myName = '';
let currentPackage = [];
let greenlitFilms = [];
let currentBidAmount = 0;

// Check for saved session on page load
const savedPlayerName = sessionStorage.getItem('playerName');
if (savedPlayerName) {
    myName = savedPlayerName;
    console.log('📱 Found saved session for:', myName);
}

// Configure Socket.IO reconnection
socket.io.opts.reconnection = true;
socket.io.opts.reconnectionAttempts = Infinity;  // Keep trying forever
socket.io.opts.reconnectionDelay = 1000;         // Start with 1s
socket.io.opts.reconnectionDelayMax = 5000;      // Max 5s between attempts
socket.io.opts.timeout = 20000;                  // 20s timeout

// Connection status function
function updateConnectionStatus(status, message) {
    // Updates the visual indicator
}

// Socket.IO reconnection handlers
socket.on('connect', () => {
    // Auto-rejoin if we have saved name
    if (myName && myName !== '') {
        socket.emit('join_game', {name: myName});
    }
});

socket.on('disconnect', (reason) => {
    updateConnectionStatus('disconnected', 'Connection lost...');
});

socket.on('reconnect', (attemptNumber) => {
    updateConnectionStatus('connected');
});

socket.on('reconnect_attempt', (attemptNumber) => {
    updateConnectionStatus('disconnected', `Reconnecting (${attemptNumber})...`);
});

// Page visibility detection
document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !socket.connected) {
        // Phone woke up but we're disconnected - reconnect!
        socket.connect();
    }
});

// Heartbeat every 30 seconds
setInterval(() => {
    if (socket.connected && myName) {
        socket.emit('heartbeat', {name: myName});
    }
}, 30000);


// Default names for pre-filling
const DEFAULT_NAMES = {
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
};

function joinGame() {
    myName = document.getElementById('playerName').value.trim();
    if (myName) {
        // Save to session storage
        sessionStorage.setItem('playerName', myName);
        socket.emit('join_game', {name: myName});
    }
}

socket.on('joined', () => {
    console.log('✅ Successfully joined game as:', myName);
    
    // Save to session storage
    sessionStorage.setItem('playerName', myName);

    showScreen('lobby-screen');
    document.getElementById('studioName').textContent = myName;
    document.getElementById('studioNameP1').textContent = myName;
    document.getElementById('studioNamePkg').textContent = myName;
    document.getElementById('studioNameRel').textContent = myName;

    // Update connection status
    updateConnectionStatus('connected');

});

socket.on('selection_error', (data) => {
    alert(data.message);
});

socket.on('package_error', (data) => {
    alert(data.message);
});

socket.on('vote_error', (data) => {
    alert(data.message);
});

socket.on('game_update', (data) => {
    const myData = data.players[socket.id];
    if (!myData) return;
    
    // Update money displays
    document.getElementById('lobbyMoney').textContent = myData.money;
    document.getElementById('p1Money').textContent = myData.money;
    document.getElementById('pkgMoney').textContent = myData.money;
    document.getElementById('relMoney').textContent = myData.money;
    document.getElementById('biddingMoney').textContent = myData.money;  
    document.getElementById('resultsMoney').textContent = myData.money;
    document.getElementById('relScore').textContent = myData.score;
    
    // Update greenlit films from server
    if (myData.films) {
        greenlitFilms = myData.films;
    }
    
    // Handle phase transitions
    if (data.phase === 'phase0_naming') {
        showScreen('naming-screen');
        
        const myProg = data.naming_progress.submissions[socket.id];
        if (!myProg) return;
        
        if (myProg.complete) {
            document.getElementById('roleType').textContent = 'All Done!';
            document.getElementById('roleProgress').textContent = 'Waiting for other players...';
            document.getElementById('submit-btn').disabled = true;
            document.getElementById('talentName').disabled = true;
            return;
        }
        
        // Determine what to name next
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
        document.getElementById('roleProgress').textContent = `${currentCount + 1} of ${maxCount}`;
        document.getElementById('submit-btn').disabled = false;
        document.getElementById('talentName').disabled = false;
        
        // ONLY pre-fill with default name if this is a NEW role type
        // (prevents resetting player's input when other players submit)
        const roleKey = `${currentRole}_${currentCount}`;
        if (window.lastNamingRole !== roleKey) {
            const defaultName = getDefaultName(currentRole, currentCount);
            document.getElementById('talentName').value = defaultName;
            document.getElementById('talentName').select();
            document.getElementById('talentName').focus();
            window.lastNamingRole = roleKey;
            console.log('🆕 New role to name - pre-filled with:', defaultName);
        } else {
            console.log('✅ Same role - preserving user input');
        }
        
    } else if (data.phase === 'phase0_complete') {
        showScreen('phase0-complete-screen');
        
    } else if (data.phase === 'phase1_production') {
        showScreen('phase1-screen');
        document.getElementById('year').textContent = data.year;
        document.getElementById('turnNum').textContent = `☃️ Winter Turn ${data.turn}`;
        
        console.log('Phase 1 - cards:', data.current_turn_cards);
        
        updateRoleInventory(myData.roles || [], 'roleInventory');
        renderProductionCards(data, myData);
        
    } else if (data.phase === 'phase2_production') {
        showScreen('phase1-screen');
        document.getElementById('year').textContent = data.year;
        document.getElementById('turnNum').textContent = `☀️ Summer Turn ${data.turn}`;
        
        console.log('Phase 2 - cards:', data.current_turn_cards);
        
        updateRoleInventory(myData.roles || [], 'roleInventory');
        renderProductionCards(data, myData);
        
    } else if (data.phase === 'phase1_bidding' || data.phase === 'phase2_bidding') {
        console.log('🔥 BIDDING PHASE DETECTED!', data.phase);
        console.log('Bidding war data:', data.bidding_war);
        showScreen('bidding-screen');
        try {
            updateBiddingView(data, myData);
        } catch (error) {
            console.error('❌ Error in updateBiddingView:', error);
        }
        
    } else if (data.phase === 'phase1_bidding_results' || data.phase === 'phase2_bidding_results') {
        console.log('📊 BIDDING RESULTS PHASE!', data.phase);
        showScreen('bidding-results-screen');
        try {
            updateBiddingResultsView(data, myData);
        } catch (error) {
            console.error('❌ Error in updateBiddingResultsView:', error);
        }
    
    } else if (data.phase === 'phase1_packaging') {
        showScreen('packaging-screen');
        console.log('Spring Packaging - my roles:', myData.roles);
        updatePackagingView(data, myData);
    } else if (data.phase === 'phase2_packaging') {
        showScreen('packaging-screen');
        console.log('Holiday Packaging - my roles:', myData.roles);
        updatePackagingView(data, myData);
    } else if (data.phase === 'phase1_releases') {
        showScreen('releases-screen');
        updateReleasesView(data, myData, 'Spring');
    } else if (data.phase === 'phase2_releases') {
        showScreen('releases-screen');
        updateReleasesView(data, myData, 'Holiday');
    } else if (data.phase === 'awards_voting') {
        showScreen('awards-screen');
        updateAwardsVotingView(data, myData);
    } else if (data.phase === 'awards_results') {
        showScreen('awards-results-screen');
        updateAwardsResultsView(data, myData);
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

function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');
}

function getDefaultName(roleType, count) {
    const roleNames = DEFAULT_NAMES[roleType] || [];
    return count < roleNames.length ? roleNames[count] : '';
}

function updateRoleInventory(roles, elementId) {
    const counts = {producer: 0, screenwriter: 0, director: 0, star: 0};
    roles.forEach(r => {
        if (counts[r.role] !== undefined) counts[r.role]++;
    });
    
    const inv = document.getElementById(elementId);
    inv.innerHTML = `
        <strong>Roles:</strong> 
        📋 ${counts.producer} Producer | 
        ✍️ ${counts.screenwriter} Writer | 
        🎬 ${counts.director} Director | 
        ⭐ ${counts.star} Star
    `;
}

function renderProductionCards(data, myData) {
    const cardsArea = document.getElementById('cards-area');
    cardsArea.innerHTML = '';
    
    if (!data.current_turn_cards || data.current_turn_cards.length === 0) {
        cardsArea.innerHTML = '<p style="color: red;">ERROR: No cards available!</p>';
        return;
    }
    
    cardsArea.innerHTML = '<h3>Select a Role:</h3>';
    
    data.current_turn_cards.forEach((card, index) => {
        const selected = data.player_selections[socket.id] === index;
        const disabled = data.player_selections[socket.id] !== undefined;
        const canAfford = myData.money >= card.salary;
        
        cardsArea.innerHTML += `
            <div class="info-box" style="margin: 10px 0; ${selected ? 'border: 2px solid #e50914;' : ''} ${!canAfford ? 'opacity: 0.5;' : ''}">
                <h3>${card.name}</h3>
                <p><strong>${card.role.toUpperCase()}</strong></p>
                <p>Heat: ${card.heat_bucket} | Prestige: ${card.prestige_bucket}</p>
                <p>Salary: $${card.salary}M ${!canAfford ? '❌ TOO EXPENSIVE' : ''}</p>
                ${card.genre ? `<p>Genre: ${card.genre}</p>` : ''}
                ${card.audience ? `<p>Audience: ${card.audience}</p>` : ''}
                <button onclick="selectCard(${index})" ${disabled || !canAfford ? 'disabled' : ''}>
                    ${selected ? 'Selected ✓' : canAfford ? 'Select' : 'Cannot Afford'}
                </button>
            </div>
        `;
    });
    
    const passDisabled = data.player_selections[socket.id] !== undefined;
    const passSelected = data.player_selections[socket.id] === 'pass';
    cardsArea.innerHTML += `
        <button onclick="selectPass()" ${passDisabled ? 'disabled' : ''} 
                style="background: #666; margin-top: 10px;">
            ${passSelected ? 'Passed ✓' : 'Pass This Turn'}
        </button>
    `;
    
    const statusDiv = document.getElementById('selection-status');
    if (data.player_selections[socket.id] !== undefined) {
        statusDiv.innerHTML = '<p style="color: #e50914;">✓ Selection made! Waiting for other players...</p>';
    } else {
        statusDiv.innerHTML = '';
    }
}

function updatePackagingView(gameData, playerData) {
    const availableRoles = playerData.roles || [];
    const noNameTalent = gameData.no_name_talent || {};
    
    // DEBUG: Log what we're receiving
    console.log('=== PACKAGING DEBUG ===');
    console.log('Game data:', gameData);
    console.log('No-name talent:', noNameTalent);
    console.log('No-name talent keys:', Object.keys(noNameTalent));
    console.log('No-name talent values:', Object.values(noNameTalent));
    
    updateRoleInventory(availableRoles, 'pkgRoleInventory');
    
    const rolesDiv = document.getElementById('available-roles');
    rolesDiv.innerHTML = '';
    
    // Show no-name talent first (if available)
    if (Object.keys(noNameTalent).length > 0) {
        rolesDiv.innerHTML += '<h4 style="color: #888;">Budget Indie Talent (Always Available):</h4>';
        
        // Convert no-name talent to array with special negative indices
        Object.values(noNameTalent).forEach((role, idx) => {
            const specialIndex = -(idx + 1);
            const inPackage = currentPackage.includes(specialIndex);
            
            rolesDiv.innerHTML += `
                <div class="info-box" style="margin: 10px 0; border: 1px dashed #666; ${inPackage ? 'border: 2px solid #e50914;' : ''}">
                    <strong>${role.name}</strong> (${role.role.toUpperCase()})<br>
                    Heat: ${role.heat_bucket} | Prestige: ${role.prestige_bucket}<br>
                    Salary: ${role.salary}M<br>
                    ${role.genre ? `Genre: ${role.genre}<br>` : ''}
                    ${role.audience ? `Audience: ${role.audience}<br>` : ''}
                    <button onclick="toggleRole(${specialIndex})">
                        ${inPackage ? 'Remove from Film' : 'Add to Film'}
                    </button>
                </div>
            `;
        });
        
        rolesDiv.innerHTML += '<h4 style="margin-top: 20px;">Your Purchased Talent:</h4>';
    }
    
    // Show purchased roles
    if (availableRoles.length === 0) {
        rolesDiv.innerHTML += '<p><em>No purchased roles (use budget indie talent above)</em></p>';
    } else {
        availableRoles.forEach((role, index) => {
            const inPackage = currentPackage.includes(index);
            rolesDiv.innerHTML += `
                <div class="info-box" style="margin: 10px 0; ${inPackage ? 'border: 2px solid #e50914;' : ''}">
                    <strong>${role.name}</strong> (${role.role.toUpperCase()})<br>
                    Heat: ${role.heat_bucket} | Prestige: ${role.prestige_bucket}<br>
                    Salary: ${role.salary}M<br>
                    ${role.genre ? `Genre: ${role.genre}<br>` : ''}
                    ${role.audience ? `Audience: ${role.audience}<br>` : ''}
                    <button onclick="toggleRole(${index})">
                        ${inPackage ? 'Remove from Film' : 'Add to Film'}
                    </button>
                </div>
            `;
        });
    }
    
    updatePackageDisplay(availableRoles, noNameTalent);
    updateGreenlitDisplay();
}

function toggleRole(index) {
    if (currentPackage.includes(index)) {
        currentPackage = currentPackage.filter(i => i !== index);
    } else {
        currentPackage.push(index);
    }
    socket.emit('request_update');
}

function updatePackageDisplay(availableRoles, noNameTalent) {
    const packageDiv = document.getElementById('current-package');
    const actionsDiv = document.getElementById('package-actions');
    
    if (currentPackage.length === 0) {
        packageDiv.innerHTML = '<p><em>Select roles below to add to your film...</em></p>';
        actionsDiv.style.display = 'none';
        return;
    }
    
    let hasProducer = false, hasWriter = false, hasDirector = false, hasStar = false;
    let totalHeat = 0, totalPrestige = 0, roleCount = 0;
    
    packageDiv.innerHTML = '<h4>Roles in this film:</h4>';
    currentPackage.forEach(idx => {
        let role;
        
        if (idx < 0) {
            const noNameArray = Object.values(noNameTalent);
            role = noNameArray[Math.abs(idx) - 1];
        } else {
            role = availableRoles[idx];
        }
        
        if (!role) return;
        
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

function updateReleasesView(gameData, playerData, seasonName) {
    const continueBtn = document.getElementById('continue-btn');
    if (seasonName === 'Spring') {
        continueBtn.textContent = 'Continue to Summer Production ☀️';
        continueBtn.onclick = () => socket.emit('continue_to_summer');
    } else {
        continueBtn.textContent = 'Continue to Award Season 🏆';
        continueBtn.onclick = () => socket.emit('start_awards');
    }
    
    const myFilmsDiv = document.getElementById('my-films');
    const myFilms = playerData.films || [];
    
    if (myFilms.length === 0) {
        myFilmsDiv.innerHTML = '<p><em>You didn\'t release any films this season</em></p>';
    } else {
        myFilmsDiv.innerHTML = '';
        myFilms.forEach(film => {
            const performance = film.box_office > 100 ? '🔥 Hit!' : film.box_office > 50 ? '✓ Success' : '📉 Modest';
            myFilmsDiv.innerHTML += `
                <div class="info-box" style="border: 2px solid ${film.box_office > 100 ? '#4CAF50' : '#ff9800'}; margin: 10px 0;">
                    <h3 style="color: #e50914; margin-top: 0;">${film.title}</h3>
                    <p style="font-style: italic;">"${film.teaser || 'No teaser'}"</p>
                    <p><strong>Heat:</strong> ${film.heat} x ${film.multiplier} = <strong style="color: #4CAF50;">${film.box_office}M</strong></p>
                    <p>${performance}</p>
                </div>
            `;
        });
    }
    
    const allFilmsDiv = document.getElementById('all-films');
    allFilmsDiv.innerHTML = '';
    
    let allFilms = [];
    for (let [sid, player] of Object.entries(gameData.players)) {
        if (player.films) {
            player.films.forEach(film => {
                allFilms.push({
                    ...film,
                    studio: player.name
                });
            });
        }
    }
    
    allFilms.sort((a, b) => b.box_office - a.box_office);
    
    allFilms.forEach((film, index) => {
        const isMyFilm = film.studio === playerData.name;
        const ranking = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : `#${index + 1}`;
        
        allFilmsDiv.innerHTML += `
            <div class="info-box" style="margin: 10px 0; ${isMyFilm ? 'border: 2px solid #e50914;' : ''}">
                <p style="margin: 0;"><strong>${ranking} ${film.title}</strong> (${film.studio})</p>
                <p style="margin: 5px 0; color: #4CAF50;"><strong>${film.box_office}M</strong></p>
            </div>
        `;
    });
    
    // Show ready status
    const statusDiv = document.getElementById('releases-ready-status');
    const readyFlag = seasonName === 'Spring' ? 'spring_releases_ready' : 'holiday_releases_ready';
    const readyCount = Object.values(gameData.players).filter(p => p[readyFlag]).length;
    const totalCount = Object.keys(gameData.players).length;
    const imReady = playerData[readyFlag];
    
    if (imReady) {
        statusDiv.innerHTML = `<p style="color: #4CAF50; font-size: 18px;">✓ You're ready! Waiting for others... (${readyCount}/${totalCount})</p>`;
        continueBtn.disabled = true;
    } else {
        // Always re-enable the button if player hasn't clicked yet
        continueBtn.disabled = false;
        if (readyCount > 0) {
            statusDiv.innerHTML = `<p style="color: #aaa; font-size: 16px;">${readyCount}/${totalCount} players ready</p>`;
        } else {
            statusDiv.innerHTML = '';
        }
    }
}

function continueToSummer() {
    socket.emit('continue_to_summer');
}

function continueToAwards() {
    socket.emit('start_awards');
}

function updateAwardsVotingView(gameData, playerData) {
    const currentCat = gameData.awards.current_category;
    const category = gameData.awards.categories[currentCat];
    
    document.getElementById('awardCategory').textContent = category.name;
    
    const nomineesArea = document.getElementById('nominees-area');
    nomineesArea.innerHTML = '';
    
    const myStudio = playerData.name;
    const hasVoted = category.votes[socket.id] !== undefined;
    
    category.nominees.forEach((film, index) => {
        const isMyFilm = film.studio === myStudio;
        const isSelected = category.votes[socket.id] === index;
        
        nomineesArea.innerHTML += `
            <div class="info-box" style="margin: 10px 0; ${isSelected ? 'border: 2px solid #FFD700;' : ''} ${isMyFilm ? 'opacity: 0.5;' : ''}">
                <h3 style="color: #FFD700;">${film.title}</h3>
                <p><strong>Studio:</strong> ${film.studio} ${isMyFilm ? '(YOUR FILM)' : ''}</p>
                <p><strong>Prestige:</strong> ${film.prestige}</p>
                <p style="font-style: italic;">"${film.teaser}"</p>
                <button onclick="voteForNominee(${index})" ${hasVoted || isMyFilm ? 'disabled' : ''}>
                    ${isSelected ? 'Voted ✓' : isMyFilm ? 'Cannot Vote' : 'Vote for This Film'}
                </button>
            </div>
        `;
    });
    
    const statusDiv = document.getElementById('vote-status');
    if (hasVoted) {
        const votedFilm = category.nominees[category.votes[socket.id]];
        statusDiv.innerHTML = `<p style="color: #FFD700; font-size: 18px;">✓ You voted for: <strong>${votedFilm.title}</strong></p><p>Waiting for other players...</p>`;
    } else {
        statusDiv.innerHTML = '';
    }
}

function voteForNominee(index) {
    socket.emit('vote_for_nominee', {nominee_index: index});
}

function updateAwardsResultsView(gameData, playerData) {
    const currentCat = gameData.awards.current_category;
    const category = gameData.awards.categories[currentCat];
    const winner = category.winner;
    
    const winnerDiv = document.getElementById('winner-announcement');
    winnerDiv.innerHTML = `
        <div style="text-align: center; padding: 30px;">
            <h1 style="color: #FFD700; font-size: 64px; margin: 0;">🏆</h1>
            <h2 style="color: #FFD700; margin: 10px 0;">${category.name}</h2>
            <h1 style="color: #e50914; margin: 20px 0; font-size: 32px;">${winner.title}</h1>
            <p style="font-size: 20px;"><strong>${winner.studio}</strong></p>
            <p style="font-size: 16px; color: #aaa; font-style: italic;">"${winner.teaser}"</p>
            <p style="font-size: 18px; margin-top: 20px; color: #4CAF50;">+${category.points_value} points!</p>
        </div>
    `;
    
    const standingsDiv = document.getElementById('final-standings');
    standingsDiv.innerHTML = '<h2>Final Standings:</h2>';
    
    const playerArray = Object.entries(gameData.players).map(([sid, p]) => p);
    playerArray.sort((a, b) => b.score - a.score);
    
    playerArray.forEach((player, index) => {
        const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : '';
        const isMe = player.name === playerData.name;
        
        standingsDiv.innerHTML += `
            <div class="info-box" style="margin: 10px 0; ${isMe ? 'border: 2px solid #e50914;' : ''}">
                <p style="font-size: 20px; margin: 0;">${medal} <strong>${player.name}</strong></p>
                <p style="margin: 5px 0;">${player.score} points | ${player.films ? player.films.length : 0} films</p>
            </div>
        `;
    });
    
    // Show ready status
    const statusDiv = document.getElementById('awards-ready-status');
    const awardsBtn = document.getElementById('continue-awards-btn');
    const readyCount = Object.values(gameData.players).filter(p => p.awards_results_ready).length;
    const totalCount = Object.keys(gameData.players).length;
    const imReady = playerData.awards_results_ready;
    
    if (imReady) {
        statusDiv.innerHTML = `<p style="color: #4CAF50; font-size: 18px;">✓ You're ready! Waiting for others... (${readyCount}/${totalCount})</p>`;
        awardsBtn.disabled = true;
    } else {
        // Always re-enable the button if player hasn't clicked yet
        awardsBtn.disabled = false;
        if (readyCount > 0) {
            statusDiv.innerHTML = `<p style="color: #aaa; font-size: 16px;">${readyCount}/${totalCount} players ready</p>`;
        } else {
            statusDiv.innerHTML = '';
        }
    }
}

// ============================================================================
// BIDDING WAR FUNCTIONS
// ============================================================================

function updateBiddingView(gameData, playerData) {
    /**
     * Updates the bidding screen with the contested card info and bidding controls
     */

    console.log('🎯 updateBiddingView called');
    console.log('  - gameData.bidding_war:', gameData.bidding_war);
    console.log('  - playerData:', playerData);

    const biddingWar = gameData.bidding_war;
    
    if (!biddingWar || !biddingWar.active) {
        console.error('❌ No active bidding war!');
        return;
    }
    
     console.log('✅ Active bidding war confirmed');

    const cardData = biddingWar.card_data;
    const isParticipant = biddingWar.participants.includes(socket.id);
    const hasAlreadyBid = biddingWar.bids && biddingWar.bids[socket.id] !== undefined;
    
    // ALWAYS check if this is a new bidding war and reset bid amount
    const currentCard = biddingWar.card_index;
    if (window.lastBiddingCardIndex !== currentCard) {
        currentBidAmount = 0;
        window.lastBiddingCardIndex = currentCard;
        console.log('New bidding war detected - reset bid to $0M');
    }
    
    console.log('  - isParticipant:', isParticipant);
    console.log('  - hasAlreadyBid:', hasAlreadyBid);
    console.log('  - cardData:', cardData);
    console.log('  - currentBidAmount:', currentBidAmount);

     // Update budget display at top of screen
    document.getElementById('biddingMoney').textContent = playerData.money;


    // Display the contested card
    const contestedCard = document.getElementById('contested-card');
    contestedCard.innerHTML = `
        <h2 style="color: #e50914; margin: 10px 0; font-size: 28px;">${cardData.name}</h2>
        <p style="font-size: 18px; margin: 5px 0;"><strong>${cardData.role.toUpperCase()}</strong></p>
        <p style="margin: 5px 0;">Heat: ${cardData.heat_bucket} | Prestige: ${cardData.prestige_bucket}</p>
        <p style="font-size: 20px; margin: 10px 0; color: #4CAF50;">
            <strong>Base Salary: $${cardData.salary}M</strong>
        </p>
        ${cardData.genre ? `<p>Genre: ${cardData.genre}</p>` : ''}
        ${cardData.audience ? `<p>Audience: ${cardData.audience}</p>` : ''}
    `;
    
    // Set base salary
    document.getElementById('baseSalary').textContent = cardData.salary;
    
    if (!isParticipant) {
        // Not participating in this bidding war
        document.getElementById('bid-status').innerHTML = `
            <div class="info-box" style="background: #2a2a2a; text-align: center;">
                <p style="font-size: 18px; color: #aaa;">
                    You're not involved in this bidding war.
                </p>
                <p style="margin-top: 10px;">Waiting for other players to bid...</p>
            </div>
        `;
        document.getElementById('submit-bid-btn').disabled = true;
        document.getElementById('submit-bid-btn').style.display = 'none';
        
        // Hide bid controls
        document.querySelector('[onclick="decreaseBid()"]').style.display = 'none';
        document.querySelector('[onclick="increaseBid()"]').style.display = 'none';
        
    } else if (hasAlreadyBid) {
        // Already submitted bid
        const myBid = biddingWar.bids[socket.id];
        document.getElementById('bid-status').innerHTML = `
            <div class="info-box" style="background: #1a1a1a; border: 2px solid #4CAF50; text-align: center;">
                <p style="font-size: 20px; color: #4CAF50;">✓ Bid Submitted!</p>
                <p style="font-size: 24px; margin: 10px 0;">$${myBid}M extra</p>
                <p style="color: #aaa;">Waiting for other players...</p>
            </div>
        `;
        document.getElementById('submit-bid-btn').disabled = true;
        document.getElementById('submit-bid-btn').style.display = 'none';
        
        // Hide bid controls
        document.querySelector('[onclick="decreaseBid()"]').style.display = 'none';
        document.querySelector('[onclick="increaseBid()"]').style.display = 'none';
        document.getElementById('currentBid').parentElement.parentElement.style.display = 'none';
        
    } else {
        // Can bid - display controls
        updateBidDisplay(cardData.salary, playerData.money);
        document.getElementById('submit-bid-btn').disabled = false;
        document.getElementById('submit-bid-btn').style.display = 'block';
        document.getElementById('bid-status').innerHTML = '';
        
        // Show bid controls
        document.querySelector('[onclick="decreaseBid()"]').style.display = 'inline-block';
        document.querySelector('[onclick="increaseBid()"]').style.display = 'inline-block';
        document.getElementById('currentBid').parentElement.parentElement.style.display = 'flex';
    }
}

function updateBidDisplay(baseSalary, playerMoney) {
    /**
     * Updates the bid display elements (current bid, total cost, affordability)
     */
    document.getElementById('currentBid').textContent = currentBidAmount;
    
    const totalCost = baseSalary + currentBidAmount;
    document.getElementById('totalCost').textContent = totalCost;
    
    // Check affordability
    const canAfford = playerMoney >= totalCost;
    const warning = document.getElementById('affordabilityWarning');
    const submitBtn = document.getElementById('submit-bid-btn');
    
    if (!canAfford) {
        warning.style.display = 'block';
        submitBtn.disabled = true;
        submitBtn.style.opacity = '0.5';
    } else {
        warning.style.display = 'none';
        submitBtn.disabled = false;
        submitBtn.style.opacity = '1';
    }
}

function increaseBid() {
    /**
     * Increase bid by $1M
     */
    currentBidAmount++;
    const baseSalary = parseInt(document.getElementById('baseSalary').textContent);
    const playerMoney = parseInt(document.getElementById('biddingMoney').textContent);
    updateBidDisplay(baseSalary, playerMoney);
}

function decreaseBid() {
    /**
     * Decrease bid by $1M (minimum $0M)
     */
    if (currentBidAmount > 0) {
        currentBidAmount--;
        const baseSalary = parseInt(document.getElementById('baseSalary').textContent);
        const playerMoney = parseInt(document.getElementById('biddingMoney').textContent);
        updateBidDisplay(baseSalary, playerMoney);
    }
}

function submitBid() {
    /**
     * Submit the current bid to the server
     */
    console.log(`Submitting bid: $${currentBidAmount}M`);
    socket.emit('submit_bid', {bid_amount: currentBidAmount});
}

function updateBiddingResultsView(gameData, playerData) {
    /**
     * Updates the results screen showing who won the bidding war
     */
    const biddingWar = gameData.bidding_war;
    
    if (!biddingWar) {
        return;
    }
    
    // Update budget display
    document.getElementById('resultsMoney').textContent = playerData.money;

    const cardData = biddingWar.card_data;
    const bids = biddingWar.bids || {};
    const participants = biddingWar.participants || [];
    
    // Display the contested role name
    document.getElementById('contestedRoleName').textContent = cardData.name;
    
    // Display all bids
    const allBidsDiv = document.getElementById('all-bids');
    allBidsDiv.innerHTML = '<h3 style="margin-top: 0;">All Bids:</h3>';
    
    // Sort bids by amount (highest first)
    const sortedBids = participants
        .map(sid => ({
            sid: sid,
            name: gameData.players[sid].name,
            bid: bids[sid] || 0
        }))
        .sort((a, b) => b.bid - a.bid);
    
    sortedBids.forEach((bidder, index) => {
        const isMe = bidder.sid === socket.id;
        const isHighest = index === 0;
        const borderColor = isMe ? '#e50914' : (isHighest ? '#4CAF50' : '#666');
        
        allBidsDiv.innerHTML += `
            <div class="info-box" style="margin: 10px 0; border: 2px solid ${borderColor};">
                <p style="font-size: 18px; margin: 0;">
                    <strong>${bidder.name}</strong> ${isMe ? '(You)' : ''}
                </p>
                <p style="font-size: 24px; color: ${isHighest ? '#4CAF50' : '#fff'}; margin: 5px 0;">
                    $${bidder.bid}M
                </p>
            </div>
        `;
    });
    
    // Determine winner
    const maxBid = Math.max(...Object.values(bids));
    const winners = participants.filter(sid => bids[sid] === maxBid);
    
    const winnerBox = document.getElementById('winner-announcement-box');
    
    if (winners.length > 1) {
        // TIE - Nobody gets it!
        winnerBox.innerHTML = `
            <h1 style="font-size: 48px; margin: 20px 0;">💔</h1>
            <h2 style="color: #ff9800; margin: 10px 0;">TIE!</h2>
            <p style="font-size: 20px; color: #aaa; margin: 10px 0;">
                Multiple studios bid $${maxBid}M
            </p>
            <p style="font-size: 18px; color: #aaa;">
                ${cardData.name} is disgusted by studio politicking!
            </p>
            <p style="font-size: 16px; color: #888; margin-top: 15px;">
                Nobody gets the role. All bids refunded.
            </p>
        `;
    } else {
        // We have a winner!
        const winnerSid = winners[0];
        const winnerName = gameData.players[winnerSid].name;
        const isYou = winnerSid === socket.id;
        
        winnerBox.innerHTML = `
            <h1 style="font-size: 64px; margin: 20px 0;">🏆</h1>
            <h2 style="color: #4CAF50; margin: 10px 0;">WINNER!</h2>
            <p style="font-size: 28px; color: ${isYou ? '#e50914' : '#fff'}; margin: 10px 0;">
                <strong>${winnerName}</strong> ${isYou ? '(You!)' : ''}
            </p>
            <p style="font-size: 20px; color: #aaa; margin: 10px 0;">
                Winning bid: <span style="color: #4CAF50;">$${maxBid}M</span>
            </p>
            <p style="font-size: 18px; color: #aaa;">
                Total cost: $${cardData.salary + maxBid}M
            </p>
            ${isYou ? '<p style="font-size: 16px; color: #4CAF50; margin-top: 15px;">✓ ' + cardData.name + ' added to your roster!</p>' : ''}
        `;
    }
    
    // Show ready status
    const statusDiv = document.getElementById('bidding-ready-status');
    const biddingBtn = document.querySelector('#bidding-results-screen button');
    const readyCount = Object.values(gameData.players).filter(p => p.bidding_results_ready).length;
    const totalCount = Object.keys(gameData.players).length;
    const imReady = playerData.bidding_results_ready;
    
    if (imReady) {
        statusDiv.innerHTML = `<p style="color: #4CAF50; font-size: 18px;">✓ You're ready! Waiting for others... (${readyCount}/${totalCount})</p>`;
        biddingBtn.disabled = true;
    } else {
        // Always re-enable the button if player hasn't clicked yet
        biddingBtn.disabled = false;
        if (readyCount > 0) {
            statusDiv.innerHTML = `<p style="color: #aaa; font-size: 16px;">${readyCount}/${totalCount} players ready</p>`;
        } else {
            statusDiv.innerHTML = '';
        }
    }
}

function continueAfterBidding() {
    /**
     * Signal to server that we're ready to continue after viewing results
     */
    console.log('Continuing after bidding war results');
    socket.emit('continue_after_bidding');
}

function continueFromAwards() {
    /**
     * Signal to server that we're ready to continue from awards results
     */
    console.log('Continuing from awards results');
    socket.emit('continue_from_awards');
}

document.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        if (document.getElementById('join-screen').classList.contains('active')) {
            joinGame();
        } else if (document.getElementById('naming-screen').classList.contains('active')) {
            submitName();
        }
    }
});