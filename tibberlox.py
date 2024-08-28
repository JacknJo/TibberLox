#!/usr/bin/env python3

import os
import math
import json
import logging
import subprocess
import sys
import socket
import time
import statistics
import datetime
import argparse
import operator
from collections import namedtuple
try:
    import tibber
except:
    pass

logger = None

physical_script_directory = os.path.dirname(os.path.realpath(os.path.abspath(__file__)))
venv_dir = os.path.join(physical_script_directory, '.venv')
venv_python_exe = os.path.join(venv_dir, 'bin', 'python')


# Be slightly ahead of time. If we send cyclically every minute, this ensures at the new full hour trigger the correct prices are given.
global_time_compensation_seconds = 70


def faketime_today():
    return faketime_now().date()


def faketime_now():
    return datetime.datetime.now() + datetime.timedelta(seconds=global_time_compensation_seconds)


def in_venv():
    return sys.prefix != sys.base_prefix


def setup_virtual_envionment():
    if not os.path.isdir(venv_dir):
        subprocess.run(f'python3 -m venv {venv_dir}', shell=True, cwd=physical_script_directory)
        venv_python_exe = os.path.join(venv_dir, 'bin', 'python')
        print(subprocess.run(f'{venv_python_exe} -m ensurepip', shell=True))
        print(subprocess.run(f'{venv_python_exe} -m pip install -r requirements.txt', shell=True, cwd=physical_script_directory))


def run_in_venv(file_to_run):
    if file_to_run is None:
        file_to_run == __file__
    if not in_venv():
        real_abs_file = os.path.realpath(os.path.abspath(file_to_run))
        print(f'Restarting the process in virtual environment: {venv_python_exe}')
        print(sys.argv[0])
        subprocess.run([venv_python_exe, real_abs_file] + sys.argv[1:], cwd=physical_script_directory)
        sys.exit()


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
    return logger


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
    today = faketime_today()
    time_information["date_now"] = str(today)
    time_information["date_now_epoch"] = time.mktime(today.timetuple())
    time_information["date_now_seconds_since_epoch"] = int(time.time())
    time_information["date_now_day"] = today.day
    time_information["date_now_month"] = today.month
    time_information["date_now_year"] = today.year
    return time_information


def calculate_delta_days(datetime_a, isostr_b):
    datetime_b = datetime.date.fromisoformat(isostr_b)
    return abs((datetime_a - datetime_b).days)


CacheObject = namedtuple("CacheObject", "total currency starts_at")


def store_price_history_cache(cache_file, price_info_today, days_to_keep=7):
    date = faketime_today()
    cache = load_price_history_cache(cache_file)
    if date.isoformat() in cache:
        return

    cache[date.isoformat()] = [CacheObject(p.total, p.currency, p.starts_at) for p in price_info_today]

    obsolete_keys = []
    for k in cache.keys():
        if calculate_delta_days(date, k) > days_to_keep:
            obsolete_keys.append(k)

    for o in obsolete_keys:
        del cache[o]

    with open(cache_file, 'w') as f:
        json.dump(cache, f, indent=4)


