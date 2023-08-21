from tibberlox import setup_logger, setup_virtual_envionment, run_in_venv, SortedDefaultsHelpFormatter, load_or_create_json_config
import argparse
import logging
import os
import json
import socket

try:
    import tibber
except:
    pass

logger = None

if __name__ == '__main__':
    logger = setup_logger()
    setup_virtual_envionment()
    run_in_venv(__file__)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(formatter_class=SortedDefaultsHelpFormatter)
    choice_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}

    parser.add_argument('-l', '--log', choices=choice_map.keys(), default="INFO", help="Logging level for the application.")

    parser.add_argument('-c', '--config', type=str, default=".tibberlox_config",
                        help=f"The filename of the configuration file in use, relative to {script_dir}")

    parser.add_argument('--no-ping-check', action="store_true",
                        help='Skip the validation of entered ip addresses by using the ping command.')

    args = parser.parse_args()
    logger.setLevel(choice_map[args.log])

    logger.debug(str(args))

    config = load_or_create_json_config(args.config)
    tibber_account = tibber.Account(config["token"])
    home = tibber_account.homes[config['home_id']]

    @home.event("live_measurement")
    async def show_current_power(data):
        d = dir(data)
        send_datagram = {}
        for attribute in d:
            if attribute.startswith('__'):
                continue
            v = getattr(data, attribute)
            if (type(v) in [int, float]):
                send_datagram[attribute] = v

        send_string = json.dumps(send_datagram).replace('"', '').replace("'", '').encode()
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        host = d['ip']
        port = d['port'] + 1
        print(f"Sending to {host}:{port}")
        print(send_string)
        for d in config['destinations']:
            s.sendto(send_string, (host, port))

    home.start_live_feed(user_agent="UserAgent/0.0.1")
