#!/usr/bin/env python3

import os
import math
import json
import logging
import subprocess
import sys
import socket
import tibber
import time
import statistics
import datetime
import argparse

logger = None

# This value will be sent if no valid data is available for a relative entry.
invalid_data_value = -1000


def setup_logger():

    class CustomFormatter(logging.Formatter):
        def format(self, record):
            record.msg = self.formatTime(record, "%H:%M:%S") + '.' + str(int(record.msecs)
                                                                         ) + ' ' + record.levelname[0] + ' | ' + record.msg
            return super().format(record)

    global logger
    logger = logging.getLogger(__name__)
    stream_handler = logging.StreamHandler()
    formatter = CustomFormatter('%(message)s')
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)


def home_to_string(home):
    return f"{home.address1}, {home.postal_code} {home.city}, {home.country}"


def load_or_create_json_config(config_file_name, skip_destination_ping=False):
    if os.path.exists(config_file_name):
        try:
            with open(config_file_name, "r") as f:
                logger.info(f"Loading credentials from: {config_file_name}")
                return json.load(f)
        except Exception as e:
            logger.fatal(
                f"Failed to read credentials from {config_file_name}. Please check permissions or delete the credentials file and re-run the script.")
            sys.exit(1)

    destination_not_reachable = True
    max_port_number = 2**16-1

    while destination_not_reachable:
        destination_ips = input(
            "Please enter your destination IPs or hostnames of the (Miniserver) in a comma seperated list with the port appended seperated by ':'.\n  e.g. 192.168.168.10:55555, 192.168.168.99:34633\n\n > ")
        destination_ip_port_tuples = [s.strip() for s in destination_ips.split(',')]
        if len(destination_ip_port_tuples) < 1:
            continue

        destinations = []
        all_ips_valid = True
        try:
            for ip_port in destination_ip_port_tuples:
                ip, port = ip_port.split(':')
                if skip_destination_ping:
                    error, output = subprocess.getstatusoutput("ping -c 1 -w 1 " + ip)
                    if error:
                        logger.error(output)
                        all_ips_valid = False
                        break

                port = int(port)
                if port > max_port_number or port < 1:
                    raise ValueError(f"The given port {port} is not in the valid range [1-{max_port_number}].")

                destinations.append({"ip": ip, "port": port})

            if all_ips_valid:
                destination_not_reachable = False

        except Exception as e:
            logger.error(e)

    token_invalid = True
    while (token_invalid):
        token = input("Please enter your Tibber API Token:\n > ")
        token = token.strip()
        try:
            account = tibber.Account(token)
            token_invalid = False
        except Exception as e:
            logger.error(e)

    invalid_home_selected = True
    while invalid_home_selected:
        home_id = input("Please select the number of the home you wish to monitor:\n" +
                        "\n".join(f"{i:2d}: " + home_to_string(h) for i, h in enumerate(account.homes)) + "\n > ")
        try:
            home_id = int(home_id)
            max_len = len(account.homes) - 1
            if home_id < 0 or home_id > max_len:
                raise ValueError(f"The given id {home_id} is not in the valid range [0-{max_len}].")
            invalid_home_selected = False
        except Exception as e:
            logger.error(e)

    config = {}
    config["destinations"] = destinations

    config["token"] = token
    config["home_id"] = home_id

    with open(config_file_name, "w") as f:
        json.dump(config, f, indent=4)
        logger.info(f"Stored credentials in {config_file_name}")

    # Set the credentials to be write protected and readable for the user only.
    os.chmod(config_file_name, 0o400)

    return config


def get_time_dictionary():
    time_information = {}
    today = datetime.date.today()
    time_information["date_now"] = str(today)
    time_information["date_now_epoch"] = time.mktime(today.timetuple())
    time_information["date_now_seconds_since_epoch"] = int(time.time())
    time_information["date_now_day"] = today.day
    time_information["date_now_month"] = today.month
    time_information["date_now_year"] = today.year
    return time_information


def format_price(price, price_multiplier, precicion):
    return round(price * price_multiplier, precicion)


