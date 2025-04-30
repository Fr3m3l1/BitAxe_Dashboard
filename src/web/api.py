import sqlite3
from flask import Blueprint, request, jsonify
from db.database import DATABASE, get_latest_data
from send.telegram_notification import send_telegram_notification

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/input', methods=['POST'])
def receive_data():
    """
    Receives miner data via a POST request and stores it in the SQLite database.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data received'}), 400
    
    # compare with the data before saving it
    # get the last data from the database
    last_data = get_latest_data()
    
    if last_data:
        # check if the last data has a lower bestDiff than the current data
        last_difficulty = last_data['bestDiff']
        last_session_difficulty = last_data['bestSessionDiff']
        current_difficulty = data.get('bestDiff')
        current_session_difficulty = data.get('bestSessionDiff')
        if last_difficulty < current_difficulty:
            send_telegram_notification(f"New best OVERALL difficulty found: {current_difficulty}")
        else:
            if last_session_difficulty < current_session_difficulty:
                send_telegram_notification(f"New best SESSION difficulty found: {current_session_difficulty}")


    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO miner_data (
                power, voltage, current, temp, vrTemp, hashRate, bestDiff, bestSessionDiff,
                stratumDiff, isUsingFallbackStratum, freeHeap, coreVoltage, coreVoltageActual,
                frequency, ssid, macAddr, hostname, wifiStatus, sharesAccepted, sharesRejected,
                uptimeSeconds, asicCount, smallCoreCount, ASICModel, stratumURL, fallbackStratumURL,
                stratumPort, fallbackStratumPort, stratumUser, fallbackStratumUser, version, idfVersion,
                boardVersion, runningPartition, flipscreen, overheat_mode, invertscreen, invertfanpolarity,
                autofanspeed, fanspeed, fanrpm
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            data.get('power'),
            data.get('voltage'),
            data.get('current'),
            data.get('temp'),
            data.get('vrTemp'),
            data.get('hashRate'),
            data.get('bestDiff'),
            data.get('bestSessionDiff'),
            data.get('stratumDiff'),
            data.get('isUsingFallbackStratum'),
            data.get('freeHeap'),
            data.get('coreVoltage'),
            data.get('coreVoltageActual'),
            data.get('frequency'),
            data.get('ssid'),
            data.get('macAddr'),
            data.get('hostname'),
            data.get('wifiStatus'),
            data.get('sharesAccepted'),
            data.get('sharesRejected'),
            data.get('uptimeSeconds'),
            data.get('asicCount'),
            data.get('smallCoreCount'),
            data.get('ASICModel'),
            data.get('stratumURL'),
            data.get('fallbackStratumURL'),
            data.get('stratumPort'),
            data.get('fallbackStratumPort'),
            data.get('stratumUser'),
            data.get('fallbackStratumUser'),
            data.get('version'),
            data.get('idfVersion'),
            data.get('boardVersion'),
            data.get('runningPartition'),
            data.get('flipscreen'),
            data.get('overheat_mode'),
            data.get('invertscreen'),
            data.get('invertfanpolarity'),
            data.get('autofanspeed'),
            data.get('fanspeed'),
            data.get('fanrpm')
        ))
        conn.commit()

    # Check if the temperature is too high
    if data.get('temp') and data.get('temp') > 65:
        send_telegram_notification(f"Warning: High temperature detected ({data.get('temp')}°C)")

    if data.get('vrTemp') and data.get('vrTemp') > 75:
        send_telegram_notification(f"Warning: High VR temperature detected ({data.get('vrTemp')}°C)")

    if data.get('isUsingFallbackStratum'):
        send_telegram_notification("Warning: Using fallback stratum")

    if data.get('sharesRejected') and data.get('sharesAccepted'):
        reject_rate = data.get('sharesRejected') / (data.get('sharesRejected') + data.get('sharesAccepted'))
        if (reject_rate*100) > 0.5:
            send_telegram_notification(f"Warning: High reject rate detected ({reject_rate:.2%})")

    return jsonify({'message': 'Data saved successfully'}), 200
