import os
import sys
from zipfile import BadZipFile, ZipFile
from tarfile import open as tar_open
from tarfile import CompressionError, ReadError
import zlib


ZIP_EXTENSIONS = {".jar", ".war", ".sar", ".ear", ".par", ".zip", ".apk"}
TAR_EXTENSIONS = {".tar.gz", ".tar"}


def examine_class(rel_path, file_name, content, silent_mode) -> bool:
    if b"withECDSA" in content:
        print ("In {}/{} potential use of ECDSA - may be vulnerable".format(rel_path, file_name))
        return True

    return False


def zip_file(file, rel_path: str, silent_mode: bool) -> bool:
    problem_found = False
    try:
        with ZipFile(file) as jarfile:
            for file_name in jarfile.namelist():
                if acceptable_filename(file_name):
                    with jarfile.open(file_name, "r") as next_file:
                        problem_found |= test_file(
                            next_file, os.path.join(rel_path, file_name), silent_mode
                        )
                        continue
                if file_name.endswith(".class") and not file_name.endswith(
                    "module-info.class"
                ):
                    content = jarfile.read(file_name)
                    problem_found |= examine_class(
                        rel_path, file_name, content, silent_mode
                    )

            # went over all the files in the current layer; draw conclusions
    except (IOError, BadZipFile, UnicodeDecodeError, zlib.error, RuntimeError) as e:
        if not silent_mode:
            print(rel_path + ": " + str(e))
    return problem_found


def tar_file(file, rel_path: str, silent_mode: bool) -> bool:
    problem_found = False
    try:
        with tar_open(fileobj=file) as tarfile:
            for item in tarfile.getmembers():
                if "../" in item.name:
                    continue
                if item.isfile() and acceptable_filename(item.name):
                    fileobj = tarfile.extractfile(item)
                    new_path = rel_path + "/" + item.name
                    problem_found |= test_file(fileobj, new_path, silent_mode)

    except (
        IOError,
        FileExistsError,
        CompressionError,
        ReadError,
        RuntimeError,
        UnicodeDecodeError,
        zlib.error,
    ) as e:
        if not silent_mode:
            print(rel_path + ": " + str(e))
        return False
    return problem_found


def test_file(file, rel_path: str, silent_mode: bool) -> bool:
    if any(rel_path.endswith(ext) for ext in ZIP_EXTENSIONS):
        return zip_file(file, rel_path, silent_mode)

    elif any(rel_path.endswith(ext) for ext in TAR_EXTENSIONS):
        return tar_file(file, rel_path, silent_mode)
    return False


def acceptable_filename(filename: str):
    return any(filename.endswith(ext) for ext in ZIP_EXTENSIONS | TAR_EXTENSIONS)


def run_scanner(root_dir: str, exclude_dirs, silent_mode: bool) -> bool:
    problem_found = False
    if os.path.isdir(root_dir):
        for directory, dirs, files in os.walk(root_dir, topdown=True):
            [
                dirs.remove(excluded_dir)
                for excluded_dir in list(dirs)
                if os.path.join(directory, excluded_dir) in exclude_dirs
            ]

            for filename in files:
                if acceptable_filename(filename):
                    full_path = os.path.join(directory, filename)
                    rel_path = os.path.relpath(full_path, root_dir)
                    try:
                        with open(full_path, "rb") as file:
                            problem_found |= test_file(file, rel_path, silent_mode)
                    except FileNotFoundError as fnf_error:
                        if not silent_mode:
                            print(fnf_error)
    elif os.path.isfile(root_dir):
        if acceptable_filename(root_dir):
            with open(root_dir, "rb") as file:
                if any(root_dir.endswith(ext) for ext in ZIP_EXTENSIONS):
                    problem_found = zip_file(file, "", silent_mode)

                elif any(root_dir.endswith(ext) for ext in TAR_EXTENSIONS):
                    problem_found = tar_file(file, "", silent_mode)
    return problem_found


def print_usage():
    print(
        "Usage: "
        + sys.argv[0]
        + " <root_folder> [-quiet] [-exclude <folder1> <folder2> ...]"
    )
    print("or: " + sys.argv[0] + "<archive_file> [-quiet]")
    exit()


def parse_command_line():
    if len(sys.argv) < 2:
        print_usage()

    root_dir = sys.argv[1]
    exclude_folders = []

    silent = len(sys.argv) > 2 and sys.argv[2] == "-quiet"
    exclude_start = 3 if silent else 2
    if len(sys.argv) > exclude_start:
        if not sys.argv[exclude_start] == "-exclude":
            print_usage()
        exclude_folders = sys.argv[exclude_start + 1 :]

    return root_dir, exclude_folders, silent


if __name__ == "__main__":
    root_dir, exclude_dirs, silent_mode = parse_command_line()

    for dir_to_check in exclude_dirs:
        if not os.path.isdir(dir_to_check):
            print(dir_to_check + " is not a directory")
            print_usage()
    if not os.path.isdir(root_dir) and not (
        os.path.isfile(root_dir) and acceptable_filename(root_dir)
    ):
        print(root_dir + " is not a directory or an archive")
        print_usage()

    print("Scanning " + root_dir)
    if exclude_dirs:
        print("Excluded: " + ", ".join(exclude_dirs))

    problem_found = run_scanner(root_dir, set(exclude_dirs), silent_mode)
    if problem_found:
        sys.exit(1)
