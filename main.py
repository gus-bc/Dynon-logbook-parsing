#!/usr/bin/env python3
import os
import sys
import csv
import json
from haversine import haversine
import argparse


METERS_PER_FOOT = 0.3048


class CsvFile:
    def __init__(self):
        self.text = ""

    def __repr__(self):
        return self.text

    def write(self, s: str):
        self.text += s


class Config:

    def __init__(self, **kwargs):
        """
        Create a config object consisting of key/value pairs.
        Each dictionary key becomes a member of this object
        :param kwargs: key/value pairs to use as member variables
        """
        for k, v in kwargs.items():
            setattr(self, k, v)


def csv_to_json(s):
    return json.dumps(list(csv.DictReader(s.splitlines(), delimiter=",")))


def get_session_list(cfg) -> list:
    session_list = list()

    csv_row_index = 0

    # read a CSV file as a dictionary
    with open(cfg.csv_input_filename, newline='') as csv_file:
        csv_reader = csv.DictReader(csv_file)

        last_session_time = -1.0

        for csv_row in csv_reader:
            # read the session times
            session_time = csv_row['Session Time']

            # continue if the session time is blank
            if not session_time:
                continue

            # convert it to a number
            session_time = float(session_time)

            # if this is the first session or the session time went backwards,
            # it must be a new session
            if (csv_row_index == 0) or (session_time < last_session_time):
                session_list.append(csv_row_index)

            last_session_time = session_time
            csv_row_index += 1

        # add a final entry at the end so consumers know when to stop
        # this final entry does not mark the start of a new session
        session_list.append(csv_row_index)
    return session_list


def convert_userdatalog_csv_trip_log(cfg):
    # note: the last index in this list is not the start of a new session
    # it only marks the end of the very last session
    session_list = get_session_list(cfg)
    if not session_list:
        print('Empty session index. Is the input file empty?')
        return

    session_index = 0
    csv_row_index = 0

    output = CsvFile()
    output.write("start_date_time, end_date_time, end of trip hobbs time, start_waypoint, end_waypoint\n")

    # read a CSV file as a dictionary
    with open(cfg.csv_input_filename, newline='') as csv_file:
        csv_reader = csv.DictReader(csv_file)

        for csv_row in csv_reader:
            # we are at the start of a new session
            if session_list[session_index] == csv_row_index:
                # start a new session list
                session_data = []

            data = generate_data_dict(cfg, csv_row)
            # print(data)
            if data is None:
                pass
            else:
                # print(data)
                session_data.append(data)
                # print(session_data)

            if session_data:
                if session_list[session_index+1] == csv_row_index+1:
                    hobbs = session_data[-1]['Hobbs Time']
                    start_waypoint = check_waypoint(cfg, session_data[0]['Latitude'], session_data[0]['Longitude'])
                    end_waypoint = check_waypoint(cfg, session_data[-1]['Latitude'], session_data[-1]['Longitude'])
                    start_date_time = session_data[0]['GPS Date & Time']
                    end_date_time = session_data[-1]['GPS Date & Time']
                    session_log = f"{start_date_time}," \
                                  f"{end_date_time}," \
                                  f"{hobbs}," \
                                  f"{start_waypoint}," \
                                  f"{end_waypoint} \n"

                    output.write(session_log)
                    session_index += 1

                csv_row_index += 1

    if cfg.output_type == 'json':
        return csv_to_json(output.text)
    else:
        return output.text


def generate_data_dict(cfg, csv_row):
    fix_quality = csv_row['GPS Fix Quality']
    num_sats = csv_row['Number of Satellites']
    date_and_time = csv_row['GPS Date & Time']

    # skip the row if these entries are blank
    if not fix_quality or not num_sats or not date_and_time:
        # print("fix_quality and/or number of satelites was missing from data")
        return None

    # skip the row if the quality is low
    # print("fix_quality and/or number of satelites was too low")
    if (int(fix_quality) < cfg.min_fix_quality) or (int(num_sats) < cfg.min_satellites):
        return None

    lat = csv_row['Latitude (deg)']
    lon = csv_row['Longitude (deg)']
    alt = csv_row['GPS Altitude (feet)']
    hobbs = csv_row["Hobbs Time"]
    time_date = csv_row["GPS Date & Time"]

    # skip the row if any of these fields are missing
    if not lat or not lon or not alt or not hobbs or not time_date:
        # print("File does not contain Latitude (deg), Longitude (deg), GPS Altitude (feet), Hobbs Time and/or GPS Date & Time information.")
        return None

    # convert altitude from feet to meters
    alt_meters = str(float(alt) * METERS_PER_FOOT)

    data_dict = {'Latitude': lat,
                 'Longitude': lon,
                 'Altitude_meter': alt_meters,
                 'Hobbs Time': hobbs,
                 'GPS Date & Time': time_date}
    return data_dict


def check_waypoint(cfg, lat, lon):
    accepted_error_meter = 1000
    loc1 = (float(lat), float(lon))

    with open(cfg.csv_waypoint_file, newline='') as waypoint_file:
        csv_reader = csv.DictReader(waypoint_file)

        for csv_row in csv_reader:
            w_lat = float(csv_row['Latitude'])
            w_lon = float(csv_row['Longitude'])
            loc2 = (w_lat, w_lon)
            if float(haversine(loc2, loc1, unit='m')) < float(accepted_error_meter):
                return csv_row['Short Name']
    return f"{lat}/{lon}"


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--user_data_log', type=str, required=True, help="Path to user_data_log")
    parser.add_argument('-w', '--user_waypoints', type=str, required=True, help="Path to user_waypoints")
    parser.add_argument('-f', '--output_type', type=str, required=True, help="Choose between 'csv' or 'json'")
    args = parser.parse_args()

    csv_input_filename = args.user_data_log
    csv_waypoint_file = args.user_waypoints
    output_type = args.output_type

    if not os.path.exists(csv_input_filename):
        print('File [{csv_file}] does not exist!'.format(csv_file=csv_input_filename))
        return 1

    cfg = Config(
        csv_input_filename=csv_input_filename,
        delete_output_dir_on_start=True,
        min_fix_quality=1,
        min_satellites=4,
        csv_waypoint_file=csv_waypoint_file,
        output_type=output_type
    )
    print(convert_userdatalog_csv_trip_log(cfg))
    return 0


if __name__ == '__main__':

    exit_code = main()
    sys.exit(exit_code)
