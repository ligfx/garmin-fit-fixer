from garminfit import *
import sys

# def semicircles_to_degrees(semicircles):
#     return semicircles * ( 180 / (2 ** 31 ))
#
#
# from math import sin, cos, sqrt, atan2, radians
#
# def geodistance_meters(first, second):
#     # approximate radius of earth in meters
#     R = 6373000
#
#     lat1 = radians(first[0])
#     lon1 = radians(first[1])
#     lat2 = radians(second[0])
#     lon2 = radians(second[1])
#
#     dlon = lon2 - lon1
#     dlat = lat2 - lat1
#
#     a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
#     c = 2 * atan2(sqrt(a), sqrt(1 - a))
#
#     distance = R * c
#     return distance
#
def main():

    # print(geodistance_meters((semicircles_to_degrees(510118987), semicircles_to_degrees(-1007628433)), (semicircles_to_degrees(-805322948), semicircles_to_degrees(-805323008))))

    def my_checks():
        return [
            CheckMonotonicallyIncreasingRecordTimestamps(),
            CheckNoCompressedAndNormalTimestamps(),
            CheckFileIdExistsAndIsFirst(),
            CheckOnlyOneFileId(),
        ]

    input_filename = sys.argv[1]

    with open(input_filename, "rb") as f:
        reader = FitReader(f, additional_checks=my_checks())
        print(reader.read_file_header())

        while reader.should_read_message():
            last_good_file_position = f.tell()
            try:
                message_header = reader.read_message_header()
                print(message_header)
                message = reader.read_message_content(message_header)
                print(message)
            except BadFitFileException as e:
                print("* At position %i: %s" % (f.tell(), e))
                exit(1)
        print(reader.read_file_footer())

    return None


if __name__ == "__main__":
    main()
