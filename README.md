# TibberLox

## Deutsch
Hierbei handelt es sich um ein kleines Hile-Skript um die Tibber Api auszulesen und per UDP weiter zu senden. Spziell hilfreich ist dies für Loxone, da das Auslesen der Tibber `graphql`-API nicht nativ in der Loxone unterstützt wird. Das Script wandelt die gelesenen Informationen in UDP-Befehle um, die der Beschreibung https://loxwiki.atlassian.net/wiki/spaces/LOX/pages/1522696197/Anbinden+der+aWATTar+hourly+API entsprechen.

### Installation
Zunächst die python version testen. Das Script funktioniert nur mit `python3.9` oder höher. Diese Abhänigkeit kommt nicht aus der Programmierung des Scriptes, sondern von der Library https://github.com/BeatsuDev/tibber.py.

``` bash
❯ python3 --version
Python 3.10.8  # Muss größer oder gleich 3.9 sein!
```

Installation der Abhängigkeit https://pypi.org/project/tibber.py:
``` bash
❯ pip3 install tibber.py
```

Python Pfad identifizieren:
``` bash
❯ which python3
/usr/bin/python3
```

Cronjob anlegen:
``` bash
❯ crontab -e
```

und im Textfeld folgende Zeile einfügen. Der Python Pfad muss mit dem Output von `which python3` übereinstimmen, ebenso der Pfad zum heruntergeladenen Pythonfile `tibberlox.py`.
```
*/30 * * * * /usr/bin/python3 /home/jacknjo/TibberLox/tibberlox.py
```

### Konfiguration
Das Script fragt beim ersten Start nach den Konfigurationsparametern, die für den Zugang zur Tibber-API notwendig sind. Ebenso müssen IP und Port der Zieladresse angegeben werden. Die Informationen werden unter Zugangscode `0400` schreibgeschützt und nur für den Nutzer lesbar auf dem Dateisystem parallel zum `tibberlox.py` Skript unter dem Namen `.tibberlox_config` abgelegt.

Die Datei `.tibberlox_config` kann auch manuell von `demo_tibberlox_config` kopiert, modifiziert und unter dem Namen `.tibberlox_config` abgelegt werden. Damit kann der Konfigurationsschritt umgangen werden.

### Manuelle Benutzung

``` bash
# Ausführbarmachen des scriptes.
chmod +x tibberlox.py

# Ausführung mit default-Parametern.
./tibberlox.py

# Oder für mehr/weniger logging-Informationen.
./tibberlox.py -l DEBUG

# Alternativ für die Hilfe.
./tibberlox.py -h
```

### Benutzung in Loxone
Im Repository ist die `VUI_tibberlox.xml` hinterlegt. Diese beinhaltet alle Werte, die vom Skript gesendet werden. Der Großteil der Werte entspricht der API-Beschreibung von: https://loxwiki.atlassian.net/wiki/spaces/LOX/pages/1522696197/Anbinden+der+aWATTar+hourly+API

Die folgenden Elemente wurden zusätzlich hinzugefügt:
- `date_now_seconds_since_epoch` Kann als Trigger/Zeitstempel verwendet werden.
- `price_stdev` Standardabweichung der Preise des aktuellen Tages
- `data_price_hour_rel_num_negatives` Anzahl der validen negativen Relativwerte (invalide Werte tragen den Wert -1000).
- `data_price_hour_rel_num_positives` Anzahl der validen positiven Relativwerte (invalide Werte tragen den Wert -1000).
- `price_multiplicator_to_eur` Multiplicator um die per UDP empfangenen Preiswerte in EURO umzurechnen.


## English
This is a small helper script that reads the tibber API and forwards the information read to a remote destination. This can be used for a Loxone Miniserver, as the functionality to receive information via `graphql`-API is not given natively. The UDP datagram contains one big packed package with the information as specified here: https://loxwiki.atlassian.net/wiki/spaces/LOX/pages/1522696197/Anbinden+der+aWATTar+hourly+API.

### Installation
First of all you need to test your python version, as the script only works for `python3.9` or higher. This dependency is injected by the https://github.com/BeatsuDev/tibber.py module.

``` bash
❯ python3 --version
Python 3.10.8  # Needs to be >= 3.9
```

Installation of the dependency https://pypi.org/project/tibber.py:
``` bash
❯ pip3 install tibber.py
```

Identify the python path
``` bash
❯ which python3
/usr/bin/python3
```

Create a cronjob:
``` bash
❯ crontab -e
```

In the promt add the following line. Attention! The python path must match the output of `which python3`, as must the absolute path to the pythonfile `tibberlox.py`.
```
*/30 * * * * /usr/bin/python3 /home/jacknjo/TibberLox/tibberlox.py
```

### Configuration
At first invocation the script prompts for configuration parameters necessary for the runtime. These include the Tibber-API Token as the destination ip and port touple(s). Those settings will be saved in a file called `.tibberlox_config` parallel to the `tibberlox.py`-script with access modifier `0400` in a write protected manner and only readable to the user.

If you want to skip the configuration process, just copy the `demo_tibberlox_config` modify the fields as desired and write it to `.tibberlox_config` next to the `tibberlox.py` script. As long as this file exists and is readable, the prompt will not show up.


### Manual Usage

``` bash
# First make the script executable.
chmod +x tibberlox.py

# Run with default options.
./tibberlox.py

# For more/less verbosity.
./tibberlox.py -l DEBUG

# To read the help.
./tibberlox.py -h
```

### Usage in Loxone

In the repository you find the file `VUI_tibberlox.xml`. This contains the library definition of all values sent by the script. This is mainly as documented in https://loxwiki.atlassian.net/wiki/spaces/LOX/pages/1522696197/Anbinden+der+aWATTar+hourly+API.

The following elements were added in addition:
- `date_now_seconds_since_epoch` Can be used as trigger for new data.
- `price_stdev` Standard deviation of the prices from the current day.
- `data_price_hour_rel_num_negatives` Number of valid negative relative values (invalid values carry value -1000).
- `data_price_hour_rel_num_positives` Number of valid positive relative values (invalid values carry value -1000).