def load_price_history_cache(cache_file):
    try:
        with open(cache_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(str(e))
        return {}


def load_yesterday_prices(cache_file):
    try:
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        cache = load_price_history_cache(cache_file)
        yesterday_cache = cache[yesterday.isoformat()]
        return [CacheObject(*e) for e in yesterday_cache]
    except Exception as e:
        logger.warning("Failed to load prices from yesterday: " + str(e))
        return []


def convert_to_target_unit(price, target_in_euro, precicion):
    def is_euro(unit):
        return unit.upper() in ["EUR", "EURO", "€"]

    def convert_price(price):
        price_multiplier_matrix = [
            [1, 0.01],
            [100, 1]
        ]
        return round(price.total * price_multiplier_matrix[is_euro(price.currency)][target_in_euro], precicion)

    if type(price) is list:
        return [convert_price(p) for p in price]
    else:
        return convert_price(price)


def get_price_dictionary(tibber_account, home_id, target_price_in_euro, no_invalid_fields=False, precicion=4,
                         invalid_data_value=-1000, use_cache=True, number_of_positive_relative_data=35, number_of_negative_relative_data=23, history_length=10):
    subscription = tibber_account.homes[home_id].current_subscription

    cache_file = 'tibberlox_cache.json'
    store_price_history_cache(cache_file, subscription.price_info.today, days_to_keep=history_length)
    prices_total = convert_to_target_unit(subscription.price_info.today, target_price_in_euro, precicion)
    price_current = convert_to_target_unit(subscription.price_info.current, target_price_in_euro, precicion)

    price_information = {}
    price_information["price_low"] = min(prices_total)
    price_information["price_high"] = max(prices_total)
    price_information["price_median"] = round(statistics.median(prices_total), precicion)
    price_information["price_average"] = round(statistics.mean(prices_total), precicion)
    price_information["price_stdev"] = round(statistics.stdev(prices_total), precicion)
    price_information["price_current"] = price_current
    price_information["price_unit"] = "EUR" if target_price_in_euro else "Cent"
    price_information["price_multiplicator_to_eur"] = 1 if target_price_in_euro else 0.01

    logger.info(f"Sending price information in '{price_information['price_unit']}'.")
    logger.info(
        f"Overview: {{ current: {price_information['price_current']}, avg: {price_information['price_average']}, low: {price_information['price_low']}, high: {price_information['price_high']} }}")

    prices_total_sorted = sorted(prices_total)
    for i, p in enumerate(prices_total_sorted):
        price_information[f"price_threshold_{i:02d}"] = p

    for i, p in enumerate(prices_total):
        price_information[f"data_price_hour_abs_{i:02}_amount"] = p

    # Setting this variable to False will cause to only valid send valid values and skip the placeholders.
    if not no_invalid_fields:
        # Assume there is never more than 23 values in the past and never more than
        # 36 values in the future. First store all values in an invalid state.
        for i in range(number_of_negative_relative_data, 0, -1):
            price_information[f"data_price_hour_rel_-{i:02}_amount"] = invalid_data_value

        for i in range(number_of_positive_relative_data):
            price_information[f"data_price_hour_rel_+{i:02}_amount"] = invalid_data_value

    # Merge two lists into one and preserve order.
    prices_yesterday = load_yesterday_prices(cache_file)

    price_information_available = prices_yesterday + subscription.price_info.today + subscription.price_info.tomorrow
    now = faketime_now()

    number_of_valid_negative_relatives = 0
    number_of_valid_positive_relatives = 0
    for price_info in price_information_available:
        price_date = datetime.datetime.fromisoformat(price_info.starts_at).replace(tzinfo=None)
        delta_hour = math.ceil((price_date - now).total_seconds()/3600)

        if delta_hour < -number_of_negative_relative_data or delta_hour >= number_of_positive_relative_data:
            continue

        if delta_hour < 0:
            number_of_valid_negative_relatives += 1
        else:
            number_of_valid_positive_relatives += 1

        sign = '-' if delta_hour < 0 else '+'
        key = f"data_price_hour_rel_{sign}{abs(delta_hour):02}_amount"
        price_information[key] = convert_to_target_unit(price_info, target_price_in_euro, precicion)

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


class SortedDefaultsHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    def add_arguments(self, actions):
        actions = sorted(actions, key=operator.attrgetter('option_strings'))
        long_options = [a for a in actions if operator.attrgetter('option_strings')(a)[0].startswith('--')]
        short_options = [a for a in actions if not operator.attrgetter('option_strings')(a)[0].startswith('--')]
        actions = short_options + long_options
        super(argparse.ArgumentDefaultsHelpFormatter, self).add_arguments(actions)


if __name__ == '__main__':
    setup_logger()
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

    parser.add_argument('--no-invalid-fields', action="store_true",
                        help=f'By default all relative value fileds [-23, +36] are sent, even if no data is available.')

    parser.add_argument('--no-yesterday-cache', action="store_true",
                        help="Do not cache the price values from the day before to always provide past 23h of relative data.")

    parser.add_argument('--price-unit', choices=["EUR", "Cent"], default="EUR",  help="The price unit sent in the UDP interface")

    parser.add_argument('--invalid-data-value', type=int, default=999,
                        help="The value that is sent for the relative fields that have no data available.")

    valid_values = range(36)
    parser.add_argument('-f', '--future', type=int, choices=valid_values, metavar=f"[{min(valid_values)}-{max(valid_values)}]", default=35,
                        help="Maximum number of positive relative entries to send for the future. 0 to disable. E.g. '3' will result in +00, +01 and +02 being sent.")

    valid_values = range(48)
    parser.add_argument('-p', '--past', type=int, choices=valid_values, metavar=f"[{min(valid_values)}-{max(valid_values)}]", default=23,
                        help="Maximum number of negative relative entries to send for the past. 0 to disable. E.g. '3' will result in -03, -02 and -01 being sent.")

    valid_values = range(10000)
    parser.add_argument('--history-length', type=int, choices=valid_values, metavar=f"[{min(valid_values)}-{max(valid_values)}]", default=365,
                        help="The number of history entries (days) to store.")

    parser.add_argument('--time-shift', type=int, default=30,
                        help="Modify system time to be slightly ahead or behind the correct time. This allows the miniserver to have the correct time available at the hour tick")

    args = parser.parse_args()
    global_time_compensation_seconds = args.time_shift

    logger.setLevel(choice_map[args.log])

    logger.info("Realtime: " + str(datetime.datetime.now()))
    logger.info("Time offset: " + str(global_time_compensation_seconds) + " [s]")
    logger.info("Using faketime: " + str(faketime_now()))

    config = load_or_create_json_config(os.path.join(script_dir, args.config), skip_destination_ping=args.no_ping_check)

    tibber_account = tibber.Account(config["token"])
    # tibber_account.send_push_notification("My title", "Hello! I'm a message!")

    time_dict = get_time_dictionary()
    price_dict = get_price_dictionary(tibber_account, config["home_id"], args.price_unit == "EUR", no_invalid_fields=args.no_invalid_fields,
                                      invalid_data_value=args.invalid_data_value, use_cache=not args.no_yesterday_cache,
                                      number_of_positive_relative_data=args.future, number_of_negative_relative_data=args.past, history_length=args.history_length)

    power_dict = get_power_dictionary(tibber_account, config)

    information_to_be_sent = merge_dictionaries([time_dict, price_dict, power_dict])

    send_to_destination(config, information_to_be_sent)
