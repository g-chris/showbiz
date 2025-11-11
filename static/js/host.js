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
        detailsDiv.innerHTML = `<p>☃️ Winter - Year ${state.year}, Turn ${state.turn} of 5</p>`;
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
    } else if (state.phase === 'phase1_bidding' || state.phase === 'phase1_bidding_results') {
        const bw = state.bidding_war;
        const isResults = state.phase === 'phase1_bidding_results';
        
        detailsDiv.innerHTML = `<p>💥 Winter BIDDING WAR - Turn ${state.turn} of 5</p>`;
        
        if (bw && bw.card_data) {
            const card = bw.card_data;
            contentDiv.innerHTML = `
                <div style="background: #8B0000; padding: 20px; border-radius: 10px; margin: 20px 0;">
                    <h2 style="color: #FFD700; text-align: center; margin: 0;">💥 BIDDING WAR 💥</h2>
                </div>
                
                <div class="talent-card" style="border: 3px solid #FFD700; background: #2a2a2a;">
                    <h2 style="color: #FFD700; margin-top: 0;">CONTESTED ROLE:</h2>
                    <h3>${card.name}</h3>
                    <p><strong>Role:</strong> ${card.role.toUpperCase()}</p>
                    <p><strong>Heat:</strong> ${card.heat_bucket} | <strong>Prestige:</strong> ${card.prestige_bucket}</p>
                    <p><strong>Base Salary:</strong> $${card.salary}M</p>
                    ${card.genre ? `<p><strong>Genre:</strong> ${card.genre}</p>` : ''}
                    ${card.audience ? `<p><strong>Audience:</strong> ${card.audience}</p>` : ''}
                </div>
                
                <h3 style="margin-top: 30px;">Participants:</h3>
                <div class="submissions">
            `;
            
            bw.participants.forEach(sid => {
                const player = state.players[sid];
                const hasBid = bw.bids[sid] !== undefined;
                const status = hasBid ? '✓ Bid Submitted' : '⏳ Bidding...';
                
                contentDiv.innerHTML += `
                    <div class="player-card" style="display: inline-block; margin: 10px;">
                        <h3>${player.name}</h3>
                        <p>💰 Budget: $${player.money}M</p>
                        <p>${status}</p>
                    </div>
                `;
            });
            
            contentDiv.innerHTML += '</div>';
            
            const numBids = Object.keys(bw.bids).length;
            const numParticipants = bw.participants.length;
            contentDiv.innerHTML += `<p style="text-align: center; font-size: 18px; margin-top: 20px;">
                ${numBids} of ${numParticipants} players have bid
            </p>`;
            
            if (isResults) {
                contentDiv.innerHTML += `
                    <div style="background: #1a1a1a; padding: 20px; margin: 20px 0; border-radius: 10px;">
                        <h2 style="color: #FFD700; text-align: center;">BIDDING RESULTS</h2>
                `;
                
                // Show all bids
                bw.participants.forEach(sid => {
                    const player = state.players[sid];
                    const bid = bw.bids[sid] || 0;
                    contentDiv.innerHTML += `<p style="font-size: 18px;"><strong>${player.name}:</strong> $${bid}M</p>`;
                });
                
                contentDiv.innerHTML += '</div>';
            }
        } else {
            contentDiv.innerHTML = '<p>Bidding war state not properly initialized...</p>';
        }
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
    } else if (state.phase === 'phase1_releases') {
        detailsDiv.innerHTML = '<p>🎬 Spring Releases - Box Office Results! 🎬</p>';
        contentDiv.innerHTML = '<h2>This Season\'s Films:</h2>';
        
        // Collect all films from all players
        let allFilms = [];
        for (let [sid, player] of Object.entries(state.players)) {
            if (player.films) {
                player.films.forEach(film => {
                    allFilms.push({
                        ...film,
                        studio: player.name
                    });
                });
            }
        }
        
        // Display each film
        allFilms.forEach(film => {
            contentDiv.innerHTML += `
                <div class="talent-card" style="width: 90%; max-width: 600px; background: #2a2a2a; border-left: 4px solid #e50914;">
                    <h3 style="color: #e50914; margin-top: 0;">${film.title}</h3>
                    <p style="font-style: italic; color: #aaa;">"${film.teaser || 'No teaser provided'}"</p>
                    <p><strong>Studio:</strong> ${film.studio}</p>
                    <p><strong>Genre:</strong> ${film.genre} | <strong>Audience:</strong> ${film.audience}</p>
                    
                    <div style="background: #1a1a1a; padding: 10px; margin: 10px 0; border-radius: 5px;">
                        <h4 style="margin-top: 0;">Cast & Crew:</h4>
                        ${film.roles.map(r => `
                            <p style="margin: 5px 0;">
                                <strong>${r.role.toUpperCase()}:</strong> ${r.name}
                                <span style="color: #888;">(Heat: ${r.heat_bucket}, Prestige: ${r.prestige_bucket})</span>
                            </p>
                        `).join('')}
                    </div>
                    
                    <div style="background: #1a1a1a; padding: 15px; margin: 10px 0; border-radius: 5px; border: 2px solid ${film.box_office > 100 ? '#4CAF50' : '#ff9800'};">
                        <h4 style="margin-top: 0; color: #4CAF50;">📊 Box Office Results</h4>
                        <p><strong>Total Heat:</strong> ${film.heat}</p>
                        <p><strong>Market Multiplier:</strong> ${film.multiplier}x</p>
                        <p style="font-size: 24px; color: #4CAF50; margin: 10px 0;">
                            <strong>💰 $${film.box_office}M</strong>
                        </p>
                    </div>
                </div>
            `;
        });
        
        // Show player standings
        contentDiv.innerHTML += '<h2 style="margin-top: 40px;">Studio Standings:</h2>';
        contentDiv.innerHTML += '<div class="submissions">';
        
        // Sort players by score
        const playerArray = Object.entries(state.players).map(([sid, p]) => p);
        playerArray.sort((a, b) => b.score - a.score);
        
        playerArray.forEach((player, index) => {
            const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : '';
            contentDiv.innerHTML += `
                <p>${medal} <strong>${player.name}:</strong> $${player.money}M budget | ${player.score} points | ${player.films ? player.films.length : 0} films</p>
            `;
        });
        contentDiv.innerHTML += '</div>';
        
        // Button to continue to Summer
        contentDiv.innerHTML += '<button onclick="continueToSummer()" style="margin-top: 20px; padding: 15px 30px; font-size: 18px;">Continue to Summer Production ☀️</button>';
        
    } else if (state.phase === 'phase2_production') {
        detailsDiv.innerHTML = `<p>☀️ Summer - Year ${state.year}, Turn ${state.turn} of 5</p>`;
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
        const numPlayers2 = Object.keys(state.players).length;
        const numSelections2 = Object.keys(state.player_selections).length;
        
        for (let [sid, player] of Object.entries(state.players)) {
            const selected = state.player_selections[sid] !== undefined ? '✓' : '⏳';
            const selectionInfo = state.player_selections[sid] === 'pass' ? ' (Passed)' : '';
            contentDiv.innerHTML += `<p>${selected} ${player.name}${selectionInfo}</p>`;
        }
        contentDiv.innerHTML += `</div><p>${numSelections2}/${numPlayers2} players have selected</p>`;
    } else if (state.phase === 'phase2_bidding' || state.phase === 'phase2_bidding_results') {
        const bw = state.bidding_war;
        const isResults = state.phase === 'phase2_bidding_results';
        
        detailsDiv.innerHTML = `<p>💥 Summer BIDDING WAR - Turn ${state.turn} of 5</p>`;
        
        if (bw && bw.card_data) {
            const card = bw.card_data;
            contentDiv.innerHTML = `
                <div style="background: #8B0000; padding: 20px; border-radius: 10px; margin: 20px 0;">
                    <h2 style="color: #FFD700; text-align: center; margin: 0;">💥 BIDDING WAR 💥</h2>
                </div>
                
                <div class="talent-card" style="border: 3px solid #FFD700; background: #2a2a2a;">
                    <h2 style="color: #FFD700; margin-top: 0;">CONTESTED ROLE:</h2>
                    <h3>${card.name}</h3>
                    <p><strong>Role:</strong> ${card.role.toUpperCase()}</p>
                    <p><strong>Heat:</strong> ${card.heat_bucket} | <strong>Prestige:</strong> ${card.prestige_bucket}</p>
                    <p><strong>Base Salary:</strong> $${card.salary}M</p>
                    ${card.genre ? `<p><strong>Genre:</strong> ${card.genre}</p>` : ''}
                    ${card.audience ? `<p><strong>Audience:</strong> ${card.audience}</p>` : ''}
                </div>
                
                <h3 style="margin-top: 30px;">Participants:</h3>
                <div class="submissions">
            `;
            
            bw.participants.forEach(sid => {
                const player = state.players[sid];
                const hasBid = bw.bids[sid] !== undefined;
                const status = hasBid ? '✓ Bid Submitted' : '⏳ Bidding...';
                
                contentDiv.innerHTML += `
                    <div class="player-card" style="display: inline-block; margin: 10px;">
                        <h3>${player.name}</h3>
                        <p>💰 Budget: $${player.money}M</p>
                        <p>${status}</p>
                    </div>
                `;
            });
            
            contentDiv.innerHTML += '</div>';
            
            const numBids = Object.keys(bw.bids).length;
            const numParticipants = bw.participants.length;
            contentDiv.innerHTML += `<p style="text-align: center; font-size: 18px; margin-top: 20px;">
                ${numBids} of ${numParticipants} players have bid
            </p>`;
            
            if (isResults) {
                contentDiv.innerHTML += `
                    <div style="background: #1a1a1a; padding: 20px; margin: 20px 0; border-radius: 10px;">
                        <h2 style="color: #FFD700; text-align: center;">BIDDING RESULTS</h2>
                `;
                
                // Show all bids
                bw.participants.forEach(sid => {
                    const player = state.players[sid];
                    const bid = bw.bids[sid] || 0;
                    contentDiv.innerHTML += `<p style="font-size: 18px;"><strong>${player.name}:</strong> $${bid}M</p>`;
                });
                
                contentDiv.innerHTML += '</div>';
            }
        } else {
            contentDiv.innerHTML = '<p>Bidding war state not properly initialized...</p>';
        }
    } else if (state.phase === 'phase2_packaging') {
        detailsDiv.innerHTML = '<p>🎄 Holiday Packaging - Players assembling their films...</p>';
        contentDiv.innerHTML = '<h3>Player Progress:</h3><div class="submissions">';
        
        for (let [sid, player] of Object.entries(state.players)) {
            const ready = player.holiday_ready ? '✅' : '⏳';
            const roleCount = player.roles ? player.roles.length : 0;
            const filmCount = player.films ? player.films.length : 0;
            contentDiv.innerHTML += `<p>${ready} ${player.name} - ${roleCount} roles, ${filmCount} films</p>`;
        }
        contentDiv.innerHTML += '</div>';
    } else if (state.phase === 'phase2_releases') {
        detailsDiv.innerHTML = '<p>🎬 Holiday Releases - Box Office Results! 🎬</p>';
        contentDiv.innerHTML = '<h2>This Season\'s Films:</h2>';
        
        // Collect all films from all players
        let allFilms = [];
        for (let [sid, player] of Object.entries(state.players)) {
            if (player.films) {
                player.films.forEach(film => {
                    allFilms.push({
                        ...film,
                        studio: player.name
                    });
                });
            }
        }
        
        // Display each film
        allFilms.forEach(film => {
            contentDiv.innerHTML += `
                <div class="talent-card" style="width: 90%; max-width: 600px; background: #2a2a2a; border-left: 4px solid #e50914;">
                    <h3 style="color: #e50914; margin-top: 0;">${film.title}</h3>
                    <p style="font-style: italic; color: #aaa;">"${film.teaser || 'No teaser provided'}"</p>
                    <p><strong>Studio:</strong> ${film.studio}</p>
                    <p><strong>Genre:</strong> ${film.genre} | <strong>Audience:</strong> ${film.audience}</p>
                    
                    <div style="background: #1a1a1a; padding: 10px; margin: 10px 0; border-radius: 5px;">
                        <h4 style="margin-top: 0;">Cast & Crew:</h4>
                        ${film.roles.map(r => `
                            <p style="margin: 5px 0;">
                                <strong>${r.role.toUpperCase()}:</strong> ${r.name}
                                <span style="color: #888;">(Heat: ${r.heat_bucket}, Prestige: ${r.prestige_bucket})</span>
                            </p>
                        `).join('')}
                    </div>
                    
                    <div style="background: #1a1a1a; padding: 15px; margin: 10px 0; border-radius: 5px; border: 2px solid ${film.box_office > 100 ? '#4CAF50' : '#ff9800'};">
                        <h4 style="margin-top: 0; color: #4CAF50;">📊 Box Office Results</h4>
                        <p><strong>Total Heat:</strong> ${film.heat}</p>
                        <p><strong>Market Multiplier:</strong> ${film.multiplier}x</p>
                        <p style="font-size: 24px; color: #4CAF50; margin: 10px 0;">
                            <strong>💰 $${film.box_office}M</strong>
                        </p>
                    </div>
                </div>
            `;
        });
        
        // Show player standings
        contentDiv.innerHTML += '<h2 style="margin-top: 40px;">Studio Standings:</h2>';
        contentDiv.innerHTML += '<div class="submissions">';
        
        // Sort players by score
        const playerArray2 = Object.entries(state.players).map(([sid, p]) => p);
        playerArray2.sort((a, b) => b.score - a.score);
        
        playerArray2.forEach((player, index) => {
            const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : '';
            contentDiv.innerHTML += `
                <p>${medal} <strong>${player.name}:</strong> $${player.money}M budget | ${player.score} points | ${player.films ? player.films.length : 0} films</p>
            `;
        });
        contentDiv.innerHTML += '</div>';
        
        // Button to continue to Award Season
        contentDiv.innerHTML += '<button onclick="continueToAwards()" style="margin-top: 20px; padding: 15px 30px; font-size: 18px;">Continue to Award Season 🏆</button>';
        
    } else if (state.phase === 'awards_voting') {
        const currentCat = state.awards.current_category;
        const category = state.awards.categories[currentCat];
        
        detailsDiv.innerHTML = `<p>🏆 Award Season - ${category.name}</p>`;
        contentDiv.innerHTML = '<h2>Nominees:</h2>';
        
        category.nominees.forEach((film, index) => {
            contentDiv.innerHTML += `
                <div class="talent-card" style="width: 90%; max-width: 600px; background: #2a2a2a; border-left: 4px solid #FFD700;">
                    <h3 style="color: #FFD700; margin-top: 0;">${index + 1}. ${film.title}</h3>
                    <p><strong>Studio:</strong> ${film.studio}</p>
                    <p><strong>Prestige:</strong> ${film.prestige}</p>
                    <p style="font-style: italic;">"${film.teaser}"</p>
                </div>
            `;
        });
        
        contentDiv.innerHTML += '<h2 style="margin-top: 30px;">Votes:</h2><div class="submissions">';
        
        // Show who has voted (and for what)
        const numPlayers3 = Object.keys(state.players).length;
        const numVotes = Object.keys(category.votes).length;
        
        for (let [sid, player] of Object.entries(state.players)) {
            if (category.votes[sid] !== undefined) {
                const voteIndex = category.votes[sid];
                const votedFilm = category.nominees[voteIndex];
                contentDiv.innerHTML += `<p>✅ <strong>${player.name}</strong> voted for: ${votedFilm.title}</p>`;
            } else {
                contentDiv.innerHTML += `<p>⏳ ${player.name} - hasn't voted yet</p>`;
            }
        }
        
        contentDiv.innerHTML += `</div><p>${numVotes}/${numPlayers3} players have voted</p>`;
        
    } else if (state.phase === 'awards_results') {
        const currentCat = state.awards.current_category;
        const category = state.awards.categories[currentCat];
        const winner = category.winner;
        
        detailsDiv.innerHTML = `<p>🏆 ${category.name} Winner!</p>`;
        contentDiv.innerHTML = '<div style="text-align: center; padding: 40px;">';
        
        if (winner) {
            contentDiv.innerHTML += `
                <h1 style="color: #FFD700; font-size: 48px; margin: 20px 0;">🏆</h1>
                <h2 style="color: #FFD700; margin: 10px 0;">${category.name}</h2>
                <h1 style="color: #e50914; margin: 20px 0;">${winner.title}</h1>
                <p style="font-size: 24px;"><strong>${winner.studio}</strong></p>
                <p style="font-size: 18px; color: #aaa; font-style: italic;">"${winner.teaser}"</p>
                <p style="font-size: 20px; margin-top: 30px;">+${category.points_value} points awarded!</p>
            `;
        }
        
        contentDiv.innerHTML += '</div>';
        
        // Show final standings
        contentDiv.innerHTML += '<h2 style="margin-top: 40px;">Final Standings:</h2>';
        contentDiv.innerHTML += '<div class="submissions">';
        
        const playerArray3 = Object.entries(state.players).map(([sid, p]) => p);
        playerArray3.sort((a, b) => b.score - a.score);
        
        playerArray3.forEach((player, index) => {
            const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : '';
            contentDiv.innerHTML += `
                <p style="font-size: 20px;">${medal} <strong>${player.name}:</strong> ${player.score} points | ${player.films ? player.films.length : 0} films</p>
            `;
        });
        contentDiv.innerHTML += '</div>';
        
        contentDiv.innerHTML += '<button onclick="endGame()" style="margin-top: 30px; padding: 15px 30px; font-size: 18px;">End Game</button>';
        
    }
}

function startPhase0() {
    socket.emit('start_phase0');
}

function startPhase1() {
    socket.emit('start_phase1');
}

function continueToSummer() {
    socket.emit('continue_to_summer');
}

function continueToAwards() {
    socket.emit('start_awards');
}

function endGame() {
    if (confirm('Game complete! Start a new game?')) {
        location.reload();
    }
}