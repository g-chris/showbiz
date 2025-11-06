// Player screen logic for Hollywood Moguls

const socket = io();
let myName = '';
let currentPackage = [];
let greenlitFilms = [];

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
        socket.emit('join_game', {name: myName});
    }
}

socket.on('joined', () => {
    showScreen('lobby-screen');
    document.getElementById('studioName').textContent = myName;
    document.getElementById('studioNameP1').textContent = myName;
    document.getElementById('studioNamePkg').textContent = myName;
    document.getElementById('studioNameRel').textContent = myName;
});

socket.on('selection_error', (data) => {
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
        
        // Pre-fill with default name
        const defaultName = getDefaultName(currentRole, currentCount);
        document.getElementById('talentName').value = defaultName;
        document.getElementById('talentName').select();
        document.getElementById('talentName').focus();
        
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
        showScreen('phase1-screen'); // Reuse same screen
        document.getElementById('year').textContent = data.year;
        document.getElementById('turnNum').textContent = `☀️ Summer Turn ${data.turn}`;
        
        console.log('Phase 2 - cards:', data.current_turn_cards);
        
        updateRoleInventory(myData.roles || [], 'roleInventory');
        renderProductionCards(data, myData);
        
    } else if (data.phase === 'phase1_production') {
        showScreen('phase1-screen');
        document.getElementById('year').textContent = data.year;
        document.getElementById('turnNum').textContent = `☃️ Winter Turn ${data.turn}`;
        
        console.log('Phase 1 - cards:', data.current_turn_cards);
        
        updateRoleInventory(myData.roles || [], 'roleInventory');
        renderProductionCards(data, myData);
        
    } else if (data.phase === 'phase2_production') {
        showScreen('phase1-screen'); // Reuse same screen
        document.getElementById('year').textContent = data.year;
        document.getElementById('turnNum').textContent = `☀️ Summer Turn ${data.turn}`;
        
        console.log('Phase 2 - cards:', data.current_turn_cards);
        
        updateRoleInventory(myData.roles || [], 'roleInventory');
        renderProductionCards(data, myData);
        
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
                <p>Salary: ${card.salary}M ${!canAfford ? '❌ TOO EXPENSIVE' : ''}</p>
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
    
    updateRoleInventory(availableRoles, 'pkgRoleInventory');
    
    const rolesDiv = document.getElementById('available-roles');
    rolesDiv.innerHTML = '';
    
    if (availableRoles.length === 0) {
        rolesDiv.innerHTML = '<p><em>No roles available</em></p>';
    } else {
        availableRoles.forEach((role, index) => {
            const inPackage = currentPackage.includes(index);
            rolesDiv.innerHTML += `
                <div class="info-box" style="margin: 10px 0; ${inPackage ? 'border: 2px solid #e50914;' : ''}">
                    <strong>${role.name}</strong> (${role.role.toUpperCase()})<br>
                    Heat: ${role.heat_bucket} | Prestige: ${role.prestige_bucket}<br>
                    Salary: $${role.salary}M<br>
                    ${role.genre ? `Genre: ${role.genre}<br>` : ''}
                    ${role.audience ? `Audience: ${role.audience}<br>` : ''}
                    <button onclick="toggleRole(${index})">
                        ${inPackage ? 'Remove from Film' : 'Add to Film'}
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
        currentPackage = currentPackage.filter(i => i !== index);
    } else {
        currentPackage.push(index);
    }
    socket.emit('request_update');
}

function updatePackageDisplay(availableRoles) {
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

function updateReleasesView(gameData, playerData) {
    // Show player's own films
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
    
    // Show all films from all players
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
    
    // Sort by box office
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
}

function continueGame() {
    alert('Next phase not yet implemented!');
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