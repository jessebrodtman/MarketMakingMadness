// Initialize Socket.IO connection
const socket = io();

// Get the current lobby ID and username from Flask
const lobbyId = "{{ lobby.id }}";
const username = "{{ session.get('username') }}";

// Emit join_room_event when the page loads
socket.emit("join_room_event", { lobby_id: lobbyId, username });
console.log(`Client is attempting to join room with lobby_id: ${lobbyId}`);

// Emit leave_room_event when the page unloads
window.addEventListener("beforeunload", () => {
    socket.emit("leave_room_event", { lobby_id: lobbyId, username });
});

socket.on('connect', () => {
    console.log("SocketIO Connected");
});

socket.on('disconnect', () => {
    console.log("SocketIO Disconnected");
});

// Listen for timer updates
socket.on('timer_update', (data) => {
    document.getElementById('timer').innerText = `${data.game_length}`;
    console.log(`Time Remaining: ${data.game_length} second`);
});

// Listen for when the timer ends
socket.on('timer_ended', (data) => {
    console.log('Timer Ended');
    document.getElementById('timer').innerText = data.message;

    // Redirect the user after 60 seconds
    setTimeout(() => {
        window.location.href = data.redirect_url;
    }, 60000);
});

// Listen for market updates (bids and asks)
socket.on("market_update", (data) => {
    const bids = data.bids;
    const asks = data.asks;

    // Update the bids table
    const bidsTableBody = document.querySelector("#bids-table tbody");
    bidsTableBody.innerHTML = bids
        .map(
            (bid) => `
            <tr>
                <td class="text-center text-success">${bid.price}</td>
                <td class="text-center">${bid.total_quantity}</td>
            </tr>
        `
        )
        .join("");

    // Update the asks table
    const asksTableBody = document.querySelector("#asks-table tbody");
    asksTableBody.innerHTML = asks
        .map(
            (ask) => `
            <tr>
                <td class="text-center text-danger">${ask.price}</td>
                <td class="text-center">${ask.total_quantity}</td>
            </tr>
        `
        )
        .join("");
});

// Listen for trade updates
socket.on("trade_update", (trade) => {
    const tradeHistoryTableBody = document.querySelector("#trade-history-table tbody");
    const newRow = `
        <tr>
            <td class="text-center">${trade.price}</td>
            <td class="text-center">${trade.quantity}</td>
            <td class="text-center">${trade.timestamp}</td>
        </tr>
    `;

    // Prepend the new trade to the table
    tradeHistoryTableBody.insertAdjacentHTML("afterbegin", newRow);
});

// Listen for roster updates
socket.on("roster_update", (data) => {
    const rosterList = document.querySelector("#roster-list");
    rosterList.innerHTML = data.players
        .map(
            (player) => `
            <li class="list-group-item d-flex justify-content-between align-items-center">
                <span>${player.name}</span>
                <span class="badge ${
                    player.ready ? "bg-success" : "bg-danger"
                }">${player.ready ? "Ready" : "Not Ready"}</span>
            </li>
        `
        )
        .join("");
});

// Listen for the leaderboard data when the game ends
socket.on("game_end_leaderboard", (data) => {
    const leaderboard = data.leaderboard;
    displayLeaderboard(leaderboard);
});

// Function to display the leaderboard
function displayLeaderboard(leaderboard) {
    // Create the leaderboard modal
    const modalHtml = `
        <div class="modal fade" id="leaderboardModal" tabindex="-1" aria-labelledby="leaderboardModalLabel" aria-hidden="true">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="leaderboardModalLabel">Game Leaderboard</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <table class="table table-striped">
                            <thead>
                                <tr>
                                    <th>Rank</th>
                                    <th>User</th>
                                    <th>P&L</th>
                                    <th>Accuracy</th>
                                    <th>Trades</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${leaderboard
                                    .map(
                                        (player, index) => `
                                        <tr>
                                            <td>${index + 1}</td>
                                            <td>${player.user_id}</td>
                                            <td>${player.pnl.toFixed(2)}</td>
                                            <td>${player.accuracy}%</td>
                                            <td>${player.trade_count}</td>
                                        </tr>
                                    `
                                    )
                                    .join("")}
                            </tbody>
                        </table>
                    </div>
                    <div class="modal-footer">
                        <a href="/play" class="btn btn-primary">Return to Lobby</a>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Append the modal to the body
    document.body.insertAdjacentHTML("beforeend", modalHtml);

    // Show the modal
    const leaderboardModal = new bootstrap.Modal(document.getElementById("leaderboardModal"));
    leaderboardModal.show();
}


