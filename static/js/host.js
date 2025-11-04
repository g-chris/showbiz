// Host screen logic for Hollywood Moguls

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
        detailsDiv.innerHTML = `<p>Year ${state.year}, Turn ${state.turn} of 5</p>`;
        contentDiv.innerHTML = '<h3>Available Roles This Turn:</h3>';
        
        state.current_turn_cards.forEach((card, i) => {
            contentDiv.innerHTML += `
                <div class="talent-card">
                    <strong>${card.name}</strong> (${card.role.toUpperCase()})<br>
                    Heat: ${card.heat_bucket} | Prestige: ${card.prestige_bucket}<br>
                    Salary: $${card.salary}M<br>
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
            const selectionInfo = state.player_selections[sid] === 'pass' ? ' (Passed)' : '';
            contentDiv.innerHTML += `<p>${selected} ${player.name}${selectionInfo}</p>`;
        }
        contentDiv.innerHTML += `</div><p>${numSelections}/${numPlayers} players have selected</p>`;
    } else if (state.phase === 'phase1_packaging') {
        detailsDiv.innerHTML = '<p>Spring Packaging - Players assembling their films...</p>';
        contentDiv.innerHTML = '<h3>Player Progress:</h3><div class="submissions">';
        
        for (let [sid, player] of Object.entries(state.players)) {
            const ready = player.spring_ready ? '✅' : '⏳';
            const roleCount = player.roles ? player.roles.length : 0;
            const filmCount = player.films ? player.films.length : 0;
            contentDiv.innerHTML += `<p>${ready} ${player.name} - ${roleCount} roles, ${filmCount} films</p>`;
        }
        contentDiv.innerHTML += '</div>';
    } else if (state.phase === 'phase1_complete') {
        detailsDiv.innerHTML = '<p>Winter production complete! Ready for Spring releases.</p>';
        contentDiv.innerHTML = '';
    }
}

function startPhase0() {
    socket.emit('start_phase0');
}

function startPhase1() {
    socket.emit('start_phase1');
}