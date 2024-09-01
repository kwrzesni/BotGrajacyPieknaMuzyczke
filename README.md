# BotGrajacyPieknaMuzyczke

## Ruquirements
- Python >= 3.10
- Java >= 17

## Running bot
1. Clone the repository: ```git clone https://github.com/kwrzesni/BotGrajacyPieknaMuzyczke.git```
2. Go to repository folder: ```cd BotGrajacyPieknaMuzyczke```
3. Create virtual enviroment: ```python -m venv SrodowiskoMuzyczne```
4. Source virtual enviroment: ```source SrodowiskoMuzyczne/bin/activate```
5. Install required python packages: ```python -m pip install -r requirements.txt```
6. Add .env file with bot token - file format: TOKEN = YOUR_TOKEN
7. Go to Lavalink directory: ```cd Lavalink```
8. Start Lavalink process in background: ```java -jar Lavalink.jar > /dev/null 2>&1 &```
9. Go back to previous directory: ```cd ..```
10. Run the bot  in background: ```python main.py > /dev/null 2>&1 &```
11. Leave session: Press: <kbd>Ctrl</kbd>+<kbd>D</kbd>

## Stopping bot
1. Kill all python processes: ```killall python3.10```
2. Kill all java processes: ```killall java```
