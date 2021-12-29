from garminfit import *
from garminfit import _read_exact, _write_uint8, _write_uint16le, _write_uint32le
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
            CheckOnlyOneFileCreator(),
            CheckOnlyOneUserData(),
        ]

    input_filename = sys.argv[1]
    skips = []

    with open(input_filename, "rb") as f:
        reader = FitReader(f, additional_checks=my_checks())
        print(reader.read_file_header())
        tentative_messages = []
        last_good_file_position = f.tell()

        bytes_to_skip = 0
        while reader.should_read_message():
            try:
                message_header = reader.read_message_header()
                message = reader.read_message_content(message_header)

                if bytes_to_skip:
                    print("* Tentative parse: %r" % message)
                    tentative_messages.append(message)
                    if len(tentative_messages) >= 10:
                        print("* Found a solution, skipping %i bytes" % bytes_to_skip)
                        skips.append((last_good_file_position, bytes_to_skip))
                        for message in tentative_messages:
                            print(message)
                        last_good_file_position = f.tell()
                        tentative_messages = []
                        bytes_to_skip = 0
                else:
                    print(message)
                    last_good_file_position = f.tell()

            except BadFitFileException as e:
                print(
                    "* Starting from %i, error at position %i: %s"
                    % (last_good_file_position + bytes_to_skip, f.tell(), e)
                )
                if not bytes_to_skip:
                    print("* Searching for viable restart point...")
                tentative_messages = []
                bytes_to_skip += 1
                f.seek(last_good_file_position + bytes_to_skip)
        print(reader.read_file_footer())

    if not skips:
        print("* File looks good!")

    for (position, num_bytes) in skips:
        print("* Need to skip %i bytes at position %i" % (num_bytes, position))

    if len(sys.argv) > 2:
        output_filename = sys.argv[2]

        new_data = b""
        with open(sys.argv[1], "rb") as f:
            header = FitReader(f).read_file_header()
            for (position, num_bytes) in skips:
                new_data += _read_exact(f, position - f.tell())
                _read_exact(f, num_bytes)
            new_data += _read_exact(f, header.data_size + header.header_size - f.tell())
            assert len(new_data) == header.data_size - sum(_[1] for _ in skips)

        out = io.BytesIO()
        _write_uint8(out, header.header_size)
        _write_uint8(out, header.protocol_version)
        _write_uint16le(out, header.profile_version)
        _write_uint32le(out, len(new_data))
        out.write(b".FIT")
        _write_uint16le(out, 0)  # header crc
        out.write(new_data)

        data_crc = crc16(out.getvalue())
        _write_uint16le(out, data_crc)

        print("* Writing %s" % output_filename)
        with open(output_filename, "wb") as f:
            f.write(out.getvalue())


if __name__ == "__main__":
    main()
