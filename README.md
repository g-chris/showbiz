# 🎬 Hollywood Moguls

A party game for two or more people where you run rival movie studios. One computer hosts the game on a TV or laptop screen, and everyone plays on their own phone. Nobody needs to install an app.

You name the talent, fight over stars in blind bidding wars, package films, and release them at the box office. At the end, the studios vote for Best Picture.

## Download

| Platform | Download |
|---|---|
| **Windows** (64-bit) | [HollywoodMoguls-windows-x64.exe](https://github.com/g-chris/showbiz/releases/latest/download/HollywoodMoguls-windows-x64.exe) |
| **macOS** (Apple Silicon: M1 or later) | [HollywoodMoguls-macos-arm64.zip](https://github.com/g-chris/showbiz/releases/latest/download/HollywoodMoguls-macos-arm64.zip) |
| **Linux** (x86_64) | [HollywoodMoguls-linux-x86_64.tar.gz](https://github.com/g-chris/showbiz/releases/latest/download/HollywoodMoguls-linux-x86_64.tar.gz) |

All versions are on the [Releases page](https://github.com/g-chris/showbiz/releases).

### First run

The game is a single file. When you run it, a console window opens and the host screen opens in your browser. **Keep the console window open while you play**, because closing it stops the game.

The first launch can take about 10 seconds while the game unpacks itself.

**Windows**
1. Double-click `HollywoodMoguls-windows-x64.exe`.
2. If you see "Windows protected your PC", click **More info**, then **Run anyway**. The game isn't code-signed, so Windows shows this warning for any download like it.
3. When Windows Firewall asks, allow access on **private networks**. Phones can't connect without this.

**macOS**
1. Unzip the download and double-click `HollywoodMoguls`.
2. macOS will say it "can't verify" the app, because it isn't notarized by Apple. Open **System Settings → Privacy & Security**, scroll down, and click **Open Anyway** next to the message about HollywoodMoguls. Then open it again.
   - Or, in Terminal: `xattr -d com.apple.quarantine ~/Downloads/HollywoodMoguls`
3. If macOS asks whether to accept incoming network connections, click **Allow**.

**Linux**
```bash
tar -xzf HollywoodMoguls-linux-x86_64.tar.gz
./HollywoodMoguls
```
If no browser opens, go to http://localhost:8080 yourself.

## Hosting a game

1. Run Hollywood Moguls on a computer connected to the TV or screen everyone can see. The host screen opens at http://localhost:8080.
2. Players join the **same Wi-Fi network** as the host computer, then scan the QR code on the host screen (or type in the address shown under it).
3. Each player enters a studio name. When everyone's in, the host clicks **Start Game**.
4. The game moves along by itself from there. Most steps have a countdown, so nobody can stall the game.

You don't need an internet connection. The host computer and the phones only need to be on the same local network.

**If a phone disconnects** (screen locked, browser closed, battery died), reopen the player page and join with the **same studio name**. Your money, talent and films are kept.

**If someone leaves for good** during talent naming or film packaging, the host can click **Skip Waiting Players** to fill in their choices and keep going. The other steps advance on a timer anyway.

**To play again,** click **New Game (Same Studios)** on the host screen after the final results. Everyone stays connected and goes back to the lobby.

## How to play

Every studio starts with **$100M**. The highest score at the end wins. You score points from box office earnings, plus a big bonus for winning Best Picture.

1. **Name the talent.** Each player invents 3 screenwriters, 3 directors and 5 stars. Each gets hidden stats for Heat (box-office draw), Prestige (critical respect) and Salary.
2. **Winter production (5 turns).** Each turn a set of talent cards is dealt. Pick one to sign or pass, within 60 seconds. If two or more studios pick the same card, it goes to a **bidding war**: everyone secretly bids extra money and the highest bid wins. On a tie, the talent walks away from all of you.
3. **Spring packaging.** Build films from the talent you signed. A film needs a **Producer, Screenwriter, Director and Star**. Budget "No Name" talent ($1M each) is always available to fill gaps. Give each film a title and greenlight it. Talent you don't use is released for a 50% refund.
4. **Spring releases.** Films earn box office based on their total Heat, multiplied by some luck.
5. **Summer production, Holiday packaging and Holiday releases** repeat the same steps.
6. **Award season.** The five most prestigious films are nominated for Best Picture. Every studio votes, but you can't vote for your own film. The winner earns **+1000 points**.

## Running from source

Requires Python 3.9 or newer.

```bash
git clone https://github.com/g-chris/showbiz.git
cd showbiz
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

| Environment variable | Effect |
|---|---|
| `SHOWBIZ_PORT=9000` | Use a different port (default 8080), for example if something else already uses 8080 |
| `SHOWBIZ_NO_BROWSER=1` | Don't open a browser on startup (useful on headless machines) |

## Troubleshooting

- **Phones can't connect.** Make sure they're on the same Wi-Fi as the host computer, not on mobile data, and that your firewall allows Hollywood Moguls. Some guest or public Wi-Fi networks block devices from talking to each other. A home network or a phone hotspot usually works.
- **"Port 8080 is already in use".** Hollywood Moguls is probably already running in another window. Use that one, or set `SHOWBIZ_PORT` to another port.
- **The QR code shows `localhost`.** The host computer couldn't work out its own network address. Find its local IP address (for example `192.168.1.20`) and have players go to `http://<that address>:8080/player`.

## Building the executables

Releases are built automatically by GitHub Actions ([`.github/workflows/release.yml`](.github/workflows/release.yml)) when a version tag such as `v1.0.0` is pushed. To build locally for your own platform:

```bash
pip install -r requirements.txt pyinstaller
pyinstaller showbiz.spec        # output: dist/HollywoodMoguls
```

See [ChangeLog.txt](ChangeLog.txt) for version history.
