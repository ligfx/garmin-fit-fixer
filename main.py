from garminfit import *
from garminfit import _read_exact, _write_uint8, _write_uint16le, _write_uint32le
import sys


def main():
    def my_checks():
        return [
            CheckMonotonicallyIncreasingRecordTimestamps(),
            CheckNoCompressedAndNormalTimestamps(),
            CheckFileIdExistsAndIsFirst(),
            CheckOnlyOneFileId(),
        ]

    input_filename = sys.argv[1]

    def find_good_up_to():
        with open(input_filename, "rb") as f:
            reader = FitReader(f, additional_checks=my_checks())
            reader.read_file_header()

            while reader.should_read_message():
                last_good_file_position = f.tell()
                try:
                    message_header = reader.read_message_header()
                    message = reader.read_message_content(message_header)
                except BadFitFileException as e:
                    print("* At position %i: %s" % (f.tell(), e))
                    return last_good_file_position
            reader.read_file_footer()
        return None

    corruption_start = find_good_up_to()
    if not corruption_start:
        print("* File looks good!")
        exit(0)
    print("* Found start of corrupted data: %i" % corruption_start)

    def try_with_skip(f, place_to_skip, bytes_to_skip):
        reader = FitReader(f, additional_checks=my_checks())
        reader.read_file_header()

        while reader.should_read_message():
            if f.tell() == place_to_skip:
                _read_exact(f, bytes_to_skip)
            message_header = reader.read_message_header()
            message = reader.read_message_content(message_header)
        reader.read_file_footer()

    for corruption_length in range(1, 100000):
        with open(input_filename, "rb") as f:
            try:
                try_with_skip(f, corruption_start, corruption_length)
                break
            except BadFitFileException as e:
                print(
                    "* Skipping %i bytes: At position %i: %s"
                    % (corruption_length, f.tell(), e)
                )

    print("* Skipping %i bytes: success!" % corruption_length)
    print("* Found length of corrupted data: %i" % corruption_length)

    if len(sys.argv) > 2:
        output_filename = sys.argv[2]

        new_data = b""
        with open(sys.argv[1], "rb") as f:
            header = FitReader(f).read_file_header()

            new_data += _read_exact(f, corruption_start - f.tell())
            _read_exact(f, corruption_length)
            new_data += _read_exact(
                f,
                header.data_size
                + header.header_size
                - corruption_start
                - corruption_length,
            )

            assert len(new_data) == header.data_size - corruption_length

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
