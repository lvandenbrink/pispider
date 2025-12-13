import os
from logger import log
from py_irsend import irsend
from ping3 import ping

kef_host = os.getenv("KEF_IP", "localhost")

class Kef:

    def __init__(self):
        self.on = self._is_online()
        self.muted = False
        self.volume = 10

    def execute(self, command, data):
        log.info('execute kef command %s: %s', command, data)

        if command == "get" or command == "state":
            # skip just return info
            pass
        if 'set' == command:
            if 'state' in data:
                state = data['state']
                if state == 'on':
                    self._kef_command('KEY_POWER')
                    self.on = not self.on
                elif state == 'off':
                    self._kef_command('KEY_POWER')
                    self.on = not self.on
            elif 'volume' in data:
                action = data['volume']
                if action == 'mute':
                    self._kef_command('KEY_MUTE')
                    self.muted = not self.muted
                elif action == 'unmute':
                    self._kef_command('KEY_MUTE')
                    self.muted = not self.muted
                elif action == 'increase' or action == 'up':
                    self._kef_command('KEY_VOLUMEUP')
                    self._kef_command('KEY_VOLUMEUP')
                    self.volume += 5
                elif action == 'decrease' or action == 'down':
                    self._kef_command('KEY_VOLUMEDOWN')
                    self._kef_command('KEY_VOLUMEDOWN')
                    self.volume -= 5
            elif 'toggle' in data:
                toggle = data['toggle']
                if toggle == 'power':
                    self._kef_command('KEY_POWER')
                    self.on = not self.on
                elif toggle == 'source':
                    self._kef_command('KEY_INPUT')
            elif 'media' in data:
                action = data['media']
                if action == 'next':
                    self._kef_command('KEY_NEXTSONG')
                elif action == 'previous':
                    self._kef_command('KEY_PREVIOUSSONG')
                elif action == 'pause':
                    self._kef_command('KEY_PLAYPAUSE')
            else :
                log.error("kef: unknown action `%s` for command `%s`", data, command)
                return { "errorCode": "offline", "status" : "ERROR" }
        elif command == "toggle":
            self._kef_command('KEY_POWER')
            self.on = not self.on
        else:
            log.error("kef: unknown command `%s` with data: '%s'", command, data)
            return { "errorCode": "offline", "status" : "ERROR" }

        return self.state()

    def state(self):
        info = {
            "on": self.on,
			"state": "ON" if self.on else "FALSE",
			"CurrentVolume": self.volume,
            "IsMuted": self.muted,
        }

        log.info('kef state: %s', info)

        return info

    def _kef_command(self, command):
        irsend.send_once('KEF_LS50', [command, command, command, command, command])

    def _is_online(self):
        result = ping(kef_host)
        log.debug("speaker is reachable, time: %s ms", result)
        return result is not None