def get_price_dictionary(tibber_account, home_id, target_price_unit, no_invalid_values=False, precicion=4):
    subscription = tibber_account.homes[home_id].current_subscription
    price_info_today = subscription.price_info.today

    euro_list = ["EUR", "EURO", "€"]
    is_euro = subscription.price_info.current.currency in euro_list
    target_price_unit_is_eur = target_price_unit in euro_list

    price_multiplier_matrix = [
        [1, 0.01],
        [100, 1]
    ]
    price_multiplier = price_multiplier_matrix[is_euro][target_price_unit_is_eur]

    prices_total = [format_price(p.total, price_multiplier, precicion) for p in price_info_today]
    price_current = format_price(subscription.price_info.current.total, price_multiplier, precicion)

    price_information = {}
    price_information["price_low"] = min(prices_total)
    price_information["price_high"] = max(prices_total)
    price_information["price_median"] = round(statistics.median(prices_total), precicion)
    price_information["price_average"] = round(statistics.mean(prices_total), precicion)
    price_information["price_stdev"] = round(statistics.stdev(prices_total), precicion)
    price_information["price_current"] = price_current
    price_information["price_unit"] = "EUR" if target_price_unit_is_eur else "Cent"

    logger.info(f"Sending price information in '{price_information['price_unit']}'.")
    logger.info(
        f"Overview: {{ current: {price_information['price_current']}, avg: {price_information['price_average']}, low: {price_information['price_low']}, high: {price_information['price_high']} }}")

    prices_total_sorted = sorted(prices_total)
    for i, p in enumerate(prices_total_sorted):
        price_information[f"price_threshold_{i:02d}"] = p

    for i, p in enumerate(prices_total):
        price_information[f"data_price_hour_abs_{i:02}_amount"] = p

    # Merge two lists into one and preserve order.
    price_information_available = subscription.price_info.today + subscription.price_info.tomorrow
    now = datetime.datetime.now()

    # Setting this variable to False will cause to only valid send valid values and skip the placeholders.
    if not no_invalid_values:
        # Assume there is never more than 23 values in the past and never more than
        # 36 values in the future. First store all values in an invalid state.
        for i in range(23, 0, -1):
            price_information[f"data_price_hour_rel_-{i:02}_amount"] = invalid_data_value

        for i in range(36):
            price_information[f"data_price_hour_rel_+{i:02}_amount"] = invalid_data_value

    number_of_valid_negative_relatives = 0
    number_of_valid_positive_relatives = 0
    for i, price_info in enumerate(price_information_available):
        isoformat = datetime.datetime.fromisoformat(price_info.starts_at).replace(tzinfo=None)
        delta_hour = math.ceil((isoformat - now).total_seconds()/3600)
        sign = '-' if delta_hour < 0 else '+'
        if delta_hour < 0:
            number_of_valid_negative_relatives += 1
        else:
            number_of_valid_positive_relatives += 1

        price_information[f"data_price_hour_rel_{sign}{abs(delta_hour):02}_amount"] = format_price(
            price_info.total, price_multiplier, precicion)

    price_information["data_price_hour_rel_num_negatives"] = number_of_valid_negative_relatives
    price_information["data_price_hour_rel_num_positives"] = number_of_valid_positive_relatives
    return price_information


def get_power_dictionary(tibber_account, config):
    # Not implemented yet
    return {}


def merge_dictionaries(dict_list):
    result = {}
    for d in dict_list:
        result.update(d)
    return result


def prepare_datagram_string(key_value_dictionary, format=False):
    s = json.dumps(key_value_dictionary, indent=2 if format else None)
    s = s.replace('"', '')
    return s


def send_to_destination(config, key_value_dictionary):
    string_to_be_sent = prepare_datagram_string(key_value_dictionary)
    string_to_be_sent_formatted = prepare_datagram_string(key_value_dictionary, format=True)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    string_to_be_sent_encoded = string_to_be_sent.encode()
    for destination in config["destinations"]:
        dst = (destination["ip"], destination["port"])
        bytes_sent = s.sendto(string_to_be_sent_encoded, dst)

        if bytes_sent < len(string_to_be_sent):
            logger.error("Failed to send the information to " + dst)
        else:
            logger.info(f"Sent {bytes_sent} bytes to {dst}")
            logger.debug(f"Sent the following string:\n" + string_to_be_sent_formatted)


if __name__ == '__main__':
    setup_logger()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    choice_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}
    parser.add_argument('-l', '--log', help="Logging level for the application.",
                        choices=choice_map.keys(), default="INFO")
    parser.add_argument(
        '-c', '--config', help=f"The filename of the configuration file in use, relative to {script_dir}", type=str, default=".tibberlox_config")
    parser.add_argument(
        '--no-ping-check', help='Skip the validation of entered ip addresses by using the ping command.', action="store_true")
    parser.add_argument('--no-invalid-values',
                        help=f'By default all relative value fileds are sent, even if no data is available. Invalid data is indicated by a value of {invalid_data_value}.', action="store_true")
    parser.add_argument('--price-unit', help="The price unit sent in the UDP interface",
                        choices=["EUR", "Cent"], default="EUR")
    args = parser.parse_args()

    logger.setLevel(choice_map[args.log])

    config = load_or_create_json_config(os.path.join(script_dir, args.config), skip_destination_ping=args.no_ping_check)

    tibber_account = tibber.Account(config["token"])
    # tibber_account.send_push_notification("My title", "Hello! I'm a message!")

    time_dict = get_time_dictionary()
    price_dict = get_price_dictionary(
        tibber_account, config["home_id"], args.price_unit, no_invalid_values=args.no_invalid_values)
    power_dict = get_power_dictionary(tibber_account, config)

    information_to_be_sent = merge_dictionaries([time_dict, price_dict, power_dict])

    send_to_destination(config, information_to_be_sent)
